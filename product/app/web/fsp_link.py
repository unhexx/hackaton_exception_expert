"""Связь уже вошедшего соискателя с ID участника. Учётку из токена не создаёт."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.db.models import Profile
from product.app.services import oidc
from product.app.services.categories import recompute
from product.app.services.errors import explain
from product.app.web.guards import page_user

router = APIRouter()

_STATE_KEY = "fsp_state"
_VERIFIER_KEY = "fsp_verifier"


def _back(request: Request, text: str) -> RedirectResponse:
    request.session["link_error"] = text
    return RedirectResponse("/candidate", status_code=302)


def _same(expected: object, sent: str) -> bool:
    if not isinstance(expected, str) or expected == "" or len(expected) != len(sent):
        return False
    return secrets.compare_digest(expected, sent)


@router.get("/auth/fsp/start", include_in_schema=False)
def start_link(request: Request, db: Session = Depends(db_session)):
    _user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    started = oidc.begin_link()
    request.session[_STATE_KEY] = started["state"]
    request.session[_VERIFIER_KEY] = started["code_verifier"]
    return RedirectResponse(started["url"], status_code=302)


@router.get("/auth/fsp/callback", include_in_schema=False)
def finish_link(
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(db_session),
):
    """Сверяет state, стирает его и только потом меняет код. Строку профиля не вставляет."""
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    expected = request.session.pop(_STATE_KEY, None)
    verifier = request.session.pop(_VERIFIER_KEY, None)
    if not _same(expected, state) or not isinstance(verifier, str) or verifier == "":
        return _back(request, "Запрос связи не совпал. Откройте связь ещё раз из кабинета.")
    try:
        claims = oidc.exchange(code, verifier)
    except oidc.OidcError as exc:
        return _back(request, str(exc))
    external_id = oidc.external_id_from_claims(claims)
    if external_id is None:
        return _back(request, "В токене нет годного идентификатора участника.")
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        return _back(request, "Сначала сохраните анкету")
    profile.external_id = external_id
    try:
        recompute(db, profile.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        return _back(request, explain("external_id_taken"))
    request.session["link_hint"] = "ID участника записан"
    return RedirectResponse("/candidate", status_code=302)
