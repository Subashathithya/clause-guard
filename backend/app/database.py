"""SQLAlchemy engine, session factory and declarative base.

Dev default is SQLite (data/clauseguard.sqlite3, inside the repo). Set
``DATABASE_URL`` to a PostgreSQL URL for cloud deployments (Neon, Render, RDS).

Models live in ``app/models``; persistence helpers in ``app/services``.
"""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import settings

DATABASE_URL = settings.DATABASE_URL

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def utcnow() -> datetime:
    """Naive-UTC now (stored consistently across SQLite and Postgres)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create whatever tables are missing. Idempotent."""
    from app import models  # noqa: F401 - registers all models on Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a scoped session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()