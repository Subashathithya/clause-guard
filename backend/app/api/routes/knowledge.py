"""Knowledge base endpoints: the fair-clause reference library."""
import json
import os

from fastapi import APIRouter

from app import db

router = APIRouter()


@router.get("/fair-clauses")
async def fair_clauses(limit: int = 5):
    with open(os.path.join(db.DATA_DIR, "fair_clauses.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    by_category: dict[str, int] = {}
    samples_by_category: dict[str, list[str]] = {}
    for category, texts in (data.get("clauses_by_category") or {}).items():
        by_category[category] = len(texts)
        samples_by_category[category] = texts[:limit]
    return {
        "version": data.get("version", "2.0"),
        "count": data.get("total", sum(by_category.values())),
        "indexed": db.fair_clause_count(),
        "by_category": by_category,
        "samples_by_category": samples_by_category,
    }


@router.post("/fair-clauses/seed")
async def seed_fair_clauses(force: bool = False):
    return {"status": "SUCCESS", "indexed": db.seed_fair_clauses(force=force)}