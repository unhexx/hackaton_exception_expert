"""Золотой прогон офлайн: числа только из этого запуска, порога нет."""

from __future__ import annotations

import ast
from pathlib import Path

import product
from product.matching.golden_run import (
    grade_separation_counts,
    is_drift,
    item_separates,
    load_cases,
    render_report,
    summarize,
)
from product.matching.rules import load_rules
from product.matching.stems import catalog
from product.tests.conftest import register_and_confirm


def test_golden_report_prints_this_run_only():
    path = Path(product.__file__).resolve().parent / "matching" / "golden" / "cases.json"
    before = path.read_bytes()
    text = render_report()
    assert path.read_bytes() == before
    lines = text.strip().splitlines()
    assert len(lines) == 6
    assert "%" not in text
    separated, total = grade_separation_counts()
    assert lines[5] == f"grade_separation {separated} {total}"
    assert separated <= total
    assert total == 216
    assert separated < total
    counts = summarize()
    assert lines[0] == f"category_match {counts['category_match'][0]} {counts['category_match'][1]}"
    assert counts["category_match"][0] == counts["category_match"][1]
    assert counts["category_match"][1] >= 30
    outcome_hit, outcome_total = counts["outcome_match"]
    assert outcome_total > 0
    assert outcome_hit == outcome_total
    stable_hit, stable_total = counts["template_stable"]
    assert stable_total > 0
    assert stable_hit == stable_total
    resume_hit, resume_total = counts["resume_ok"]
    assert resume_total > 0
    assert resume_hit == resume_total
    hit, slots = counts["relevant_in_top"]
    assert hit > 0
    assert slots > hit
    cases = load_cases()
    assert cases["top_k"] == 3
    per_spec: dict[str, int] = {}
    for need in cases["needs"]:
        spec = need["category_id"].split(":")[0]
        per_spec[spec] = per_spec.get(spec, 0) + 1
    assert set(per_spec) == set(load_rules()["specializations"])
    assert all(1 <= count <= 2 for count in per_spec.values())


def _stem(template_id: str, question_id: str) -> tuple[dict, dict]:
    row = next(item for item in catalog() if item["template_id"] == template_id)
    question = next(item for item in row["questions"] if item["id"] == question_id)
    return row, question


def test_grade_separation_is_not_a_threshold():
    assert load_rules()["grades"][0] == "junior"
    junior_axis = {
        "correct": "b",
        "choices": [
            {"id": "a", "text": "200 и пустое тело"},
            {"id": "b", "text": "4xx и поле ошибки"},
            {"id": "c", "text": "HTML 500"},
        ],
    }
    assert item_separates(junior_axis, "junior") is True
    assert item_separates(junior_axis, "middle") is True
    assert item_separates(junior_axis, "intern") is False
    color_and_likes = {
        "correct": "b",
        "choices": [
            {"id": "a", "text": "Цвет дашборда"},
            {"id": "b", "text": "контракт"},
            {"id": "c", "text": "Число лайков"},
        ],
    }
    assert item_separates(color_and_likes, "junior") is False
    assert item_separates(color_and_likes, "lead") is False
    one_drift = {
        "correct": "a",
        "choices": [
            {"id": "a", "text": "контракт на границе"},
            {"id": "b", "text": "Цвет дашборда"},
            {"id": "c", "text": "Общий root на проде"},
        ],
    }
    assert item_separates(one_drift, "senior") is False
    assert is_drift("Логотип BI") is True
    assert is_drift("Имя дашборда") is True
    assert is_drift("Бренд брокера") is True
    assert is_drift("Число звезд на GitHub") is True
    assert is_drift("Свои цвета в каждом репо") is False
    assert is_drift("Подогнать дашборд под ожидаемое число") is False
    assert is_drift("Скрыть колонку на дашборде") is False
    assert is_drift("Хранить tar на ноутбуке") is False
    own_colors = {
        "correct": "b",
        "choices": [
            {"id": "a", "text": "Свои цвета в каждом репо"},
            {"id": "b", "text": "Общие токены"},
            {"id": "c", "text": "Копипасту CSS"},
        ],
    }
    assert item_separates(own_colors, "lead") is True
    separated_ids = (
        ("backend-junior-a", "q1"),
        ("data-senior-c", "q2"),
        ("data-lead-a", "q3"),
        ("data-senior-b", "q3"),
        ("frontend-lead-a", "q1"),
    )
    for template_id, question_id in separated_ids:
        row, question = _stem(template_id, question_id)
        assert item_separates(question, row["grade"]) is True
    drifted_ids = (
        ("devops-junior-a", "q1"),
        ("frontend-junior-a", "q3"),
        ("security-lead-a", "q1"),
    )
    for template_id, question_id in drifted_ids:
        row, question = _stem(template_id, question_id)
        assert item_separates(question, row["grade"]) is False
    assert "grade_separation" not in summarize()


def test_top_slots_follow_rank_key():
    cases = {
        "top_k": 2,
        "profiles": [
            {
                "profile_id": 1,
                "specialization": "data",
                "grade": "junior",
                "test_score": 10,
                "test_outcome": "suggest_lower",
                "fsp_confirmed_count": 9,
                "stack": [],
                "team_role": "разработчик",
                "work_format": "офис",
                "experience": "",
                "expected_category_id": "data:junior",
            },
            {
                "profile_id": 2,
                "specialization": "data",
                "grade": "junior",
                "test_score": 90,
                "test_outcome": "suggest_higher",
                "fsp_confirmed_count": 0,
                "stack": [],
                "team_role": "разработчик",
                "work_format": "офис",
                "experience": "",
                "expected_category_id": "data:junior",
            },
            {
                "profile_id": 3,
                "specialization": "data",
                "grade": "junior",
                "test_score": 50,
                "test_outcome": "confirm",
                "fsp_confirmed_count": 3,
                "stack": [],
                "team_role": "разработчик",
                "work_format": "офис",
                "experience": "",
                "expected_category_id": "data:junior",
            },
        ],
        "needs": [
            {
                "id": "tiny",
                "category_id": "data:junior",
                "stack": [],
                "team_role": "",
                "work_format": "",
                "has_fsp": None,
                "q": "",
                "relevant_profile_ids": [2, 1],
            }
        ],
    }
    assert summarize(cases)["relevant_in_top"] == (1, 2)


def test_matching_package_does_not_call_network():
    root = Path(product.__file__).resolve().parent / "matching"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(name.split(".")[0] not in {"httpx", "urllib", "requests", "socket"} for name in names)


def test_validation_action_is_plain_text(client):
    anon = client.get("/validation")
    assert anon.status_code == 401
    assert anon.json()["error"] == "unauthorized"
    register_and_confirm(client, email="jury@example.com", role="employer")
    report = client.get("/validation")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/plain")
    assert report.text == render_report()
    page = client.get("/employer/shortlist")
    assert 'hx-swap="afterbegin"' in page.text
    assert 'id="shown"' in page.text
    assert "Прогон валидации" in page.text
    first = client.get(
        "/employer/shortlist",
        params={"category_id": "backend:middle"},
        headers={"HX-Request": "true"},
    )
    second = client.get(
        "/employer/shortlist",
        params={"category_id": "frontend:middle"},
        headers={"HX-Request": "true"},
    )
    assert "Подборка backend:middle" in first.text
    assert "frontend:middle" not in first.text
    assert "Подборка frontend:middle" in second.text
    assert "backend:middle" not in second.text
