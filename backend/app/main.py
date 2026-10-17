"""ClauseGuard FastAPI application — app factory + router registration.

Endpoints live in `app/api/routes/` (one module per resource area):

    GET    /health               health.py
    POST   /analyze              analysis.py
    POST   /upload               analysis.py
    POST   /chat                 chat.py
    POST   /compare              compare.py
    POST   /drift                compare.py
    GET    /contracts ...        contracts.py
    GET    /fair-clauses ...     knowledge.py
    GET    /stats, /history      history.py
    POST   /test-api-key         misc.py
    POST   /auth/...             auth.py

Run (from backend/):
    python -m uvicorn app.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.settings import settings
from app.api.routes import (
    analysis,
    auth,
    chat,
    compare,
    contracts,
    health,
    history,
    knowledge,
    misc,
)
from app.constants import APP_VERSION
from app.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clauseguard")

app = FastAPI(title="ClauseGuard API", version=APP_VERSION)

allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    # Vector-store reconcile: legacy collections created with the default l2
    # (Euclidean) HNSW space make the 0..1 similarity thresholds saturate at 0.
    # Recreate any non-cosine collection from the relational store (cosine space)
    # so retrieval math and the grounded-chat thresholds hold. Controlled by
    # ``AUTO_RECONCILE_VECTOR_STORE``. No content is logged by this step.
    if settings.AUTO_RECONCILE_VECTOR_STORE:
        try:
            migrated = db.collections_need_migration()
            if migrated:
                db.recreate_collections(migrated)
                logger.info("Vector collections recreated on cosine space: %s (%s)",
                            migrated, db.seed_fair_clauses())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector-store reconcile failed (continuing): %s", exc)
    try:
        count = db.seed_fair_clauses()
        logger.info("Fair-clause library ready: %s references", count)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not seed fair clauses: %s", exc)


for _router in (
    health.router,
    auth.router,
    analysis.router,
    chat.router,
    compare.router,
    contracts.router,
    knowledge.router,
    history.router,
    misc.router,
):
    app.include_router(_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)