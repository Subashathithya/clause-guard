"""Thin wrapper around the Groq chat-completions API.

Centralises retries, JSON parsing and model selection so the agents stay
declarative.
"""
import json
import logging
import re
import time
from typing import Any

from groq import Groq
from pydantic import BaseModel, ValidationError

from app.observability import observability
from app.settings import settings

logger = logging.getLogger(__name__)

_client: Groq | None = None
_CALL_COUNT = 0
_CHAR_COUNT = 0


def get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def get_call_count() -> int:
    """Total successful LLM requests since import (used by the eval harness)."""
    return _CALL_COUNT


def get_char_count() -> int:
    """Total prompt characters sent since import (used for cost estimates)."""
    return _CHAR_COUNT


def _extract_json(raw: str) -> Any:
    """Best-effort extraction of a JSON object/array from an LLM response."""
    raw = raw.strip()
    # strip markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # fall back to first {...} or [...] block
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw.find(open_ch)
        end = raw.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("LLM response did not contain valid JSON")


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
    retries: int = 2,
    stage: str = "llm",
) -> str:
    """Return raw assistant text. Retries transient failures."""
    global _CALL_COUNT, _CHAR_COUNT

    client = get_client()
    last_err: Exception | None = None

    kwargs: dict[str, Any] = {
        "model": model or settings.PRIMARY_MODEL,
        "messages": messages,
        "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(retries + 1):
        try:
            completion = client.chat.completions.create(**kwargs)
            _CALL_COUNT += 1
            _CHAR_COUNT += sum(len(str(m.get("content", ""))) for m in messages)
            observability.llm_call(stage=stage, ok=True, attempts=attempt + 1)
            return completion.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last_err = exc
            logger.warning("Groq call failed (attempt %s): %s", attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    observability.llm_call(stage=stage, ok=False, attempts=retries + 1)
    raise RuntimeError(f"LLM call failed after retries: {last_err}")


def chat_json(messages: list[dict], **kwargs: Any) -> Any:
    """Call the LLM and parse the response as JSON."""
    kwargs.setdefault("json_mode", True)
    raw = chat(messages, **kwargs)
    return _extract_json(raw)


def _recover_failed_generation(exc: Exception) -> str | None:
    """Pull Groq's ``failed_generation`` payload out of a 400 json-validation
    RuntimeError chain so already-completed model output is not lost."""
    try:
        text = str(exc)
        start = text.find("'failed_generation'")
        if start == -1:
            return None
        if text.find("'failed_generation': ''") != -1:
            return None
        after = text[start:]
        brace = after.find("{")
        end = after.rfind("}")
        if brace == -1 or end == -1 or end <= brace:
            return None
        return after[brace : end + 1]
    except Exception:  # noqa: BLE001
        return None


def chat_json_validated(
    messages: list[dict],
    *,
    schema: type[BaseModel],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    validation_retries: int = 1,
    stage: str = "structured",
    **kwargs: Any,
) -> tuple[Any | None, Any | None]:
    """Structured LLM call: parse JSON, validate against ``schema``, retry.

    Flow for every structured output:
        LLM call -> JSON parsing -> Pydantic validation -> valid? return
        invalid/unparseable -> up to ``validation_retries`` more LLM attempts
        still invalid -> observability.fallback + (None, None)

    Groq's ``json_object`` response format hard-rejects a generation that does
    not satisfy its server-side JSON validation (``json_validate_failed``).
    That failure is flaky on some models (e.g. ``openai/gpt-oss-120b`` emits
    tokens like ``0. nine``), so when the rejected generation is empty we retry
    the same attempt in plain-text mode and validate the JSON client-side;
    when the rejected generation is present we recover it directly.

    Transport failures keep the existing ``chat()`` retry contract and are
    re-raised as RuntimeError so callers' deterministic fallbacks handle them.

    Returns ``(validated_model_or_None, parsed_data_or_None)``. Nothing here
    touches raw contract content: only stage + counts are observed.
    """
    parsed: Any = None
    for attempt in range(validation_retries + 1):
        raw: str = ""
        try:
            raw = chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
                stage=stage,
                **kwargs,
            )
        except RuntimeError as exc:
            recovered = _recover_failed_generation(exc)
            if recovered is not None:
                raw = recovered
            else:
                # Rejected generation was empty: retry this attempt in
                # plain-text mode (token-stable for these models) and validate
                # the parsed JSON client-side.
                raw = chat(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=False,
                    stage=stage,
                    **kwargs,
                )
        try:
            parsed = _extract_json(raw)
            validated = schema.model_validate(parsed)
        except (ValidationError, ValueError):
            observability.validation(stage=stage, ok=False, attempts=attempt + 1)
            if attempt < validation_retries:
                continue
            observability.fallback(stage=stage)
            return None, parsed
        observability.validation(stage=stage, ok=True, attempts=attempt + 1)
        return validated, parsed
    observability.fallback(stage=stage)
    return None, parsed
