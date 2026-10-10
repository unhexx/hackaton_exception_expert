"""Шкала уровня кандидата и границы грейдов.

Уровень кандидата («theta», θ) — одно число на общей шкале для всех
специализаций. Грейд — интервал на этой шкале. Так тест любого варианта
переводится в один и тот же грейд: варианты разные, шкала общая
(ТЗ §2: «сопоставимая сложность и объективность оценки между кандидатами»).

Числа условные, но согласованы между собой:

    junior  [-1.8; -0.6)
    middle  [-0.6;  0.6)
    senior  [ 0.6;  1.8)
    lead    [ 1.8;  3.0]

Ниже -1.8 — «грейд не подтверждён» (минимальный порог входа).
"""

from __future__ import annotations

GRADES: tuple[str, ...] = ("junior", "middle", "senior", "lead")

# Нижняя граница каждого грейда на шкале θ. Вопрос «уровня g» калибруется так,
# что кандидат ровно на нижней границе g решает его с вероятностью ~50% (без учёта
# угадывания). Это и делает вопрос «пограничным» для решения о грейде g.
LOWER: dict[str, float] = {"junior": -1.8, "middle": -0.6, "senior": 0.6, "lead": 1.8}
TOP: float = 3.0  # верхняя граница шкалы для генерации кандидатов lead


def band(grade: str) -> tuple[float, float]:
    """Интервал θ, который соответствует грейду: [нижняя граница; следующая граница)."""
    index = GRADES.index(grade)
    upper = LOWER[GRADES[index + 1]] if index + 1 < len(GRADES) else TOP
    return LOWER[grade], upper


def grade_of(theta: float) -> str | None:
    """Истинный грейд по уровню θ. None — ниже порога junior."""
    found = None
    for grade in GRADES:
        if theta >= LOWER[grade]:
            found = grade
    return found


def next_grade(grade: str) -> str | None:
    index = GRADES.index(grade)
    return GRADES[index + 1] if index + 1 < len(GRADES) else None


def prev_grade(grade: str) -> str | None:
    index = GRADES.index(grade)
    return GRADES[index - 1] if index > 0 else None


def grade_index(grade: str | None) -> int:
    """Номер грейда для сравнений; «не подтверждён» = -1."""
    return -1 if grade is None else GRADES.index(grade)
