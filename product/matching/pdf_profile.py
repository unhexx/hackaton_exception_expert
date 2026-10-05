"""PDF кабинета. Отрасль стоит рядом с категорией, не внутри её имени."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT = Path(__file__).resolve().parents[1] / "static" / "fonts" / "JetBrainsMono-Regular.ttf"
_FONT_NAME = "JetBrainsMono"


def _ensure_font() -> None:
    if _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT)))


def render_profile_pdf(fields: dict) -> bytes:
    _ensure_font()
    category = str(fields.get("category_id") or "ещё нет")
    stack = ", ".join(fields.get("stack") or [])
    soft = ", ".join(fields.get("soft_skills") or [])
    lines = [
        f"ФИО: {fields.get('full_name') or ''}",
        f"Отрасль: {fields.get('industry') or ''}",
        f"Категория: {category}",
        f"Специализация: {fields.get('specialization') or ''}",
        f"Грейд: {fields.get('grade') or ''}",
        f"Стек: {stack}",
        f"Роль: {fields.get('team_role') or ''}",
        f"Формат: {fields.get('work_format') or ''}",
        f"Стаж: {fields.get('experience') or ''}",
        f"Софт-скиллы: {soft}",
    ]
    buffer = BytesIO()
    sheet = canvas.Canvas(buffer)
    sheet.setFont(_FONT_NAME, 11)
    top = 800
    for index, line in enumerate(lines):
        sheet.drawString(40, top - index * 18, line)
    sheet.save()
    return buffer.getvalue()
