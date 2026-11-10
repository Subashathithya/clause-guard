"""Hermetic seam test for the version-comparison engine + its wire mapping.

Mirrors ``test_cross_clause_pipeline_seam.py``: verifies the deterministic
path end-to-end without an LLM, a vector store, or a real DB.

* ``app.services.version_comparison.detect`` — two ``Termination`` clauses whose
  written-notice term changed (``30 days`` -> ``60 days``) must yield exactly
  one ``modified`` change with the literal previous/current values; identical
  clauses must NOT produce a change; the deterministic path must report
  ``llm_calls == 0`` and ``semantic_pairs_scanned == 0``.
* ``app.services.version_comparison.to_out`` — maps the engine report onto the
  exact wire schema the API ships (``VersionComparisonReportOut``): clause
  IDs, canonical categories, canonical change labels, literal values only —
  never raw clause text, never an LLM verdict.
* the attention-evolution seam — attention bands ride the same report so
  /drift can surface "this term now demands more attention".

Hermetic by construction: every assert runs with zero LLM calls.
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]  # backend/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _extracted_a():
    from app.schemas import ExtractedClause

    return [
        ExtractedClause(
            clause_id="a1",
            category="Termination",
            text="Either party may terminate with 30 days written notice.",
            confidence=0.9,
        ),
        ExtractedClause(
            clause_id="a2",
            category="Confidentiality",
            text="Confidential data must be returned within 30 days of termination.",
            confidence=0.9,
        ),
    ]


def _extracted_b():
    from app.schemas import ExtractedClause

    return [
        ExtractedClause(
            clause_id="b1",
            category="Termination",
            text="Either party may terminate with 60 days written notice.",
            confidence=0.9,
        ),
        ExtractedClause(
            clause_id="b2",
            category="Confidentiality",
            text="Confidential data must be returned within 30 days of termination.",
            confidence=0.9,
        ),
    ]


def test_version_comparison_golden_30_to_60_days():
    """The gold scenario: 30 days -> 60 days is one modified change."""
    from app.services.version_comparison import detect

    report = detect(_extracted_a(), _extracted_b(), semantic=None)

    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.change_type == "modified"
    assert change.category == "Termination"
    assert "30" in change.previous_value
    assert "60" in change.current_value
    assert change.clause_id_a == "a1"
    assert change.clause_id_b == "b1"
    # the identical confidentiality clause does not produce a change
    assert "a2" not in {c.clause_id_a for c in report.changes}

    # deterministic path — no semantic scan, no LLM
    assert report.llm_calls == 0
    assert report.semantic_pairs_scanned == 0


def test_version_comparison_maps_exactly_onto_wire_schema():
    """to_out must ship the exact VersionComparisonReportOut wire contract."""
    from app.schemas import (
        AttentionEvolutionOut,
        VersionChangeOut,
        VersionComparisonReportOut,
    )
    from app.services.version_comparison import detect, to_out

    out = to_out(detect(_extracted_a(), _extracted_b(), semantic=None))

    assert isinstance(out, VersionComparisonReportOut)
    assert isinstance(out.changes[0], VersionChangeOut)
    assert out.changes[0].clause_id_a == "a1"
    assert out.changes[0].clause_id_b == "b1"
    assert out.changes[0].change_type == "modified"
    assert "30" in out.changes[0].previous_value
    assert "60" in out.changes[0].current_value

    # wire payload carries clause ids + canonical values — never clause text,
    # never an LLM verdict
    dumped = out.model_dump()
    assert "Either party may terminate" not in str(dumped)
    assert "Confidential data must be returned" not in str(dumped)
    assert out.llm_calls == 0

    # attention evolution rides the same seam, typed to the wire schema
    assert isinstance(out.attention_evolution[0], AttentionEvolutionOut)
    for ev in out.attention_evolution:
        assert ev.clause_id in {"a1", "b1", "a2", "b2"}
        assert ev.evolution in {"unchanged", "increased", "decreased", "new", "removed"}
        assert ev.previous_attention in {"red", "yellow", "green", "unknown"}
    # the golden pair must appear with a literal, deterministic evolution label
    terminal_ids = {ev.clause_id for ev in out.attention_evolution}
    assert "a1" in terminal_ids or "b1" in terminal_ids
