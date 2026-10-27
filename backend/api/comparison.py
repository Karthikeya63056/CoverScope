"""Policy comparison and protection gap analysis API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_cached_policy, get_current_user
from backend.api.schemas import (
    ComparisonDimension,
    ComparisonProtectionGap,
    ComparisonRequest,
    ComparisonResponse,
)
from backend.database.client import get_database
from backend.database.repositories import AnalysisRepository
from backend.domain import ComparisonAssumptions, PolicyComparisonEngine
from backend.services.auth_service import AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comparison", tags=["Comparison"])
comparison_engine = PolicyComparisonEngine()


@router.post("/compare", response_model=ComparisonResponse)
def compare_policies(
    req: ComparisonRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ComparisonResponse:
    """Compare two policy documents across benefits, waiting periods, copays, and protection gaps."""
    policy_a = get_cached_policy(req.policy_id_a, current_user.user_id)
    policy_b = get_cached_policy(req.policy_id_b, current_user.user_id)

    if not policy_a or not policy_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Both policies must be active in memory for comparison. Please upload or load both documents.",
        )

    assumptions = ComparisonAssumptions(
        elapsed_months=req.continuous_months,
        member_entry_age=req.member_age,
    )

    try:
        result = comparison_engine.compare(policy_a, policy_b, assumptions=assumptions)
    except Exception as exc:
        logger.error("Error executing policy comparison: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The policy comparison could not be completed. Please try again.",
        ) from exc

    dimensions = [
        ComparisonDimension(
            name=getattr(d, "dimension_label", str(getattr(d, "dimension_key", "Dimension"))),
            policy_a_value=getattr(d.policy_a_value, "display_value", str(d.policy_a_value)) if d.policy_a_value else "Not stated",
            policy_b_value=getattr(d.policy_b_value, "display_value", str(d.policy_b_value)) if d.policy_b_value else "Not stated",
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            assessment=getattr(d, "summary_difference", ""),
            conditions_a=list(getattr(d.policy_a_value, "conditions", ()) or ()) if d.policy_a_value else [],
            conditions_b=list(getattr(d.policy_b_value, "conditions", ()) or ()) if d.policy_b_value else [],
            limitations=list(getattr(d, "limitations", ()) or ()),
        )
        for d in result.dimensions
    ]

    gaps = [
        ComparisonProtectionGap(
            severity=g.severity.value if hasattr(g.severity, "value") else str(g.severity),
            dimension=(
                g.dimension_key.value
                if hasattr(g.dimension_key, "value")
                else str(g.dimension_key)
            ),
            title=g.title,
            description=g.description,
        )
        for g in result.protection_gaps
    ]

    # Persist audit record in MongoDB Atlas
    db = get_database()
    if db is not None:
        try:
            repo = AnalysisRepository(db)
            repo.save_analysis(
                user_id=current_user.user_id,
                policy_id=f"{req.policy_id_a}_vs_{req.policy_id_b}",
                analysis_type="policy_comparison",
                input_summary=req.model_dump(),
                result_summary={
                    "total_dimensions": len(dimensions),
                    "total_gaps": len(gaps),
                    "policy_a": policy_a.filename,
                    "policy_b": policy_b.filename,
                },
            )
        except Exception as exc:
            logger.warning("Could not persist comparison record: %s", exc)

    return ComparisonResponse(
        policy_a_name=policy_a.filename,
        policy_b_name=policy_b.filename,
        dimensions=dimensions,
        gaps=gaps,
        assumptions_used=req.model_dump(),
        general_limitations=list(getattr(result, "general_limitations", ()) or ()),
        caveats=list(getattr(result, "caveats", ()) or ()),
    )
