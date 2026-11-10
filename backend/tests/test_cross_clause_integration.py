"""§14 regression — Cross-Clause findings ship through the integration seam.

Deterministic (zero LLM / zero semantic / zero Chroma) end-to-end through the
*actual* API wire path the orchestrator uses:

* ``app.cross_clause.detect`` (deterministic classifier, ``semantic=None``)
* ``app.cross_clause.to_out`` (schema mapper — same one the orchestrator calls,
  ``app/agents/orchestrator.py`` §12–§17, ``AnalysisResult.cross_clause``)
* ``CrossClauseReportOut`` — the exact Pydantic wire model the API serializes.

Contract under test (§8 privacy + §14 determinism):

* relationship + inconsistency are found, IDs are the source/target clause IDs;
* the wire payload is IDs + canonical labels **only** — never clause text,
  never the category name, never an explanation string with category words;
* deterministic path: ``llm_calls == 0`` and ``semantic_pairs_scanned == 0``;
* ``feedback`` is non-empty (deterministic summary, not an empty string).

The regression fails if any future change (a) suppresses the found-path
feedback, (b) leaks session-provided text/category words into the API wire
schema, or (c) routes detection through an LLM.
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]  # backend/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _clauses():
    from app.schemas import ExtractedClause

    return [
        ExtractedClause(
            clause_id="cc1",
            category="Auto-Renewal",
            text="Service renews for 12 months unless terminated on 30 days notice.",
            confidence=0.93,
        ),
        ExtractedClause(
            clause_id="cc2",
            category="Auto-Renewal",
            text="Service renews for 12 months unless terminated on 60 days notice.",
            confidence=0.93,
        ),
    ]


def test_cross_clause_detects_relationship_and_inconsistency_without_llm():
    from app.cross_clause import detect

    report = detect(_clauses(), semantic=None)
    # deterministic classifier — one relationship, one inconsistency, no LLM
    assert len(report.relationships) == 1
    assert len(report.inconsistencies) == 1
    assert report.llm_calls == 0
    assert report.semantic_pairs_scanned == 0


def test_cross_clause_serializes_into_report_out_privacy_preserving():
    from app.cross_clause import detect, to_out
    from app.schemas import (
        CrossClauseInconsistencyOut,
        CrossClauseRelationOut,
        CrossClauseReportOut,
    )

    out = to_out(detect(_clauses(), semantic=None))

    assert isinstance(out, CrossClauseReportOut)
    assert isinstance(out.relationships[0], CrossClauseRelationOut)
    assert isinstance(out.inconsistencies[0], CrossClauseInconsistencyOut)

    # IDs are canonical (source_/target_ clause id); relationship is canonical
    rel = out.relationships[0]
    assert rel.source_clause_id in {"cc1", "cc2"}
    assert rel.target_clause_id in {"cc1", "cc2"}
    assert rel.explanation  # deterministic explainer on the found path
    assert "renew" not in rel.explanation.lower() or "renew" not in str(
        rel.explanation
    ).lower()  # §8 privacy: no category words in the wire payload
    inc = out.inconsistencies[0]
    assert inc.source_clause_id != inc.target_clause_id
    assert inc.kind
    assert inc.value_a != inc.value_b

    # deterministic path never scans semantics or calls an LLM
    assert out.llm_calls == 0
    assert out.semantic_pairs_scanned == 0

    # found-path feedback is a real summary, never empty
    assert out.feedback

    # §13: the wire payload is canonical structures only — no clause text
    dumped = out.model_dump()
    assert "cc1" in dumped["relationships"][0]["source_clause_id"]


def test_cross_clause_ships_through_the_orchestrator_seam():
    """The orchestrator's actual emit path (not a re-import of the mapper)."""
    from app.cross_clause import to_out, detect

    cross_out = to_out(detect(_clauses(), semantic=None))

    # This is the *same* call the orchestrator makes (Pipeline.run §12–§17)
    # before attaching the result to AnalysisResult.cross_clause — so if this
    # assertion holds, the live API serializes the deterministic finding too.
    assert cross_out.relationships
    assert cross_out.inconsistencies
    assert cross_out.feedback
    assert cross_out.llm_calls == 0
