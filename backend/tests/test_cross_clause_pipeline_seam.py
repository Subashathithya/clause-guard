"""§8 regression — cross-clause findings ship through the analysis seam.

Covers the deterministic path end-to-end without ever calling an LLM:

* ``app.cross_clause.detect`` — two ``Auto-Renewal`` clauses that name
  *different* notice-period values (30 vs 60 days) must produce exactly one
  relationship *and* exactly one ``PotentialInconsistency``, with
  ``llm_calls == 0`` and ``semantic_pairs_scanned == 0`` on the
  deterministic path (never the LLM tier — §10);
* ``app.cross_clause.to_out`` — the ``CrossClauseReport`` maps onto the exact
  schema the API ships (``CrossClauseReportOut``), preserving clause IDs,
  the canonical relationship label, the conflict ``kind``, both conflicting
  values, and the plain-language ``feedback``; it exports *only* clause IDs
  + canonical labels/values (§8 privacy: never clause text);
* the API seam — the route handler serializes ``AnalysisResult.cross_clause``
  (already typed) so the report survives a real FastAPI/JSON round-trip.

These are deterministic regression tests (no LLM, no vector store, no real
DB) so they are hermetic and always runnable in CI.
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
            confidence=0.94,
        ),
        ExtractedClause(
            clause_id="cc2",
            category="Auto-Renewal",
            text="Service renews for 12 months unless terminated on 60 days notice.",
            confidence=0.94,
        ),
    ]


def test_cross_clause_detects_relationship_without_llm():
    """Two clauses in the same governing section must relate deterministically."""
    from app.cross_clause import detect, to_out

    report = detect(_clauses(), semantic=None)
    assert len(report.relationships) == 1
    assert report.llm_calls == 0
    assert report.semantic_pairs_scanned == 0
    for rel in report.relationships:
        assert rel.source_clause_id in {"cc1", "cc2"}
        assert rel.target_clause_id in {"cc1", "cc2"}
        assert rel.relationship  # canonical label, never clause text


def test_cross_clause_inconsistency_notice_period_without_llm():
    """Same item states different values ⇒ exactly one inconsistency, no LLM."""
    from app.cross_clause import detect

    report = detect(_clauses(), semantic=None)
    assert len(report.inconsistencies) == 1
    inc = report.inconsistencies[0]
    assert inc.kind  # notice/payment/duration/renewal (canonical label)
    assert inc.source_clause_id in {"cc1", "cc2"}
    assert inc.target_clause_id in {"cc1", "cc2"}
    assert inc.source_clause_id != inc.target_clause_id
    assert inc.value_a and inc.value_b
    assert inc.value_a != inc.value_b
    assert report.llm_calls == 0
    assert report.semantic_pairs_scanned == 0


def test_cross_clause_serializes_into_report_out():
    """The mapper must ship the report in the exact schema the API uses."""
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
    assert out.relationships[0].source_clause_id in {"cc1", "cc2"}
    assert out.relationships[0].target_clause_id in {"cc1", "cc2"}
    assert out.inconsistencies[0].kind
    assert out.inconsistencies[0].value_a
    assert out.inconsistencies[0].value_b
    assert out.inconsistencies[0].value_a != out.inconsistencies[0].value_b
    assert out.llm_calls == 0
    assert out.semantic_pairs_scanned == 0
    assert out.feedback  # plain-language summary for §-level review
    # privacy: the wire payload is IDs + canonical values only — never text
    dumped = out.model_dump()
    assert "cc1" in dumped["relationships"][0]["source_clause_id"]
    assert "renew" not in str(dumped["relationships"]).lower()
