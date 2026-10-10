"""Эталон для сравнения: «единый набор заданий» — то, от чего ТЗ предостерегает.

ТЗ §2: «Единый набор заданий для всех кандидатов не подходит — задания и ответы
быстро разойдутся между участниками рынка». Чтобы показать это на цифрах,
симуляция прогоняет тех же кандидатов через простой тест такого типа:

- 3 вопроса по 3 варианта из каталога ``product.matching.stems``, один верный
  ответ; ключ во всех наборах одинаковый по позициям (b, c, a);
- набор для кандидата выбирается детерминированно (SHA-256 от номера и пары),
  пересдача даёт тот же набор;
- балл 0 / 33 / 67 / 100, пороги: ≥ 50 — грейд подтверждён, ≥ 80 — предложен выше.

Кабинет этим тестом не пользуется: он нужен только как точка отсчёта в отчёте
(ТЗ §6 критерий 2 — сравнение механик в процедуре валидации).

Сложность вопросов эталона не калибровалась. Для честного сравнения им заданы
те же параметры, что у вопросов банка того же уровня: a = 1.0, b = нижняя
граница грейда (+ та же ошибка калибровки), c = 1/3.
"""

from __future__ import annotations

import hashlib
import random
from functools import lru_cache

from product.validation_sim.irt import p_correct
from product.validation_sim.responders import true_params
from product.validation_sim.scale import GRADES, LOWER

LETTERS = ("a", "b", "c")
CONFIRM_MIN = 50
HIGHER_MIN = 80


@lru_cache(maxsize=1)
def question_sets() -> tuple[dict, ...]:
    """Наборы из трёх вопросов каталога. Импорт здесь: пакет переносим и без проекта."""
    from product.matching.stems import catalog

    return catalog()


def profile_number(candidate_id: str) -> int:
    """sim-0042 -> 42: номер кандидата для выбора набора."""
    return int(candidate_id.split("-")[-1])


def pick_set(number: int, specialization: str, grade: str) -> dict:
    found = sorted(
        (row for row in question_sets() if row["specialization"] == specialization and row["grade"] == grade),
        key=lambda row: row["set_id"],
    )
    digest = hashlib.sha256(f"v1|{number}|{specialization}|{grade}".encode()).digest()
    return found[int.from_bytes(digest, "big") % len(found)]


def score_set(grade: str, answers: list[str], qset: dict) -> dict:
    """Балл и итог: ≥ 80 — выше, ≥ 50 — подтверждён, иначе — ниже."""
    correct_n = sum(a == q["correct"] for a, q in zip(answers, qset["questions"]))
    score = round(100 * correct_n / len(qset["questions"]))
    index = GRADES.index(grade)
    if score >= HIGHER_MIN:
        outcome = "confirm" if index == len(GRADES) - 1 else "suggest_higher"
        proposed = GRADES[min(index + 1, len(GRADES) - 1)]
    elif score >= CONFIRM_MIN:
        outcome, proposed = "confirm", grade
    else:
        outcome, proposed = "suggest_lower", GRADES[max(index - 1, 0)]
    return {"score": score, "outcome": outcome, "proposed_grade": proposed}


class BaselineSystem:
    """Единый набор заданий: тот же интерфейс ``take``, что у ``simulate.NewSystem``."""

    name = "Единый набор (3 вопроса, общий ключ)"

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    @staticmethod
    def set_ids() -> list[str]:
        return [row["set_id"] for row in question_sets()]

    def qset(self, candidate: dict, grade: str) -> dict:
        return pick_set(profile_number(candidate["candidate_id"]), candidate["specialization"], grade)

    def _answer(self, question: dict, index: int, qset: dict, strategy: str, theta: float,
                leaked: set[str]) -> str:
        correct = question["correct"]
        if strategy == "leaked" and qset["set_id"] in leaked:
            return correct
        if strategy in ("honest", "leaked"):
            a, b = true_params(f"{qset['set_id']}/{question['id']}", 1.0, LOWER[qset["grade"]])
            if self.rng.random() < p_correct(theta, a, b, 1 / 3):
                return correct
            return self.rng.choice([x for x in LETTERS if x != correct])
        if strategy == "random":
            return self.rng.choice(LETTERS)
        if strategy == "always_b":
            return "b"
        if strategy == "pattern_bca":
            return "bca"[index % 3]
        if strategy == "longest":
            return max(question["choices"], key=lambda c: len(c["text"]))["id"]
        raise ValueError(strategy)

    def take(self, candidate: dict, grade: str, strategy: str = "honest",
             theta: float | None = None, leaked: set[str] | None = None) -> dict:
        qset = self.qset(candidate, grade)
        theta = candidate["theta"] if theta is None else theta
        answers = [
            self._answer(q, i, qset, strategy, theta, leaked or set())
            for i, q in enumerate(qset["questions"])
        ]
        result = score_set(grade, answers, qset)
        outcome = result["outcome"]
        proposed = result["proposed_grade"]
        if outcome == "suggest_lower" and grade == GRADES[0]:
            proposed = None  # ниже junior некуда: грейд не подтверждён
        return {
            "outcome": outcome,
            "proposed_grade": proposed,
            "percent": result["score"],
            "theta": None,
            "items": [(f"{qset['set_id']}/{q['id']}", a == q["correct"])
                      for q, a in zip(qset["questions"], answers)],
        }
