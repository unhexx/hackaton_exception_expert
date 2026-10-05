"""Карточка достижений по external_id. Чужой и пустой id — пустая история."""

from __future__ import annotations

from product.fsp_mock.client import JsonFspClient


def achievements_for(external_id: str | None) -> dict:
    if external_id is None or not str(external_id).strip():
        return {"display_name": "", "rank": "", "results": []}
    person = JsonFspClient().get_participant(str(external_id))
    if person is None:
        return {"display_name": "", "rank": "", "results": []}
    return {
        "display_name": person["display_name"],
        "rank": person["rank"],
        "results": list(person["results"]),
    }
