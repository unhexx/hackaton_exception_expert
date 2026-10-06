"""Общий стенд тестов: временный SQLite, секрет и клиент.

Новые фикстуры срезов сюда не добавлять.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if len(os.environ.get("PRODUCT_SECRET", "")) < 32:
    os.environ["PRODUCT_SECRET"] = "test-secret-32-characters-minimum!!"
os.environ["PRODUCT_COOKIE_SECURE"] = "0"

import pytest
from fastapi.testclient import TestClient

from product.app.db.session import reset_engine
from product.seed import init_db


def pytest_sessionfinish(session, exitstatus):
    from product.tests.badge import write_session_badge

    write_session_badge(session, exitstatus)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "app.sqlite"
    monkeypatch.setenv("PRODUCT_SQLITE", str(db_path))
    reset_engine()
    init_db()
    from product.app.main import app

    app.openapi_schema = None
    with TestClient(app) as test_client:
        test_client.db_path = db_path
        yield test_client
    reset_engine()


def register_and_confirm(
    client: TestClient,
    email: str = "seeker@example.com",
    password: str = "password-ok",
    role: str = "candidate",
    consent: bool = True,
):
    body: dict = {"email": email, "password": password, "role": role}
    if role == "candidate":
        body["consent"] = consent
    created = client.post("/api/auth/register", json=body)
    assert created.status_code == 201, created.text
    confirmed = client.post(
        "/api/auth/confirm",
        json={"email": email, "code": created.json()["code"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    logged = client.post("/api/auth/login", json={"email": email, "password": password})
    assert logged.status_code == 200, logged.text
    return logged
