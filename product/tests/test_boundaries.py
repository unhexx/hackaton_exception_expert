"""Границы каркаса: схема, секрет, мок и отсутствие обвязки."""

from __future__ import annotations

import ast
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import product
from product.fsp_mock.client import JsonFspClient
from product.matching.rules import load_rules


def test_schema_matches_rules_and_wal(client):
    rules = load_rules()
    assert rules["rule_version"] == "v1"
    assert rules["grade_change_interval_days"] == 90
    assert rules["grades"] == ["junior", "middle", "senior", "lead"]
    assert rules["industries"] == ["it"]
    with sqlite3.connect(client.db_path) as db:
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        names = {row[0] for row in db.execute("select name from sqlite_master where type = 'table'")}
        profile_sql = db.execute(
            "select sql from sqlite_master where name = 'profiles'"
        ).fetchone()[0]
        offer_sql = db.execute(
            "select sql from sqlite_master where name = 'offers'"
        ).fetchone()[0]
        participants = db.execute("select count(*) from fsp_participants").fetchone()[0]
        achievements = db.execute("select count(*) from fsp_achievements").fetchone()[0]
    assert mode.lower() == "wal"
    assert {
        "users",
        "companies",
        "profiles",
        "consents",
        "survey_attempts",
        "test_attempts",
        "category_assignments",
        "offers",
        "fsp_participants",
        "fsp_achievements",
    } <= names
    for item in rules["specializations"] + rules["grades"] + rules["work_formats"] + rules["industries"]:
        assert item in profile_sql
    assert "salary_currency = 'RUB'" in offer_sql
    assert "salary_max > salary_min" in offer_sql
    people = JsonFspClient().list_participants()
    assert participants == len(people)
    assert participants >= 3
    assert achievements == sum(len(person["results"]) for person in people)


def test_pages_and_docs_do_not_need_network(client):
    css = client.get("/static/brand.css")
    assert css.status_code == 200
    assert "--fsp-blue: #402FFF" in css.text
    assert "tailwind" not in css.text.lower()
    script = client.get("/static/htmx.min.js")
    assert script.status_code == 200
    assert "htmx" in script.text
    fonts = client.get("/fonts/README")
    assert fonts.status_code == 200
    docs = client.get("/docs")
    assert docs.status_code == 503
    assert docs.json()["error"] == "docs_assets"
    redoc = client.get("/redoc")
    assert redoc.status_code == 503
    assert redoc.json()["error"] == "docs_assets"


def test_product_does_not_import_memory():
    root = Path(product.__file__).resolve().parent
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name.split(".")[0] == "memory" for name in names):
                offenders.append(str(path))
    assert offenders == []


def test_short_secret_does_not_start():
    env = {key: value for key, value in os.environ.items() if key != "PRODUCT_SECRET"}
    env["PRODUCT_SECRET"] = "short"
    env["PYTHONPATH"] = str(Path(product.__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", "import product.app.main"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "PRODUCT_SECRET" in (proc.stderr + proc.stdout)
