"""Hermetic environment for the test suite.

All tests run against a throwaway ``CHROMA_DIR`` (a temp directory) and a
throwaway SQLite ``DATABASE_URL`` so the suite:

  * never touches the developer's live ``chroma_db/`` corpus, and
  * never sends real GROQ/LLM traffic (``GROQ_API_KEY`` is cleared; LLM stages
    are stubbed per-test with ``monkeypatch``).

The env must be set BEFORE ``app.settings`` is imported, because settings are
resolved once at import time.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make ``app`` importable no matter which directory pytest is invoked from.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_tmp = tempfile.mkdtemp(prefix="clasueguard_tests_")
os.environ["CHROMA_DIR"] = os.path.join(_tmp, "chroma")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "clauseguard.db").replace("\\", "/")
os.environ["GROQ_API_KEY"] = ""  # never make real LLM calls in tests
os.environ["AUTO_RECONCILE_VECTOR_STORE"] = "true"
# The sign-in rate limit is a production guard, not a test constraint: the
# test client shares one IP, so the default limit would leak between test
# files. The rate limiter's own test lowers the limit explicitly.
os.environ["AUTH_RATE_LIMIT"] = "1000"
os.environ["AUTH_RATE_WINDOW_SECONDS"] = "300"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Start every test with empty rate-limit buckets."""
    from app.core.ratelimit import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture()
def client():
    """FastAPI ``TestClient`` bound to the throwaway store + SQLite database.

    Entering the context manager runs the app's startup hook, so tables are
    created and the fair-clause library is seeded exactly as in production.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def app_client(client):
    """Alias used by the engine-correctness suite for the same TestClient."""
    return client


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


def _clause_lookup(clauses):
    """Deterministic by-clause_id lookup for the deterministic evidence check."""
    return {c.clause_id: c for c in clauses}
