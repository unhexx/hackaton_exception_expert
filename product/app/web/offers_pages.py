"""Страницы приглашения. Карточку компании этот модуль не пишет.

ТЗ §2.1 «Выход на контакт», «Просмотр приглашений»; ТЗ §2.2 п.1–3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.services.company import get_company
from product.app.services.errors import ApiError, hint as catalog_hint
from product.app.services.offers import (
    create_offer,
    get_offer,
    list_candidate_offers,
    list_employer_offers,
    open_offer,
    set_offer_status,
)
from product.app.web.forms import form_int
from product.app.web.guards import page_user, same_site_navigation
from product.app.web.render import assert_csrf, ensure_csrf, page_error, render

router = APIRouter()


def _candidate_context(request: Request, db: Session, user, error: str = "") -> dict:
    offers = list_candidate_offers(db, user)
    return {
        "csrf": ensure_csrf(request),
        "error": error,
        "hint": "" if offers else catalog_hint("hint_no_invites_candidate"),
        "user": user,
        "offers": offers,
    }


def _employer_context(
    request: Request,
    db: Session,
    user,
    error: str = "",
    *,
    profile_id: str = "",
    category_id: str = "",
) -> dict:
    company = None
    try:
        company = get_company(db, user)
    except ApiError:
        company = None
    prefill_profile = profile_id or (request.query_params.get("profile_id") or "").strip()
    prefill_category = category_id or (request.query_params.get("category_id") or "").strip()
    name = "" if company is None else str(company.get("name") or "")
    contact = "" if company is None else str(company.get("contact") or "")
    hint = "" if name.strip() and contact.strip() else catalog_hint("hint_offer_form")
    return {
        "csrf": ensure_csrf(request),
        "error": error,
        "hint": hint,
        "user": user,
        "company": company,
        "offers": list_employer_offers(db, user),
        "prefill_profile_id": prefill_profile,
        "prefill_category_id": prefill_category,
    }


@router.get("/candidate/offers")
def candidate_offers(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    return render(request, "candidate/offers.html", _candidate_context(request, db, user))


@router.get("/candidate/offers/{offer_id}")
def candidate_offer(offer_id: int, request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    try:
        if same_site_navigation(request):
            open_offer(db, user, offer_id)
        else:
            get_offer(db, user, offer_id)
    except ApiError as exc:
        return page_error(request, "candidate/offers.html", _candidate_context(request, db, user), exc)
    return render(request, "candidate/offers.html", _candidate_context(request, db, user))


@router.post("/candidate/offers/{offer_id}/accept")
def accept_page(
    offer_id: int,
    request: Request,
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    try:
        assert_csrf(request, csrf)
        set_offer_status(db, user, offer_id, "accepted")
    except ApiError as exc:
        return page_error(request, "candidate/offers.html", _candidate_context(request, db, user), exc)
    return RedirectResponse("/candidate/offers", status_code=303)


@router.post("/candidate/offers/{offer_id}/decline")
def decline_page(
    offer_id: int,
    request: Request,
    csrf: str = Form(""),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    try:
        assert_csrf(request, csrf)
        set_offer_status(db, user, offer_id, "declined")
    except ApiError as exc:
        return page_error(request, "candidate/offers.html", _candidate_context(request, db, user), exc)
    return RedirectResponse("/candidate/offers", status_code=303)


@router.get("/employer/offers")
def employer_offers(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    return render(request, "employer/offer.html", _employer_context(request, db, user))


@router.post("/employer/offers")
def send_page(
    request: Request,
    csrf: str = Form(""),
    profile_id: str = Form(""),
    category_id: str = Form(""),
    company_name: str = Form(""),
    contact_channel: str = Form(""),
    message: str = Form(""),
    salary_min: str = Form(""),
    salary_max: str = Form(""),
    salary_currency: str = Form("RUB"),
    db: Session = Depends(db_session),
):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    payload = {
        "profile_id": form_int(profile_id),
        "category_id": category_id,
        "company_name": company_name,
        "contact_channel": contact_channel,
        "message": message,
        "salary_min": form_int(salary_min),
        "salary_max": form_int(salary_max),
        "salary_currency": salary_currency,
    }
    try:
        assert_csrf(request, csrf)
        create_offer(db, user, payload)
    except ApiError as exc:
        return page_error(
            request,
            "employer/offer.html",
            _employer_context(
                request,
                db,
                user,
                profile_id=str(profile_id or "").strip(),
                category_id=str(category_id or "").strip(),
            ),
            exc,
        )
    return RedirectResponse("/employer/offers", status_code=303)
