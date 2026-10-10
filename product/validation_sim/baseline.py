"""Модель ТЕКУЩЕГО теста проекта — для сравнения «было / стало».

Используется настоящий код проекта ``product.matching.grade``:
выбор шаблона ``select_template`` (по номеру профиля), подсчёт балла и решение
``score_attempt`` (пороги 50 и 80). Ничего не переписано — только вызвано.

Особенности текущего теста, которые и проверяет сравнение:
- 3 вопроса по 3 варианта, ключ во всех 72 шаблонах одинаковый: b, c, a;
- шаблон для профиля всегда один и тот же, пересдача — тот же шаблон;
- возможные баллы только 0, 33, 67, 100.

Сложность старых вопросов не калибровалась. Для честного сравнения им заданы
те же параметры, что у новых вопросов того же уровня: a = 1.0, b = нижняя
граница грейда (+ та же ошибка калибровки), c = 1/3.

ТЗ §6 критерий 2: сравнение механик в процедуре валидации.
"""

from __future__ import annotations

import random

from product.validation_sim.irt import p_correct
from product.validation_sim.responders import true_params
from product.validation_sim.scale import LOWER

LETTERS = ("a", "b", "c")


def _grade_module():
    # Импорт здесь: остальной пакет переносим и без кода проекта.
    from product.matching import grade

    return grade


def profile_number(candidate_id: str) -> int:
    """sim-0042 -> 42: номер профиля для select_template."""
    return int(candidate_id.split("-")[-1])


class OldSystem:
    """Текущая механика: тот же интерфейс ``take``, что у новой (``simulate.NewSystem``)."""

    name = "Текущий тест (3 вопроса, ключ b-c-a)"

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.grade = _grade_module()

    def template(self, candidate: dict, grade: str) -> dict:
        template_id = self.grade.select_template(
            profile_number(candidate["candidate_id"]), candidate["specialization"], grade, "v1"
        )
        return self.grade.load_template(template_id)

    def _answer(self, question: dict, index: int, template: dict, strategy: str, theta: float,
                leaked: set[str]) -> str:
        correct = question["correct"]
        if strategy == "leaked" and template["template_id"] in leaked:
            return correct
        if strategy in ("honest", "leaked"):
            a, b = true_params(f"{template['template_id']}/{question['id']}", 1.0, LOWER[template["grade"]])
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
        template = self.template(candidate, grade)
        theta = candidate["theta"] if theta is None else theta
        answers = [
            self._answer(q, i, template, strategy, theta, leaked or set())
            for i, q in enumerate(template["questions"])
        ]
        result = self.grade.score_attempt(template, answers)
        outcome = result["outcome"]
        proposed = result["proposed_grade"]
        if outcome == "suggest_lower" and grade == "junior":
            proposed = None  # ниже junior некуда: грейд не подтверждён
        return {
            "outcome": outcome,
            "proposed_grade": proposed,
            "percent": result["score"],
            "theta": None,
            "items": [(f"{template['template_id']}/{q['id']}", a == q["correct"])
                      for q, a in zip(template["questions"], answers)],
        }
