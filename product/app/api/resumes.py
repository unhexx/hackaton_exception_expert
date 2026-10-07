"""Загрузка резюме и PDF профиля."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, require_candidate
from product.app.db.models import User
from product.app.services.errors import example, response_example
from product.app.services.resumes import apply_resume, profile_pdf
from product.matching.resume import _LIMIT

# Запас на границы multipart и поле csrf. Сам файл длиннее _LIMIT сюда не входит.
_BODY_SLACK = 64 * 1024

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
_NO_TEXT = example("resume_no_text")
_LARGE = example("resume_too_large")
_NOT_PDF = example("resume_not_pdf")
_MISSING = example("not_found", "not_found_profile")
_DENIED = example("unauthorized")
_FORBIDDEN = example("forbidden", "forbidden_candidate")


async def read_resume_upload(request: Request) -> tuple[bytes, str, bool]:
    """Байты файла, csrf и флаг обрыва. Хвост тела длиннее предела не читается."""
    content_type = request.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().casefold() != "multipart/form-data":
        return b"", "", False
    cap = _LIMIT + _BODY_SLACK
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        room = cap + 1 - total
        if len(chunk) > room:
            return b"", "", True
        chunks.append(chunk)
        total += len(chunk)
        if total > cap:
            return b"", "", True
    # form() снова идёт в stream(); отдаём ему уже собранное тело, не сокет.
    request._body = b"".join(chunks)
    request._stream_consumed = False
    form = await request.form()
    uploaded = form.get("file")
    csrf_raw = form.get("csrf")
    csrf = csrf_raw if isinstance(csrf_raw, str) else ""
    if uploaded is None or isinstance(uploaded, str):
        return b"", csrf, False
    return await uploaded.read(_LIMIT + 1), csrf, False


@router.post(
    "/candidate/resume",
    responses={
        200: {"content": {"application/json": {"example": _STORED}}},
        401: {"content": {"application/json": {"example": _DENIED}}},
        403: {"content": {"application/json": {"example": _FORBIDDEN}}},
        404: {"content": {"application/json": {"example": _MISSING}}},
        413: response_example(413, _LARGE),
        422: response_example(422, _NO_TEXT),
    },
)
async def upload_resume(
    request: Request,
    user: User = Depends(require_candidate),
    db: Session = Depends(db_session),
):
    data, _csrf, stopped = await read_resume_upload(request)
    return apply_resume(db, user, data, too_large=stopped)


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
