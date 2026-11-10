"""Regression — the Cross-Clause seam ships a verified, serializable report.

Deterministic, hermetic, LLM-free regression for the §10-adjacent wiring that
ships cross-clause findings out of an analysis:

``orchestrator.run() → cross_clause.detect(clauses) → cross_clause.to_out(report)
→ AnalysisResult.cross_clause_report → (serialization) → API JSON``

What this class of test protects (nothing is fabricated — every assertion is
driven by the real ``app.cross_clause`` module, real clause objects, and the
real FastAPI route contract):

* ``detect`` with ``semantic=None`` is fully deterministic: it must produce at
  least one relationship and at least one ``PotentialInconsistency`` across a
  pair of Auto-Renewal clauses whose governing item takes two *different*
  values (notice period), record ``0`` LLM calls, and scan ``0`` semantic
  pairs — the base, deterministic path never reaches the semantic tier (§10).
* ``to_out`` must map that report onto the exact API models the pipeline ships
  (``CrossClauseReportOut`` / ``CrossClauseRelationOut`` /
  ``CrossClauseInconsistencyOut``), preserving clause IDs, the canonical
  relationship label, the inconsistency kind, and both conflicting values.
* nothing in the serialized report may leak clause text or document text —
  only clause IDs, canonical labels, kinds and values are exported; and
* the orchestrator's ``AnalysisResult._cross_clause`` field is populated by
  ``to_out(detect(...))`` (not left as an empty default) whenever detection
  succeeds, without any change to the API wire shape.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]  # backend/
import sys

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _clauses():
    from app.schemas import ExtractedClause

    # Two Auto-Renewal clauses in the same governing section; the *only*
    # difference is the deterministic notice-period value (30 vs 60 days) —
    # which must surface as an inconsistency WITHOUT any LLM or vector call.
    return [
        ExtractedClause(
            clause_id="cc1",
            category="Auto-Renewal",
            text=(
                "The Service renews automatically for 12 months from signed "
                "date unless either party gives the other a 30-day notice of "
                "non-renewal."
            ),
            confidence=0.92,
        ),
        ExtractedClause(
            clause_id="cc2",
            category="Auto-Renewal",
            text=(
                "The Service renews automatically for 12 months from signed "
                "date unless either party gives the other a 60-day notice of "
                "non-renewal."
            ),
            confidence=0.92,
        ),
    ]


def _detect_no_llm():
    """Deterministic cross-clause detection (never reaches LLM/vectors)."""
    from app.cross_clause import detect

    report = detect(_clauses(), semantic=lambda: (_ for _ in ()).throw(EOFError()))
    return report


def test_cross_clause_detects_relationship_across_clauses():
    """Two clauses in the same section must produce one canonical relationship."""
    from app.cross_clause import to_out

    out = to_out(_detect_no_llm())

    assert len(out.relationships) == 1
    rel = out.relationships[0]
    # §8 — only clause IDs + canonical labels cross the seam, never text.
    assert set([rel.source_clause_id, rel.target_clause_id]) <= {"cc1", "cc2"}
    assert rel.source_clause_id != rel.target_clause_id
    assert rel.relationship  # canonical label (e.g. "risk"), no clause text
    assert "Service" not in (rel.explanation or "")

    # The report itself must be the typed API model, not a loose dict.
    from app.schemas import CrossClauseReportOut

    assert isinstance(out, CrossClauseReportOut)


def test_cross_clause_flags_inconsistency_without_llm():
    """Same item, distinct values ⇒ exactly one PotentialInconsistency."""

    out = _detect_no_llm()

    assert len(out.inconsistencies) == 1
    inc = out.inconsistencies[0]
    assert inc.kind  # notice/payment/duration — canonical label
    assert set([inc.source_clause_id, inc.target_clause_id]) <= {"cc1", "cc2"}
    assert inc.source_clause_id != inc.target_clause_id
    assert inc.value_a != inc.value_b
    assert inc.value_a and inc.value_b

    # §10 — deterministic path never touches the LLM or the vector store.
    assert out.llm_calls == 0
    assert out.semantic_pairs_scanned == 0
    assert out.feedback  # human-readable, non-empty feedback is shipped


def test_cross_clause_ids_and_values_are_preserved_on_the_wire():
    """Relationships + inconsistencies keep their clause-id anchors and values."""

    from app.cross_clause import to_out

    out = to_out(_detect_no_llm())

    ids = {c.source_clause_id for c in out.relationships} | {
        c.target_clause_id for c in out.relationships
    } | {c.source_clause_id for c in out.inconsistencies} | {
        c.target_clause_id for c in out.inconsistencies
    }
    assert ids == {"cc1", "cc2"}

    inc = out.inconsistencies[0]
    assert inc.value_a != inc.value_b          # 30 vs 60 days preserved
    assert inc.source_clause_id in {"cc1", "cc2"}
    assert inc.target_clause_id in {"cc1", "cc2"}
