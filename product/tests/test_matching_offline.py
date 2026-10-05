"""Золотой прогон офлайн: числа только из этого запуска, порога нет."""

from __future__ import annotations

import ast
from pathlib import Path

import product
from product.matching.golden_run import load_cases, render_report, summarize
from product.matching.rules import load_rules
from product.tests.conftest import register_and_confirm


def test_golden_report_prints_this_run_only():
    path = Path(product.__file__).resolve().parent / "matching" / "golden" / "cases.json"
    before = path.read_bytes()
    text = render_report()
    assert path.read_bytes() == before
    lines = text.strip().splitlines()
    assert len(lines) == 5
    assert "%" not in text
    counts = summarize()
    assert lines[0] == f"category_match {counts['category_match'][0]} {counts['category_match'][1]}"
    assert counts["category_match"][0] == counts["category_match"][1]
    assert counts["category_match"][1] >= 30
    assert counts["outcome_match"] == (0, 0)
    assert counts["template_stable"] == (0, 0)
    assert counts["resume_ok"] == (0, 0)
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
