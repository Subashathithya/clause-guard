"""Analysed contract (one row per completed /analyze or /upload run).

Raw text is kept for re-analysis and owner-scoped access; aggregate risk and the
agent trace are denormalised here so list/history endpoints never hit the LLM.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20), default="paste")  # paste | upload
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS")

    overall_risk: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    average_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    red_count: Mapped[int] = mapped_column(Integer, default=0)
    yellow_count: Mapped[int] = mapped_column(Integer, default=0)
    green_count: Mapped[int] = mapped_column(Integer, default=0)
    total_clauses: Mapped[int] = mapped_column(Integer, default=0)
    total_financial_exposure_inr: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)

    summary_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_priorities: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped["User | None"] = relationship("User", back_populates="contracts")
    clauses: Mapped[list["Clause"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Contract {self.name!r} ({self.id[:8]})>"