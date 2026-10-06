"""Чужая роль получает 403, а не чужой кабинет."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from product.app.api.deps import load_session_user
from product.app.web.render import ensure_csrf, render


def same_site_navigation(request: Request) -> bool:
    site = (request.headers.get("sec-fetch-site") or "").casefold()
    return site not in {"cross-site"}


def page_user(request: Request, db: Session, role: str):
    user = load_session_user(request, db)
    if user is None:
        return None, RedirectResponse("/auth/login", status_code=303)
    if user.role != role:
        return None, render(request, "forbidden.html", {"csrf": ensure_csrf(request)}, status_code=403)
    return user, None
