"""Вход и выход категории. Резюме и дисциплина сюда не входят."""

from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class Need:
    category_id: str
    stack: tuple[str, ...] = ()
    team_role: str = ""
    work_format: str = ""
    has_fsp: bool | None = None
    q: str = ""

    @classmethod
    def from_mapping(cls, raw: dict) -> Need:
        has = raw.get("has_fsp")
        if has is not True and has is not False:
            has = None
        return cls(
            category_id=str(raw.get("category_id") or ""),
            stack=tuple(item for item in (raw.get("stack") or []) if item),
            team_role=str(raw.get("team_role") or ""),
            work_format=str(raw.get("work_format") or ""),
            has_fsp=has,
            q=str(raw.get("q") or ""),
        )


@dataclass(frozen=True)
class NeedFit:
    """Один проход: фильтр, порядок внутри категории и фраза для карточки.

    sort_key: совпадения стека, роли, формата, признака ФСП, токенов, затем rank_key.
    Большее значение выше при сортировке reverse=True. Баллов нет.
    """

    matched: bool
    sort_key: tuple[int, int, int, int, int, str]
    reason: str
