"""Policy and document management API endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.deps import (
    cache_processed_policy,
    get_all_cached_policies,
    get_cached_policy,
    get_current_user,
    remove_cached_policy,
    store_offline_raw_policy,
)
from backend.api.schemas import (
    FactItem,
    PageTextResponse,
    PolicyDetailResponse,
    PolicyFactsResponse,
    PolicyListResponse,
    PolicySummary,
)
from backend.config import settings
from backend.database.client import get_database
from backend.database.repositories import (
    AnalysisRepository,
    ConversationRepository,
    PolicyRepository,
)
from backend.domain import extract_candidate_facts
from backend.qa.workflow import PolicyProcessingError, prepare_policy
from backend.services.auth_service import AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policies", tags=["Policies"])


@router.post("/upload", response_model=PolicySummary)
async def upload_policy(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
) -> PolicySummary:
    """Upload and process a health insurance policy PDF document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported (.pdf).",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {settings.max_upload_bytes // (1024 * 1024)} MB.",
        )

    try:
        policy = prepare_policy(
            content,
            file.filename,
            max_upload_bytes=settings.max_upload_bytes,
            max_extracted_chars=settings.max_extracted_chars,
            min_page_chars=settings.min_page_chars,
            chunk_chars=settings.chunk_chars,
        )
    except PolicyProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error processing PDF: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The PDF could not be processed. It may be corrupted, image-only, or encrypted.",
        )

    # Persist raw PDF directly to MongoDB Atlas GridFS (zero plaintext exposure on local disk)
    policy_id = policy.fingerprint
    db = get_database()
    gridfs_id: str | None = None

    if db is not None:
        repo = PolicyRepository(db)
        try:
            if hasattr(repo, "save_policy_file"):
                gridfs_id = repo.save_policy_file(
                    user_id=current_user.user_id,
                    document_hash=policy.fingerprint,
                    filename=policy.filename,
                    file_bytes=content,
                )
        except Exception as exc:
            logger.warning("Could not persist policy file to MongoDB GridFS: %s", exc)

        try:
            db_id = repo.save_policy_metadata(
                user_id=current_user.user_id,
                document_name=policy.filename,
                document_hash=policy.fingerprint,
                page_count=policy.page_count,
                storage_reference={
                    "type": "gridfs",
                    "file_id": gridfs_id,
                } if gridfs_id else {},
                metadata={
                    "char_count": policy.extracted_characters,
                    "chunk_count": len(policy.chunks),
                    "file_size": len(content),
                    "gridfs_file_id": gridfs_id,
                },
            )
            if db_id:
                policy_id = db_id
        except Exception as exc:
            logger.warning("Could not persist policy metadata to MongoDB: %s", exc)
    else:
        # Offline / test fallback in process memory (never written to local disk)
        store_offline_raw_policy(current_user.user_id, policy.fingerprint, policy.filename, content)

    # Cache the prepared policy for rapid Q&A and analysis access. The Mongo
    # id is registered as an alias so every endpoint can resolve either id.
    cache_processed_policy(policy, user_id=current_user.user_id, alias=policy_id)

    return PolicySummary(
        id=policy_id,
        document_name=policy.filename,
        document_hash=policy.fingerprint,
        page_count=policy.page_count,
        processing_status="processed",
        metadata={
            "char_count": policy.extracted_characters,
            "chunk_count": len(policy.chunks),
        },
    )


@router.get("", response_model=PolicyListResponse)
def list_policies(current_user: AuthUser = Depends(get_current_user)) -> PolicyListResponse:
    """List all policies accessible by the user, combining user uploads and preloaded policies."""
    db = get_database()
    items: list[PolicySummary] = []
    seen_hashes: set[str] = set()

    # 1. Query MongoDB for policies owned by the current user
    if db is not None:
        try:
            repo = PolicyRepository(db)
            docs = repo.list_user_policies(current_user.user_id)
            for d in docs:
                p_id = d.get("id", "")
                p_hash = d.get("document_hash", "")
                if p_hash:
                    seen_hashes.add(p_hash)
                    if p_id:
                        from backend.api.deps import _POLICY_ALIASES, _POLICY_MEMORY_CACHE, _cache_key
                        owner_k = _cache_key(p_hash, current_user.user_id)
                        _POLICY_ALIASES[p_id] = owner_k if owner_k in _POLICY_MEMORY_CACHE else p_hash

                items.append(
                    PolicySummary(
                        id=p_id,
                        document_name=d.get("document_name", "Untitled Policy"),
                        document_hash=p_hash,
                        page_count=d.get("page_count", 1),
                        processing_status=d.get("processing_status", "processed"),
                        created_at=d.get("created_at", "").isoformat() if hasattr(d.get("created_at"), "isoformat") else str(d.get("created_at", "")),
                        updated_at=d.get("updated_at", "").isoformat() if hasattr(d.get("updated_at"), "isoformat") else str(d.get("updated_at", "")),
                        metadata=d.get("metadata", {}),
                    )
                )
        except Exception as exc:
            logger.warning("Error querying policies from MongoDB: %s", exc)

    # 2. Include preloaded bundled demonstration policies and cached user policies if not already present
    for cached in get_all_cached_policies(current_user.user_id):
        if cached.fingerprint not in seen_hashes:
            seen_hashes.add(cached.fingerprint)
            items.append(
                PolicySummary(
                    id=cached.fingerprint,
                    policy_id=cached.fingerprint,
                    document_name=cached.filename,
                    filename=cached.filename,
                    document_hash=cached.fingerprint,
                    page_count=cached.page_count,
                    total_characters=cached.extracted_characters,
                    total_chunks=len(cached.chunks),
                    processing_status="processed",
                    status="bundled",
                    metadata={
                        "char_count": cached.extracted_characters,
                        "chunk_count": len(cached.chunks),
                    },
                )
            )

    return PolicyListResponse(policies=items, total=len(items))


@router.get("/{policy_id}", response_model=PolicyDetailResponse)
def get_policy_detail(
    policy_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> PolicyDetailResponse:
    """Retrieve detailed policy information strictly scoped to owner."""
    db = get_database()
    doc_hash = policy_id
    doc_name = "Policy Document"
    page_count = 1
    char_count = 0
    chunk_count = 0
    created_at: str | None = None
    resolved_id = policy_id
    found = False

    if db is not None:
        try:
            repo = PolicyRepository(db)
            doc = repo.get_policy(current_user.user_id, policy_id)
            if not doc:
                doc = repo.get_policy_by_hash(current_user.user_id, policy_id)
            if doc:
                found = True
                resolved_id = doc.get("id", policy_id)
                doc_name = doc.get("document_name", doc_name)
                doc_hash = doc.get("document_hash", doc_hash)
                page_count = doc.get("page_count", 1)
                created = doc.get("created_at")
                if hasattr(created, "isoformat"):
                    created_at = created.isoformat()
                elif created:
                    created_at = str(created)
                meta = doc.get("metadata") or {}
                char_count = meta.get("char_count", 0)
                chunk_count = meta.get("chunk_count", 0)
        except Exception as exc:
            logger.warning("Error fetching policy from DB: %s", exc)

    # Check cached policy object (aliases resolve Mongo ids back to fingerprints)
    cached = get_cached_policy(policy_id, current_user.user_id)
    if cached is None and doc_hash != policy_id:
        cached = get_cached_policy(doc_hash, current_user.user_id)
    if cached:
        found = True
        doc_name = cached.filename
        page_count = cached.page_count
        char_count = cached.extracted_characters
        chunk_count = len(cached.chunks)

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found or access denied.",
        )

    return PolicyDetailResponse(
        id=resolved_id,
        document_name=doc_name,
        document_hash=doc_hash,
        page_count=page_count,
        char_count=char_count,
        chunk_count=chunk_count,
        created_at=created_at,
    )


@router.get("/{policy_id}/pages/{page_number}", response_model=PageTextResponse)
def get_page_text(
    policy_id: str,
    page_number: int,
    current_user: AuthUser = Depends(get_current_user),
) -> PageTextResponse:
    """Fetch verbatim extracted text for a specific page."""
    policy = get_cached_policy(policy_id, current_user.user_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy document text is not currently loaded in memory. Please re-upload.",
        )

    for p in policy.pages:
        if p.page_number == page_number:
            return PageTextResponse(
                policy_id=policy_id,
                page_number=page_number,
                text=p.text,
                char_count=len(p.text),
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Page {page_number} not found (document has {policy.page_count} pages).",
    )


@router.get("/{policy_id}/facts", response_model=PolicyFactsResponse)
def get_policy_facts(
    policy_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> PolicyFactsResponse:
    """Extract candidate policy facts (waiting periods, exclusions, limits, co-payments)."""
    policy = get_cached_policy(policy_id, current_user.user_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy document is not loaded in memory. Please select or upload a policy.",
        )

    raw_facts = extract_candidate_facts(policy)
    facts = []
    for f in raw_facts:
        page_num = f.evidence_references[0].page_number if f.evidence_references else 1
        conf = 1.0 if f.is_evidence_grounded else 0.8
        facts.append(
            FactItem(
                category=f.category.value if hasattr(f.category, "value") else str(f.category),
                text=f.proposition,
                page_number=page_num,
                confidence=conf,
            )
        )
    return PolicyFactsResponse(
        policy_id=policy_id,
        document_name=policy.filename,
        facts=facts,
        total_facts=len(facts),
    )


@router.delete("/{policy_id}")
def delete_policy(
    policy_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete policy metadata, GridFS stored file, and any owner-scoped in-memory copy."""
    db = get_database()
    deleted = False
    candidate_ids = {policy_id}

    if db is not None:
        repo = PolicyRepository(db)
        # 1. Resolve all linked identifiers (MongoDB _id and SHA256 document_hash) BEFORE deleting the policy record
        doc = repo.get_policy(current_user.user_id, policy_id)
        if not doc:
            doc = repo.get_policy_by_hash(current_user.user_id, policy_id)
        if doc:
            if doc.get("id"):
                candidate_ids.add(str(doc["id"]))
            if doc.get("document_hash"):
                candidate_ids.add(str(doc["document_hash"]))

        cached = get_cached_policy(policy_id, current_user.user_id)
        if cached:
            candidate_ids.add(cached.fingerprint)

        # 2. Cascading deletion of user's conversations and analysis audit records for this policy
        try:
            conv_repo = ConversationRepository(db)
            analysis_repo = AnalysisRepository(db)
            for cid in candidate_ids:
                conv_repo.delete_conversations_for_policy(current_user.user_id, cid)
                analysis_repo.delete_analyses_for_policy(current_user.user_id, cid)
        except Exception as exc:
            logger.debug("Cascading cleanup warning during delete_policy: %s", exc)

        # 3. Delete policy metadata and GridFS raw file
        for cid in candidate_ids:
            if repo.delete_policy(current_user.user_id, cid):
                deleted = True
            elif repo.delete_policy_by_hash(current_user.user_id, cid):
                deleted = True

    cache_removed = False
    for cid in candidate_ids:
        if remove_cached_policy(cid, current_user.user_id):
            cache_removed = True

    if deleted or cache_removed:
        return {"success": True, "message": "Policy deleted successfully."}

    if get_cached_policy(policy_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bundled demonstration policies are read-only and cannot be deleted.",
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Policy not found or access denied.",
    )
