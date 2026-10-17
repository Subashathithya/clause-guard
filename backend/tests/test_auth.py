"""Auth endpoint tests: register, login, /auth/me, token enforcement."""
from app.database import SessionLocal
from app.models import User


def test_register_login_me(client):
    resp = client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "password123", "full_name": "Ann"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "a@b.com"
    assert body["user"]["quota"]["monthly_limit"] >= 1
    token = body["access_token"]
    assert token

    # duplicate email rejected
    dup = client.post("/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert dup.status_code == 409

    # invalid email rejected by validation
    bad = client.post("/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert bad.status_code == 422

    # weak password rejected
    weak = client.post("/auth/register", json={"email": "x@b.com", "password": "short"})
    assert weak.status_code == 422

    # login is case-insensitive on email
    login = client.post("/auth/login", json={"email": "A@B.COM", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["access_token"]

    # wrong password rejected
    wrong = client.post("/auth/login", json={"email": "a@b.com", "password": "wrongpass1"})
    assert wrong.status_code == 401

    # /auth/me with token
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"

    # /auth/me without token
    noauth = client.get("/auth/me")
    assert noauth.status_code == 401


def test_register_persists_user(client):
    client.post("/auth/register", json={"email": "b@b.com", "password": "password123"})
    with SessionLocal() as session:
        user = session.query(User).filter_by(email="b@b.com").first()
        assert user is not None
        assert user.hashed_password
        assert user.hashed_password != "password123"  # hashed, never plaintext


def test_user_scoped_analyses(client, monkeypatch):
    """Authenticated users only see their own records."""
    from app.api.routes import analysis
    from app.database import SessionLocal
    from app.models import Contract

    def fake_run(text, document_name="Unnamed Document"):
        return _fake_api_result(document_name)

    monkeypatch.setattr(analysis, "run_orchestrator", fake_run)

    alice = client.post(
        "/auth/register", json={"email": "alice@b.com", "password": "password123"}
    ).json()
    alice_token = alice["access_token"]
    auth = {"Authorization": f"Bearer {alice_token}"}

    resp = client.post(
        "/analyze", json={"text": "D" * 90, "document_name": "Alice Doc"}, headers=auth
    )
    assert resp.status_code == 200
    alice_doc = resp.json()["document_id"]
    assert resp.json()["user_id"] == alice["user"]["id"]

    # guest analysis (user_id NULL) must NOT show up for Alice
    guest = client.post(
        "/analyze", json={"text": "E" * 90, "document_name": "Guest Doc"}
    )
    guest_doc = guest.json()["document_id"]

    listed = client.get("/contracts", headers=auth).json()["contracts"]
    ids = [c["document_id"] for c in listed]
    assert alice_doc in ids
    assert guest_doc not in ids

    # Alice cannot fetch or delete the guest document
    assert client.get(f"/contracts/{guest_doc}", headers=auth).status_code == 404
    assert client.delete(f"/contracts/{guest_doc}", headers=auth).status_code == 404

    with SessionLocal() as session:
        assert session.query(Contract).filter_by(user_id=alice["user"]["id"]).count() == 1


def _fake_api_result(document_name: str = "Test Doc"):
    from app.schemas import (
        AnalysisResult,
        AnalysisSummary,
        AnalyzedClause,
        ComparisonResult,
        RiskSummary,
    )

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