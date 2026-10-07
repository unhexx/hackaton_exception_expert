"""Связь профиля с issuer: PKCE и обмен кода.

Сеть открывает только exchange. Импорт модуля и сборка приложения к Keycloak не ходят.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

REDIRECT_URI = "http://127.0.0.1:8000/auth/fsp/callback"

_DEFAULT_ISSUER = "http://127.0.0.1:8080/realms/fsp"
_DEFAULT_INTERNAL_ISSUER = "http://keycloak:8080/realms/fsp"
_DEFAULT_CLIENT_ID = "fsp-vacancies"
_TIMEOUT_SECONDS = 3


class OidcError(Exception):
    """Keycloak не ответил или токен не подошёл. На старте процесса не бросается."""

    def __init__(self, code: str) -> None:
        self.code = code
        text = {
            "unavailable": "Keycloak недоступен.",
            "issuer": "Issuer токена не совпал.",
            "token": "Токен не разобран.",
        }[code]
        super().__init__(text)


def begin_link() -> dict[str, str]:
    """state, code_verifier и url авторизации. Сеть не нужна."""
    verifier = secrets.token_urlsafe(32)
    challenge = _challenge(verifier)
    state = secrets.token_urlsafe(32)
    query = urllib.parse.urlencode(
        (
            ("client_id", _client_id()),
            ("response_type", "code"),
            ("scope", "openid"),
            ("redirect_uri", REDIRECT_URI),
            ("state", state),
            ("code_challenge", challenge),
            ("code_challenge_method", "S256"),
        )
    )
    return {
        "state": state,
        "code_verifier": verifier,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "url": f"{_public_issuer()}/protocol/openid-connect/auth?{query}",
    }


def exchange(code: str, verifier: str) -> dict:
    """Код на id_token. Ходит только на внутренний issuer."""
    public = _public_issuer()
    internal = _internal_issuer()
    discovery = http_get(f"{internal}/.well-known/openid-configuration")
    token_url = _token_url(discovery.get("token_endpoint"), public, internal)
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": _client_id(),
        "code_verifier": verifier,
    }
    secret = _client_secret()
    if secret:
        body["client_secret"] = secret
    token = http_post(token_url, body)
    id_token = token.get("id_token")
    if not isinstance(id_token, str):
        raise OidcError("token")
    claims = _claims(id_token)
    iss = claims.get("iss")
    if not isinstance(iss, str) or iss.rstrip("/") != public:
        raise OidcError("issuer")
    return claims


def external_id_from_claims(claims: dict) -> str | None:
    """Непустой fsp_external_id до 64 символов, иначе такой же sub. Не обрезает."""
    own = _fit(claims.get("fsp_external_id"))
    if own is not None:
        return own
    return _fit(claims.get("sub"))


def http_get(url: str) -> dict:
    return _read(url, None)


def http_post(url: str, body: dict[str, str]) -> dict:
    encoded = urllib.parse.urlencode(body).encode("ascii")
    return _read(url, encoded)


def _read(url: str, data: bytes | None) -> dict:
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
    )
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OidcError("unavailable") from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OidcError("unavailable") from exc
    if not isinstance(parsed, dict):
        raise OidcError("unavailable")
    return parsed


def _claims(id_token: str) -> dict:
    # Подпись отдельной библиотекой не проверяется: берётся только середина JWT.
    parts = id_token.split(".")
    if len(parts) != 3 or not parts[1]:
        raise OidcError("token")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OidcError("token") from exc
    if not isinstance(parsed, dict):
        raise OidcError("token")
    return parsed


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _fit(value: object) -> str | None:
    if not isinstance(value, str) or value == "" or len(value) > 64:
        return None
    return value


def _public_issuer() -> str:
    return _env_url("OIDC_ISSUER", _DEFAULT_ISSUER)


def _internal_issuer() -> str:
    return _env_url("OIDC_INTERNAL_ISSUER", _DEFAULT_INTERNAL_ISSUER)


def _client_id() -> str:
    return _env_text("OIDC_CLIENT_ID", _DEFAULT_CLIENT_ID)


def _client_secret() -> str:
    return os.environ.get("OIDC_CLIENT_SECRET", "").strip()


def _env_text(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_url(name: str, default: str) -> str:
    return _env_text(name, default).rstrip("/")


def _token_url(token_endpoint: object, public: str, internal: str) -> str:
    # Discovery может отдать публичный token_endpoint. Обмен идёт на внутренний адрес.
    if isinstance(token_endpoint, str) and token_endpoint.startswith(public):
        rest = token_endpoint[len(public):]
        if rest == "" or rest.startswith("/"):
            return internal + rest
    return f"{internal}/protocol/openid-connect/token"
