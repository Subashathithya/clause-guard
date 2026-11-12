"""Phase 4: user-owned dates, reminders, bookmarks and checklists.

These tests run against the throwaway SQLite store and never call an LLM. A
contract is written directly with the persistence helper (the analysis pipeline
is covered elsewhere) so each case can focus on tracking behaviour.
"""
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Bookmark, ChecklistItem, Contract, ContractDate
from app.schemas import (
    AnalysisResult,
    AnalysisSummary,
    AnalyzedClause,
    ComparisonResult,
    RiskSummary,
)
from app.services import contract_service

RELATIVE_CLAUSE = "Late payment is charged a fee within 30 days of the due date."


def _result() -> AnalysisResult:
    def clause(cid, category, text, level, score, points, counter="", negotiation=None):
        return AnalyzedClause(
            clause_id=cid,
            category=category,
            text=text,
            risk_level=level,
            risk_score=score,
            risk_percentage=score,
            explanation=f"{category} terms need attention.",
            confidence=0.9,
            comparison=ComparisonResult(
                standard_match="partial", similarity=0.5, reference_category=category
            ),
            financial_impact="Possible cost",
            financial_impact_inr=10000 if level != "green" else None,
            negotiation_needed=(level != "green") if negotiation is None else negotiation,
            suggested_counter_clause=counter,
            talking_points=points,
            success_probability=60,
        )

    clauses = [
        clause(
            "clause_1",
            "Payment",
            "The fee may be increased at any time without notice.",
            "red",
            90,
            ["Ask for a 60-day notice period.", "Cap annual increases."],
            "Increase only with 60 days' written notice.",
        ),
        clause(
            "clause_2",
            "Auto-Renewal",
            "The term renews on 1 January 2027 and the fee is due on 15 February 2027.",
            "yellow",
            55,
            ["Confirm the renewal date in writing."],
            "Renew only on mutual written agreement.",
        ),
        clause("clause_3", "Warranty", RELATIVE_CLAUSE, "green", 20, []),
    ]
    return AnalysisResult(
        document_name="Tracking Contract",
        total_clauses=len(clauses),
        risk_summary=RiskSummary(
            red_count=1,
            yellow_count=1,
            green_count=1,
            overall_risk="HIGH",
            average_risk_score=55.0,
            total_financial_exposure_inr=20000,
        ),
        clauses=clauses,
        summary=AnalysisSummary(
            total_analyzed=3, red_flags=1, warnings=1, safe=1, top_priorities=[]
        ),
    )


def _register(client, email: str) -> dict:
    resp = client.post(
        "/auth/register", json={"email": email, "password": "password123", "full_name": "Tester"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"user": body["user"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}


def _make_contract(owner_id, doc_id: str, name: str = "Tracking Contract") -> None:
    with SessionLocal() as session:
        existing = session.get(Contract, doc_id)
        if existing is not None:
            contract_service.delete_contract(session, existing)
    with SessionLocal() as session:
        contract_service.persist_contract(
            session,
            result=_result(),
            document_id=doc_id,
            name=name,
            text="Contract body used for tracking tests.",
            source="paste",
            user_id=owner_id,
        )


def _count(model, doc_id: str) -> int:
    with SessionLocal() as session:
        if model is ContractDate:
            return session.query(ContractDate).filter_by(contract_id=doc_id).count()
        if model is Bookmark:
            return session.query(Bookmark).filter_by(contract_id=doc_id).count()
        return session.query(ChecklistItem).filter_by(contract_id=doc_id).count()


# --------------------------------------------------------------------------- #
# Dates + reminders
# --------------------------------------------------------------------------- #
def test_date_crud_and_reminders(client):
    account = _register(client, "dates@example.com")
    doc_id = "phase4-dates"
    _make_contract(account["user"]["id"], doc_id)
    auth = account["headers"]

    due = date.today() + timedelta(days=5)
    created = client.post(
        f"/contracts/{doc_id}/dates",
        json={
            "label": "Rent",
            "due_date": due.isoformat(),
            "kind": "payment",
            "notes": "Next cycle",
            "remind_days_before": 7,
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["days_until"] == 5
    assert row["remind_on"] == (due - timedelta(days=7)).isoformat()
    assert row["is_overdue"] is False

    listed = client.get(f"/contracts/{doc_id}/dates", headers=auth)
    assert [d["id"] for d in listed.json()["dates"]] == [row["id"]]

    # A date far outside the window is stored but not reminded yet.
    far = (date.today() + timedelta(days=120)).isoformat()
    far_row = client.post(
        f"/contracts/{doc_id}/dates", json={"label": "Far away", "due_date": far}, headers=auth
    )
    assert far_row.status_code == 201

    feed = client.get("/reminders?days=30", headers=auth).json()
    labels = [r["label"] for r in feed["reminders"]]
    assert "Rent" in labels and "Far away" not in labels
    assert all(r["contract_name"] == "Tracking Contract" for r in feed["reminders"])

    # Overdue dates stay visible in the feed and are counted.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    overdue = client.post(
        f"/contracts/{doc_id}/dates", json={"label": "Missed", "due_date": yesterday}, headers=auth
    )
    assert overdue.json()["is_overdue"] is True
    feed = client.get("/reminders?days=30", headers=auth).json()
    assert feed["overdue"] >= 1
    assert any(r["label"] == "Missed" for r in feed["reminders"])

    updated = client.patch(
        f"/contracts/{doc_id}/dates/{row['id']}",
        json={"label": "Monthly rent", "remind_days_before": 3},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Monthly rent"
    assert updated.json()["remind_days_before"] == 3

    removed = client.delete(f"/contracts/{doc_id}/dates/{row['id']}", headers=auth)
    assert removed.status_code == 200
    assert row["id"] not in [d["id"] for d in client.get(f"/contracts/{doc_id}/dates", headers=auth).json()["dates"]]
    assert _count(ContractDate, doc_id) == 2


def test_far_future_filter_can_exclude_overdue(client):
    account = _register(client, "window@example.com")
    doc_id = "phase4-window"
    _make_contract(account["user"]["id"], doc_id)
    auth = account["headers"]
    client.post(
        f"/contracts/{doc_id}/dates",
        json={"label": "Past", "due_date": (date.today() - timedelta(days=3)).isoformat()},
        headers=auth,
    )
    client.post(
        f"/contracts/{doc_id}/dates",
        json={"label": "Soon", "due_date": (date.today() + timedelta(days=3)).isoformat()},
        headers=auth,
    )
    feed = client.get("/reminders?days=10&include_overdue=false", headers=auth).json()
    assert [r["label"] for r in feed["reminders"]] == ["Soon"]


# --------------------------------------------------------------------------- #
# Owner scoping
# --------------------------------------------------------------------------- #
def test_tracking_is_owner_scoped(client):
    alice = _register(client, "alice4@example.com")
    bob = _register(client, "bob4@example.com")
    doc_id = "phase4-scope"
    _make_contract(alice["user"]["id"], doc_id)

    # Bob cannot read or write Alice's tracking rows.
    assert client.get(f"/contracts/{doc_id}/dates", headers=bob["headers"]).status_code == 404
    assert client.get(f"/contracts/{doc_id}/bookmarks", headers=bob["headers"]).status_code == 404
    assert client.get(f"/contracts/{doc_id}/checklist", headers=bob["headers"]).status_code == 404
    assert (
        client.post(
            f"/contracts/{doc_id}/dates",
            json={"label": "Nope", "due_date": date.today().isoformat()},
            headers=bob["headers"],
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/contracts/{doc_id}/bookmarks",
            json={"clause_index": "clause_1"},
            headers=bob["headers"],
        ).status_code
        == 404
    )
    assert (
        client.post(f"/contracts/{doc_id}/checklist/generate", headers=bob["headers"]).status_code
        == 404
    )

    # The same contract does not appear in Bob's reminder feed.
    own = client.post(
        f"/contracts/{doc_id}/dates",
        json={"label": "Alice date", "due_date": date.today().isoformat()},
        headers=alice["headers"],
    )
    assert own.status_code == 201
    bob_feed = client.get("/reminders?days=30", headers=bob["headers"]).json()
    assert all(r["label"] != "Alice date" for r in bob_feed["reminders"])


# --------------------------------------------------------------------------- #
# Bookmarks
# --------------------------------------------------------------------------- #
def test_bookmarks_are_idempotent_and_validated(client):
    account = _register(client, "bookmarks4@example.com")
    doc_id = "phase4-bookmarks"
    _make_contract(account["user"]["id"], doc_id)
    auth = account["headers"]

    first = client.post(
        f"/contracts/{doc_id}/bookmarks",
        json={"clause_index": "clause_1", "note": "Review the fee increase."},
        headers=auth,
    )
    assert first.status_code == 200, first.text
    again = client.post(
        f"/contracts/{doc_id}/bookmarks",
        json={"clause_index": "clause_1", "note": "Updated note"},
        headers=auth,
    )
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["note"] == "Updated note"
    assert _count(Bookmark, doc_id) == 1

    unknown = client.post(
        f"/contracts/{doc_id}/bookmarks", json={"clause_index": "clause_99"}, headers=auth
    )
    assert unknown.status_code == 404

    listed = client.get(f"/contracts/{doc_id}/bookmarks", headers=auth).json()
    assert len(listed["bookmarks"]) == 1

    removed = client.delete(
        f"/contracts/{doc_id}/bookmarks/{first.json()['id']}", headers=auth
    )
    assert removed.status_code == 200
    assert _count(Bookmark, doc_id) == 0


# --------------------------------------------------------------------------- #
# Checklist
# --------------------------------------------------------------------------- #
def test_checklist_generate_is_additive_and_deduped(client):
    account = _register(client, "checklist4@example.com")
    doc_id = "phase4-checklist"
    _make_contract(account["user"]["id"], doc_id)
    auth = account["headers"]

    first = client.post(f"/contracts/{doc_id}/checklist/generate", headers=auth)
    assert first.status_code == 200, first.text
    body = first.json()
    # Only the red + yellow sections generate items; the green one does not.
    assert body["added"] == 2
    assert {i["clause_index"] for i in body["items"]} == {"clause_1", "clause_2"}
    assert all(i["done"] is False for i in body["items"])

    second = client.post(f"/contracts/{doc_id}/checklist/generate", headers=auth).json()
    assert second["added"] == 0
    assert len(second["items"]) == 2

    manual = client.post(
        f"/contracts/{doc_id}/checklist", json={"text": "Email the landlord"}, headers=auth
    )
    assert manual.status_code == 201
    item_id = manual.json()["id"]

    third = client.post(f"/contracts/{doc_id}/checklist/generate", headers=auth).json()
    assert third["added"] == 0
    assert item_id in [i["id"] for i in third["items"]]

    patched = client.patch(
        f"/contracts/{doc_id}/checklist/{item_id}", json={"done": True}, headers=auth
    )
    assert patched.status_code == 200 and patched.json()["done"] is True

    deleted = client.delete(f"/contracts/{doc_id}/checklist/{item_id}", headers=auth)
    assert deleted.status_code == 200
    assert _count(ChecklistItem, doc_id) == 2


# --------------------------------------------------------------------------- #
# Suggestions
# --------------------------------------------------------------------------- #
def test_date_suggestions_are_explicit_only(client):
    account = _register(client, "suggest4@example.com")
    doc_id = "phase4-suggest"
    _make_contract(account["user"]["id"], doc_id)

    payload = client.get(f"/contracts/{doc_id}", headers=account["headers"]).json()
    suggestions = payload["date_suggestions"]
    dates = [s["date"] for s in suggestions]
    assert dates == ["2027-01-01", "2027-02-15"]
    assert all(s["clause_index"] == "clause_2" for s in suggestions)
    assert suggestions[0]["kind"] == "renewal"
    assert suggestions[1]["kind"] == "payment"
    # Relative wording ("within 30 days") must never become a fake date.
    assert all(s["clause_index"] != "clause_3" for s in suggestions)


# --------------------------------------------------------------------------- #
# Cascade
# --------------------------------------------------------------------------- #
def test_deleting_contract_removes_tracking_rows(client):
    account = _register(client, "cascade4@example.com")
    doc_id = "phase4-cascade"
    _make_contract(account["user"]["id"], doc_id)
    auth = account["headers"]

    assert (
        client.post(
            f"/contracts/{doc_id}/dates",
            json={"label": "Renewal", "due_date": (date.today() + timedelta(days=10)).isoformat()},
            headers=auth,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/contracts/{doc_id}/bookmarks", json={"clause_index": "clause_1"}, headers=auth
        ).status_code
        == 200
    )
    assert client.post(f"/contracts/{doc_id}/checklist/generate", headers=auth).status_code == 200
    assert _count(ContractDate, doc_id) == 1
    assert _count(Bookmark, doc_id) == 1
    assert _count(ChecklistItem, doc_id) == 2

    removed = client.delete(f"/contracts/{doc_id}", headers=auth)
    assert removed.status_code == 200
    assert _count(ContractDate, doc_id) == 0
    assert _count(Bookmark, doc_id) == 0
    assert _count(ChecklistItem, doc_id) == 0
