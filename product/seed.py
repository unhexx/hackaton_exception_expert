"""Создаёт недостающие таблицы и вызывает пустую загрузку мока.

Повтор не удаляет строки тома. Нарушение уникального ключа пишется в журнал
и не останавливает процесс. Другая ошибка — останавливает.

ТЗ §3.3 «воспроизводимый запуск»: схема, догоняющие колонки и мок ФСП при старте.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from product.app.db.models import Base, User
from product.app.db.session import ensure_columns, get_engine, open_session
from product.app.log import log_event
from product.app.services.clock import utc_now
from product.app.services.passwords import hash_secret
from product.fsp_mock.load import load_into
from product.paths import sqlite_path

_DEMO_EMAIL = "demo@example.com"


def _maybe_demo(db) -> None:
    password = os.environ.get("PRODUCT_DEMO_PASSWORD", "")
    if not password:
        return
    exists = db.scalar(select(User.id).where(User.email == _DEMO_EMAIL))
    if exists is not None:
        return
    db.add(
        User(
            email=_DEMO_EMAIL,
            password_hash=hash_secret(password),
            role="candidate",
            email_verified=1,
            confirmation_code_hash=None,
            confirmation_expires_at=None,
            confirmation_attempts=0,
            consent_processing=0,
            consent_publication=0,
            created_at=utc_now(),
        )
    )


def init_db() -> None:
    previous = os.umask(0o077)
    try:
        path = sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(get_engine())
        ensure_columns(get_engine())  # том, созданный до появления колонок: добавить их
        db = open_session()
        try:
            load_into(db)
            _maybe_demo(db)
            db.commit()
        except IntegrityError:
            db.rollback()
            log_event("seed_unique", "unique")
        finally:
            db.close()
    finally:
        os.umask(previous)


def main() -> None:
    init_db()


if __name__ == "__main__":
    main()
