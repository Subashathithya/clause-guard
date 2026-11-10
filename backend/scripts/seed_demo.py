"""Seed a realistic demo workspace for reviews and demos.

Creates a demo account plus a set of fully-analysed contracts (deterministic —
no LLM calls, no API key required) so the dashboard, charts, workspace and chat
all have meaningful data the moment the app opens.

Two scopes are seeded:

  * guest  — documents with ``user_id = NULL`` so the default (no-login) view is
             populated, which is what most reviewers see first;
  * demo   — the same documents owned by the demo account, so logging in shows a
             populated, owner-scoped workspace.

Usage (from the ``backend`` directory):

    python scripts/seed_demo.py            # add demo data (idempotent)
    python scripts/seed_demo.py --reset    # delete previously seeded rows first

Demo credentials:  demo@clauseguard.app / Demo@12345
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import timedelta

# Make ``app`` importable when run as ``python scripts/seed_demo.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db as vdb  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal, init_db, utcnow  # noqa: E402
from app.models import Contract, User  # noqa: E402
from app.schemas import (  # noqa: E402
    AnalysisResult,
    AnalysisSummary,
    AnalyzedClause,
    ComparisonResult,
    RiskSummary,
)
from app.services import contract_service  # noqa: E402

DEMO_EMAIL = "demo@clauseguard.app"
DEMO_PASSWORD = "Demo@12345"
DEMO_NAME = "Demo Reviewer"

_NAMESPACE = uuid.UUID("6f1c2b64-9a2e-4c9d-8f2a-1c3d5e7f9a01")


# --------------------------------------------------------------------------- #
# Clause / document helpers
# --------------------------------------------------------------------------- #
def _clause(
    cid: str,
    category: str,
    text: str,
    level: str,
    score: int,
    explanation: str,
    impact: str,
    amount: int | None,
    counter: str,
    points: list[str],
    probability: int,
    match: str = "worse",
    similarity: float = 0.82,
) -> AnalyzedClause:
    return AnalyzedClause(
        clause_id=cid,
        category=category,
        text=text,
        risk_level=level,  # type: ignore[arg-type]
        risk_score=score,
        risk_percentage=score,
        explanation=explanation,
        confidence=0.9,
        comparison=ComparisonResult(
            standard_match=match,
            similarity=similarity,
            reference_clause=None,
            reference_category=category,
            notes="Compared against the ClauseGuard fair-clause library.",
        ),
        financial_impact=impact,
        financial_impact_inr=amount,
        negotiation_needed=level != "green",
        suggested_counter_clause=counter,
        talking_points=points,
        success_probability=probability,
        reasoning="",
    )


def _build(key: str, name: str, text: str, clauses: list[AnalyzedClause]) -> AnalysisResult:
    red = sum(1 for c in clauses if c.risk_level == "red")
    yellow = sum(1 for c in clauses if c.risk_level == "yellow")
    green = sum(1 for c in clauses if c.risk_level == "green")
    exposure = sum(c.financial_impact_inr or 0 for c in clauses)
    avg = round(sum(c.risk_score for c in clauses) / len(clauses), 1) if clauses else 0.0
    overall = "HIGH" if red else ("MODERATE" if yellow else "LOW")

    priorities = [
        f"{c.category}: {c.explanation}"
        for c in sorted(clauses, key=lambda c: c.risk_score, reverse=True)
        if c.risk_level != "green"
    ][:3]

    recommendation = (
        "This document contains high-risk terms that should be negotiated before signing. "
        "Prioritise liability, data handling and termination rights."
        if red
        else "A few clauses are worth clarifying, but there are no critical red flags."
        if yellow
        else "The document looks broadly balanced. Only minor clarifications are suggested."
    )

    return AnalysisResult(
        document_id=str(uuid.uuid5(_NAMESPACE, key)),
        document_name=name,
        total_clauses=len(clauses),
        risk_summary=RiskSummary(
            red_count=red,
            yellow_count=yellow,
            green_count=green,
            overall_risk=overall,
            average_risk_score=avg,
            total_financial_exposure_inr=exposure,
        ),
        clauses=clauses,
        summary=AnalysisSummary(
            total_analyzed=len(clauses),
            red_flags=red,
            warnings=yellow,
            safe=green,
            recommendation=recommendation,
            top_priorities=priorities,
        ),
        agent_trace=[
            {"agent": "Extractor", "ms": 812},
            {"agent": "Comparator", "ms": 415},
            {"agent": "Ranker", "ms": 1290},
            {"agent": "Negotiator", "ms": 2330},
        ],
        status="SUCCESS",
    )


# --------------------------------------------------------------------------- #
# Demo documents
# --------------------------------------------------------------------------- #
def _documents() -> list[tuple[str, str, str, AnalysisResult, int]]:
    """Return (key, name, text, result, days_ago) tuples."""
    docs: list[tuple[str, str, str, AnalysisResult, int]] = []

    # ---- 1. SaaS subscription -------------------------------------------------
    name = "SaaS Subscription Agreement — Vertex Analytics"
    text = (
        "SAAS SUBSCRIPTION AGREEMENT\n\n"
        "This Agreement is between Vertex Analytics Pvt. Ltd. (\"Vertex\") and the customer. "
        "It governs access to the Vertex analytics platform.\n\n"
        "1. Fees. Subscription fees of Rs 85,000 per month are payable in advance within 7 days of invoice. "
        "Late payments accrue interest at 2% per month.\n"
        "2. Term and renewal. The initial term is 12 months and renews automatically for successive "
        "12-month periods unless either party gives 60 days' written notice.\n"
        "3. Limitation of liability. Customer indemnifies Vertex against all third-party claims. "
        "Vertex's aggregate liability is limited to the fees paid in the preceding 30 days.\n"
        "4. Data processing. Vertex may process customer data for any purpose, including product "
        "improvement and marketing, and may retain it indefinitely after termination.\n"
        "5. Suspension. Vertex may suspend the service immediately for any breach, without notice.\n"
        "6. Warranty. The service is provided 'as is', without warranty of uptime or fitness for purpose.\n"
    )
    clauses = [
        _clause(
            "clause_1", "Payment",
            "Subscription fees of Rs 85,000 per month are payable in advance within 7 days of invoice. "
            "Late payments accrue interest at 2% per month.",
            "red", 72,
            "Large advance payments with an aggressive 2% monthly late-payment penalty create real cash-flow and cost exposure.",
            "Rs 10,20,000 billed annually in advance", 1020000,
            "Change to monthly billing in arrears with a 30-day payment window and a capped late fee of 1% per month.",
            ["Ask for monthly billing in arrears rather than prepaid.", "Cap late-payment interest at 1% per month."],
            65, "worse", 0.74,
        ),
        _clause(
            "clause_2", "Auto-Renewal",
            "The initial term is 12 months and renews automatically for successive 12-month periods unless "
            "either party gives 60 days' written notice.",
            "yellow", 55,
            "A 60-day notice window is easy to miss and locks you into another full year.",
            "Rs 10,20,000 per renewal cycle", 1020000,
            "Reduce the notice period to 30 days and allow renewal on a month-to-month basis.",
            ["Negotiate a 30-day notice window.", "Add a renewal price-increase cap."],
            70, "worse", 0.86,
        ),
        _clause(
            "clause_3", "Liability",
            "Customer indemnifies Vertex against all third-party claims. Vertex's aggregate liability is "
            "limited to the fees paid in the preceding 30 days.",
            "red", 80,
            "A one-sided indemnity with a 30-day liability cap leaves you bearing almost all risk.",
            "Uncapped indemnity exposure", None,
            "Make the indemnity mutual and raise Vertex's liability cap to 12 months of fees.",
            ["Request a mutual indemnity.", "Raise the liability cap to at least the annual fee."],
            55, "worse", 0.91,
        ),
        _clause(
            "clause_4", "Data Privacy",
            "Vertex may process customer data for any purpose, including product improvement and marketing, "
            "and may retain it indefinitely after termination.",
            "red", 85,
            "Broad, purpose-free processing and indefinite retention conflict with typical data-protection expectations.",
            "Compliance and repudiation risk", None,
            "Limit processing to delivering the service, require deletion within 30 days of termination, "
            "and add a standard data-processing addendum.",
            ["Ask for a data-processing agreement (DPA).", "Require data deletion within 30 days of exit."],
            50, "worse", 0.88,
        ),
        _clause(
            "clause_5", "Other",
            "Vertex may suspend the service immediately for any breach, without notice.",
            "yellow", 50,
            "Immediate suspension for any breach — including a trivial one — can disrupt your operations.",
            "Operational interruption risk", None,
            "Require written notice and a 15-day cure period before suspension, except for non-payment beyond 30 days.",
            ["Add a cure period before suspension.", "Limit suspension to material breaches."],
            72, "worse", 0.79,
        ),
        _clause(
            "clause_6", "Warranty",
            "The service is provided 'as is', without warranty of uptime or fitness for purpose.",
            "yellow", 58,
            "No uptime commitment means you have no remedy if the platform is frequently unavailable.",
            "Service-availability risk", None,
            "Add a 99.5% uptime SLA with service credits.",
            ["Ask for an uptime SLA and credits.", "Remove the blanket 'as is' disclaimer for availability."],
            68, "worse", 0.83,
        ),
    ]
    docs.append(("saas-vertex", name, text, _build("saas-vertex", name, text, clauses), 96))

    # ---- 2. Freelance design contract ----------------------------------------
    name = "Freelance Design Contract — Nimbus Studio"
    text = (
        "DESIGN SERVICES CONTRACT\n\n"
        "Nimbus Studio will provide brand and product design services to the Client.\n\n"
        "1. Fees. 50% is due upfront and the balance within 45 days of delivery.\n"
        "2. Intellectual property. All work product, including unused concepts, becomes the property of "
        "Nimbus Studio upon payment.\n"
        "3. Termination. The Client may terminate at any time; Nimbus retains 100% of fees.\n"
        "4. Liability. Nimbus's total liability is capped at Rs 50,000.\n"
        "5. Disputes. Disputes are resolved by arbitration in Mumbai; costs are borne by the Client.\n"
    )
    clauses = [
        _clause(
            "clause_1", "Payment",
            "50% is due upfront and the balance within 45 days of delivery.",
            "yellow", 45,
            "A 45-day balance window is workable but slow; clarify what counts as 'delivery'.",
            "Rs 75,000 outstanding at a time", 75000,
            "Shorten the balance window to 15 days after written acceptance.",
            ["Define acceptance in writing.", "Shorten the balance window to 15 days."],
            78, "match", 0.81,
        ),
        _clause(
            "clause_2", "Other",
            "All work product, including unused concepts, becomes the property of Nimbus Studio upon payment.",
            "red", 75,
            "You would not own the designs you paid for, and unused concepts stay with the studio.",
            "Ownership of all deliverables", None,
            "Assign all delivered work to the Client on payment; keep only a portfolio-use licence for Nimbus.",
            ["Require full IP assignment on payment.", "Limit Nimbus to a showcase licence."],
            60, "worse", 0.9,
        ),
        _clause(
            "clause_3", "Other",
            "The Client may terminate at any time; Nimbus retains 100% of fees.",
            "red", 70,
            "Termination refunds nothing, even if work has barely started.",
            "Full fee forfeiture", None,
            "Refund any prepaid amount for work not yet performed, pro-rated to progress.",
            ["Add pro-rated refunds on termination.", "Tie payment milestones to deliverables."],
            58, "worse", 0.87,
        ),
        _clause(
            "clause_4", "Liability",
            "Nimbus's total liability is capped at Rs 50,000.",
            "green", 32,
            "A clearly capped, modest liability is typical for creative services.",
            "Capped at Rs 50,000", 50000,
            "Consider raising the cap for gross negligence or wilful misconduct.",
            ["Carve out gross negligence from the cap."],
            80, "match", 0.76,
        ),
        _clause(
            "clause_5", "Dispute",
            "Disputes are resolved by arbitration in Mumbai; costs are borne by the Client.",
            "yellow", 55,
            "Forcing the Client to bear all arbitration costs discourages legitimate claims.",
            "Arbitration cost exposure", None,
            "Split arbitration costs equally and allow good-faith negotiation first.",
            ["Split arbitration costs.", "Add a 30-day negotiation step before arbitration."],
            70, "worse", 0.84,
        ),
    ]
    docs.append(("freelance-nimbus", name, text, _build("freelance-nimbus", name, text, clauses), 61))

    # ---- 3. Gym membership ----------------------------------------------------
    name = "Gym Membership — IronHouse Fitness"
    text = (
        "GYM MEMBERSHIP AGREEMENT\n\n"
        "1. Fees. Membership is Rs 2,999 per month, auto-debited. A joining fee of Rs 5,000 is non-refundable.\n"
        "2. Renewal. Membership renews automatically every month. Cancel with 14 days' notice.\n"
        "3. Liability. The member waives all claims for injury, including injury caused by the gym's negligence.\n"
        "4. Data. Biometric and health data may be shared with marketing and insurance partners.\n"
    )
    clauses = [
        _clause(
            "clause_1", "Payment",
            "Membership is Rs 2,999 per month, auto-debited. A joining fee of Rs 5,000 is non-refundable.",
            "yellow", 45,
            "Auto-debit plus a non-refundable joining fee makes exit costly.",
            "Rs 35,988 per year plus Rs 5,000 joining fee", 40988,
            "Refund the joining fee pro-rata if you cancel within the first 30 days.",
            ["Ask for a refundable joining fee.", "Confirm the auto-debit cancellation process."],
            75, "match", 0.8,
        ),
        _clause(
            "clause_2", "Auto-Renewal",
            "Membership renews automatically every month. Cancel with 14 days' notice.",
            "yellow", 55,
            "Monthly auto-renewal with a 14-day notice window is typical but easy to forget.",
            "Rs 2,999 per month", 35988,
            "Allow cancellation any time before the next billing date.",
            ["Request same-day cancellation before renewal.", "Get renewal confirmation by email."],
            78, "match", 0.85,
        ),
        _clause(
            "clause_3", "Liability",
            "The member waives all claims for injury, including injury caused by the gym's negligence.",
            "red", 88,
            "Waiving claims for the gym's own negligence is unusually aggressive and often unenforceable.",
            "Personal-injury exposure", None,
            "Carve out the gym's negligence and provide adequate supervision and equipment checks.",
            ["Remove the negligence waiver.", "Ask about insurance and safety policies."],
            45, "worse", 0.93,
        ),
        _clause(
            "clause_4", "Data Privacy",
            "Biometric and health data may be shared with marketing and insurance partners.",
            "red", 85,
            "Health and biometric data are sensitive; sharing them with insurers and marketers is high-risk.",
            "Sensitive-data exposure", None,
            "Require explicit opt-in consent and prohibit sharing with insurers and marketers.",
            ["Demand an opt-in for health data.", "Ask what data is shared and with whom."],
            48, "worse", 0.89,
        ),
    ]
    docs.append(("gym-ironhouse", name, text, _build("gym-ironhouse", name, text, clauses), 34))

    # ---- 4. Residential lease -------------------------------------------------
    name = "Residential Lease — Flat 4B, Bengaluru"
    text = (
        "RESIDENTIAL LEASE AGREEMENT\n\n"
        "1. Rent. Rent is Rs 42,000 per month, due on the 1st. Late payment attracts Rs 1,000 per day.\n"
        "2. Deposit. An interest-free security deposit of Rs 2,52,000 is refundable within 60 days of "
        "vacating, subject to deductions.\n"
        "3. Repairs. The landlord is responsible for structural repairs; the tenant bears all other repairs "
        "regardless of cause.\n"
        "4. Termination. The landlord may terminate with 30 days' notice for any reason.\n"
        "5. Disputes. Courts in Bengaluru have exclusive jurisdiction.\n"
    )
    clauses = [
        _clause(
            "clause_1", "Payment",
            "Rent is Rs 42,000 per month, due on the 1st. Late payment attracts Rs 1,000 per day.",
            "yellow", 62,
            "A Rs 1,000/day late fee is disproportionate and can exceed the rent itself within a month.",
            "Rs 30,000 per month in potential late fees", 360000,
            "Cap the late fee at 5% of monthly rent with a 5-day grace period.",
            ["Cap the daily late fee.", "Add a grace period."],
            74, "worse", 0.86,
        ),
        _clause(
            "clause_2", "Other",
            "An interest-free security deposit of Rs 2,52,000 is refundable within 60 days of vacating, "
            "subject to deductions.",
            "yellow", 50,
            "A six-month deposit and a 60-day refund window tie up a large sum with vague deductions.",
            "Rs 2,52,000 held interest-free", 252000,
            "Reduce the deposit to three months and require itemised, documentary deductions within 30 days.",
            ["Negotiate a smaller deposit.", "Require written, itemised deductions."],
            68, "worse", 0.82,
        ),
        _clause(
            "clause_3", "Other",
            "The landlord is responsible for structural repairs; the tenant bears all other repairs regardless of cause.",
            "yellow", 55,
            "Making the tenant pay for repairs 'regardless of cause' could include normal wear and landlord faults.",
            "Unbounded repair costs", None,
            "Limit tenant repairs to minor day-to-day upkeep; landlord covers equipment and structural failures.",
            ["Define 'minor repairs' with a cost cap.", "Exclude damage from landlord equipment."],
            72, "worse", 0.84,
        ),
        _clause(
            "clause_4", "Other",
            "The landlord may terminate with 30 days' notice for any reason.",
            "red", 72,
            "Termination without cause or compensation leaves you facing sudden relocation.",
            "Relocation and deposit risk", None,
            "Require a 60-day notice period and a minimum lock-in, or compensation for early termination.",
            ["Ask for a 60-day notice and lock-in period.", "Add compensation for no-fault termination."],
            62, "worse", 0.88,
        ),
        _clause(
            "clause_5", "Dispute",
            "Courts in Bengaluru have exclusive jurisdiction.",
            "green", 25,
            "A local-jurisdiction clause is standard and reasonable here.",
            "None identified", None,
            "No change needed.",
            ["Standard clause — no action."],
            88, "match", 0.71,
        ),
    ]
    docs.append(("lease-flat4b", name, text, _build("lease-flat4b", name, text, clauses), 18))

    # ---- 5. Employment offer --------------------------------------------------
    name = "Employment Offer Letter — Junior Data Analyst"
    text = (
        "EMPLOYMENT OFFER LETTER\n\n"
        "1. Salary. The annual salary is Rs 6,50,000, reviewed annually at the company's discretion.\n"
        "2. Notice. The employee must give 90 days' notice; the company may terminate with 30 days.\n"
        "3. Confidentiality. The employee assigns all intellectual property created during employment, "
        "including work outside office hours.\n"
        "4. Monitoring. The company may monitor all devices and communications.\n"
        "5. Disputes. Disputes are subject to arbitration; the employee waives the right to court.\n"
    )
    clauses = [
        _clause(
            "clause_1", "Payment",
            "The annual salary is Rs 6,50,000, reviewed annually at the company's discretion.",
            "yellow", 40,
            "The 'discretion' wording means no guaranteed raise or inflation adjustment.",
            "Rs 6,50,000 per year", 650000,
            "Add a documented annual review with a defined range or inflation-linked floor.",
            ["Ask for a review framework.", "Clarify bonus and increments."],
            80, "match", 0.78,
        ),
        _clause(
            "clause_2", "Other",
            "The employee must give 90 days' notice; the company may terminate with 30 days.",
            "yellow", 56,
            "Asymmetric notice periods favour the employer.",
            "Three months' salary at risk on exit", 162500,
            "Make notice periods symmetrical at 60 days for both parties.",
            ["Request equal notice periods.", "Clarify garden-leave terms."],
            70, "worse", 0.85,
        ),
        _clause(
            "clause_3", "Other",
            "The employee assigns all intellectual property created during employment, including work outside office hours.",
            "red", 70,
            "Claiming IP from personal, off-hours projects is unusually broad.",
            "Ownership of personal projects", None,
            "Limit assignment to IP created in the course of employment using company resources.",
            ["Narrow the IP assignment.", "Carve out personal side projects."],
            62, "worse", 0.9,
        ),
        _clause(
            "clause_4", "Data Privacy",
            "The company may monitor all devices and communications.",
            "yellow", 60,
            "Blanket monitoring should be scoped and disclosed in a clear policy.",
            "Privacy exposure", None,
            "Restrict monitoring to company devices during work hours and disclose the policy.",
            ["Ask for the monitoring policy.", "Clarify personal-device rules."],
            68, "worse", 0.83,
        ),
        _clause(
            "clause_5", "Dispute",
            "Disputes are subject to arbitration; the employee waives the right to court.",
            "red", 65,
            "Waiving court access can disadvantage employees in statutory disputes.",
            "Loss of court access", None,
            "Preserve statutory remedies and make arbitration optional for the employee.",
            ["Ask to keep statutory rights.", "Clarify who pays arbitration costs."],
            60, "worse", 0.87,
        ),
    ]
    docs.append(("offer-analyst", name, text, _build("offer-analyst", name, text, clauses), 6))

    return docs


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #
def _demo_user(session) -> User:
    user = session.query(User).filter(User.email == DEMO_EMAIL).first()
    if user is None:
        user = User(
            id=str(uuid.uuid5(_NAMESPACE, "demo-user")),
            email=DEMO_EMAIL,
            full_name=DEMO_NAME,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _remove_if_present(session, doc_id: str) -> None:
    existing = session.get(Contract, doc_id)
    if existing is not None:
        vdb.delete_document(doc_id)
        contract_service.delete_contract(session, existing)


def seed(reset: bool = False) -> int:
    init_db()
    session = SessionLocal()
    created = 0
    try:
        user = _demo_user(session)
        scopes = [(None, "guest", 0), (user.id, "demo", 1)]

        for owner, label, offset in scopes:
            for key, name, text, base, days_ago in _documents():
                doc_id = str(uuid.uuid5(_NAMESPACE, f"{label}:{key}"))
                result = base.model_copy(deep=True)
                result.document_id = doc_id

                if reset:
                    _remove_if_present(session, doc_id)
                elif session.get(Contract, doc_id) is not None:
                    continue

                vdb.index_document(doc_id, name, text)
                vdb.save_analysis(doc_id, name, result.model_dump())
                contract = contract_service.persist_contract(
                    session,
                    result=result,
                    document_id=doc_id,
                    name=name,
                    text=text,
                    source="paste",
                    user_id=owner,
                )
                # Spread creation dates so the activity chart has shape.
                contract.created_at = utcnow() - timedelta(days=days_ago + offset)
                session.commit()
                created += 1
                print(f"  + [{label}] {name}")
    finally:
        session.close()
    return created


def main() -> None:
    reset = "--reset" in sys.argv
    print("Seeding ClauseGuard demo workspace..." + (" (reset)" if reset else ""))
    count = seed(reset=reset)
    print(f"\nDone. {count} document(s) written across guest + demo scopes.")
    print(f"Demo login:  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
