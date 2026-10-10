"""Поведение синтетических кандидатов при ответе на вопрос.

Каждая стратегия — функция ``(item, key, rng) -> ответ`` для нового теста.
``key`` нужен только «честному» кандидату и сценарию утечки: симуляция
решает, ответил ли он верно, и тогда возвращает верный ответ. Остальные
стратегии ключ не видят — как и настоящий кандидат.

Стратегии (ТЗ, критерий 2: «устойчивость механики к распространению заданий»):

    honest       честный ответ по уровню θ (модель IRT)
    random       наугад
    always_b     всегда второй вариант («всегда b»)
    pattern_bca  выученный общий ключ эталона: b, c, a, b, c, a…
    longest      самый длинный вариант ответа (типичная уловка на тестах)
    leaked       знает ответы на «утёкшие» варианты, остальное — честно
"""

from __future__ import annotations

import hashlib
import random
from typing import Callable

from product.validation_sim.irt import p_correct

Responder = Callable[[dict, object, random.Random], object]

# Ошибка калибровки: «настоящая» сложность варианта отличается от записанной
# в банке. Без этого симуляция была бы слишком оптимистичной.
CALIBRATION_SD_B = 0.15
CALIBRATION_SD_A = 0.10


def true_params(item_id: str, a: float, b: float) -> tuple[float, float]:
    """Стабильный (по id) сдвиг параметров: один и тот же для всех кандидатов."""
    digest = hashlib.sha256(item_id.encode()).digest()
    local = random.Random(int.from_bytes(digest[:8], "big"))
    return max(0.4, a + local.gauss(0, CALIBRATION_SD_A)), b + local.gauss(0, CALIBRATION_SD_B)


def _judge_sets(item: dict) -> list[frozenset]:
    """Все 8 разметок «верно / неверно» для трёх вариантов (judge)."""
    ids = [o["id"] for o in item["options"]]
    return [frozenset(i for k, i in enumerate(ids) if mask >> k & 1) for mask in range(2 ** len(ids))]


def _wrong(item: dict, key: object, rng: random.Random) -> object:
    if item["type"] == "judge":
        return rng.choice([s for s in _judge_sets(item) if s != frozenset({key})])
    if "options" in item:
        return rng.choice([o["id"] for o in item["options"] if o["id"] != key])
    choices = [i for i in range(item["space"]) if i != key]
    return rng.choice(choices)


def _random(item: dict, rng: random.Random) -> object:
    if item["type"] == "judge":
        return rng.choice(_judge_sets(item))
    if "options" in item:
        return rng.choice(item["options"])["id"]
    return rng.randrange(item["space"])


def _by_position(item: dict, position: int) -> object:
    """Ответ «по позиции»: для single — вариант на этом месте, иначе номер."""
    if "options" in item:
        chosen = item["options"][position % len(item["options"])]["id"]
        return frozenset({chosen}) if item["type"] == "judge" else chosen
    return position % item["space"]


def honest(theta: float) -> Responder:
    def answer(item: dict, key: object, rng: random.Random) -> object:
        a, b = true_params(item["item_id"], item["a"], item["b"])
        if rng.random() < p_correct(theta, a, b, item["c"]):
            return frozenset({key}) if item["type"] == "judge" else key
        return _wrong(item, key, rng)

    return answer


def random_guess() -> Responder:
    return lambda item, key, rng: _random(item, rng)


def always_b() -> Responder:
    return lambda item, key, rng: _by_position(item, 1)


def pattern_bca() -> Responder:
    counter = {"n": 0}

    def answer(item: dict, key: object, rng: random.Random) -> object:
        position = (1, 2, 0)[counter["n"] % 3]  # b, c, a
        counter["n"] += 1
        return _by_position(item, position)

    return answer


def longest() -> Responder:
    def answer(item: dict, key: object, rng: random.Random) -> object:
        if "options" in item:
            chosen = max(item["options"], key=lambda o: len(o["text"]))["id"]
            return frozenset({chosen}) if item["type"] == "judge" else chosen
        return _random(item, rng)  # у multi/order/numeric «длинного варианта» нет

    return answer


def leaked(theta: float, leaked_ids: set[str]) -> Responder:
    base = honest(theta)

    def answer(item: dict, key: object, rng: random.Random) -> object:
        if item["item_id"] in leaked_ids:
            return frozenset({key}) if item["type"] == "judge" else key
        return base(item, key, rng)

    return answer
