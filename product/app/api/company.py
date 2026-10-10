"""Карточка компании работодателя.

ТЗ §2.1, кабинет работодателя: «Профиль компании: описание, направление деятельности, контактные данные».
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_employer
from product.app.db.models import User
from product.app.services.company import get_company, save_company
from product.app.services.errors import example, response_example

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
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        403: {"content": {"application/json": {"example": example("forbidden", "forbidden_employer")}}},
        404: {"content": {"application/json": {"example": example("company_missing")}}},
    },
)
def read_company(user: User = Depends(require_employer), db: Session = Depends(db_session)):
    return get_company(db, user)


@router.put(
    "/employer/company",
    responses={
        200: {"content": {"application/json": {"example": _CARD}}},
        422: response_example(422, example("extra_forbidden")),
    },
)
def write_company(
    payload: dict = Body(..., examples={"card": {"value": _CARD}}),
    user: User = Depends(require_employer),
    db: Session = Depends(db_session),
):
    return save_company(db, user, payload)
