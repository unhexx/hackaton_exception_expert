"""Каталог ошибок: три абзаца, интервал грейда, подсказки кабинета."""

from __future__ import annotations

import pytest

from product.app.services.clock import days_remaining, utc_now
from product.app.services.errors import ApiError, _CATALOG, _DEFAULTS, compose, explain, fail
from product.tests.conftest import register_and_confirm


def test_compose_joins_three_parts():
    text = compose("А.", "Б.", "В.")
    assert text == "Что случилось. А.\nПочему. Б.\nЧто сделать. В."


def test_every_catalog_key_has_headings_and_advice():
    assert _CATALOG
    for key in _CATALOG:
        text = explain(key, **_DEFAULTS.get(key, {}))
        assert text.startswith("Что случилось. "), key
        assert "\nПочему. " in text, key
        assert "\nЧто сделать. " in text, key


def test_explain_without_parts_raises():
    with pytest.raises(KeyError):
        explain("grade_interval")


def test_fail_sets_machine_code():
    with pytest.raises(ApiError) as caught:
        fail(409, "survey_required")
    assert caught.value.status == 409
    assert caught.value.error == "survey_required"
    assert "Что случилось" in caught.value.message


def test_grade_interval_names_days_and_grades():
    text = explain(
        "grade_interval",
        current="middle",
        requested="senior",
        changed_at="2026-01-01T00:00:00Z",
        interval=90,
        left=87,
    )
    assert "90" in text
    assert "87" in text
    assert "middle" in text
    assert "senior" in text


def test_days_remaining_zero_after_deadline():
    assert days_remaining("2000-01-01T00:00:00Z", 90) == 0


def test_days_remaining_counts_open_interval():
    left = days_remaining(utc_now(), 90)
    assert 89 <= left <= 90


def test_start_without_survey_explains_next_step(client):
    register_and_confirm(client)
    response = client.post("/api/candidate/tests/start", json={})
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "survey_required"
    assert "Что случилось" in body["message"]
    assert "Почему" in body["message"]
    assert "Что сделать" in body["message"]
    assert "анкет" in body["message"].casefold()


def test_cabinet_without_profile_shows_hint(client):
    register_and_confirm(client)
    page = client.get("/candidate")
    assert page.status_code == 200
    assert "Что случилось. Анкеты ещё нет." in page.text
    assert "Приглашений нет" in page.text
    assert "Тест ещё не сдан" in page.text
