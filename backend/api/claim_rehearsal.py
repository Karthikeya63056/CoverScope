"""Claim Rehearsal API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_cached_policy, get_current_user
from backend.api.schemas import (
    ClaimRehearsalRequest,
    ClaimRehearsalResponse,
)
from backend.database.client import get_database
from backend.database.repositories import AnalysisRepository
from backend.services.auth_service import AuthUser
from backend.services.claim_rehearsal_service import evaluate_claim_rehearsal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claim-rehearsal", tags=["Claim Rehearsal"])


@router.post("/rehearse", response_model=ClaimRehearsalResponse)
def rehearse_claim(
    req: ClaimRehearsalRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ClaimRehearsalResponse:
    """Evaluate a planned medical procedure or claim against policy facts, room-rent, and waiting periods."""
    policy = get_cached_policy(req.policy_id, current_user.user_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested policy is not currently active in memory. Please select or upload it.",
        )

    try:
        report = evaluate_claim_rehearsal(policy, req)
    except Exception as exc:
        logger.error("Error evaluating claim rehearsal: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate claim rehearsal. Please check inputs and try again.",
        ) from exc

    # Persist rehearsal report to MongoDB Atlas under authenticated user
    db = get_database()
    if db is not None:
        try:
            repo = AnalysisRepository(db)
            repo.save_analysis(
                user_id=current_user.user_id,
                policy_id=req.policy_id,
                analysis_type="claim_rehearsal",
                input_summary=req.model_dump(),
                result_summary={
                    "rehearsal_id": report.rehearsal_id,
                    "policy_name": report.policy_name,
                    "readiness_status": report.readiness_status,
                    "headline": report.headline,
                    "executive_summary": report.executive_summary,
                    "financial_breakdown": report.financial_breakdown.model_dump() if report.financial_breakdown else None,
                },
                source_references=report.supporting_clauses,
            )
        except Exception as exc:
            logger.warning("Could not persist claim rehearsal audit to MongoDB: %s", exc)

    return report


@router.get("/history")
def get_rehearsal_history(
    policy_id: str | None = None,
    current_user: AuthUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return past claim rehearsals performed by the authenticated user."""
    db = get_database()
    if policy_id and policy_id.strip():
        clean_pid = policy_id.strip()
        policy = get_cached_policy(clean_pid, current_user.user_id)
        if not policy:
            if db is not None:
                from backend.database.repositories import PolicyRepository
                p_repo = PolicyRepository(db)
                if not p_repo.get_policy(current_user.user_id, clean_pid) and not p_repo.get_policy_by_hash(current_user.user_id, clean_pid):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Policy not found or access denied.",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Policy not found or access denied.",
                )

    if db is None:
        return []

    try:
        repo = AnalysisRepository(db)
        records = repo.list_analyses(
            user_id=current_user.user_id,
            policy_id=policy_id.strip() if policy_id else None,
            analysis_type="claim_rehearsal",
            limit=20,
        )
        return records
    except Exception as exc:
        logger.warning("Error fetching claim rehearsal history: %s", exc)
        return []
