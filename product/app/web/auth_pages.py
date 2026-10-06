"""Регистрация, код на странице и вход. Кода в адресе нет."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.services.auth import authenticate, confirm_email, register_user, resend_code
from product.app.services.errors import ApiError
from product.app.web.render import assert_csrf, ensure_csrf, page_error, render

router = APIRouter()


def _checked(value: str | None) -> bool:
    return value in {"1", "on", "true", "True"}


@router.get("/auth/register")
def register_form(request: Request):
    return render(
        request,
        "auth/register.html",
        {"csrf": ensure_csrf(request), "error": ""},
    )


@router.post("/auth/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    csrf: str = Form(""),
    consent: str | None = Form(None),
    db: Session = Depends(db_session),
):
    try:
        assert_csrf(request, csrf)
        flag: bool | None = _checked(consent) if role == "candidate" else None
        user, code = register_user(db, email=email, password=password, role=role, consent=flag)
    except ApiError as exc:
        return page_error(
            request,
            "auth/register.html",
            {"csrf": ensure_csrf(request)},
            exc,
        )
    request.session["stand_code"] = code
    request.session["stand_email"] = user.email
    return RedirectResponse("/auth/confirm", status_code=303)


@router.get("/auth/confirm")
def confirm_form(request: Request):
    return render(
        request,
        "auth/confirm.html",
        {
            "csrf": ensure_csrf(request),
            "error": "",
            "code": request.session.get("stand_code", ""),
            "email": request.session.get("stand_email", ""),
        },
    )


@router.post("/auth/confirm")
def confirm_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    try:
        assert_csrf(request, csrf)
        confirm_email(db, email=email, code=code)
    except ApiError as exc:
        return page_error(
            request,
            "auth/confirm.html",
            {
                "csrf": ensure_csrf(request),
                "code": request.session.get("stand_code", ""),
                "email": email,
            },
            exc,
        )
    request.session.pop("stand_code", None)
    return RedirectResponse("/auth/login", status_code=303)


@router.post("/auth/confirm/resend")
def confirm_resend(
    request: Request,
    email: str = Form(...),
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    try:
        assert_csrf(request, csrf)
        code = resend_code(db, email=email)
    except ApiError as exc:
        return page_error(
            request,
            "auth/confirm.html",
            {"csrf": ensure_csrf(request), "code": "", "email": email},
            exc,
        )
    request.session["stand_code"] = code
    request.session["stand_email"] = email.strip().lower()
    return RedirectResponse("/auth/confirm", status_code=303)


@router.get("/auth/login")
def login_form(request: Request):
    return render(request, "auth/login.html", {"csrf": ensure_csrf(request), "error": ""})


@router.post("/auth/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    try:
        assert_csrf(request, csrf)
        user = authenticate(db, email=email, password=password)
    except ApiError as exc:
        return page_error(
            request,
            "auth/login.html",
            {"csrf": ensure_csrf(request)},
            exc,
        )
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    request.session["csrf"] = secrets.token_urlsafe(32)
    target = "/candidate" if user.role == "candidate" else "/employer"
    return RedirectResponse(target, status_code=303)


@router.post("/auth/logout")
def logout_submit(request: Request, csrf: str = Form("")):
    try:
        assert_csrf(request, csrf)
    except ApiError as exc:
        return page_error(request, "auth/login.html", {"csrf": ensure_csrf(request)}, exc)
    request.session.clear()
    return RedirectResponse("/auth/login", status_code=303)
