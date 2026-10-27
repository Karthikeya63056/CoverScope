"""MongoDB collection schema definitions, ownership rules, and idempotent index setup.

CoverScope Collections:
- `users`: Authenticated user profiles with external IAM / administrator mappings.
- `policies`: Tenant-scoped policy document metadata and storage references.
- `conversations`: Q&A consultation sessions linked to a user and policy.
- `messages`: Evidence-linked dialogue messages with citation references.
- `analysis_records`: Summaries of scenario evaluations and policy comparisons.
"""
from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# Canonical collection names
COLL_USERS = "users"
COLL_POLICIES = "policies"
COLL_CONVERSATIONS = "conversations"
COLL_MESSAGES = "messages"
COLL_ANALYSIS_RECORDS = "analysis_records"


def _ensure_collection_indexes(coll: Any, indexes: list[IndexModel]) -> list[str]:
    """Create indexes idempotently, safely migrating altered index specifications if needed."""
    try:
        return coll.create_indexes(indexes)
    except PyMongoError as exc:
        if getattr(exc, "code", None) == 86 or "IndexKeySpecsConflict" in str(exc) or "same name" in str(exc):
            try:
                existing_info = coll.index_information()
                for idx in indexes:
                    idx_name = idx.document.get("name")
                    if idx_name and idx_name in existing_info:
                        old_spec = existing_info[idx_name]
                        if bool(old_spec.get("unique")) != bool(idx.document.get("unique")):
                            coll.drop_index(idx_name)
                return coll.create_indexes(indexes)
            except Exception as inner_exc:
                logger.warning("Could not automatically recreate conflicting index: %s", inner_exc)
        raise


def init_db_indexes(db: Database[dict[str, Any]]) -> dict[str, list[str]]:
    """Create collection indexes idempotently without dropping or modifying data.

    Returns a mapping of collection names to created index names.
    """
    results: dict[str, list[str]] = {}

    try:
        # 1. users: Unique compound index on (auth_provider, auth_provider_user_id)
        user_indexes = [
            IndexModel(
                [("auth_provider", ASCENDING), ("auth_provider_user_id", ASCENDING)],
                unique=True,
                name="idx_users_provider_uid",
            ),
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email"),
        ]
        created = _ensure_collection_indexes(db[COLL_USERS], user_indexes)
        results[COLL_USERS] = created

        # 2. policies: Owner lookup, recency ordering, and duplicate upload detection
        policy_indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("updated_at", DESCENDING)],
                name="idx_policies_user_updated",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("document_hash", ASCENDING)],
                unique=True,
                name="idx_policies_user_doc_hash",
            ),
        ]
        created = _ensure_collection_indexes(db[COLL_POLICIES], policy_indexes)
        results[COLL_POLICIES] = created

        # 3. conversations: User-scoped conversation lookups
        conv_indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("updated_at", DESCENDING)],
                name="idx_conv_user_updated",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("policy_id", ASCENDING)],
                unique=True,
                name="idx_conv_user_policy",
            ),
        ]
        created = _ensure_collection_indexes(db[COLL_CONVERSATIONS], conv_indexes)
        results[COLL_CONVERSATIONS] = created

        # 4. messages: Conversation chronological ordering and user audit
        msg_indexes = [
            IndexModel(
                [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
                name="idx_msg_conv_created",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_msg_user_created",
            ),
        ]
        created = _ensure_collection_indexes(db[COLL_MESSAGES], msg_indexes)
        results[COLL_MESSAGES] = created

        # 5. analysis_records: Scenario and comparison history lookup
        analysis_indexes = [
            IndexModel(
                [
                    ("user_id", ASCENDING),
                    ("policy_id", ASCENDING),
                    ("created_at", DESCENDING),
                ],
                name="idx_analysis_user_policy_created",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("analysis_type", ASCENDING)],
                name="idx_analysis_user_type",
            ),
        ]
        created = _ensure_collection_indexes(db[COLL_ANALYSIS_RECORDS], analysis_indexes)
        results[COLL_ANALYSIS_RECORDS] = created

        logger.info("Successfully ensured all MongoDB indexes for CoverScope.")
        return results

    except PyMongoError as exc:
        logger.error("Failed to initialize database indexes: %s", exc)
        raise
