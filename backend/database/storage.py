"""Document storage interface and storage reference contracts for CoverScope.

Architecture Rule:
Policy metadata, audit logs, and extraction summaries are stored in MongoDB Atlas,
while full raw PDF binaries are kept in-memory or referenced via secure, private
object storage references. Storing raw 20MB PDFs directly in standard MongoDB documents
violates BSON size limits (16MB) and degrades cluster cache performance.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any


@dataclass(frozen=True)
class StorageReference:
    """Descriptor for a document binary stored in an external or in-memory backend."""
    storage_type: str  # e.g., "in_memory", "s3", "azure_blob", "gridfs"
    storage_key: str
    sha256_hash: str
    byte_size: int
    content_type: str = "application/pdf"
    stored_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "storage_type": self.storage_type,
            "storage_key": self.storage_key,
            "sha256_hash": self.sha256_hash,
            "byte_size": self.byte_size,
            "content_type": self.content_type,
            "stored_at": self.stored_at or datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StorageReference:
        return cls(
            storage_type=data.get("storage_type", "in_memory"),
            storage_key=data.get("storage_key", ""),
            sha256_hash=data.get("sha256_hash", ""),
            byte_size=data.get("byte_size", 0),
            content_type=data.get("content_type", "application/pdf"),
            stored_at=data.get("stored_at", ""),
        )


class DocumentStorageInterface(ABC):
    """Abstract interface for policy binary storage and retrieval."""

    @abstractmethod
    def store_document(
        self,
        *,
        user_id: str,
        document_name: str,
        data: bytes,
    ) -> StorageReference:
        """Store policy binary bytes and return a verifiable storage reference."""

    @abstractmethod
    def retrieve_document(
        self,
        *,
        user_id: str,
        reference: StorageReference,
    ) -> bytes | None:
        """Retrieve binary bytes matching a verified storage reference and owner."""

    @abstractmethod
    def delete_document(
        self,
        *,
        user_id: str,
        reference: StorageReference,
    ) -> bool:
        """Delete stored binary matching owner and reference."""


class InMemoryStorageAdapter(DocumentStorageInterface):
    """Default in-memory storage adapter for zero-cloud and local development."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def store_document(
        self,
        *,
        user_id: str,
        document_name: str,
        data: bytes,
    ) -> StorageReference:
        sha = hashlib.sha256(data).hexdigest()
        key = f"{user_id}/{sha}_{document_name}"
        self._store[key] = data
        return StorageReference(
            storage_type="in_memory",
            storage_key=key,
            sha256_hash=sha,
            byte_size=len(data),
            content_type="application/pdf",
            stored_at=datetime.now(timezone.utc).isoformat(),
        )

    def retrieve_document(
        self,
        *,
        user_id: str,
        reference: StorageReference,
    ) -> bytes | None:
        if not reference.storage_key.startswith(f"{user_id}/"):
            return None
        return self._store.get(reference.storage_key)

    def delete_document(
        self,
        *,
        user_id: str,
        reference: StorageReference,
    ) -> bool:
        if not reference.storage_key.startswith(f"{user_id}/"):
            return False
        return self._store.pop(reference.storage_key, None) is not None
