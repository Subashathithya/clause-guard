"""Remove legacy / scratch contracts from the workspace.

Earlier manual testing leaves rows named "My Contract", "Unnamed Document",
"probe" and similar at the top of the list. This script lists them and, with
``--yes``, deletes them (vector entries + relational rows).

Seeded demo documents (from ``scripts/seed_demo.py``) are always preserved.

Usage (from ``backend``):

    python scripts/clean_workspace.py                 # dry run: show what would go
    python scripts/clean_workspace.py --yes           # delete guest scratch rows
    python scripts/clean_workspace.py --yes --scope all   # guest + demo user rows
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db as vdb  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Contract, User  # noqa: E402
from app.services import contract_service  # noqa: E402
from scripts.seed_demo import _NAMESPACE, _documents  # noqa: E402


def _seeded_ids() -> set[str]:
    ids: set[str] = set()
    for key, *_ in _documents():
        ids.add(str(uuid.uuid5(_NAMESPACE, f"guest:{key}")))
        ids.add(str(uuid.uuid5(_NAMESPACE, f"demo:{key}")))
    return ids


def main() -> None:
    apply = "--yes" in sys.argv
    scope_all = "--scope" in sys.argv and "all" in sys.argv

    init_db()
    session = SessionLocal()
    keep = _seeded_ids()
    try:
        query = session.query(Contract)
        if not scope_all:
            query = query.filter(Contract.user_id.is_(None))

        removable = [c for c in query.all() if c.id not in keep]

        if not removable:
            print("Nothing to clean — workspace already looks tidy.")
            return

        print(f"{'Deleting' if apply else 'Would delete'} {len(removable)} contract(s):\n")
        for c in sorted(removable, key=lambda c: c.created_at, reverse=True):
            print(f"  - {c.name[:60]:60}  {c.created_at:%Y-%m-%d}  {c.id[:8]}")

        if not apply:
            print("\nDry run. Re-run with --yes to delete these rows.")
            return

        for c in removable:
            vdb.delete_document(c.id)
            contract_service.delete_contract(session, c)
        print(f"\nRemoved {len(removable)} contract(s). Demo documents were preserved.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
