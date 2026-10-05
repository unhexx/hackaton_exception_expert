"""Метки времени строкой ISO-8601 в UTC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_after(minutes: int) -> str:
    moment = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_past(stamp: str | None) -> bool:
    if not stamp:
        return True
    text = stamp.replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment <= datetime.now(timezone.utc)
