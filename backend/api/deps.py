"""Authentication dependencies, JWT token management, and policy cache for FastAPI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
import secrets
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Header, Request, status
import jwt

from backend.services.auth_service import AuthUser

logger = logging.getLogger(__name__)

# Security configuration. A per-process random secret is used when the operator
# has not configured one, so the application never ships with a known signing key.
_configured_jwt_secret = os.getenv("COVERSCOPE_JWT_SECRET")
if not _configured_jwt_secret:
    logger.warning(
        "COVERSCOPE_JWT_SECRET is not set; using a random per-process secret. "
        "Existing sessions will be invalidated when the process restarts."
    )
JWT_SECRET = _configured_jwt_secret or secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Global in-memory cache for processed policy objects. Bundled policies are
# shared (owner None); uploaded policies are keyed by owner + fingerprint so a
# cached document can never leak across authenticated users.
_POLICY_MEMORY_CACHE: dict[str, Any] = {}
_POLICY_OWNERS: dict[str, str | None] = {}
_POLICY_ALIASES: dict[str, str] = {}
_OFFLINE_RAW_BYTES: dict[str, tuple[bytes, str]] = {}


def store_offline_raw_policy(user_id: str, document_hash: str, filename: str, content: bytes) -> None:
    """Store raw PDF bytes in memory during offline mode when MongoDB is unavailable."""
    if user_id and document_hash and content:
        _OFFLINE_RAW_BYTES[f"{user_id}:{document_hash}"] = (content, filename)


def remove_offline_raw_policy(user_id: str, identifier: str) -> None:
    """Remove offline raw bytes from RAM."""
    _OFFLINE_RAW_BYTES.pop(f"{user_id}:{identifier}", None)


def _cache_key(fingerprint: str, user_id: str | None) -> str:
    return f"{user_id}:{fingerprint}" if user_id else fingerprint


def _resolve_cache_key(identifier: str, user_id: str | None) -> str | None:
    """Resolve a public policy id (Mongo _id, fingerprint, or alias) to a cache key."""
    if not identifier:
        return None

    alias_key = _POLICY_ALIASES.get(identifier)
    if alias_key is not None:
        return alias_key

    if user_id is not None:
        owner_key = _cache_key(identifier, user_id)
        if owner_key in _POLICY_MEMORY_CACHE:
            return owner_key

    if identifier in _POLICY_MEMORY_CACHE:
        return identifier
    return None


def cache_processed_policy(
    policy: Any,
    *,
    user_id: str | None = None,
    alias: str | None = None,
) -> None:
    """Store a prepared policy in memory, scoped to its owner when provided."""
    fingerprint = getattr(policy, "fingerprint", None)
    if policy is None or not fingerprint:
        return

    key = _cache_key(fingerprint, user_id)
    _POLICY_MEMORY_CACHE[key] = policy
    _POLICY_OWNERS[key] = user_id
    if alias and alias != fingerprint:
        _POLICY_ALIASES[str(alias)] = key


def get_cached_policy(identifier: str, user_id: str | None = None) -> Any | None:
    """Retrieve a prepared policy by fingerprint, database id, or alias.

    Owner-scoped entries are only returned to the matching authenticated user.
    Bundled policies (stored without an owner) remain available to everyone.
    If an owner policy is not found in memory, attempts multi-tier on-demand restoration:
    1. Direct in-memory lookup via key, alias, or document_hash.
    2. MongoDB lookup to resolve Mongo _id to document_hash and check active cache.
    3. Direct on-demand restoration from MongoDB Atlas GridFS storage.
    4. Offline in-memory raw buffer fallback (when MongoDB is unavailable).
    5. Bundled read-only PDFs in the pdfs/ repository folder.
    """
    if not identifier:
        return None

    # 1. Direct in-memory cache resolution
    key = _resolve_cache_key(identifier, user_id)
    if key is not None:
        owner = _POLICY_OWNERS.get(key)
        if owner is None or owner == user_id:
            cached = _POLICY_MEMORY_CACHE.get(key)
            if cached is not None:
                return cached

    # 2. Check if identifier directly matches an unowned/bundled policy
    if identifier in _POLICY_MEMORY_CACHE:
        return _POLICY_MEMORY_CACHE[identifier]

    # 3. Resolve Mongo _id or fingerprint via MongoDB Atlas
    p_doc: dict[str, Any] | None = None
    doc_hash: str = identifier
    doc_name: str | None = None

    db = None
    try:
        from backend.database.client import get_database
        from backend.database.repositories import PolicyRepository
        db = get_database()
        if db is not None:
            repo = PolicyRepository(db)
            if user_id:
                p_doc = repo.get_policy(user_id, identifier)
                if not p_doc:
                    p_doc = repo.get_policy_by_hash(user_id, identifier)
            if not p_doc:
                # Search by ObjectId directly in case user scoping varies
                try:
                    from bson import ObjectId
                    raw = db["policies"].find_one({"_id": ObjectId(identifier)})
                    if raw:
                        p_doc = dict(raw)
                        p_doc["id"] = str(p_doc["_id"])
                except Exception:
                    pass

            if p_doc:
                doc_hash = p_doc.get("document_hash") or doc_hash
                doc_name = p_doc.get("document_name")
    except Exception as exc:
        logger.debug("Database lookup in get_cached_policy for %s: %s", identifier, exc)

    # 4. If resolved doc_hash is already in memory cache, link alias and return
    if doc_hash:
        if user_id:
            owner_key = _cache_key(doc_hash, user_id)
            if owner_key in _POLICY_MEMORY_CACHE:
                _POLICY_ALIASES[identifier] = owner_key
                return _POLICY_MEMORY_CACHE[owner_key]

        if doc_hash in _POLICY_MEMORY_CACHE:
            _POLICY_ALIASES[identifier] = doc_hash
            return _POLICY_MEMORY_CACHE[doc_hash]

    # 5. Restore raw PDF bytes directly from MongoDB Atlas GridFS
    pdf_bytes: bytes | None = None
    resolved_filename = doc_name or f"{identifier}.pdf"

    if db is not None and user_id:
        try:
            repo = PolicyRepository(db)
            grid_res = repo.get_policy_file(user_id, identifier)
            if not grid_res and doc_hash != identifier:
                grid_res = repo.get_policy_file(user_id, doc_hash)
            if grid_res is not None:
                pdf_bytes, resolved_filename = grid_res
                logger.info("Successfully fetched policy file from MongoDB Atlas GridFS for user %s (%s).", user_id, resolved_filename)
        except Exception as exc:
            logger.debug("GridFS lookup failed in get_cached_policy: %s", exc)

    # 5b. Offline memory fallback (when MongoDB is offline/mocked)
    if pdf_bytes is None and user_id:
        offline_res = _OFFLINE_RAW_BYTES.get(f"{user_id}:{doc_hash}") or _OFFLINE_RAW_BYTES.get(f"{user_id}:{identifier}")
        if offline_res:
            pdf_bytes, resolved_filename = offline_res

    # 5c. Check single baseline demo policy in pdfs/ repository folder
    baseline_filename = "Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf"
    if pdf_bytes is None:
        from pathlib import Path
        baseline_file = Path("pdfs") / baseline_filename
        if baseline_file.exists():
            try:
                b = baseline_file.read_bytes()
                from backend.qa.workflow import fingerprint
                fp = fingerprint(b, baseline_file.name)
                if fp == doc_hash or fp == identifier or identifier in (baseline_filename, "demo", "star"):
                    pdf_bytes = b
                    resolved_filename = baseline_file.name
            except Exception:
                pass

    # 6. If PDF content found, parse with prepare_policy and populate cache & alias
    if pdf_bytes is not None:
        try:
            from backend.qa.workflow import prepare_policy
            policy = prepare_policy(pdf_bytes, resolved_filename)
            cache_processed_policy(policy, user_id=user_id, alias=identifier)
            _POLICY_ALIASES[identifier] = _cache_key(policy.fingerprint, user_id)
            logger.info("Successfully reconstructed policy '%s' (%s) into memory for user %s.", policy.filename, identifier, user_id)
            return policy
        except Exception as exc:
            logger.warning("Could not reconstruct policy for %s: %s", identifier, exc)

    return None


def get_all_cached_policies(user_id: str | None = None) -> list[Any]:
    """Retrieve policies visible to the user: shared bundles plus their own uploads."""
    visible: list[Any] = []
    for key, policy in _POLICY_MEMORY_CACHE.items():
        owner = _POLICY_OWNERS.get(key)
        if owner is None or (user_id is not None and owner == user_id):
            visible.append(policy)
    return visible


def remove_cached_policy(identifier: str, user_id: str | None) -> bool:
    """Remove an owner-scoped cached policy. Shared bundles cannot be removed."""
    key = _resolve_cache_key(identifier, user_id)
    removed = False
    if key is not None:
        owner = _POLICY_OWNERS.get(key)
        if owner is not None and owner == user_id:
            _POLICY_MEMORY_CACHE.pop(key, None)
            _POLICY_OWNERS.pop(key, None)
            for alias, alias_key in list(_POLICY_ALIASES.items()):
                if alias_key == key:
                    _POLICY_ALIASES.pop(alias, None)
            removed = True

    if user_id:
        remove_offline_raw_policy(user_id, identifier)
    return removed


def create_access_token(user: AuthUser) -> str:
    """Generate a signed JWT access token for an authenticated user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "name": user.display_name,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode a JWT access token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    """Extract authenticated user identity from Bearer header or HttpOnly cookie."""
    token: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    return AuthUser(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        display_name=payload.get("name", payload.get("email", "User")),
        role=payload.get("role", "policyholder"),
        authenticated_at=payload.get("iat", 0.0),
    )


async def get_optional_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser | None:
    """Permit unauthenticated or guest fallback for public health/status endpoints."""
    try:
        return await get_current_user(request, authorization)
    except HTTPException:
        return None
