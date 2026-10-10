"""Категория v1: специализация и записанный грейд. Балл только ранжирует.

`category_id` не содержит отрасль и не содержит балл; `rank_key`
лексикографически кодирует confirmed-score-count-prize-id.

ТЗ §2 «Категория… связка специализации и грейда; внутри категории выше те, у кого сильнее подтверждённый профиль и есть опыт ФСП»; Q&A: грейд только по тесту, ФСП — ранжирование.
"""

from __future__ import annotations

from product.matching.rules import load_rules
from product.matching.types import CategoryAssignment, CategoryError, ProfileView

_OUTCOME = {
    "confirm": "заявленный грейд подтверждён",
    "suggest_lower": "предложен грейд ниже",
    "suggest_higher": "предложен грейд выше",
}

PRIZE_PLACES = frozenset({"1", "2", "3"})


def has_prize_place(places: list[str] | tuple[str, ...]) -> bool:
    return any(str(place) in PRIZE_PLACES for place in places)


def rank_key(
    test_score: int,
    fsp_confirmed_count: int,
    profile_id: int,
    *,
    confirmed: bool,
    has_prize: bool,
) -> str:
    """Порядок полей фиксирован, чтобы сортировка выдачи совпала у прогона и кабинета.

    Балл сюда входит, в `category_id` — нет.
    """
    return (
        f"{int(confirmed)}-{test_score:03d}-"
        f"{fsp_confirmed_count:04d}-{int(has_prize)}-{profile_id:08d}"
    )


def assign_category(profile: ProfileView, rule_version: str) -> CategoryAssignment:
    """Назначение читает опрос и итог теста; отсутствие сдачи оставляет `test_score` пустым, но категорию всё равно пишет.

    Чужой `rule_version` — ошибка, не тихое v1.
    """
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
        rank_key=rank_key(
            points,
            profile.fsp_confirmed_count,
            profile.profile_id,
            # Q&A: неподтверждённый грейд показываем, но ниже подтверждённых.
            # Подтверждён — тест сдан с итогом confirm или suggest_higher; провал
            # (suggest_lower) грейд не понижает (ТЗ §2), но и не подтверждает.
            confirmed=profile.test_outcome in ("confirm", "suggest_higher"),
            has_prize=profile.fsp_has_prize,
        ),
    )
