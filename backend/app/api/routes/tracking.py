"""Phase 4 tracking endpoints: key dates, reminders, bookmarks and checklists.

Everything here is owner-scoped through the same rule as the contract endpoints:
signed-in users only touch their own contracts, guests only touch the legacy
(user_id NULL) records. Tracking rows are user-owned and survive re-analysis of
the contract text; deleting a contract removes them via FK cascade.
"""
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_optional_user
from app.database import get_db
from app.models import Bookmark, ChecklistItem, Clause, Contract, ContractDate, User
from app.schemas import (
    BookmarkCreate,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    ContractDateCreate,
    ContractDateUpdate,
)
from app.services import checklist as checklist_service
from app.services import contract_service
from app.settings import settings

router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _require_auth(user: Optional[User]) -> None:
    if user is None and settings.REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required")


def _contract_or_404(db: Session, document_id: str, user: Optional[User]) -> Contract:
    contract = contract_service.contract_for_user(db, document_id, user)
    if contract is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return contract


def _date_out(row: ContractDate, *, contract_name: str | None = None) -> dict:
    today = date.today()
    days_until = (row.due_date - today).days
    out = {
        "id": row.id,
        "contract_id": row.contract_id,
        "label": row.label,
        "due_date": row.due_date,
        "kind": row.kind,
        "notes": row.notes or "",
        "remind_days_before": row.remind_days_before,
        "created_at": row.created_at,
        "days_until": days_until,
        "remind_on": row.due_date - timedelta(days=row.remind_days_before),
        "is_overdue": days_until < 0,
    }
    if contract_name is not None:
        out["contract_name"] = contract_name
    return out


def _bookmark_out(row: Bookmark) -> dict:
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "clause_index": row.clause_index,
        "note": row.note or "",
        "created_at": row.created_at,
    }


def _item_out(row: ChecklistItem) -> dict:
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "clause_index": row.clause_index,
        "text": row.text,
        "done": row.done,
        "position": row.position,
        "created_at": row.created_at,
    }


def _date_or_404(db: Session, contract: Contract, date_id: str) -> ContractDate:
    row = (
        db.query(ContractDate)
        .filter(ContractDate.id == date_id, ContractDate.contract_id == contract.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Date not found")
    return row


def _item_or_404(db: Session, contract: Contract, item_id: str) -> ChecklistItem:
    row = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.id == item_id, ChecklistItem.contract_id == contract.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return row


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
@router.get("/contracts/{document_id}/dates")
async def list_dates(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    rows = (
        db.query(ContractDate)
        .filter(ContractDate.contract_id == contract.id)
        .order_by(ContractDate.due_date.asc())
        .all()
    )
    return {"dates": [_date_out(row) for row in rows]}


@router.post("/contracts/{document_id}/dates", status_code=201)
async def add_date(
    document_id: str,
    body: ContractDateCreate,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = ContractDate(
        id=str(uuid.uuid4()),
        contract_id=contract.id,
        label=body.label.strip(),
        due_date=body.due_date,
        kind=body.kind,
        notes=body.notes.strip(),
        remind_days_before=body.remind_days_before,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _date_out(row)


@router.patch("/contracts/{document_id}/dates/{date_id}")
async def update_date(
    document_id: str,
    date_id: str,
    body: ContractDateUpdate,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = _date_or_404(db, contract, date_id)
    data = body.model_dump(exclude_unset=True)
    if "label" in data and data["label"] is not None:
        row.label = data["label"].strip()
    if data.get("due_date") is not None:
        row.due_date = data["due_date"]
    if data.get("kind") is not None:
        row.kind = data["kind"]
    if data.get("notes") is not None:
        row.notes = data["notes"].strip()
    if data.get("remind_days_before") is not None:
        row.remind_days_before = data["remind_days_before"]
    db.commit()
    db.refresh(row)
    return _date_out(row)


@router.delete("/contracts/{document_id}/dates/{date_id}")
async def delete_date(
    document_id: str,
    date_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = _date_or_404(db, contract, date_id)
    db.delete(row)
    db.commit()
    return {"status": "SUCCESS", "deleted": date_id}


# --------------------------------------------------------------------------- #
# Reminders (cross-contract feed)
# --------------------------------------------------------------------------- #
@router.get("/reminders")
async def list_reminders(
    days: int = 30,
    include_overdue: bool = True,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Dates whose due date falls inside the window, plus past-due items."""
    _require_auth(user)
    days = max(0, min(days, 3650))
    today = date.today()
    cutoff = today + timedelta(days=days)

    q = db.query(ContractDate, Contract.name).join(
        Contract, ContractDate.contract_id == Contract.id
    )
    if user is not None:
        q = q.filter(Contract.user_id == user.id)
    else:
        q = q.filter(Contract.user_id.is_(None))
    if include_overdue:
        q = q.filter(ContractDate.due_date <= cutoff)
    else:
        q = q.filter(ContractDate.due_date >= today, ContractDate.due_date <= cutoff)

    rows = q.order_by(ContractDate.due_date.asc()).all()
    reminders = [_date_out(row, contract_name=name) for row, name in rows]
    return {
        "days": days,
        "today": today,
        "overdue": sum(1 for r in reminders if r["is_overdue"]),
        "reminders": reminders,
    }


# --------------------------------------------------------------------------- #
# Bookmarks
# --------------------------------------------------------------------------- #
@router.get("/contracts/{document_id}/bookmarks")
async def list_bookmarks(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    rows = (
        db.query(Bookmark)
        .filter(Bookmark.contract_id == contract.id)
        .order_by(Bookmark.created_at.asc())
        .all()
    )
    return {"bookmarks": [_bookmark_out(row) for row in rows]}


@router.post("/contracts/{document_id}/bookmarks")
async def add_bookmark(
    document_id: str,
    body: BookmarkCreate,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Save a section. Re-saving the same section returns the existing row."""
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    clause = (
        db.query(Clause)
        .filter(Clause.contract_id == contract.id, Clause.clause_index == body.clause_index)
        .first()
    )
    if clause is None:
        raise HTTPException(status_code=404, detail="Section not found")

    existing = (
        db.query(Bookmark)
        .filter(
            Bookmark.contract_id == contract.id,
            Bookmark.clause_index == body.clause_index,
        )
        .first()
    )
    if existing is not None:
        if body.note and body.note.strip() != (existing.note or ""):
            existing.note = body.note.strip()
            db.commit()
            db.refresh(existing)
        return _bookmark_out(existing)

    row = Bookmark(
        id=str(uuid.uuid4()),
        contract_id=contract.id,
        clause_index=body.clause_index,
        note=body.note.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _bookmark_out(row)


@router.delete("/contracts/{document_id}/bookmarks/{bookmark_id}")
async def delete_bookmark(
    document_id: str,
    bookmark_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = (
        db.query(Bookmark)
        .filter(Bookmark.id == bookmark_id, Bookmark.contract_id == contract.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.delete(row)
    db.commit()
    return {"status": "SUCCESS", "deleted": bookmark_id}


# --------------------------------------------------------------------------- #
# Checklist
# --------------------------------------------------------------------------- #
@router.get("/contracts/{document_id}/checklist")
async def list_checklist(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    rows = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.contract_id == contract.id)
        .order_by(ChecklistItem.position.asc(), ChecklistItem.created_at.asc())
        .all()
    )
    return {"items": [_item_out(row) for row in rows]}


@router.post("/contracts/{document_id}/checklist", status_code=201)
async def add_checklist_item(
    document_id: str,
    body: ChecklistItemCreate,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    count = db.query(ChecklistItem).filter(ChecklistItem.contract_id == contract.id).count()
    row = ChecklistItem(
        id=str(uuid.uuid4()),
        contract_id=contract.id,
        clause_index=body.clause_index,
        text=body.text.strip(),
        done=False,
        position=count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.post("/contracts/{document_id}/checklist/generate")
async def generate_checklist(
    document_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Add checklist items derived from this contract's stored analysis.

    Generation is additive and idempotent per section: items already linked to a
    section are not duplicated, and user-written items are never touched.
    """
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)

    clauses = [
        {
            "clause_id": c.clause_index,
            "category": c.category,
            "risk_level": c.risk_level,
            "negotiation_needed": c.negotiation_needed,
            "talking_points": c.talking_points or [],
            "suggested_counter_clause": c.suggested_counter_clause,
        }
        for c in contract.clauses
    ]
    generated = checklist_service.checklist_from_clauses(clauses)
    existing = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.contract_id == contract.id)
        .order_by(ChecklistItem.position.asc(), ChecklistItem.created_at.asc())
        .all()
    )
    new_rows = checklist_service.missing_rows(existing, generated)
    for row in new_rows:
        db.add(
            ChecklistItem(
                id=str(uuid.uuid4()),
                contract_id=contract.id,
                clause_index=row.get("clause_index"),
                text=row["text"],
                done=False,
                position=row["position"],
            )
        )
    db.commit()

    rows = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.contract_id == contract.id)
        .order_by(ChecklistItem.position.asc(), ChecklistItem.created_at.asc())
        .all()
    )
    return {"added": len(new_rows), "items": [_item_out(row) for row in rows]}


@router.patch("/contracts/{document_id}/checklist/{item_id}")
async def update_checklist_item(
    document_id: str,
    item_id: str,
    body: ChecklistItemUpdate,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = _item_or_404(db, contract, item_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("text") is not None:
        row.text = data["text"].strip()
    if data.get("done") is not None:
        row.done = data["done"]
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.delete("/contracts/{document_id}/checklist/{item_id}")
async def delete_checklist_item(
    document_id: str,
    item_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    _require_auth(user)
    contract = _contract_or_404(db, document_id, user)
    row = _item_or_404(db, contract, item_id)
    db.delete(row)
    db.commit()
    return {"status": "SUCCESS", "deleted": item_id}
