"""Целое из поля HTML-формы. Мусор остаётся строкой: сервис ответит 422, а не 500."""

from __future__ import annotations


def form_int(raw: str) -> int | str:
    """Один минус и цифры — int. Мусор, который int не читает, остаётся строкой."""
    text = raw.strip()
    body = text[1:] if text.startswith("-") else text
    if not body.isdigit():
        return raw
    try:
        return int(text)
    except ValueError:
        return raw
