"""Общий разбор вилки зарплаты.

Журнал пишет сервис через reject: приглашение — offer_rejected,
вакансия — vacancy_rejected. Этот модуль событие не выбирает.

ТЗ §2.2 п.1: «уровень заработной платы указывается обязательно… диапазон от–до, в рублях».
"""

from __future__ import annotations

from collections.abc import Callable

from product.app.db.session import sqlite_int


def parse_fork(low: object, high: object, reject: Callable[..., None]) -> tuple[int, int]:
    """Две целые границы в диапазоне INTEGER. Верхняя строго больше нижней."""
    salary_min = _bound(low, reject)
    salary_max = _bound(high, reject)
    if salary_max <= salary_min:
        reject(422, "salary_range")
    return salary_min, salary_max


def _bound(value: object, reject: Callable[..., None]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        reject(422, "salary_range", "salary_range_type")
    if sqlite_int(value) is None:
        reject(422, "salary_range")
    return value
