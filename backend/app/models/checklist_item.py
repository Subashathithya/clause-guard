"""One item in a contract's negotiation checklist.

Items are either generated from the stored analysis (real negotiation points
and talking points) or added by the user. They stay attached to the contract so
progress survives reloads and device changes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    # Links the item back to the section it came from, when there is one.
    clause_index: Mapped[str | None] = mapped_column(String(30), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="checklist_items")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ChecklistItem {self.text[:24]!r} done={self.done}>"
