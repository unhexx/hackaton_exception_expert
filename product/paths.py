"""Пути внутри пакета.

После установки в образ `__file__` лежит в site-packages, поэтому корень
репозитория не вычисляем. Запасной файл базы — только если PRODUCT_SQLITE
не задана; на стенде переменная есть всегда.

ТЗ §3.1, §3.5: запуск на обычной машине, путь к базе задаётся переменной.
"""

from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parent


def sqlite_path() -> Path:
    raw = os.environ.get("PRODUCT_SQLITE")
    if raw:
        return Path(raw)
    return package_root() / "var" / "app.sqlite"
