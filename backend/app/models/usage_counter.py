"""Per-IP monthly usage counters for anonymous (guest) quota enforcement."""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM
    analyze_count: Mapped[int] = mapped_column(Integer, default=0)