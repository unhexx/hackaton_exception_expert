"""Чужая роль получает 403, а не чужой кабинет."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from product.app.db.models import User
from product.app.web.render import ensure_csrf, render


def page_user(request: Request, db: Session, role: str):
    raw = request.session.get("user_id")
    if not raw:
        return None, RedirectResponse("/auth/login", status_code=303)
    user = db.get(User, int(raw))
    if user is None:
        request.session.clear()
        return None, RedirectResponse("/auth/login", status_code=303)
    if user.role != role:
        return None, render(request, "forbidden.html", {"csrf": ensure_csrf(request)}, status_code=403)
    return user, None
