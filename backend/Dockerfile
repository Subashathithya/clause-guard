FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data volume: only runtime state lives under /app/data/persist, so the
# read-only knowledge base at /app/data/fair_clauses.json from the image stays
# visible (a mount directly on /app/data would shadow it).
VOLUME ["/app/data/persist"]

EXPOSE 8000

# One worker: the demo uses a local SQLite file + persistent Chroma client, and
# a single process avoids write-lock contention. Scale out with Postgres first.
# --no-server-header / --no-date-header keep the server banner out of the
# responses; the app sets its own security headers.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-server-header --no-date-header --proxy-headers --forwarded-allow-ips=\"*\""]