"""Анкета соискателя. Первая запись создаёт профиль, согласие и попытку опроса.

Грейд после первой записи этим запросом не меняется: его пишет только тест.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product.app.db.models import CategoryAssignment, Consent, Profile, SurveyAttempt, User
from product.app.services.categories import recompute
from product.app.services.clock import utc_now
from product.app.services.errors import ApiError
from product.matching.rules import load_rules, rule_version

_FORM_FIELDS = (
    "full_name",
    "industry",
    "stack",
    "specialization",
    "grade",
    "team_role",
    "work_format",
    "experience",
    "soft_skills",
    "external_id",
)


def _as_labels(value: object, allowed: list[str], label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in allowed for item in value):
        raise ApiError(422, "closed_list", f"{label} не из списка")
    return list(value)


def _one(value: object, allowed: list[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ApiError(422, "closed_list", "Значение не из списка")
    return value


def latest_assignment(db: Session, profile_id: int) -> CategoryAssignment | None:
    return db.scalar(
        select(CategoryAssignment)
        .where(CategoryAssignment.profile_id == profile_id)
        .order_by(CategoryAssignment.id.desc())
        .limit(1)
    )


def profile_payload(db: Session, user: User, profile: Profile) -> dict:
    consent = db.scalar(select(Consent).where(Consent.profile_id == profile.id))
    assignment = latest_assignment(db, profile.id)
    publication = bool(consent.publication) if consent is not None else False
    return {
        "profile_id": profile.id,
        "full_name": profile.full_name,
        "email": user.email,
        "industry": profile.industry,
        "specialization": profile.specialization,
        "grade": profile.grade,
        "stack": json.loads(profile.stack_json or "[]"),
        "team_role": profile.team_role,
        "work_format": profile.work_format,
        "experience": profile.experience,
        "soft_skills": json.loads(profile.soft_skills_json or "[]"),
        "external_id": profile.external_id,
        "publication": publication,
        "category_id": assignment.category_id if assignment else None,
        "explanation": assignment.explanation if assignment else None,
        "field_sources": json.loads(profile.field_sources_json or "{}"),
    }


def get_own_profile(db: Session, user: User) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise ApiError(404, "not_found", "Анкета ещё не заполнена")
    return profile


def save_profile(db: Session, user: User, payload: dict) -> dict:
    rules = load_rules()
    industry = _one(payload.get("industry"), rules["industries"])
    specialization = _one(payload.get("specialization"), rules["specializations"])
    grade = _one(payload.get("grade"), rules["grades"])
    team_role = _one(payload.get("team_role"), rules["team_roles"])
    work_format = _one(payload.get("work_format"), rules["work_formats"])
    stack = _as_labels(payload.get("stack"), rules["stack"], "Стек")
    soft = _as_labels(payload.get("soft_skills"), rules["soft_skills"], "Софт-скиллы")
    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or not full_name.strip():
        raise ApiError(422, "full_name", "Нужно ФИО")
    experience = payload.get("experience", "")
    if experience is None:
        experience = ""
    if not isinstance(experience, str):
        raise ApiError(422, "experience", "Стаж — строка")
    external = payload.get("external_id")
    if external is None or external == "":
        external_id = None
    elif isinstance(external, str) and external.strip():
        external_id = external.strip()
    else:
        raise ApiError(422, "external_id", "Идентификатор ФСП — строка")
    if "publication" in payload and payload["publication"] is not None:
        if not isinstance(payload["publication"], bool):
            raise ApiError(422, "consent_required", "Публикация — да или нет")
        flag = 1 if payload["publication"] else 0
    else:
        flag = 1 if user.consent_publication else 0

    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is not None and profile.grade != grade:
        raise ApiError(409, "grade_via_test", "Грейд меняет только тест")

    now = utc_now()
    stack_json = json.dumps(stack, ensure_ascii=False)
    soft_json = json.dumps(soft, ensure_ascii=False)
    if profile is None:
        sources = {key: "form" for key in _FORM_FIELDS}
        profile = Profile(
            user_id=user.id,
            full_name=full_name.strip(),
            industry=industry,
            stack_json=stack_json,
            specialization=specialization,
            grade=grade,
            grade_changed_at=now,
            team_role=team_role,
            work_format=work_format,
            experience=experience,
            soft_skills_json=soft_json,
            external_id=external_id,
            field_sources_json=json.dumps(sources, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        db.flush()
        db.add(
            Consent(
                profile_id=profile.id,
                processing=flag,
                publication=flag,
                accepted_at=now,
            )
        )
    else:
        sources = json.loads(profile.field_sources_json or "{}")
        for key in _FORM_FIELDS:
            if key == "grade":
                continue
            sources[key] = "form"
        profile.full_name = full_name.strip()
        profile.industry = industry
        profile.stack_json = stack_json
        profile.specialization = specialization
        profile.team_role = team_role
        profile.work_format = work_format
        profile.experience = experience
        profile.soft_skills_json = soft_json
        profile.external_id = external_id
        profile.field_sources_json = json.dumps(sources, ensure_ascii=False)
        profile.updated_at = now
        consent = db.scalar(select(Consent).where(Consent.profile_id == profile.id))
        if consent is None:
            db.add(
                Consent(
                    profile_id=profile.id,
                    processing=flag,
                    publication=flag,
                    accepted_at=now,
                )
            )
        else:
            consent.processing = flag
            consent.publication = flag
            consent.accepted_at = now

    db.add(
        SurveyAttempt(
            profile_id=profile.id,
            full_name=profile.full_name,
            industry=profile.industry,
            stack_json=profile.stack_json,
            specialization=profile.specialization,
            grade=profile.grade,
            team_role=profile.team_role,
            work_format=profile.work_format,
            experience=profile.experience,
            soft_skills_json=profile.soft_skills_json,
            external_id=profile.external_id,
            rule_version=rule_version(),
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "external_id", "Идентификатор ФСП уже занят") from None
    db.refresh(profile)
    recompute(db, profile.id)
    return profile_payload(db, user, profile)
