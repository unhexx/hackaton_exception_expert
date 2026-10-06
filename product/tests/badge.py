"""Пишет бейдж последнего прогона pytest в docs/badges."""

from __future__ import annotations

import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "docs" / "badges"


def badge_dir() -> Path:
    raw = os.environ.get("PRODUCT_BADGE_DIR", "").strip()
    return Path(raw) if raw else _DEFAULT_DIR


def write_session_badge(session, exitstatus: int) -> None:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        passed = failed = skipped = 0
    else:
        passed = len(reporter.stats.get("passed", []))
        failed = len(reporter.stats.get("failed", [])) + len(reporter.stats.get("error", []))
        skipped = len(reporter.stats.get("skipped", []))
    if exitstatus != 0 and failed == 0:
        failed = max(failed, 1)
    target = badge_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    svg_path = target / "tests.svg"
    json_path = target / "tests.json"
    try:
        svg_path.write_text(render_svg(passed, failed, skipped), encoding="utf-8")
        json_path.write_text(render_json(passed, failed, skipped), encoding="utf-8")
        json_path.chmod(0o644)
        svg_path.chmod(0o644)
    except OSError:
        return


def render_json(passed: int, failed: int, skipped: int) -> str:
    payload = {
        "schemaVersion": 1,
        "label": "tests",
        "message": _message(passed, failed, skipped),
        "color": "red" if failed else "brightgreen",
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


def render_svg(passed: int, failed: int, skipped: int) -> str:
    label = "tests"
    message = _message(passed, failed, skipped)
    color = "#e05d44" if failed else "#4c1"
    label_w = _width(label)
    message_w = _width(message)
    total = label_w + message_w
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" '
        f'aria-label="{escape(label)}: {escape(message)}">\n'
        f'  <title>{escape(label)}: {escape(message)}</title>\n'
        f'  <linearGradient id="s" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        f'    <stop offset="1" stop-opacity=".1"/>\n'
        f'  </linearGradient>\n'
        f'  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>\n'
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{label_w}" height="20" fill="#555"/>\n'
        f'    <rect x="{label_w}" width="{message_w}" height="20" fill="{color}"/>\n'
        f'    <rect width="{total}" height="20" fill="url(#s)"/>\n'
        f'  </g>\n'
        f'  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="11">\n'
        f'    <text x="{label_w / 2}" y="15" fill="#010101" fill-opacity=".3">{escape(label)}</text>\n'
        f'    <text x="{label_w / 2}" y="14">{escape(label)}</text>\n'
        f'    <text x="{label_w + message_w / 2}" y="15" fill="#010101" fill-opacity=".3">{escape(message)}</text>\n'
        f'    <text x="{label_w + message_w / 2}" y="14">{escape(message)}</text>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _message(passed: int, failed: int, skipped: int) -> str:
    if failed:
        return f"{failed} failed"
    text = f"{passed} passed"
    if skipped:
        text += f" {skipped} skipped"
    return text


def _width(text: str) -> int:
    return max(20, 6 * len(text) + 12)
