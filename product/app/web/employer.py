"""Кабинет работодателя и форма карточки компании.

ТЗ §2.1 «Личный кабинет Работодатель».
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.db.models import Company, Offer
from product.app.services.company import save_company
from product.app.services.errors import ApiError, hint as catalog_hint
from product.app.web.guards import page_user
from product.app.web.render import assert_csrf, ensure_csrf, page_error, render

router = APIRouter()


def _context(request: Request, db: Session, user, error: str = "") -> dict:
    company = db.scalar(select(Company).where(Company.employer_id == user.id))
    has_offers = db.scalar(select(Offer.id).where(Offer.employer_id == user.id)) is not None
    if company is None or not company.name or not company.contact:
        hint = catalog_hint("company_missing")
    elif not has_offers:
        hint = catalog_hint("hint_no_invites_employer")
    else:
        hint = ""
    return {
        "csrf": ensure_csrf(request),
        "error": error,
        "hint": hint,
        "user": user,
        "company": company,
        "has_offers": has_offers,
    }


@router.get("/employer")
def cabinet(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    return render(request, "employer/cabinet.html", _context(request, db, user))


@router.post("/employer/company")
def save_card(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    direction: str = Form(""),
    contact: str = Form(""),
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    try:
        assert_csrf(request, csrf)
        save_company(
            db,
            user,
            {
                "name": name,
                "description": description,
                "direction": direction,
                "contact": contact,
            },
        )
    except ApiError as exc:
        return page_error(request, "employer/cabinet.html", _context(request, db, user), exc)
    return RedirectResponse("/employer", status_code=303)
