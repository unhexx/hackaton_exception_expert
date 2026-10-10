"""Кладёт участников мока в базу. Повторный вызов уже занятый ключ не трогает.

ТЗ §4: доступа к реестру ФСП нет — команда работает на собственных тестовых данных.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import FspAchievement, FspParticipant
from product.fsp_mock.client import JsonFspClient


def load_into(session: Session) -> None:
    for person in JsonFspClient().list_participants():
        current = session.get(FspParticipant, person["external_id"])
        if current is None:
            session.add(
                FspParticipant(
                    external_id=person["external_id"],
                    display_name=person["display_name"],
                    rank=person["rank"],
                )
            )
            session.flush()
        for row in person["results"]:
            found = session.scalar(
                select(FspAchievement.id).where(
                    FspAchievement.external_id == person["external_id"],
                    FspAchievement.competition_id == row["competition_id"],
                )
            )
            if found is not None:
                continue
            session.add(
                FspAchievement(
                    external_id=person["external_id"],
                    competition_id=row["competition_id"],
                    competition_name=row["competition_name"],
                    discipline=row["discipline"],
                    role_in_team=row["role_in_team"],
                    place=row["place"],
                    held_on=row["held_on"],
                )
            )
