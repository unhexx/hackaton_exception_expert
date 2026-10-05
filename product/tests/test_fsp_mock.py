"""Мок ФСП: разряд строкой, пустая история, повторный seed без второй строки."""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

import product
from product.app.db.session import open_session
from product.fsp_mock.adapter import CANONICAL_DISCIPLINES, discipline_label
from product.fsp_mock.client import JsonFspClient
from product.fsp_mock.load import load_into
from product.fsp_mock.read import achievements_for
from product.seed import init_db
from product.tests.conftest import register_and_confirm

_PROFILE = {
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "specialization": "backend",
    "grade": "middle",
    "stack": ["python"],
    "team_role": "разработчик",
    "work_format": "удалённо",
    "experience": "3 года",
    "soft_skills": ["коммуникация"],
    "publication": True,
}


def _section(html: str) -> str:
    start = html.index('<section id="achievements">')
    end = html.index("</section>", start)
    return html[start:end]


def test_json_keeps_rank_and_adapts_discipline():
    path = Path(product.__file__).resolve().parent / "fsp_mock" / "participants.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    by_id = {row["external_id"]: row for row in raw["participants"]}
    assert by_id["fsp-synth-1"]["display_name"] == "Иван Синтетиков"
    assert by_id["fsp-synth-1"]["rank"] == "I"
    assert by_id["fsp-synth-1"]["results"][0]["discipline"] == "алгоритмика"
    assert by_id["fsp-synth-1"]["results"][0]["place"] == "2"
    assert by_id["fsp-synth-2"]["rank"] == "КМС"
    assert by_id["fsp-synth-2"]["results"] == []
    assert by_id["fsp-synth-3"]["rank"] == "вне списка"
    assert by_id["fsp-synth-3"]["results"][0]["place"] == "1"

    ivan = JsonFspClient().get_participant("fsp-synth-1")
    assert ivan is not None
    assert ivan["rank"] == "I"
    assert {row["discipline"] for row in ivan["results"]} == set(CANONICAL_DISCIPLINES)
    assert {row["role_in_team"] for row in ivan["results"]} >= {
        "капитан",
        "участник хакатона",
        "разработчик задачи",
    }
    maria = JsonFspClient().get_participant("fsp-synth-2")
    assert maria is not None
    assert maria["results"] == []
    petr = JsonFspClient().get_participant("fsp-synth-3")
    assert petr is not None
    assert petr["rank"] == "вне списка"
    assert petr["results"][0]["discipline"] == "Квест выходного дня"
    assert petr["results"][0]["place"] == "1"
    assert JsonFspClient().get_participant("fsp-no-such") is None
    assert discipline_label("алгоритмика") == "Программирование алгоритмическое"
    assert discipline_label("Продуктовое программирование") == "Продуктовое программирование"


def test_unknown_id_is_empty_history():
    assert achievements_for(None) == {"display_name": "", "rank": "", "results": []}
    assert achievements_for("") == {"display_name": "", "rank": "", "results": []}
    assert achievements_for("fsp-no-such") == {"display_name": "", "rank": "", "results": []}


def test_seed_loads_once_and_skips_existing_keys(client):
    with sqlite3.connect(client.db_path) as db:
        people = db.execute("select external_id, rank from fsp_participants order by external_id").fetchall()
        algo = db.execute(
            "select discipline from fsp_achievements where competition_id = 'synth-algo-2025'"
        ).fetchone()
        odd = db.execute(
            "select place, discipline from fsp_achievements where external_id = 'fsp-synth-3'"
        ).fetchone()
        maria = db.execute(
            "select count(*) from fsp_achievements where external_id = 'fsp-synth-2'"
        ).fetchone()[0]
    assert [row[0] for row in people] == ["fsp-synth-1", "fsp-synth-2", "fsp-synth-3"]
    assert dict(people)["fsp-synth-3"] == "вне списка"
    assert algo[0] == "Программирование алгоритмическое"
    assert odd == ("1", "Квест выходного дня")
    assert maria == 0

    with sqlite3.connect(client.db_path) as db:
        db.execute(
            "update fsp_participants set rank = 'не трогать' where external_id = 'fsp-synth-1'"
        )
        db.commit()
    session = open_session()
    try:
        load_into(session)
        session.commit()
    finally:
        session.close()
    init_db()
    with sqlite3.connect(client.db_path) as db:
        assert db.execute("select count(*) from fsp_participants").fetchone()[0] == 3
        assert db.execute("select count(*) from fsp_achievements").fetchone()[0] == 6
        kept = db.execute(
            "select rank from fsp_participants where external_id = 'fsp-synth-1'"
        ).fetchone()[0]
    assert kept == "не трогать"


def test_cabinet_shows_rank_role_and_empty_history(client):
    register_and_confirm(client)
    before = client.get("/api/candidate/achievements")
    assert before.status_code == 200
    assert before.json() == {"display_name": "", "rank": "", "results": []}

    saved = client.put("/api/candidate/profile", json={**_PROFILE, "external_id": "fsp-synth-1"})
    assert saved.status_code == 200
    body = client.get("/api/candidate/achievements").json()
    assert body["display_name"] == "Иван Синтетиков"
    assert body["rank"] == "I"
    assert "email" not in body
    assert {row["discipline"] for row in body["results"]} == set(CANONICAL_DISCIPLINES)
    page = _section(client.get("/candidate").text)
    assert "Разряд источника: I" in page
    assert "Программирование алгоритмическое" in page
    assert "роль на старте: капитан" in page
    assert "результат: 1" in page
    assert "Достижений ФСП нет." not in page

    empty = client.put("/api/candidate/profile", json={**_PROFILE, "external_id": "fsp-synth-2"})
    assert empty.status_code == 200
    maria = client.get("/api/candidate/achievements").json()
    assert maria["display_name"] == "Мария Черновикова"
    assert maria["rank"] == "КМС"
    assert maria["results"] == []
    blank = _section(client.get("/candidate").text)
    assert "Мария Черновикова" in blank
    assert "Разряд источника: КМС" in blank
    assert "Достижений ФСП нет." in blank

    odd = client.put("/api/candidate/profile", json={**_PROFILE, "external_id": "fsp-synth-3"})
    assert odd.status_code == 200
    petr = client.get("/api/candidate/achievements").json()
    assert petr["rank"] == "вне списка"
    assert petr["results"][0]["place"] == "1"
    odd_page = _section(client.get("/candidate").text)
    assert "Разряд источника: вне списка" in odd_page

    missing = client.put("/api/candidate/profile", json={**_PROFILE, "external_id": "fsp-no-such"})
    assert missing.status_code == 200
    assert client.get("/api/candidate/achievements").json() == {
        "display_name": "",
        "rank": "",
        "results": [],
    }
    gone = _section(client.get("/candidate").text)
    assert "Достижений ФСП нет." in gone
    assert "Разряд источника" not in gone


def test_employer_does_not_read_candidate_achievements(client):
    register_and_confirm(client, email="boss@example.com", role="employer")
    denied = client.get("/api/candidate/achievements")
    assert denied.status_code == 403
    assert denied.json()["error"] == "forbidden"


def test_mock_package_has_no_http_and_no_rank_formula():
    root = Path(product.__file__).resolve().parent / "fsp_mock"
    modules = list(root.glob("*.py"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in modules)
    assert "httpx" not in source
    assert "urllib" not in source
    assert "requests" not in source
    assert "rank_from" not in source
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(name.split(".")[0] not in {"httpx", "urllib", "requests"} for name in names)
