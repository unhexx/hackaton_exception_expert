"""Регистрация, код подтверждения и вход.

Открытый код в базу не пишется. Сравнение — через Argon2, не по строке хэша.

ТЗ §2.2 п.4 «регистрация по почте с подтверждением адреса»; ТЗ §3.5 «Безопасность».
ТЗ §3.5 «защита от несанкционированного доступа»: код подтверждения сбрасывается
после 5 ошибок, вход по паролю блокируется на 15 минут после 5 ошибок подряд.
"""

from __future__ import annotations

import re
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product.app.db.models import LoginThrottle, User
from product.app.log import log_event
from product.app.services.clock import utc_after, utc_now, is_past
from product.app.services.errors import ApiError, fail
from product.app.services.passwords import hash_secret, verify_secret

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE_ATTEMPTS = 5
_CODE_TTL_MINUTES = 30
_LOGIN_ATTEMPTS = 5
_LOGIN_LOCK_MINUTES = 15


def _clean_email(email: object) -> str:
    if not isinstance(email, str):
        fail(422, "email")
    cleaned = email.strip().lower()
    if len(cleaned) > 254 or not _EMAIL.match(cleaned):
        fail(422, "email")
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
        fail(422, "password_length", minimum=8, maximum=128)
    if role not in ("candidate", "employer"):
        fail(422, "role")
    if role == "candidate":
        if not isinstance(consent, bool):
            fail(422, "consent_required")
        flag = 1 if consent else 0
    else:
        flag = 0
    taken = db.scalar(select(User.id).where(User.email == cleaned))
    if taken is not None:
        fail(409, "email_taken")
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
        fail(409, "email_taken")
    db.refresh(user)
    log_event("register")
    return user, code


def confirm_email(db: Session, *, email: object, code: object) -> None:
    try:
        cleaned = _clean_email(email)
    except ApiError:
        log_event("confirm_failed", "code_invalid")
        fail(400, "code_invalid")
    user = db.scalar(select(User).where(User.email == cleaned))
    if user is None:
        log_event("confirm_failed", "code_invalid")
        fail(400, "code_invalid")
    if user.email_verified:
        fail(409, "already_verified")
    if not user.confirmation_code_hash or user.confirmation_attempts >= _CODE_ATTEMPTS:
        log_event("confirm_failed", "code_locked")
        fail(400, "code_locked", attempts=_CODE_ATTEMPTS)
    if is_past(user.confirmation_expires_at):
        log_event("confirm_failed", "code_expired")
        fail(400, "code_expired", minutes=_CODE_TTL_MINUTES)
    if not isinstance(code, str) or not verify_secret(user.confirmation_code_hash, code):
        user.confirmation_attempts += 1
        if user.confirmation_attempts >= _CODE_ATTEMPTS:
            user.confirmation_code_hash = None
            db.commit()
            log_event("confirm_failed", "code_locked")
            fail(400, "code_locked", attempts=_CODE_ATTEMPTS)
        db.commit()
        log_event("confirm_failed", "code_invalid")
        fail(400, "code_invalid")
    user.email_verified = 1
    user.confirmation_code_hash = None
    user.confirmation_attempts = 0
    user.confirmation_expires_at = None
    db.commit()


def resend_code(db: Session, *, email: object) -> str:
    if not isinstance(email, str):
        fail(400, "email")
    cleaned = email.strip().lower()
    if len(cleaned) > 254 or not _EMAIL.match(cleaned):
        fail(400, "email")
    user = db.scalar(select(User).where(User.email == cleaned))
    if user is None or user.email_verified:
        fail(400, "email", "email_resend")
    code = _new_code()
    user.confirmation_code_hash = hash_secret(code)
    user.confirmation_attempts = 0
    user.confirmation_expires_at = utc_after(_CODE_TTL_MINUTES)
    db.commit()
    return code


def authenticate(db: Session, *, email: object, password: object) -> User:
    """Вход по почте и паролю с защитой от подбора пароля.

    Пять неверных паролей подряд для одного адреса — вход по нему закрыт на
    15 минут (ответ 429), даже с верным паролем. Счётчик ведётся и для
    незарегистрированных адресов, поэтому ответ не раскрывает, есть ли учётка.
    Удачный вход счётчик сбрасывает.
    """
    cleaned = email.strip().lower() if isinstance(email, str) else ""
    throttle = db.get(LoginThrottle, cleaned) if cleaned and len(cleaned) <= 254 else None
    if throttle is not None and throttle.locked_until and not is_past(throttle.locked_until):
        log_event("login_failed", "login_locked")
        fail(429, "login_locked", attempts=_LOGIN_ATTEMPTS, minutes=_LOGIN_LOCK_MINUTES)
    user = db.scalar(select(User).where(User.email == cleaned)) if cleaned else None
    if user is None or not isinstance(password, str) or not verify_secret(user.password_hash, password):
        if cleaned and len(cleaned) <= 254:
            _count_failure(db, throttle, cleaned)
        log_event("login_failed", "credentials")
        fail(401, "credentials")
    if throttle is not None:
        db.delete(throttle)
        db.commit()
    if not user.email_verified:
        log_event("login_failed", "email_unverified")
        fail(403, "email_unverified")
    return user


def _count_failure(db: Session, throttle: LoginThrottle | None, email: str) -> None:
    """+1 к неудачным входам; на пятой — блокировка и обнуление счётчика."""
    if throttle is None:
        throttle = LoginThrottle(email=email, failures=0, locked_until=None)
        db.add(throttle)
    throttle.failures += 1
    if throttle.failures >= _LOGIN_ATTEMPTS:
        throttle.failures = 0
        throttle.locked_until = utc_after(_LOGIN_LOCK_MINUTES)
    db.commit()
