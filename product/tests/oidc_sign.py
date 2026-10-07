"""Тестовый id_token, подписанный RS256. Ключ один на процесс."""

from __future__ import annotations

import base64
import json
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "stand-test"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def jwks() -> dict:
    numbers = _PRIVATE.public_key().public_numbers()
    modulus = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    exponent = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _KID,
                "n": _b64(modulus),
                "e": _b64(exponent),
            }
        ]
    }


def sign(payload: dict, *, aud: str = "fsp-vacancies", exp: int | None = None) -> str:
    claims = dict(payload)
    claims.setdefault("aud", aud)
    claims.setdefault("exp", exp if exp is not None else int(time.time()) + 3600)
    header = {"alg": "RS256", "typ": "JWT", "kid": _KID}
    signing = ".".join(
        (
            _b64(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8")),
        )
    )
    signature = _PRIVATE.sign(
        signing.encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return f"{signing}.{_b64(signature)}"
