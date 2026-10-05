"""Карточка компании работодателя."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_employer
from product.app.db.models import User
from product.app.services.company import get_company, save_company

router = APIRouter(tags=["employer"])

_CARD = {
    "name": "Синтетика",
    "description": "Платежи",
    "direction": "backend",
    "contact": "telegram: @sintetika",
}


@router.get(
    "/employer/company",
    responses={
        200: {"content": {"application/json": {"example": _CARD}}},
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет работодателя"}}}},
        404: {"content": {"application/json": {"example": {"error": "company_missing", "message": "Карточка компании не заполнена"}}}},
    },
)
def read_company(user: User = Depends(require_employer), db: Session = Depends(db_session)):
    return get_company(db, user)


@router.put(
    "/employer/company",
    responses={
        200: {"content": {"application/json": {"example": _CARD}}},
        422: {"content": {"application/json": {"example": {"error": "extra_forbidden", "message": "Лишнее поле"}}}},
    },
)
def write_company(
    payload: dict = Body(..., examples={"card": {"value": _CARD}}),
    user: User = Depends(require_employer),
    db: Session = Depends(db_session),
):
    return save_company(db, user, payload)
