"""Policy Q&A and conversation history API endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_cached_policy, get_current_user
from backend.api.schemas import (
    AskQuestionRequest,
    AskQuestionResponse,
    CitationItem,
    ConversationHistoryResponse,
    MessageItem,
)
from backend.database.client import get_database
from backend.database.repositories import ConversationRepository
from backend.services.auth_service import AuthUser
from backend.services.policy_service import PolicyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qa", tags=["Q&A"])
policy_service = PolicyService()


@router.post("/ask", response_model=AskQuestionResponse)
def ask_question(
    req: AskQuestionRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> AskQuestionResponse:
    """Submit a coverage question, retrieve evidence, and verify citations in Python."""
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question text cannot be empty.",
        )

    policy = get_cached_policy(req.policy_id, current_user.user_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested policy is not currently active in memory. Please upload or select it.",
        )

    try:
        result = policy_service.ask_question(policy, req.question.strip())
    except Exception as exc:
        logger.error("Error executing QA pipeline: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The coverage question could not be evaluated. Please try again.",
        ) from exc

    citations = [
        CitationItem(
            chunk_id=c.chunk_id,
            page_number=c.page_number,
            quote=c.quote,
        )
        for c in result.citations
    ]

    conv_id: str | None = None
    policy = get_cached_policy(req.policy_id, current_user.user_id)
    canonical_id = getattr(policy, "fingerprint", req.policy_id) if policy else req.policy_id

    db = get_database()
    if db is not None:
        try:
            repo = ConversationRepository(db)
            conv_id = repo.get_or_create_conversation(
                user_id=current_user.user_id,
                policy_id=canonical_id,
                title=req.question[:60],
            )
            # Record user question
            repo.append_message(
                user_id=current_user.user_id,
                conversation_id=conv_id,
                policy_id=canonical_id,
                role="user",
                content=req.question.strip(),
            )
            # Record assistant verdict & answer with verified citations
            repo.append_message(
                user_id=current_user.user_id,
                conversation_id=conv_id,
                policy_id=canonical_id,
                role="assistant",
                content=result.answer,
                evidence_metadata={
                    "verdict": result.verdict,
                    "confidence": result.confidence,
                    "citations": [c.model_dump() if hasattr(c, "model_dump") else c.__dict__ for c in citations],
                    "citations_valid": result.citations_valid,
                    "manual_review_required": result.manual_review_required,
                    "warnings": list(result.warnings or []),
                    "unverified_answer": result.unverified_answer,
                    "caveats": list(result.caveats or []),
                },
            )
        except Exception as exc:
            logger.warning("Could not persist conversation history: %s", exc)

    return AskQuestionResponse(
        verdict=result.verdict,
        answer=result.answer,
        citations=citations,
        confidence=result.confidence,
        caveats=result.caveats or [],
        conversation_id=conv_id,
        citations_valid=result.citations_valid,
        manual_review_required=result.manual_review_required,
        warnings=list(result.warnings or []),
        unverified_answer=result.unverified_answer,
    )


@router.get("/history/{policy_id}", response_model=ConversationHistoryResponse)
def get_conversation_history(
    policy_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> ConversationHistoryResponse:
    """Retrieve chronological Q&A messages for this policy from MongoDB Atlas."""
    db = get_database()
    messages: list[MessageItem] = []
    conv_id = ""

    policy = get_cached_policy(policy_id, current_user.user_id)
    canonical_id = getattr(policy, "fingerprint", policy_id) if policy else policy_id

    if db is not None:
        try:
            repo = ConversationRepository(db)
            convs = repo.list_user_conversations(current_user.user_id, policy_id)
            if not convs and canonical_id != policy_id:
                convs = repo.list_user_conversations(current_user.user_id, canonical_id)
            if convs:
                conv_id = convs[0].get("id", "")
                raw_msgs = repo.list_messages(current_user.user_id, conv_id)
                for m in raw_msgs:
                    messages.append(
                        MessageItem(
                            id=m.get("id", ""),
                            role=m.get("role", "assistant"),
                            content=m.get("content", ""),
                            created_at=str(m.get("created_at", "")),
                            evidence_metadata=m.get("evidence_metadata", {}),
                        )
                    )
        except Exception as exc:
            logger.warning("Error fetching conversation history: %s", exc)

    return ConversationHistoryResponse(
        conversation_id=conv_id,
        policy_id=policy_id,
        messages=messages,
    )
