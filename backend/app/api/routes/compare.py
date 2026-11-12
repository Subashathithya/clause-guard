"""Contract comparison endpoints: /compare (side-by-side) and /drift (version drift).

Only documents the caller is allowed to see (owner-scoped) are considered.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import db as vdb
from app.core.security import get_optional_user
from app.database import get_db
from app.llm import chat
from app.models import User
from app.schemas import CompareInput, DriftInput, ExtractedClause
from app.services import contract_service, version_comparison
from app.settings import settings

router = APIRouter()


def _to_extracted(clause: dict) -> ExtractedClause:
    """Surface one stored analysis clause as an engine ExtractedClause.

    The ranker's risk fields (``risk_level``/``risk_score``) are carried along
    so the version-comparison engine's attention banding stays meaningful;
    default pydantic construction only keeps the four contract fields.
    """
    ec = ExtractedClause(
        clause_id=str(clause.get("clause_id", "")),
        category=clause.get("category", ""),
        text=clause.get("text", ""),
        confidence=float(clause.get("confidence", 0.0)),
    )
    for attr in ("risk_level", "risk_score"):
        value = clause.get(attr)
        if value is not None:
            object.__setattr__(ec, attr, value)
    return ec


def _authorized(user: Optional[User]) -> None:
    if user is None and settings.REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required")


@router.post("/compare")
async def compare_contracts(
    input_data: CompareInput,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _authorized(user)
    if len(input_data.document_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two document_ids")

    visible = set(contract_service.visible_document_ids(db, user))
    analyses = []
    for doc_id in input_data.document_ids:
        if doc_id not in visible:
            continue
        stored = vdb.get_analysis(doc_id)
        if stored:
            analyses.append(contract_service.normalize_payload(stored))
    if len(analyses) < 2:
        raise HTTPException(status_code=404, detail="Not enough analysed documents found")

    # Build a per-category matrix of average risk scores
    categories = sorted({c["category"] for a in analyses for c in a.get("clauses", [])})
    matrix = []
    for cat in categories:
        row = {"category": cat, "by_document": {}, "winner": None}
        scores = {}
        for a in analyses:
            cat_clauses = [c for c in a.get("clauses", []) if c["category"] == cat]
            if cat_clauses:
                avg = round(sum(c["risk_score"] for c in cat_clauses) / len(cat_clauses), 1)
                scores[a["document_name"]] = avg
                row["by_document"][a["document_name"]] = avg
        if scores:
            row["winner"] = min(scores, key=scores.get)  # lowest risk = fairest
        matrix.append(row)

    # LLM narrative
    digest = "\n".join(
        f"- {a['document_name']}: overall {a['risk_summary']['overall_risk']}, "
        f"avg score {a['risk_summary']['average_risk_score']}"
        for a in analyses
    )
    try:
        narrative = chat(
            [
                {"role": "system", "content": "You compare contracts for a consumer in plain English."},
                {
                    "role": "user",
                    "content": (
                        f"Compare these contracts:\n{digest}\n\n"
                        "In 3-4 sentences, say which is fairest and the single biggest "
                        "difference the consumer should care about."
                    ),
                },
            ],
            max_tokens=400,
            temperature=0.3,
        )
    except Exception as exc:  # noqa: BLE001
        # Keep the internal cause out of the response body.
        logger.warning("Comparison narrative unavailable: %s", exc)
        narrative = "(comparison narrative unavailable)"

    return {
        "status": "SUCCESS",
        "documents": [
            {"document_id": a["document_id"], "document_name": a["document_name"],
             "overall_risk": a["risk_summary"]["overall_risk"],
             "average_risk_score": a["risk_summary"]["average_risk_score"]}
            for a in analyses
        ],
        "category_matrix": matrix,
        "narrative": narrative,
    }


@router.post("/drift")
async def policy_drift(
    input_data: DriftInput,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Detect how terms changed across two versions of a contract."""
    _authorized(user)
    if len(input_data.document_ids) != 2:
        raise HTTPException(status_code=400, detail="Provide exactly two document_ids (old, new)")

    visible = set(contract_service.visible_document_ids(db, user))
    if not {input_data.document_ids[0], input_data.document_ids[1]} <= visible:
        raise HTTPException(status_code=404, detail="Both documents must be analysed first")

    old = vdb.get_analysis(input_data.document_ids[0])
    new = vdb.get_analysis(input_data.document_ids[1])
    if not old or not new:
        raise HTTPException(status_code=404, detail="Both documents must be analysed first")
    old = contract_service.normalize_payload(old)
    new = contract_service.normalize_payload(new)

    def cat_scores(a):
        out = {}
        for c in a.get("clauses", []):
            out.setdefault(c["category"], []).append(c["risk_score"])
        return {k: round(sum(v) / len(v), 1) for k, v in out.items()}

    old_scores, new_scores = cat_scores(old), cat_scores(new)
    changes = []
    for cat in sorted(set(old_scores) | set(new_scores)):
        before = old_scores.get(cat)
        after = new_scores.get(cat)
        if before is None or after is None:
            delta = None
            direction = "added" if before is None else "removed"
        else:
            delta = round(after - before, 1)
            direction = "worsened" if delta > 3 else "improved" if delta < -3 else "stable"
        changes.append({"category": cat, "before": before, "after": after,
                        "delta": delta, "direction": direction})

    old_overall = old["risk_summary"]["average_risk_score"]
    new_overall = new["risk_summary"]["average_risk_score"]
    overall_delta = round(new_overall - old_overall, 1)

    old_clauses_engine = [_to_extracted(c) for c in old.get("clauses", [])]
    new_clauses_engine = [_to_extracted(c) for c in new.get("clauses", [])]
    _report = version_comparison.detect(
        old_clauses_engine,
        new_clauses_engine,
        version_a=old.get("document_name", ""),
        version_b=new.get("document_name", ""),
    )
    _version_report = version_comparison.to_out(_report)

    return {
        "status": "SUCCESS",
        "old": {"document_id": old["document_id"], "document_name": old["document_name"],
                "average_risk_score": old_overall, "overall_risk": old["risk_summary"]["overall_risk"]},
        "new": {"document_id": new["document_id"], "document_name": new["document_name"],
                "average_risk_score": new_overall, "overall_risk": new["risk_summary"]["overall_risk"]},
        "overall_delta": overall_delta,
        "overall_direction": "worsened" if overall_delta > 3 else "improved" if overall_delta < -3 else "stable",
        "changes": changes,
        "version_comparison": _version_report,
    }