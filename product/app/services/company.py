"""Карточка компании. Регистрация и seed строку не создают."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.db.models import Company, User
from product.app.services.clock import utc_now
from product.app.services.errors import ApiError, explain

_LABELS = {
    "name": "название",
    "description": "описание",
    "direction": "направление",
    "contact": "контакт",
}

_FIELDS = ("name", "description", "direction", "contact")


def company_payload(row: Company) -> dict:
    return {
        "name": row.name,
        "description": row.description,
        "direction": row.direction,
        "contact": row.contact,
    }


def get_company(db: Session, user: User) -> dict:
    row = db.scalar(select(Company).where(Company.employer_id == user.id))
    if row is None:
        raise ApiError(404, "company_missing", explain("company_missing"))
    return company_payload(row)


def save_company(db: Session, user: User, payload: dict) -> dict:
    extra = set(payload) - set(_FIELDS)
    if extra:
        raise ApiError(422, "extra_forbidden", explain("extra_forbidden"))
    values: dict[str, str] = {}
    for key in _FIELDS:
        raw = payload.get(key)
        if not isinstance(raw, str):
            raise ApiError(422, key, explain("company_field", field=key, label=_LABELS[key]))
        values[key] = raw.strip()
    row = db.scalar(select(Company).where(Company.employer_id == user.id))
    now = utc_now()
    if row is None:
        row = Company(employer_id=user.id, updated_at=now, **values)
        db.add(row)
    else:
        row.name = values["name"]
        row.description = values["description"]
        row.direction = values["direction"]
        row.contact = values["contact"]
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return company_payload(row)
