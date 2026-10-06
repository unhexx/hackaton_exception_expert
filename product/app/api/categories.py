"""Категория соискателя и выдача работодателя."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate, require_employer
from product.app.db.models import User
from product.app.services.categories import employer_candidates, latest_assignment, parse_has_fsp
from product.app.services.errors import ApiError, example, explain
from product.app.services.profiles import get_own_profile

router = APIRouter(tags=["category"])

_CATEGORY = {
    "profile_id": 1,
    "category_id": "backend:middle",
    "rule_version": "v1",
    "explanation": "Опрос: специализация backend, грейд middle. Тест ещё не сдан. Правила v1.",
    "test_score": None,
    "industry": "it",
}
_MISSING = example("category_id")
_CARD = {
    "profile_id": 1,
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "category_id": "backend:middle",
    "explanation": _CATEGORY["explanation"],
    "list_reason": "Категория backend:middle.",
    "rank_key": "067-0000-00000001",
    "test_score": 67,
    "stack": ["python"],
    "team_role": "разработчик",
    "work_format": "удалённо",
}


@router.get(
    "/candidate/category",
    responses={
        200: {"content": {"application/json": {"example": _CATEGORY}}},
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        403: {"content": {"application/json": {"example": example("forbidden", "forbidden_candidate")}}},
        404: {"content": {"application/json": {"example": example("not_found", "not_found_category")}}},
    },
)
def read_category(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    profile = get_own_profile(db, user)
    row = latest_assignment(db, profile.id)
    if row is None:
        raise ApiError(404, "not_found", explain("not_found_category"))
    return {
        "profile_id": profile.id,
        "category_id": row.category_id,
        "rule_version": row.rule_version,
        "explanation": row.explanation,
        "test_score": row.test_score,
        "rank_key": row.rank_key,
        "industry": profile.industry,
    }


@router.get(
    "/employer/candidates",
    responses={
        200: {"content": {"application/json": {"example": [_CARD]}}},
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
        403: {"content": {"application/json": {"example": example("forbidden", "forbidden_employer")}}},
        422: {"content": {"application/json": {"example": _MISSING}}},
    },
)
def read_candidates(
    category_id: str | None = Query(default=None),
    stack: list[str] = Query(default=[]),
    team_role: str = Query(default=""),
    work_format: str = Query(default=""),
    has_fsp: str | None = Query(default=None),
    q: str = Query(default=""),
    _user: User = Depends(require_employer),
    db: Session = Depends(db_session),
):
    if not category_id:
        raise ApiError(422, "category_id", explain("category_id"))
    return employer_candidates(
        db,
        category_id=category_id,
        stack=stack,
        team_role=team_role,
        work_format=work_format,
        has_fsp=parse_has_fsp(has_fsp),
        q=q,
    )
