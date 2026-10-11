"""Текстовый PDF заполняет поля с source=resume и пересчитывает категорию.

ТЗ §2.1 «загрузка PDF с автораспознаванием».
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import product
from product.matching.pdf_profile import render_profile_pdf
from product.matching.resume import read_resume_bytes
from product.tests.conftest import register_and_confirm, take_test

_PROFILE = {
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "specialization": "backend",
    "grade": "middle",
    "stack": ["python"],
    "team_role": "разработчик",
    "work_format": "удалённо",
    "experience": "синтетический стаж",
    "soft_skills": ["коммуникация"],
    "publication": True,
}
_GOLDEN = Path(product.__file__).resolve().parent / "matching" / "golden" / "resumes"
_LIMIT = 2 * 1024 * 1024


def _seeker(client, email: str = "resume@example.com") -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json=_PROFILE)
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _stamp(client, profile_id: int) -> str:
    with sqlite3.connect(client.db_path) as db:
        return db.execute("select grade_changed_at from profiles where id = ?", (profile_id,)).fetchone()[0]


def _achievements(client) -> int:
    with sqlite3.connect(client.db_path) as db:
        return db.execute("select count(*) from fsp_achievements").fetchone()[0]


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]




def test_reader_keeps_known_fields_and_reports_bad_files():
    root = Path(product.matching.resume.__file__).resolve().parent
    for name in ("resume.py", "pdf_profile.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(name.split(".")[0] != "sqlalchemy" for name in names)
    full = read_resume_bytes((_GOLDEN / "full.pdf").read_bytes())
    assert "error" not in full
    assert full["full_name"] == "Анна Синтетикова"
    assert full["stack"] == ["python", "go"]
    assert full["industry"] == "it"
    assert full["specialization"] == "backend"
    assert full["grade"] == "senior"
    assert full["team_role"] == "разработчик"
    assert full["work_format"] == "удалённо"
    assert full["experience"] == "четыре года в контуре"
    assert full["soft_skills"] == ["коммуникация", "менторство"]
    partial = read_resume_bytes((_GOLDEN / "partial.pdf").read_bytes())
    assert "error" not in partial
    assert partial["full_name"] == "Пётр Черновик"
    assert partial["experience"] == "год практики"
    assert "industry" not in partial
    assert "specialization" not in partial
    assert "stack" not in partial
    assert read_resume_bytes((_GOLDEN / "empty.pdf").read_bytes())["error"] == "resume_no_text"
    assert read_resume_bytes((_GOLDEN / "notes.pdf").read_bytes())["error"] == "resume_not_pdf"
    huge = b"%PDF-1.4\n" + b"0" * _LIMIT
    assert read_resume_bytes(huge)["error"] == "resume_too_large"
    sheet = render_profile_pdf(
        {
            "full_name": "Иван",
            "industry": "it",
            "category_id": "backend:middle",
            "specialization": "backend",
            "grade": "middle",
            "stack": ["python"],
            "team_role": "разработчик",
            "work_format": "удалённо",
            "experience": "стаж",
            "soft_skills": ["коммуникация"],
        }
    )
    assert sheet.startswith(b"%PDF")
    assert b"JetBrainsMono" in sheet
    again = render_profile_pdf({"full_name": "Иван", "industry": "it", "category_id": "backend:middle"})
    assert again.startswith(b"%PDF")


def test_upload_writes_resume_source_without_category_or_fsp(client):
    register_and_confirm(client, email="plain@example.com")
    missing = client.post(
        "/api/candidate/resume",
        files={"file": ("notes.pdf", b"not a pdf", "application/pdf")},
    )
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    profile_id = _seeker(client)
    stamp = _stamp(client, profile_id)
    before = client.get("/api/candidate/category").json()
    assert before["category_id"] == "backend:middle"
    achievements = _achievements(client)
    stored = client.post(
        "/api/candidate/resume",
        files={"file": ("full.pdf", (_GOLDEN / "full.pdf").read_bytes(), "application/pdf")},
    )
    assert stored.status_code == 200, stored.text
    body = stored.json()
    assert body["grade"] == "senior"
    assert body["grade_skipped"] is False
    assert "error" not in body
    assert body["category_id"] == "backend:senior"
    assert "it" not in body["category_id"]
    assert body["field_sources"]["grade"] == "resume"
    assert body["field_sources"]["full_name"] == "resume"
    assert body["field_sources"]["stack"] == "resume"
    assert body["full_name"] == "Анна Синтетикова"
    assert body["stack"] == ["python", "go"]
    assert body["experience"] == "четыре года в контуре"
    assert _stamp(client, profile_id) == stamp
    assert _achievements(client) == achievements
    assert client.get("/api/candidate/category").json()["category_id"] == "backend:senior"
    assert "Тест ещё не сдан" in client.get("/api/candidate/category").json()["explanation"]
    kept = client.post(
        "/api/candidate/resume",
        files={"file": ("partial.pdf", (_GOLDEN / "partial.pdf").read_bytes(), "application/pdf")},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["industry"] == "it"
    assert kept.json()["specialization"] == "backend"
    assert kept.json()["stack"] == ["python", "go"]
    assert kept.json()["experience"] == "год практики"
    assert kept.json()["field_sources"]["experience"] == "resume"
    assert kept.json()["field_sources"]["industry"] == "resume"
    empty = client.post(
        "/api/candidate/resume",
        files={"file": ("empty.pdf", (_GOLDEN / "empty.pdf").read_bytes(), "application/pdf")},
    )
    assert empty.status_code == 422
    assert empty.json()["error"] == "resume_no_text"
    assert client.get("/api/candidate/profile").json()["experience"] == "год практики"
    huge = b"%PDF-1.4\n" + b"0" * _LIMIT
    large = client.post("/api/candidate/resume", files={"file": ("big.pdf", huge, "application/pdf")})
    assert large.status_code == 413
    assert large.json()["error"] == "resume_too_large"
    naked = client.post("/api/candidate/resume")
    assert naked.status_code == 422
    assert naked.json()["error"] == "resume_not_pdf"


def test_pdf_grade_stops_after_the_test_and_profile_pdf_stays_separate(client):
    profile_id = _seeker(client, "tested@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    submitted = take_test(client, started.json(), "confirm")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["grade"] == "middle"
    stored = client.post(
        "/api/candidate/resume",
        files={"file": ("full.pdf", (_GOLDEN / "full.pdf").read_bytes(), "application/pdf")},
    )
    assert stored.status_code == 200, stored.text
    body = stored.json()
    assert body["grade"] == "middle"
    assert body["grade_skipped"] is True
    assert body["error"] == "grade_via_test"
    assert body["category_id"] == "backend:middle"
    assert body["experience"] == "четыре года в контуре"
    assert body["field_sources"]["experience"] == "resume"
    assert body["field_sources"]["grade"] == "form"
    same = render_profile_pdf({"industry": "it", "category_id": "backend:middle", "grade": "middle"})
    assert b"JetBrainsMono" in same
    downloaded = client.get("/api/candidate/profile.pdf")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.content.startswith(b"%PDF")
    assert b"JetBrainsMono" in downloaded.content
    from pypdf import PdfReader
    from io import BytesIO

    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(downloaded.content)).pages)
    assert "Отрасль: it" in text
    assert "Категория: backend:middle" in text
    assert "it:backend" not in text
    assert "it/backend" not in text
    assert "Грейд: middle" in text
    register_and_confirm(client, email="boss-resume@example.com", role="employer")
    denied = client.post(
        "/api/candidate/resume",
        files={"file": ("full.pdf", (_GOLDEN / "full.pdf").read_bytes(), "application/pdf")},
    )
    assert denied.status_code == 403
    assert denied.json()["error"] == "forbidden"
    assert client.get("/api/candidate/profile.pdf").status_code == 403


def test_same_grade_pdf_does_not_rewrite_source(client):
    profile_id = _seeker(client, "same-grade@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    submitted = take_test(client, started.json(), "confirm")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["grade"] == "middle"
    stamp = _stamp(client, profile_id)
    sheet = render_profile_pdf(
        {
            "full_name": "Иван Синтетиков",
            "industry": "it",
            "specialization": "backend",
            "grade": "middle",
            "experience": "стаж после совпавшего грейда",
        }
    )
    stored = client.post(
        "/api/candidate/resume",
        files={"file": ("same.pdf", sheet, "application/pdf")},
    )
    assert stored.status_code == 200, stored.text
    body = stored.json()
    assert body["grade"] == "middle"
    assert body["grade_skipped"] is False
    assert "error" not in body
    assert body["field_sources"]["grade"] == "form"
    assert body["experience"] == "стаж после совпавшего грейда"
    assert body["field_sources"]["experience"] == "resume"
    assert body["category_id"] == "backend:middle"
    assert _stamp(client, profile_id) == stamp


def test_cabinet_form_shows_resume_source(client):
    anon = client.get("/candidate", follow_redirects=False)
    assert anon.status_code == 303
    _seeker(client, "page-resume@example.com")
    page = client.get("/candidate")
    assert "Из резюме поля ещё не заполнялись." in page.text
    assert "Загрузить резюме" in page.text
    assert "PDF профиля" in page.text
    sent = client.post(
        "/candidate/resume",
        data={"csrf": _csrf(page.text)},
        files={"file": ("full.pdf", (_GOLDEN / "full.pdf").read_bytes(), "application/pdf")},
        follow_redirects=False,
    )
    assert sent.status_code == 303
    again = client.get("/candidate")
    assert "Из резюме:" in again.text
    assert "Анна Синтетикова" in again.text
    assert "Разряд источника" not in again.text.split("Резюме", 1)[1]
    broken = client.post(
        "/candidate/resume",
        data={"csrf": _csrf(again.text)},
        files={"file": ("empty.pdf", (_GOLDEN / "empty.pdf").read_bytes(), "application/pdf")},
    )
    assert broken.status_code == 422
    assert "текстового слоя" in broken.text


def test_oversized_resume_stops_before_the_whole_file(client, monkeypatch):
    from starlette.requests import Request

    _seeker(client, "cap-read@example.com")
    pulled = {"n": 0}
    original = Request.stream
    step = 32 * 1024

    def stream(self):
        async def pieces():
            async for chunk in original(self):
                for offset in range(0, len(chunk), step):
                    piece = chunk[offset : offset + step]
                    pulled["n"] += len(piece)
                    yield piece

        return pieces()

    monkeypatch.setattr(Request, "stream", stream)
    huge = b"%PDF-1.4\n" + b"0" * (_LIMIT + 512 * 1024)
    large = client.post("/api/candidate/resume", files={"file": ("big.pdf", huge, "application/pdf")})
    assert large.status_code == 413
    assert large.json()["error"] == "resume_too_large"
    assert 0 < pulled["n"] <= _LIMIT + 128 * 1024
    assert pulled["n"] < len(huge)
    pulled["n"] = 0
    page = client.get("/candidate")
    sent = client.post(
        "/candidate/resume",
        data={"csrf": _csrf(page.text)},
        files={"file": ("big.pdf", huge, "application/pdf")},
    )
    assert sent.status_code == 413
    assert "2 МиБ" in sent.text
    assert 0 < pulled["n"] <= _LIMIT + 128 * 1024
    assert pulled["n"] < len(huge)
