"""Испытание грейда: шаблон, интервал и смена только после confirm."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import product
from product.app.services.clock import utc_now
from product.matching.grade import (
    is_adjacent_grade,
    is_lower_grade,
    load_template,
    score_attempt,
    select_template,
    templates_for,
)
from product.matching.rules import load_rules
from product.matching.stems import catalog
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


def test_lower_grade_follows_scale_not_adjacency():
    assert is_lower_grade("middle", "junior") is True
    assert is_lower_grade("junior", "middle") is False
    assert is_lower_grade("lead", "senior") is True
    assert is_lower_grade("junior", "lead") is False
    assert is_lower_grade("lead", "junior") is True
    assert is_adjacent_grade("lead", "junior") is False
    assert is_adjacent_grade("middle", "junior") is True
    assert is_lower_grade("middle", "unknown") is False
    assert is_adjacent_grade("middle", "unknown") is False
    assert is_lower_grade("ghost", "junior") is False
    assert is_adjacent_grade("ghost", "junior") is False


def test_pair_templates_are_stable_and_offline():
    rules = load_rules()
    root = Path(product.matching.grade.__file__).resolve().parent
    source = (root / "grade.py").read_text(encoding="utf-8")
    assert "sqlalchemy" not in source
    assert "samples.json" not in source
    assert not list((root / "templates").glob("*.json"))
    rows = catalog()
    ids = [row["template_id"] for row in rows]
    assert len(ids) == len(set(ids))
    texts = []
    families = ("refusal_contract", "close_cause", "offline_check")
    letters = {"a", "b", "c"}
    for row in rows:
        assert len(row["questions"]) == 3
        keys = [question["correct"] for question in row["questions"]]
        assert len(set(keys)) == 3
        for index, question in enumerate(row["questions"]):
            assert question["correct"] in letters
            assert sum(1 for choice in question["choices"] if choice["id"] == question["correct"]) == 1
            assert {choice["id"] for choice in question["choices"]} == letters
            assert question["family"] in families
            assert question["family"] == families[index]
            texts.append(question["text"])
            blob = question["text"] + "".join(choice["text"] for choice in question["choices"])
            assert "вариант a про" not in blob
            assert "Пара " not in blob
    assert len(texts) == len(set(texts))
    covered = 0
    for spec in rules["specializations"]:
        for grade in rules["grades"]:
            found = templates_for(spec, grade, "v1")
            assert len(found) == 3
            covered += len(found)
            assert [row["template_id"] for row in found] == sorted(row["template_id"] for row in found)
            triples = [tuple(question["correct"] for question in row["questions"]) for row in found]
            assert len(set(triples)) == 3
            for slot in range(3):
                assert {row["questions"][slot]["correct"] for row in found} == letters
    assert len(rows) == covered == 72
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
    dumped = json.dumps(body)
    assert "correct" not in dumped
    assert "family" not in dumped
    assert "refusal_contract" not in dumped
    assert "close_cause" not in dumped
    assert "offline_check" not in dumped
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
    assert client.post("/api/candidate/tests/start", json={"grade": "lead"}).json()["error"] == "grade_not_offered"
    assert client.post("/api/candidate/tests/start", json={"grade": "junior"}).json()["error"] == "grade_not_offered"
    open_draft = client.post("/api/candidate/tests/start", json={})
    conflict = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "attempt_open"
    assert _drafts(client, profile_id) == 1
    _submit(client, open_draft.json()["attempt_id"], _answers(load_template(open_draft.json()["template_id"]), 3))
    survey_stamp = _stamp(client, profile_id)
    adjacent = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert adjacent.status_code == 201, adjacent.text
    assert adjacent.json()["declared_grade"] == "senior"
    assert adjacent.json()["template_id"] == select_template(profile_id, "backend", "senior", "v1")
    failed = _submit(client, adjacent.json()["attempt_id"], _answers(load_template(adjacent.json()["template_id"]), 1))
    assert failed.status_code == 200, failed.text
    assert failed.json()["outcome"] == "suggest_lower"
    assert failed.json()["grade"] == "middle"
    assert _stamp(client, profile_id) == survey_stamp
    retry = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert retry.status_code == 201, retry.text
    assert retry.json()["declared_grade"] == "senior"


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
    overflow = _submit(client, 10**30, ["a", "b", "c"])
    assert overflow.status_code == 404
    assert overflow.json()["error"] == "not_found"
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
    assert "Что случилось" not in again.text
    assert "ещё нельзя" not in again.text
    assert "grade_interval" not in again.text
    click = client.post(
        "/candidate/test/start",
        data={"csrf": _csrf(again.text), "grade": "senior"},
        follow_redirects=False,
    )
    assert click.status_code == 303
    assert "Что случилось" not in click.text


def test_first_lower_attempt_skips_interval(client):
    _seeker(client, "first-down@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    failed = _submit(
        client,
        started.json()["attempt_id"],
        _answers(load_template(started.json()["template_id"]), 1),
    )
    assert failed.json()["outcome"] == "suggest_lower"
    assert failed.json()["proposed_grade"] == "junior"
    assert failed.json()["grade"] == "middle"
    down = client.post("/api/candidate/tests/start", json={"grade": "junior"})
    assert down.status_code == 201, down.text
    assert down.json()["declared_grade"] == "junior"


def test_resume_grade_does_not_burn_first_lower_attempt(client):
    profile_id = _seeker(client, "pdf-down@example.com")
    stamp = _stamp(client, profile_id)
    pdf = Path(product.__file__).resolve().parent / "matching" / "golden" / "resumes" / "full.pdf"
    uploaded = client.post(
        "/api/candidate/resume",
        files={"file": ("full.pdf", pdf.read_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["grade"] == "senior"
    assert _stamp(client, profile_id) == stamp
    started = client.post("/api/candidate/tests/start", json={})
    assert started.json()["declared_grade"] == "senior"
    failed = _submit(
        client,
        started.json()["attempt_id"],
        _answers(load_template(started.json()["template_id"]), 1),
    )
    assert failed.json()["outcome"] == "suggest_lower"
    assert failed.json()["proposed_grade"] == "middle"
    assert failed.json()["grade"] == "senior"
    down = client.post("/api/candidate/tests/start", json={"grade": "middle"})
    assert down.status_code == 201, down.text
    assert down.json()["declared_grade"] == "middle"
    assert _stamp(client, profile_id) == stamp


def test_hundred_on_lower_grade_does_not_burn_retry(client):
    _seeker(client, "retry-down@example.com")
    recorded = client.post("/api/candidate/tests/start", json={})
    confirmed = _submit(
        client,
        recorded.json()["attempt_id"],
        _answers(load_template(recorded.json()["template_id"]), 2),
    )
    assert confirmed.json()["outcome"] == "confirm"
    failed = client.post("/api/candidate/tests/start", json={})
    lowered = _submit(
        client,
        failed.json()["attempt_id"],
        _answers(load_template(failed.json()["template_id"]), 1),
    )
    assert lowered.json()["outcome"] == "suggest_lower"
    assert lowered.json()["proposed_grade"] == "junior"
    assert lowered.json()["grade"] == "middle"
    first = client.post("/api/candidate/tests/start", json={"grade": "junior"})
    assert first.status_code == 201, first.text
    hundred = _submit(
        client,
        first.json()["attempt_id"],
        _answers(load_template(first.json()["template_id"]), 3),
    )
    assert hundred.status_code == 200, hundred.text
    assert hundred.json()["outcome"] == "suggest_higher"
    assert hundred.json()["proposed_grade"] == "middle"
    assert hundred.json()["grade"] == "middle"
    retry = client.post("/api/candidate/tests/start", json={"grade": "junior"})
    assert retry.status_code == 201, retry.text
    assert retry.json()["declared_grade"] == "junior"


def test_repeat_adjacent_after_written_change_waits_interval(client):
    profile_id = _seeker(client, "repeat-down@example.com", grade="senior")
    started = client.post("/api/candidate/tests/start", json={})
    offered = _submit(
        client,
        started.json()["attempt_id"],
        _answers(load_template(started.json()["template_id"]), 1),
    )
    assert offered.json()["proposed_grade"] == "middle"
    first_down = client.post("/api/candidate/tests/start", json={"grade": "middle"})
    assert first_down.status_code == 201, first_down.text
    moved = _submit(
        client,
        first_down.json()["attempt_id"],
        _answers(load_template(first_down.json()["template_id"]), 2),
    )
    assert moved.json()["outcome"] == "confirm"
    assert moved.json()["grade"] == "middle"
    assert client.post("/api/candidate/tests/start", json={"grade": "junior"}).json()["error"] == "grade_not_offered"
    assert client.post("/api/candidate/tests/start", json={"grade": "senior"}).json()["error"] == "grade_not_offered"
    recorded = client.post("/api/candidate/tests/start", json={})
    lowered = _submit(
        client,
        recorded.json()["attempt_id"],
        _answers(load_template(recorded.json()["template_id"]), 1),
    )
    assert lowered.json()["proposed_grade"] == "junior"
    blocked_down = client.post("/api/candidate/tests/start", json={"grade": "junior"})
    assert blocked_down.status_code == 409
    assert blocked_down.json()["error"] == "grade_interval"
    higher = client.post("/api/candidate/tests/start", json={})
    offered_up = _submit(
        client,
        higher.json()["attempt_id"],
        _answers(load_template(higher.json()["template_id"]), 3),
    )
    assert offered_up.json()["proposed_grade"] == "senior"
    blocked_up = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert blocked_up.status_code == 409
    assert blocked_up.json()["error"] == "grade_interval"
    _set_stamp(client, profile_id, "2000-01-01T00:00:00Z")
    opened = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert opened.status_code == 201, opened.text
    _set_stamp(client, profile_id, utc_now())
    late = _submit(
        client,
        opened.json()["attempt_id"],
        _answers(load_template(opened.json()["template_id"]), 2),
    )
    assert late.status_code == 409
    assert late.json()["error"] == "grade_interval"
    assert _status(client, opened.json()["attempt_id"]) == "draft"


def test_page_first_lower_offer_has_no_interval_notice(client):
    _seeker(client, "html-down@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    failed = _submit(
        client,
        started.json()["attempt_id"],
        _answers(load_template(started.json()["template_id"]), 1),
    )
    assert failed.json()["proposed_grade"] == "junior"
    page = client.get("/candidate/test")
    assert page.status_code == 200
    assert "Начать тест грейда junior" in page.text
    assert "Что случилось" not in page.text
    assert "grade_interval" not in page.text
