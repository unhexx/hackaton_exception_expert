"""Клиент мока. Читает JSON из репозитория, реестр по HTTP не вызывается.

ТЗ §3.4 «схема предполагаемой интеграции с реестром ФСП»: интерфейс клиента, сейчас — JSON-мок.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from product.fsp_mock.adapter import adapt_participant

_DATA = Path(__file__).resolve().parent / "participants.json"


class FspClient(Protocol):
    def get_participant(self, external_id: str) -> dict | None: ...


class JsonFspClient:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DATA

    def _rows(self) -> list[dict]:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        rows = payload.get("participants", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def list_participants(self) -> list[dict]:
        return [adapt_participant(row) for row in self._rows()]

    def get_participant(self, external_id: str) -> dict | None:
        key = external_id.strip()
        if not key:
            return None
        for person in self.list_participants():
            if person["external_id"] == key:
                return person
        return None
