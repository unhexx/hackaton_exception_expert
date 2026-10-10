"""Чтение замороженных правил v1. Файл рядом с модулем, не из корня репозитория.

ТЗ §2 «Справочник специализаций и грейдов команда составляет самостоятельно»; интервал смены грейда.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent / "rules" / "v1.json"


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def rule_version() -> str:
    return str(load_rules()["rule_version"])
