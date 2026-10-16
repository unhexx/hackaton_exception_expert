"""Локальный issuer стенда: PKCE, реалм fsp, подпись, которую принимает oidc.exchange.

ТЗ §3.5 «Аутентификация»: Keycloak — ориентир. Образ сервера стенд не скачивает.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import tarfile
import urllib.parse
from pathlib import Path

import pytest

from product.app.services import oidc
from product.stand_oidc import serve

_REALM = {
    "realm": "fsp",
    "clients": [
        {
            "clientId": "fsp-vacancies",
            "redirectUris": ["http://127.0.0.1:8000/auth/fsp/callback"],
        }
    ],
    "users": [
        {
            "username": "synth",
            "credentials": [{"type": "password", "value": "synth"}],
            "attributes": {"fsp_external_id": ["fsp-synth-1"]},
        }
    ],
}


@pytest.fixture
def stand(monkeypatch, tmp_path):
    realm_path = tmp_path / "fsp-realm.json"
    realm_path.write_text(json.dumps(_REALM), encoding="utf-8")
    placeholder = "http://127.0.0.1:9/realms/fsp"
    server = serve("127.0.0.1", 0, realm_path, placeholder)
    port = server.server_address[1]
    issuer = f"http://127.0.0.1:{port}/realms/fsp"
    server.RequestHandlerClass.stand.issuer = issuer
    monkeypatch.setenv("OIDC_ISSUER", issuer)
    monkeypatch.setenv("OIDC_INTERNAL_ISSUER", issuer)
    monkeypatch.setenv("OIDC_CLIENT_ID", "fsp-vacancies")
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    try:
        yield issuer
    finally:
        server.shutdown()


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _request(method: str, url: str, body: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    payload = None
    headers = {}
    if body is not None:
        payload = urllib.parse.urlencode(body)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=3)
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        got = {key.lower(): value for key, value in response.getheaders()}
        return response.status, got, raw
    finally:
        connection.close()


def _get(url: str) -> tuple[int, dict[str, str], bytes]:
    return _request("GET", url)


def _post(url: str, body: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    return _request("POST", url, body)


def _auth_query(issuer: str, verifier: str, **extra: str) -> str:
    query = {
        "client_id": "fsp-vacancies",
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": "http://127.0.0.1:8000/auth/fsp/callback",
        "state": "state-1",
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
    }
    query.update(extra)
    return f"{issuer}/protocol/openid-connect/auth?{urllib.parse.urlencode(query)}"


def test_exchange_accepts_stand_token(stand: str):
    verifier = "verifier-stand-oidc-32-characters-minimum"
    status, _headers, body = _get(_auth_query(stand, verifier))
    assert status == 200
    assert "synth" in body.decode("utf-8")
    status, headers, _body = _post(
        f"{stand}/protocol/openid-connect/auth",
        {
            "client_id": "fsp-vacancies",
            "response_type": "code",
            "redirect_uri": "http://127.0.0.1:8000/auth/fsp/callback",
            "state": "state-1",
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "username": "synth",
            "password": "synth",
        },
    )
    assert status == 302
    location = urllib.parse.urlsplit(headers["location"])
    params = urllib.parse.parse_qs(location.query)
    assert params["state"] == ["state-1"]
    claims = oidc.exchange(params["code"][0], verifier)
    assert claims["fsp_external_id"] == "fsp-synth-1"
    assert oidc.external_id_from_claims(claims) == "fsp-synth-1"


def test_wrong_password_does_not_redirect(stand: str):
    verifier = "verifier-stand-oidc-32-characters-minimum"
    status, headers, body = _post(
        _auth_query(stand, verifier),
        {"username": "synth", "password": "no"},
    )
    assert status == 401
    assert "location" not in headers
    assert "не подошли" in body.decode("utf-8")


def test_code_is_single_use(stand: str):
    verifier = "verifier-stand-oidc-32-characters-minimum"
    _status, headers, _body = _post(
        _auth_query(stand, verifier),
        {
            "username": "synth",
            "password": "synth",
        },
    )
    code = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["code"][0]
    first = oidc.exchange(code, verifier)
    assert first["sub"] == "synth"
    with pytest.raises(oidc.OidcError) as raised:
        oidc.exchange(code, verifier)
    assert raised.value.code == "unavailable"


def test_foreign_redirect_is_refused(stand: str):
    verifier = "verifier-stand-oidc-32-characters-minimum"
    status, _headers, body = _get(
        _auth_query(stand, verifier, redirect_uri="https://evil.example/cb")
    )
    assert status == 400
    assert "redirect_uri" in body.decode("utf-8")


def test_dockerfiles_do_not_call_docker_hub():
    root = Path(__file__).resolve().parents[2]
    dockerfile = root / "deploy" / "fsp" / "Dockerfile"
    rootfs = root / "deploy" / "fsp" / "python-3.12-slim-rootfs.tar.gz"
    if not dockerfile.is_file():
        return
    text = dockerfile.read_text(encoding="utf-8")
    assert "FROM scratch" in text
    assert "FROM python" not in text
    assert "docker.io" not in text
    assert "pip install" not in text
    assert not (root / "deploy" / "fsp" / "oidc.Dockerfile").exists()
    assert rootfs.is_file()
    with tarfile.open(rootfs, "r:gz") as archive:
        names = archive.getnames()
    assert not any("perl-base" in name or name.endswith("XSLoader.pm") for name in names)
    assert any(name.endswith("bin/python3.12") for name in names)
    assert any("site-packages/fastapi/" in name or name.endswith("site-packages/fastapi") for name in names)


def test_compose_does_not_pull_keycloak_image():
    compose = Path(__file__).resolve().parents[2] / "deploy" / "fsp" / "compose.yaml"
    if not compose.is_file():
        return
    text = compose.read_text(encoding="utf-8")
    assert "image: quay.io/keycloak" not in text
    assert "oidc.Dockerfile" not in text
    assert "pull_policy: never" in text
    assert "image: fsp-vacancies:local" in text
    assert "/srv/product/stand_oidc.py" in text
