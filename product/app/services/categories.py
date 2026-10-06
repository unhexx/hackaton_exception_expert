"""Сохраняет назначение категории и собирает выдачу работодателя.

Правила живут в product.matching. Здесь только запись и фильтр чтения.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from product.app.db.models import CategoryAssignment as StoredCategory
from product.app.db.models import Consent, FspAchievement, FspParticipant, Profile, TestAttempt
from product.app.services.clock import utc_now
from product.app.services.errors import ApiError
from product.matching.category import assign_category
from product.matching.need import haystack_text, list_reason, matches_need, need_score, rank_tuple
from product.matching.rules import load_rules, rule_version
from product.matching.types import ProfileView


def recompute(session: Session, profile_id: int) -> None:
    session.flush()
    profile = session.get(Profile, profile_id)
    if profile is None:
        return
    fsp_count = 0
    if profile.external_id:
        fsp_count = int(
            session.scalar(
                select(func.count())
                .select_from(FspAchievement)
                .where(FspAchievement.external_id == profile.external_id)
            )
            or 0
        )
    attempt = session.scalar(
        select(TestAttempt)
        .where(
            TestAttempt.profile_id == profile.id,
            TestAttempt.status == "submitted",
            TestAttempt.specialization == profile.specialization,
            TestAttempt.declared_grade == profile.grade,
            TestAttempt.score.is_not(None),
        )
        .order_by(TestAttempt.id.desc())
        .limit(1)
    )
    view = ProfileView(
        profile_id=profile.id,
        specialization=profile.specialization,
        grade=profile.grade,
        test_score=None if attempt is None else attempt.score,
        test_outcome=None if attempt is None else attempt.outcome,
        fsp_confirmed_count=fsp_count,
    )
    decision = assign_category(view, rule_version())
    session.add(
        StoredCategory(
            profile_id=profile.id,
            category_id=decision.category_id,
            rule_version=decision.rule_version,
            explanation=decision.explanation,
            test_score=decision.test_score,
            rank_key=decision.rank_key,
            scored_at=utc_now(),
            test_attempt_id=None if attempt is None else attempt.id,
        )
    )
    session.flush()


def latest_assignment(session: Session, profile_id: int) -> StoredCategory | None:
    return session.scalar(
        select(StoredCategory)
        .where(
            StoredCategory.profile_id == profile_id,
            StoredCategory.rule_version == rule_version(),
        )
        .order_by(StoredCategory.id.desc())
        .limit(1)
    )


def _require_category(category_id: str) -> str:
    rules = load_rules()
    parts = category_id.split(":")
    if (
        len(parts) != 2
        or parts[0] not in rules["specializations"]
        or parts[1] not in rules["grades"]
        or "/" in category_id
    ):
        raise ApiError(422, "category_id", "Нужна категория из специализации и грейда")
    return category_id


def parse_has_fsp(raw: str | None) -> bool | None:
    if raw is None or raw == "":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ApiError(422, "closed_list", "Признак достижений — true или false")


def _closed(value: str, allowed: list[str], code: str) -> None:
    if value not in allowed:
        raise ApiError(422, code, "Значение не из списка")


def _need(
    *,
    category_id: str,
    stack: list[str],
    team_role: str,
    work_format: str,
    has_fsp: bool | None,
    q: str,
) -> dict:
    return {
        "category_id": category_id,
        "stack": stack,
        "team_role": team_role,
        "work_format": work_format,
        "has_fsp": has_fsp,
        "q": q,
    }


def _profile_matches(
    session: Session,
    profile: Profile,
    assignment: StoredCategory,
    need: dict,
) -> tuple[bool, list[str], list[FspAchievement], str, str]:
    labels = json.loads(profile.stack_json or "[]")
    achievements: list[FspAchievement] = []
    rank = ""
    if profile.external_id:
        rank_row = session.get(FspParticipant, profile.external_id)
        if rank_row is not None:
            rank = rank_row.rank
        achievements = list(
            session.scalars(
                select(FspAchievement).where(FspAchievement.external_id == profile.external_id)
            ).all()
        )
    haystack = haystack_text(
        specialization=profile.specialization,
        grade=profile.grade,
        stack=labels,
        team_role=profile.team_role,
        work_format=profile.work_format,
        experience=profile.experience or "",
    )
    ok = matches_need(
        assigned_category_id=assignment.category_id,
        test_score=assignment.test_score,
        stack=labels,
        team_role=profile.team_role,
        work_format=profile.work_format,
        fsp_count=len(achievements),
        haystack=haystack,
        need=need,
    )
    return ok, labels, achievements, rank, haystack


def visible_in_category(session: Session, profile_id: int, category_id: str) -> bool:
    category_id = _require_category(category_id)
    profile = session.get(Profile, profile_id)
    if profile is None:
        return False
    consent = session.scalar(select(Consent).where(Consent.profile_id == profile.id))
    if consent is None or not consent.publication:
        return False
    assignment = latest_assignment(session, profile.id)
    if assignment is None:
        return False
    ok, _labels, _achievements, _rank, _haystack = _profile_matches(
        session,
        profile,
        assignment,
        _need(
            category_id=category_id,
            stack=[],
            team_role="",
            work_format="",
            has_fsp=None,
            q="",
        ),
    )
    return ok


def employer_candidates(
    session: Session,
    *,
    category_id: str,
    stack: list[str],
    team_role: str,
    work_format: str,
    has_fsp: bool | None,
    q: str,
) -> list[dict]:
    rules = load_rules()
    category_id = _require_category(category_id)
    for item in stack:
        _closed(item, rules["stack"], "closed_list")
    if team_role:
        _closed(team_role, rules["team_roles"], "closed_list")
    if work_format:
        _closed(work_format, rules["work_formats"], "closed_list")
    need = _need(
        category_id=category_id,
        stack=stack,
        team_role=team_role,
        work_format=work_format,
        has_fsp=has_fsp,
        q=q,
    )
    found: list[dict] = []
    profiles = session.scalars(select(Profile)).all()
    for profile in profiles:
        consent = session.scalar(select(Consent).where(Consent.profile_id == profile.id))
        if consent is None or not consent.publication:
            continue
        assignment = latest_assignment(session, profile.id)
        if assignment is None:
            continue
        ok, labels, achievements, rank, haystack = _profile_matches(session, profile, assignment, need)
        if not ok:
            continue
        found.append(
            _card(
                profile,
                assignment,
                labels,
                achievements,
                rank,
                haystack=haystack,
                need=need,
            )
        )
    found.sort(key=lambda item: rank_tuple(item["_need_score"], item["rank_key"]), reverse=True)
    for item in found:
        item.pop("_need_score")
    return found


def _card(
    profile: Profile,
    assignment: StoredCategory,
    labels: list[str],
    achievements: list[FspAchievement],
    rank: str,
    *,
    haystack: str,
    need: dict,
) -> dict:
    fsp_count = len(achievements)
    return {
        "profile_id": profile.id,
        "full_name": profile.full_name,
        "industry": profile.industry,
        "category_id": assignment.category_id,
        "explanation": assignment.explanation,
        "list_reason": list_reason(
            assigned_category_id=assignment.category_id,
            stack=labels,
            team_role=profile.team_role,
            work_format=profile.work_format,
            fsp_count=fsp_count,
            haystack=haystack,
            need=need,
        ),
        "rank_key": assignment.rank_key,
        "_need_score": need_score(
            stack=labels,
            team_role=profile.team_role,
            work_format=profile.work_format,
            fsp_count=fsp_count,
            haystack=haystack,
            need=need,
        ),
        "test_score": assignment.test_score,
        "stack": labels,
        "team_role": profile.team_role,
        "work_format": profile.work_format,
        "experience": profile.experience,
        "fsp_rank": rank,
        "achievements": [
            {
                "discipline": row.discipline,
                "role_in_team": row.role_in_team,
                "place": row.place,
            }
            for row in achievements
        ],
    }
