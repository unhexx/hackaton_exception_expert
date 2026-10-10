"""Приглашение из категории. Почта соискателя в строку не копируется.

ТЗ §2 — главная механика: работодатель сам выходит на кандидата; ТЗ §2.2 п.1–3.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product.app.db.models import Offer, User
from product.app.db.session import sqlite_int
from product.app.log import log_event
from product.app.services.categories import visible_in_category
from product.app.services.clock import utc_now
from product.app.services.company import posted_company
from product.app.services.errors import fail
from product.app.services.fork import parse_fork
from product.app.services.profile_ref import candidate_email, own_profile_id

_FIELDS = {
    "profile_id",
    "category_id",
    "company_name",
    "message",
    "salary_min",
    "salary_max",
    "salary_currency",
    "contact_channel",
}


def _fail(status: int, code: str, key: str | None = None, **parts: object) -> None:
    log_event("offer_rejected", code)
    fail(status, code, key, **parts)


def offer_payload(db: Session, row: Offer, *, viewer: str) -> dict:
    body = {
        "id": row.id,
        "profile_id": row.profile_id,
        "category_id": row.category_id,
        "company_name": row.company_name,
        "message": row.message,
        "salary_min": row.salary_min,
        "salary_max": row.salary_max,
        "salary_currency": row.salary_currency,
        "contact_channel": row.contact_channel,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    # ТЗ §2.2 п.2: почта кандидата раскрывается работодателю только после «принято».
    if viewer == "employer" and row.status == "accepted":
        body["candidate_email"] = candidate_email(db, row.profile_id)
    return body


def list_candidate_offers(db: Session, user: User) -> list[dict]:
    profile_id = own_profile_id(db, user)
    if profile_id is None:
        return []
    rows = db.scalars(
        select(Offer).where(Offer.profile_id == profile_id).order_by(Offer.id.desc())
    ).all()
    return [offer_payload(db, row, viewer="candidate") for row in rows]


def list_employer_offers(db: Session, user: User) -> list[dict]:
    rows = db.scalars(
        select(Offer).where(Offer.employer_id == user.id).order_by(Offer.id.desc())
    ).all()
    return [offer_payload(db, row, viewer="employer") for row in rows]


def _candidate_offer(db: Session, user: User, offer_id: int) -> Offer:
    profile_id = own_profile_id(db, user)
    row = db.get(Offer, offer_id) if sqlite_int(offer_id) is not None else None
    if row is None or profile_id is None or row.profile_id != profile_id:
        fail(404, "not_found", "not_found_offer")
    return row


def create_offer(db: Session, user: User, payload: dict) -> dict:
    extra = set(payload) - _FIELDS
    if extra:
        _fail(422, "extra_forbidden")
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        _fail(422, "offer_incomplete", "offer_incomplete_message")
    # ТЗ §2.2 п.1: вилка «от–до» в рублях обязательна в каждом приглашении.
    salary_min, salary_max = parse_fork(payload.get("salary_min"), payload.get("salary_max"), _fail)
    if payload.get("salary_currency") != "RUB":
        _fail(422, "currency")
    company = posted_company(db, user, payload, _fail)
    profile_id = payload.get("profile_id")
    if isinstance(profile_id, bool) or not isinstance(profile_id, int):
        _fail(422, "offer_incomplete", "offer_incomplete_profile")
    category_id = payload.get("category_id")
    if not isinstance(category_id, str):
        _fail(422, "category_id")
    if not visible_in_category(db, profile_id, category_id):
        _fail(404, "profile_not_in_category")
    opened = db.scalar(
        select(Offer).where(
            Offer.employer_id == user.id,
            Offer.profile_id == profile_id,
            Offer.status.in_(("sent", "seen")),
        )
    )
    if opened is not None:
        _fail(409, "offer_open")
    now = utc_now()
    row = Offer(
        employer_id=user.id,
        profile_id=profile_id,
        category_id=category_id,
        company_name=company.name,
        message=message.strip(),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="RUB",
        contact_channel=company.contact,
        vacancy_id=None,
        status="sent",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _fail(409, "offer_open")
    db.refresh(row)
    return offer_payload(db, row, viewer="employer")


def get_offer(db: Session, user: User, offer_id: int) -> dict:
    row = _candidate_offer(db, user, offer_id)
    return offer_payload(db, row, viewer="candidate")


def open_offer(db: Session, user: User, offer_id: int) -> dict:
    # ТЗ §2.2 п.3: статусы отражают ход взаимодействия — открытие переводит sent → seen.
    row = _candidate_offer(db, user, offer_id)
    if row.status == "sent":
        now = utc_now()
        result = db.execute(
            update(Offer)
            .where(Offer.id == row.id, Offer.status == "sent")
            .values(status="seen", updated_at=now)
        )
        db.commit()
        db.refresh(row)
        if result.rowcount:
            log_event("offer_status", "seen")
    return offer_payload(db, row, viewer="candidate")


def set_offer_status(db: Session, user: User, offer_id: int, status: str) -> dict:
    # ТЗ §2.1 «принять или отклонить». Условный UPDATE по текущему статусу:
    # два одновременных ответа не перезапишут друг друга.
    row = _candidate_offer(db, user, offer_id)
    now = utc_now()
    result = db.execute(
        update(Offer)
        .where(Offer.id == row.id, Offer.status.in_(("sent", "seen")))
        .values(status=status, updated_at=now)
    )
    db.commit()
    db.refresh(row)
    if result.rowcount == 0:
        _fail(409, "offer_closed")
    log_event("offer_status", status)
    return offer_payload(db, row, viewer="candidate")
