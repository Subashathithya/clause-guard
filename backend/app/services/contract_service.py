"""Persistence + quota + scoping helpers for the relational store.

Everything here is owner-scoped: authenticated users only ever see their own
contracts; guest (anonymous) runs are stored with ``user_id`` NULL and are the
only records visible to other guests. Legacy rows migrated from the pre-Phase-2
SQLite cache also carry ``user_id`` NULL.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Clause, Contract, UsageCounter, User
from app.settings import settings


def _month_window(now: datetime | None = None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, nxt


def _contract_query(db: Session, user: User | None):
    """Base query scoped to what ``user`` may see."""
    q = db.query(Contract)
    if user is not None:
        return q.filter(Contract.user_id == user.id)
    return q.filter(Contract.user_id.is_(None))


# --------------------------------------------------------------------------- #
# Quota
# --------------------------------------------------------------------------- #
def user_usage(db: Session, user: User) -> int:
    start, nxt = _month_window()
    return (
        db.query(func.count(Contract.id))
        .filter(Contract.user_id == user.id, Contract.created_at >= start, Contract.created_at < nxt)
        .scalar()
        or 0
    )


def user_remaining(db: Session, user: User) -> int:
    return max(0, settings.FREE_TIER_ANALYSES_PER_MONTH - user_usage(db, user))


def anonymous_used(db: Session, ip: str) -> int:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    counter = db.query(UsageCounter).filter_by(ip=ip, month=month).first()
    return counter.analyze_count if counter else 0


def anonymous_remaining(db: Session, ip: str) -> int:
    return max(0, settings.FREE_TIER_ANALYSES_PER_MONTH - anonymous_used(db, ip))


def bump_anonymous_usage(db: Session, ip: str) -> int:
    """Increment the caller's monthly counter and return the new count."""
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    counter = db.query(UsageCounter).filter_by(ip=ip, month=month).first()
    if counter is None:
        counter = UsageCounter(ip=ip, month=month, analyze_count=0)
        db.add(counter)
    counter.analyze_count += 1
    db.commit()
    return counter.analyze_count


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def persist_contract(
    db: Session,
    *,
    result,
    document_id: str,
    name: str,
    text: str,
    source: str,
    user_id: str | None,
) -> Contract:
    """Write an orchestration result into the relational store."""
    risk = result.risk_summary
    contract = Contract(
        id=document_id,
        user_id=user_id,
        name=name,
        source=source,
        status=result.status,
        overall_risk=risk.overall_risk,
        average_risk_score=risk.average_risk_score,
        red_count=risk.red_count,
        yellow_count=risk.yellow_count,
        green_count=risk.green_count,
        total_clauses=result.total_clauses,
        total_financial_exposure_inr=risk.total_financial_exposure_inr,
        char_count=len(text),
        text=text,
        agent_trace=result.agent_trace,
        summary_recommendation=result.summary.recommendation,
        top_priorities=result.summary.top_priorities,
    )
    db.add(contract)
    for c in result.clauses:
        db.add(
            Clause(
                contract_id=document_id,
                clause_index=c.clause_id,
                category=c.category,
                text=c.text,
                risk_level=c.risk_level,
                risk_score=c.risk_score,
                risk_percentage=c.risk_percentage,
                explanation=c.explanation,
                confidence=c.confidence,
                financial_impact=c.financial_impact,
                financial_impact_inr=c.financial_impact_inr,
                negotiation_needed=c.negotiation_needed,
                suggested_counter_clause=c.suggested_counter_clause,
                talking_points=c.talking_points,
                success_probability=c.success_probability,
                reasoning=c.reasoning,
                standard_match=c.comparison.standard_match,
                similarity=c.comparison.similarity,
                reference_clause=c.comparison.reference_clause,
                reference_category=c.comparison.reference_category,
            )
        )
    db.commit()
    db.refresh(contract)
    return contract


def delete_contract(db: Session, contract: Contract) -> None:
    """Delete a contract and its clause rows (FK cascade via ORM)."""
    db.delete(contract)
    db.commit()


# --------------------------------------------------------------------------- #
# Scoping
# --------------------------------------------------------------------------- #
def contract_for_user(db: Session, document_id: str, user: User | None) -> Contract | None:
    return _contract_query(db, user).filter(Contract.id == document_id).first()


def visible_document_ids(db: Session, user: User | None) -> list[str]:
    return [row[0] for row in _contract_query(db, user).with_entities(Contract.id).all()]


# --------------------------------------------------------------------------- #
# Views / payloads
# --------------------------------------------------------------------------- #
def list_contracts(db: Session, user: User | None, limit: int = 200) -> list[dict]:
    """Lightweight rows; field names match the frontend ``Contract`` type."""
    rows = (
        _contract_query(db, user)
        .order_by(Contract.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "document_id": c.id,
            "document_name": c.name,
            "status": c.status,
            "overall_risk": c.overall_risk,
            "source": c.source,
            "chunk_count": 0,
            "char_count": c.char_count,
            "total_clauses": c.total_clauses,
            "red_count": c.red_count,
            "yellow_count": c.yellow_count,
            "green_count": c.green_count,
            "total_financial_exposure_inr": c.total_financial_exposure_inr,
            "created_at": c.created_at.isoformat(),
        }
        for c in rows
    ]


def build_payload(contract: Contract) -> dict:
    """Reconstruct the full stored analysis payload (same shape as /analyze)."""
    clauses = []
    for c in contract.clauses:
        clauses.append(
            {
                "clause_id": c.clause_index,
                "category": c.category,
                "text": c.text,
                "risk_level": c.risk_level,
                "risk_score": c.risk_score,
                "risk_percentage": c.risk_percentage,
                "explanation": c.explanation,
                "confidence": c.confidence,
                "financial_impact": c.financial_impact,
                "financial_impact_inr": c.financial_impact_inr,
                "negotiation_needed": c.negotiation_needed,
                "suggested_counter_clause": c.suggested_counter_clause,
                "talking_points": c.talking_points or [],
                "success_probability": c.success_probability,
                "reasoning": c.reasoning,
                "comparison": {
                    "standard_match": c.standard_match,
                    "similarity": c.similarity,
                    "reference_clause": c.reference_clause,
                    "reference_category": c.reference_category,
                },
            }
        )
    return {
        "document_id": contract.id,
        "document_name": contract.name,
        "source": contract.source,
        "status": contract.status,
        "total_clauses": contract.total_clauses,
        "risk_summary": {
            "red_count": contract.red_count,
            "yellow_count": contract.yellow_count,
            "green_count": contract.green_count,
            "overall_risk": contract.overall_risk,
            "average_risk_score": contract.average_risk_score,
            "total_financial_exposure_inr": contract.total_financial_exposure_inr,
        },
        "summary": {
            "total_analyzed": contract.total_clauses,
            "red_flags": contract.red_count,
            "warnings": contract.yellow_count,
            "safe": contract.green_count,
            "recommendation": contract.summary_recommendation or "",
            "top_priorities": contract.top_priorities or [],
        },
        "clauses": clauses,
        "agent_trace": contract.agent_trace or [],
    }


def stats(db: Session, user: User | None) -> dict:
    """Dashboard aggregates, scoped to the caller's records."""
    q = _contract_query(db, user)
    total_contracts = q.count()
    start, nxt = _month_window()
    contracts_this_month = (
        q.filter(Contract.created_at >= start, Contract.created_at < nxt).count()
    )

    by_level = dict(
        db.query(Clause.risk_level, func.count(Clause.id))
        .join(Contract, Clause.contract_id == Contract.id)
        .filter(Contract.user_id == (user.id if user else None))
        .group_by(Clause.risk_level)
        .all()
    )
    # NOTE: for guest scope, `user.id if user else None` matches NULL contracts.
    total_clauses = sum(by_level.values())
    return {
        "total_contracts": total_contracts,
        "contracts_this_month": contracts_this_month,
        "total_clauses": total_clauses,
        "red_clauses": by_level.get("red", 0),
        "yellow_clauses": by_level.get("yellow", 0),
        "green_clauses": by_level.get("green", 0),
        "analysis_credits_this_month": (
            user_usage(db, user) if user else anonymous_used(db, "unknown")
        ),
        "scope": "user" if user else "guest",
    }