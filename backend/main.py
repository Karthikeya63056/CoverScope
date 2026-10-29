"""FastAPI application entry point for CoverScope.

Exposes REST API endpoints for authentication, policy document ingestion,
lexical retrieval, Groq AI question answering, policy comparisons,
and scenario analyses backed by MongoDB Atlas.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import sys
from typing import Any

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import api_router
from backend.api.deps import cache_processed_policy
from backend.config import settings
from backend.database.client import get_database, redact_mongo_uri
from backend.database.healthcheck import check_mongodb_health
from backend.database.schema import init_db_indexes
from backend.qa.workflow import prepare_policy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coverscope.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database indexes and seed bundled policies into memory."""
    logger.info("Initializing CoverScope backend engine...")
    db = get_database()
    if db is not None:
        try:
            init_db_indexes(db)
            health = check_mongodb_health()
            logger.info("MongoDB Atlas connected: %s (latency: %.1f ms)", health.redacted_uri, health.latency_ms)
        except Exception as exc:
            logger.warning("MongoDB Atlas initialization warning: %s", exc)
    else:
        logger.info("Running in offline in-memory session mode (MONGODB_URI not set).")

    # Pre-cache single baseline demonstration policy from pdfs/ directory
    pdf_dir = ROOT / "pdfs"
    baseline_filename = "Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf"
    baseline_path = pdf_dir / baseline_filename
    if baseline_path.exists():
        try:
            data = baseline_path.read_bytes()
            policy = prepare_policy(
                data,
                baseline_filename,
                max_upload_bytes=settings.max_upload_bytes,
                max_extracted_chars=settings.max_extracted_chars,
                min_page_chars=settings.min_page_chars,
                chunk_chars=settings.chunk_chars,
            )
            cache_processed_policy(policy)
            logger.info("Loaded baseline policy: '%s' (%d pages, hash: %s)", policy.filename, policy.page_count, policy.fingerprint[:12])
        except Exception as exc:
            logger.warning("Could not pre-cache '%s': %s", baseline_filename, exc)

    # Reconcile existing MongoDB policy IDs with in-memory bundled policies
    if db is not None:
        try:
            from backend.api.deps import _POLICY_ALIASES, _POLICY_MEMORY_CACHE
            reconciled = 0
            for pdoc in db["policies"].find({}, {"_id": 1, "document_hash": 1}):
                pid = str(pdoc["_id"])
                phash = pdoc.get("document_hash")
                if phash and phash in _POLICY_MEMORY_CACHE:
                    _POLICY_ALIASES[pid] = phash
                    reconciled += 1
            if reconciled:
                logger.info("Reconciled %d MongoDB policy record(s) with pre-cached policy documents.", reconciled)
        except Exception as exc:
            logger.debug("MongoDB policy alias reconciliation error: %s", exc)

    yield

    logger.info("Shutting down CoverScope backend engine.")


app = FastAPI(
    title="CoverScope REST API",
    description="Evidence-grounded health insurance policy intelligence and scenario analysis API.",
    version="3.2.0",
    lifespan=lifespan,
)

# Configure CORS for local development and explicit production frontends
DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def get_allowed_origins() -> list[str]:
    """Load allowed CORS origins from environment and defaults.

    Allows specific production frontend domains without granting wildcard
    access to arbitrary hosted subdomains.
    """
    origins = list(DEFAULT_DEV_ORIGINS)
    env_origins = os.getenv("COVERSCOPE_ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS", "")
    if env_origins:
        for origin in env_origins.split(","):
            clean_org = origin.strip().rstrip("/")
            if clean_org and clean_org not in origins:
                origins.append(clean_org)
    return origins


ALLOWED_ORIGINS = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

app.include_router(api_router)


@app.get("/", tags=["Health"])
def root_status(request: Request) -> Any:
    """Service status or React SPA entry point depending on client."""
    accept = request.headers.get("accept", "")
    dist_index = ROOT / "frontend" / "dist" / "index.html"
    if "text/html" in accept and dist_index.is_file():
        from starlette.responses import FileResponse
        return FileResponse(dist_index)
    return {
        "service": "CoverScope Intelligence API",
        "version": "3.2.0",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/api/v1/health", tags=["Health"])
def api_health() -> dict[str, Any]:
    """Detailed health check reporting provider model, retrieval window, and database status."""
    db_report = check_mongodb_health()
    return {
        "status": "healthy",
        "groq_model": settings.groq_model,
        "retrieval_top_k": settings.retrieval_top_k,
        "database": {
            "status": db_report.status.value,
            "target_database": db_report.database_name,
            "latency_ms": db_report.latency_ms,
            "cluster": db_report.redacted_uri,
        },
    }


# Mount built React assets if dist/ directory exists
_dist_dir = ROOT / "frontend" / "dist"
if _dist_dir.exists():
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    _assets_dir = _dist_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="spa_assets")

    @app.get("/{full_path:path}")
    async def serve_react_spa(full_path: str):
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Endpoint not found")
        file_path = _dist_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_dist_dir / "index.html")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Centralized exception handler to prevent leaking internal stack traces."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.error("Unhandled API exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again."},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
