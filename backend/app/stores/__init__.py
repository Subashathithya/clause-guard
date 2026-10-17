"""Vector/knowledge store package (the RAG backend).

`app/stores/store_protocol.py` defines the ``Store`` interface the pipeline
depends on; `app/stores/chroma_store.py` implements it with local ChromaDB.
`app/db.py` keeps acting as a module-level facade so existing call sites and
tests are untouched. A Postgres pgvector implementation can be added later by
implementing the same protocol.
"""