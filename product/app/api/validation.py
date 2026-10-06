"""Один запуск прогона на стенде. Ответ — пять строк, без порога."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from product.app.api.deps import current_user
from product.app.services.errors import example
from product.app.db.models import User
from product.matching.golden_run import render_report

router = APIRouter(tags=["validation"])

_SAMPLE = (
    "category_match 0 0\n"
    "outcome_match 0 0\n"
    "template_stable 0 0\n"
    "relevant_in_top 0 0\n"
    "resume_ok 0 0\n"
)


@router.get(
    "/validation",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/plain": {"example": _SAMPLE}}},
        401: {"content": {"application/json": {"example": example("unauthorized")}}},
    },
)
def validation_report(_user: User = Depends(current_user)):
    return PlainTextResponse(render_report(), media_type="text/plain; charset=utf-8")
