"""Phase 7 security tests: CORS, error hygiene, auth enforcement, rate limits.

These lock in the guarantees the app now makes to the people using it:
  * only configured browser origins may call the API with credentials;
  * internal failures never reach the caller as text;
  * production cannot start with the development settings;
  * the sign-in endpoints are rate limited.
"""
import pytest


LONG_TEXT = "This is a residential lease agreement. " * 10  # well over the 50 char minimum


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #
def test_allowed_origin_gets_credentials(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_unknown_origin_gets_no_cors_grant(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "https://not-our-site.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Without the matching allow-origin header the browser blocks the call,
    # whatever else the preflight response carries.
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}
    assert resp.status_code == 400


def test_wildcard_is_not_used(monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ALLOWED_ORIGINS", "", raising=False)
    monkeypatch.setattr(settings_module.settings, "IS_PRODUCTION", False, raising=False)
    origins = settings_module.allowed_origins()
    assert "*" not in origins
    assert "http://127.0.0.1:3000" in origins

    # In production only the configured origins (plus the native app) are used.
    monkeypatch.setattr(settings_module.settings, "IS_PRODUCTION", True, raising=False)
    production_origins = settings_module.allowed_origins()
    assert "http://127.0.0.1:3000" not in production_origins
    assert "https://localhost" in production_origins  # the packaged Android app


# --------------------------------------------------------------------------- #
# Error hygiene
# --------------------------------------------------------------------------- #
def test_analysis_failure_does_not_leak_internals(client, monkeypatch):
    from app.api.routes import analysis as analysis_route

    secret = "SECRET-UPSTREAM-KEY-abc123"

    def boom(*args, **kwargs):
        raise RuntimeError(f"upstream failed with {secret} at /srv/app/llm.py:42")

    monkeypatch.setattr(analysis_route, "run_orchestrator", boom)

    resp = client.post("/analyze", json={"text": LONG_TEXT, "document_name": "Lease"})
    assert resp.status_code == 500
    body = resp.text
    assert secret not in body
    assert "Traceback" not in body
    assert "/srv/app" not in body
    # The caller still gets something useful: plain language plus a reference.
    assert "reference" in body


def test_upload_failure_does_not_leak_internals(client, monkeypatch):
    from app.api.routes import analysis as analysis_route

    secret = "SECRET-PDF-LIB-xyz789"

    def boom(*args, **kwargs):
        raise ValueError(f"pdf internals: {secret} /usr/lib/python3/site-packages/pypdf/x.py")

    monkeypatch.setattr(analysis_route.uploads, "extract_text", boom)

    resp = client.post(
        "/upload",
        files={"file": ("lease.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"document_name": "Lease"},
    )
    assert resp.status_code == 400
    assert secret not in resp.text
    assert "/usr/lib" not in resp.text


def test_api_key_check_does_not_leak_internals(client, monkeypatch):
    from app.api.routes import misc as misc_route

    secret = "SECRET-GROQ-KEY-123"

    def boom():
        raise RuntimeError(f"401 Unauthorized for key gsk_{secret}")

    monkeypatch.setattr(misc_route, "get_client", boom)

    resp = client.post("/test-api-key")
    # The endpoint is owner-only, so a guest cannot even reach it.
    assert resp.status_code == 401
    assert secret not in resp.text


def test_orchestrator_trace_hides_internal_error_text(monkeypatch):
    from app.agents import orchestrator as orchestrator_module

    secret = "SECRET-EXTRACTOR-ERR"

    class Boom:
        def extract(self, text):
            raise RuntimeError(f"boom {secret}")

    orchestrator = orchestrator_module.Orchestrator.__new__(orchestrator_module.Orchestrator)
    orchestrator.extractor = Boom()
    orchestrator.agent_flags = []
    result = orchestrator.run("some contract text", "Doc")
    payload = result.model_dump()
    assert secret not in str(payload)
    assert payload["status"] == "EXTRACTOR_ERROR"


# --------------------------------------------------------------------------- #
# Authentication enforcement
# --------------------------------------------------------------------------- #
def test_require_auth_blocks_guests(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "REQUIRE_AUTH", True, raising=False)
    resp = client.post("/analyze", json={"text": LONG_TEXT})
    assert resp.status_code == 401
    assert client.get("/contracts").status_code == 401


def test_guest_mode_still_works_without_auth(client, monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "REQUIRE_AUTH", False, raising=False)
    resp = client.post("/analyze", json={"text": LONG_TEXT})
    # The pipeline is stubbed out in tests, so any non-401 status is fine; the
    # point is that the guest is not turned away.
    assert resp.status_code != 401


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
def test_login_is_rate_limited(client, monkeypatch):
    from app.core import ratelimit
    from app.settings import settings

    ratelimit.reset_rate_limits()
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 3, raising=False)
    monkeypatch.setattr(settings, "AUTH_RATE_WINDOW_SECONDS", 60, raising=False)

    statuses = [
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-pass"}).status_code
        for _ in range(4)
    ]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    ratelimit.reset_rate_limits()


# --------------------------------------------------------------------------- #
# Production posture
# --------------------------------------------------------------------------- #
def test_production_refuses_unsafe_settings(monkeypatch):
    from app.main import _check_production_config
    from app.settings import DEV_JWT_SECRET, settings

    monkeypatch.setattr(settings, "JWT_SECRET", DEV_JWT_SECRET, raising=False)
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "", raising=False)
    monkeypatch.setattr(settings, "REQUIRE_AUTH", False, raising=False)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "", raising=False)

    with pytest.raises(RuntimeError) as exc:
        _check_production_config()
    message = str(exc.value)
    assert "JWT_SECRET" in message
    assert "ALLOWED_ORIGINS" in message
    assert "REQUIRE_AUTH" in message


def test_production_passes_with_safe_settings(monkeypatch):
    from app.main import _check_production_config
    from app.settings import settings

    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 48, raising=False)
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clauseguard.app", raising=False)
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True, raising=False)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-test", raising=False)
    _check_production_config()  # must not raise


# --------------------------------------------------------------------------- #
# Headers and body limits
# --------------------------------------------------------------------------- #
def test_security_headers_are_present(client):
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers["permissions-policy"]


def test_oversized_body_is_rejected(client):
    from app.settings import settings

    limit = (settings.MAX_UPLOAD_MB + 1) * 1024 * 1024
    resp = client.post(
        "/analyze",
        content=b"x" * 10,
        headers={"Content-Length": str(limit + 1), "Content-Type": "application/json"},
    )
    assert resp.status_code == 413
