"""Связь профиля с issuer: PKCE, обмен кода и проверка подписи RS256.

Сеть открывает только exchange. Импорт модуля и сборка приложения к Keycloak не ходят.
Боевой коннектор — тот же обмен: JWKS берётся у issuer из окружения, не из локального реалма.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

REDIRECT_URI = "http://127.0.0.1:8000/auth/fsp/callback"

_DEFAULT_ISSUER = "http://127.0.0.1:8080/realms/fsp"
_DEFAULT_INTERNAL_ISSUER = "http://keycloak:8080/realms/fsp"
_DEFAULT_CLIENT_ID = "fsp-vacancies"
_TIMEOUT_SECONDS = 3
_SKEW_SECONDS = 30


class OidcError(Exception):
    """Keycloak не ответил или токен не подошёл. На старте процесса не бросается."""

    def __init__(self, code: str) -> None:
        self.code = code
        text = {
            "unavailable": "Keycloak недоступен.",
            "issuer": "Issuer токена не совпал.",
            "token": "Токен не разобран.",
            "signature": "Подпись токена не сошлась.",
            "expired": "Срок токена вышел.",
            "audience": "Токен выписан не этому клиенту.",
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
    """Код на проверенный id_token. Ходит только на внутренний issuer."""
    public = _public_issuer()
    internal = _internal_issuer()
    client_id = _client_id()
    discovery = http_get(f"{internal}/.well-known/openid-configuration")
    token_url = _rewritten(discovery.get("token_endpoint"), public, internal, "token")
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    secret = _client_secret()
    if secret:
        body["client_secret"] = secret
    token = http_post(token_url, body)
    id_token = token.get("id_token")
    if not isinstance(id_token, str):
        raise OidcError("token")
    jwks_url = _rewritten(discovery.get("jwks_uri"), public, internal, "certs")
    return _verified_claims(id_token, http_get(jwks_url), public, client_id)


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


def _verified_claims(id_token: str, jwks: dict, public: str, client_id: str) -> dict:
    header, claims, signing_input, signature = _parts(id_token)
    if header.get("alg") != "RS256":
        raise OidcError("token")
    key = _rsa_key(_select_jwk(jwks, header.get("kid")))
    try:
        key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise OidcError("signature") from exc
    iss = claims.get("iss")
    if not isinstance(iss, str) or iss.rstrip("/") != public:
        raise OidcError("issuer")
    _fresh(claims.get("exp"), claims.get("nbf"))
    if not _audience(claims.get("aud"), claims.get("azp"), client_id):
        raise OidcError("audience")
    return claims


def _parts(id_token: str) -> tuple[dict, dict, bytes, bytes]:
    pieces = id_token.split(".")
    if len(pieces) != 3 or not all(pieces):
        raise OidcError("token")
    try:
        header = json.loads(_b64(pieces[0]))
        claims = json.loads(_b64(pieces[1]))
        signature = _b64(pieces[2])
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OidcError("token") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OidcError("token")
    return header, claims, f"{pieces[0]}.{pieces[1]}".encode("ascii"), signature


def _select_jwk(jwks: dict, kid: object) -> dict:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise OidcError("token")
    usable = [
        key for key in keys
        if isinstance(key, dict) and key.get("kty") == "RSA" and key.get("use", "sig") == "sig"
    ]
    if isinstance(kid, str) and kid != "":
        usable = [key for key in usable if key.get("kid") == kid]
    if len(usable) != 1:
        raise OidcError("token")
    return usable[0]


def _rsa_key(jwk: dict):
    n_raw = jwk.get("n")
    e_raw = jwk.get("e")
    if not isinstance(n_raw, str) or not isinstance(e_raw, str):
        raise OidcError("token")
    try:
        modulus = int.from_bytes(_b64(n_raw), "big")
        exponent = int.from_bytes(_b64(e_raw), "big")
        return RSAPublicNumbers(exponent, modulus).public_key()
    except ValueError as exc:
        raise OidcError("token") from exc


def _fresh(exp: object, nbf: object) -> None:
    now = int(time.time())
    if not isinstance(exp, int) or exp < now - _SKEW_SECONDS:
        raise OidcError("expired")
    if nbf is not None and (not isinstance(nbf, int) or nbf > now + _SKEW_SECONDS):
        raise OidcError("expired")


def _audience(aud: object, azp: object, client_id: str) -> bool:
    if isinstance(aud, str):
        values = [aud]
    elif isinstance(aud, list) and all(isinstance(item, str) for item in aud):
        values = aud
    else:
        return False
    if client_id in values:
        return True
    return "account" in values and azp == client_id


def _b64(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


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


def _rewritten(endpoint: object, public: str, internal: str, leaf: str) -> str:
    # Discovery может отдать публичный адрес. Обмен и JWKS идут на внутренний.
    if isinstance(endpoint, str) and endpoint.startswith(public):
        rest = endpoint[len(public):]
        if rest == "" or rest.startswith("/"):
            return internal + rest
    return f"{internal}/protocol/openid-connect/{leaf}"
