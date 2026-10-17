"""History + usage stats endpoints (owner-scoped relational reads)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import db as vdb
from app.core.security import get_optional_user
from app.database import get_db
from app.models import User
from app.services import contract_service
from app.settings import settings

router = APIRouter()


def _require_auth(user: Optional[User]) -> None:
    if user is None and settings.REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required")


@router.get("/stats")
async def stats(
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    return contract_service.stats(db, user)


@router.get("/history")
async def history(
    limit: int = 50,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    rows = contract_service.list_contracts(db, user, limit=min(limit, 200))
    return {"count": len(rows), "analyses": rows}


@router.delete("/analyses/{analysis_id}")
async def remove_analysis(
    analysis_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = contract_service.contract_for_user(db, analysis_id, user)
    if contract is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    vdb.delete_document(analysis_id)
    contract_service.delete_contract(db, contract)
    return {"status": "SUCCESS", "deleted": analysis_id}