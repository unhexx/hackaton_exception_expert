"""Достижения из тех же таблиц, что и пересчёт категории."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import FspAchievement, FspParticipant

_EMPTY = {"display_name": "", "rank": "", "results": []}


def achievements_for(session: Session, external_id: str | None) -> dict:
    if external_id is None or not str(external_id).strip():
        return dict(_EMPTY)
    person = session.get(FspParticipant, str(external_id).strip())
    if person is None:
        return dict(_EMPTY)
    rows = session.scalars(
        select(FspAchievement)
        .where(FspAchievement.external_id == person.external_id)
        .order_by(FspAchievement.id)
    ).all()
    return {
        "display_name": person.display_name,
        "rank": person.rank,
        "results": [
            {
                "competition_id": row.competition_id,
                "competition_name": row.competition_name,
                "discipline": row.discipline,
                "role_in_team": row.role_in_team,
                "place": row.place,
                "held_on": row.held_on,
            }
            for row in rows
        ],
    }
