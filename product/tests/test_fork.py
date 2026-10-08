"""Общий разбор вилки. Журналы приглашения и вакансии не смешиваются."""

from __future__ import annotations

import pytest

from product.app.services.errors import ApiError
from product.app.services.fork import parse_fork
from product.tests.conftest import register_and_confirm

_CARD = {
    "name": "Синтетика",
    "description": "Платежи",
    "direction": "backend",
    "contact": "telegram: @sintetika",
}


def _stop(status: int, code: str, key: str | None = None, **_parts: object) -> None:
    raise ApiError(status, code, key or code)


def test_parse_fork_keeps_ordered_ints_and_stops_on_the_first_bound(capsys):
    assert parse_fork(180000, 250000, _stop) == (180000, 250000)
    assert parse_fork(-2, -1, _stop) == (-2, -1)
    with pytest.raises(ApiError) as kind:
        parse_fork(True, 2, _stop)
    assert kind.value.error == "salary_range"
    assert kind.value.message == "salary_range_type"
    with pytest.raises(ApiError) as huge:
        parse_fork(1, 10**30, _stop)
    assert huge.value.message == "salary_range"
    with pytest.raises(ApiError) as flat:
        parse_fork(180000, 180000, _stop)
    assert flat.value.message == "salary_range"
    seen: list[str] = []

    def _once(status: int, code: str, key: str | None = None, **_parts: object) -> None:
        seen.append(key or code)
        raise ApiError(status, code, key or code)

    with pytest.raises(ApiError):
        parse_fork("180000", "250000", _once)
    assert seen == ["salary_range_type"]
    assert capsys.readouterr().out == ""


def test_bad_fork_logs_the_service_that_rejected_it(client, capsys):
    register_and_confirm(client, email="fork-boss@example.com", role="employer")
    saved = client.put("/api/employer/company", json=_CARD)
    assert saved.status_code == 200, saved.text
    capsys.readouterr()
    offer = client.post(
        "/api/employer/offers",
        json={
            "profile_id": 1,
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "message": "Ищем backend",
            "salary_min": "180000",
            "salary_max": 250000,
            "salary_currency": "RUB",
            "contact_channel": "telegram: @sintetika",
        },
    )
    assert offer.status_code == 422
    assert offer.json()["error"] == "salary_range"
    assert "целыми числами" in offer.json()["message"]
    offer_log = capsys.readouterr().out
    assert "offer_rejected salary_range" in offer_log
    assert "vacancy_rejected" not in offer_log
    vacancy = client.post(
        "/api/employer/vacancies",
        json={
            "title": "Backend middle",
            "description": "Платежи",
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "contact_channel": "telegram: @sintetika",
            "salary_min": 250000,
            "salary_max": 180000,
            "salary_currency": "RUB",
        },
    )
    assert vacancy.status_code == 422
    assert vacancy.json()["error"] == "salary_range"
    assert "целыми числами" not in vacancy.json()["message"]
    vacancy_log = capsys.readouterr().out
    assert "vacancy_rejected salary_range" in vacancy_log
    assert "offer_rejected" not in vacancy_log


def test_card_mismatch_logs_the_service_that_rejected_it(client, capsys):
    register_and_confirm(client, email="card-boss@example.com", role="employer")
    saved = client.put("/api/employer/company", json=_CARD)
    assert saved.status_code == 200, saved.text
    capsys.readouterr()
    offer = client.post(
        "/api/employer/offers",
        json={
            "profile_id": 1,
            "category_id": "backend:middle",
            "company_name": "Чужая",
            "message": "Ищем backend",
            "salary_min": 180000,
            "salary_max": 250000,
            "salary_currency": "RUB",
            "contact_channel": "telegram: @sintetika",
        },
    )
    assert offer.status_code == 422
    assert offer.json()["error"] == "company_name"
    offer_log = capsys.readouterr().out
    assert "offer_rejected company_name" in offer_log
    assert "vacancy_rejected" not in offer_log
    vacancy = client.post(
        "/api/employer/vacancies",
        json={
            "title": "Backend middle",
            "description": "Платежи",
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "contact_channel": "почта@example.com",
            "salary_min": 180000,
            "salary_max": 250000,
            "salary_currency": "RUB",
        },
    )
    assert vacancy.status_code == 422
    assert vacancy.json()["error"] == "contact_channel"
    vacancy_log = capsys.readouterr().out
    assert "vacancy_rejected contact_channel" in vacancy_log
    assert "offer_rejected" not in vacancy_log
