"""API-level tests using FastAPI's TestClient.

The orchestration LLM calls are stubbed at the router layer; Chroma writes are
stubbed in conftest so tests never touch real infrastructure. The relational
store is exercised for real against a throwaway SQLite file.
"""
import pytest

from app.api.routes import analysis
from app.schemas import AnalysisResult, AnalysisSummary, AnalyzedClause, ComparisonResult, RiskSummary


def _fake_result(document_name: str = "Test Doc") -> AnalysisResult:
    return AnalysisResult(
        document_name=document_name,
        total_clauses=1,
        risk_summary=RiskSummary(
            red_count=1, yellow_count=0, green_count=0,
            overall_risk="HIGH", average_risk_score=90.0,
        ),
        clauses=[
            AnalyzedClause(
                clause_id="c1",
                category="Payment",
                text="The company may change any fee at any time.",
                risk_level="red",
                risk_score=90,
                risk_percentage=90,
                explanation="Unilateral price changes.",
                confidence=0.9,
                comparison=ComparisonResult(similarity=0.3, standard_match="no"),
                financial_impact="High",
                negotiation_needed=True,
                suggested_counter_clause="Fees change only with 30 days notice.",
                talking_points=["Point"],
                success_probability=60,
                reasoning="Fair alternative exists.",
            )
        ],
        summary=AnalysisSummary(
            total_analyzed=1, red_flags=1,
            recommendation="Renegotiate the payment clause.",
            top_priorities=["Payment"],
        ),
        status="SUCCESS",
    )


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "API is running"
    assert body["pipeline"] == ["Extractor", "Comparator", "Ranker", "Negotiator"]


def test_analyze_rejects_short_text(client):
    resp = client.post("/analyze", json={"text": "short", "document_name": "x"})
    assert resp.status_code == 422
    assert "too short" in resp.json()["detail"].lower()


def test_analyze_rejects_empty_text(client):
    resp = client.post("/analyze", json={"text": "   ", "document_name": "x"})
    assert resp.status_code == 422


def test_analyze_success(client, monkeypatch):
    def fake_run(text, document_name="Unnamed Document"):
        return _fake_result(document_name)

    monkeypatch.setattr(analysis, "run_orchestrator", fake_run)

    resp = client.post(
        "/analyze",
        json={"text": "A" * 80, "document_name": "Contract A"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"]
    assert body["risk_summary"]["overall_risk"] == "HIGH"
    assert body["clauses"][0]["reasoning"]
    assert body["quota_remaining"] >= 0


def test_analyze_persists_contract_row(client, monkeypatch):
    from app.database import SessionLocal
    from app.models import Clause, Contract

    def fake_run(text, document_name="Unnamed Document"):
        return _fake_result(document_name)

    monkeypatch.setattr(analysis, "run_orchestrator", fake_run)

    resp = client.post("/analyze", json={"text": "B" * 90, "document_name": "Recorded Doc"})
    assert resp.status_code == 200
    document_id = resp.json()["document_id"]

    with SessionLocal() as session:
        contract = session.query(Contract).filter_by(id=document_id).first()
        assert contract is not None
        assert contract.name == "Recorded Doc"
        assert contract.user_id is None
        assert contract.total_clauses == 1
        assert contract.source == "paste"
        assert session.query(Clause).filter_by(contract_id=document_id).count() == 1


def test_analyze_then_list_fetch_delete(client, monkeypatch):
    from app.database import SessionLocal
    from app.models import Contract

    def fake_run(text, document_name="Unnamed Document"):
        return _fake_result(document_name)

    monkeypatch.setattr(analysis, "run_orchestrator", fake_run)

    resp = client.post("/analyze", json={"text": "C" * 90, "document_name": "Scoped Doc"})
    document_id = resp.json()["document_id"]

    listed = client.get("/contracts").json()
    assert any(c["document_id"] == document_id for c in listed["contracts"])

    fetched = client.get(f"/contracts/{document_id}")
    assert fetched.status_code == 200
    assert fetched.json()["risk_summary"]["overall_risk"] == "HIGH"
    assert fetched.json()["clauses"][0]["comparison"]["similarity"] == 0.3

    deleted = client.delete(f"/contracts/{document_id}")
    assert deleted.status_code == 200
    with SessionLocal() as session:
        assert session.query(Contract).filter_by(id=document_id).first() is None


def test_upload_rejects_short_text(client, monkeypatch):
    def fake_run(text, document_name="Unnamed Document"):
        return _fake_result(document_name)

    monkeypatch.setattr(analysis, "run_orchestrator", fake_run)

    resp = client.post(
        "/upload",
        files={"file": ("tiny.txt", b"tiny", "text/plain")},
        data={"document_name": "Tiny"},
    )
    assert resp.status_code == 422


def test_fair_clauses_new_format(client):
    resp = client.get("/fair-clauses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "2.0"
    assert set(body["by_category"]) == {
        "Payment", "Auto-Renewal", "Liability", "Data Privacy", "Dispute", "Warranty", "Other"
    }
    assert body["count"] >= 150
    assert "samples_by_category" in body


def test_stats_and_history(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert "total_contracts" in resp.json()
    assert "total_clauses" in resp.json()

    resp = client.get("/history")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 0