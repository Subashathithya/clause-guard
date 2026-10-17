"""Structured internal observability for the AI pipeline.

Collects lightweight, non-sensitive metrics from every engine stage so the
evaluation hooks (Hit@K, evidence-support rate, validation/fallback rates,
LLM calls, latency) can be computed from real runs later.

Privacy contract (enforced at call sites):
  * never log API keys, passwords, full contract text or full chat messages;
  * document IDs and aggregate metadata are allowed;
  * questions are represented only by their character length, never their text.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Any


class Observability:
    """Thread-safe event accumulation with a snapshot() for eval hooks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._counters: Counter[str] = Counter()

    # ------------------------------------------------------------------ core
    def _emit(self, event: str, **fields: Any) -> None:
        with self._lock:
            record: dict[str, Any] = {"event": event, "ts": round(time.time(), 3)}
            record.update(fields)
            self._events.append(record)
            self._counters[f"event:{event}"] += 1
            for key, value in fields.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._counters[f"{event}:{key}:sum"] += value
                    self._counters[f"{event}:{key}:count"] += 1

    # ------------------------------------------------------------ emits
    def llm_call(self, stage: str = "llm", ok: bool = True, attempts: int = 1) -> None:
        """One terminal LLM chat/completion call (after transport retries)."""
        self._emit("llm_call", stage=stage, ok=ok, attempts=attempts)

    def validation(self, stage: str = "", ok: bool = True, attempts: int = 1) -> None:
        """Structured-output validation outcome (ok=False => retried/fallback)."""
        self._emit("validation", stage=stage, ok=ok, attempts=attempts)

    def retrieval(
        self,
        stage: str = "rag",
        query_chars: int = 0,
        requested_count: int = 0,
        top_k: int = 0,
        returned: int = 0,
        empty: bool = False,
        scope_ids: list[str] | None = None,
    ) -> None:
        """Vector retrieval event. IDs only; never the query text."""
        self._emit(
            "retrieval",
            stage=stage,
            query_chars=query_chars,
            requested_count=requested_count,
            top_k=top_k,
            returned=returned,
            empty=empty,
            scope_ids=scope_ids or [],
        )

    def evidence(self, checked: int = 0, supported: int = 0, unsupported: int = 0) -> None:
        self._emit("evidence", checked=checked, supported=supported, unsupported=unsupported)

    def fallback(self, stage: str = "") -> None:
        """Deterministic fallback engaged for a stage."""
        self._emit("fallback", stage=stage)

    def latency(self, stage: str = "", ms: float = 0.0) -> None:
        self._emit("latency", stage=stage, ms=round(ms, 3))

    def chat(self, grounded: bool = True, sources: int = 0) -> None:
        """Outcome of a /chat turn."""
        self._emit("chat", grounded=grounded, sources=sources)

    # ------------------------------------------------------------ queries
    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def snapshot(self) -> dict[str, Any]:
        """Aggregated counters for the evaluation hooks (no raw content)."""
        with self._lock:
            c = dict(self._counters)

        def s(key: str) -> int:
            return int(c.get(key, 0))

        def fail(key: str) -> int:
            return max(0, s(f"event:{key}") - s(f"{key}:ok:count"))

        return {
            "llm_calls": s("event:llm_call"),
            "llm_call_failures": fail("llm_call"),
            "llm_call_attempts_total": s("llm_call:attempts:sum"),
            "validation_events": s("event:validation"),
            "validation_failures": fail("validation"),
            "validation_attempts_total": s("validation:attempts:sum"),
            "retrieval_events": s("event:retrieval"),
            "empty_retrievals": s("retrieval:empty:count"),
            "retrieval_returned_total": s("retrieval:returned:sum"),
            "retrieval_topk_total": s("retrieval:top_k:sum"),
            "evidence_checked": s("evidence:checked:sum"),
            "evidence_supported": s("evidence:supported:sum"),
            "evidence_unsupported": s("evidence:unsupported:sum"),
            "fallback_events": s("event:fallback"),
            "latency_events": s("event:latency"),
            "latency_ms_total": round(float(c.get("latency:ms:sum", 0.0)), 3),
            "chat_turns": s("event:chat"),
            "chat_grounded": s("chat:grounded:count"),
            "chat_refusals": max(0, s("event:chat") - s("chat:grounded:count")),
        }

    def reset(self) -> None:
        with self._lock:
            self._events = []
            self._counters = Counter()


# Module-level singleton used across all stages.
observability = Observability()