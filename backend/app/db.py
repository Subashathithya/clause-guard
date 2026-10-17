"""Vector store facade (backwards-compatible module).

Phase 3 split the store out of this module:
  * app/stores/store_protocol.py — the ``Store`` interface (swap-in seam)
  * app/stores/chroma_store.py    — the ChromaDB implementation

This module keeps the old module-level function names backed by a singleton
``ChromaStore``, so every existing call site (``from app import db`` /
``from app import db as vdb``) and test patch keeps working unchanged.
"""
import os
from functools import lru_cache

from app.stores.chroma_store import ChromaStore
from app.settings import settings as _settings

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

_store = ChromaStore(data_dir=DATA_DIR)

# Exposed for utility use; mirrors the original module-level helpers.
chunk_text = _store.chunk_text


def index_document(document_id: str, document_name: str, text: str) -> int:
    return _store.index_document(document_id, document_name, text)


def save_analysis(document_id: str, document_name: str, analysis: dict) -> None:
    _store.save_analysis(document_id, document_name, analysis)


def get_analysis(document_id: str) -> dict | None:
    return _store.get_analysis(document_id)


def get_document_text(document_id: str) -> str | None:
    return _store.get_document_text(document_id)


def get_documents() -> list[dict]:
    return _store.get_documents()


def delete_document(document_id: str) -> None:
    _store.delete_document(document_id)


def retrieve_context(question: str, document_ids: list[str] | None = None, top_k: int = 6) -> list[dict]:
    return _store.retrieve_context(question, document_ids, top_k)


def seed_fair_clauses(force: bool = False) -> int:
    return _store.seed_fair_clauses(force)


def collections_need_migration() -> list[str]:
    return _store.collections_need_migration()


def recreate_collections(names: list[str]) -> None:
    _store.recreate_collections(names)


def fair_clause_count() -> int:
    return _store.fair_clause_count()


def compare_to_standard(
    clause_text: str, category: str | None = None, top_k: int = 2
) -> dict:
    return _store.compare_to_standard(clause_text, category, top_k)


# --------------------------------------------------------------- optional infra
@lru_cache(maxsize=1)
def get_redis():
    """Return a Redis client or None if REDIS_URL is not configured."""
    if not _settings.REDIS_URL:
        return None
    try:
        import redis  # type: ignore

        client = redis.from_url(_settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def get_pg():
    """Return a PostgreSQL (Neon) connection factory or None when not configured.

    Since Phase 2 the default ``DATABASE_URL`` is local SQLite, so Postgres is
    only used when the URL explicitly uses the postgres scheme.
    """
    if not _settings.DATABASE_URL.startswith(("postgres://", "postgresql://")):
        return None
    try:
        import psycopg  # type: ignore

        return psycopg
    except Exception:  # noqa: BLE001
        return None