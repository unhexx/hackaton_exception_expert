"""Регистрация, код подтверждения и вход.

Открытый код в базу не пишется. Сравнение — через Argon2, не по строке хэша.
"""

from __future__ import annotations

import re
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product.app.db.models import User
from product.app.log import log_event
from product.app.services.clock import utc_after, utc_now, is_past
from product.app.services.errors import ApiError
from product.app.services.passwords import hash_secret, verify_secret

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE_ATTEMPTS = 5
_CODE_TTL_MINUTES = 30


def _clean_email(email: object) -> str:
    if not isinstance(email, str):
        raise ApiError(422, "email", "Некорректная почта")
    cleaned = email.strip().lower()
    if len(cleaned) > 254 or not _EMAIL.match(cleaned):
        raise ApiError(422, "email", "Некорректная почта")
    return cleaned


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def register_user(
    db: Session,
    *,
    email: object,
    password: object,
    role: object,
    consent: object,
) -> tuple[User, str]:
    cleaned = _clean_email(email)
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ApiError(422, "password_length", "Пароль от 8 до 128 символов")
    if role not in ("candidate", "employer"):
        raise ApiError(422, "role", "Роль не из списка")
    if role == "candidate":
        if not isinstance(consent, bool):
            raise ApiError(422, "consent_required", "Нужно явное согласие")
        flag = 1 if consent else 0
    else:
        flag = 0
    taken = db.scalar(select(User.id).where(User.email == cleaned))
    if taken is not None:
        raise ApiError(409, "email_taken", "Почта уже зарегистрирована")
    code = _new_code()
    user = User(
        email=cleaned,
        password_hash=hash_secret(password),
        role=str(role),
        email_verified=0,
        confirmation_code_hash=hash_secret(code),
        confirmation_expires_at=utc_after(_CODE_TTL_MINUTES),
        confirmation_attempts=0,
        consent_processing=flag,
        consent_publication=flag,
        created_at=utc_now(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "email_taken", "Почта уже зарегистрирована") from None
    db.refresh(user)
    log_event("register")
    return user, code


def confirm_email(db: Session, *, email: object, code: object) -> None:
    try:
        cleaned = _clean_email(email)
    except ApiError:
        log_event("confirm_failed", "code_invalid")
        raise ApiError(400, "code_invalid", "Код не подошёл") from None
    user = db.scalar(select(User).where(User.email == cleaned))
    if user is None:
        log_event("confirm_failed", "code_invalid")
        raise ApiError(400, "code_invalid", "Код не подошёл")
    if user.email_verified:
        raise ApiError(409, "already_verified", "Почта уже подтверждена")
    if not user.confirmation_code_hash or user.confirmation_attempts >= _CODE_ATTEMPTS:
        log_event("confirm_failed", "code_locked")
        raise ApiError(400, "code_locked", "Код больше не действует")
    if is_past(user.confirmation_expires_at):
        log_event("confirm_failed", "code_expired")
        raise ApiError(400, "code_expired", "Срок кода истёк")
    if not isinstance(code, str) or not verify_secret(user.confirmation_code_hash, code):
        user.confirmation_attempts += 1
        if user.confirmation_attempts >= _CODE_ATTEMPTS:
            user.confirmation_code_hash = None
            db.commit()
            log_event("confirm_failed", "code_locked")
            raise ApiError(400, "code_locked", "Код больше не действует")
        db.commit()
        log_event("confirm_failed", "code_invalid")
        raise ApiError(400, "code_invalid", "Код не подошёл")
    user.email_verified = 1
    user.confirmation_code_hash = None
    user.confirmation_attempts = 0
    user.confirmation_expires_at = None
    db.commit()


def resend_code(db: Session, *, email: object) -> str:
    if not isinstance(email, str):
        raise ApiError(400, "email", "Некорректная почта")
    cleaned = email.strip().lower()
    if len(cleaned) > 254 or not _EMAIL.match(cleaned):
        raise ApiError(400, "email", "Некорректная почта")
    user = db.scalar(select(User).where(User.email == cleaned))
    if user is None or user.email_verified:
        raise ApiError(400, "email", "Код для этой почты не отправить")
    code = _new_code()
    user.confirmation_code_hash = hash_secret(code)
    user.confirmation_attempts = 0
    user.confirmation_expires_at = utc_after(_CODE_TTL_MINUTES)
    db.commit()
    return code


def authenticate(db: Session, *, email: object, password: object) -> User:
    cleaned = email.strip().lower() if isinstance(email, str) else ""
    user = db.scalar(select(User).where(User.email == cleaned)) if cleaned else None
    if user is None or not isinstance(password, str) or not verify_secret(user.password_hash, password):
        log_event("login_failed", "credentials")
        raise ApiError(401, "credentials", "Неверная почта или пароль")
    if not user.email_verified:
        log_event("login_failed", "email_unverified")
        raise ApiError(403, "email_unverified", "Почта не подтверждена")
    return user
