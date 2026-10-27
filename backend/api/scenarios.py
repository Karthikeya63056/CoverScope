"""Scenario evaluation API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_cached_policy, get_current_user
from backend.api.schemas import ScenarioRequest, ScenarioResponse
from backend.database.client import get_database
from backend.database.repositories import AnalysisRepository
from backend.domain import ScenarioEvaluator, ScenarioInput
from backend.domain.enums import ScenarioType
from backend.services.auth_service import AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenarios", tags=["Scenarios"])
scenario_evaluator = ScenarioEvaluator()


@router.post("/evaluate", response_model=ScenarioResponse)
def evaluate_scenario(
    req: ScenarioRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ScenarioResponse:
    """Run deterministic rule-based evaluation of waiting periods, copays, and exclusions."""
    policy = get_cached_policy(req.policy_id, current_user.user_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested policy is not currently active in memory. Please select or upload it.",
        )

    raw_scenario_type = (req.scenario_type or "pre_existing_condition").strip().lower()
    try:
        scenario_type = ScenarioType(raw_scenario_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported scenario_type. Supported values: "
                + ", ".join(item.value for item in ScenarioType)
                + "."
            ),
        ) from exc

    if scenario_type == ScenarioType.UNSUPPORTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The 'unsupported' scenario type cannot be requested directly.",
        )

    scenario_input = ScenarioInput(
        scenario_type=scenario_type,
        condition_name=req.ailment.strip(),
        elapsed_months=req.elapsed_months,
        elapsed_days=req.elapsed_days,
        member_age_at_entry=req.member_age,
        is_pre_existing=scenario_type == ScenarioType.PRE_EXISTING_CONDITION,
    )

    try:
        result = scenario_evaluator.evaluate(policy, scenario_input)
    except Exception as exc:
        logger.error("Error evaluating scenario: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The scenario could not be evaluated. Please try again.",
        ) from exc

    raw_refs = getattr(result, "source_references", ()) or ()
    clauses = [
        {
            "chunk_id": (
                ref.get("chunk_id") or ref.get("fact_id", "")
                if isinstance(ref, dict)
                else getattr(ref, "chunk_id", "") or getattr(ref, "fact_id", "")
            ),
            "page_number": ref.get("page_number", 1) if isinstance(ref, dict) else getattr(ref, "page_number", 1),
            "text": ref.get("quote", ref.get("text", "")) if isinstance(ref, dict) else getattr(ref, "quote", getattr(ref, "text", "")),
        }
        for ref in raw_refs
    ]
    caveats = list(getattr(result, "limitations", ()) or ()) + list(getattr(result, "unresolved_conditions", ()) or ())

    # Persist audit record in MongoDB Atlas
    db = get_database()
    if db is not None:
        try:
            repo = AnalysisRepository(db)
            repo.save_analysis(
                user_id=current_user.user_id,
                policy_id=req.policy_id,
                analysis_type="scenario_evaluation",
                input_summary=req.model_dump(),
                result_summary={
                    "verdict": result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict),
                    "headline": result.headline,
                    "explanation": result.explanation,
                },
                source_references=clauses,
            )
        except Exception as exc:
            logger.warning("Could not persist scenario audit record: %s", exc)

    return ScenarioResponse(
        verdict=result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict),
        headline=result.headline,
        explanation=result.explanation,
        applicable_clauses=clauses,
        caveats=caveats,
        missing_inputs=list(getattr(result, "missing_inputs", ()) or ()),
        user_assumptions=list(getattr(result, "user_assumptions", ()) or ()),
        calculation_formula=getattr(result, "calculation_formula", None),
        decision_state=(
            result.decision_state.value
            if hasattr(result.decision_state, "value")
            else str(result.decision_state)
            if result.decision_state
            else None
        ),
        evidentiary_support=getattr(result, "evidentiary_support", ""),
    )
