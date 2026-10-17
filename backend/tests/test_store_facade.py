"""Phase 3: vector-store facade + protocol compatibility checks.

Guards the seam introduced by the store split: existing call sites use
`app.db.<fn>` and MUST keep working, and the Chroma implementation MUST satisfy
the `Store` protocol so a pgvector implementation could be swapped in later.
"""
from app import db
from app.stores.chroma_store import ChromaStore
from app.stores.store_protocol import Store

FACADE_FUNCTIONS = (
    "index_document",
    "save_analysis",
    "get_analysis",
    "get_document_text",
    "get_documents",
    "delete_document",
    "retrieve_context",
    "seed_fair_clauses",
    "fair_clause_count",
    "compare_to_standard",
    "chunk_text",
)


def test_facade_exposes_store_functions():
    for name in FACADE_FUNCTIONS:
        assert callable(getattr(db, name, None)), f"app.db.{name} missing"
    assert db.DATA_DIR  # knowledge.py reads db.DATA_DIR for the json path


def test_chroma_store_implements_protocol():
    assert isinstance(ChromaStore(data_dir=db.DATA_DIR), Store)


def test_facade_delegates_chunk_text():
    text = "one two three four five"
    assert db.chunk_text(text) == [text]