"""Разбор текстового PDF. Словарь стека локальный, сеть и запись профиля здесь не живут."""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from product.matching.rules import load_rules

_LIMIT = 2 * 1024 * 1024
_SYNONYMS = Path(__file__).resolve().parent / "stack_synonyms.json"
_LABELS = {
    "фио": "full_name",
    "стек": "stack",
    "отрасль": "industry",
    "специализация": "specialization",
    "грейд": "grade",
    "роль": "team_role",
    "формат": "work_format",
    "стаж": "experience",
    "софт-скиллы": "soft_skills",
}


def _synonym_map() -> dict[str, str]:
    raw = json.loads(_SYNONYMS.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for canonical, aliases in raw.items():
        mapping[str(canonical).casefold()] = str(canonical)
        for alias in aliases:
            mapping[str(alias).casefold()] = str(canonical)
    return mapping


def _tokens(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def _from_list(value: str, allowed: list[str]) -> list[str]:
    folded = {item.casefold(): item for item in allowed}
    found: list[str] = []
    for token in _tokens(value):
        canonical = folded.get(token.casefold())
        if canonical and canonical not in found:
            found.append(canonical)
    return found


def _stack(value: str, allowed: list[str]) -> list[str]:
    synonyms = _synonym_map()
    folded = {item.casefold(): item for item in allowed}
    found: list[str] = []
    for token in _tokens(value):
        canonical = synonyms.get(token.casefold()) or folded.get(token.casefold())
        if canonical and canonical not in found:
            found.append(canonical)
    return found


def _one(value: str, allowed: list[str]) -> str | None:
    folded = {item.casefold(): item for item in allowed}
    return folded.get(value.casefold())


def _fields_from_text(text: str) -> dict:
    rules = load_rules()
    closed = {
        "industry": rules["industries"],
        "specialization": rules["specializations"],
        "grade": rules["grades"],
        "team_role": rules["team_roles"],
        "work_format": rules["work_formats"],
    }
    found: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = _LABELS.get(label.strip().casefold())
        value = value.strip()
        if key is None or not value:
            continue
        if key == "stack":
            items = _stack(value, rules["stack"])
            if items:
                found[key] = items
            continue
        if key == "soft_skills":
            items = _from_list(value, rules["soft_skills"])
            if items:
                found[key] = items
            continue
        options = closed.get(key)
        if options is not None:
            canonical = _one(value, options)
            if canonical:
                found[key] = canonical
            continue
        found[key] = value
    return found


def _text_layer(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts).strip()


def read_resume_bytes(data: bytes) -> dict:
    if len(data) > _LIMIT:
        return {"error": "resume_too_large"}
    if not data.startswith(b"%PDF"):
        return {"error": "resume_not_pdf"}
    try:
        text = _text_layer(data)
    except Exception:
        return {"error": "resume_not_pdf"}
    if not text:
        return {"error": "resume_no_text"}
    return _fields_from_text(text)
