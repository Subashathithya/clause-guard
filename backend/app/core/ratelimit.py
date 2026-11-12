"""A small in-memory rate limiter for the sign-in endpoints.

Enough to stop credential stuffing and casual abuse on a single instance. A
multi-instance deployment should point the limiter at Redis instead.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.settings import settings

# bucket name -> {client key -> timestamps of recent attempts}
_BUCKETS: dict[str, dict[str, deque[float]]] = defaultdict(dict)


def client_key(request: Request) -> str:
    """Identify the caller behind a proxy, when there is one."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, bucket: str) -> None:
    """Raise 429 when the caller has made too many attempts in the window."""
    limit = settings.AUTH_RATE_LIMIT
    window = settings.AUTH_RATE_WINDOW_SECONDS
    if limit <= 0 or window <= 0:
        return

    now = time.monotonic()
    key = client_key(request)
    hits = _BUCKETS[bucket].setdefault(key, deque())
    while hits and now - hits[0] > window:
        hits.popleft()

    if len(hits) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a few minutes and try again.",
        )
    hits.append(now)

    # Keep the store small: drop buckets that have gone quiet.
    if len(_BUCKETS[bucket]) > 512:
        for stale_key in [k for k, v in _BUCKETS[bucket].items() if not v]:
            _BUCKETS[bucket].pop(stale_key, None)


def reset_rate_limits() -> None:
    """Clear every bucket (used by tests)."""
    _BUCKETS.clear()
