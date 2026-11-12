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
    tracking,
)
from app.constants import APP_VERSION
from app.database import init_db
from app.settings import DEV_JWT_SECRET, allowed_origins

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clauseguard")

# The interactive docs describe every endpoint; they are helpful while
# developing and unnecessary (and noisy) in production.
_DOCS = None if settings.IS_PRODUCTION else "/docs"

app = FastAPI(
    title="ClauseGuard API",
    version=APP_VERSION,
    docs_url=_DOCS,
    redoc_url=None if settings.IS_PRODUCTION else "/redoc",
    openapi_url=None if settings.IS_PRODUCTION else "/openapi.json",
)

# --- CORS -----------------------------------------------------------------
# Phase 7: an explicit origin list replaces the old wildcard. Credentials are
# only ever allowed for origins the operator named.
_origins = allowed_origins()
if "*" in _origins:
    logger.warning(
        "ALLOWED_ORIGINS contains '*' - browser credentials are disabled for CORS."
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
logger.info("CORS origins: %s", ", ".join(_origins) or "(none configured)")


@app.middleware("http")
async def _security_headers(request, call_next):
    """Baseline security headers on every response."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if settings.IS_PRODUCTION:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.middleware("http")
async def _limit_request_size(request, call_next):
    """Reject oversized bodies before they are read into memory."""
    raw_length = request.headers.get("content-length")
    if raw_length and raw_length.isdigit():
        max_bytes = (settings.MAX_UPLOAD_MB + 1) * 1024 * 1024
        if int(raw_length) > max_bytes:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={"detail": f"Request is larger than {settings.MAX_UPLOAD_MB} MB."},
            )
    return await call_next(request)


def _check_production_config() -> None:
    """Refuse to start a production instance with unsafe settings."""
    problems: list[str] = []
    if settings.JWT_SECRET == DEV_JWT_SECRET:
        problems.append("JWT_SECRET is still the development default")
    elif len(settings.JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be at least 32 characters")
    if not settings.ALLOWED_ORIGINS.strip():
        problems.append("ALLOWED_ORIGINS must list the frontend origins")
    if not settings.REQUIRE_AUTH:
        problems.append("REQUIRE_AUTH must be enabled")
    if not settings.GROQ_API_KEY:
        problems.append("GROQ_API_KEY is not set")
    if problems:
        raise RuntimeError(
            "Refusing to start with APP_ENV=production: " + "; ".join(problems)
        )


@app.on_event("startup")
def _startup() -> None:
    if settings.IS_PRODUCTION:
        _check_production_config()
        logger.info("Production posture verified (auth required, explicit origins).")
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
    tracking.router,
):
    app.include_router(_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)