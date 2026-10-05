"""Анкета соискателя и пустой слот достижений."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from sqlalchemy import select

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import Profile, User
from product.app.services.profiles import get_own_profile, profile_payload, save_profile
from product.fsp_mock.read import achievements_for

router = APIRouter(tags=["candidate"])

_PROFILE = {
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "specialization": "backend",
    "grade": "middle",
    "stack": ["python"],
    "team_role": "разработчик",
    "work_format": "удалённо",
    "experience": "3 года",
    "soft_skills": ["коммуникация"],
    "external_id": "",
    "publication": True,
}
_NOT_FOUND = {"error": "not_found", "message": "Анкета ещё не заполнена"}
_CLOSED = {"error": "closed_list", "message": "Значение не из списка"}


@router.get(
    "/candidate/profile",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "profile_id": 1,
                        "full_name": "Иван Синтетиков",
                        "email": "seeker@example.com",
                        "industry": "it",
                        "specialization": "backend",
                        "grade": "middle",
                        "category_id": None,
                        "publication": True,
                    }
                }
            }
        },
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
        404: {"content": {"application/json": {"example": _NOT_FOUND}}},
    },
)
def read_profile(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    profile = get_own_profile(db, user)
    return profile_payload(db, user, profile)


@router.put(
    "/candidate/profile",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "profile_id": 1,
                        "industry": "it",
                        "category_id": None,
                        "grade": "middle",
                        "specialization": "backend",
                    }
                }
            }
        },
        409: {"content": {"application/json": {"example": {"error": "grade_via_test", "message": "Грейд меняет только тест"}}}},
        422: {"content": {"application/json": {"example": _CLOSED}}},
    },
)
def write_profile(
    payload: dict = Body(..., examples={"survey": {"value": _PROFILE}}),
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    return save_profile(db, user, payload)


@router.get(
    "/candidate/achievements",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {"display_name": "", "rank": "", "results": []}
                }
            }
        },
        401: {"content": {"application/json": {"example": {"error": "unauthorized", "message": "Нужен вход"}}}},
        403: {"content": {"application/json": {"example": {"error": "forbidden", "message": "Это кабинет соискателя"}}}},
    },
)
def read_achievements(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    external_id = db.scalar(select(Profile.external_id).where(Profile.user_id == user.id))
    return achievements_for(external_id)
