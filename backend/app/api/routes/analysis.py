"""Contract analysis endpoints: /analyze (pasted text) and /upload (files).

An analysis is persisted in three places:
  * Chroma — clause chunks (RAG + chat) and cached analysis JSON (legacy reads);
  * relational — the authoritative Contract/Clause rows (Phase 2 owner scoping);
  * anonymous UsageCounter / user Contract count — monthly quota enforcement.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app import db as vdb
from app import uploads
from app.agents.orchestrator import run_orchestrator
from app.core.security import get_optional_user
from app.database import get_db
from app.models import User
from app.schemas import DocumentInput
from app.services import contract_service
from app.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_minimum_length(text: str) -> str:
    text = (text or "").strip()
    if len(text) < settings.MIN_TEXT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Text is too short: {len(text)} chars. "
                f"Paste at least {settings.MIN_TEXT_LENGTH} characters of contract text."
            ),
        )
    return text


def _quota_guard(request: Request, db: Session, user: Optional[User]) -> tuple[int, Optional[str], Optional[str]]:
    """Return (remaining, user_id, anon_ip); raises 401/429 when blocked."""
    if user is not None:
        return contract_service.user_remaining(db, user), user.id, None
    if settings.REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required")
    ip = request.client.host if request.client else "unknown"
    return contract_service.anonymous_remaining(db, ip), None, ip


def _persist_and_return(
    request: Request,
    result,
    document_name: str,
    text: str,
    source: str,
    db: Session,
    user: Optional[User],
    anon_ip: Optional[str],
) -> dict:
    document_id = str(uuid.uuid4())
    vdb.index_document(document_id, document_name, text)
    payload = result.model_dump()
    payload["document_id"] = document_id
    payload["document_name"] = document_name
    vdb.save_analysis(document_id, document_name, payload)
    contract_service.persist_contract(
        db, result=result, document_id=document_id, name=document_name,
        text=text, source=source, user_id=user.id if user else None,
    )
    if anon_ip:
        contract_service.bump_anonymous_usage(db, anon_ip)
    payload["source"] = source
    payload["user_id"] = user.id if user else None
    return payload


@router.post("/analyze")
async def analyze_contract(
    input_data: DocumentInput,
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    text = _require_minimum_length(input_data.text)
    remaining, _, anon_ip = _quota_guard(request, db, user)
    try:
        result = run_orchestrator(text, input_data.document_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    if result.status == "NO_CLAUSES":
        return result.model_dump()

    payload = _persist_and_return(request, result, input_data.document_name, text, "paste", db, user, anon_ip)
    payload["quota_remaining"] = max(0, remaining - 1)
    return payload


@router.post("/upload")
async def upload_contract(
    request: Request,
    file: UploadFile = File(...),
    document_name: str = Form("Uploaded Document"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB} MB")

    file_type = uploads.detect_file_type(file.content_type or "", file.filename or "")
    if file_type not in settings.ALLOWED_UPLOAD_TYPES.values():
        hint = " (Legacy .doc is not supported - save as .docx or PDF.)" if file_type == "doc" else ""
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.filename or file.content_type}{hint}",
        )

    try:
        text = uploads.extract_text(content, file.content_type or "", file.filename or "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    text = _require_minimum_length(text)

    remaining, _, anon_ip = _quota_guard(request, db, user)
    try:
        result = run_orchestrator(text, document_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    if result.status == "NO_CLAUSES":
        return result.model_dump()

    payload = _persist_and_return(request, result, document_name, text, "upload", db, user, anon_ip)
    payload["quota_remaining"] = max(0, remaining - 1)
    return payload