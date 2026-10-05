"""Старт, сдача и история испытания грейда."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import Profile, TestAttempt, User
from product.app.services.categories import latest_assignment, recompute
from product.app.services.clock import utc_now
from product.app.services.errors import ApiError
from product.matching.grade import GradeError, load_template, public_questions, score_attempt, select_template
from product.matching.rules import load_rules, rule_version

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


def _parse_stamp(stamp: str) -> datetime:
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def interval_open(stamp: str) -> bool:
    days = int(load_rules()["grade_change_interval_days"])
    return datetime.now(timezone.utc) >= _parse_stamp(stamp) + timedelta(days=days)


def _grades() -> list[str]:
    return list(load_rules()["grades"])


def _one_step(current: str, requested: str) -> bool:
    grades = _grades()
    if current not in grades or requested not in grades:
        return False
    return abs(grades.index(current) - grades.index(requested)) == 1


def _profile(db: Session, user: User) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user.id))


def _draft(db: Session, profile_id: int) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt).where(
            TestAttempt.profile_id == profile_id,
            TestAttempt.status == "draft",
        )
    )


def _offer(db: Session, profile: Profile) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt)
        .where(
            TestAttempt.profile_id == profile.id,
            TestAttempt.status == "submitted",
            TestAttempt.specialization == profile.specialization,
            TestAttempt.declared_grade == profile.grade,
        )
        .order_by(TestAttempt.id.desc())
        .limit(1)
    )


def _public_attempt(row: TestAttempt) -> dict:
    template = load_template(row.template_id)
    return {
        "attempt_id": row.id,
        "template_id": row.template_id,
        "specialization": row.specialization,
        "declared_grade": row.declared_grade,
        "questions": public_questions(template),
    }


def list_attempts(db: Session, user: User) -> list[dict]:
    profile = _profile(db, user)
    if profile is None:
        return []
    rows = db.scalars(
        select(TestAttempt).where(TestAttempt.profile_id == profile.id).order_by(TestAttempt.id.desc())
    ).all()
    history = []
    for row in rows:
        history.append(
            {
                "attempt_id": row.id,
                "template_id": row.template_id,
                "specialization": row.specialization,
                "declared_grade": row.declared_grade,
                "status": row.status,
                "score": row.score,
                "outcome": row.outcome,
                "proposed_grade": row.proposed_grade,
                "created_at": row.created_at,
                "submitted_at": row.submitted_at,
            }
        )
    return history


def start_attempt(db: Session, user: User, payload: dict | None) -> dict:
    profile = _profile(db, user)
    if profile is None:
        raise ApiError(409, "survey_required", "Сначала заполните анкету")
    requested = ""
    if payload:
        raw = payload.get("grade", "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            raise ApiError(422, "closed_list", "Грейд — строка")
        requested = raw.strip()
    target = profile.grade
    adjacent = False
    if requested and requested != profile.grade:
        if not _one_step(profile.grade, requested):
            raise ApiError(409, "grade_not_offered", "Этот грейд не предложен")
        offer = _offer(db, profile)
        if offer is None or offer.proposed_grade != requested:
            raise ApiError(409, "grade_not_offered", "Этот грейд не предложен")
        target = requested
        adjacent = True
    draft = _draft(db, profile.id)
    if draft is not None:
        same = draft.specialization == profile.specialization and draft.declared_grade == target
        if not same:
            raise ApiError(409, "attempt_open", "Сначала сдайте открытый тест")
        return _public_attempt(draft)
    if adjacent and not interval_open(profile.grade_changed_at):
        raise ApiError(409, "grade_interval", "Смена грейда ещё рано")
    spec = profile.specialization
    try:
        template_id = select_template(profile.id, spec, target, rule_version())
    except GradeError as exc:
        raise ApiError(409, exc.code, "Для пары нет двух своих шаблонов") from exc
    row = TestAttempt(
        profile_id=profile.id,
        specialization=spec,
        declared_grade=target,
        template_id=template_id,
        rule_version=rule_version(),
        answers_json=None,
        score=None,
        outcome=None,
        proposed_grade=None,
        status="draft",
        created_at=utc_now(),
        submitted_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _public_attempt(row)


def submit_attempt(db: Session, user: User, attempt_id: int, payload: dict) -> dict:
    profile = _profile(db, user)
    if profile is None:
        raise ApiError(404, "not_found", "Попытка не найдена")
    row = db.get(TestAttempt, attempt_id)
    if row is None or row.profile_id != profile.id:
        raise ApiError(404, "not_found", "Попытка не найдена")
    if row.status != "draft":
        raise ApiError(409, "attempt_closed", "Попытка уже сдана")
    recorded = row.specialization == profile.specialization and row.declared_grade == profile.grade
    if not recorded and not interval_open(profile.grade_changed_at):
        raise ApiError(409, "grade_interval", "Смена грейда ещё рано")
    answers = payload.get("answers") if isinstance(payload, dict) else None
    try:
        template = load_template(row.template_id)
        scored = score_attempt(template, answers)
    except GradeError as exc:
        if exc.code == "answer_unknown":
            raise ApiError(422, "answer_unknown", "Ответ не из вариантов") from exc
        raise ApiError(409, exc.code, "Шаблон испытания не найден") from exc
    row.answers_json = json.dumps(answers, ensure_ascii=False)
    row.score = scored["score"]
    row.outcome = scored["outcome"]
    row.proposed_grade = scored["proposed_grade"]
    row.status = "submitted"
    row.submitted_at = utc_now()
    if not recorded and scored["outcome"] == "confirm":
        profile.grade = row.declared_grade
        profile.grade_changed_at = row.submitted_at
        profile.updated_at = row.submitted_at
    db.flush()
    recompute(db, profile.id)
    assignment = latest_assignment(db, profile.id)
    return {
        "attempt_id": row.id,
        "score": row.score,
        "outcome": row.outcome,
        "proposed_grade": row.proposed_grade,
        "category_id": None if assignment is None else assignment.category_id,
        "grade": profile.grade,
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
