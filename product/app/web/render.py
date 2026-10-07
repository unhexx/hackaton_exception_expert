"""Jinja и проверка csrf на формах. JSON API это не использует."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from product.app.services.errors import ApiError, fail

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES))


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not isinstance(token, str) or len(token) < 16:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def tokens_match(expected: object, sent: object) -> bool:
    if not isinstance(expected, str) or not isinstance(sent, str):
        return False
    if len(expected) != len(sent) or not expected:
        return False
    return secrets.compare_digest(expected, sent)


def assert_csrf(request: Request, form_token: str) -> None:
    header = request.headers.get("x-csrf-token", "")
    sent = header or form_token
    if not tokens_match(request.session.get("csrf"), sent):
        fail(403, "csrf")


def render(request: Request, name: str, context: dict, status_code: int = 200):
    ctx = dict(context)
    ctx["request"] = request
    try:
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)
    except TypeError:
        return templates.TemplateResponse(name, ctx, status_code=status_code)


def page_error(request: Request, template: str, context: dict, exc: ApiError):
    if exc.error == "csrf":
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.error, "message": exc.message},
        )
    context = dict(context)
    context["error"] = exc.message
    return render(request, template, context, status_code=exc.status)
