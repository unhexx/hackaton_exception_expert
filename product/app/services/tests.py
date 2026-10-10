"""Старт, сдача и история испытания грейда.

Интервал держит смену записанного грейда, не повтор той же пары.
Черновик хранит `template_id`; ключи живут в каталоге; POST сдачи — три буквы a|b|c.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import Profile, TestAttempt, User
from product.app.services.categories import latest_assignment, recompute
from product.app.services.clock import days_elapsed, days_remaining, utc_now
from product.app.services.errors import explain, fail
from product.matching.grade import (
    GradeError,
    is_adjacent_grade,
    load_template,
    public_questions,
    score_attempt,
    select_template,
)
from product.matching.rules import load_rules, rule_version

_OUTCOME = {
    "confirm": "заявленный грейд подтверждён",
    "suggest_lower": "предложен грейд ниже",
    "suggest_higher": "предложен грейд выше",
}


def interval_days() -> int:
    return int(load_rules()["grade_change_interval_days"])


def interval_open(stamp: str) -> bool:
    return days_elapsed(stamp, interval_days())


def interval_parts(profile: Profile, requested: str) -> dict[str, object]:
    days = interval_days()
    return {
        "current": profile.grade,
        "requested": requested,
        "changed_at": profile.grade_changed_at,
        "interval": days,
        "left": days_remaining(profile.grade_changed_at, days),
    }


def interval_message(profile: Profile, requested: str) -> str:
    return explain("grade_interval", **interval_parts(profile, requested))


def grade_written_by_test(db: Session, profile: Profile) -> bool:
    """True, только если соседний confirm уже записал новый грейд (ветка submit_attempt)."""
    rows = db.scalars(
        select(TestAttempt)
        .where(
            TestAttempt.profile_id == profile.id,
            TestAttempt.status == "submitted",
        )
        .order_by(TestAttempt.id.asc())
    ).all()
    if not rows:
        return False
    running = rows[0].declared_grade
    written = False
    for row in rows:
        if row.outcome == "confirm" and row.declared_grade != running:
            written = True
            running = row.declared_grade
    return written


def interval_blocks(db: Session, profile: Profile, requested: str) -> bool:
    """True, когда запрошен не записанный грейд, штамп интервала ещё свежий и соседний confirm уже записал новый грейд.

    Пока тест грейд не писал — соседний старт интервал не ждёт.
    """
    if requested == profile.grade:
        return False
    if interval_open(profile.grade_changed_at):
        return False
    return grade_written_by_test(db, profile)


def _profile(db: Session, user: User) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user.id))


def _draft(db: Session, profile_id: int) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt).where(
            TestAttempt.profile_id == profile_id,
            TestAttempt.status == "draft",
        )
    )


def latest_recorded_attempt(db: Session, profile: Profile) -> TestAttempt | None:
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


def proposed_adjacent(db: Session, profile: Profile) -> str:
    offer = latest_recorded_attempt(db, profile)
    if offer is None or not offer.proposed_grade or offer.proposed_grade == profile.grade:
        return ""
    if not is_adjacent_grade(profile.grade, offer.proposed_grade):
        return ""
    return offer.proposed_grade


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
                "outcome_label": _OUTCOME.get(row.outcome or "", ""),
                "proposed_grade": row.proposed_grade,
                "created_at": row.created_at,
                "submitted_at": row.submitted_at,
            }
        )
    return history


def start_attempt(db: Session, user: User, payload: dict | None) -> dict:
    """Один черновик на профиль. Шаблон выбирает `select_template`; клиент получает вопросы без `correct`.

    Соседний грейд — только предложенный последней сдачей записанной пары.
    """
    profile = _profile(db, user)
    if profile is None:
        fail(409, "survey_required")
    requested = ""
    if payload:
        raw = payload.get("grade", "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            fail(422, "closed_list", "closed_list_grade")
        requested = raw.strip()
    target = profile.grade
    adjacent = False
    if requested and requested != profile.grade:
        if not is_adjacent_grade(profile.grade, requested):
            fail(
                409,
                "grade_not_offered",
                "grade_not_adjacent",
                current=profile.grade,
                requested=requested,
            )
        offered = proposed_adjacent(db, profile)
        if offered != requested:
            fail(
                409,
                "grade_not_offered",
                "grade_not_proposed",
                current=profile.grade,
                requested=requested,
                offered=offered or "нет",
            )
        target = requested
        adjacent = True
    draft = _draft(db, profile.id)
    if draft is not None:
        same = draft.specialization == profile.specialization and draft.declared_grade == target
        if not same:
            fail(
                409,
                "attempt_open",
                draft_grade=draft.declared_grade,
                template_id=draft.template_id,
            )
        return _public_attempt(draft)
    if adjacent and interval_blocks(db, profile, target):
        fail(409, "grade_interval", **interval_parts(profile, target))
    spec = profile.specialization
    try:
        template_id = select_template(profile.id, spec, target, rule_version())
    except GradeError as exc:
        fail(409, exc.code, "template_pair", specialization=spec, grade=target)
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
    """Балл считает `score_attempt` по сохранённому `template_id`. Записанная пара грейд не пишет.

    Соседний `confirm` пишет грейд и штамп; `suggest_higher` на грейде ниже — нет.
    """
    profile = _profile(db, user)
    if profile is None:
        fail(404, "not_found", "not_found_attempt")
    row = db.get(TestAttempt, attempt_id)
    if row is None or row.profile_id != profile.id:
        fail(404, "not_found", "not_found_attempt")
    if row.status != "draft":
        fail(409, "attempt_closed")
    recorded = row.specialization == profile.specialization and row.declared_grade == profile.grade
    if not recorded and interval_blocks(db, profile, row.declared_grade):
        fail(409, "grade_interval", **interval_parts(profile, row.declared_grade))
    answers = payload.get("answers") if isinstance(payload, dict) else None
    try:
        template = load_template(row.template_id)
        scored = score_attempt(template, answers)
    except GradeError as exc:
        if exc.code == "answer_unknown":
            fail(422, "answer_unknown")
        fail(409, exc.code, "template_missing", template_id=row.template_id)
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
    db.commit()
    return {
        "attempt_id": row.id,
        "score": row.score,
        "outcome": row.outcome,
        "proposed_grade": row.proposed_grade,
        "category_id": None if assignment is None else assignment.category_id,
        "grade": profile.grade,
    }
