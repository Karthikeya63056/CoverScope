"""CoverScope MongoDB Atlas persistence layer."""
from __future__ import annotations

from typing import Any

__all__ = [
    "COLL_ANALYSIS_RECORDS",
    "COLL_CONVERSATIONS",
    "COLL_MESSAGES",
    "COLL_POLICIES",
    "COLL_USERS",
    "AnalysisRepository",
    "ConversationRepository",
    "DatabaseHealthReport",
    "DatabaseHealthStatus",
    "DocumentStorageInterface",
    "InMemoryStorageAdapter",
    "PolicyRepository",
    "StorageReference",
    "UserRepository",
    "check_mongodb_health",
    "close_mongodb_client",
    "get_database",
    "get_mongodb_client",
    "init_db_indexes",
    "redact_mongo_uri",
    "sanitize_mongo_error",
]


def __getattr__(name: str) -> Any:
    if name in ("get_mongodb_client", "get_database", "close_mongodb_client", "redact_mongo_uri", "sanitize_mongo_error"):
        from backend.database import client
        return getattr(client, name)
    if name in ("check_mongodb_health", "DatabaseHealthStatus", "DatabaseHealthReport"):
        from backend.database import healthcheck
        return getattr(healthcheck, name)
    if name in ("init_db_indexes", "COLL_USERS", "COLL_POLICIES", "COLL_CONVERSATIONS", "COLL_MESSAGES", "COLL_ANALYSIS_RECORDS"):
        from backend.database import schema
        return getattr(schema, name)
    if name in ("UserRepository", "PolicyRepository", "ConversationRepository", "AnalysisRepository"):
        from backend.database import repositories
        return getattr(repositories, name)
    if name in ("DocumentStorageInterface", "InMemoryStorageAdapter", "StorageReference"):
        from backend.database import storage
        return getattr(storage, name)
    raise AttributeError(f"module 'backend.database' has no attribute '{name}'")
