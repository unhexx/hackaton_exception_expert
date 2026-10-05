"""Пустая история достижений, пока мок не наполнен."""

from __future__ import annotations


def achievements_for(external_id: str | None) -> dict:
    return {"display_name": "", "rank": "", "results": []}
