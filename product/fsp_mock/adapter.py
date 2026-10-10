"""Синонимы дисциплины к канону. Разряд и место не трогаем.

ТЗ §2: состав данных ФСП команда определяет сама; Q&A — дисциплины не ранжируются.
"""

from __future__ import annotations

CANONICAL_DISCIPLINES = (
    "Программирование алгоритмическое",
    "Продуктовое программирование",
    "Программирование систем информационной безопасности",
    "Программирование робототехники",
    "Программирование БАС",
)

_SYNONYMS = {
    "алгоритмика": "Программирование алгоритмическое",
    "алгоритмическое": "Программирование алгоритмическое",
    "алгоритмическое программирование": "Программирование алгоритмическое",
    "продуктовое": "Продуктовое программирование",
    "информационная безопасность": "Программирование систем информационной безопасности",
    "иб": "Программирование систем информационной безопасности",
    "робототехника": "Программирование робототехники",
    "бас": "Программирование БАС",
    "беспилотные авиационные системы": "Программирование БАС",
}


def discipline_label(raw: str) -> str:
    text = raw.strip()
    if text in CANONICAL_DISCIPLINES:
        return text
    mapped = _SYNONYMS.get(text.casefold())
    if mapped is not None:
        return mapped
    return text


def adapt_participant(raw: dict) -> dict:
    results = []
    for row in raw.get("results") or []:
        results.append(
            {
                "competition_id": str(row["competition_id"]),
                "competition_name": str(row["competition_name"]),
                "discipline": discipline_label(str(row["discipline"])),
                "role_in_team": str(row["role_in_team"]),
                "place": str(row["place"]),
                "held_on": str(row["held_on"]),
            }
        )
    return {
        "external_id": str(raw["external_id"]),
        "display_name": str(raw["display_name"]),
        "rank": str(raw["rank"]).strip(),
        "results": results,
    }
