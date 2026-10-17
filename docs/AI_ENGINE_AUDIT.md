# ClauseGuard AI Engine Audit

**Status:** Source-code audit — no changes made.
**Date:** 2026-09-18
**Evidence basis:** Every claim below is traced to the actual backend source in
`backend/` (files + line references). No metric or capability is assumed or
invented. Where a behaviour could not be verified from code it is explicitly
marked **UNVERIFIED** or **PENDING** (see `docs/METHODOLOGY.md` for the
project's own "never invent numbers" rule).

---

## 1. Executive Summary

ClauseGuard is a **4-agent LLM analysis pipeline** (Extractor → Comparator →
Ranker → Negotiator) fronted by a FastAPI service, with a **hybrid
deterministic+RAG+LLM** design. A single `/analyze` run performs **`2 + N +
(N − G)` LLM calls** (N = extracted clauses, G = clauses ranker marks green;
see §6). The Comparator is **pure deterministic RAG** (semantic similarity
against a 197-clause fair/industry-standard library) and never calls an LLM.
Ranking, negotiation drafting and the executive summary are LLM calls, each
with a deterministic fallback, so the pipeline **never hard-fails** on a single
agent error (`PARTIAL_SUCCESS`/`EXTRACTOR_ERROR` states, `agent_flags`).

The strongest part of the design is its **defence-in-depth around
grounding** (§9): every risky-clause verdict is seeded by a similarity-vs-fair
reference that is also injected into the ranker and negotiator prompts, and
each agent owns a cold deterministic fallback. 

The most important weaknesses, in impact order (task §14):

1. **Similarity score is based on raw L2 distance, not cosine (§10, §13).**
   Collections are created without a `metadata` space selector, so Chroma uses
   its default `l2`. `similarity = max(0.0, 1.0 − distance)` saturates at `0.0`
   very often for these embeddings. The `0.65/0.70/0.85` thresholds that drive
   the whole red/yellow/green decision tree were clearly designed for a
   cosine-like 0-1 score. This is the most plausible cause of the measured
   red-heavy behaviour (red recall 100%, yellow recall only 23.8%).
2. **`/chat` can answer without grounding and outside the caller's scope (§7,
   §13).** When the vector search returns nothing the system prompt explicitly
   says *"Answer generically if possible"*, and when `document_ids` are
   omitted (or all invisible to the caller) retrieval falls back to **the
   entire indexed corpus across all users** — the documented intent ("scope to
   empty set") is not what the code does.
3. **`/compare` and `/drift` are aggregate/score statistics, not textual
   comparisons (§10).** No clause-to-clause matching and no text diff anywhere.
4. **LLM JSON output is parsed but never schema-validated (§6).** Agents
   coerce with `.get()` defaults; there is no retry-on-invalid-shape.

The system is honest about its own evaluation: the labelled harness
(`experiments/run_experiments.py`, 70 cases) recorded **68.57% accuracy** on
the WITH-RAG baseline; the NO-RAG ablation is **PENDING** after an invalidated
Groq quota run (§14). Groq remains the only provider (option `--ablate-rag`
exists for experiments only).

---

## 2. Scope, Method and Evidence

**Scope.** Backend AI engine only: the four agents, the orchestrator, the LLM
wrapper, the vector store (ChromaDB), the RAG retrieval path, the fair-clause
library, and every endpoint that invokes the engine (`/analyze`, `/upload`,
`/chat`, `/compare`, `/drift`, plus `/test-api-key`). Persistence, auth and
quota layers are covered only where they touch the AI engine.

**Method.** Traced the actual execution path end-to-end from route handler →
service → store for each operation; enumerated every `llm.*` and
`vdb.*` call; read all four agent files, the orchestrator, `llm.py`,
`chroma_store.py`, `db.py`, `settings.py`, `schemas.py`, `uploads.py`,
`contract_service.py` and the relevant route modules in full.

**Evidence rules.** (a) No live LLM call was made for this audit — the file's
cost/latency numbers are structural (inferred from code), not measured.
(b) Historical numbers cited (§10, §12, §14) are the ones already recorded in
`experiments/*.json` and `docs/METHODOLOGY.md`; they are reproduced, not
repeated as new measurements.

---

## 3. Architecture Map and Data Model

```
Frontend (React, :3000)  ──HTTP──►  FastAPI backend (:8011)
                                    ├─ app/main.py          app factory, CORS, startup seed
                                    ├─ app/settings.py      env config (Groq, quotas, uploads)
                                    ├─ app/api/routes/      analysis, chat, compare, contracts,
                                    │                       knowledge, history, misc, auth, health
                                    ├─ app/agents/          extract / compare / rank / negotiate
                                    │                       + orchestrator (pipeline)
                                    ├─ app/llm.py           Groq wrapper (retry + JSON parse)
                                    ├─ app/stores/          store_protocol.py (interface),
                                    │                       chroma_store.py (impl)
                                    ├─ app/db.py            facade -> single ChromaStore
                                    ├─ app/services/        contract_service.py (RDBMS + quotas)
                                    └─ app/uploads.py       PDF/TXT/MD/DOCX text extraction

Stores (two, deliberately split):
  └─ ChromaDB (chroma_db/, on-disk PersistentClient)
       ├─ clause_chunks   RAG chunks (600w, 100w overlap) + metadata {doc id/name, idx}
       ├─ documents       full text per document + {chunk_count, char_count, created_at}
       ├─ analyses        full analysis JSON per document (legacy fidelity cache)
       └─ fair_clauses    197 seeded fair / industry-standard references (7 categories)
  └─ SQLAlchemy relational (SQLite default: data/clauseguard.sqlite3)
       ├─ contracts (owner-scoped, denormalised aggregates + full text)
       ├─ clauses    (per-clause result incl. RAG evidence columns)
       ├─ users / usage_counters / chat_messages
```

**Persistence rule.** Each analysis is written in **three places**
(`app/api/routes/analysis.py:3-7`): Chroma clause chunks + analysis JSON
(`vdb.index_document`, `vdb.save_analysis`) and relational rows
(`contract_service.persist_contract`). The relational store is authoritative
for list/detail reads (`contract_service.build_payload`); `get_analysis`
(Chroma JSON) is used only by `/compare` and `/drift`. Deletion
(`history.py:42-54`) removes from Chroma then the relational row — the two
stores are not updated transactionally (§13).

---

## 4. Full Call-Path Traces

### 4.1 `POST /analyze` (pasted text) — `app/api/routes/analysis.py:79-99`
1. `_require_minimum_length` → 422 below `MIN_TEXT_LENGTH=50` chars.
2. `_quota_guard` → 429 if monthly quota exhausted:
   - logged-in → `FREE_TIER_ANALYSES_PER_MONTH − count(user's contracts, this month)`;
   - guest ⇒ `anonymous_remaining(ip)` via `UsageCounter` keyed on `ip + YYYY-MM`.
3. `run_orchestrator(text, name)` — full 4-agent pipeline (§5).
4. If `status == "NO_CLAUSES"` → return result, **neither persisted nor billed**.
5. Else `_persist_and_return`: new `uuid4()` → Chroma index + analysis JSON →
   relational rows → bump anon counter → return payload + `quota_remaining`.

### 4.2 `POST /upload` (file) — `analysis.py:102-140`
1. Size guard: `> MAX_UPLOAD_MB (10) * MiB` → 413.
2. `uploads.detect_file_type(content_type, filename)`; allowed set = pdf, txt,
   md, docx (`settings.ALLOWED_UPLOAD_TYPES`). Legacy `.doc` explicitly rejected.
3. `uploads.extract_text` — `pypdf` (PDF), `python-docx` (DOCX incl. table
   cells joined with `" | "`), UTF-8 decode for TXT/MD; scanned-PDF → clear
   "No selectable text" error.
4. Then identical to `/analyze` (min-length → quota → pipeline → persist).

### 4.3 `POST /chat` (RAG Q&A) — `app/api/routes/chat.py`
Detailed trace in §7. Summary: visibility-filter requested ids → `retrieve_context`
→ prompt with context block → 1 LLM call → persist `ChatMessage` → return
answer + used_documents + sources.

### 4.4 `POST /compare` — `app/api/routes/compare.py:27-99`
1. Require ≥2 `document_ids`; intersect with `visible_document_ids`.
2. Load stored analyses via `vdb.get_analysis` (Chroma JSON); <2 analyzable → 404.
3. Build **per-category matrix of average `risk_score`**; `winner` = doc with
   lowest category average (line 61).
4. One LLM narrative call (digest = overall risk + avg score per doc only).
5. Return matrix + narrative. **No clause-level matching** (§10).

### 4.5 `POST /drift` — `compare.py:102-155`
1. Exactly 2 visible, analysed docs (old, new) → else 404.
2. Per-category averages from stored analyses; `delta = after − before`;
   direction `worsened` if `delta > 3`, `improved` if `< −3`, else `stable`;
   categories present in only one doc ⇒ `added`/`removed` (`delta=None`).
3. `overall_delta` on average risk score; same ±3 band.
4. **Zero LLM calls.** Purely deterministic score arithmetic (§10).

### 4.6 `POST /test-api-key` — `misc.py`
Single call to `FAST_MODEL` (gpt-oss-20b, `max_tokens=50`). Dev utility.

### 4.7 Auth path relevance
`get_optional_user` (core/security.py) decodes a Bearer JWT (HS256,
`JWT_EXPIRES_MINUTES=1440`) and returns the User or `None`; with
`REQUIRE_AUTH=false` (default) every engine endpoint runs in guest mode.

---

## 5. Multi-Agent Pipeline Audit

Executed by `Orchestrator.run` (`app/agents/orchestrator.py:52-183`).

| # | Agent | Stage | Parallelism | LLM? | Failure handling |
|---|-------|-------|-------------|------|------------------|
| 1 | **Extractor** (`extract_agent.py`) | Split contract into clauses; classify into 7 canonical categories; merge fragments <10 words; max 40 clauses | sequential | 1 JSON call | crash → `EXTRACTOR_ERROR` + trace; empty → `NO_CLAUSES` |
| 2 | **Comparator** (`compare_agent.py`) | `db.compare_to_standard(text, category, top_k=3)` semantic search vs fair library | `ThreadPoolExecutor` (4) | **none** | `ComparisonResult(notes=err)`; flag "Comparator" |
| 3 | **Ranker** (`ranker_agent.py`) | risk level+score+explanation+₹ impact, seeded by similarity prior | ThreadPool (4) | 1 JSON call per clause | deterministic similarity fallback; flag "Ranker" |
| 4 | **Negotiator** (`negotiator_agent.py`) | counter-clause + talking points + success prob; **green clauses skipped** (canned "No negotiation needed") | ThreadPool (4), subset | 1 JSON call per non-green | canned fallback (uses reference text); flag "Negotiator" |
| — | **Summary** (`orchestrator._synthesize`) | executive recommendation + top-3 priorities | sequential | 1 JSON call | deterministic fallback text |

Then: merge per-clause outputs into `AnalyzedClause`, **sort by `risk_score`
desc**, `_aggregate` (deterministic risk summary: any red ⇒ HIGH, else any
yellow ⇒ MODERATE, else SAFE; exposure = Σ financial_impact_inr). Status =
`SUCCESS`, or `PARTIAL_SUCCESS` if any `agent_flags` were recorded.

Design verdict: **deliberately fail-soft** — work is never lost on a single
agent error, and the RAG comparator is the only deterministic safety net that
always runs.

---

## 6. LLM Inventory

Provider: **Groq** (`app/llm.py`), client created with API key only (no
explicit request timeout configured — **UNVERIFIED** whether the Groq SDK
default applies). Models: `PRIMARY_MODEL=openai/gpt-oss-120b` (all pipeline +
chat + compare), `FAST_MODEL=openai/gpt-oss-20b` (only `/test-api-key`).

**Wrapper behaviour (`llm.py:67-108`):** `retries=2` ⇒ up to **3 attempts**;
linear backoff `time.sleep(1.5 * (attempt + 1))` (i.e. 1.5 s then 3.0 s) —
no fixed total-time budget, no jitter, no per-attempt timeout param.
`json_mode` adds `response_format={"type":"json_object"}`. `chat_json`
parses via `_extract_json` (fence-strip → full parse → first `{…}`/`[…]`
block) — **no schema validation, no retry-on-invalid-shape**. Per-call success/
prompt-char counters (`get_call_count/get_char_count`) exist for the eval
harness only.

### 6.1 Table of every LLM call

| Call site | Endpoint | Mode | Model | Temp | Max tokens | JSON | Retries | Parallel |
|---|---|---|---|---|---|---|---|---|
| Extract (`extract_agent.py:75`) | /analyze, /upload | `chat_json` | PRIMARY | 0.2 (default) | 4096 (default) | yes | 2 | — (1) |
| Rank (`ranker_agent.py:117`) | /analyze, /upload | `chat_json` | PRIMARY | **0.1** | 4096 | yes | 2 | 4 workers |
| Negotiate (`negotiator_agent.py:67`) | /analyze, /upload | `chat_json` | PRIMARY | **0.3** | 4096 | yes | 2 | 4 workers |
| Summary (`orchestrator.py:232`) | /analyze, /upload | `chat_json` | PRIMARY | 0.2 | 4096 | yes | 2 | — (1) |
| Chat (`chat.py:58`) | /chat | raw `chat` | PRIMARY | **0.3** | **1024** | no | 2 | — (1) |
| Compare narrative (`compare.py:71`) | /compare | raw `chat` | PRIMARY | **0.3** | **400** | no | 2 | — (1) |
| API key test (`misc.py:14`) | /test-api-key | `client.chat…` | **FAST** | default* | 50 | no | none (outer try) | — |

*`misc.py` bypasses the `llm.chat` wrapper (no retry, no char counting).

### 6.2 Call counts per operation

- **`/analyze` = `/upload`:** `1 (Extract) + N (Rank) + (N − G) (Negotiate) + 1 (Summary)`
  = **`2 + 2N − G` LLM calls** — e.g. 6 clauses with 2 green ⇒ 12 calls;
  worst case (`MAX_CLAUSES=40`, none green) ⇒ **82 calls**. Comparator: 0 calls.
  Retries can push this up to 3× per failed call.
- **`/compare`:** 1 (narrative; on error → inline "(comparison narrative
  unavailable…)" string, status stays SUCCESS).
- **`/drift`:** 0.
- **`/chat`:** 1 (up to 3 with retries).
- **`/test-api-key`:** 1 (FAST model).

### 6.3 JSON output validation (gaps)

- Parse-only; agents coerce defensively: `risk_score` clamped 0–100, `level`
  validated against `{red,yellow,green}` else derived from score
  (`_level_from_score`: ≥67 red, ≥34 yellow), `financial_impact_inr` via
  `int(float(…))` (None on error), `top_priorities[:3]`, `talking_points[:5]`,
  `clauses[:40]`.
- No Pydantic validation of LLM-produced dicts, no re-prompt on malformed
  shapes. Consequences are bounded (fallbacks) but silent.

---

## 7. RAG Audit — `/chat`

**Embedding model.** `ONNXMiniLM_L6_V2` (chroma_store.py:47-50) — local ONNX
`all-MiniLM-L6-v2` (384-dim); **no remote embedding calls, no embedding cost**.

**Chunking** (`chroma_store.py:73-80`). Word-based: `chunk_size=600` words,
`overlap=100` ⇒ step 500; short docs stay one chunk. Applied at index time to
the whole contract text; each chunk stored with metadata
`{document_id, document_name, chunk_index}`. No sentence-boundary awareness,
no recursive splitting, no headings — chunk boundaries can cut mid-clause.

**Collections.** `clause_chunks` (chunks), `documents` (full text + counts),
`analyses` (full JSON), `fair_clauses` (references). `get_or_create_collection`
is called with **no `metadata` space selector** ⇒ Chroma default **`l2`**
metric (§10 consequence).

**Retrieval** (`chroma_store.py:171-189`, called with `top_k=6` default).
`query(query_texts=[question], n_results=top_k, where={"document_id": {"$in": ids}})`,
`similarity = max(0.0, 1.0 − float(dist))`. **No reranker, no minimum
similarity gate, no metadata filter besides document ids.**

**Prompt construction** (`chat.py:35-58`).
- System prompt: *"Answer the user's question based ONLY on the retrieved
  contract context below. Quote specific clauses… If context is insufficient,
  say so clearly."* — then `context_block`, each item rendered
  `[<document_name> | <similarity as %>]\n<text>`.
- **Empty context fallback:** `"No stored contracts match your question.
  Answer generically if possible."` — i.e. the model is *invited* to answer
   ungrounded (§9).
- History: `messages += input_data.history[-10:]` — raw client-supplied dicts
  appended **before** the user question, elements used verbatim (a history item
  with `role: "system"` would be injected as a system message; a malformed item
  would 400 the Groq call). Role/content not validated.
- Answer `max_tokens=1024`, `temperature=0.3`. `ChatMessage` row persisted;
  response returns `answer`, `status`, `used_documents`, `sources` (each with
  text, document_id, document_name, similarity).

**Scoping flaw (§13).** `requested = [d for d in document_ids if d in visible]`;
if `requested` becomes empty it is set to `None`, which `retrieve_context`
treats as *search everything* (`where=None`) — the opposite of "scope to empty
set". The same happens when `document_ids` is omitted entirely. In a corpus
shared by multiple users this retrieves **other tenants' chunks** into the
prompt and returned sources.

---

## 8. Context Usage Matrix

What each LLM call actually receives:

| Call | Context injected | Grounding anchor | Source |
|---|---|---|---|
| Extract | Raw full contract text | none (task: split/classify) | prompt embeds text |
| Rank | Clause text + category + **similarity% + nearest fair reference text** + mapping/prior | fair-library reference | comparison output |
| Negotiate | Clause text + category + priority (HIGH red / LOW) + level+score + **fair reference** | fair-library reference | comparison output |
| Summary | doc name, overall risk/avg, counts, digest = per-clause `[LEVEL score] category: explanation[:180]` | aggregate (no RAG) | risk_summary |
| Chat | Top-6 chunks (similarity ≥0) + last-10 history + question | retrieved chunks | retrieve_context |
| Compare narrative | Only per-doc overall risk + avg score (no clause text, no references) | none | risk_summary digest |

**Observations.** (a) The only RAG evidence flowing into analysis is the
**top-1 nearest fair reference** (top_k=3 requested by `compare_agent` but only
`docs[0]` is consumed at `chroma_store.py:242-249`). (b) Ranker includes the
reference but **not** the full retrieved chunk windows. (c) Compare narrative
is written from two numbers per document — it cannot compare clauses.

---

## 9. Evidence & Hallucination Audit

Strengths:
- Ranker/negotiator ground every risky-clause output in an actual fair
  reference text pulled from the local library (`ranker_agent.py:85-98`,
  `negotiator_agent.py:45-52`), with the similarity mapped to a stated prior.
- Chat prompt enforces "based ONLY on retrieved context" and returns the exact
  source snippets to the frontend (`chat.py`).
- Deterministic fallbacks ensured the unsupported/ablated paths could never
  silently fabricate scores beyond the similarity look-up.

Risks (each with code location):
- **Ungrounded /chat when retrieval is empty** (`chat.py:41`) — explicit
  generic-answer permission.
- **Ungrounded /chat when retrieval is low-similarity** — no floor; top-6 are
  always injected no matter how irrelevant (`chroma_store.py:175`).
- **No citation enforcement** — the model is told what to base the answer on,
  but nothing verifies the answer only uses that context (no faithfulness
  check).
- **Unverifiable self-quantities surfaced as facts** — `financial_impact_inr`
  and `success_probability` are LLM estimates presented as precise numbers in
  the UI; no calibration or hedging metadata is attached.
- **Compare narrative hallucination surface** — written only from two summary
  numbers, not from clause content.
- **No schema validation** (§6.3) means malformed-but-parseable JSON (e.g.
  risk_score "85.5") silently falls back instead of retrying.
- History poisoning /instruction-injection vector via raw `history` dicts (§7).

---

## 10. Comparator & Drift Technical Audit

**Comparator** (`compare_agent.py` + `chroma_store.compare_to_standard`).
Semantic search against `fair_clauses` (197 refs, metadata `{category,
clause_ref}`), `where={"category": …}` so search is scoped by the extractor's
category label (falls back to unscoped if the filtered query raises).
`standard_match = "match" if similarity ≥ 0.65 else "worse"` — note **"better"
is never emitted** (the schema allows it, no path produces it). **Only the
top-1 result is used** for similarity + reference.

**Critical metric issue.** All collections are created without an explicit
embedding-space (`chroma_store.py:52-69`), so Chroma uses its default
**`l2` (Euclidean)** metric. Similarity is then `1 − l2_distance`, clamped at
`0.0`. For `all-MiniLM-L6-v2` embeddings the Euclidean distances between
unrelated clauses are routinely ≥ 1, so scores saturate at 0.0 and the
0.65–0.85 thresholds (which implicitly assume a cosine-like 0-1 score) classify
most clauses as `worse`/red. **This is consistent with** the measured eval
pattern — red recall 100%, yellow recall 23.8%, green precision 100%
(`METHODOLOGY.md §4`). It should be treated as a strong hypothesis to confirm
by switching to cosine and re-running the harness — not a measured fact of this
audit.

**Compare endpoint** (`compare.py`). Aggregate-only: averages of `risk_score`
per category per document; "winner" = lowest category average. No clause-to-
clause matching, no overlap metric, no redirection to full clause evidence.
Output = category matrix + 1 LLM narrative.

**Drift endpoint** (`compare.py:122-155`). Entirely deterministic score
arithmetic on stored analyses: per-category average deltas, banded at ±3
points. It measures **output-score drift, not textual drift** — two versions
whose wording changed but whose scores didn't are reported "stable", and it
cannot attribute *what* changed. Requires both documents pre-analysed (404
otherwise) and reads the Chroma JSON cache (§3).

---

## 11. Architecture Diagram

```
                            ┌────────────────────────────────────────────────────┐
                            │                 FastAPI :8011                       │
                            │  analyze / upload / chat / compare / drift /        │
                            │  contracts / history / fair-clauses / auth / health │
                            └───────────────┬────────────────────────────────────┘
                                            │ run_orchestrator (agents/orchestrator.py)
                                            ▼
   ┌────────────┐     1 Extract (LLM, JSON) ┌─────────┐   N× compare (RAG, no LLM)
   │ raw text   │ ─────────────────────────►│         │──────────────►───────────┐
   │ / PDF/DOCX │                            │  Pool   │                         ▼
   └────────────┘                            │   (4)   │          Chroma fair_clauses ─┐
                                            └─────────┘              (197 refs)         │ cosine-ish? no─► l2
                                             top-1 reference + similarity %              ▲
                                                                                        │
   N× rank (LLM) ◄──────────────────────────────────────────────────────────────────────┘
        │  risk_level/score + ₹ impact
        ▼
   (N−G)× negotiate (LLM)                deterministic merge:
        │                                sort desc by score, risk_summary, agent_flags
        ▼
   1× summary synthesis (LLM) ──────────► AnalysisResult ─────────────────────────────┐
                                                                                      │
   index_document (chunk 600w/100w) ──► Chroma clause_chunks (+documents)             │
   save_analysis                        Chroma analyses  ◄── used by /compare,/drift    │
   persist_contract                     SQLite contracts/clauses  ◄── rich data        │
                                                                                      │
   /chat:  retrieve_context (top_k=6) ◄── Chroma clause_chunks ──► prompt ──► 1× LLM ─┘
```
Concurrency: three per-clause stages each run a `ThreadPoolExecutor` width 4;
the Chroma client is shared across those threads (§13.4).

---

## 12. Cost, Latency and Quotas

**Structural cost/latency (from code, not measured).**
- Calls per analysis: `2 + 2N − G` (§6.2). A typical 10-clause contract with 3
  green ≈ 19 calls ⇒ ~19 Groq round-trips; worst-case 40 clauses ≈ 82 calls.
- RAG adds zero API/embedding cost (local ONNX embedder).
- Parallel stages mean latency ≈ extract + `ceil(N/4)·rank` +
  `ceil((N−G)/4)·negotiate` + summary, bounded below by per-call Groq latency
  and above by retries (up to 3 attempts, waits 1.5 s + 3.0 s).
- Harness cost model (`run_experiments.py:41-42`): 4 chars/token × $0.002/1k
  tokens for gpt-oss-120b — **approximate; not audited against Groq billing**.

**Quotas** (`settings.py`, `contract_service.py`).
- `FREE_TIER_ANALYSES_PER_MONTH=5` per user *or* per anonymous IP (monthly
  `UsageCounter` per ip+YYYY-MM). `/analyze` and `/upload` enforce it; chat
  and compare/drift are **unquotaed**.
- Uploads: `MAX_UPLOAD_MB=10`; allowed pdf/txt/md/docx; legacy `.doc` blocked.
- `MIN_TEXT_LENGTH=50` chars (422 below).
- `REQUIRE_AUTH=false` by default ⇒ guest mode is the norm until flipped.
- JWT: HS256, `JWT_SECRET` default is `"dev-only-secret-change-me"`,
  `JWT_EXPIRES_MINUTES=1440`.

---

## 13. Latent Bugs, Security and Privacy

Ordered roughly by severity:

1. **`/chat` cross-scope retrieval (data exposure)** — `chat.py:31-35` sets
   `requested=None` when no requested id is visible (or none provided),
   turning a *narrowing* intention into *search-everything* across the shared
   Chroma corpus (`chroma_store.py:174`). Other tenants' chunk text can reach
   the prompt and the returned `sources`.
2. **CORS `allow_origins=["*"]` + `allow_credentials=True`** (`main.py:45-52`)
   — an invalid/unsafe combination; any website can issue non-credentialed
   calls to the API. With optional auth this is low-impact today, but the
   pair should never ship together in production.
3. **Similarity metric flaw** (§10) — silently biases every verdict toward red;
   surfaces to users as lower-quality reports, not as an error.
4. **Shared Chroma client across threads** — `PersistentClient`/collection
   handles are used concurrently from 4 worker threads and from FastAPI's
   default threadpool; Chroma is not documented as thread-safe. Races on
   `get_or_create_collection` are possible (`chroma_store.py:52-57`).
5. **Non-atomic dual-store persistence** — Chroma writes, relational writes and
   quota bumps are separate commits (`analysis.py:62-76`); a mid-run failure
   can orphan Chroma chunks or under/over-count quota.
6. **History trust** — raw `history` dicts are forwarded unbounded (only
   clipped to last 10) with unvalidated `role` (§7).
7. **Login brute-force surface** — no rate limiting around auth endpoints
   (auth module not rate-limited anywhere in code reviewed).
8. **Guest quota trusts client IP** — `request.client.host` (no
   `X-Forwarded-For`) drives anonymous quotas; trivial to rotate behind a proxy.
9. **`standard_match="better"` never produced** (§10) — dead schema branch.

---

## 14. Documentation vs Code Drift, and Evaluation State

**Drift found:**
- `docs/EVALUATION.md §1` describes a **39-case v1 dataset**; the current
  `data/eval_dataset.json` is **v2 with 70 cases** (10/category). METHODOLOGY.md
  is the accurate, current record.
- `docs/METHODOLOGY.md` is internally accurate for `openai/gpt-oss-120b`,
  0.2 temp, JSON mode — but omits the per-call temperature/max_tokens
  deviations found in §6.1 (ranker 0.1; chat/narrative 0.3; max_tokens 400/1024).
- `experiments/run_experiments.py` docstring matches behaviour
  (—ablate-rag, —limit, —delay all present).
- `main.py` docstring route table matches registered routers (health, auth,
  analysis, chat, compare, contracts, knowledge, history, misc).

**Recorded results (valid):** WITH-RAG baseline `report_r1789656419.json` —
**68.57% (48/70)**, 262 LLM calls, ≈18 min runtime (METHODOLOGY §4).
The abortive NO-RAG run (Groq daily-token cap) is preserved as
`report_r1789672949_INVALID_TPD.json` and **must not be cited**; a valid
NO-RAG ablation is **PENDING** (METHODOLOGY §5) — i.e. the RAG-attribution
delta the product claims is not yet measured.

---

## 15. Recommended Next Implementation Phase

All items below are **research/implementation proposals derived from this
audit** — none changes existing production behaviour until chosen.

**Correctness first (highest leverage):**
1. **Fix the similarity metric** — create Chroma collections with
   `metadata={"hnsw:space":"cosine"}` (or explicitly=`l2` and *calibrate*
   thresholds against measured distance distributions); set a principled
   floor; re-run the 70-case harness and compare 68.57%.
2. **Ground /chat hard** — require a minimum similarity (or chunk count) or
   answer only "no relevant clause found"; validate/normalise `history`
   roles; drop or explicitly scope the generic-answer fallback.
3. **Scope /chat strictly to the caller** — always apply `visible_document_ids`
   as the *upper bound* (never the no-op `None` fallback) so cross-tenant
   retrieval is impossible.

**Capability gaps:**
4. **Clause-level /compare** — pair clauses across documents (lexical + chunk
   similarity) instead of category averages; return matched/miss-matched
   pairs + a narrated diff with per-pair source evidence.
5. **Textual /drift** — run the comparator/differencing on the old vs new token
   sequence, not only stored score deltas, so wording changes that leave scores
   unchanged are still reported.
6. **LLM output contracts** — parse LLM JSON into the Pydantic result schemas
   with one retry-on-invalid (bounded), so "85.5"-style integers retry instead
   of silently falling back.

**Measurement & reliability:**
7. **Resume the NO-RAG ablation** in two chunks (avoiding the TPD cap) and
   record the WITH/NO-RAG delta here and in METHODOLOGY — the central
   attribution claim is still unmeasured.
8. **Chunk/embedding/retrieval ablation** — 600w/100w, MiniLM, top_k=6 and the
   no-gate retrieval are all unvalidated choices; add a recall@k harness.
9. **Sand down sharp edges** — per-request timeout on Groq calls, thread-safe
   Chroma access or client-per-request, atomic Chroma+SQLite persistence,
   safe CORS, prod JWT secret via env, guest quota via trusted proxy header,
   and CI eval gate (block merges that regress accuracy).

**Longer-term product/research (from EVALUATION.md §3-4):** multi-jurisdiction
corpus, image/OCR (scanned PDF) contracts, user feedback on risk labels to
grow a real agreement-measured dataset, and tracking self-reported
counter-clause acceptance to validate `success_probability`.