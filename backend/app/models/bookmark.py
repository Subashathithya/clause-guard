"""A saved section (clause) inside one analyzed contract."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class Bookmark(Base):
    __tablename__ = "contract_bookmarks"
    __table_args__ = (
        UniqueConstraint("contract_id", "clause_index", name="uq_bookmark_contract_clause"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    clause_index: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="bookmarks")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Bookmark {self.contract_id[:8]} {self.clause_index}>"
