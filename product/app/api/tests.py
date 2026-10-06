"""Старт, сдача и история испытания грейда."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import User
from product.app.services.errors import example
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
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        403: {"content": {"application/json": {"example": example("forbidden", "forbidden_candidate")}}},
        409: {"content": {"application/json": {"example": example("survey_required")}}},
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
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        404: {"content": {"application/json": {"example": example("not_found", "not_found_attempt")}}},
        409: {"content": {"application/json": {"example": example("attempt_closed")}}},
        422: {"content": {"application/json": {"example": example("answer_unknown")}}},
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
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        403: {"content": {"application/json": {"example": example("forbidden", "forbidden_candidate")}}},
    },
)
def history_route(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    return list_attempts(db, user)
