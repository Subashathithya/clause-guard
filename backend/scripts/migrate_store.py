"""One-off migration: legacy pre-Phase-2 SQLite store -> relational store.

Reads the old `data/clauseguard.sqlite3` (tables: analyses, usage) created by
the now-removed `app/sqlite.py` and inserts the rows into the Phase 2
SQLAlchemy store as guest (user_id NULL) records. Idempotent: rows whose id
/ (ip, month) already exist in the target are skipped.

Run from backend/:
    python -m scripts.migrate_store
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Contract, UsageCounter  # noqa: E402
from app.settings import settings  # noqa: E402

LEGACY_PATH = os.path.join(settings.BASE_DIR, "data", "clauseguard.sqlite3")


def migrate_analyses(db) -> tuple[int, int]:
    if not os.path.exists(LEGACY_PATH):
        print(f"Legacy store not found at {LEGACY_PATH} - nothing to migrate.")
        return 0, 0

    conn = sqlite3.connect(LEGACY_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM analyses").fetchall()
    except sqlite3.Error as exc:
        print(f"Could not read legacy analyses table: {exc}")
        return 0, 0

    migrated, skipped = 0, 0
    for row in rows:
        existing = db.query(Contract).filter_by(id=row["id"]).first()
        if existing:
            skipped += 1
            continue
        # created_at was stored as a unix epoch
        created = datetime.fromtimestamp(float(row["created_at"]), tz=timezone.utc).replace(tzinfo=None)
        try:
            payload = json.loads(row["result_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        db.add(
            Contract(
                id=row["id"],
                user_id=None,
                name=row["document_name"],
                source="legacy",
                status=row["status"],
                overall_risk=row["overall_risk"],
                average_risk_score=float(row["avg_risk_score"] or 0),
                red_count=int(row["red_count"] or 0),
                yellow_count=int(row["yellow_count"] or 0),
                green_count=int(row["green_count"] or 0),
                total_clauses=int(row["total_clauses"] or 0),
                char_count=len(payload.get("document_name") or row["document_name"]),
                summary_recommendation=(payload.get("summary") or {}).get("recommendation") or "",
                top_priorities=(payload.get("summary") or {}).get("top_priorities") or [],
                agent_trace=payload.get("agent_trace") or [],
                created_at=created,
            )
        )
        migrated += 1
    db.commit()
    conn.close()
    return migrated, skipped


def migrate_usage(db) -> tuple[int, int]:
    if not os.path.exists(LEGACY_PATH):
        return 0, 0
    conn = sqlite3.connect(LEGACY_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT ip, month, analyze_count FROM usage").fetchall()
    except sqlite3.Error as exc:
        print(f"Could not read legacy usage table: {exc}")
        conn.close()
        return 0, 0

    migrated, skipped = 0, 0
    for row in rows:
        existing = db.query(UsageCounter).filter_by(ip=row["ip"], month=row["month"]).first()
        if existing:
            skipped += 1
            continue
        db.add(UsageCounter(ip=row["ip"], month=row["month"], analyze_count=int(row["analyze_count"])))
        migrated += 1
    db.commit()
    conn.close()
    return migrated, skipped


if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        m1, s1 = migrate_analyses(db)
        m2, s2 = migrate_usage(db)
    print(f"Analyses migrated={m1} skipped={s1}")
    print(f"Usage counters migrated={m2} skipped={s2}")
    print("Done. The legacy tables remain untouched in the same .sqlite3 file.")