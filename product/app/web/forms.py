"""Целое из поля HTML-формы. Мусор остаётся строкой: сервис ответит 422, а не 500."""

from __future__ import annotations


def form_int(raw: str) -> int | str:
    """Один минус и цифры — int. Двойной минус, плюс и пусто не бросают ValueError."""
    text = raw.strip()
    if text.startswith("-"):
        digits = text[1:]
        if digits.isdigit():
            return int(text)
        return raw
    if text.isdigit():
        return int(text)
    return raw
