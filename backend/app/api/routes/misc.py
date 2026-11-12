"""Misc utility endpoints (e.g. LLM provider key check).

The key check is an owner-only diagnostic: it confirms whether the server's
LLM credential works. It is not a public capability check.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.errors import public_error
from app.core.security import get_current_user
from app.database import get_db
from app.llm import get_client
from app.models import User
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test-api-key")
async def test_api_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        client = get_client()
        completion = client.chat.completions.create(
            model=settings.FAST_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": "Reply with: API working"}],
        )
        return {"status": "SUCCESS", "message": completion.choices[0].message.content,
                "api_key_valid": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM key check failed: %s", exc)
        raise public_error(
            502,
            "The analysis service is not reachable right now. Please try again later.",
            exc,
        ) from exc