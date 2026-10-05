"""Категория после опроса и выдача только со сданным тестом."""

from __future__ import annotations

import json

from product.app.db import models as db_models
from product.app.db.session import open_session
from product.app.services.categories import recompute
from product.app.services.clock import utc_now
from product.matching.category import assign_category, rank_key
from product.matching.types import CategoryError, ProfileView
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


def _view(**kwargs) -> ProfileView:
    base = dict(
        profile_id=1,
        specialization="backend",
        grade="middle",
        test_score=None,
        test_outcome=None,
        fsp_confirmed_count=0,
    )
    base.update(kwargs)
    return ProfileView(**base)


def test_category_is_spec_and_grade_without_fsp_or_industry():
    plain = assign_category(_view(), "v1")
    assert plain.category_id == "backend:middle"
    assert "/" not in plain.category_id
    assert "it" not in plain.category_id
    assert plain.scored_at is None
    assert plain.test_score is None
    assert plain.explanation == (
        "Опрос: специализация backend, грейд middle. Тест ещё не сдан. Правила v1."
    )
    assert "разряд" not in plain.explanation.casefold()
    assert "резюме" not in plain.explanation.casefold()
    taken = assign_category(
        _view(test_score=0, test_outcome="suggest_lower", fsp_confirmed_count=4),
        "v1",
    )
    assert taken.category_id == plain.category_id
    assert taken.test_score == 0
    assert taken.explanation == (
        "Опрос: специализация backend, грейд middle. "
        "Тест: предложен грейд ниже, балл 0. Правила v1."
    )
    assert taken.rank_key == rank_key(0, 4, 1)
    try:
        assign_category(_view(), "v2")
    except CategoryError as exc:
        assert exc.code == "rule_version"
    else:
        raise AssertionError("чужая версия правил должна отказать")


def test_rank_orders_score_then_achievements_and_keeps_ties():
    rows = [
        _view(profile_id=11, test_score=80, test_outcome="confirm", fsp_confirmed_count=1),
        _view(profile_id=12, test_score=80, test_outcome="confirm", fsp_confirmed_count=5),
        _view(profile_id=13, test_score=90, test_outcome="suggest_higher", fsp_confirmed_count=0),
        _view(profile_id=14, test_score=80, test_outcome="confirm", fsp_confirmed_count=5),
    ]
    ordered = sorted((assign_category(row, "v1") for row in rows), key=lambda item: item.rank_key, reverse=True)
    assert [item.profile_id for item in ordered] == [13, 14, 12, 11]
    assert {item.category_id for item in ordered} == {"backend:middle"}


def _seeker(client, email: str, **extra) -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json={**_PROFILE, **extra})
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _submit(profile_id: int, score: int, outcome: str, spec: str = "backend", grade: str = "middle") -> None:
    db = open_session()
    try:
        now = utc_now()
        db.add(
            db_models.TestAttempt(
                profile_id=profile_id,
                specialization=spec,
                declared_grade=grade,
                template_id=f"{spec}-{grade}-a",
                rule_version="v1",
                answers_json="[]",
                score=score,
                outcome=outcome,
                proposed_grade=grade,
                status="submitted",
                created_at=now,
                submitted_at=now,
            )
        )
        db.commit()
        recompute(db, profile_id)
    finally:
        db.close()


def test_survey_shows_category_before_the_test(client):
    register_and_confirm(client)
    missing = client.get("/api/candidate/category")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    saved = client.put("/api/candidate/profile", json=_PROFILE)
    assert saved.status_code == 200
    body = client.get("/api/candidate/category").json()
    assert body["category_id"] == "backend:middle"
    assert body["industry"] == "it"
    assert body["rule_version"] == "v1"
    assert body["test_score"] is None
    assert body["explanation"].endswith("Тест ещё не сдан. Правила v1.")
    page = client.get("/candidate")
    assert "backend:middle" in page.text
    assert "Опрос:" in page.text


def test_employer_sees_scored_profiles_without_email(client):
    high = _seeker(client, "high@example.com", experience="платежи в контуре", stack=["python"])
    many = _seeker(client, "many@example.com", external_id="fsp-synth-1", stack=["go"])
    one = _seeker(client, "one@example.com", external_id="fsp-synth-3", stack=["python"], team_role="аналитик")
    tie_low = _seeker(client, "tie-a@example.com", stack=["sql"])
    tie_high = _seeker(client, "tie-b@example.com", stack=["sql"])
    zero = _seeker(client, "zero@example.com", stack=["python"])
    hidden = _seeker(client, "hidden@example.com", publication=False, stack=["python"])
    fresh = _seeker(client, "fresh@example.com", stack=["python"])
    _submit(high, 90, "suggest_higher")
    _submit(many, 40, "suggest_lower")
    _submit(one, 40, "suggest_lower")
    _submit(tie_low, 40, "suggest_lower")
    _submit(tie_high, 40, "suggest_lower")
    _submit(zero, 0, "suggest_lower")
    _submit(hidden, 100, "suggest_higher")

    register_and_confirm(client, email="boss@example.com", role="employer")
    denied = client.get("/api/candidate/category")
    assert denied.status_code == 403
    naked = client.get("/api/employer/candidates")
    assert naked.status_code == 422
    assert naked.json()["error"] == "category_id"
    bad = client.get("/api/employer/candidates", params={"category_id": "it:middle"})
    assert bad.status_code == 422
    assert bad.json()["error"] == "category_id"
    flag = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "has_fsp": "yes"},
    )
    assert flag.status_code == 422
    assert flag.json()["error"] == "closed_list"

    listed = client.get("/api/employer/candidates", params={"category_id": "backend:middle"})
    assert listed.status_code == 200
    cards = listed.json()
    ids = [card["profile_id"] for card in cards]
    assert fresh not in ids
    assert hidden not in ids
    assert zero in ids
    assert ids[0] == high
    assert ids.index(many) < ids.index(one)
    assert ids.index(one) < ids.index(tie_low)
    assert ids.index(one) < ids.index(tie_high)
    assert tie_high in ids and tie_low in ids
    assert ids.index(tie_high) < ids.index(tie_low)
    dumped = json.dumps(cards, ensure_ascii=False)
    assert "high@example.com" not in dumped
    assert "candidate_email" not in dumped
    for card in cards:
        assert "email" not in card
        assert card["industry"] == "it"
        assert card["category_id"] == "backend:middle"
        assert "it" not in card["category_id"]
    many_card = next(card for card in cards if card["profile_id"] == many)
    assert many_card["fsp_rank"] == "I"
    assert len(many_card["achievements"]) == 5
    assert "Программирование алгоритмическое" in {row["discipline"] for row in many_card["achievements"]}
    zero_card = next(card for card in cards if card["profile_id"] == zero)
    assert zero_card["test_score"] == 0
    assert "балл 0" in zero_card["explanation"]

    only_python = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "stack": "python"},
    )
    python_ids = {card["profile_id"] for card in only_python.json()}
    assert high in python_ids
    assert many not in python_ids
    text = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "q": "платеж"},
    )
    assert [card["profile_id"] for card in text.json()] == [high]
    assert "Текст: платеж" in text.json()[0]["list_reason"]
    role = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "team_role": "аналитик"},
    )
    assert [card["profile_id"] for card in role.json()] == [one]
    with_fsp = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "has_fsp": "true"},
    )
    assert {card["profile_id"] for card in with_fsp.json()} == {many, one}
    without = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "has_fsp": "false"},
    )
    assert many not in {card["profile_id"] for card in without.json()}
    odd = client.get(
        "/api/employer/candidates",
        params={"category_id": "backend:middle", "q": "https://jobs.example/vacancy"},
    )
    assert odd.status_code == 200
    assert odd.json() == []


def test_history_survives_specialization_change(client):
    profile_id = _seeker(client, "move@example.com")
    _submit(profile_id, 70, "confirm")
    moved = client.put(
        "/api/candidate/profile",
        json={**_PROFILE, "specialization": "frontend"},
    )
    assert moved.status_code == 200
    assert moved.json()["category_id"] == "frontend:middle"
    assert "Тест ещё не сдан" in moved.json()["explanation"]
    import sqlite3

    with sqlite3.connect(client.db_path) as db:
        stored = db.execute(
            "select category_id, test_score from category_assignments where profile_id = ? order by id",
            (profile_id,),
        ).fetchall()
    assert ("backend:middle", 70) in stored
    assert stored[-1] == ("frontend:middle", None)
    assert len(stored) >= 2
