"""Stored-contract endpoints: list / fetch / delete analyses.

Owner-scoped: authenticated users see only their own records; guests see the
legacy (user_id NULL) records. Reconstructed payloads match the /analyze shape.
"""
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


@router.get("/contracts")
async def list_contracts(
    limit: int = 200,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    return {"contracts": contract_service.list_contracts(db, user, limit=limit)}


@router.get("/contracts/{document_id}")
async def get_contract(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = contract_service.contract_for_user(db, document_id, user)
    if contract is None:
        # Legacy / unmigrated document: only guests in guest mode may read it.
        if user is None and not settings.REQUIRE_AUTH:
            stored = vdb.get_analysis(document_id)
            if stored is not None:
                stored.setdefault("user_id", None)
                return stored
        raise HTTPException(status_code=404, detail="Document not found")
    # Prefer the full-fidelity cached payload (chroma), else reconstruct from
    # the relational rows (covers a cleared vector store).
    stored = vdb.get_analysis(document_id)
    if stored is not None:
        stored.setdefault("user_id", contract.user_id)
        return stored
    return contract_service.build_payload(contract)


@router.delete("/contracts/{document_id}")
async def remove_contract(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = contract_service.contract_for_user(db, document_id, user)
    if contract is None:
        raise HTTPException(status_code=404, detail="Document not found")
    vdb.delete_document(document_id)
    contract_service.delete_contract(db, contract)
    return {"status": "SUCCESS", "deleted": document_id}