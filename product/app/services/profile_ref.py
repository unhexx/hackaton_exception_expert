"""Почта соискателя и номер своего профиля.

Приглашение и вакансия читают одно и то же. События журнала здесь не пишутся.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import Profile, User


def candidate_email(db: Session, profile_id: int) -> str:
    profile = db.get(Profile, profile_id)
    if profile is None:
        return ""
    owner = db.get(User, profile.user_id)
    return "" if owner is None else owner.email


def own_profile_id(db: Session, user: User) -> int | None:
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    return None if profile is None else profile.id
