"""Приглашение: контакт компании виден сразу, почта соискателя только после принятия."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate, require_employer
from product.app.db.models import User
from product.app.services.offers import (
    create_offer,
    get_offer,
    list_candidate_offers,
    list_employer_offers,
    open_offer,
    set_offer_status,
)

router = APIRouter(tags=["offers"])

_CREATED = {
    "id": 1,
    "profile_id": 12,
    "category_id": "backend:middle",
    "company_name": "Синтетика",
    "message": "Ищем backend middle в команду платежей",
    "salary_min": 180000,
    "salary_max": 250000,
    "salary_currency": "RUB",
    "contact_channel": "telegram: @sintetika",
    "status": "sent",
    "created_at": "2026-10-05T12:00:00Z",
    "updated_at": "2026-10-05T12:00:00Z",
}
_ACCEPTED = {**_CREATED, "status": "accepted", "candidate_email": "seeker@example.com"}
_BODY = {
    "profile_id": 12,
    "category_id": "backend:middle",
    "company_name": "Синтетика",
    "message": "Ищем backend middle в команду платежей",
    "salary_min": 180000,
    "salary_max": 250000,
    "salary_currency": "RUB",
    "contact_channel": "telegram: @sintetika",
}
_DENIED = {"error": "unauthorized", "message": "Нужен вход"}
_FORBIDDEN = {"error": "forbidden", "message": "Это кабинет работодателя"}
_RANGE = {"error": "salary_range", "message": "Верхняя граница больше нижней"}
_MISSING = {"error": "not_found", "message": "Приглашение не найдено"}
_CLOSED = {"error": "offer_closed", "message": "Приглашение уже закрыто"}


@router.post(
    "/employer/offers",
    status_code=201,
    responses={
        201: {"content": {"application/json": {"example": _CREATED}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": _FORBIDDEN}}},
        404: {"content": {"application/json": {"example": {"error": "profile_not_in_category", "message": "Профиля нет в этой категории"}}}},
        409: {"content": {"application/json": {"example": {"error": "offer_open", "message": "Открытое приглашение уже есть"}}}},
        422: {"content": {"application/json": {"example": _RANGE}}},
    },
)
def send_offer(
    payload: dict = Body(..., examples={"offer": {"value": _BODY}}),
    user: User = Depends(require_employer),
    db: Session = Depends(db_session),
):
    return create_offer(db, user, payload)


@router.get(
    "/employer/offers",
    responses={
        200: {"content": {"application/json": {"example": [_ACCEPTED]}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": _FORBIDDEN}}},
    },
)
def employer_offers(user: User = Depends(require_employer), db: Session = Depends(db_session)):
    return list_employer_offers(db, user)


@router.get(
    "/candidate/offers",
    responses={
        200: {"content": {"application/json": {"example": [_CREATED]}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
    },
)
def candidate_offers(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return list_candidate_offers(db, user)


@router.get(
    "/candidate/offers/{offer_id}",
    responses={
        200: {"content": {"application/json": {"example": _CREATED}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
    },
)
def read_offer(offer_id: int, user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return get_offer(db, user, offer_id)


@router.post(
    "/candidate/offers/{offer_id}/open",
    responses={
        200: {"content": {"application/json": {"example": {**_CREATED, "status": "seen"}}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
    },
)
def open_offer_route(offer_id: int, user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return open_offer(db, user, offer_id)


@router.post(
    "/candidate/offers/{offer_id}/accept",
    responses={
        200: {"content": {"application/json": {"example": {**_CREATED, "status": "accepted"}}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
        409: {"content": {"application/json": {"example": _CLOSED}}},
    },
)
def accept_offer(offer_id: int, user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return set_offer_status(db, user, offer_id, "accepted")


@router.post(
    "/candidate/offers/{offer_id}/decline",
    responses={
        200: {"content": {"application/json": {"example": {**_CREATED, "status": "declined"}}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
        409: {"content": {"application/json": {"example": _CLOSED}}},
    },
)
def decline_offer(offer_id: int, user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return set_offer_status(db, user, offer_id, "declined")
