# Evaluation & Research

## 1. Evaluation methodology

ClauseGuard ships with a labelled evaluation harness
(`backend/evaluate_system.py` + `backend/data/eval_dataset.json`).

- **Dataset**: 39 clause-level cases spread across all 7 categories (7 Payment &
  Fees, 7 Renewal & Termination, 6 Data Privacy, 5 Liability, 5 IP, 4 Dispute
  Resolution, 5 Service Level). Each case has a human-assigned `expected_risk`.
- **Protocol**: for each case, run the full in-process pipeline, take the
  highest-risk predicted level among returned clauses, compare to the label.
- **Metrics**: overall accuracy, per-class precision/recall, and a confusion
  matrix. Full report → `backend/data/eval_report.json`.
- **Mode**: `--api` evaluates against a running server; default is in-process.

```bash
python evaluate_system.py --limit 10     # quick
python evaluate_system.py                # full set (recommended, ~40 LLM batches)
python evaluate_system.py --api --api-url http://127.0.0.1:8000
```

> Accuracy depends on model quality and prompt version. Track results across
> commits — with the bundled evaluator it is reproducible in CI.

## 2. Roadmap to >90% precision at scale

Target: validate on **30–50 real contracts** (diverse: SaaS ToS, gym memberships,
rental leases, loans, employment NDAs, insurance) and hold **>90% precision**.

1. Expand `eval_dataset.json` to 40–50 full contracts *and* clause-level labels.
2. Add an inter-annotator step (2 reviewers label each clause; disagreements
   resolved → gold set).
3. Iterate on prompts: evaluate after each change (script makes this cheap).
4. Record and compare per-category metrics; fix worst categories first.
5. Add a regression gate in CI: block merges that drop accuracy >1%.

## 3. Research paper outline
*(Target: student/lean academic venue; use your institution's co-authors.)*

**Title (working):** *ClauseGuard: A Multi-Agent LLM System for Consumer
Contract Risk Assessment and Negotiation Assistance*

1. **Introduction** — the consumer-contract information asymmetry problem;
   motivation from financial literacy and consumer-protection literature.
2. **Related Work** — legal NLP (ATES, contract summarisation), large language
   models in law, retrieval-augmented generation, negotiation support.
3. **System** — 4-agent architecture (Extractor/Comparator/Ranker/Negotiator),
   prompt design, RAG over a fair-clause corpus.
4. **Dataset & Evaluation** — the 70-case labelled set (7 categories × 10
   cases, 3 red / 3 yellow / 4 green each), metrics, agreement between model
   and human labels, error analysis.
5. **Results** — accuracy, per-class precision/recall, comparison to a single-shot
   (non-agent) baseline and a no-RAG baseline.
6. **Discussion** — limitations (hallucination, legal risk, emerging jurisdictions),
   ethics & disclaimers (not legal advice), impact on consumer protection.
7. **Conclusion & Future Work** — drift detection, multi-jurisdiction corpus,
   multimodal (image/OCR) contracts, user studies.
8. **Appendix** — full evaluation dataset, prompt templates, $ and ₹ cost model.

**Suggested venues**: ACL SRW, NLLP (Natural Legal Language Processing, EMNLP
workshop), ICAIL, recent "AI for consumer protection" workshops.

## 4. Measurement for impact statement

Instrument product analytics (see `docs/BUSINESS_MODEL.md`) to report:
- contracts analysed / month · clauses surfaced red-yellow ·
- counter-clauses accepted by counterparties (self-reported) ·
- user-reported savings (₹) — these feed the consumer-protection impact narrative.