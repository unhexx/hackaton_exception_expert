"""Оценка ответов и решение по грейду (ТЗ §2: «по результату теста грейд не
понижается принудительно… кандидат, справившийся уверенно, — повысить грейд»).

Решение принимается по уровню θ, а не по проценту: см. ``irt``. Правило:

    θ ≥ нижней границы следующего грейда  → suggest_higher (предложить тест выше)
    θ ≥ нижней границы заявленного грейда  → confirm (грейд подтверждён)
    иначе                                  → suggest_lower (предложить тест ниже;
                                             по ТЗ грейд не понижается сам)

Процент верных ответов возвращается для интерфейса кабинета, но на решение
не влияет: на разных вариантах он несравним.
"""

from __future__ import annotations

from product.validation_sim.irt import estimate_theta
from product.validation_sim.scale import LOWER, next_grade, prev_grade


def is_correct(item: dict, answer: object, key: object) -> bool:
    """Верен ли ответ на один вопрос.

    single / multi / order / numeric — ответ совпадает с ключом попытки;
    judge — набор вариантов, отмеченных «верно», равен ровно {верный вариант}:
    каждый из трёх вариантов оценён правильно.
    """
    if item["type"] == "judge":
        if answer is None or isinstance(answer, str):
            return False
        return set(answer) == {key}
    return answer == key


def check_answers(form: dict, answers: dict[str, object]) -> list[bool]:
    """Сверка с серверным ключом попытки, в порядке ``form['items']``."""
    key = form["key"]
    return [is_correct(item, answers.get(item["item_id"]), key[item["item_id"]]) for item in form["items"]]


def decide(theta: float, grade: str) -> tuple[str, str | None]:
    """Итог попытки и предлагаемый грейд (None — ниже junior, «не подтверждён»)."""
    upper = next_grade(grade)
    if upper is not None and theta >= LOWER[upper]:
        return "suggest_higher", upper
    if theta >= LOWER[grade]:
        return "confirm", grade
    return "suggest_lower", prev_grade(grade)


def score_form(form: dict, answers: dict[str, object]) -> dict:
    """Полный итог попытки: θ, его погрешность, процент, решение."""
    correct = check_answers(form, answers)
    responses = [
        (item["a"], item["b"], item["c"], ok) for item, ok in zip(form["items"], correct)
    ]
    theta, se = estimate_theta(responses)
    outcome, proposed = decide(theta, form["grade"])
    return {
        "theta": round(theta, 3),
        "se": round(se, 3),
        "percent": round(100 * sum(correct) / len(correct)),
        "outcome": outcome,
        "proposed_grade": proposed,
        "correct": correct,
    }
