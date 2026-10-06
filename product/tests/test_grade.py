"""Испытание грейда: шаблон, интервал и смена только после confirm."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import product
from product.app.services.clock import utc_now
from product.matching.grade import load_template, score_attempt, select_template, templates_for
from product.matching.rules import load_rules
from product.tests.conftest import register_and_confirm

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


def _seeker(client, email: str = "seeker@example.com", **extra) -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json={**_PROFILE, **extra})
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _login(client, email: str) -> None:
    logged = client.post("/api/auth/login", json={"email": email, "password": "password-ok"})
    assert logged.status_code == 200, logged.text


def _answers(template: dict, correct_n: int) -> list[str]:
    chosen = []
    for index, question in enumerate(template["questions"]):
        if index < correct_n:
            chosen.append(question["correct"])
        else:
            chosen.append(next(choice["id"] for choice in question["choices"] if choice["id"] != question["correct"]))
    return chosen


def _submit(client, attempt_id: int, answers: list[str]):
    return client.post(f"/api/candidate/tests/{attempt_id}/submit", json={"answers": answers})


def _stamp(client, profile_id: int) -> str:
    with sqlite3.connect(client.db_path) as db:
        return db.execute("select grade_changed_at from profiles where id = ?", (profile_id,)).fetchone()[0]


def _set_stamp(client, profile_id: int, stamp: str) -> None:
    with sqlite3.connect(client.db_path) as db:
        db.execute("update profiles set grade_changed_at = ? where id = ?", (stamp, profile_id))
        db.commit()


def _drafts(client, profile_id: int) -> int:
    with sqlite3.connect(client.db_path) as db:
        return db.execute(
            "select count(*) from test_attempts where profile_id = ? and status = 'draft'",
            (profile_id,),
        ).fetchone()[0]


def _status(client, attempt_id: int) -> str:
    with sqlite3.connect(client.db_path) as db:
        return db.execute("select status from test_attempts where id = ?", (attempt_id,)).fetchone()[0]


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def test_pair_templates_are_stable_and_offline():
    rules = load_rules()
    root = Path(product.matching.grade.__file__).resolve().parent
    source = (root / "grade.py").read_text(encoding="utf-8")
    assert "sqlalchemy" not in source
    assert "samples.json" not in source
    files = list((root / "templates").glob("*.json"))
    assert len(files) == 48
    for spec in rules["specializations"]:
        for grade in rules["grades"]:
            found = templates_for(spec, grade, "v1")
            assert len(found) == 2
            assert [row["template_id"] for row in found] == sorted(row["template_id"] for row in found)
    chosen = {select_template(profile_id, "backend", "middle", "v1") for profile_id in range(1, 31)}
    assert len(chosen) >= 2
    assert select_template(7, "backend", "middle", "v1") == select_template(7, "backend", "middle", "v1")
    template = load_template("backend-middle-a")
    before = json.dumps(template, ensure_ascii=False)
    answers = _answers(template, 2)
    first = score_attempt(template, answers)
    second = score_attempt(template, answers)
    assert first == second
    assert first["score"] == 67
    assert first["outcome"] == "confirm"
    assert json.dumps(template, ensure_ascii=False) == before
    samples = json.loads((root / "vacancies" / "samples.json").read_text(encoding="utf-8"))
    shown = [item["shows_template"] for item in samples["vacancies"]]
    assert shown
    for template_id in shown:
        load_template(template_id)
    for path in files:
        blob = path.read_text(encoding="utf-8")
        assert "вариант a про" not in blob
        assert "Пара " not in blob
        row = json.loads(blob)
        assert len(row["questions"]) == 3
        assert {choice["id"] for choice in row["questions"][0]["choices"]} == {"a", "b", "c"}


def test_recorded_attempt_confirms_without_moving_grade(client):
    register_and_confirm(client)
    naked = client.post("/api/candidate/tests/start", json={})
    assert naked.status_code == 409
    assert naked.json()["error"] == "survey_required"
    saved = client.put("/api/candidate/profile", json=_PROFILE)
    assert saved.status_code == 200, saved.text
    profile_id = saved.json()["profile_id"]
    stamp = _stamp(client, profile_id)
    started = client.post("/api/candidate/tests/start", json={})
    assert started.status_code == 201, started.text
    body = started.json()
    assert "correct" not in json.dumps(body)
    assert body["declared_grade"] == "middle"
    assert body["template_id"] == select_template(profile_id, "backend", "middle", "v1")
    explicit = client.post("/api/candidate/tests/start", json={"grade": "middle"})
    assert explicit.status_code == 201
    assert explicit.json()["attempt_id"] == body["attempt_id"]
    template = load_template(body["template_id"])
    unknown = _submit(client, body["attempt_id"], ["nope", "b", "c"])
    assert unknown.status_code == 422
    assert unknown.json()["error"] == "answer_unknown"
    assert _status(client, body["attempt_id"]) == "draft"
    confirmed = _submit(client, body["attempt_id"], _answers(template, 2))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["score"] == 67
    assert confirmed.json()["outcome"] == "confirm"
    assert confirmed.json()["proposed_grade"] == "middle"
    assert confirmed.json()["grade"] == "middle"
    assert confirmed.json()["category_id"] == "backend:middle"
    assert client.get("/api/candidate/category").json()["test_score"] == 67
    assert _stamp(client, profile_id) == stamp
    closed = _submit(client, body["attempt_id"], _answers(template, 2))
    assert closed.status_code == 409
    assert closed.json()["error"] == "attempt_closed"
    again = client.post("/api/candidate/tests/start", json={})
    assert again.status_code == 201
    higher = _submit(client, again.json()["attempt_id"], _answers(load_template(again.json()["template_id"]), 3))
    assert higher.status_code == 200, higher.text
    assert higher.json()["score"] == 100
    assert higher.json()["outcome"] == "suggest_higher"
    assert higher.json()["proposed_grade"] == "senior"
    assert higher.json()["grade"] == "middle"
    assert _stamp(client, profile_id) == stamp
    history = client.get("/api/candidate/tests").json()
    assert [row["attempt_id"] for row in history[:2]] == [again.json()["attempt_id"], body["attempt_id"]]
    assert "correct" not in json.dumps(history)


def test_adjacent_grade_respects_offer_and_interval(client):
    profile_id = _seeker(client, "adj@example.com")
    early = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert early.status_code == 409
    assert early.json()["error"] == "grade_not_offered"
    assert _drafts(client, profile_id) == 0
    started = client.post("/api/candidate/tests/start", json={})
    template = load_template(started.json()["template_id"])
    offered = _submit(client, started.json()["attempt_id"], _answers(template, 3))
    assert offered.json()["proposed_grade"] == "senior"
    blocked = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "grade_interval"
    assert _drafts(client, profile_id) == 0
    assert client.post("/api/candidate/tests/start", json={"grade": "lead"}).json()["error"] == "grade_not_offered"
    assert client.post("/api/candidate/tests/start", json={"grade": "junior"}).json()["error"] == "grade_not_offered"
    open_draft = client.post("/api/candidate/tests/start", json={})
    conflict = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "attempt_open"
    assert _drafts(client, profile_id) == 1
    _submit(client, open_draft.json()["attempt_id"], _answers(load_template(open_draft.json()["template_id"]), 3))
    _set_stamp(client, profile_id, "2000-01-01T00:00:00Z")
    adjacent = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert adjacent.status_code == 201, adjacent.text
    assert adjacent.json()["declared_grade"] == "senior"
    assert adjacent.json()["template_id"] == select_template(profile_id, "backend", "senior", "v1")
    _set_stamp(client, profile_id, utc_now())
    late = _submit(client, adjacent.json()["attempt_id"], _answers(load_template(adjacent.json()["template_id"]), 2))
    assert late.status_code == 409
    assert late.json()["error"] == "grade_interval"
    assert _status(client, adjacent.json()["attempt_id"]) == "draft"
    _set_stamp(client, profile_id, "2000-01-01T00:00:00Z")
    failed = _submit(client, adjacent.json()["attempt_id"], _answers(load_template(adjacent.json()["template_id"]), 1))
    assert failed.status_code == 200, failed.text
    assert failed.json()["score"] == 33
    assert failed.json()["outcome"] == "suggest_lower"
    assert failed.json()["proposed_grade"] == "middle"
    assert failed.json()["grade"] == "middle"
    assert _stamp(client, profile_id) == "2000-01-01T00:00:00Z"


def test_confirmed_adjacent_grade_replaces_category(client):
    profile_id = _seeker(client, "move-grade@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    recorded = _submit(
        client,
        started.json()["attempt_id"],
        _answers(load_template(started.json()["template_id"]), 3),
    )
    assert recorded.json()["category_id"] == "backend:middle"
    register_and_confirm(client, email="boss-grade@example.com", role="employer")

    def listed(category_id: str) -> list[dict]:
        response = client.get("/api/employer/candidates", params={"category_id": category_id})
        assert response.status_code == 200, response.text
        return response.json()

    assert profile_id in {card["profile_id"] for card in listed("backend:middle")}
    assert profile_id not in {card["profile_id"] for card in listed("backend:senior")}
    _login(client, "move-grade@example.com")
    _set_stamp(client, profile_id, "2000-01-01T00:00:00Z")
    adjacent = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert adjacent.status_code == 201, adjacent.text
    _login(client, "boss-grade@example.com")
    assert profile_id in {card["profile_id"] for card in listed("backend:middle")}
    assert profile_id not in {card["profile_id"] for card in listed("backend:senior")}
    _login(client, "move-grade@example.com")
    done = _submit(client, adjacent.json()["attempt_id"], _answers(load_template(adjacent.json()["template_id"]), 2))
    assert done.status_code == 200, done.text
    assert done.json()["outcome"] == "confirm"
    assert done.json()["score"] == 67
    assert done.json()["grade"] == "senior"
    assert done.json()["category_id"] == "backend:senior"
    assert _stamp(client, profile_id) != "2000-01-01T00:00:00Z"
    _login(client, "boss-grade@example.com")
    middle = listed("backend:middle")
    senior = listed("backend:senior")
    assert profile_id not in {card["profile_id"] for card in middle}
    card = next(item for item in senior if item["profile_id"] == profile_id)
    assert card["test_score"] == 67
    assert "email" not in card


def test_edges_keep_recorded_grade(client):
    junior_id = _seeker(client, "jun@example.com", grade="junior")
    started = client.post("/api/candidate/tests/start", json={})
    done = _submit(client, started.json()["attempt_id"], _answers(load_template(started.json()["template_id"]), 1))
    assert done.json()["outcome"] == "suggest_lower"
    assert done.json()["proposed_grade"] == "junior"
    assert done.json()["grade"] == "junior"
    assert _stamp(client, junior_id)

    _seeker(client, "lead@example.com", grade="lead")
    started = client.post("/api/candidate/tests/start", json={})
    done = _submit(client, started.json()["attempt_id"], _answers(load_template(started.json()["template_id"]), 3))
    assert done.json()["score"] == 100
    assert done.json()["outcome"] == "confirm"
    assert done.json()["proposed_grade"] == "lead"
    assert done.json()["grade"] == "lead"

    senior_id = _seeker(client, "sen@example.com", grade="senior")
    started = client.post("/api/candidate/tests/start", json={})
    done = _submit(client, started.json()["attempt_id"], _answers(load_template(started.json()["template_id"]), 1))
    assert done.json()["proposed_grade"] == "middle"
    assert done.json()["grade"] == "senior"
    _set_stamp(client, senior_id, "2000-01-01T00:00:00Z")
    adjacent = client.post("/api/candidate/tests/start", json={"grade": "middle"})
    assert adjacent.status_code == 201, adjacent.text
    higher = _submit(
        client,
        adjacent.json()["attempt_id"],
        _answers(load_template(adjacent.json()["template_id"]), 3),
    )
    assert higher.json()["outcome"] == "suggest_higher"
    assert higher.json()["proposed_grade"] == "senior"
    assert higher.json()["grade"] == "senior"
    assert _stamp(client, senior_id) == "2000-01-01T00:00:00Z"

    _seeker(client, "own@example.com")
    attempt_id = client.post("/api/candidate/tests/start", json={}).json()["attempt_id"]
    _seeker(client, "other@example.com")
    foreign = _submit(client, attempt_id, ["a", "b", "c"])
    assert foreign.status_code == 404
    assert foreign.json()["error"] == "not_found"
    missing = _submit(client, 999999, ["a", "b", "c"])
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    register_and_confirm(client, email="bare@example.com")
    bare = client.post("/api/candidate/tests/1/submit", json={"answers": ["a", "b", "c"]})
    assert bare.status_code == 404
    assert bare.json()["error"] == "not_found"
    register_and_confirm(client, email="boss-edge@example.com", role="employer")
    denied = client.post("/api/candidate/tests/start", json={})
    assert denied.status_code == 403
    assert denied.json()["error"] == "forbidden"
    assert client.get("/candidate/test").status_code == 403


def test_page_shows_attempt_history_and_vacancy_link(client):
    anon = client.get("/candidate/test", follow_redirects=False)
    assert anon.status_code == 303
    _seeker(client, "page@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    body = started.json()
    template = load_template(body["template_id"])
    page = client.get("/candidate/test")
    assert page.status_code == 200
    assert template["questions"][0]["text"] in page.text
    assert "принять грейд" not in page.text.casefold()
    assert "Синтетическая вакансия backend middle" in page.text
    assert "показывает шаблон backend-middle-a" in page.text
    answers = _answers(template, 3)
    sent = client.post(
        "/candidate/test/submit",
        data={
            "csrf": _csrf(page.text),
            "attempt_id": str(body["attempt_id"]),
            "answer_0": answers[0],
            "answer_1": answers[1],
            "answer_2": answers[2],
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    again = client.get("/candidate/test")
    assert "балл 100" in again.text
    assert "предложен грейд выше" in again.text
    assert "Начать тест грейда senior" in again.text
