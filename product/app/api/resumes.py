"""Загрузка резюме и PDF профиля."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import User
from product.app.services.resumes import apply_resume, profile_pdf

router = APIRouter(tags=["resume"])

_STORED = {
    "profile_id": 1,
    "full_name": "Анна Синтетикова",
    "industry": "it",
    "specialization": "backend",
    "grade": "senior",
    "category_id": "backend:middle",
    "field_sources": {"full_name": "resume", "grade": "resume"},
    "grade_skipped": False,
}
_NO_TEXT = {
    "error": "resume_no_text",
    "message": "В PDF нет текстового слоя. Скан без текста не читается, заполните поля вручную.",
}
_LARGE = {"error": "resume_too_large", "message": "Файл больше 2 МиБ"}
_NOT_PDF = {"error": "resume_not_pdf", "message": "Файл не похож на PDF"}
_MISSING = {"error": "not_found", "message": "Анкета ещё не заполнена"}
_DENIED = {"error": "unauthorized", "message": "Нужен вход"}
_FORBIDDEN = {"error": "forbidden", "message": "Это кабинет соискателя"}


@router.post(
    "/candidate/resume",
    responses={
        200: {"content": {"application/json": {"example": _STORED}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": _FORBIDDEN}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
        413: {"content": {"application/json": {"example": _LARGE}}},
        422: {"content": {"application/json": {"example": _NO_TEXT}}},
    },
)
async def upload_resume(
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    form = await request.form()
    uploaded = form.get("file")
    if uploaded is None or isinstance(uploaded, str):
        return apply_resume(db, user, b"")
    data = await uploaded.read()
    return apply_resume(db, user, data)


@router.get(
    "/candidate/profile.pdf",
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": _FORBIDDEN}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
    },
)
def download_profile(user: User = Depends(require_candidate), db: Session = Depends(db_session)):
    payload = profile_pdf(db, user)
    return Response(content=payload, media_type="application/pdf")
