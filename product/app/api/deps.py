"""Сессия и роль на каждом маршруте."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from product.app.db.models import User
from product.app.db.session import session_scope
from product.app.services.errors import ApiError


def db_session():
    yield from session_scope()


def current_user(request: Request, db: Session = Depends(db_session)) -> User:
    raw = request.session.get("user_id")
    if not raw:
        raise ApiError(401, "unauthorized", "Нужен вход")
    user = db.get(User, int(raw))
    if user is None:
        raise ApiError(401, "unauthorized", "Нужен вход")
    return user


def require_candidate(user: User = Depends(current_user)) -> User:
    if user.role != "candidate":
        raise ApiError(403, "forbidden", "Это кабинет соискателя")
    return user


def require_employer(user: User = Depends(current_user)) -> User:
    if user.role != "employer":
        raise ApiError(403, "forbidden", "Это кабинет работодателя")
    return user
