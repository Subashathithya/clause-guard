"""Create the ClauseGuard API service on Render through the Render API.

Render's free web services cannot hold a disk, so the relational store lives in
an external Postgres (Neon) and the vector store is rebuilt at startup.

Inputs (environment variables):
    RENDER_API_KEY   a Render API key (dashboard -> Settings -> API Keys)
    DATABASE_URL     the Postgres connection string
    GROQ_API_KEY     optional: read from backend/.env when not set

Usage:
    $env:RENDER_API_KEY = "rnd_..."
    $env:DATABASE_URL   = "postgresql://..."
    python scripts/create_render_service.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO = "https://github.com/Subashathithya/clause-guard"
FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN", "https://clause-guard-virid.vercel.app"
)


def read_groq_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if key:
        return key
    env = BACKEND_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GROQ_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call(method: str, path: str, api_key: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "https://api.render.com" + path,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:800]
    except Exception as exc:
        return None, str(exc)[:200]


def main() -> int:
    api_key = os.getenv("RENDER_API_KEY", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    groq = read_groq_key()

    missing = [
        name
        for name, value in (
            ("RENDER_API_KEY", api_key),
            ("DATABASE_URL", database_url),
            ("GROQ_API_KEY", groq),
        )
        if not value
    ]
    if missing:
        print("Missing: " + ", ".join(missing))
        print(
            "  RENDER_API_KEY: Render dashboard -> Settings -> API Keys -> Create API Key\n"
            "  DATABASE_URL  : the Neon pooled connection string\n"
            "  GROQ_API_KEY  : taken from backend/.env when present"
        )
        return 1

    payload = {
        "name": "clauseguard-api",
        "type": "web",
        "repo": REPO,
        "branch": "main",
        "plan": "free",
        "runtime": "docker",
        "dockerContext": "./backend",
        "dockerfilePath": "./backend/Dockerfile",
        "healthCheckPath": "/health",
        "autoDeployTrigger": "checksPassWithCommits",
        "envVars": [
            {"key": "GROQ_API_KEY", "value": groq},
            {"key": "DATABASE_URL", "value": database_url},
            {"key": "ALLOWED_ORIGINS", "value": FRONTEND_ORIGIN},
            {"key": "APP_ENV", "value": "production"},
            {"key": "REQUIRE_AUTH", "value": "true"},
            {"key": "JWT_SECRET", "generateValue": True},
            {"key": "PRIMARY_MODEL", "value": "openai/gpt-oss-120b"},
            {"key": "FAST_MODEL", "value": "openai/gpt-oss-20b"},
            {"key": "CHAT_MIN_SIMILARITY", "value": "0.25"},
            {"key": "AUTO_RECONCILE_VECTOR_STORE", "value": "true"},
            {"key": "CHROMA_DIR", "value": "/tmp/chroma_db"},
            {"key": "SEED_DEMO_ON_STARTUP", "value": "true"},
        ],
    }

    status, created = call("POST", "/v1/services", api_key, payload)
    print("create service ->", status)
    if status not in (200, 201):
        print(str(created)[:800])
        return 1

    service = created.get("service") or created
    sid = service.get("id")
    print("service id :", sid)
    print("service url:", service.get("serviceDetails", {}).get("webServiceDetail", {}).get("url")
          or service.get("url"))
    print("dashboard :", f"https://dashboard.render.com/web/srv/{sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
