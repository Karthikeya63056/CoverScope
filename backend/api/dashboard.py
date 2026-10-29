"""Dashboard summary API endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_all_cached_policies, get_current_user
from backend.api.schemas import DashboardSummaryResponse, PolicySummary
from backend.database.client import get_database
from backend.database.healthcheck import check_mongodb_health
from backend.database.repositories import (
    AnalysisRepository,
    ConversationRepository,
    PolicyRepository,
)
from backend.services.auth_service import AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(current_user: AuthUser = Depends(get_current_user)) -> DashboardSummaryResponse:
    """Return consolidated dashboard statistics and recent activity for the user."""
    db = get_database()
    total_policies = 0
    total_convs = 0
    total_analyses = 0
    recent_policies: list[PolicySummary] = []
    recent_messages: list[dict[str, Any]] = []

    health = check_mongodb_health()
    db_status = health.status.value

    if db is not None and health.is_connected:
        try:
            p_repo = PolicyRepository(db)
            c_repo = ConversationRepository(db)
            a_repo = AnalysisRepository(db)

            policies = p_repo.list_user_policies(current_user.user_id, limit=5)
            total_policies = p_repo.count_user_policies(current_user.user_id)
            for p in policies:
                raw_created = p.get("created_at")
                created_at_str = (
                    raw_created.isoformat()
                    if hasattr(raw_created, "isoformat")
                    else (str(raw_created) if raw_created is not None else None)
                )
                recent_policies.append(
                    PolicySummary(
                        id=p.get("id", ""),
                        document_name=p.get("document_name", "Untitled Policy"),
                        document_hash=p.get("document_hash", ""),
                        page_count=p.get("page_count", 1),
                        processing_status=p.get("processing_status", "processed"),
                        created_at=created_at_str,
                        metadata=p.get("metadata", {}),
                    )
                )

            total_convs = c_repo.count_user_conversations(current_user.user_id)
            convs = c_repo.list_user_conversations(current_user.user_id, limit=1)
            if convs and convs[0].get("id"):
                msgs = c_repo.list_messages(current_user.user_id, convs[0]["id"])
                recent_messages = msgs[-5:]

            total_analyses = a_repo.count_user_analyses(current_user.user_id)
        except Exception as exc:
            logger.warning("Error loading dashboard summary from DB: %s", exc)

    # Augment with active in-memory cached / bundled policies if not already present
    seen_hashes: set[str] = {p.document_hash for p in recent_policies if p.document_hash}
    for cp in get_all_cached_policies(current_user.user_id):
        if cp.fingerprint not in seen_hashes:
            seen_hashes.add(cp.fingerprint)
            recent_policies.append(
                PolicySummary(
                    id=cp.fingerprint,
                    policy_id=cp.fingerprint,
                    document_name=cp.filename,
                    filename=cp.filename,
                    document_hash=cp.fingerprint,
                    page_count=cp.page_count,
                    total_characters=cp.extracted_characters,
                    total_chunks=len(cp.chunks),
                    processing_status="processed",
                    status="bundled",
                    metadata={
                        "char_count": cp.extracted_characters,
                        "chunk_count": len(cp.chunks),
                    },
                )
            )
    total_policies = max(total_policies, len(recent_policies))

    return DashboardSummaryResponse(
        total_policies=total_policies,
        total_conversations=total_convs,
        total_analyses=total_analyses,
        database_status=db_status,
        recent_policies=recent_policies,
        recent_messages=recent_messages,
    )
