"""Один процесс, одно соединение на запрос, журнал WAL.

NullPool не держит соединение между запросами. timeout и busy_timeout
совпадают и не короче пяти секунд.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from product.paths import sqlite_path

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def reset_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        path = sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{path}",
            poolclass=NullPool,
            connect_args={"check_same_thread": False, "timeout": 5.0},
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _connection_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        _engine = engine
        _factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return _engine


def open_session() -> Session:
    get_engine()
    assert _factory is not None
    return _factory()


def session_scope() -> Iterator[Session]:
    db = open_session()
    try:
        yield db
    finally:
        db.close()
