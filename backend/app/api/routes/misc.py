"""Misc utility endpoints (e.g. LLM provider key check)."""
from fastapi import APIRouter

from app.llm import get_client
from app.settings import settings

router = APIRouter()


@router.post("/test-api-key")
async def test_api_key():
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
        return {"status": "ERROR", "message": str(exc), "api_key_valid": False}