"""Короткий журнал в stdout. Пароль, код, хэш, cookie и секрет сюда не попадают."""

from __future__ import annotations

from datetime import datetime, timezone


def log_event(event: str, reason: str | None = None, level: str = "INFO") -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if reason:
        print(f"{stamp} {level} {event} {reason}", flush=True)
    else:
        print(f"{stamp} {level} {event}", flush=True)
