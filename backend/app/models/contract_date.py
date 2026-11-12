"""A user-tracked date for one analyzed contract.

Dates are deliberately user-owned: ClauseGuard can *suggest* dates it finds in
the contract text, but a reminder is only created when the user adds one. Each
date carries its own lead time so reminders stay in-app and predictable.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class ContractDate(Base):
    __tablename__ = "contract_dates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )

    label: Mapped[str] = mapped_column(String(120))
    due_date: Mapped[date] = mapped_column(Date)
    # payment | renewal | notice | termination | other
    kind: Mapped[str] = mapped_column(String(20), default="other")
    notes: Mapped[str] = mapped_column(Text, default="")
    remind_days_before: Mapped[int] = mapped_column(Integer, default=7)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="dates")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ContractDate {self.label!r} {self.due_date}>"
