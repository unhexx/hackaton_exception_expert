"""Ошибка API с машинным кодом. Текст на русском тесты не сверяют."""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str) -> None:
        self.status = status
        self.error = error
        self.message = message
        super().__init__(message)
