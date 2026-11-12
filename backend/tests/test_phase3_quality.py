"""Phase 3 regressions — evidence, cross-clause reasoning, version comparison.

All tests are deterministic and hermetic: no LLM, vector store or database is
contacted. They protect the defects fixed in Phase 3:

* the orchestrator used to reference an undefined ``by_id`` and ran a second
  evidence pass that could never mark a clause supported;
* cross-clause findings were computed but never attached to ``AnalysisResult``;
* conflict values dropped their units (``12 months`` rendered as ``12``);
* version comparison dropped duration units, reported re-categorised sections
  as removed+added, and hard-coded ``unchanged`` attention for identical text.
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]  # backend/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _extracted(clause_id: str, category: str, text: str, risk_level: str = "yellow"):
    from app.schemas import ExtractedClause

    clause = ExtractedClause(
        clause_id=clause_id,
        category=category,
        text=text,
        confidence=0.9,
    )
    object.__setattr__(clause, "risk_level", risk_level)
    object.__setattr__(clause, "risk_score", {"red": 85, "yellow": 55, "green": 15}[risk_level])
    return clause


# --------------------------------------------------------------- orchestrator
def _stub_pipeline(monkeypatch):
    from app import llm
    from app.agents.compare_agent import CompareAgent
    from app.agents.extract_agent import ExtractAgent
    from app.agents.negotiator_agent import NegotiateAgent
    from app.agents.ranker_agent import RankAgent
    from app.schemas import (
        ComparisonResult,
        ExtractorOutput,
        LLMSummaryOutput,
        NegotiatorOutput,
        RankerOutput,
    )

    clauses = [
        _extracted(
            "c1",
            "Auto-Renewal",
            "The Service renews for 12 months unless either party gives 30 days notice.",
        ),
        _extracted(
            "c2",
            "Auto-Renewal",
            "The Service renews for 12 months unless either party gives 60 days notice.",
        ),
    ]

    monkeypatch.setattr(
        ExtractAgent,
        "extract",
        lambda self, text: ExtractorOutput(total_clauses=len(clauses), clauses=clauses),
    )
    monkeypatch.setattr(
        CompareAgent,
        "compare",
        lambda self, clause, top_k=3: ComparisonResult(
            standard_match="match",
            similarity=0.91,
            reference_clause="A fair standard renewal section.",
            reference_category=clause.category,
        ),
    )
    monkeypatch.setattr(
        RankAgent,
        "rank",
        lambda self, clause, comparison, include_reference=True: RankerOutput(
            risk_level="red" if clause.clause_id == "c1" else "green",
            risk_score=85 if clause.clause_id == "c1" else 15,
            risk_percentage=85 if clause.clause_id == "c1" else 15,
            explanation="A plain-English explanation for this section.",
            financial_impact="None identified",
            financial_impact_inr=None,
        ),
    )
    monkeypatch.setattr(
        NegotiateAgent,
        "negotiate",
        lambda self, clause, comparison, rank: NegotiatorOutput(
            negotiation_needed=True,
            suggested_counter_clause="A fairer 30-day notice wording.",
            talking_points=["Ask for a shorter notice period."],
            success_probability=60,
            reasoning="Similar terms are common.",
        ),
    )
    monkeypatch.setattr(
        llm,
        "chat_json_validated",
        lambda *args, **kwargs: (
            LLMSummaryOutput(recommendation="Review the renewal wording.", top_priorities=[]),
            {},
        ),
    )


def test_orchestrator_ships_cross_clause_and_evidence(monkeypatch):
    from app.agents.orchestrator import Orchestrator

    _stub_pipeline(monkeypatch)
    result = Orchestrator().run("A long enough contract body for the pipeline.", "Renewal")

    # Cross-clause findings must actually ride the result (not be discarded).
    assert result.cross_clause.relationships
    assert len(result.cross_clause.inconsistencies) == 1
    inconsistency = result.cross_clause.inconsistencies[0]
    assert inconsistency.kind == "notice period"
    assert inconsistency.value_a == "30 days"
    assert inconsistency.value_b == "60 days"
    assert result.cross_clause.llm_calls == 0

    # Evidence is computed once, after ranking, and reflects real references.
    assert result.evidence.total == 2
    assert result.evidence.reference_backed == 2
    assert result.evidence.supported == 2
    assert result.evidence.by_clause["c1"].reference_credible is True

    # The deterministic summary fallback includes the cross-section conflict
    # instead of returning an empty priority list.
    assert result.summary.top_priorities
    assert any("different notice period" in item for item in result.summary.top_priorities)

    payload = result.model_dump()
    assert payload["cross_clause"]["inconsistencies"][0]["value_a"] == "30 days"
    assert payload["evidence"]["reference_backed"] == 2


# ------------------------------------------------------------------- evidence
def test_analysis_evidence_requires_a_credible_reference():
    from app.evidence import analysis_clause_evidence
    from app.schemas import AnalyzedClause, ComparisonResult

    base = dict(
        clause_id="e1",
        category="Payment",
        text="The fee is payable within 30 days.",
        risk_level="yellow",
        risk_score=55,
        risk_percentage=55,
        explanation="Late fees may apply.",
        confidence=0.9,
    )

    no_reference = AnalyzedClause(**base, comparison=ComparisonResult(similarity=0.0))
    missing = analysis_clause_evidence(no_reference)
    assert missing["reference_present"] is False
    assert missing["reference_backed"] is False
    assert missing["supported"] is False

    credible = AnalyzedClause(
        **base,
        comparison=ComparisonResult(
            standard_match="match",
            similarity=0.88,
            reference_clause="A fair payment section.",
        ),
    )
    supported = analysis_clause_evidence(credible)
    assert supported["reference_backed"] is True
    assert supported["supported"] is True

    inconsistent_band = AnalyzedClause(
        **{**base, "risk_level": "red"},
        comparison=credible.comparison,
    )
    flags = analysis_clause_evidence(inconsistent_band)
    assert flags["risk_consistent"] is False
    assert flags["reference_backed"] is True
    assert flags["supported"] is False


# --------------------------------------------------------------- cross-clause
def test_conflict_values_keep_units_and_understand_equivalence():
    from app.cross_clause import detect

    payment = detect(
        [
            _extracted("p1", "Payment", "The customer must make payment within 30 days."),
            _extracted("p2", "Payment", "The customer must make payment within 60 days."),
        ],
        semantic=None,
    )
    assert len(payment.inconsistencies) == 1
    assert payment.inconsistencies[0].value_a == "30 days"
    assert payment.inconsistencies[0].value_b == "60 days"

    equivalent = detect(
        [
            _extracted("d1", "Auto-Renewal", "The agreement lasts 12 months."),
            _extracted("d2", "Auto-Renewal", "The agreement lasts 1 year."),
        ],
        semantic=None,
    )
    assert equivalent.inconsistencies == []


def test_uncategorised_sections_are_not_linked_to_each_other():
    from app.cross_clause import detect

    report = detect(
        [
            _extracted("o1", "Other", "Governing law is the state of Karnataka."),
            _extracted("o2", "Other", "Notices must be sent by email."),
        ],
        semantic=None,
    )
    assert report.relationships == []


def test_cross_clause_feedback_uses_pair_counts_not_character_counts():
    from app.cross_clause import detect, to_out

    report = to_out(
        detect(
            [
                _extracted("p1", "Payment", "Payment is due within 30 days."),
                _extracted("p2", "Payment", "Payment is due within 60 days."),
            ],
            semantic=None,
        )
    )
    assert "relationship(s)" in report.feedback
    assert "inconsistency(ies)" in report.feedback


# ----------------------------------------------------------- version compare
def test_version_comparison_keeps_duration_units():
    from app.services.version_comparison import detect

    report = detect(
        [_extracted("a1", "Auto-Renewal", "The agreement lasts 12 months.")],
        [_extracted("b1", "Auto-Renewal", "The agreement lasts 24 months.")],
    )
    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.change_type == "modified"
    assert change.previous_value == "12 months"
    assert change.current_value == "24 months"


def test_version_comparison_treats_recategorised_text_as_modified():
    from app.services.version_comparison import detect

    report = detect(
        [_extracted("a1", "Payment", "The fee is payable monthly in advance.")],
        [_extracted("b1", "Other", "The fee is payable monthly in advance.")],
    )
    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.change_type == "modified"
    assert change.clause_id_a == "a1"
    assert change.clause_id_b == "b1"


def test_version_comparison_reports_real_ambiguity():
    from app.services.version_comparison import detect

    report = detect(
        [_extracted("a1", "Payment", "The fee is payable monthly in advance by bank transfer.")],
        [
            _extracted("b1", "Payment", "Customer shall pay all taxes and duties when due."),
            _extracted("b2", "Payment", "Late payment attracts an administrative charge of two percent."),
        ],
    )
    assert len(report.changes) == 3
    ambiguous = [c for c in report.changes if c.change_type == "ambiguous"]
    assert len(ambiguous) == 1
    assert ambiguous[0].clause_id_a == "a1"
    assert {c.change_type for c in report.changes} == {"ambiguous", "added"}
    assert report.ambiguous_pairs == 1


def test_version_comparison_detects_attention_increase_for_identical_text():
    from app.services.version_comparison import detect

    old = [_extracted("a1", "Payment", "The fee is payable monthly.", risk_level="green")]
    new = [_extracted("b1", "Payment", "The fee is payable monthly.", risk_level="red")]
    report = detect(old, new, semantic=None)

    assert report.changes == []  # wording did not move
    evolution = next(e for e in report.attention_evolution if e.clause_id == "b1")
    assert evolution.previous_attention == "green"
    assert evolution.current_attention == "red"
    assert evolution.evolution == "increased"


# --------------------------------------------------------------- store scoring
def test_cosine_distance_maps_to_real_similarity():
    """Chroma cosine distance is ``2 - 2*cos``; the plain ``1 - d`` mapping
    halved every score and clamped most clauses to 0. Pinned to the calibrated
    values measured against real embeddings (d=0.6744 -> cos=0.6628)."""
    from app.stores.chroma_store import ChromaStore

    assert ChromaStore.distance_to_similarity(0.0) == 1.0
    assert ChromaStore.distance_to_similarity(0.6744) == 0.663
    assert ChromaStore.distance_to_similarity(0.3604) == 0.82
    assert ChromaStore.distance_to_similarity(2.0) == 0.0
    assert ChromaStore.distance_to_similarity(5.0) == 0.0


def test_notice_conflict_accepts_apostrophe_wording():
    from app.cross_clause import detect
    from app.services.version_comparison import detect as detect_versions

    cross = detect(
        [
            _extracted("n1", "Other", "The landlord may terminate with 30 days' written notice."),
            _extracted("n2", "Other", "The landlord may terminate with 60 days' written notice."),
        ],
        semantic=None,
    )
    assert len(cross.inconsistencies) == 1
    assert cross.inconsistencies[0].value_a == "30 days"
    assert cross.inconsistencies[0].value_b == "60 days"

    versions = detect_versions(
        [_extracted("a1", "Auto-Renewal", "Either party may end this agreement with 30 days' notice.")],
        [_extracted("b1", "Auto-Renewal", "Either party may end this agreement with 60 days' notice.")],
    )
    change = versions.changes[0]
    assert change.previous_value == "30 days"
    assert change.current_value == "60 days"


# ------------------------------------------------------------- relational store
def test_deleting_a_contract_removes_its_clauses():
    """SQLite needs ``PRAGMA foreign_keys=ON`` before ``ON DELETE CASCADE``
    works; without it deleted contracts left clause rows behind (which showed
    up as duplicate sections when a document id was reused)."""
    from sqlalchemy import func

    from app.database import SessionLocal, init_db
    from app.models import Clause, Contract
    from app.services.contract_service import delete_contract

    init_db()
    session = SessionLocal()
    try:
        contract = Contract(id="cascade-check", name="Cascade Check", total_clauses=1)
        session.add(contract)
        session.add(
            Clause(
                contract_id="cascade-check",
                clause_index="clause_1",
                category="Payment",
                text="Payment is due within 30 days.",
            )
        )
        session.commit()
        assert session.query(Clause).filter_by(contract_id="cascade-check").count() == 1
        before = session.query(func.count(Clause.id)).scalar()

        delete_contract(session, contract)

        assert session.query(Clause).filter_by(contract_id="cascade-check").count() == 0
        assert session.query(func.count(Clause.id)).scalar() == before - 1
    finally:
        session.rollback()
        session.query(Clause).filter_by(contract_id="cascade-check").delete()
        session.query(Contract).filter_by(id="cascade-check").delete()
        session.commit()
        session.close()


# ------------------------------------------------------- cached payload shape
def test_normalize_payload_fills_phase3_fields_for_old_contracts():
    from app.services.contract_service import normalize_payload

    old_payload = {
        "document_id": "old-doc",
        "document_name": "Old Contract",
        "clauses": [
            {
                "clause_id": "x1",
                "category": "Payment",
                "text": "The fee is payable within 30 days.",
                "risk_level": "red",
                "risk_score": 85,
                "comparison": {
                    "standard_match": "match",
                    "similarity": 0.9,
                    "reference_clause": "A fair payment section.",
                },
            }
        ],
    }

    payload = normalize_payload(old_payload)

    assert payload["cross_clause"]["relationships"] == []
    assert payload["cross_clause"]["inconsistencies"] == []
    assert payload["evidence"]["total"] == 1
    assert payload["evidence"]["reference_backed"] == 1
    assert payload["evidence"]["supported"] == 1
    assert payload["risk_summary"]["red_count"] == 1
    assert payload["risk_summary"]["overall_risk"] == "HIGH"
    assert payload["summary"]["total_analyzed"] == 1
    assert payload["clauses"][0]["talking_points"] == []
    assert payload["clauses"][0]["comparison"]["notes"] == ""


def test_normalize_payload_recomputes_cross_clause_for_old_contracts():
    from app.services.contract_service import normalize_payload

    old_payload = {
        "document_id": "old-doc-2",
        "document_name": "Old Renewal Contract",
        "clauses": [
            {
                "clause_id": "r1",
                "category": "Auto-Renewal",
                "text": "The Service renews for 12 months unless either party gives 30 days notice.",
                "risk_level": "yellow",
                "risk_score": 55,
                "comparison": {
                    "standard_match": "match",
                    "similarity": 0.8,
                    "reference_clause": "A fair renewal section.",
                },
            },
            {
                "clause_id": "r2",
                "category": "Auto-Renewal",
                "text": "The Service renews for 12 months unless either party gives 60 days notice.",
                "risk_level": "red",
                "risk_score": 80,
                "comparison": {
                    "standard_match": "worse",
                    "similarity": 0.6,
                    "reference_clause": "A fair renewal section.",
                },
            },
        ],
    }

    payload = normalize_payload(old_payload)

    assert payload["cross_clause"]["relationships"]
    assert len(payload["cross_clause"]["inconsistencies"]) == 1
    assert payload["cross_clause"]["inconsistencies"][0]["value_a"] == "30 days"
    assert payload["cross_clause"]["inconsistencies"][0]["value_b"] == "60 days"
    assert payload["evidence"]["reference_backed"] == 2
