"""Connection pool + idempotent schema migration."""
from __future__ import annotations

import atexit
from pathlib import Path
import threading

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "init.sql"

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def ensure_schema(database_url: str | None = None) -> None:
    """Apply db/init.sql. Safe to run repeatedly (all statements are IF NOT EXISTS)."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url or settings.database_url, autocommit=True) as conn:
        # Serialise concurrent starters (API workers + CLI) on the same DB.
        conn.execute("SELECT pg_advisory_lock(727401)")
        try:
            conn.execute(sql)
        finally:
            conn.execute("SELECT pg_advisory_unlock(727401)")


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)
    conn.row_factory = dict_row


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            ensure_schema()
            _pool = ConnectionPool(
                settings.database_url,
                min_size=1,
                max_size=10,
                configure=_configure,
                open=True,
            )
            atexit.register(close_pool)
    return _pool


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None
