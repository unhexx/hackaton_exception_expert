"""Запись полей из текстового PDF. После записи категория пересчитывается тем же правилом, что и после анкеты."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import Profile, TestAttempt, User
from product.app.log import log_event
from product.app.services.categories import latest_assignment, recompute
from product.app.services.clock import utc_now
from product.app.services.errors import ApiError
from product.app.services.profiles import profile_payload
from product.matching.pdf_profile import render_profile_pdf
from product.matching.resume import read_resume_bytes

_MESSAGES = {
    "resume_too_large": "Файл больше 2 МиБ",
    "resume_not_pdf": "Файл не похож на PDF",
    "resume_no_text": "В PDF нет текстового слоя. Скан без текста не читается, заполните поля вручную.",
}
_TEXT_FIELDS = ("full_name", "industry", "specialization", "team_role", "work_format", "experience")


def _reject(code: str) -> None:
    log_event("resume_rejected", code)
    status = 413 if code == "resume_too_large" else 422
    raise ApiError(status, code, _MESSAGES[code])


def _own(db: Session, user: User) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        log_event("resume_rejected", "not_found")
        raise ApiError(404, "not_found", "Анкета ещё не заполнена")
    return profile


def _grade_fixed(db: Session, profile_id: int) -> bool:
    found = db.scalar(
        select(TestAttempt.id).where(
            TestAttempt.profile_id == profile_id,
            TestAttempt.status == "submitted",
            TestAttempt.outcome.is_not(None),
        )
    )
    return found is not None


def apply_resume(db: Session, user: User, data: bytes) -> dict:
    profile = _own(db, user)
    parsed = read_resume_bytes(data)
    code = parsed.get("error")
    if code:
        _reject(str(code))
    sources = json.loads(profile.field_sources_json or "{}")
    for key in _TEXT_FIELDS:
        if key not in parsed:
            continue
        setattr(profile, key, parsed[key])
        sources[key] = "resume"
    if "stack" in parsed:
        profile.stack_json = json.dumps(parsed["stack"], ensure_ascii=False)
        sources["stack"] = "resume"
    if "soft_skills" in parsed:
        profile.soft_skills_json = json.dumps(parsed["soft_skills"], ensure_ascii=False)
        sources["soft_skills"] = "resume"
    skipped = False
    if "grade" in parsed:
        if _grade_fixed(db, profile.id):
            if parsed["grade"] != profile.grade:
                skipped = True
        else:
            profile.grade = parsed["grade"]
            sources["grade"] = "resume"
    profile.field_sources_json = json.dumps(sources, ensure_ascii=False)
    profile.updated_at = utc_now()
    recompute(db, profile.id)
    db.commit()
    db.refresh(profile)
    body = profile_payload(db, user, profile)
    body["grade_skipped"] = skipped
    if skipped:
        body["error"] = "grade_via_test"
        log_event("resume_rejected", "grade_via_test")
    return body


def profile_pdf(db: Session, user: User) -> bytes:
    profile = _own(db, user)
    assignment = latest_assignment(db, profile.id)
    fields = {
        "full_name": profile.full_name,
        "industry": profile.industry,
        "category_id": None if assignment is None else assignment.category_id,
        "specialization": profile.specialization,
        "grade": profile.grade,
        "stack": json.loads(profile.stack_json or "[]"),
        "team_role": profile.team_role,
        "work_format": profile.work_format,
        "experience": profile.experience,
        "soft_skills": json.loads(profile.soft_skills_json or "[]"),
    }
    return render_profile_pdf(fields)
