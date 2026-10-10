"""Старт, сдача и история испытания грейда (ТЗ §2.1 «Прохождение тестирования»;
ТЗ §3.5 «API: все методы описаны через OpenAPI»).

Механика теста: свой вариант из 12 вопросов, ключ только на сервере, у границы
грейдов — доп. блоки (ответ ``status: "extra"``), итог с уверенностью.
Подробно — ``product/matching/assessment.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import User
from product.app.services.errors import example, response_example
from product.app.services.tests import list_attempts, start_attempt, submit_attempt

router = APIRouter(tags=["tests"])

_STARTED = {
    "attempt_id": 1,
    "template_id": "bank",
    "specialization": "backend",
    "declared_grade": "middle",
    "answered": 0,
    "total": 12,
    "questions": [
        {
            "id": "q1",
            "type": "judge",
            "text": "Синтетический вопрос: оцените каждый вариант",
            "choices": [
                {"id": "3f9a1c07", "text": "первый"},
                {"id": "b41e9d22", "text": "второй"},
                {"id": "0c7d5e18", "text": "третий"},
            ],
        }
    ],
}
_EXTRA = {**_STARTED, "status": "extra", "answered": 12, "total": 18}
_SUBMITTED = {
    "attempt_id": 1,
    "status": "submitted",
    "score": 67,
    "outcome": "confirm",
    "proposed_grade": "middle",
    "category_id": "backend:middle",
    "grade": "middle",
    "confidence": 0.91,
    "test_status": "уверенно",
    "position": "средняя",
    "n_items": 12,
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
        200: {"content": {"application/json": {"examples": {
            "submitted": {"value": _SUBMITTED},
            "extra": {"value": _EXTRA},
        }}}},
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        404: {"content": {"application/json": {"example": example("not_found", "not_found_attempt")}}},
        409: {"content": {"application/json": {"example": example("attempt_closed")}}},
        422: response_example(422, example("answer_unknown")),
    },
)
def submit_route(
    attempt_id: int,
    payload: dict = Body(
        ...,
        examples={
            # judge: для каждого вопроса — id вариантов, отмеченных «верно»
            "by_id": {"value": {"answers": {"q1": ["b41e9d22"], "q2": ["0c7d5e18"]}}},
            "in_order": {"value": {"answers": [["b41e9d22"], ["0c7d5e18"]]}},
        },
    ),
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    # Все открытые вопросы этапа сразу. status "extra" — выданы доп. вопросы.
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
