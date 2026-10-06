"""Старт, сдача и история испытания грейда."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import User
from product.app.services.tests import list_attempts, start_attempt, submit_attempt

router = APIRouter(tags=["tests"])

_STARTED = {
    "attempt_id": 1,
    "template_id": "backend-middle-a",
    "specialization": "backend",
    "declared_grade": "middle",
    "questions": [
        {
            "id": "q1",
            "text": "Синтетический вопрос",
            "choices": [{"id": "a", "text": "первый"}, {"id": "b", "text": "второй"}],
        }
    ],
}
_SUBMITTED = {
    "attempt_id": 1,
    "score": 67,
    "outcome": "confirm",
    "proposed_grade": "middle",
    "category_id": "backend:middle",
    "grade": "middle",
}


@router.post(
    "/candidate/tests/start",
    status_code=201,
    responses={
        201: {"content": {"application/json": {"example": _STARTED}}},
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
        409: {"content": {"application/json": {"example": {"error": "survey_required", "message": "Сначала заполните анкету"}}}},
    },
)
def start_route(
    payload: dict | None = Body(
        default=None,
        examples={"recorded": {"value": {}}, "adjacent": {"value": {"grade": "senior"}}},
    ),
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    return start_attempt(db, user, payload)


@router.post(
    "/candidate/tests/{attempt_id}/submit",
    responses={
        200: {"content": {"application/json": {"example": _SUBMITTED}}},
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        404: {"content": {"application/json": {"example": {"error": "not_found", "message": "Попытка не найдена"}}}},
        409: {"content": {"application/json": {"example": {"error": "attempt_closed", "message": "Попытка уже сдана"}}}},
        422: {"content": {"application/json": {"example": {"error": "answer_unknown", "message": "Ответ не из вариантов"}}}},
    },
)
def submit_route(
    attempt_id: int,
    payload: dict = Body(..., examples={"answers": {"value": {"answers": ["a", "b", "c"]}}}),
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    return submit_attempt(db, user, attempt_id, payload)


@router.get(
    "/candidate/tests",
    responses={
        200: {"content": {"application/json": {"example": [_SUBMITTED]}}},
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
    },
)
def history_route(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return list_attempts(db, user)
