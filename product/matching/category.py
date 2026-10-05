"""Категория v1: специализация и записанный грейд. Балл только ранжирует."""

from __future__ import annotations

from product.matching.rules import load_rules
from product.matching.types import CategoryAssignment, CategoryError, ProfileView

_OUTCOME = {
    "confirm": "заявленный грейд подтверждён",
    "suggest_lower": "предложен грейд ниже",
    "suggest_higher": "предложен грейд выше",
}


def rank_key(test_score: int, fsp_confirmed_count: int, profile_id: int) -> str:
    return f"{test_score:03d}-{fsp_confirmed_count:04d}-{profile_id:08d}"


def assign_category(profile: ProfileView, rule_version: str) -> CategoryAssignment:
    current = str(load_rules()["rule_version"])
    if rule_version != current:
        raise CategoryError("rule_version")
    if profile.test_score is not None and profile.test_outcome not in _OUTCOME:
        raise CategoryError("test_outcome")
    category_id = f"{profile.specialization}:{profile.grade}"
    points = 0 if profile.test_score is None else profile.test_score
    if profile.test_score is None:
        explanation = (
            f"Опрос: специализация {profile.specialization}, грейд {profile.grade}. "
            f"Тест ещё не сдан. Правила {rule_version}."
        )
        stored_score = None
    else:
        explanation = (
            f"Опрос: специализация {profile.specialization}, грейд {profile.grade}. "
            f"Тест: {_OUTCOME[profile.test_outcome]}, балл {profile.test_score}. "
            f"Правила {rule_version}."
        )
        stored_score = profile.test_score
    return CategoryAssignment(
        profile_id=profile.profile_id,
        category_id=category_id,
        rule_version=rule_version,
        explanation=explanation,
        test_score=stored_score,
        rank_key=rank_key(points, profile.fsp_confirmed_count, profile.profile_id),
        scored_at=None,
    )
