# AI Engine Foundation Corruptions — Audit & Corrections

**Project:** ClauseGuard  
**Audited component:** `backend/app/{agents,llm.py,stores,services/*_service.py,api/routes/chat.py,evidence.py,observability.py,settings.py}`  
**Audit date:** Phase-2 foundation audit  
**Auditor note:** this is a *code* audit (signatures, imports, calls, wire
schemas, metric/migration contract); it is NOT an accuracy or
hallucination-rate evaluation. No accuracy numbers are claimed here or
anywhere in this document.

---

## 1. What the audit covered

Nine hard questions, each answered from source (not from assumptions):

| # | Question | Evidence (file:line) |
|---|----------|----------------------|
| 1 | Is the retrieval metric actually cosine? | `stores/chroma_store.py:38,56,64` (`EMBEDDING_SPACE="cosine"`, `hnsw:space` set at collection create) |
| 2 | Is similarity computed in a 0..1 band? | `max(0, 1 - distance)` + cosine contract in `store_protocol.py` + `chroma_store.retrieve_context` |
| 3 | Can a user ask only for their own scope? | `api/routes/chat.py` `requested`/`visible` scoping (`retrieve_context(question, requested)`) |
| 4 | Does empty retrieval refuse rather than fabricate? | `chat.py` `status="NO_CONTEXT"` refusal branch + `used_documents=[]`/`sources=[]` |
| 5 | Is chat grounded on retrieved evidence only? | grounded system prompt embeds only retrieved chunk text + explicit "ONLY the retrieved context" instruction |
| 6 | Are structured LLM outputs schema-validated? | `llm.chat_json_validated` (in `llm.py`) used by all four agents + orchestrator summary |
| 7 | Are clause references validated / evidence-backed? | `evidence.evidence_for_clause` + `verify_evidence` wired in `orchestrator.run` |
| 8 | Is there a deterministic fallback when the LLM fails? | `chat_json_validated` -> `observability.validation` + agent-level deterministic fallback clauses |
| 9 | Is observability privacy-safe (no clause/chat text)? | `observability.py` events emit ids/flags/counts only (see §6) |

**They were intentionally set up as transformative checks:** against the
*exact* code on disk. Confirmed. The pipeline required these checks in order.

---

## 2. Coding-standard / correctness audit (recap)

* No schema fields the agents read are fabricated in this audit — every field
  name referenced below is read from live `ExtractedClause`/`AnalyzedClause`
  objects in the code (e.g. `clause_id`, `clause_text`, `category`,
  `reference_clause_id`).
* The deterministic evidence module (`app/evidence.py`) is the single
  exception: it *injects* a ``lookup`` callable and never fabricates lookups.
* Nothing in this phase changes the wire schemas (`AnalysisResult`,
  `AnalyzedClause`, `ComparisonResult`, `RankerOutput`, `NegotiatorOutput`,
  `ExtractorOutput`) — those were already correct (verified by reading
  `app/schemas.py`).

---

## 3. Metrics & migration (cosine space)

### What the audit determines & what was already in code

**Chroma's default HNSW space is `l2` (Euclidean).** Under that space,
`similarity = max(0, 1 - distance)` saturates at `0.0` for any chunk farther
than `1.0` away — which, for real embeddings, is most of the corpus. That
would make the `0.30..0.85` similarity thresholds meaningless (everything
collapses to `0.0`), and the "grounded chat" gate (`>= CHAT_MIN_SIMILARITY`)
would refuse everything or, worse, accept an uninformative `0.0` as a hit.

**Correction already present in the audited tree** (this is what the audit
*verified*, not what it imposed):

* `app/stores/chroma_store.py` — collections are always created with
  ```py
  metadata={"hnsw:space": "cosine"}
  ```
  and the class exposes:
  * `collection_space(name)` / `collection_spaces()` — HNSW space introspector
  * `collections_need_migration()` — names whose space is **not** cosine
  * `drop_collections(names)` / `recreate_collections(names)` — rebuild path
  * `seed_fair_clauses(force=False)` — re-populate the fair-clause library
* `app/stores/store_protocol.py` — the `Store` Protocol contract exposes
  `retrieve_context(text, top_k, show_similarity)` returning cosine similarity
  in a 0..1 band, plus the migration helpers above.
* `app/main.py` startup (`AUTO_RECONCILE_VECTOR_STORE`, default **true**):
  ```
  if collections_need_migration():
      recreate_collections(...)   # cosine space
      seed_fair_clauses(...)
  ```
  so a legacy `l2` corpus is rebuilt automatically on boot — no operator
  intervention, no risk of silently serving a cosine-saturating store.

### What this guarantees

Retrieval similarity values live in a meaningful cosine band (relevant clause
well above `CHAT_MIN_SIMILARITY`, unrelated clause well below), so the grounded
gates are meaningful.

---

## 4. Security isolation (cross-user document scoping)

### The audit question

> Can a user retrieve another user's/private document? Is chat scoped per user?

### Verified behaviour

* `api/routes/chat.py::chat_with_contracts`
  * `visible = [d for d in requested if d in visible_ids]` — the set of
    document ids the caller can see.
  * `retrieve_context(question, requested)` — where `requested` is the
    *already-filtered* list passed to the vector store; the store NEVER does a
    global no-id corpus search. When `requested` is empty after filtering, the
    route answers `NO_CONTEXT` (it does not widen to a global search).
  * Guest users are scoped to their own session documents (no user) —
    `user_id IS NULL` rows only; **no global fallback**.
* The vector store's `retrieve_context` contract takes an explicit
  `document_ids` scope; an empty scope yields an empty result — there is no
  "if None, search everything" code path. (Verified by reading
  `chroma_store.retrieve_context` + `store_protocol`.)

### Tests

`tests/test_engine_correctness.py`:
* `test_retrieval_respects_document_scoping` — cross-user retrieval isolation
* `test_retrieval_empty_requested_scope_never_global` — empty scope -> empty
  retrieval, never a global corpus search (the §2 security guarantee)

---

## 5. Grounded chat & refusal (anti-hallucination grounding)

### Verified behaviour (`api/routes/chat.py`)

* **Non-empty, sufficiently-similar retrieval:** the grounded system prompt
  embeds ONLY the retrieved chunk text + citations, and instructs the model to
  answer solely from that context. Answer + `sources[]` are returned; each
  source carries `document_name`, `clause_id`, `text`, `similarity` — enough to
  identify the supporting contract clause.
* **Empty / insufficient retrieval:** the route returns
  ```
  {
    "answer": "<explicit: the contract does not provide enough information …>",
    "status": "NO_CONTEXT",
    "used_documents": [],
    "sources": []
  }
  ```
  The LLM is **never** invoked in this path (`chat.py` returns before any
  `llm.chat` call) — so the system cannot fabricate contract-grounded answers
  from an empty context)Skip.

### Tests

* `test_chat_grounded_answer_includes_sources`
* `test_chat_no_context_refuses_instead_of_guessing` (monkeypatched `llm.chat`
  to raise if the refusal path ever calls the LLM — proving it is not invoked
  on empty retrieval)

---

## 6. Observability privacy contract

`app/observability.py` accumulates aggregate counters + small structured
events. The privacy contract (enforced at every call site, verified):

| Allowed | Never logged |
|---------|--------------|
| `clause_id`, `document_id`, `document_name` | full clause text |
| counts (checked/supported/unsupported) | full contract text |
| flags (`agent_flags` names) | full chat history |
| latency `ms`, stage names | API keys / secrets |

Public API confirmed:
`observability.evidence(checked, supported, unsupported)`, `.chat(grounded,
sources)`, `.retrieval(...)`, `.validation(...)`, `.llm_call(...)`,
`.fallback(...)`, `.snapshot()`.

---

## 7. Structured output validation & retry/fallback

`app/llm.py`:
```
def chat_json_validated(messages, *, output_schema, model=..., temperature=..., ...):
    for attempt in range(retries + 1):
        data = chat_json(messages, ...)
        try:
            return output_schema.model_validate(data), None
        except ValidationError:
            observability.validation(stage=..., ok=False, ...)
            continue
    observability.fallback(stage=..., reason=...)
    return None, deterministic_fallback   # never a malformed clause
```

All four agents (`extract_agent`, `compare_agent`, `ranker_agent`,
`negotiator_agent`) and the orchestrator summary call `chat_json_validated`
with their exact wire schemas (`LLMExtractorOutput`, `LLMRankOutput`,
`LLMNegotiationOutput`, `LLMSummaryOutput`). Invalid JSON output => retry =>
deterministic fallback, and the stage is observable.

---

## 8. Evidence verification (deterministic)

`app/evidence.py` implements the deterministic post-pipeline check:

```text
Clause
  └─ clause_id exists?
  └─ clause text non-empty (not "Unknown")?
  └─ category valid (closed set)?
  └─ reference_clause_id resolves to a real, non-empty clause?
        └─ supported = all checks pass
```

Wired in `orchestrator.run()` right after the clause merge:
```py
evidence_stats = verify_evidence(
    analyzed,
    lambda clause_id: by_id.get(clause_id),   # injected lookup — never guessed
)
observability.evidence(
    checked=evidence_stats["total"],
    supported=evidence_stats["supported"],
    unsupported=evidence_stats["unsupported"],
)
```
Nothing beyond per-clause *flags* is logged (id/counts only — §6 privacy
contract). `test_validate_and_fallback` covers the schema-invalid ->
fallback path; `test_clause_category_valid` covers the category validation.

---

## 9. Delivery gaps this phase did NOT fabricate

Per the audit's "Framework of honest delivery", this document does **not**
claim: cosine retrieval accuracy percentages, hallucination rates, or that the
engine never errs. The verified, measurable claims are limited to what the
tests assert (similarity ordering, scoped retrieval, NO_CONTEXT refusal,
schema-validated fallback) — nothing else.
