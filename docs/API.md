# ClauseGuard REST API

The complete, up-to-date API reference lives in
[**`docs/API_DOCUMENTATION.md`**](API_DOCUMENTATION.md).

Quick summary:

- `GET /health` — service status + vector store stats
- `POST /analyze` — full 4-agent analysis of pasted text (**≥ 50 chars**, else 422)
- `POST /upload` — PDF/TXT/MD/DOCX upload → analysis (≥ 50 chars after extraction)
- `POST /chat` — RAG Q&A with source citations
- `POST /compare` · `POST /drift` — multi-contract comparison / version drift
- `GET /contracts` · `GET|DELETE /contracts/{id}` — owner-scoped contract storage
- `POST /auth/register` · `POST /auth/login` · `GET /auth/me` — JWT auth (guest mode by default)
- `GET /fair-clauses` · `POST /fair-clauses/seed` — fair-clause library
- `GET /history` · `GET /stats` · `DELETE /analyses/{id}` — relational history/stats
- `POST /test-api-key` — Groq key check