"""Старт, ответы, сдача и история испытания грейда.

ТЗ §2: категория определяется «обязательным путём при регистрации: опрос по
отрасли и специализации, самостоятельный выбор предполагаемого грейда и
тестирование на заявленный грейд»; «по результату теста грейд не понижается
принудительно… смена грейда ограничена по времени».
ТЗ §2.1 «Категория и грейд: … возможность пройти тест на грейд ниже или выше
с ограничением по частоте смены грейда».

Сборка варианта, оценка и решение — ``product.matching.assessment`` (тот же код,
что проверен симуляцией ``product.validation_sim``). Здесь — правила кабинета:
черновик попытки, интервал смены грейда, запись грейда и пересчёт категории.

Интервал держит смену записанного грейда, не повтор той же пары.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import Profile, TestAttempt, User
from product.app.db.session import sqlite_int
from product.app.services.categories import latest_assignment, recompute
from product.app.services.clock import days_elapsed, days_remaining, utc_now
from product.app.services.errors import explain, fail
from product.matching import assessment
from product.matching.rules import load_rules, rule_version

ACCUMULATE_LAST = 2  # сколько прошлых попыток учитывать вместе с текущей (как в симуляции: до 3)

_OUTCOME = {
    "confirm": "заявленный грейд подтверждён",
    "suggest_lower": "предложен грейд ниже",
    "suggest_higher": "предложен грейд выше",
}


# --- Грейды и интервал смены (ТЗ §2: «не чаще одного раза в N месяцев») -------


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


def interval_days() -> int:
    return int(load_rules()["grade_change_interval_days"])


def interval_open(stamp: str) -> bool:
    return days_elapsed(stamp, interval_days())


def interval_parts(profile: Profile, requested: str) -> dict[str, object]:
    days = interval_days()
    return {
        "current": profile.grade,
        "requested": requested,
        "changed_at": profile.grade_changed_at,
        "interval": days,
        "left": days_remaining(profile.grade_changed_at, days),
    }


def interval_message(profile: Profile, requested: str) -> str:
    return explain("grade_interval", **interval_parts(profile, requested))


def grade_written_by_test(db: Session, profile: Profile) -> bool:
    """True, только если соседний confirm уже записал новый грейд (ветка сдачи)."""
    rows = db.scalars(
        select(TestAttempt)
        .where(TestAttempt.profile_id == profile.id, TestAttempt.status == "submitted")
        .order_by(TestAttempt.id.asc())
    ).all()
    if not rows:
        return False
    running = rows[0].declared_grade
    written = False
    for row in rows:
        if row.outcome == "confirm" and row.declared_grade != running:
            written = True
            running = row.declared_grade
    return written


def interval_blocks(db: Session, profile: Profile, requested: str) -> bool:
    """True, когда запрошен не записанный грейд, штамп интервала ещё свежий и
    соседний confirm уже записал новый грейд.

    Пока тест грейд не писал — первый соседний старт (вверх после
    suggest_higher или вниз после suggest_lower) интервал не ждёт.
    ТЗ §2.1 «ограничение по частоте смены грейда»; Q&A: провал и уход ниже —
    без сжигания попытки.
    """
    if requested == profile.grade:
        return False
    if interval_open(profile.grade_changed_at):
        return False
    return grade_written_by_test(db, profile)


# --- Попытки ------------------------------------------------------------------


def _profile(db: Session, user: User) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user.id))


def _draft(db: Session, profile_id: int) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt).where(TestAttempt.profile_id == profile_id, TestAttempt.status == "draft")
    )


def _form(row: TestAttempt) -> dict:
    if not row.form_json:
        return {"items": [], "answers": {}, "blocks": 0}
    return json.loads(row.form_json)


def _result(row: TestAttempt) -> dict:
    return json.loads(row.result_json) if row.result_json else {}


def attempt_result(row: TestAttempt | None) -> dict:
    """Уверенность, статус и положение в грейде из сданной попытки ({} — нет)."""
    return {} if row is None else _result(row)


def latest_recorded_attempt(db: Session, profile: Profile) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt)
        .where(
            TestAttempt.profile_id == profile.id,
            TestAttempt.status == "submitted",
            TestAttempt.specialization == profile.specialization,
            TestAttempt.declared_grade == profile.grade,
        )
        .order_by(TestAttempt.id.desc())
        .limit(1)
    )


def proposed_adjacent(db: Session, profile: Profile) -> str:
    offer = latest_recorded_attempt(db, profile)
    if offer is None or not offer.proposed_grade or offer.proposed_grade == profile.grade:
        return ""
    if not is_adjacent_grade(profile.grade, offer.proposed_grade):
        return ""
    return offer.proposed_grade


def _public_attempt(row: TestAttempt) -> dict:
    stored = _form(row)
    questions = assessment.public_questions(assessment.pending(stored))
    return {
        "attempt_id": row.id,
        "template_id": row.template_id,
        "specialization": row.specialization,
        "declared_grade": row.declared_grade,
        "answered": len(stored.get("answers") or {}),
        "total": len(stored["items"]),
        "questions": questions,
    }


def public_draft(row: TestAttempt) -> dict:
    """Черновик для страницы кабинета (те же поля, что у API)."""
    return _public_attempt(row)


def list_attempts(db: Session, user: User) -> list[dict]:
    profile = _profile(db, user)
    if profile is None:
        return []
    rows = db.scalars(
        select(TestAttempt).where(TestAttempt.profile_id == profile.id).order_by(TestAttempt.id.desc())
    ).all()
    history = []
    for row in rows:
        result = _result(row)
        history.append(
            {
                "attempt_id": row.id,
                "template_id": row.template_id,
                "specialization": row.specialization,
                "declared_grade": row.declared_grade,
                "status": row.status,
                "score": row.score,
                "outcome": row.outcome,
                "outcome_label": _OUTCOME.get(row.outcome or "", ""),
                "proposed_grade": row.proposed_grade,
                "confidence": result.get("confidence"),
                "test_status": result.get("status"),
                "position": result.get("position"),
                "n_items": result.get("n_items"),
                "created_at": row.created_at,
                "submitted_at": row.submitted_at,
            }
        )
    return history


def _previous_forms(db: Session, profile: Profile, spec: str, exclude_id: int | None = None) -> list[dict]:
    rows = db.scalars(
        select(TestAttempt)
        .where(
            TestAttempt.profile_id == profile.id,
            TestAttempt.specialization == spec,
            TestAttempt.form_json.is_not(None),
        )
        .order_by(TestAttempt.id.asc())
    ).all()
    return [_form(row) for row in rows if row.id != exclude_id]


def _exposure(db: Session):
    """Показы вариантов по всей платформе — для равномерного расхода банка."""
    forms = [
        json.loads(raw)
        for raw in db.scalars(select(TestAttempt.form_json).where(TestAttempt.form_json.is_not(None))).all()
    ]
    return assessment.exposure_from(forms)


def start_attempt(db: Session, user: User, payload: dict | None) -> dict:
    """Один черновик на профиль. Вариант собирает `assessment.new_form`; клиент получает вопросы без ключа.

    Соседний грейд — только предложенный последней сдачей записанной пары.
    """
    profile = _profile(db, user)
    if profile is None:
        fail(409, "survey_required")
    requested = ""
    if payload:
        raw = payload.get("grade", "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            fail(422, "closed_list", "closed_list_grade")
        requested = raw.strip()
    target = profile.grade
    adjacent = False
    if requested and requested != profile.grade:
        if not is_adjacent_grade(profile.grade, requested):
            fail(409, "grade_not_offered", "grade_not_adjacent", current=profile.grade, requested=requested)
        offered = proposed_adjacent(db, profile)
        if offered != requested:
            fail(
                409,
                "grade_not_offered",
                "grade_not_proposed",
                current=profile.grade,
                requested=requested,
                offered=offered or "нет",
            )
        target = requested
        adjacent = True
    draft = _draft(db, profile.id)
    if draft is not None and not draft.form_json:
        # Черновик без сохранённого варианта (form_json пуст — например, строка
        # из тома до добавления колонки): в базе может быть только один черновик,
        # поэтому строка переиспользуется под новый вариант.
        spec = profile.specialization
        seen = assessment.history_from(_previous_forms(db, profile, spec))
        draft.specialization, draft.declared_grade = spec, target
        draft.template_id = assessment.ENGINE
        draft.answers_json = None
        draft.form_json = json.dumps(assessment.new_form(spec, target, seen, _exposure(db)), ensure_ascii=False)
        db.commit()
        return _public_attempt(draft)
    if draft is not None:
        same = draft.specialization == profile.specialization and draft.declared_grade == target
        if not same:
            fail(409, "attempt_open", draft_grade=draft.declared_grade)
        return _public_attempt(draft)
    if adjacent and interval_blocks(db, profile, target):
        fail(409, "grade_interval", **interval_parts(profile, target))
    spec = profile.specialization
    # Пересдача — другие темы: уже показанные кандидату семейства идут последними.
    seen = assessment.history_from(_previous_forms(db, profile, spec))
    stored = assessment.new_form(spec, target, seen, _exposure(db))
    if not stored["items"]:
        fail(409, "bank_empty", specialization=spec, grade=target)
    row = TestAttempt(
        profile_id=profile.id,
        specialization=spec,
        declared_grade=target,
        template_id=assessment.ENGINE,
        rule_version=rule_version(),
        answers_json=None,
        score=None,
        outcome=None,
        proposed_grade=None,
        status="draft",
        created_at=utc_now(),
        submitted_at=None,
        form_json=json.dumps(stored, ensure_ascii=False),
        result_json=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _public_attempt(row)


def _own_draft(db: Session, user: User, attempt_id: object) -> tuple[Profile, TestAttempt]:
    profile = _profile(db, user)
    if profile is None:
        fail(404, "not_found", "not_found_attempt")
    row = db.get(TestAttempt, attempt_id) if sqlite_int(attempt_id) is not None else None
    if row is None or row.profile_id != profile.id:
        fail(404, "not_found", "not_found_attempt")
    if row.status != "draft":
        fail(409, "attempt_closed")
    return profile, row


def _record_answers(stored: dict, answers: dict[str, object]) -> None:
    """Проверка и запись ответов на ещё не отвеченные вопросы попытки."""
    open_rows = {row["qid"]: row for row in assessment.pending(stored)}
    for qid, raw in answers.items():
        row = open_rows.get(qid)
        if row is None:
            fail(422, "answer_unknown")
        value = assessment.normalize_answer(row, raw)
        if value is None:
            fail(422, "answer_unknown")
        stored.setdefault("answers", {})[qid] = value


def _parse_answers(stored: dict, payload: object) -> dict[str, object]:
    """Ответы API: {"answers": {qid: [id…]}} или список по порядку открытых вопросов."""
    raw = payload.get("answers") if isinstance(payload, dict) else None
    open_rows = assessment.pending(stored)
    if isinstance(raw, list):
        if len(raw) != len(open_rows):
            fail(422, "answer_unknown")
        return {row["qid"]: value for row, value in zip(open_rows, raw)}
    if isinstance(raw, dict):
        if set(raw) != {row["qid"] for row in open_rows}:
            fail(422, "answer_unknown")
        return dict(raw)
    fail(422, "answer_unknown")
    return {}


def _close_stage(db: Session, profile: Profile, row: TestAttempt, stored: dict) -> dict:
    """Все вопросы этапа отвечены: либо доп. блок у границы, либо итог попытки."""
    previous = _previous_forms(db, profile, row.specialization, exclude_id=row.id)
    weights = None
    # п.3 плана: накопление. Учитываются ответы последних ACCUMULATE_LAST сданных
    # попыток этой специализации: цепочка «тест → ниже/выше» не начинает с нуля,
    # а давний провал не держит кандидата вечно (ТЗ §2: профиль актуален).
    answered = [form for form in previous if form.get("answers")]
    for form in answered[-ACCUMULATE_LAST:]:
        weights = assessment.update_weights(weights, form)
    weights = assessment.update_weights(weights, stored)
    boundary = assessment.disputed_boundary(weights, row.declared_grade)
    if boundary is not None and int(stored.get("blocks", 0)) < assessment.adaptive.MAX_EXTRA_BLOCKS:
        seen = assessment.history_from(previous + [stored])
        added = assessment.add_block(stored, row.specialization, row.declared_grade, boundary, seen, _exposure(db))
        if added:
            row.form_json = json.dumps(stored, ensure_ascii=False)
            db.commit()
            body = _public_attempt(row)
            body["status"] = "extra"
            return body
    outcome, proposed = assessment.decide(weights, row.declared_grade)
    overall = assessment.summary(weights)
    flags = [ok for _item, ok in assessment.correct_flags(stored)]
    result = {**overall, "n_items": len(flags), "blocks": int(stored.get("blocks", 0))}
    recorded = row.specialization == profile.specialization and row.declared_grade == profile.grade
    row.form_json = json.dumps(stored, ensure_ascii=False)
    row.answers_json = json.dumps(stored.get("answers") or {}, ensure_ascii=False)
    row.result_json = json.dumps(result, ensure_ascii=False)
    row.score = round(100 * sum(flags) / len(flags))
    row.outcome = outcome
    row.proposed_grade = proposed
    row.status = "submitted"
    row.submitted_at = utc_now()
    # Записанный грейд меняет только соседняя попытка с итогом confirm (ТЗ §2:
    # грейд не понижается принудительно, смена — через отдельный тест).
    if not recorded and outcome == "confirm":
        profile.grade = row.declared_grade
        profile.grade_changed_at = row.submitted_at
        profile.updated_at = row.submitted_at
    db.flush()
    recompute(db, profile.id)
    assignment = latest_assignment(db, profile.id)
    db.commit()
    return {
        "attempt_id": row.id,
        "status": "submitted",
        "score": row.score,
        "outcome": row.outcome,
        "proposed_grade": row.proposed_grade,
        "category_id": None if assignment is None else assignment.category_id,
        "grade": profile.grade,
        "confidence": result["confidence"],
        "test_status": result["status"],
        "position": result["position"],
        "n_items": result["n_items"],
    }


def submit_attempt(db: Session, user: User, attempt_id: int, payload: dict) -> dict:
    """Ответы на все открытые вопросы этапа сразу (API).

    Ответ ``status: "extra"`` — результат у границы грейдов, выданы ещё
    вопросы (до трёх блоков по 6); их сдают тем же методом.
    """
    profile, row = _own_draft(db, user, attempt_id)
    recorded = row.specialization == profile.specialization and row.declared_grade == profile.grade
    if not recorded and interval_blocks(db, profile, row.declared_grade):
        fail(409, "grade_interval", **interval_parts(profile, row.declared_grade))
    stored = _form(row)
    _record_answers(stored, _parse_answers(stored, payload))
    return _close_stage(db, profile, row, stored)


def answer_question(
    db: Session, user: User, attempt_id: int, qid: str, raw: object, marked: set[str] | None = None
) -> dict:
    """Ответ на один вопрос (кабинет: вопросы по одному, без возврата назад).

    ``marked`` — варианты, которые кандидат оценил (верно или неверно): в
    формате judge оценить нужно все три, иначе ответ не принимается.
    Ответ сохраняется сразу — обновление страницы не открывает уже отвеченный
    вопрос. Когда отвечен последний вопрос этапа, этап закрывается.
    """
    profile, row = _own_draft(db, user, attempt_id)
    stored = _form(row)
    if marked is not None:
        current = next((item for item in assessment.pending(stored) if item["qid"] == qid), None)
        if current is None or set(marked) != {opt["id"] for opt in current.get("options") or []}:
            fail(422, "answer_unknown")
    _record_answers(stored, {qid: raw})
    if assessment.pending(stored):
        row.form_json = json.dumps(stored, ensure_ascii=False)
        db.commit()
        body = _public_attempt(row)
        body["status"] = "draft"
        return body
    recorded = row.specialization == profile.specialization and row.declared_grade == profile.grade
    if not recorded and interval_blocks(db, profile, row.declared_grade):
        fail(409, "grade_interval", **interval_parts(profile, row.declared_grade))
    return _close_stage(db, profile, row, stored)
