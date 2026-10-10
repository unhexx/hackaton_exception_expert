"""Один контур секрета сессии: переменная или файл, без молчаливой подстановки.

ТЗ §3.5 «Безопасность: безопасное хранение паролей и токенов».
"""

from __future__ import annotations

import os
from pathlib import Path

_SECRET_MIN = 32


def product_secret() -> str:
    secret = os.environ.get("PRODUCT_SECRET", "")
    if len(secret) >= _SECRET_MIN:
        return secret
    path = os.environ.get("PRODUCT_SECRET_FILE", "").strip()
    if path:
        try:
            secret = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            secret = ""
    if len(secret) < _SECRET_MIN:
        raise RuntimeError("PRODUCT_SECRET короче 32 символов")
    return secret
