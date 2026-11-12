"""Back up the ClauseGuard data store.

Copies the relational database (SQLite) with a consistent snapshot — the
online backup API is used, so a write during the copy cannot corrupt the
result — and leaves the vector store alone: ChromaDB is always rebuildable from
the relational rows and the fair-clause library.

Usage (from the ``backend`` directory)::

    python scripts/backup_store.py                     # writes data/backups/
    python scripts/backup_store.py --out /mnt/persist  # somewhere else
    python scripts/backup_store.py --keep 14           # keep the last 14 copies

On a Render deployment with a mounted disk, run this from the Render Shell
(Settings -> Shell) or from a cron job; the disk lives at /app/data/persist.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = BACKEND_DIR / "data" / "backups"


def _sqlite_path(database_url: str) -> Path | None:
    """The local SQLite file for a DATABASE_URL, or None for another engine."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix):]
    if not raw or raw == ":memory:":
        return None
    return Path(raw)


def _copy_sqlite(source: Path, target: Path) -> None:
    """Copy a SQLite database using its online backup API."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)


def _copy_plain(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up the ClauseGuard store.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="backup folder")
    parser.add_argument("--keep", type=int, default=14, help="how many copies to keep")
    args = parser.parse_args()

    # Read the same environment the app reads.
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND_DIR / ".env")
    except Exception:  # noqa: BLE001 — dotenv is optional here
        pass

    database_url = os.getenv("DATABASE_URL", "")
    out_dir = Path(args.out)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_dir / f"clauseguard-{stamp}.sqlite3"

    source = _sqlite_path(database_url) if database_url else None
    if source is None:
        # Fall back to the default local SQLite file.
        source = BACKEND_DIR / "data" / "clauseguard.sqlite3"

    if not source.exists():
        print(f"Nothing to back up: {source} does not exist.")
        return 1

    try:
        if source.suffix == ".sqlite3" or source.suffix == ".db":
            _copy_sqlite(source, target)
        else:
            _copy_plain(source, target)
    except Exception as exc:  # noqa: BLE001
        print(f"Backup failed: {exc}")
        return 1

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"Backup written: {target} ({size_mb:.1f} MB)")

    # Keep only the most recent copies.
    copies = sorted(out_dir.glob("clauseguard-*.sqlite3"))
    for old in copies[: max(0, len(copies) - max(1, args.keep))]:
        old.unlink()
        print(f"Removed old backup: {old.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
