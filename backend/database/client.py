"""MongoDB Atlas connection client and lifecycle management for CoverScope.

Provides a thread-safe singleton connection pool, lazy initialization,
strict connection timeouts, and credential redaction helpers so that sensitive
URIs and passwords are never exposed in logs, exceptions, or UI output.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from backend.config import settings

logger = logging.getLogger(__name__)

_CLIENT_LOCK = threading.Lock()
_CLIENT_INSTANCE: MongoClient[dict[str, Any]] | None = None
_CLIENT_URI: str | None = None

_PASSWORD_URI_RE = re.compile(r":([^@/:?#]+)@")


def redact_mongo_uri(uri: str | None) -> str:
    """Mask credentials in a MongoDB connection URI for safe diagnostic logging."""
    if not uri or not isinstance(uri, str):
        return "<not configured>"
    cleaned = uri.strip()
    if not cleaned:
        return "<not configured>"
    try:
        parts = urlsplit(cleaned)
        netloc = parts.netloc
        if "@" in netloc:
            creds, host = netloc.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                masked_netloc = f"{user}:*****@{host}"
            else:
                masked_netloc = f"*****@{host}"
            return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        # Fallback regex substitution
        return _PASSWORD_URI_RE.sub(r":*****@", cleaned)


def sanitize_mongo_error(exc: Exception) -> str:
    """Return a customer-safe error message stripped of passwords and full URIs."""
    msg = str(exc)
    redacted = _PASSWORD_URI_RE.sub(r":*****@", msg)
    # Further strip any mongodb+srv or mongodb scheme details if exposed
    if "mongodb+srv://" in redacted:
        redacted = re.sub(r"mongodb\+srv://[^\s]+", "<mongodb-cluster>", redacted)
    if "mongodb://" in redacted:
        redacted = re.sub(r"mongodb://[^\s]+", "<mongodb-cluster>", redacted)
    return redacted


def get_mongodb_client(
    uri: str | None = None,
    *,
    force_reconnect: bool = False,
) -> MongoClient[dict[str, Any]] | None:
    """Return the application singleton MongoClient.

    If no URI is supplied and MONGODB_URI is unset in configuration, returns None
    cleanly without raising exceptions, allowing safe offline and in-memory execution.
    """
    global _CLIENT_INSTANCE, _CLIENT_URI

    target_uri = uri if uri is not None else os.getenv("MONGODB_URI")
    if not target_uri or not target_uri.strip():
        return None
    clean_uri = target_uri.strip()

    with _CLIENT_LOCK:
        if (
            _CLIENT_INSTANCE is not None
            and not force_reconnect
            and _CLIENT_URI == clean_uri
        ):
            return _CLIENT_INSTANCE

        # Close any previous client before replacing it. Without this, every
        # forced reconnect would orphan a connection pool.
        if _CLIENT_INSTANCE is not None:
            try:
                _CLIENT_INSTANCE.close()
            except Exception as exc:
                logger.debug("Error closing previous MongoDB client: %s", exc)
            finally:
                _CLIENT_INSTANCE = None
                _CLIENT_URI = None

        try:
            client: MongoClient[dict[str, Any]] = MongoClient(
                clean_uri,
                serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
                connectTimeoutMS=settings.mongodb_connect_timeout_ms,
                retryWrites=True,
                appName="CoverScope",
            )
            _CLIENT_INSTANCE = client
            _CLIENT_URI = clean_uri
            return _CLIENT_INSTANCE
        except PyMongoError as exc:
            logger.warning(
                "Failed to initialize MongoDB client: %s",
                sanitize_mongo_error(exc),
            )
            raise


def get_database(
    db_name: str | None = None,
    uri: str | None = None,
) -> Database[dict[str, Any]] | None:
    """Return the configured Database instance, or None if MongoDB is unconfigured."""
    client = get_mongodb_client(uri)
    if client is None:
        return None
    name = (db_name or settings.mongodb_database or "coverscope").strip()
    return client[name]


def close_mongodb_client() -> None:
    """Close the active MongoClient and reset the singleton reference."""
    global _CLIENT_INSTANCE, _CLIENT_URI
    with _CLIENT_LOCK:
        if _CLIENT_INSTANCE is not None:
            try:
                _CLIENT_INSTANCE.close()
            except Exception as exc:
                logger.debug("Error closing MongoDB client: %s", exc)
            finally:
                _CLIENT_INSTANCE = None
                _CLIENT_URI = None
