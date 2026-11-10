FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data volume: Chroma vectors + the SQLite relational store both live under
# /app/data (see CHROMA_DIR and DATABASE_URL defaults).
VOLUME ["/app/data"]

EXPOSE 8000

# One worker: the demo uses a local SQLite file + persistent Chroma client, and
# a single process avoids write-lock contention. Scale out with Postgres first.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]