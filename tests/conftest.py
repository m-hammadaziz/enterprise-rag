"""Test configuration.

Unit tests need nothing. Integration tests (marked ``integration``) need the
Postgres from docker compose; they are skipped automatically if it is not
reachable. They force the offline backends so no model download or API key is
needed, and they run against a SEPARATE database (``<your db>_test``) so the
offline test vectors never overwrite the real data your API uses.
"""
import os

os.environ["EMBED_BACKEND"] = "hash"
os.environ["RERANK_BACKEND"] = "lexical"
os.environ["GROQ_API_KEY"] = ""  # offline unless a test opts in with a mocked LLM

from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql
import pytest

from app.config import settings

settings.embed_backend = "hash"
settings.rerank_backend = "lexical"
settings.groq_api_key = ""


def _test_db_url(url: str) -> str:
    parts = urlsplit(url)
    name = parts.path.lstrip("/") or "rag"
    if not name.endswith("_test"):
        name += "_test"
    return urlunsplit(parts._replace(path="/" + name))


def _prepare_test_db() -> bool:
    """Create <db>_test next to the real database if it does not exist yet."""
    test_url = _test_db_url(settings.database_url)
    test_name = urlsplit(test_url).path.lstrip("/")
    try:
        with psycopg.connect(settings.database_url, connect_timeout=2, autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_name,)).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_name)))
    except Exception:
        return False
    settings.database_url = test_url
    os.environ["DATABASE_URL"] = test_url
    return True


DB_OK = _prepare_test_db()


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs a running Postgres+pgvector")


def pytest_collection_modifyitems(config, items):
    if DB_OK:
        return
    skip = pytest.mark.skip(reason="Postgres not reachable (start it with: docker compose up -d db)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def corpus():
    """Ingest the sample corpus + demo users once per session (idempotent)."""
    from pathlib import Path

    from app.ingest.pipeline import ingest_manifest
    from scripts.seed_users import main as seed

    root = Path(__file__).resolve().parent.parent
    ingest_manifest(root / "data" / "sample" / "manifest.json")
    seed([])
    return True
