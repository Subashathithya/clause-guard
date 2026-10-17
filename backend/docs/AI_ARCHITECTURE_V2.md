# ClauseGuard — AI Architecture V2

Deterministic-first, LLM-validated, observability-safe contract analysis.

---

## 0. Principles

1. **Deterministic where it must be.** Grounding, refusal, evidence checks and
   schema validation are deterministic — never left to the LLM to "just say the
   right thing".
2. **LLM where it adds judgment.** Extraction, categorisation, ranking,
   negotiation and summary use the LLM, but every structured call goes through
   `chat_json_validated` (retry -> validated -> deterministic fallback).
3. **Grounded chat or nothing.** The chat route answers from retrieval only;
   with no relevant context it refuses (`NO_CONTEXT`) instead of fabricating.
4. **Scoped to the caller.** Retrieval/grounding is scoped per user/per
   document — never a global corpus search.
5. **Privacy-safe observability.** Counts, ids and stage flags only; never
   clause text, chat text or secrets.

---

## 1. Pipeline (unchanged agent contract, verified)

```
                    CONTRACT
                       │
                       ▼
                 Extraction           ExtractAgent  ── chat_json_validated(LLMExtractorOutput)
                       │
                       ▼
                Clause Data
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Comparator   Ranker      Negotiator        (parallel, RAG vector-store)
          │            │            │
          └────────────┼────────────┘
                       ▼
                    Merge / sort
                       │
                       ▼
                 Evidence Check      evidence.verify_evidence (deterministic)
                       │
                       ▼
                  AnalysisResult     (⇑ ENRICHED AnalysisResult
                       │               fields: clause_id, category, text,
                       ▼               risk_*, negotiation_*, evidence flags)
                    Summary          chat_json_validated(LLMSummaryOutput)
```

## 2. Grounded contract chat (as implemented)

```
Question
   ↓
  scoped request        document_ids ∩ visible (per user/session) — never global
   ↓
Embedding Retrieval     vector store: cosine space, top_k=CHAT_TOP_K,
                       CHAT_MIN_SIMILARITY gate
   ↓
Relevant Evidence?      no  → NO_CONTEXT answer + empty sources (LLM never called)
   │ yes
   ↓
Grounded LLM Answer     system prompt embeds ONLY retrieved chunk text + citations
   ↓
Source Validation       answers with sources[] (document_name, clause_id,
                       similarity) — enough ids to be evidence-checkable
   ↓
Answer + Sources
```

## 3. Deterministic evidence check (per clause)

```
Clause → clause_id exists? → text non-empty? → category valid? →
reference_clause_id resolves to a real, non-empty clause?
      supported = all checks pass
```

Returns `{total, supported, unsupported, by_clause}`; emits
`observability.evidence(checked, supported, unsupported)`.

## 4. Configuration surface (settings.py)

| Knob | Default | Effect |
|------|---------|--------|
| `CHAT_TOP_K` | 6 | retrieval chunk count for chat grounding |
| `CHAT_MIN_SIMILARITY` | 0.30 | minimum cosine similarity for grounding (below -> NO_CONTEXT) |
| `AUTO_RECONCILE_VECTOR_STORE` | true | recreate non-cosine collections + reseed fair clauses at startup |

## 5. Observability events

`observability.{llm_call, validation, retrieval, evidence, chat, fallback,
latency}` — all aggregate/id/count only (privacy contract §0.5).

## 6. Scope of this document

Describes the corrected architecture verified by `docs/AI_ENGINE_AUDIT.md`
against the implementation on disk. It deliberately does **not** claim
accuracy/hallucination metrics — those require a dedicated evaluation dataset
and are outside this phase.
