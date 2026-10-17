"""One row per extracted clause with its full risk + negotiation result."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    clause_index: Mapped[str] = mapped_column(String(30))  # e.g. clause_1

    category: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)

    risk_level: Mapped[str] = mapped_column(String(10), default="yellow")
    risk_score: Mapped[int] = mapped_column(Integer, default=50)
    risk_percentage: Mapped[int] = mapped_column(Integer, default=50)
    explanation: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

    financial_impact: Mapped[str] = mapped_column(Text, default="")
    financial_impact_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    negotiation_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_counter_clause: Mapped[str] = mapped_column(Text, default="")
    talking_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    success_probability: Mapped[int] = mapped_column(Integer, default=50)
    reasoning: Mapped[str] = mapped_column(Text, default="")

    # comparator (RAG) evidence
    standard_match: Mapped[str] = mapped_column(String(20), default="unknown")
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    reference_clause: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="clauses")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Clause {self.clause_index} {self.category} {self.risk_level}>"