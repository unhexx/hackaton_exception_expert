"""Почта, код на стенде и сессия."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from product.app.api.deps import current_user, db_session
from product.app.db.models import User
from product.app.services.auth import authenticate, confirm_email, register_user, resend_code
from product.app.services.errors import example, response_example

router = APIRouter(prefix="/auth", tags=["auth"])

_CANDIDATE = {
    "email": "seeker@example.com",
    "password": "password-ok",
    "role": "candidate",
    "consent": True,
}
_ERR = example("email")


@router.post(
    "/register",
    status_code=201,
    responses={
        201: {"content": {"application/json": {"example": {"code": "123456"}}}},
        409: {"content": {"application/json": {"example": example("email_taken")}}},
        422: response_example(422, example("consent_required")),
    },
)
def register(
    request: Request,
    payload: dict = Body(..., examples={"candidate": {"value": _CANDIDATE}}),
    db: Session = Depends(db_session),
):
    consent = payload["consent"] if "consent" in payload else None
    user, code = register_user(
        db,
        email=payload.get("email"),
        password=payload.get("password"),
        role=payload.get("role"),
        consent=consent,
    )
    request.session["stand_code"] = code
    request.session["stand_email"] = user.email
    return {"code": code}


@router.post(
    "/confirm",
    responses={
        200: {"content": {"application/json": {"example": {"verified": True}}}},
        400: {"content": {"application/json": {"example": example("code_invalid")}}},
        409: {"content": {"application/json": {"example": example("already_verified")}}},
    },
)
def confirm(
    payload: dict = Body(..., examples={"code": {"value": {"email": "seeker@example.com", "code": "123456"}}}),
    db: Session = Depends(db_session),
):
    confirm_email(db, email=payload.get("email"), code=payload.get("code"))
    return {"verified": True}


@router.post(
    "/confirm/resend",
    responses={
        200: {"content": {"application/json": {"example": {"code": "654321"}}}},
        400: {"content": {"application/json": {"example": _ERR}}},
    },
)
def confirm_resend(
    request: Request,
    payload: dict = Body(..., examples={"email": {"value": {"email": "seeker@example.com"}}}),
    db: Session = Depends(db_session),
):
    code = resend_code(db, email=payload.get("email"))
    request.session["stand_code"] = code
    request.session["stand_email"] = str(payload.get("email", "")).strip().lower()
    return {"code": code}


@router.post(
    "/login",
    responses={
        200: {"content": {"application/json": {"example": {"role": "candidate"}}}},
        401: {"content": {"application/json": {"example": example("credentials")}}},
        403: {"content": {"application/json": {"example": example("email_unverified")}}},
    },
)
def login(
    request: Request,
    payload: dict = Body(
        ...,
        examples={"login": {"value": {"email": "seeker@example.com", "password": "password-ok"}}},
    ),
    db: Session = Depends(db_session),
):
    user = authenticate(db, email=payload.get("email"), password=payload.get("password"))
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    request.session["csrf"] = secrets.token_urlsafe(32)
    return {"role": user.role}


@router.post(
    "/logout",
    status_code=204,
    responses={
        204: {"description": "Сессия закрыта"},
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
    },
)
def logout(request: Request, user: User = Depends(current_user)):
    request.session.clear()
    return Response(status_code=204)
