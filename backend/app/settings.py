"""Central configuration for ClauseGuard backend.

All values are read from environment variables (backend/.env) with sensible
defaults so the app runs locally with nothing but a GROQ_API_KEY.

Production posture (Phase 7):
  * ``APP_ENV=production`` turns authentication on by default, refuses to start
    with the development JWT secret, and hides the API docs.
  * ``ALLOWED_ORIGINS`` replaces the old wildcard CORS policy with an explicit
    list of browser origins.
"""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default relational store: repo-local SQLite (Phase 2). Override with a
# PostgreSQL URL for cloud deployments (Neon, Render, RDS).
_DEFAULT_DB_URL = "sqlite:///" + os.path.join(
    BASE_DIR, "data", "clauseguard.sqlite3"
).replace("\\", "/")

# Origins the development frontend may use.
_DEV_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"

# The native Android/iOS app talks to the API from the Capacitor WebView,
# whose origin is https://localhost (Android) or capacitor://localhost (iOS).
# These are always allowed so the shipped app keeps working.
_NATIVE_ORIGINS = "https://localhost,capacitor://localhost"

# Development-only fallback. Production must set JWT_SECRET explicitly.
DEV_JWT_SECRET = "dev-only-secret-change-me"


def _env_flag(name: str, default: bool) -> bool:
    """Read a boolean env var; fall back to ``default`` when it is unset."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    BASE_DIR: str = BASE_DIR

    # --- Environment ---
    APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
    IS_PRODUCTION: bool = APP_ENV == "production"

    # --- LLM (Groq) ---
    # mixtral-8x7b-32768 was decommissioned by Groq; gpt-oss-120b is the current
    # supported default and is verified working.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "openai/gpt-oss-120b")
    FAST_MODEL: str = os.getenv("FAST_MODEL", "openai/gpt-oss-20b")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # --- Vector store ---
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", os.path.join(BASE_DIR, "chroma_db"))
    CLAUSE_COLLECTION: str = "clause_chunks"
    DOCS_COLLECTION: str = "documents"
    FAIR_COLLECTION: str = "fair_clauses"
    # Reconcile collections to the cosine metric at startup (rebuilds from the
    # relational store where needed). Set to false to keep the raw store as-is.
    AUTO_RECONCILE_VECTOR_STORE: bool = (
        os.getenv("AUTO_RECONCILE_VECTOR_STORE", "true").lower() in ("1", "true", "yes")
    )

    # --- Grounded chat ---
    CHAT_TOP_K: int = int(os.getenv("CHAT_TOP_K", "6"))
    # Retrieval chunks below this similarity are treated as "no relevant
    # evidence": the chat answers with a refusal instead of ungrounded prose.
    CHAT_MIN_SIMILARITY: float = float(os.getenv("CHAT_MIN_SIMILARITY", "0.30"))

    # --- Relational DB (SQLAlchemy) ---
    # SQLite by default; set DATABASE_URL to a PostgreSQL URL in prod.
    DATABASE_URL: str = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

    # --- Authentication / JWT ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", DEV_JWT_SECRET)
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))
    # When True, analysis/chat/contracts/history/compare require a JWT (Bearer).
    # Development defaults to guest mode; production requires an account.
    REQUIRE_AUTH: bool = _env_flag("REQUIRE_AUTH", IS_PRODUCTION)

    # --- Browser origins (CORS) ---
    # Explicit list of web origins allowed to call this API with credentials.
    # Empty in production means "configure me" — the app refuses to start.
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "").strip()
    # Origins of the packaged native app (Capacitor WebView).
    NATIVE_APP_ORIGINS: str = os.getenv("NATIVE_APP_ORIGINS", _NATIVE_ORIGINS).strip()

    # --- Rate limiting (auth endpoints) ---
    AUTH_RATE_LIMIT: int = int(os.getenv("AUTH_RATE_LIMIT", "10"))
    AUTH_RATE_WINDOW_SECONDS: int = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "300"))

    # --- Optional infra (graceful degradation if not configured) ---
    # Redis (caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    # Firebase (auth + cloud document storage)
    FIREBASE_CREDENTIALS: str = os.getenv("FIREBASE_CREDENTIALS", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # --- Business / product ---
    FREE_TIER_ANALYSES_PER_MONTH: int = int(os.getenv("FREE_TIER_ANALYSES_PER_MONTH", "5"))
    PREMIUM_PRICE_INR: int = os.getenv("PREMIUM_PRICE_INR", "500")

    # --- Uploads ---
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    ALLOWED_UPLOAD_TYPES = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "text/markdown": "md",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }

    # --- Local data store ---
    # NOTE: SQLITE_PATH was removed in Phase 2; point DATABASE_URL at SQLite or
    # Postgres instead.

    # --- Validation ---
    MIN_TEXT_LENGTH: int = int(os.getenv("MIN_TEXT_LENGTH", "50"))


settings = Settings()


def allowed_origins() -> list[str]:
    """Browser origins allowed to call this API.

    * Development keeps the local frontend origins.
    * Production uses ``ALLOWED_ORIGINS`` exactly as configured — there is no
      wildcard fallback.
    * The packaged native app's origins are always allowed.
    """
    origins: list[str] = []
    if not settings.IS_PRODUCTION:
        origins.extend(o.strip().rstrip("/") for o in _DEV_ORIGINS.split(",") if o.strip())
    if settings.ALLOWED_ORIGINS:
        origins.extend(
            o.strip().rstrip("/") for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()
        )
    if settings.NATIVE_APP_ORIGINS:
        origins.extend(
            o.strip().rstrip("/") for o in settings.NATIVE_APP_ORIGINS.split(",") if o.strip()
        )
    seen: set[str] = set()
    return [o for o in origins if not (o in seen or seen.add(o))]
