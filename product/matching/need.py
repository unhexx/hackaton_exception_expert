"""Общий предикат выдачи. Им пользуются золотой прогон и живая подборка."""

from __future__ import annotations


def haystack_text(
    *,
    specialization: str,
    grade: str,
    stack: list[str],
    team_role: str,
    work_format: str,
    experience: str,
) -> str:
    return " ".join(
        [
            specialization,
            grade,
            " ".join(stack),
            team_role,
            work_format,
            experience or "",
        ]
    ).casefold()


def matches_need(
    *,
    assigned_category_id: str,
    test_score: int | None,
    stack: list[str],
    team_role: str,
    work_format: str,
    fsp_count: int,
    haystack: str,
    need: dict,
) -> bool:
    if assigned_category_id != need["category_id"]:
        return False
    if test_score is None:
        return False
    stack_filter = [item for item in (need.get("stack") or []) if item]
    if stack_filter and not set(stack_filter) & set(stack):
        return False
    if need.get("team_role") and team_role != need["team_role"]:
        return False
    if need.get("work_format") and work_format != need["work_format"]:
        return False
    has_fsp = need.get("has_fsp")
    if has_fsp is True and fsp_count <= 0:
        return False
    if has_fsp is False and fsp_count > 0:
        return False
    query = str(need.get("q") or "").strip()
    if query and query.casefold() not in haystack:
        return False
    return True
