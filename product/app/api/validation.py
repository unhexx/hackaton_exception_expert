"""Один запуск прогона на стенде. Пять строк, grade_separation и три CPU-персоны, без порога.

ТЗ §2 и §3.4: «собственная процедура валидации решения и её результаты».
Строки описаны в ``product/matching/golden_run.py``; подробная симуляция теста
на 500 кандидатах — ``product/validation_sim`` (отчёт out/report.md).
"""

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
    "form_stable 0 0\n"
    "relevant_in_top 0 0\n"
    "resume_ok 0 0\n"
    "grade_separation 0 0\n"
    "sim_competent 0 0\n"
    "sim_key_leak 0 0\n"
    "sim_adjacent 0 0\n"
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
