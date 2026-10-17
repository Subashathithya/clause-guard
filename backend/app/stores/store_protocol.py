"""Storage protocol for the ClauseGuard vector/knowledge layer (RAG backend).

Agents and API routes depend on this interface, not on Chroma directly. This is
the seam for swapping in a Postgres pgvector implementation (or a hosted vector
DB) without touching the pipeline.

Implementations must be thread-safe enough for FastAPI's default executor.
"""
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Store(Protocol):
    """Document + fair-clause vector store with semantic retrieval."""

    def index_document(self, document_id: str, document_name: str, text: str) -> int:
        """Chunk and index a contract; record it in the doc collection.

        Returns the number of chunks created.
        """
        ...

    def save_analysis(self, document_id: str, document_name: str, analysis: dict) -> None:
        """Persist the full analysis JSON for a document (legacy fidelity cache)."""
        ...

    def get_analysis(self, document_id: str) -> Optional[dict]:
        """Return the stored analysis payload for a document, or None."""
        ...

    def get_document_text(self, document_id: str) -> Optional[str]:
        """Return the full indexed text of a document, or None."""
        ...

    def get_documents(self) -> list[dict]:
        """List stored documents (name, char count, created_at, ...)."""
        ...

    def delete_document(self, document_id: str) -> None:
        """Remove all chunks + records for a document idempotently."""
        ...

    def retrieve_context(
        self,
        question: str,
        document_ids: Optional[list[str]] = None,
        top_k: int = 6,
    ) -> list[dict]:
        """Semantic search over indexed contract chunks.

        ``document_ids`` scopes retrieval (None = search everything — callers in
        the grounded chat path must NEVER pass None; see /chat scoping).
        Returns [{"text", "document_id", "document_name", "similarity"}, ...].
        """
        ...

    # ------------------------------------------------------- metric space ops
    def collection_space(self, name: str) -> Optional[str]:
        """Return the collection HNSW metric space: 'cosine' | 'l2' | None."""
        ...

    def collection_spaces(self) -> dict[str, Optional[str]]:
        """Map every known collection name to its HNSW space."""
        ...

    def collections_need_migration(self) -> list[str]:
        """Names whose space is NOT cosine (l2 or missing)."""
        ...

    def recreate_collection(self, name: str) -> None:
        """Recreate an empty collection on the cosine space (caller re-seeds)."""
        ...

    def seed_fair_clauses(self, force: bool = False) -> int:
        """Load the fair-clause library from the data dir; return reference count."""
        ...

    def fair_clause_count(self) -> int:
        """Number of fair-clause references currently indexed."""
        ...

    def compare_to_standard(
        self,
        clause_text: str,
        category: Optional[str] = None,
        top_k: int = 2,
    ) -> dict:
        """Semantic search against the fair-clause library.

        Returns {"standard_match", "similarity", "reference_clause",
                 "reference_category", "notes"}.
        """
        ...