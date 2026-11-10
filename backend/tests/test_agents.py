"""Agent unit tests.

Deterministic: every LLM call and Chroma query is stubbed, so tests never hit
the network.
"""
import pytest

from app import llm


# ---------------------------------------------------------------- Extractor
class TestExtractAgent:
    def test_empty_text_returns_no_clauses(self):
        from app.agents.extract_agent import ExtractAgent

        out = ExtractAgent().extract("   ")
        assert out.total_clauses == 0
        assert out.clauses == []

    def test_returns_parsed_clauses(self, monkeypatch):
        from app.agents.extract_agent import ExtractAgent
        from app.schemas import LLMExtractorOutput

        payload = {
            "clauses": [
                {"clause_id": "c1", "category": "Payment", "text": "All fees are itemised.", "confidence": 0.95},
                {"clause_id": "c2", "category": "Auto-Renewal & Termination", "text": "Auto renews yearly.", "confidence": 0.8},
            ]
        }
        monkeypatch.setattr(
            llm,
            "chat_json_validated",
            lambda *a, **k: (LLMExtractorOutput.model_validate(payload), payload),
        )

        out = ExtractAgent().extract("Sample contract text long enough to be plausible here.")
        assert out.total_clauses == 2
        assert out.clauses[0].category == "Payment"
        # fuzzy category that contains a canonical name must map to it
        assert out.clauses[1].category == "Auto-Renewal"

    def test_llm_failure_degrades_gracefully(self, monkeypatch):
        from app.agents.extract_agent import ExtractAgent

        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(llm, "chat_json_validated", boom)
        out = ExtractAgent().extract("Some real contract text here with enough length.")
        assert out.total_clauses == 0


# ---------------------------------------------------------------- Comparator
class TestCompareAgent:
    def test_maps_db_result(self, monkeypatch):
        from app import db
        from app.agents.compare_agent import CompareAgent
        from app.schemas import ExtractedClause

        monkeypatch.setattr(
            db,
            "compare_to_standard",
            lambda text, cat, top_k=3: {
                "standard_match": "yes",
                "similarity": 0.88,
                "reference_clause": "A fair payment clause.",
                "reference_category": "Payment",
                "notes": "",
            },
        )
        clause = ExtractedClause(clause_id="c1", category="Payment", text="Text.", confidence=0.9)
        res = CompareAgent().compare(clause)
        assert res.standard_match == "yes"
        assert res.similarity == 0.88
        assert res.reference_category == "Payment"

    def test_db_failure_does_not_raise(self, monkeypatch):
        from app import db
        from app.agents.compare_agent import CompareAgent
        from app.schemas import ExtractedClause

        monkeypatch.setattr(db, "compare_to_standard", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        clause = ExtractedClause(clause_id="c1", category="Other", text="Text.", confidence=0.9)
        res = CompareAgent().compare(clause)
        assert "Comparison unavailable" in res.notes


# ---------------------------------------------------------------- Ranker
def test_provisional_risk_thresholds():
    from app.agents.ranker_agent import _provisional_risk

    assert _provisional_risk(0.90) == "green"
    assert _provisional_risk(0.85) == "green"
    assert _provisional_risk(0.75) == "yellow"
    assert _provisional_risk(0.70) == "yellow"
    assert _provisional_risk(0.40) == "red"


class TestRankAgent:
    def test_llm_rank_used(self, monkeypatch):
        from app.agents.ranker_agent import RankAgent
        from app.schemas import ComparisonResult, ExtractedClause, LLMRankOutput

        def fake_chat_json(messages, **k):
            payload = {
                "risk_level": "red",
                "risk_score": 90,
                "explanation": "This clause lets the company change prices freely.",
                "financial_impact": "Up to RS 5,000 extra per year.",
                "financial_impact_inr": 5000,
            }
            return LLMRankOutput.model_validate(payload), payload

        monkeypatch.setattr(llm, "chat_json_validated", fake_chat_json)
        clause = ExtractedClause(clause_id="c1", category="Payment", text="Company may change any fee anytime.", confidence=0.9)
        comp = ComparisonResult(similarity=0.45)
        out = RankAgent().rank(clause, comp)
        assert out.risk_level == "red"
        assert out.risk_score == 90
        assert out.financial_impact_inr == 5000

    def test_fallback_on_llm_failure(self, monkeypatch):
        from app.agents.ranker_agent import RankAgent
        from app.schemas import ComparisonResult, ExtractedClause

        monkeypatch.setattr(llm, "chat_json_validated", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
        clause = ExtractedClause(clause_id="c1", category="Dispute", text="Binding arbitration mandatory.", confidence=0.9)
        comp = ComparisonResult(similarity=0.40)
        out = RankAgent().rank(clause, comp)
        assert out.risk_level == "red"        # <70% similarity prior
        assert out.risk_score >= 67


# ---------------------------------------------------------------- Negotiator
class TestNegotiateAgent:
    def test_green_clause_no_negotiation(self):
        from app.agents.negotiator_agent import NegotiateAgent
        from app.schemas import ComparisonResult, ExtractedClause, RankerOutput

        clause = ExtractedClause(clause_id="c1", category="Payment", text="Fees disclosed.", confidence=0.9)
        out = NegotiateAgent().negotiate(
            clause,
            ComparisonResult(similarity=0.9),
            RankerOutput(risk_level="green", risk_score=20),
        )
        assert out.negotiation_needed is False
        assert "No negotiation needed" in out.suggested_counter_clause

    def test_red_clause_calls_llm(self, monkeypatch):
        from app.agents.negotiator_agent import NegotiateAgent
        from app.schemas import ComparisonResult, ExtractedClause, LLMNegotiationOutput, RankerOutput

        def fake(messages, **k):
            payload = {
                "negotiation_needed": True,
                "suggested_counter_clause": "Fees may only change with 30 days written notice.",
                "talking_points": ["Point A", "Point B"],
                "success_probability": 70,
                "reasoning": "A large competitor already accepts this wording.",
            }
            return LLMNegotiationOutput.model_validate(payload), payload

        monkeypatch.setattr(llm, "chat_json_validated", fake)
        clause = ExtractedClause(clause_id="c1", category="Payment", text="Company may change any fee anytime.", confidence=0.9)
        out = NegotiateAgent().negotiate(
            clause,
            ComparisonResult(similarity=0.4),
            RankerOutput(risk_level="red", risk_score=90),
        )
        assert out.negotiation_needed is True
        assert out.success_probability == 70
        assert "receives" in out.suggested_counter_clause or "notice" in out.suggested_counter_clause
        assert out.talking_points == ["Point A", "Point B"]


# ---------------------------------------------------------------- Orchestrator
class TestOrchestrator:
    def test_full_pipeline_with_stubbed_llm(self, monkeypatch):
        """End-to-end orchestration; stubbed LLM + stubbed RAG, real agent logic."""
        from app import db
        from app.agents.orchestrator import Orchestrator

        monkeypatch.setattr(
            db,
            "compare_to_standard",
            lambda text, cat, top_k=3: {
                "standard_match": "maybe" if cat == "Payment" else "yes",
                "similarity": 0.95 if cat != "Payment" else 0.45,
                "reference_clause": "A fair reference clause of a reasonable length.",
                "reference_category": cat,
                "notes": "",
            },
        )

        calls = {"n": 0}

        def fake_chat_json(messages, **k):
            calls["n"] += 1
            user = messages[-1]["content"]
            if user.startswith("Use EXACTLY one of these categories"):
                return {
                    "clauses": [
                        {"clause_id": "c1", "category": "Payment",
                         "text": "The company may change any fee at any time without notice.", "confidence": 0.9},
                        {"clause_id": "c2", "category": "Warranty",
                         "text": "The product is covered by a 24-month warranty.", "confidence": 0.9},
                        {"clause_id": "c3", "category": "Data Privacy",
                         "text": "Your data is shared with all partners for marketing.", "confidence": 0.9},
                    ]
                }
            if 'risk_level' in user:
                level = "red" if "c1" in user or "change any fee" in user or "marketing" in user else "green"
                return {"risk_level": level, "risk_score": 90 if level == "red" else 15,
                        "explanation": "Concise explanation.", "financial_impact": "High",
                        "financial_impact_inr": 5000}
            if "PRIORITY:" in user:
                return {"negotiation_needed": True,
                        "suggested_counter_clause": "Fees may only change with 30 days written notice.",
                        "talking_points": ["P1", "P2"], "success_probability": 65,
                        "reasoning": "Fair alternative exists and is widely accepted."}
            return {"recommendation": "Renegotiate risky clauses.", "top_priorities": ["Payment"]}

        def fake_validated(messages, *, schema=None, **k):
            payload = fake_chat_json(messages, **k)
            try:
                return schema.model_validate(payload), payload
            except Exception:  # noqa: BLE001 - exercise the caller's fallback
                return None, payload

        monkeypatch.setattr(llm, "chat_json_validated", fake_validated)

        result = Orchestrator().run(
            "This is a sample contract with payment, warranty and privacy clauses that is long enough.",
            document_name="Unit Contract",
        )
        assert result.status == "SUCCESS"
        assert result.total_clauses == 3
        assert result.risk_summary.red_count >= 1
        assert result.summary.recommendation
        flagged = [c for c in result.clauses if c.risk_level == "red"]
        assert flagged and all(c.suggested_counter_clause for c in flagged)
        assert any(c.reasoning for c in flagged)

    def test_no_clauses_short_circuits(self, monkeypatch):
        from app import llm
        from app.agents.orchestrator import Orchestrator
        from app.schemas import LLMExtractorOutput

        monkeypatch.setattr(
            llm,
            "chat_json_validated",
            lambda *a, **k: (LLMExtractorOutput(clauses=[]), {"clauses": []}),
        )
        result = Orchestrator().run("Short text.", document_name="Empty")
        assert result.status == "NO_CLAUSES"

    def test_extractor_crash_returns_error_status(self, monkeypatch):
        from app.agents.extract_agent import ExtractAgent
        from app.agents.orchestrator import Orchestrator

        monkeypatch.setattr(ExtractAgent, "extract", lambda self, text: (_ for _ in ()).throw(RuntimeError("crash")))
        result = Orchestrator().run("Some long enough contract text here for the pipeline.", "Crash Doc")
        assert result.status == "EXTRACTOR_ERROR"
        assert result.agent_trace[0]["agent"] == "Extractor"