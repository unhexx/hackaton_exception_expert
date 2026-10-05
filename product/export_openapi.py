"""Пишет OpenAPI из приложения в stdout и рядом с пакетом, если каталог доступен."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    if len(os.environ.get("PRODUCT_SECRET", "")) < 32:
        os.environ["PRODUCT_SECRET"] = "export-openapi-placeholder-secret-32"
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
