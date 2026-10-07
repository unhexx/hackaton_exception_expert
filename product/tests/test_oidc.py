"""PKCE и обмен кода без Keycloak: сеть подменяется."""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

from product.app.main import create_app
from product.app.services import oidc

_PUBLIC = "http://127.0.0.1:8080/realms/fsp"
_INTERNAL = "http://keycloak:8080/realms/fsp"


@pytest.fixture(autouse=True)
def _clear_oidc_env(monkeypatch):
    for name in (
        "OIDC_ISSUER",
        "OIDC_INTERNAL_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


def _jwt(payload: dict) -> str:
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("ascii").rstrip("=")
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{head}.{body}.sig"


def _install_http(monkeypatch, payload: dict, seen: dict):
    def get(url: str) -> dict:
        seen["get"] = url
        return {
            "token_endpoint": f"{_PUBLIC}/protocol/openid-connect/token",
        }

    def post(url: str, body: dict) -> dict:
        seen["post"] = url
        seen["body"] = body
        return {"id_token": _jwt(payload)}

    monkeypatch.setattr(oidc, "http_get", get)
    monkeypatch.setattr(oidc, "http_post", post)


def test_challenge_s256():
    started = oidc.begin_link()
    digest = hashlib.sha256(started["code_verifier"].encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    assert started["code_challenge"] == expected
    assert "=" not in started["code_challenge"]
    assert started["code_challenge_method"] == "S256"
    assert started["state"]
    assert started["code_verifier"]
    assert started["url"].startswith(f"{_PUBLIC}/protocol/openid-connect/auth?")
    query = urllib.parse.urlparse(started["url"]).query
    params = urllib.parse.parse_qs(query)
    assert params["client_id"] == ["fsp-vacancies"]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid"]
    assert params["redirect_uri"] == [oidc.REDIRECT_URI]
    assert params["state"] == [started["state"]]
    assert params["code_challenge"] == [expected]
    assert params["code_challenge_method"] == ["S256"]
    again = oidc.begin_link()
    assert again["state"] != started["state"]
    assert again["code_verifier"] != started["code_verifier"]


def test_secret_omitted_when_empty(monkeypatch):
    seen: dict = {}
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    claims = oidc.exchange("code-1", "verifier-1")
    assert claims["sub"] == "fsp-synth-1"
    assert seen["get"] == f"{_INTERNAL}/.well-known/openid-configuration"
    assert seen["post"] == f"{_INTERNAL}/protocol/openid-connect/token"
    assert "client_secret" not in seen["body"]
    assert seen["body"]["grant_type"] == "authorization_code"
    assert seen["body"]["code"] == "code-1"
    assert seen["body"]["redirect_uri"] == oidc.REDIRECT_URI
    assert seen["body"]["client_id"] == "fsp-vacancies"
    assert seen["body"]["code_verifier"] == "verifier-1"


def test_secret_sent_when_set(monkeypatch):
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "stand-secret")
    seen: dict = {}
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    oidc.exchange("code-1", "verifier-1")
    assert seen["body"]["client_secret"] == "stand-secret"


def test_foreign_iss_rejected(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", f"{_PUBLIC}/")
    seen: dict = {}
    _install_http(monkeypatch, {"iss": "http://evil.example/realms/fsp", "sub": "x"}, seen)
    with pytest.raises(oidc.OidcError) as raised:
        oidc.exchange("code-1", "verifier-1")
    assert raised.value.code == "issuer"
    _install_http(monkeypatch, {"iss": _PUBLIC, "sub": "fsp-synth-1"}, seen)
    assert oidc.exchange("code-1", "verifier-1")["sub"] == "fsp-synth-1"


def test_long_claim_not_taken():
    assert oidc.external_id_from_claims({"fsp_external_id": "x" * 65, "sub": "y" * 65}) is None
    assert oidc.external_id_from_claims({"fsp_external_id": "x" * 65, "sub": "ok"}) == "ok"
    assert oidc.external_id_from_claims({"fsp_external_id": "x" * 64}) == "x" * 64
    assert oidc.external_id_from_claims({"fsp_external_id": "", "sub": "sub-1"}) == "sub-1"


def test_sub_when_own_claim_missing():
    assert oidc.external_id_from_claims({"sub": "fsp-synth-1"}) == "fsp-synth-1"
    assert oidc.external_id_from_claims({"fsp_external_id": "fsp-synth-1", "sub": "other"}) == "fsp-synth-1"
    assert oidc.external_id_from_claims({}) is None
    assert oidc.external_id_from_claims({"sub": ""}) is None


def test_import_does_not_call_http(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    importlib.reload(oidc)
    calls: list[str] = []
    monkeypatch.setattr(oidc, "http_get", lambda url: calls.append("get"))
    monkeypatch.setattr(oidc, "http_post", lambda url, body: calls.append("post"))
    importlib.import_module("product.app.services.oidc")
    create_app()
    assert calls == []


def test_network_error_is_service_exception(monkeypatch):
    def broken(*_args, **_kwargs):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "urlopen", broken)
    with pytest.raises(oidc.OidcError) as raised:
        oidc.exchange("code-1", "verifier-1")
    assert raised.value.code == "unavailable"
