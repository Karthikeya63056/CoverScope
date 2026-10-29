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
    ConversationSummaryItem,
    MessageItem,
)
from backend.database.client import get_database
from backend.database.repositories import COLL_MESSAGES, ConversationRepository
from backend.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
    LLMTimeoutError,
)
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
    except (LLMAuthError, LLMConfigError) as exc:
        logger.warning("LLM service unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {exc}",
        ) from exc
    except LLMRateLimitError as exc:
        logger.warning("LLM rate limit reached: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI service rate limit exceeded. Please wait a moment before trying again.",
        ) from exc
    except LLMTimeoutError as exc:
        logger.warning("LLM timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI analysis timed out. Please try again with a shorter question.",
        ) from exc
    except (LLMConnectionError, LLMServiceError, LLMResponseError) as exc:
        logger.warning("LLM provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider communication error: {exc}",
        ) from exc
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
            is_new = not req.conversation_id
            conv_id = repo.get_or_create_conversation(
                user_id=current_user.user_id,
                policy_id=canonical_id,
                title=req.question[:60],
                conversation_id=req.conversation_id,
                create_new=is_new,
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
    if not policy:
        doc = None
        if db is not None:
            try:
                from backend.database.repositories import PolicyRepository
                p_repo = PolicyRepository(db)
                doc = p_repo.get_policy(current_user.user_id, policy_id) or p_repo.get_policy_by_hash(current_user.user_id, policy_id)
            except Exception as exc:
                logger.warning("Could not verify policy ownership in DB for history: %s", exc)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found or access denied.",
            )

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


@router.delete("/history/{policy_id}")
def clear_conversation_history(
    policy_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete all conversation messages for a policy owned by current_user."""
    db = get_database()
    policy = get_cached_policy(policy_id, current_user.user_id)
    if not policy:
        doc = None
        if db is not None:
            try:
                from backend.database.repositories import PolicyRepository
                p_repo = PolicyRepository(db)
                doc = p_repo.get_policy(current_user.user_id, policy_id) or p_repo.get_policy_by_hash(current_user.user_id, policy_id)
            except Exception as exc:
                logger.warning("Could not verify policy ownership in DB for history: %s", exc)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found or access denied.",
            )

    canonical_id = getattr(policy, "fingerprint", policy_id) if policy else policy_id
    deleted_count = 0
    if db is not None:
        try:
            repo = ConversationRepository(db)
            deleted_count = repo.delete_conversations_for_policy(current_user.user_id, policy_id)
            if deleted_count == 0 and canonical_id != policy_id:
                deleted_count = repo.delete_conversations_for_policy(current_user.user_id, canonical_id)
        except Exception as exc:
            logger.warning("Error deleting conversation history from MongoDB: %s", exc)

    return {"success": True, "deleted_conversations": deleted_count}


@router.get("/conversations", response_model=list[ConversationSummaryItem])
def list_conversations(
    policy_id: str | None = None,
    current_user: AuthUser = Depends(get_current_user),
) -> list[ConversationSummaryItem]:
    """List conversation threads owned by the current user."""
    db = get_database()
    items: list[ConversationSummaryItem] = []
    if db is not None:
        try:
            repo = ConversationRepository(db)
            candidate_pids: list[str] | None = None
            if policy_id and policy_id.strip():
                candidate_pids = [policy_id.strip()]
                cached = get_cached_policy(policy_id.strip(), current_user.user_id)
                if cached and getattr(cached, "fingerprint", None):
                    if cached.fingerprint not in candidate_pids:
                        candidate_pids.append(cached.fingerprint)
                try:
                    from backend.database.repositories import PolicyRepository
                    p_repo = PolicyRepository(db)
                    doc = p_repo.get_policy(current_user.user_id, policy_id.strip()) or p_repo.get_policy_by_hash(current_user.user_id, policy_id.strip())
                    if doc:
                        if doc.get("document_hash") and doc["document_hash"] not in candidate_pids:
                            candidate_pids.append(doc["document_hash"])
                        if doc.get("id") and doc["id"] not in candidate_pids:
                            candidate_pids.append(doc["id"])
                except Exception:
                    pass

            raw_convs: list[dict[str, Any]] = []
            if candidate_pids and len(candidate_pids) > 1:
                seen_cids = set()
                for pid in candidate_pids:
                    for c in repo.list_user_conversations(current_user.user_id, policy_id=pid, limit=50):
                        cid = c.get("id") or str(c.get("_id", ""))
                        if cid and cid not in seen_cids:
                            seen_cids.add(cid)
                            raw_convs.append(c)
            else:
                raw_convs = repo.list_user_conversations(
                    current_user.user_id,
                    policy_id=candidate_pids[0] if candidate_pids else None,
                    limit=50,
                )

            for c in raw_convs:
                conv_id = c.get("id") or str(c.get("_id", ""))
                msg_count = db[COLL_MESSAGES].count_documents({
                    "conversation_id": conv_id,
                    "user_id": current_user.user_id,
                })
                items.append(
                    ConversationSummaryItem(
                        id=conv_id,
                        policy_id=c.get("policy_id", ""),
                        title=c.get("title", "Policy Q&A Consultation"),
                        created_at=str(c.get("created_at", "")),
                        updated_at=str(c.get("updated_at", "")),
                        message_count=msg_count,
                    )
                )
        except Exception as exc:
            logger.warning("Error listing conversations: %s", exc)
    return items


@router.get("/conversations/{conversation_id}/messages", response_model=ConversationHistoryResponse)
def get_conversation_messages_by_id(
    conversation_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> ConversationHistoryResponse:
    """Retrieve chronological messages for a specific conversation ID."""
    db = get_database()
    messages: list[MessageItem] = []
    policy_id = ""

    if db is not None:
        try:
            repo = ConversationRepository(db)
            raw_msgs = repo.list_messages(current_user.user_id, conversation_id)
            if raw_msgs:
                policy_id = raw_msgs[0].get("policy_id", "")
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
            logger.warning("Error fetching messages for conversation %s: %s", conversation_id, exc)

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        policy_id=policy_id,
        messages=messages,
    )


@router.delete("/conversations/{conversation_id}")
def delete_single_conversation(
    conversation_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a specific conversation thread and its messages."""
    db = get_database()
    success = False
    if db is not None:
        try:
            repo = ConversationRepository(db)
            success = repo.delete_conversation(current_user.user_id, conversation_id)
        except Exception as exc:
            logger.warning("Error deleting conversation %s: %s", conversation_id, exc)

    return {"success": success, "conversation_id": conversation_id}
