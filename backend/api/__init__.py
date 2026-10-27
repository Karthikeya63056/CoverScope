"""CoverScope REST API router definitions."""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.auth import router as auth_router
from backend.api.claim_rehearsal import router as claim_rehearsal_router
from backend.api.comparison import router as comparison_router
from backend.api.dashboard import router as dashboard_router
from backend.api.policies import router as policies_router
from backend.api.qa import router as qa_router
from backend.api.scenarios import router as scenarios_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(policies_router)
api_router.include_router(qa_router)
api_router.include_router(scenarios_router)
api_router.include_router(comparison_router)
api_router.include_router(claim_rehearsal_router)

__all__ = ["api_router"]
