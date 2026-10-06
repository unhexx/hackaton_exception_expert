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


def need_tokens(query: str) -> list[str]:
    tokens = []
    seen: set[str] = set()
    for raw in str(query or "").split():
        token = raw.strip().casefold()
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


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
    tokens = need_tokens(query)
    if tokens:
        if not all(token in haystack for token in tokens):
            return False
    elif query and query.casefold() not in haystack:
        return False
    return True


def need_score(
    *,
    stack: list[str],
    team_role: str,
    work_format: str,
    fsp_count: int,
    haystack: str,
    need: dict,
) -> int:
    """Степень соответствия потребности внутри уже отфильтрованной категории.

    Пустая потребность даёт 0: сортировка остаётся прежним rank_key.
    """
    points = 0
    stack_filter = [item for item in (need.get("stack") or []) if item]
    if stack_filter:
        points += 10 * len(set(stack_filter) & set(stack))
    if need.get("team_role") and team_role == need["team_role"]:
        points += 8
    if need.get("work_format") and work_format == need["work_format"]:
        points += 6
    has_fsp = need.get("has_fsp")
    if has_fsp is True and fsp_count > 0:
        points += 4
    elif has_fsp is False and fsp_count <= 0:
        points += 4
    tokens = need_tokens(str(need.get("q") or ""))
    if tokens:
        points += 3 * sum(1 for token in tokens if token in haystack)
        points += 5 * sum(1 for item in stack if item.casefold() in tokens)
    return points


def rank_tuple(need_points: int, rank_key: str) -> tuple[int, str]:
    return (need_points, rank_key)


def list_reason(
    *,
    assigned_category_id: str,
    stack: list[str],
    team_role: str,
    work_format: str,
    fsp_count: int,
    haystack: str,
    need: dict,
) -> str:
    """Почему этот человек попал в потребность, а не эхо набора фильтров."""
    parts = [f"Категория {assigned_category_id}"]
    stack_filter = [item for item in (need.get("stack") or []) if item]
    overlap = [item for item in stack if item in set(stack_filter)]
    if overlap:
        parts.append("в профиле стек " + ", ".join(overlap))
    if need.get("team_role") and team_role == need["team_role"]:
        parts.append(f"в профиле роль {team_role}")
    if need.get("work_format") and work_format == need["work_format"]:
        parts.append(f"в профиле формат {work_format}")
    has_fsp = need.get("has_fsp")
    if has_fsp is True and fsp_count > 0:
        parts.append(f"в профиле {fsp_count} достижений ФСП")
    elif has_fsp is False and fsp_count <= 0:
        parts.append("в профиле нет достижений ФСП")
    tokens = need_tokens(str(need.get("q") or ""))
    hit = [token for token in tokens if token in haystack]
    if hit:
        parts.append("в тексте профиля: " + ", ".join(hit))
    if len(parts) == 1:
        parts.append("тест сдан, потребность без уточнений")
    return ". ".join(parts) + "."
