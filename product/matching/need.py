"""Общий разбор потребности. Им пользуются золотой прогон и живая подборка."""

from __future__ import annotations

from product.matching.types import Need, NeedFit


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


def _needles(query: str) -> list[str]:
    tokens = need_tokens(query)
    if tokens:
        return tokens
    folded = str(query or "").strip().casefold()
    return [folded] if folded else []


def _as_need(need: Need | dict) -> Need:
    if isinstance(need, Need):
        return need
    return Need.from_mapping(need)


def evaluate_need(
    *,
    assigned_category_id: str,
    test_score: int | None,
    stack: list[str],
    team_role: str,
    work_format: str,
    fsp_count: int,
    haystack: str,
    need: Need | dict,
    rank_key: str = "",
) -> NeedFit:
    """Фильтр, порядок внутри категории и фраза «почему этот человек» — один проход."""
    spec = _as_need(need)
    empty = (0, 0, 0, 0, 0, rank_key)
    if assigned_category_id != spec.category_id:
        return NeedFit(False, empty, "")
    overlap = [item for item in stack if item in set(spec.stack)]
    if spec.stack and not overlap:
        return NeedFit(False, empty, "")
    if spec.team_role and team_role != spec.team_role:
        return NeedFit(False, empty, "")
    if spec.work_format and work_format != spec.work_format:
        return NeedFit(False, empty, "")
    if spec.has_fsp is True and fsp_count <= 0:
        return NeedFit(False, empty, "")
    if spec.has_fsp is False and fsp_count > 0:
        return NeedFit(False, empty, "")
    needles = _needles(spec.q)
    hit = [token for token in needles if token in haystack]
    if needles and len(hit) != len(needles):
        return NeedFit(False, empty, "")
    role_hit = 1 if spec.team_role and team_role == spec.team_role else 0
    format_hit = 1 if spec.work_format and work_format == spec.work_format else 0
    fsp_hit = 0
    if spec.has_fsp is True and fsp_count > 0:
        fsp_hit = 1
    elif spec.has_fsp is False and fsp_count <= 0:
        fsp_hit = 1
    parts = [f"Категория {assigned_category_id}"]
    if overlap:
        parts.append("в профиле стек " + ", ".join(overlap))
    if role_hit:
        parts.append(f"в профиле роль {team_role}")
    if format_hit:
        parts.append(f"в профиле формат {work_format}")
    if spec.has_fsp is True and fsp_count > 0:
        parts.append(f"в профиле {fsp_count} достижений ФСП")
    elif spec.has_fsp is False and fsp_count <= 0:
        parts.append("в профиле нет достижений ФСП")
    if hit:
        parts.append("в тексте профиля: " + ", ".join(hit))
    if len(parts) == 1:
        if test_score is None:
            parts.append("Грейд не подтверждён, потребность без уточнений")
        else:
            parts.append("Тест сдан, потребность без уточнений")
    return NeedFit(
        True,
        (len(overlap), role_hit, format_hit, fsp_hit, len(hit), rank_key),
        ". ".join(parts) + ".",
    )


def matches_need(
    *,
    assigned_category_id: str,
    test_score: int | None,
    stack: list[str],
    team_role: str,
    work_format: str,
    fsp_count: int,
    haystack: str,
    need: Need | dict,
) -> bool:
    return evaluate_need(
        assigned_category_id=assigned_category_id,
        test_score=test_score,
        stack=stack,
        team_role=team_role,
        work_format=work_format,
        fsp_count=fsp_count,
        haystack=haystack,
        need=need,
    ).matched
