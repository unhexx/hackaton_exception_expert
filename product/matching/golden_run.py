"""Прогон золотого набора. Печатает пять строк, grade_separation и три CPU-персоны, ничего не скачивает.

Пока в кейсе нет expected_outcome и template_pairs, знаменатели итога и
шаблона нулевые. resumes.json подхватывается, когда его положит разбор PDF.
score_attempt возвращает словари с ключами outcome и proposed_grade.
read_resume_bytes принимает байты и отдаёт словарь; код resume_no_text в
ключе error — успешный разбор пустого слоя, не падение.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from product.matching.category import assign_category
from product.matching.need import evaluate_need, haystack_text
from product.matching.rules import load_rules, rule_version
from product.matching.simulate import simulation_counts
from product.matching.stems import catalog
from product.matching.types import Need, ProfileView

_GOLDEN = Path(__file__).resolve().parent / "golden"
_CASES = _GOLDEN / "cases.json"

# Поверхность, не ошибка по оси: цвет, логотип, лайки, имя дашборда и то же семейство.
_DRIFT_PARTS = (
    "логотип",
    "лайк",
    "звезд",
    "бренд",
    "красот",
    "красив",
    "иконк",
    "figma",
    "артборд",
    "эмодзи",
    "пиксел",
    "lighthouse",
    "любим",
    "сторипоинт",
    "имя дашборда",
    "яркость",
    "жест шторки",
    "звук чужого",
    "скриншот",
    "язык анимации",
    "длину анимации",
    "в обзоре",
    "кто последний заходил",
    "число строк в файле",
    "лицензи",
    "раскладк",
)
_DRIFT_SPEEDS = (
    "пинг ",
    "скорость lte",
    "скорость dns",
    "скорость капчи",
    "скорость брутфорса",
    "скорость tls",
    "скорость пальца",
    "скорость вставки",
    "скорость склада",
)
_NAME_DRIFT = re.compile(
    r"^(?:название |имя (?:кластера|ветки|темы|дизайнера|алгоритма|сканера|облака|ca |from))"
)
_COUNT_DRIFT = re.compile(
    r"^число (?:дашбордов|ноутбуков|чартов|подов|узлов|пайплайнов|ведер|экранов)\b"
)
_LENGTH_DRIFT = re.compile(r"^длин[ауи] (?:base64|токена|ключа)\b")
_COLOR_WORD = re.compile(r"(?<![а-яa-z])цвет(?![а-яa-z])")
_TOKEN = re.compile(r"(?<![a-z])(?:stars|fps|splash)(?![a-z])")


def _folded(text: str) -> str:
    return text.casefold().replace("ё", "е")


def is_drift(text: str) -> bool:
    """Уход в сторону: цвет, логотип, число лайков, имя дашборда и то же семейство."""
    folded = _folded(text)
    if _COLOR_WORD.search(folded) or folded.startswith("оттенок"):
        return True
    if any(part in folded for part in _DRIFT_PARTS) or any(part in folded for part in _DRIFT_SPEEDS):
        return True
    if _TOKEN.search(folded) or _NAME_DRIFT.search(folded) or _COUNT_DRIFT.search(folded):
        return True
    return _LENGTH_DRIFT.search(folded) is not None


def item_separates(question: dict, grade: str) -> bool:
    """Оба неверных — не уход в сторону.

    На junior нижнего соседа нет, оба неверных остаются на той же оси.
    Выше junior те же неверные — ошибка соседнего нижнего грейда.
    """
    grades = [str(item) for item in load_rules()["grades"]]
    if grade not in grades:
        return False
    wrong = [str(choice["text"]) for choice in question["choices"] if choice["id"] != question["correct"]]
    if len(wrong) != 2 or any(is_drift(text) for text in wrong):
        return False
    return True


def grade_separation_counts() -> tuple[int, int]:
    """Сколько пунктов v1 разделяют грейды, и сколько пунктов всего. Порога нет."""
    separated = 0
    total = 0
    for row in catalog():
        if row.get("rule_version") != "v1":
            continue
        grade = str(row["grade"])
        for question in row["questions"]:
            total += 1
            if item_separates(question, grade):
                separated += 1
    return separated, total


def load_cases() -> dict:
    return json.loads(_CASES.read_text(encoding="utf-8"))


def _view(row: dict) -> ProfileView:
    return ProfileView(
        profile_id=int(row["profile_id"]),
        specialization=str(row["specialization"]),
        grade=str(row["grade"]),
        test_score=None if row.get("test_score") is None else int(row["test_score"]),
        test_outcome=row.get("test_outcome"),
        fsp_confirmed_count=int(row.get("fsp_confirmed_count") or 0),
    )


def _need_text(row: dict) -> str:
    return haystack_text(
        specialization=str(row.get("specialization") or ""),
        grade=str(row.get("grade") or ""),
        stack=list(row.get("stack") or []),
        team_role=str(row.get("team_role") or ""),
        work_format=str(row.get("work_format") or ""),
        experience=str(row.get("experience") or ""),
    )


def _fit(row: dict, category_id: str, rank_key: str, need: dict):
    return evaluate_need(
        assigned_category_id=category_id,
        test_score=None if row.get("test_score") is None else int(row["test_score"]),
        stack=list(row.get("stack") or []),
        team_role=str(row.get("team_role") or ""),
        work_format=str(row.get("work_format") or ""),
        fsp_count=int(row.get("fsp_confirmed_count") or 0),
        haystack=_need_text(row),
        need=Need.from_mapping(need),
        rank_key=rank_key,
    )


def _scores_match_answers(cases: dict) -> None:
    from product.matching.grade import load_template, score_attempt

    for row in cases["profiles"]:
        if "answers" not in row:
            continue
        scored = score_attempt(load_template(row["template_id"]), row["answers"])
        if row.get("expected_outcome") not in (None, scored["outcome"]):
            raise ValueError(
                f"profile {row['profile_id']}: expected_outcome {row.get('expected_outcome')} "
                f"не сходится с ответами {scored['outcome']}"
            )
        if row.get("test_score") != scored["score"] or row.get("test_outcome") != scored["outcome"]:
            raise ValueError(
                f"profile {row['profile_id']}: балл {row.get('test_score')}/{row.get('test_outcome')} "
                f"не сходится с ответами {scored['score']}/{scored['outcome']}"
            )


def _outcome_counts(cases: dict) -> tuple[int, int]:
    rows = [row for row in cases["profiles"] if "expected_outcome" in row]
    if not rows:
        return 0, 0
    from product.matching.grade import load_template, score_attempt

    hit = 0
    for row in rows:
        scored = score_attempt(load_template(row["template_id"]), row["answers"])
        if scored["outcome"] == row["expected_outcome"]:
            hit += 1
    return hit, len(rows)


def _template_counts(cases: dict) -> tuple[int, int]:
    pairs = list(cases.get("template_pairs") or [])
    if not pairs:
        return 0, 0
    from product.matching.grade import load_template, score_attempt

    hit = 0
    for pair in pairs:
        template = load_template(pair["template_id"])
        first = score_attempt(template, pair["answers"])
        second = score_attempt(template, pair["answers_repeat"])
        if first["proposed_grade"] == second["proposed_grade"]:
            hit += 1
    return hit, len(pairs)


def _resume_counts() -> tuple[int, int]:
    manifest = _GOLDEN / "resumes.json"
    if not manifest.is_file():
        return 0, 0
    from product.matching.resume import read_resume_bytes

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    ok = 0
    for item in items:
        pdf = manifest.parent / "resumes" / item["file"]
        result = read_resume_bytes(pdf.read_bytes())
        if not isinstance(result, dict):
            raise TypeError(f"разбор {item['file']} вернул {type(result)!r}")
        code = result.get("error")
        expect = item.get("expect")
        if expect:
            if code == expect:
                ok += 1
            continue
        if not code:
            ok += 1
    return ok, len(items)


def summarize(cases: dict | None = None) -> dict:
    data = cases if cases is not None else load_cases()
    _scores_match_answers(data)
    version = rule_version()
    matched = 0
    ranked = []
    for row in data["profiles"]:
        decision = assign_category(_view(row), version)
        if decision.category_id == row["expected_category_id"]:
            matched += 1
        ranked.append((row, decision))
    top_k = int(data["top_k"])
    relevant_hit = 0
    slots = 0
    for need in data["needs"]:
        fitted = [
            (pair, _fit(pair[0], pair[1].category_id, pair[1].rank_key, need))
            for pair in ranked
        ]
        pool = [(pair, fit) for pair, fit in fitted if fit.matched]
        pool.sort(key=lambda item: item[1].sort_key, reverse=True)
        taken = [pair for pair, _fit_row in pool[:top_k]]
        slots += len(taken)
        marked = set(need["relevant_profile_ids"])
        relevant_hit += sum(1 for row, _decision in taken if row["profile_id"] in marked)
    outcome_hit, outcome_total = _outcome_counts(data)
    stable_hit, stable_total = _template_counts(data)
    resume_hit, resume_total = _resume_counts()
    return {
        "category_match": (matched, len(data["profiles"])),
        "outcome_match": (outcome_hit, outcome_total),
        "template_stable": (stable_hit, stable_total),
        "relevant_in_top": (relevant_hit, slots),
        "resume_ok": (resume_hit, resume_total),
    }


def render_report(cases: dict | None = None) -> str:
    counts = summarize(cases)
    order = (
        "category_match",
        "outcome_match",
        "template_stable",
        "relevant_in_top",
        "resume_ok",
    )
    lines = [f"{name} {counts[name][0]} {counts[name][1]}" for name in order]
    separated, total = grade_separation_counts()
    lines.append(f"grade_separation {separated} {total}")
    sim = simulation_counts()
    for name in ("sim_competent", "sim_key_leak", "sim_adjacent"):
        hit, n = sim[name]
        lines.append(f"{name} {hit} {n}")
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.write(render_report())


if __name__ == "__main__":
    main()
