"""Argon2id с параметрами OWASP для нового приложения: 19 МиБ, t=2, p=1.

memory_cost в argon2-cffi задаётся в кибибайтах, поэтому передаём 19456.

ТЗ §3.5 «Безопасность: безопасное хранение паролей».
"""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    type=Type.ID,
)


def hash_secret(value: str) -> str:
    return hasher.hash(value)


def verify_secret(stored: str | None, value: str) -> bool:
    if not stored or not isinstance(value, str):
        return False
    try:
        return bool(hasher.verify(stored, value))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
