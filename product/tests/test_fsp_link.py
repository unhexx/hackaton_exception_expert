"""Связь кабинета с ID участника. Keycloak не поднимается.

ТЗ §2 «Профиль кандидата должен иметь возможность связи с ID участника ФСП».
"""

from __future__ import annotations

import base64
import hashlib
import sqlite3
import urllib.parse

from fastapi.testclient import TestClient

from product.app.main import app
from product.app.services import oidc
from product.app.services.errors import explain
from product.tests.conftest import register_and_confirm
from product.tests.oidc_sign import jwks, sign

_PUBLIC = "http://127.0.0.1:8080/realms/fsp"
_PROFILE = {
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "specialization": "backend",
    "grade": "middle",
    "stack": ["python", "sql"],
    "team_role": "разработчик",
    "work_format": "удалённо",
    "experience": "3 года",
    "soft_skills": ["коммуникация"],
    "external_id": "",
    "publication": True,
}


def _install_http(monkeypatch, payload: dict, seen: dict):
    signed = sign(payload)

    def get(url: str) -> dict:
        seen.setdefault("get", []).append(url)
        if url.endswith("openid-configuration"):
            return {
                "token_endpoint": f"{_PUBLIC}/protocol/openid-connect/token",
                "jwks_uri": f"{_PUBLIC}/protocol/openid-connect/certs",
            }
        return jwks()

    def post(url: str, body: dict) -> dict:
        seen.setdefault("post", []).append(url)
        seen["body"] = body
        return {"id_token": signed}

    monkeypatch.setattr(oidc, "http_get", get)
    monkeypatch.setattr(oidc, "http_post", post)


def _external_id(client) -> str | None:
    with sqlite3.connect(client.db_path) as db:
        row = db.execute(
            "select external_id from profiles order by id desc limit 1"
        ).fetchone()
    if row is None:
        return None
    return row[0]


def _counts(client) -> tuple[int, int, int]:
    with sqlite3.connect(client.db_path) as db:
        users = db.execute("select count(*) from users").fetchone()[0]
        profiles = db.execute("select count(*) from profiles").fetchone()[0]
        surveys = db.execute("select count(*) from survey_attempts").fetchone()[0]
    return users, profiles, surveys


def _start(client):
    response = client.get("/auth/fsp/start", follow_redirects=False)
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    return location, query["state"][0], query["code_challenge"][0]


def test_routes_stay_out_of_openapi(client):
    client.get("/auth/login")
    spec = app.openapi()
    assert "/auth/fsp/start" not in spec["paths"]
    assert "/auth/fsp/callback" not in spec["paths"]


def test_client_does_not_call_keycloak(client, monkeypatch):
    calls: list[str] = []

    def blocked(*_args, **_kwargs):
        calls.append("urlopen")
        raise AssertionError("keycloak")

    monkeypatch.setattr("urllib.request.urlopen", blocked)
    assert client.get("/auth/login").status_code == 200
    from product.app.main import create_app

    with TestClient(create_app()) as fresh:
        assert fresh.get("/auth/login").status_code == 200
    assert calls == []


def test_no_session_goes_to_login(client):
    start = client.get("/auth/fsp/start", follow_redirects=False)
    callback = client.get("/auth/fsp/callback", follow_redirects=False)
    assert start.status_code == 303
    assert callback.status_code == 303
    assert start.headers["location"] == "/auth/login"
    assert callback.headers["location"] == "/auth/login"


def test_employer_gets_cabinet_403(client):
    register_and_confirm(client, email="boss@example.com", role="employer")
    start = client.get("/auth/fsp/start")
    callback = client.get("/auth/fsp/callback")
    cabinet = client.get("/candidate")
    assert start.status_code == 403
    assert callback.status_code == 403
    assert cabinet.status_code == 403
    assert start.text == cabinet.text
    assert callback.text == cabinet.text
    assert "Это кабинет соискателя." in start.text


def test_start_stores_begin_link_and_skips_network(client, monkeypatch):
    register_and_confirm(client)
    seen: dict = {}
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    location, _state, _challenge = _start(client)
    assert location.startswith(f"{_PUBLIC}/protocol/openid-connect/auth?")
    assert seen == {}


def test_candidate_without_profile_does_not_insert_row(client, monkeypatch):
    register_and_confirm(client)
    seen: dict = {}
    _install_http(
        monkeypatch,
        {"iss": _PUBLIC, "fsp_external_id": "fsp-synth-1", "email": "other@example.com"},
        seen,
    )
    before = _counts(client)
    _location, state, _challenge = _start(client)
    done = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=False,
    )
    assert done.status_code == 302
    assert done.headers["location"] == "/candidate"
    page = client.get("/candidate")
    assert "Сначала сохраните анкету" in page.text
    assert _counts(client) == before
    assert _external_id(client) is None
    again = client.get("/candidate")
    assert "Сначала сохраните анкету" not in again.text


def test_profile_receives_fsp_synth_1(client, monkeypatch):
    register_and_confirm(client)
    saved = client.put("/api/candidate/profile", json=_PROFILE)
    assert saved.status_code == 200, saved.text
    with sqlite3.connect(client.db_path) as db:
        before = db.execute("select count(*) from category_assignments").fetchone()[0]
    seen: dict = {}
    _install_http(
        monkeypatch,
        {"iss": _PUBLIC, "fsp_external_id": "fsp-synth-1", "sub": "other"},
        seen,
    )
    location, state, challenge = _start(client)
    done = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=False,
    )
    assert done.status_code == 302
    assert done.headers["location"] == "/candidate"
    posted = seen["body"]["code_verifier"]
    digest = hashlib.sha256(posted.encode("ascii")).digest()
    expect = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    assert expect == challenge
    assert "state=" in location
    assert _external_id(client) == "fsp-synth-1"
    with sqlite3.connect(client.db_path) as db:
        after = db.execute("select count(*) from category_assignments").fetchone()[0]
        users = db.execute("select count(*) from users").fetchone()[0]
    assert after == before + 1
    assert users == 1
    page = client.get("/candidate")
    assert "ID участника записан" in page.text
    assert 'value="fsp-synth-1"' in page.text
    assert 'href="/auth/fsp/start"' in page.text
    assert "Связь с ID участника ФСП" in page.text
    assert 'id="external_id"' in page.text
    assert "Почта:" in page.text
    cleared = client.get("/candidate")
    assert "ID участника записан" not in cleared.text
    assert "Тест ещё не сдан" in cleared.text
    assert _external_id(client) == "fsp-synth-1"


def test_foreign_state_does_not_write(client, monkeypatch):
    register_and_confirm(client)
    assert client.put("/api/candidate/profile", json=_PROFILE).status_code == 200
    seen: dict = {}
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    _start(client)
    done = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": "not-the-state"},
        follow_redirects=False,
    )
    assert done.status_code == 302
    assert seen == {}
    assert _external_id(client) in {None, ""}
    page = client.get("/candidate")
    assert "Запрос связи не совпал" in page.text


def test_foreign_iss_empty_id_and_unreachable_do_not_write(client, monkeypatch):
    register_and_confirm(client)
    assert client.put("/api/candidate/profile", json=_PROFILE).status_code == 200

    seen: dict = {}
    _install_http(monkeypatch, {"iss": "http://evil.example/realms/fsp", "sub": "fsp-synth-1"}, seen)
    _location, state, _challenge = _start(client)
    foreign = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=True,
    )
    assert foreign.status_code == 200
    assert "Issuer токена не совпал." in foreign.text
    assert _external_id(client) in {None, ""}

    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "", "fsp_external_id": ""}, seen)
    _location, state, _challenge = _start(client)
    empty = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=True,
    )
    assert "В токене нет годного идентификатора участника." in empty.text
    assert _external_id(client) in {None, ""}

    def down(_url: str) -> dict:
        raise oidc.OidcError("unavailable")

    monkeypatch.setattr(oidc, "http_get", down)
    _location, state, _challenge = _start(client)
    offline = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=True,
    )
    assert "Keycloak недоступен." in offline.text
    assert _external_id(client) in {None, ""}


def test_taken_external_id_rolls_back(client, monkeypatch):
    register_and_confirm(client, email="first@example.com")
    assert client.put(
        "/api/candidate/profile",
        json={**_PROFILE, "external_id": "fsp-synth-1"},
    ).status_code == 200
    register_and_confirm(client, email="second@example.com")
    assert client.put("/api/candidate/profile", json=_PROFILE).status_code == 200
    seen: dict = {}
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    _location, state, _challenge = _start(client)
    page = client.get(
        "/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=True,
    )
    assert explain("external_id_taken") in page.text
    with sqlite3.connect(client.db_path) as db:
        rows = db.execute(
            "select u.email, p.external_id from profiles p join users u on u.id = p.user_id order by p.id"
        ).fetchall()
    assert rows == [("first@example.com", "fsp-synth-1"), ("second@example.com", None)]
