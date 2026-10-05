"""Вход и выход категории. Резюме и дисциплина сюда не входят."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class CategoryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProfileView:
    profile_id: int
    specialization: str
    grade: str
    test_score: int | None
    test_outcome: str | None
    fsp_confirmed_count: int


@dataclass(frozen=True)
class CategoryAssignment:
    profile_id: int
    category_id: str
    rule_version: str
    explanation: str
    test_score: int | None
    rank_key: str
    scored_at: datetime | None
