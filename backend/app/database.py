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

if DATABASE_URL.startswith("sqlite"):
    # SQLite ignores ``ON DELETE CASCADE`` unless foreign-key enforcement is
    # turned on for every connection. Without this, deleting a contract left
    # its clause rows behind (orphans that resurfaced as duplicated sections
    # when a document id was reused, e.g. by the demo seeder).
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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