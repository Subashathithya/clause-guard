"""Persistence + quota + scoping helpers for the relational store.

Everything here is owner-scoped: authenticated users only ever see their own
contracts; guest (anonymous) runs are stored with ``user_id`` NULL and are the
only records visible to other guests. Legacy rows migrated from the pre-Phase-2
SQLite cache also carry ``user_id`` NULL.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import cross_clause as cross_clause_engine
from app.evidence import verify_payload_evidence
from app.models import Clause, Contract, UsageCounter, User
from app.schemas import ExtractedClause
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


_EMPTY_CROSS_CLAUSE = {
    "relationships": [],
    "inconsistencies": [],
    "semantic_pairs_scanned": 0,
    "llm_calls": 0,
    "feedback": "",
}


def _normalise_clause(clause: dict, index: int) -> dict:
    """Fill every field the frontend expects, without inventing content."""
    out = dict(clause)
    out["clause_id"] = str(out.get("clause_id") or f"clause_{index + 1}")
    out["category"] = out.get("category") or "Other"
    out["text"] = out.get("text") or ""
    out["risk_level"] = out.get("risk_level") or "yellow"
    score = out.get("risk_score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        score = 50
    out["risk_score"] = score
    out["risk_percentage"] = out.get("risk_percentage") if out.get("risk_percentage") is not None else score
    out["explanation"] = out.get("explanation") or ""
    out["confidence"] = out.get("confidence") if out.get("confidence") is not None else 0.0

    comparison = out.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {}
    similarity = comparison.get("similarity")
    if not isinstance(similarity, (int, float)) or isinstance(similarity, bool):
        similarity = 0.0
    out["comparison"] = {
        "standard_match": comparison.get("standard_match") or "unknown",
        "similarity": similarity,
        "reference_clause": comparison.get("reference_clause"),
        "reference_category": comparison.get("reference_category"),
        "notes": comparison.get("notes") or "",
    }
    out["financial_impact"] = out.get("financial_impact") or ""
    out.setdefault("financial_impact_inr", None)
    out["negotiation_needed"] = bool(out.get("negotiation_needed"))
    out["suggested_counter_clause"] = out.get("suggested_counter_clause") or ""
    talking_points = out.get("talking_points")
    out["talking_points"] = talking_points if isinstance(talking_points, list) else []
    out["success_probability"] = out.get("success_probability") if out.get("success_probability") is not None else 50
    out["reasoning"] = out.get("reasoning") or ""
    return out


def _summarise_clauses(clauses: list[dict]) -> dict:
    red = sum(1 for c in clauses if c.get("risk_level") == "red")
    yellow = sum(1 for c in clauses if c.get("risk_level") == "yellow")
    green = sum(1 for c in clauses if c.get("risk_level") == "green")
    scores = [c.get("risk_score") for c in clauses if isinstance(c.get("risk_score"), (int, float))]
    average = round(sum(scores) / len(scores), 1) if scores else 0.0
    exposure = sum(
        c.get("financial_impact_inr") or 0
        for c in clauses
        if isinstance(c.get("financial_impact_inr"), (int, float))
    )
    overall = "HIGH" if red else "MODERATE" if yellow else "SAFE" if clauses else "UNKNOWN"
    return {
        "red_count": red,
        "yellow_count": yellow,
        "green_count": green,
        "overall_risk": overall,
        "average_risk_score": average,
        "total_financial_exposure_inr": exposure,
    }


def normalize_payload(payload: dict, contract: Contract | None = None) -> dict:
    """Make a cached analysis payload match the current ``/analyze`` shape.

    Older cached payloads predate cross-clause and evidence reporting. Rather
    than returning a different shape (or recomputing an expensive analysis),
    fill the additive fields with honest defaults derived from the stored rows.
    """
    out = dict(payload)
    if contract is not None:
        out["document_id"] = out.get("document_id") or contract.id
        out["document_name"] = out.get("document_name") or contract.name
        out["source"] = out.get("source") or contract.source
        out["user_id"] = contract.user_id
    out["document_id"] = out.get("document_id") or ""
    out["document_name"] = out.get("document_name") or "Unnamed Document"
    out["source"] = out.get("source") or "paste"
    out["status"] = out.get("status") or "SUCCESS"
    out["agent_trace"] = out.get("agent_trace") if isinstance(out.get("agent_trace"), list) else []

    raw_clauses = out.get("clauses") if isinstance(out.get("clauses"), list) else []
    clauses = [_normalise_clause(c, i) for i, c in enumerate(raw_clauses) if isinstance(c, dict)]
    out["clauses"] = clauses
    out["total_clauses"] = out.get("total_clauses") or len(clauses)

    risk_summary = out.get("risk_summary")
    computed = _summarise_clauses(clauses)
    if not isinstance(risk_summary, dict):
        risk_summary = {}
    for key, value in computed.items():
        risk_summary.setdefault(key, value)
    out["risk_summary"] = risk_summary

    summary = out.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.setdefault("total_analyzed", len(clauses))
    summary.setdefault("red_flags", risk_summary.get("red_count", 0))
    summary.setdefault("warnings", risk_summary.get("yellow_count", 0))
    summary.setdefault("safe", risk_summary.get("green_count", 0))
    summary.setdefault("recommendation", "")
    summary.setdefault("top_priorities", [])
    out["summary"] = summary

    cross = out.get("cross_clause")
    if not isinstance(cross, dict):
        # Older payloads predate cross-clause reporting. Recompute the
        # deterministic scan from the stored clauses (IDs/text/categories), so
        # archived contracts get the same grounded connections as new ones.
        try:
            extracted = [
                ExtractedClause(
                    clause_id=c["clause_id"],
                    category=c["category"],
                    text=c["text"],
                    confidence=float(c.get("confidence") or 0.0),
                )
                for c in clauses
            ]
            cross = cross_clause_engine.to_out(
                cross_clause_engine.detect(extracted, semantic=None)
            ).model_dump()
        except Exception:  # noqa: BLE001 — normalization must never 500 a read
            cross = dict(_EMPTY_CROSS_CLAUSE)
    else:
        cross.setdefault("relationships", [])
        cross.setdefault("inconsistencies", [])
        cross.setdefault("semantic_pairs_scanned", 0)
        cross.setdefault("llm_calls", 0)
        cross.setdefault("feedback", "")
    out["cross_clause"] = cross
    out["evidence"] = verify_payload_evidence(clauses)
    return out


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
        "cross_clause": dict(_EMPTY_CROSS_CLAUSE),
        "evidence": verify_payload_evidence(clauses),
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