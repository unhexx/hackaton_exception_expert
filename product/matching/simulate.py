"""CPU-персоны для прогона жюри. Три правила без GPU и без сети.

Множество — все шаблоны catalog(). Печатаются competent, key_leak и adjacent.
Персоны поле family не читают.
"""

from __future__ import annotations

from product.matching.grade import score_attempt
from product.matching.stems import catalog

_LETTERS = ("a", "b", "c")
_HIT = frozenset({"confirm", "suggest_higher"})
_KEY_MEMORIZER = ["b", "c", "a"]


def _is_hit(scored: dict) -> bool:
    return scored["outcome"] in _HIT


def _answers_competent(template: dict) -> list[str]:
    return [str(question["correct"]) for question in template["questions"]]


def _answers_key_memorizer(_template: dict) -> list[str]:
    return list(_KEY_MEMORIZER)


def _answers_adjacent(template: dict) -> list[str]:
    return [
        min(letter for letter in _LETTERS if letter != question["correct"])
        for question in template["questions"]
    ]


def simulation_counts() -> dict[str, tuple[int, int]]:
    """Три пары (hit, n) по каталогу. select_template здесь не нужен."""
    rows = catalog()
    n = len(rows)
    competent = 0
    leak = 0
    adjacent = 0
    for template in rows:
        if _is_hit(score_attempt(template, _answers_competent(template))):
            competent += 1
        if _is_hit(score_attempt(template, _answers_key_memorizer(template))):
            leak += 1
        if _is_hit(score_attempt(template, _answers_adjacent(template))):
            adjacent += 1
    return {
        "sim_competent": (competent, n),
        "sim_key_leak": (leak, n),
        "sim_adjacent": (adjacent, n),
    }
