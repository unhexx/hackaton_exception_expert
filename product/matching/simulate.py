"""CPU-персоны для прогона жюри. Четыре правила без GPU и без сети.

Множество — все 72 шаблона, каждый через наименьший profile_id.
Печатаются competent, key_leak и adjacent; random реализован и в отчёт не входит.
Персоны поле family не читают.
"""

from __future__ import annotations

import random
from functools import lru_cache

from product.matching.golden_run import is_drift
from product.matching.grade import load_template, score_attempt, select_template
from product.matching.rules import load_rules
from product.matching.stems import catalog

SIM_PROFILE_ID_LIMIT = 10000

_LETTERS = ("a", "b", "c")
_HIT = frozenset({"confirm", "suggest_higher"})
_RANDOM_SEED = 20261010
_KEY_MEMORIZER = ["b", "c", "a"]


def _is_hit(scored: dict) -> bool:
    return scored["outcome"] in _HIT


def _answers_competent(template: dict) -> list[str]:
    return [str(question["correct"]) for question in template["questions"]]


def _answers_key_memorizer(_template: dict) -> list[str]:
    return list(_KEY_MEMORIZER)


def _adjacent_letter(question: dict) -> str:
    incorrect = [choice for choice in question["choices"] if choice["id"] != question["correct"]]
    non_drift = [choice for choice in incorrect if not is_drift(str(choice["text"]))]
    if not non_drift:
        return str(incorrect[0]["id"])
    return min(str(choice["id"]) for choice in non_drift)


def _answers_adjacent(template: dict) -> list[str]:
    return [_adjacent_letter(question) for question in template["questions"]]


def _answers_random(template: dict, rng: random.Random) -> list[str]:
    return [rng.choice(_LETTERS) for _question in template["questions"]]


@lru_cache(maxsize=1)
def _simulation_slots() -> tuple[tuple[int, str, str, str], ...]:
    """(profile_id, specialization, grade, template_id) на каждый из 72 шаблонов."""
    known = {str(row["template_id"]) for row in catalog()}
    rules = load_rules()
    slots: list[tuple[int, str, str, str]] = []
    for specialization in rules["specializations"]:
        for grade in rules["grades"]:
            wanted = {f"{specialization}-{grade}-{letter}": None for letter in _LETTERS}
            remaining = set(wanted)
            missing = remaining - known
            if missing:
                raise RuntimeError(f"в каталоге нет шаблона {sorted(missing)[0]}")
            for profile_id in range(1, SIM_PROFILE_ID_LIMIT + 1):
                template_id = select_template(profile_id, specialization, grade, "v1")
                if template_id in remaining:
                    wanted[template_id] = profile_id
                    remaining.remove(template_id)
                    if not remaining:
                        break
            for letter in _LETTERS:
                template_id = f"{specialization}-{grade}-{letter}"
                profile_id = wanted[template_id]
                if profile_id is None:
                    raise RuntimeError(
                        f"для шаблона {template_id} нет profile_id в диапазоне 1..{SIM_PROFILE_ID_LIMIT}"
                    )
                slots.append((profile_id, specialization, grade, template_id))
    return tuple(slots)


def simulation_counts() -> dict[str, tuple[int, int]]:
    """Три пары (hit, n) для отчёта. Random считается правилом, в счётчики не входит."""
    slots = _simulation_slots()
    n = len(slots)
    competent = 0
    leak = 0
    adjacent = 0
    rng = random.Random(_RANDOM_SEED)
    for profile_id, specialization, grade, expected_id in slots:
        template_id = select_template(profile_id, specialization, grade, "v1")
        if template_id != expected_id:
            raise RuntimeError(f"select_template({profile_id}) дал {template_id}, ждали {expected_id}")
        template = load_template(template_id)
        if _is_hit(score_attempt(template, _answers_competent(template))):
            competent += 1
        if _is_hit(score_attempt(template, _answers_key_memorizer(template))):
            leak += 1
        if _is_hit(score_attempt(template, _answers_adjacent(template))):
            adjacent += 1
        score_attempt(template, _answers_random(template, rng))
    return {
        "sim_competent": (competent, n),
        "sim_key_leak": (leak, n),
        "sim_adjacent": (adjacent, n),
    }
