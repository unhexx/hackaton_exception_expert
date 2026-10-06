"""Сессия и роль на каждом маршруте."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from product.app.db.models import User
from product.app.db.session import session_scope
from product.app.services.errors import ApiError, explain


def db_session():
    yield from session_scope()


def load_session_user(request: Request, db: Session) -> User | None:
    raw = request.session.get("user_id")
    if not raw:
        return None
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        request.session.clear()
        return None
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        return None
    return user


def current_user(request: Request, db: Session = Depends(db_session)) -> User:
    user = load_session_user(request, db)
    if user is None:
        raise ApiError(401, "unauthorized", explain("unauthorized"))
    return user


def require_candidate(user: User = Depends(current_user)) -> User:
    if user.role != "candidate":
        raise ApiError(403, "forbidden", explain("forbidden_candidate"))
    return user


def require_employer(user: User = Depends(current_user)) -> User:
    if user.role != "employer":
        raise ApiError(403, "forbidden", explain("forbidden_employer"))
    return user
