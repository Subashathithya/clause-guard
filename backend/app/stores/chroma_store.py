"""ChromaDB-backed implementation of the ``Store`` protocol.

Moved verbatim from the old flat `app/db.py` (Phase 3 store split) so behaviour
is preserved while giving the pipeline a clean dependency seam.

Collections:
  * clause_chunks  - overlapping chunks of every analysed contract (RAG chat)
  * documents      - one record per contract (listing / drift / compare)
  * fair_clauses   - the curated library of fair clause references
  * analyses       - cached full analysis JSON per contract
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from app.settings import settings

logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)


class ChromaStore:
    """Local persistent ChromaDB store using all-MiniLM-L6-v2 embeddings."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        absolute = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = data_dir or os.path.join(absolute, "data")
        self._client: Optional[chromadb.ClientAPI] = None
        self._embed_fn = None

    # ----------------------------------------------------------- client utils
    def get_chroma(self) -> chromadb.ClientAPI:
        if self._client is None:
            os.makedirs(settings.CHROMA_DIR, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def get_embedding_fn(self):
        if self._embed_fn is None:
            self._embed_fn = embedding_functions.ONNXMiniLM_L6_V2()
        return self._embed_fn

    # Default HNSW space is Euclidean (l2), which makes the 0.30..0.85
    # similarity thresholds in the pipeline wrong (similarity = max(0, 1-dist)
    # saturates at 0 for anything farther than 1.0). Every collection is instead
    # created with the cosine space so the 0..1 similarity math holds.
    EMBEDDING_SPACE = "cosine"

    def _collection(self, name: str):
        client = self.get_chroma()
        try:
            return client.get_or_create_collection(
                name=name,
                embedding_function=self.get_embedding_fn(),
                metadata={"hnsw:space": self.EMBEDDING_SPACE},
            )
        except Exception:  # pragma: no cover - defensive against races
            return client.create_collection(
                name=name,
                embedding_function=self.get_embedding_fn(),
                metadata={"hnsw:space": self.EMBEDDING_SPACE},
            )

    # ---------------------------------------------------- space introspection
    def collection_space(self, name: str) -> Optional[str]:
        """Return the HNSW space of a collection: 'cosine' | 'l2' | None."""
        try:
            coll = self.get_chroma().get_collection(name=name)
            return (coll.metadata or {}).get("hnsw:space")
        except Exception:  # noqa: BLE001 - collection may not exist yet
            return None

    def collection_spaces(self) -> dict[str, Optional[str]]:
        names = (settings.CLAUSE_COLLECTION, "documents", "analyses", settings.FAIR_COLLECTION)
        return {name: self.collection_space(name) for name in names}

    def collections_need_migration(self) -> list[str]:
        """Names whose space is NOT cosine (missing/migrated/silent-default l2)."""
        return [name for name, space in self.collection_spaces().items() if space != "cosine"]

    def drop_collections(self, names: list[str]) -> None:
        client = self.get_chroma()
        for name in names:
            try:
                client.delete_collection(name=name)
            except Exception:  # noqa: BLE001 - already gone
                pass

    def recreate_collections(self, names: list[str]) -> None:
        """Recreate with cosine space (empty). Callers re-seed/re-index."""
        for name in names:
            self._collection(name)

    def clause_collection(self):
        return self._collection(settings.CLAUSE_COLLECTION)

    def docs_collection(self):
        return self._collection(settings.DOCS_COLLECTION)

    def fair_collection(self):
        return self._collection(settings.FAIR_COLLECTION)

    def analyses_collection(self):
        return self._collection("analyses")

    # --------------------------------------------------------------- chunking
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
        words = text.split()
        if len(words) <= chunk_size:
            return [text] if text.strip() else []
        chunks, step = [], chunk_size - overlap
        for i in range(0, len(words), step):
            chunks.append(" ".join(words[i : i + chunk_size]))
        return chunks

    # --------------------------------------------------------------- contracts
    def index_document(self, document_id: str, document_name: str, text: str) -> int:
        chunks = self.chunk_text(text)
        if chunks:
            self.clause_collection().add(
                ids=[f"{document_id}_{i}" for i in range(len(chunks))],
                documents=chunks,
                metadatas=[
                    {"document_id": document_id, "document_name": document_name, "chunk_index": i}
                    for i in range(len(chunks))
                ],
            )

        self.docs_collection().upsert(
            ids=[document_id],
            documents=[text],
            metadatas=[
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "chunk_count": len(chunks),
                    "char_count": len(text),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
        return len(chunks)

    def save_analysis(self, document_id: str, document_name: str, analysis: dict) -> None:
        self.analyses_collection().upsert(
            ids=[document_id],
            documents=[json.dumps(analysis)],
            metadatas=[
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "overall_risk": analysis.get("risk_summary", {}).get("overall_risk", "UNKNOWN"),
                    "average_risk_score": float(
                        analysis.get("risk_summary", {}).get("average_risk_score", 0)
                    ),
                }
            ],
        )

    def get_analysis(self, document_id: str) -> Optional[dict]:
        res = self.analyses_collection().get(ids=[document_id])
        docs = res.get("documents") or []
        if not docs:
            return None
        try:
            return json.loads(docs[0])
        except (json.JSONDecodeError, TypeError):
            return None

    def get_document_text(self, document_id: str) -> Optional[str]:
        res = self.docs_collection().get(ids=[document_id])
        docs = res.get("documents") or []
        return docs[0] if docs else None

    def get_documents(self) -> list[dict]:
        res = self.docs_collection().get()
        out = []
        for doc_id, meta in zip(res.get("ids", []), res.get("metadatas", []) or []):
            meta = meta or {}
            out.append(
                {
                    "document_id": doc_id,
                    "document_name": meta.get("document_name", "Unnamed"),
                    "chunk_count": meta.get("chunk_count", 0),
                    "char_count": meta.get("char_count", 0),
                    "created_at": meta.get("created_at", ""),
                }
            )
        out.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return out

    def delete_document(self, document_id: str) -> None:
        try:
            self.clause_collection().delete(where={"document_id": document_id})
        except Exception:  # noqa: BLE001
            pass
        for coll in (self.docs_collection(), self.analyses_collection()):
            try:
                coll.delete(ids=[document_id])
            except Exception:  # noqa: BLE001
                pass

    # --------------------------------------------------------------- RAG
    def retrieve_context(
        self, question: str, document_ids: Optional[list[str]] = None, top_k: int = 6
    ) -> list[dict]:
        where = {"document_id": {"$in": document_ids}} if document_ids else None
        res = self.clause_collection().query(query_texts=[question], n_results=top_k, where=where)
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]
        out = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            out.append(
                {
                    "text": doc,
                    "document_id": (meta or {}).get("document_id", ""),
                    "document_name": (meta or {}).get("document_name", "Unknown"),
                    "similarity": round(max(0.0, 1.0 - float(dist)), 3),
                }
            )
        return out

    # --------------------------------------------------------------- fair clauses
    def seed_fair_clauses(self, force: bool = False) -> int:
        path = os.path.join(self.data_dir, "fair_clauses.json")
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # spec format: { "Payment": [clause texts...], ... }
        by_category = data.get("clauses_by_category") or {}
        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        for category, texts in by_category.items():
            for number, text in enumerate(texts, start=1):
                ids.append(f"{category.lower().replace(' ', '_')}_{number:02d}")
                docs.append(text)
                metas.append({"category": category, "clause_ref": ids[-1]})

        coll = self.fair_collection()
        if force and coll.count() > 0:
            self.get_chroma().delete_collection(settings.FAIR_COLLECTION)
            coll = self.fair_collection()
        if coll.count() >= len(ids):
            return coll.count()
        coll.upsert(ids=ids, documents=docs, metadatas=metas)
        return coll.count()

    def compare_to_standard(
        self, clause_text: str, category: Optional[str] = None, top_k: int = 2
    ) -> dict:
        """Semantic search against the fair-clause library. Returns best match + similarity."""
        coll = self.fair_collection()
        if coll.count() == 0:
            return {"standard_match": "unknown", "similarity": 0.0, "reference_clause": None,
                    "reference_category": None, "notes": "Fair-clause library is empty."}

        where = {"category": category} if category else None
        if where:
            try:
                res = coll.query(query_texts=[clause_text], n_results=top_k, where=where)
            except Exception:  # noqa: BLE001
                res = coll.query(query_texts=[clause_text], n_results=top_k)
        else:
            res = coll.query(query_texts=[clause_text], n_results=top_k)

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        if not docs:
            return {"standard_match": "unknown", "similarity": 0.0, "reference_clause": None,
                    "reference_category": None, "notes": "No comparable reference found."}

        similarity = round(max(0.0, 1.0 - float(dists[0])), 3)
        match = "match" if similarity >= 0.65 else "worse"
        return {
            "standard_match": match,
            "similarity": similarity,
            "reference_clause": docs[0],
            "reference_category": (metas[0] or {}).get("category"),
            "notes": f"Closest industry-standard reference similarity {similarity:.0%}.",
        }

    def fair_clause_count(self) -> int:
        try:
            return self.fair_collection().count()
        except Exception:  # noqa: BLE001
            return 0