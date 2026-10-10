"""Испытание грейда. Каталог собирается из стемов, на проходе не переписывается.

ТЗ §2 «Единый набор заданий для всех не подходит». Это ПРЕЖНЯЯ механика (3 вопроса, ключ b-c-a): в кабинете не используется, оставлена для сравнения в product/validation_sim (baseline). Действующая механика — product/matching/assessment.py.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from product.matching.rules import load_rules
from product.matching.stems import catalog


class GradeError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@lru_cache(maxsize=1)
def _catalog() -> tuple[dict, ...]:
    return catalog()


def load_template(template_id: str) -> dict:
    for row in _catalog():
        if row.get("template_id") == template_id:
            return row
    raise GradeError("template_missing")


def templates_for(specialization: str, grade: str, rule_version: str) -> list[dict]:
    found = [
        row
        for row in _catalog()
        if row.get("specialization") == specialization
        and row.get("grade") == grade
        and row.get("rule_version") == rule_version
    ]
    found.sort(key=lambda row: str(row["template_id"]))
    return found


def select_template(profile_id: int, specialization: str, grade: str, rule_version: str) -> str:
    found = templates_for(specialization, grade, rule_version)
    if len(found) < 2 or len(found) > 3:
        raise GradeError("template_pair")
    digest = hashlib.sha256(f"{rule_version}|{profile_id}|{specialization}|{grade}".encode()).digest()
    index = int.from_bytes(digest, "big") % len(found)
    return str(found[index]["template_id"])


def _grades() -> list[str]:
    return list(load_rules()["grades"])


def is_adjacent_grade(current: str, requested: str) -> bool:
    grades = _grades()
    if current not in grades or requested not in grades:
        return False
    return abs(grades.index(current) - grades.index(requested)) == 1


def is_lower_grade(current: str, requested: str) -> bool:
    grades = _grades()
    if current not in grades or requested not in grades:
        return False
    return grades.index(requested) < grades.index(current)


def propose(score: int, grade: str, template: dict) -> tuple[str, str]:
    grades = _grades()
    index = grades.index(grade)
    confirm_min = int(template["confirm_min"])
    higher_min = int(template["suggest_higher_min"])
    if score >= higher_min:
        if index == len(grades) - 1:
            return "confirm", grade
        return "suggest_higher", grades[index + 1]
    if score >= confirm_min:
        return "confirm", grade
    if index == 0:
        return "suggest_lower", grades[0]
    return "suggest_lower", grades[index - 1]


def score_attempt(template: dict, answers: list) -> dict:
    questions = template["questions"]
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise GradeError("answer_unknown")
    correct_n = 0
    for question, answer in zip(questions, answers):
        if not isinstance(answer, str):
            raise GradeError("answer_unknown")
        choice_ids = {str(choice["id"]) for choice in question["choices"]}
        if answer not in choice_ids:
            raise GradeError("answer_unknown")
        if answer == question["correct"]:
            correct_n += 1
    score = round(100 * correct_n / len(questions))
    outcome, proposed = propose(score, str(template["grade"]), template)
    return {"score": score, "outcome": outcome, "proposed_grade": proposed}


def public_questions(template: dict) -> list[dict]:
    visible = []
    for question in template["questions"]:
        visible.append(
            {
                "id": question["id"],
                "text": question["text"],
                "choices": [
                    {"id": choice["id"], "text": choice["text"]} for choice in question["choices"]
                ],
            }
        )
    return visible
