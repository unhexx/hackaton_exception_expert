"""Коммитируемый OpenAPI совпадает со схемой приложения.

ТЗ §3.5 «API: все методы описаны через спецификацию OpenAPI».
"""

from __future__ import annotations

import json
from pathlib import Path

import product
from product.app.main import app


def test_committed_openapi_matches_app():
    path = Path(product.__file__).resolve().parent / "openapi.json"
    assert path.is_file(), "нет product/openapi.json"
    committed = json.loads(path.read_text(encoding="utf-8"))
    app.openapi_schema = None
    assert committed == app.openapi()


def test_routes_have_error_examples():
    app.openapi_schema = None
    spec = app.openapi()
    assert spec["components"]["securitySchemes"]["product_session"]["name"] == "product_session"
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "delete"}:
                continue
            codes = [int(code) for code in operation.get("responses", {}) if code.isdigit()]
            assert any(code >= 400 for code in codes), path
            body = operation.get("requestBody")
            if method in {"post", "put"} and body:
                content = body.get("content", {}).get("application/json", {})
                schema = content.get("schema") or {}
                assert content.get("example") or content.get("examples") or schema.get("examples"), path
