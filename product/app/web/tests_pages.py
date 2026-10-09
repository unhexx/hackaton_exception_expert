"""Страница испытания: история, черновик и связь вакансии с шаблоном."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.db.models import Profile, TestAttempt
from product.app.db.session import sqlite_int
from product.app.services.errors import ApiError, fail, hint as catalog_hint
from product.app.services.tests import (
    interval_blocks,
    interval_parts,
    latest_recorded_attempt,
    list_attempts,
    proposed_adjacent,
    start_attempt,
    submit_attempt,
)
from product.app.web.guards import page_user
from product.app.web.render import assert_csrf, ensure_csrf, page_error, render
from product.matching.grade import load_template, public_questions

router = APIRouter()
_SAMPLES = Path(__file__).resolve().parents[2] / "matching" / "vacancies" / "samples.json"
_TRUE = {"true"}
_MARKS = {"true", "false"}
_CHOICE_IDS = ("a", "b", "c")
_RETRY_HINT = "В каждом вопросе может быть только 1 верный ответ. Пройдите этот вопрос ещё раз."


def assemble_letter(marks: dict[str, str]) -> str:
    """Ровно одна «истина» → эта буква. Иначе пустая строка (на сдаче станет answer_unknown)."""
    truths = [cid for cid in _CHOICE_IDS if marks.get(cid, "") in _TRUE]
    if len(truths) == 1:
        return truths[0]
    return ""


def _parse_step(raw: str) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 12:
        return None
    return value


def _empty_marks() -> dict[int, dict[str, str]]:
    return {q: {"a": "", "b": "", "c": ""} for q in range(3)}


def _empty_answers() -> dict[int, str]:
    return {0: "", 1: "", 2: ""}


def _coerce_step(raw: object) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    if raw < 0 or raw > 12:
        return None
    return raw


def _coerce_marks(raw: object) -> dict[int, dict[str, str]]:
    marks = _empty_marks()
    if not isinstance(raw, dict):
        return marks
    for q in range(3):
        item = raw.get(str(q), raw.get(q))
        if not isinstance(item, dict):
            continue
        for cid in _CHOICE_IDS:
            value = item.get(cid, "")
            marks[q][cid] = value if isinstance(value, str) else ""
    return marks


def _coerce_answers(raw: object) -> dict[int, str]:
    answers = _empty_answers()
    if isinstance(raw, list):
        for q in range(3):
            if q < len(raw) and isinstance(raw[q], str):
                answers[q] = raw[q]
        return answers
    if isinstance(raw, dict):
        for q in range(3):
            value = raw.get(str(q), raw.get(q, ""))
            if isinstance(value, str):
                answers[q] = value
    return answers


def _load_progress(
    draft: TestAttempt,
) -> tuple[int, dict[int, dict[str, str]], dict[int, str]]:
    raw = draft.answers_json
    if not raw:
        return 0, _empty_marks(), _empty_answers()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return 0, _empty_marks(), _empty_answers()
    if not isinstance(payload, dict):
        return 0, _empty_marks(), _empty_answers()
    step = _coerce_step(payload.get("step"))
    if step is None:
        step = 0
    return step, _coerce_marks(payload.get("marks")), _coerce_answers(payload.get("answers"))


def _dump_progress(
    step: int,
    marks: dict[int, dict[str, str]],
    answers: dict[int, str],
) -> str:
    return json.dumps(
        {
            "step": step,
            "marks": {str(q): dict(marks[q]) for q in range(3)},
            "answers": [answers.get(q, "") for q in range(3)],
        },
        ensure_ascii=False,
    )


def _marks_from_fields(
    mark_0_a: str,
    mark_0_b: str,
    mark_0_c: str,
    mark_1_a: str,
    mark_1_b: str,
    mark_1_c: str,
    mark_2_a: str,
    mark_2_b: str,
    mark_2_c: str,
) -> dict[int, dict[str, str]]:
    return {
        0: {"a": mark_0_a, "b": mark_0_b, "c": mark_0_c},
        1: {"a": mark_1_a, "b": mark_1_b, "c": mark_1_c},
        2: {"a": mark_2_a, "b": mark_2_b, "c": mark_2_c},
    }


def _letters_from_form(
    answer_0: str,
    answer_1: str,
    answer_2: str,
    marks: dict[int, dict[str, str]],
) -> list[str]:
    letters = [answer_0, answer_1, answer_2]
    if all(letter in _CHOICE_IDS for letter in letters):
        return letters
    return [assemble_letter(marks[q]) for q in range(3)]


def _advance_step(
    current: int,
    advance: str,
    mark: str,
    marks: dict[int, dict[str, str]],
    answers: dict[int, str],
) -> tuple[int, str]:
    if current == 12:
        return 12, ""
    phase = current % 4
    question = current // 4
    if phase == 0:
        if advance == "1":
            return current + 1, ""
        return current, ""
    if mark not in _MARKS:
        return current, ""
    choice = _CHOICE_IDS[phase - 1]
    marks[question][choice] = mark
    if phase in (1, 2):
        return current + 1, ""
    letter = assemble_letter(marks[question])
    if letter:
        answers[question] = letter
        return current + 1, ""
    for cid in _CHOICE_IDS:
        marks[question][cid] = ""
    answers[question] = ""
    return question * 4, _RETRY_HINT


def _station_classes(step: int) -> list[str]:
    if step == 12:
        return ["test-station-done", "test-station-done", "test-station-done"]
    current_q = step // 4
    classes = []
    for index in range(3):
        if index < current_q:
            classes.append("test-station-done")
        elif index == current_q:
            classes.append("test-station-current")
        else:
            classes.append("test-station-todo")
    return classes


def _step_error_text(exc: ApiError) -> str:
    line = exc.message.split("\n", 1)[0]
    return line.removeprefix("Что случилось. ").strip() or exc.message


def _render_step(
    request: Request,
    *,
    step: int,
    questions: list[dict],
    marks: dict[int, dict[str, str]],
    answers: dict[int, str],
    hint: str = "",
    error: str = "",
):
    phase = 0 if step == 12 else step % 4
    question_index = 2 if step == 12 else step // 4
    n = 3 if step == 12 else question_index + 1
    k = 0 if step == 12 or phase == 0 else phase
    question = None
    choice = None
    if questions and 0 <= question_index < len(questions):
        question = questions[question_index]
        if question is not None and 1 <= phase <= 3:
            choices = question.get("choices") or []
            if phase - 1 < len(choices):
                choice = choices[phase - 1]
    ctx = {
        "step": step,
        "n": n,
        "k": k,
        "phase": phase,
        "stations": _station_classes(step),
        "question": question,
        "choice": choice,
        "hint": hint,
        "error": error,
        "marks": marks,
        "answers": answers,
    }
    return render(request, "candidate/_test_step.html", ctx)


def _samples() -> list[dict]:
    if not _SAMPLES.is_file():
        return []
    payload = json.loads(_SAMPLES.read_text(encoding="utf-8"))
    return list(payload.get("vacancies") or [])


def _context(request: Request, db: Session, user, error: str = "") -> dict:
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    draft = None
    questions: list[dict] = []
    if profile is not None:
        draft = db.scalar(
            select(TestAttempt).where(
                TestAttempt.profile_id == profile.id,
                TestAttempt.status == "draft",
            )
        )
        if draft is not None:
            questions = public_questions(load_template(draft.template_id))
    history = list_attempts(db, user)
    offer = proposed_adjacent(db, profile) if profile is not None else ""
    interval_notice = ""
    hint = ""
    recorded = latest_recorded_attempt(db, profile) if profile is not None else None
    outcome_view = None
    if profile is None:
        hint = catalog_hint("survey_required")
    elif offer and interval_blocks(db, profile, offer):
        interval_notice = catalog_hint("grade_interval", **interval_parts(profile, offer))
    if draft is None and recorded is not None:
        template = load_template(recorded.template_id)
        outcome_view = {
            "score": recorded.score,
            "outcome": recorded.outcome,
            "declared_grade": recorded.declared_grade,
            "proposed_grade": recorded.proposed_grade,
            "confirm_min": int(template["confirm_min"]),
            "suggest_higher_min": int(template["suggest_higher_min"]),
        }
    return {
        "csrf": ensure_csrf(request),
        "error": error,
        "hint": hint,
        "user": user,
        "profile": profile,
        "draft": draft,
        "questions": questions,
        "history": history,
        "offer": offer,
        "interval_notice": interval_notice,
        "outcome_view": outcome_view,
        "samples": _samples(),
    }


@router.get("/candidate/test")
def test_page(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    return render(request, "candidate/test.html", _context(request, db, user))


@router.post("/candidate/test/start")
def start_page(
    request: Request,
    csrf: str = Form(""),
    grade: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    payload = {"grade": grade} if grade else {}
    try:
        assert_csrf(request, csrf)
        start_attempt(db, user, payload)
    except ApiError as exc:
        return page_error(request, "candidate/test.html", _context(request, db, user), exc)
    return RedirectResponse("/candidate/test", status_code=303)


@router.post("/candidate/test/submit")
def submit_page(
    request: Request,
    csrf: str = Form(""),
    attempt_id: int = Form(...),
    answer_0: str = Form(""),
    answer_1: str = Form(""),
    answer_2: str = Form(""),
    mark_0_a: str = Form(""),
    mark_0_b: str = Form(""),
    mark_0_c: str = Form(""),
    mark_1_a: str = Form(""),
    mark_1_b: str = Form(""),
    mark_1_c: str = Form(""),
    mark_2_a: str = Form(""),
    mark_2_b: str = Form(""),
    mark_2_c: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    try:
        assert_csrf(request, csrf)
        letters = _letters_from_form(
            answer_0,
            answer_1,
            answer_2,
            _marks_from_fields(
                mark_0_a,
                mark_0_b,
                mark_0_c,
                mark_1_a,
                mark_1_b,
                mark_1_c,
                mark_2_a,
                mark_2_b,
                mark_2_c,
            ),
        )
        submit_attempt(
            db,
            user,
            attempt_id,
            {"answers": letters},
        )
    except ApiError as exc:
        return page_error(request, "candidate/test.html", _context(request, db, user), exc)
    return RedirectResponse("/candidate/test", status_code=303)


@router.post("/candidate/test/step")
def step_page(
    request: Request,
    csrf: str = Form(""),
    attempt_id: str = Form(""),
    step: str = Form(""),
    mark: str = Form(""),
    advance: str = Form(""),
    mark_0_a: str = Form(""),
    mark_0_b: str = Form(""),
    mark_0_c: str = Form(""),
    mark_1_a: str = Form(""),
    mark_1_b: str = Form(""),
    mark_1_c: str = Form(""),
    mark_2_a: str = Form(""),
    mark_2_b: str = Form(""),
    mark_2_c: str = Form(""),
    answer_0: str = Form(""),
    answer_1: str = Form(""),
    answer_2: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    hx = request.headers.get("hx-request") == "true"
    marks = _marks_from_fields(
        mark_0_a,
        mark_0_b,
        mark_0_c,
        mark_1_a,
        mark_1_b,
        mark_1_c,
        mark_2_a,
        mark_2_b,
        mark_2_c,
    )
    answers = {0: answer_0, 1: answer_1, 2: answer_2}
    posted = _parse_step(step)
    echo_step = posted if posted is not None else 0
    # htmx 2.0.4 не свапает 4xx — любой HX-ответ шага это 200 и фрагмент.
    try:
        assert_csrf(request, csrf)
    except ApiError as exc:
        if hx:
            return _render_step(
                request,
                step=echo_step,
                questions=[],
                marks=marks,
                answers=answers,
                error=_step_error_text(exc),
            )
        return page_error(request, "candidate/test.html", _context(request, db, user), exc)
    if not hx:
        return RedirectResponse("/candidate/test", status_code=303)
    try:
        try:
            parsed_id = sqlite_int(int(attempt_id))
        except (TypeError, ValueError):
            parsed_id = None
        if parsed_id is None:
            fail(404, "not_found", "not_found_attempt")
        profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
        draft = None
        if profile is not None:
            draft = db.scalar(
                select(TestAttempt).where(
                    TestAttempt.id == parsed_id,
                    TestAttempt.profile_id == profile.id,
                    TestAttempt.status == "draft",
                )
            )
        if draft is None:
            fail(404, "not_found", "not_found_attempt")
        questions = public_questions(load_template(draft.template_id))
        saved_step, marks, answers = _load_progress(draft)
        hint = ""
        display = saved_step
        acting = posted is not None and posted == saved_step and (
            advance == "1" or mark in _MARKS
        )
        if acting:
            display, hint = _advance_step(saved_step, advance, mark, marks, answers)
            draft.answers_json = _dump_progress(display, marks, answers)
            db.commit()
        return _render_step(
            request,
            step=display,
            questions=questions,
            marks=marks,
            answers=answers,
            hint=hint,
        )
    except ApiError as exc:
        return _render_step(
            request,
            step=echo_step,
            questions=[],
            marks=marks,
            answers=answers,
            error=_step_error_text(exc),
        )
