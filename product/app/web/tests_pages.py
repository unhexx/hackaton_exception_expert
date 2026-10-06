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
from product.app.services.errors import ApiError, explain
from product.app.services.tests import (
    interval_blocks,
    interval_message,
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
    if profile is None:
        hint = explain("survey_required")
    elif offer and interval_blocks(db, profile, offer):
        interval_notice = interval_message(profile, offer)
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
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    try:
        assert_csrf(request, csrf)
        submit_attempt(
            db,
            user,
            attempt_id,
            {"answers": [answer_0, answer_1, answer_2]},
        )
    except ApiError as exc:
        return page_error(request, "candidate/test.html", _context(request, db, user), exc)
    return RedirectResponse("/candidate/test", status_code=303)
