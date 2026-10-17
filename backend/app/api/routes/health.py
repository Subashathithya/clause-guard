"""Service health + pipeline/RAG status endpoint."""
from fastapi import APIRouter

from app import db
from app.constants import APP_VERSION, PIPELINE_AGENTS
from app.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "API is running",
        "version": APP_VERSION,
        "model": settings.PRIMARY_MODEL,
        "pipeline": PIPELINE_AGENTS,
        "auth_required": settings.REQUIRE_AUTH,
        "rag": {
            "documents_indexed": len(db.get_documents()),
            "fair_clauses": db.fair_clause_count(),
            "vector_store": "chromadb",
        },
    }