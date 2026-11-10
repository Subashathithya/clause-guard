"""RAG question-answering over indexed contracts: POST /chat."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import db as vdb
from app.core.security import get_optional_user
from app.database import get_db
from app.llm import chat
from app.models import ChatMessage, User
from app.observability import observability
from app.schemas import ChatInput
from app.services import contract_service
from app.settings import settings

router = APIRouter()


def _no_evidence_answer(question: str, requested: Optional[list[str]]) -> str:
    """Fallback message when retrieval finds nothing relevant enough to ground an answer."""
    scope = "your selected contracts" if requested else "the contracts you've reviewed"
    return (
        f"I couldn't find anything relevant in {scope} to answer that reliably, so I'd "
        "rather not guess. Try rephrasing the question, or analysing the document first "
        "so I can ground my answer in the actual clauses."
    )


@router.post("/chat")
async def chat_with_contracts(
    input_data: ChatInput,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if user is None and settings.REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not input_data.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    visible = contract_service.visible_document_ids(db, user)
    # Scope retrieval to the caller's own documents. When explicit ids are
    # supplied, keep only the ones they can see; an empty result means "search
    # nothing", never a silent fall back to the global corpus.
    if input_data.document_ids:
        requested = [d for d in input_data.document_ids if d in visible]
    else:
        requested = list(visible)

    context = vdb.retrieve_context(input_data.question, requested)
    observability.retrieval(
        stage="chat",
        query_chars=len(input_data.question),
        requested_count=len(requested) if requested else 0,
        top_k=settings.CHAT_TOP_K,
        returned=len(context),
        empty=not context,
        scope_ids=requested,
    )

    relevant = [c for c in context if c["similarity"] >= settings.CHAT_MIN_SIMILARITY]
    if not relevant and input_data.document_ids and visible:
        # A narrow "selected contracts" query came up empty — broaden to every
        # document the caller owns (never to documents they cannot see).
        context = vdb.retrieve_context(input_data.question, list(visible))
        relevant = [c for c in context if c["similarity"] >= settings.CHAT_MIN_SIMILARITY]
    if not relevant:
        observability.chat(grounded=False, sources=0)
        answer = _no_evidence_answer(input_data.question, requested)
        db.add(
            ChatMessage(
                user_id=user.id if user else None,
                question=input_data.question,
                answer=answer,
                used_documents=[],
                sources=[],
            )
        )
        db.commit()
        return {
            "answer": answer,
            "status": "NO_CONTEXT",
            "used_documents": [],
            "sources": [],
        }

    context_block = "\n\n".join(
        f"[{c['document_name']} | {c['similarity']:.0%}]\n{c['text']}" for c in relevant
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are ClauseGuard, a legal-tech assistant. Answer the user's question "
                "based ONLY on the retrieved contract context below. Quote specific clauses "
                "when relevant, flag risks, and suggest better wording. If context is "
                "insufficient, say so clearly.\n\n"
                f"=== RETRIEVED CONTRACT CONTEXT ===\n{context_block}"
            ),
        }
    ]
    messages += [h for h in input_data.history[-10:] if h.get("role") in ("user", "assistant")][-10:]
    messages.append({"role": "user", "content": input_data.question})

    answer = chat(messages, max_tokens=1024, temperature=0.3)
    observability.chat(grounded=True, sources=len(relevant))
    db.add(
        ChatMessage(
            user_id=user.id if user else None,
            question=input_data.question,
            answer=answer,
            used_documents=sorted({c["document_name"] for c in context}),
            sources=context,
        )
    )
    db.commit()
    return {
        "answer": answer,
        "status": "SUCCESS",
        "used_documents": sorted({c["document_name"] for c in context}),
        "sources": context,
    }