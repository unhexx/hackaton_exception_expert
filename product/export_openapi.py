"""Пишет OpenAPI из приложения в stdout и рядом с пакетом, если каталог доступен.

ТЗ §3.4 «описание API»; ТЗ §3.5 «все методы описаны через OpenAPI».
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    from product.app.main import app

    text = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    target = Path(__file__).resolve().parent / "openapi.json"
    try:
        target.write_text(text, encoding="utf-8")
    except OSError:
        pass
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
