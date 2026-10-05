"""Прогон золотого набора. Печатает пять строк и ничего не скачивает.

Пока в кейсе нет expected_outcome и template_pairs, знаменатели итога и
шаблона нулевые. resumes.json подхватывается, когда его положит разбор PDF.
score_attempt возвращает словари с ключами outcome и proposed_grade.
read_resume_bytes принимает байты и отдаёт словарь; код resume_no_text в
ключе error — успешный разбор пустого слоя, не падение.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from product.matching.category import assign_category
from product.matching.rules import rule_version
from product.matching.types import ProfileView

_GOLDEN = Path(__file__).resolve().parent / "golden"
_CASES = _GOLDEN / "cases.json"


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
    stack = " ".join(row.get("stack") or [])
    return " ".join(
        [
            str(row.get("specialization") or ""),
            str(row.get("grade") or ""),
            stack,
            str(row.get("team_role") or ""),
            str(row.get("work_format") or ""),
            str(row.get("experience") or ""),
        ]
    ).casefold()


def _matches_need(row: dict, category_id: str, need: dict) -> bool:
    if category_id != need["category_id"]:
        return False
    if row.get("test_score") is None:
        return False
    stack_filter = [item for item in (need.get("stack") or []) if item]
    if stack_filter and not set(stack_filter) & set(row.get("stack") or []):
        return False
    if need.get("team_role") and row.get("team_role") != need["team_role"]:
        return False
    if need.get("work_format") and row.get("work_format") != need["work_format"]:
        return False
    has_fsp = need.get("has_fsp")
    count = int(row.get("fsp_confirmed_count") or 0)
    if has_fsp is True and count <= 0:
        return False
    if has_fsp is False and count > 0:
        return False
    query = str(need.get("q") or "").strip()
    if query and query.casefold() not in _need_text(row):
        return False
    return True


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
        try:
            result = read_resume_bytes(pdf.read_bytes())
        except Exception:
            continue
        if not isinstance(result, dict):
            continue
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
        pool = [pair for pair in ranked if _matches_need(pair[0], pair[1].category_id, need)]
        pool.sort(key=lambda pair: pair[1].rank_key, reverse=True)
        taken = pool[:top_k]
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
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.write(render_report())


if __name__ == "__main__":
    main()
