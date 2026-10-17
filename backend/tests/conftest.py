"""Hermetic environment for the engine test suite.

All tests run against a throwaway ``CHROMA_DIR`` (a temp directory) and a
throwaway SQLite ``DATABASE_URL`` so the suite:

  * never touches the developer's live ``chroma_db/`` corpus, and
  * never sends real GROQ/LLM traffic (``GROQ_API_KEY`` is cleared; LLM stages
    are stubbed per-test with ``monkeypatch``).

The env must be set BEFORE ``app.settings`` is imported, because settings are
resolved once at import time.
"""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="clasueguard_tests_")
os.environ["CHROMA_DIR"] = os.path.join(_tmp, "chroma")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "clauseguard.db").replace("\\", "/")
os.environ["GROQ_API_KEY"] = ""  # never make real LLM calls in tests
os.environ["AUTO_RECONCILE_VECTOR_STORE"] = "true"


@pytest.fixture()
def vector_store():
    """A fresh, empty vector store on the temporarily-scoped metric.

    The store is created on a temp dir (never the live corpus). Because the
    suite runs with AUTO_RECONCILE_VECTOR_STORE=true, any collection that is
    not on the cosine metric is recreated (migration) and the fair-clause
    library is re-seeded before use — mirroring the app's real startup path.
    """
    from app.stores.chroma_store import ChromaStore

    store = ChromaStore()
    store.ensure_collections()          # create if missing (cosine space)
    store.reconcile_vector_store()      # <-- this is the startup hook under test
    store.seed_fair_clauses(force=True)
    yield store
    store.drop_collections()

_lookup_snip = None  # placeholder


def _clause_lookup(clauses):
    """Deterministic by-clause_id lookup for the deterministic evidence check."""
    return {c.clause_id: c for c in clauses}
