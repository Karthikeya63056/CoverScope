"""Tenant-scoped MongoDB repositories for CoverScope.

Authorization and Multi-Tenant Isolation Guarantee:
Every query, insert, update, and delete MUST explicitly filter by a verified,
non-empty `user_id`. Queries without owner scoping are strictly disallowed.
All identifiers are strictly validated to prevent injection or query tampering.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
import gridfs
from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from backend.database.client import sanitize_mongo_error
from backend.database.schema import (
    COLL_ANALYSIS_RECORDS,
    COLL_CONVERSATIONS,
    COLL_MESSAGES,
    COLL_POLICIES,
    COLL_USERS,
)

logger = logging.getLogger(__name__)


def _validate_user_id(user_id: str | None) -> str:
    """Validate that user_id is a non-empty, trustworthy string."""
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("A verified user_id is required for all database operations.")
    return user_id.strip()


def _parse_object_id(id_val: str | ObjectId | None, field_name: str = "id") -> ObjectId:
    """Validate and parse a MongoDB ObjectId."""
    if isinstance(id_val, ObjectId):
        return id_val
    if not id_val or not isinstance(id_val, str) or not id_val.strip():
        raise ValueError(f"Invalid {field_name}: empty identifier.")
    try:
        return ObjectId(id_val.strip())
    except (InvalidId, ValueError) as exc:
        raise ValueError(f"Invalid {field_name} format: '{id_val}' is not a valid ObjectId.") from exc


def _doc_to_dict(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize MongoDB document for application use, casting _id to str."""
    if doc is None:
        return None
    res = dict(doc)
    if "_id" in res:
        res["id"] = str(res.pop("_id"))
    return res


class UserRepository:
    """Repository for authenticated user profiles and preferences."""

    def __init__(self, db: Database[dict[str, Any]]) -> None:
        self.coll = db[COLL_USERS]

    def upsert_user(
        self,
        *,
        auth_provider: str,
        auth_provider_user_id: str,
        email: str,
        display_name: str,
        role: str = "policyholder",
        preferences: dict[str, Any] | None = None,
    ) -> str:
        """Upsert a user identity profile, returning the string user_id."""
        if not auth_provider.strip() or not auth_provider_user_id.strip():
            raise ValueError("auth_provider and auth_provider_user_id are required.")

        now = datetime.now(timezone.utc)
        filter_doc = {
            "auth_provider": auth_provider.strip(),
            "auth_provider_user_id": auth_provider_user_id.strip(),
        }
        update_doc = {
            "$set": {
                "email": email.strip().lower(),
                "display_name": display_name.strip(),
                "role": role.strip(),
                "preferences": preferences or {},
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        }
        try:
            res = self.coll.find_one_and_update(
                filter_doc,
                update_doc,
                upsert=True,
                return_document=True,
            )
            return str(res["_id"])
        except PyMongoError as exc:
            logger.error("Error upserting user: %s", sanitize_mongo_error(exc))
            raise

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Retrieve user profile by internal ID."""
        clean_uid = _validate_user_id(user_id)
        try:
            oid = _parse_object_id(clean_uid, "user_id")
            doc = self.coll.find_one({"_id": oid})
        except ValueError:
            # Fallback to string-based identifier (e.g. usr_123456)
            doc = self.coll.find_one({"auth_provider_user_id": clean_uid})
        return _doc_to_dict(doc)


class PolicyRepository:
    """Repository for tenant-scoped policy documents and metadata."""

    def __init__(self, db: Database[dict[str, Any]]) -> None:
        self.db = db
        self.coll = db[COLL_POLICIES]
        try:
            self.fs: gridfs.GridFS | None = gridfs.GridFS(db)
        except Exception as exc:
            logger.warning("Could not initialize GridFS: %s", exc)
            self.fs = None

    def save_policy_file(
        self,
        *,
        user_id: str,
        document_hash: str,
        filename: str,
        file_bytes: bytes,
    ) -> str | None:
        """Store raw policy PDF bytes in MongoDB GridFS strictly scoped to user_id.

        Replaces any prior version for this user and document_hash to avoid orphaned chunks.
        Returns the GridFS file_id string or None on failure.
        """
        clean_uid = _validate_user_id(user_id)
        clean_hash = document_hash.strip()
        clean_name = filename.strip()
        if not clean_hash or not clean_name or not file_bytes:
            raise ValueError("document_hash, filename, and non-empty file_bytes are required.")

        if self.fs is None:
            return None

        try:
            # Delete any existing file with matching owner and hash
            for existing in self.fs.find({"metadata.user_id": clean_uid, "metadata.document_hash": clean_hash}):
                try:
                    self.fs.delete(existing._id)
                except Exception:
                    pass

            grid_id = self.fs.put(
                file_bytes,
                filename=clean_name,
                metadata={
                    "user_id": clean_uid,
                    "document_hash": clean_hash,
                    "document_name": clean_name,
                    "file_size": len(file_bytes),
                    "created_at": datetime.now(timezone.utc),
                },
            )
            return str(grid_id)
        except Exception as exc:
            logger.error("Error saving policy file to GridFS: %s", sanitize_mongo_error(exc))
            return None

    def get_policy_file(
        self,
        user_id: str,
        identifier: str,
    ) -> tuple[bytes, str] | None:
        """Retrieve raw policy PDF bytes and filename from GridFS strictly scoped to user_id.

        Matches by document_hash, GridFS ObjectId, or policy collection record.
        """
        clean_uid = _validate_user_id(user_id)
        clean_id = identifier.strip()
        if not clean_id or self.fs is None:
            return None

        # 1. Direct match by metadata.document_hash
        try:
            gf = self.fs.find_one({
                "metadata.user_id": clean_uid,
                "metadata.document_hash": clean_id,
            })
            if gf is not None:
                return gf.read(), gf.filename or f"{clean_id}.pdf"
        except Exception as exc:
            logger.debug("GridFS find by document_hash error: %s", exc)

        # 2. Check if identifier is a GridFS ObjectId
        try:
            oid = ObjectId(clean_id)
            gf = self.fs.find_one({"_id": oid, "metadata.user_id": clean_uid})
            if gf is not None:
                return gf.read(), gf.filename or f"{clean_id}.pdf"
        except Exception:
            pass

        # 3. Look up policy collection record for this user to resolve file_id or document_hash
        try:
            pol = self.get_policy(clean_uid, clean_id)
            if not pol:
                pol = self.get_policy_by_hash(clean_uid, clean_id)
            if pol:
                file_id = pol.get("storage_reference", {}).get("file_id") or pol.get("metadata", {}).get("gridfs_file_id")
                if file_id:
                    try:
                        gf = self.fs.find_one({"_id": ObjectId(str(file_id)), "metadata.user_id": clean_uid})
                        if gf is not None:
                            return gf.read(), gf.filename or pol.get("document_name", f"{clean_id}.pdf")
                    except Exception:
                        pass
                p_hash = pol.get("document_hash")
                if p_hash and p_hash != clean_id:
                    gf = self.fs.find_one({
                        "metadata.user_id": clean_uid,
                        "metadata.document_hash": p_hash,
                    })
                    if gf is not None:
                        return gf.read(), gf.filename or pol.get("document_name", f"{clean_id}.pdf")
        except Exception as exc:
            logger.debug("GridFS lookup via policy record error: %s", exc)

        return None

    def delete_policy_file(self, user_id: str, identifier: str) -> bool:
        """Delete policy file(s) from GridFS strictly scoped to user_id."""
        clean_uid = _validate_user_id(user_id)
        clean_id = identifier.strip()
        if not clean_id or self.fs is None:
            return False

        deleted = False
        # Delete by metadata.document_hash
        try:
            for gf in self.fs.find({"metadata.user_id": clean_uid, "metadata.document_hash": clean_id}):
                self.fs.delete(gf._id)
                deleted = True
        except Exception as exc:
            logger.debug("GridFS delete by hash error: %s", exc)

        # Delete by ObjectId
        try:
            oid = ObjectId(clean_id)
            gf = self.fs.find_one({"_id": oid, "metadata.user_id": clean_uid})
            if gf is not None:
                self.fs.delete(oid)
                deleted = True
        except Exception:
            pass

        return deleted

    def save_policy_metadata(
        self,
        *,
        user_id: str,
        document_name: str,
        document_hash: str,
        page_count: int,
        metadata: dict[str, Any] | None = None,
        storage_reference: dict[str, Any] | None = None,
        processing_status: str = "processed",
    ) -> str:
        """Create or update policy metadata scoped strictly to user_id.

        Uses document_hash within user scope to prevent duplicate records.
        """
        clean_uid = _validate_user_id(user_id)
        if not document_name.strip() or not document_hash.strip():
            raise ValueError("document_name and document_hash are required.")

        now = datetime.now(timezone.utc)
        filter_doc = {
            "user_id": clean_uid,
            "document_hash": document_hash.strip(),
        }
        update_doc = {
            "$set": {
                "document_name": document_name.strip(),
                "page_count": max(1, page_count),
                "processing_status": processing_status,
                "metadata": metadata or {},
                "storage_reference": storage_reference or {},
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": clean_uid,
                "created_at": now,
            },
        }
        try:
            res = self.coll.find_one_and_update(
                filter_doc,
                update_doc,
                upsert=True,
                return_document=True,
            )
            return str(res["_id"])
        except PyMongoError as exc:
            logger.error("Error saving policy metadata: %s", sanitize_mongo_error(exc))
            raise

    def get_policy(self, user_id: str, policy_id: str) -> dict[str, Any] | None:
        """Retrieve policy strictly scoped to authenticated user_id.

        Returns None (rather than raising) when policy_id is a fingerprint or
        other non-ObjectId identifier, so callers can fall back to hash lookup.
        """
        clean_uid = _validate_user_id(user_id)
        try:
            oid = _parse_object_id(policy_id, "policy_id")
        except ValueError:
            return None
        doc = self.coll.find_one({"_id": oid, "user_id": clean_uid})
        return _doc_to_dict(doc)

    def get_policy_by_hash(self, user_id: str, document_hash: str) -> dict[str, Any] | None:
        """Retrieve policy by document_hash strictly scoped to authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        if not document_hash.strip():
            return None
        doc = self.coll.find_one({"user_id": clean_uid, "document_hash": document_hash.strip()})
        return _doc_to_dict(doc)

    def list_user_policies(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List recent policies owned strictly by authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        cursor = (
            self.coll.find({"user_id": clean_uid})
            .sort("updated_at", DESCENDING)
            .limit(max(1, min(limit, 100)))
        )
        return [_doc_to_dict(d) for d in cursor if d is not None]

    def count_user_policies(self, user_id: str) -> int:
        """Count total policies owned strictly by authenticated user_id without pagination limit."""
        clean_uid = _validate_user_id(user_id)
        return self.coll.count_documents({"user_id": clean_uid})

    def delete_policy(self, user_id: str, policy_id: str) -> bool:
        """Delete policy by ObjectId strictly scoped to authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        try:
            oid = _parse_object_id(policy_id, "policy_id")
        except ValueError:
            return False
        # Fetch document to clean up associated GridFS file
        doc = self.coll.find_one({"_id": oid, "user_id": clean_uid})
        if doc:
            doc_hash = doc.get("document_hash")
            if doc_hash:
                self.delete_policy_file(clean_uid, doc_hash)
            file_id = doc.get("storage_reference", {}).get("file_id") or doc.get("metadata", {}).get("gridfs_file_id")
            if file_id:
                self.delete_policy_file(clean_uid, str(file_id))

        res = self.coll.delete_one({"_id": oid, "user_id": clean_uid})
        return res.deleted_count > 0

    def delete_policy_by_hash(self, user_id: str, document_hash: str) -> bool:
        """Delete policy by document_hash strictly scoped to authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        if not document_hash.strip():
            return False
        doc = self.coll.find_one({"user_id": clean_uid, "document_hash": document_hash.strip()})
        if doc:
            file_id = doc.get("storage_reference", {}).get("file_id") or doc.get("metadata", {}).get("gridfs_file_id")
            if file_id:
                self.delete_policy_file(clean_uid, str(file_id))
        self.delete_policy_file(clean_uid, document_hash.strip())
        res = self.coll.delete_one(
            {"user_id": clean_uid, "document_hash": document_hash.strip()}
        )
        return res.deleted_count > 0


class ConversationRepository:
    """Repository for user Q&A dialogues and dialogue messages."""

    def __init__(self, db: Database[dict[str, Any]]) -> None:
        self.conv_coll = db[COLL_CONVERSATIONS]
        self.msg_coll = db[COLL_MESSAGES]

    def get_or_create_conversation(
        self,
        *,
        user_id: str,
        policy_id: str,
        title: str | None = None,
        conversation_id: str | None = None,
        create_new: bool = False,
    ) -> str:
        """Retrieve active conversation or create a new one scoped to user and policy."""
        clean_uid = _validate_user_id(user_id)
        if not policy_id.strip():
            raise ValueError("policy_id is required.")

        now = datetime.now(timezone.utc)
        if conversation_id and conversation_id.strip():
            try:
                c_oid = _parse_object_id(conversation_id, "conversation_id")
                conv = self.conv_coll.find_one({"_id": c_oid, "user_id": clean_uid})
                if conv is not None:
                    self.conv_coll.update_one({"_id": c_oid}, {"$set": {"updated_at": now}})
                    return str(conv["_id"])
            except Exception:
                pass

        if create_new:
            doc = {
                "user_id": clean_uid,
                "policy_id": policy_id.strip(),
                "title": (title or "Policy Q&A Consultation").strip(),
                "created_at": now,
                "updated_at": now,
            }
            res = self.conv_coll.insert_one(doc)
            return str(res.inserted_id)

        filter_doc = {
            "user_id": clean_uid,
            "policy_id": policy_id.strip(),
        }
        update_doc = {
            "$set": {
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": clean_uid,
                "policy_id": policy_id.strip(),
                "title": (title or "Policy Q&A Consultation").strip(),
                "created_at": now,
            },
        }
        res = self.conv_coll.find_one_and_update(
            filter_doc,
            update_doc,
            upsert=True,
            return_document=True,
        )
        return str(res["_id"])

    def list_user_conversations(
        self,
        user_id: str,
        policy_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List recent conversations owned strictly by authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        query: dict[str, Any] = {"user_id": clean_uid}
        if policy_id and policy_id.strip():
            query["policy_id"] = policy_id.strip()

        cursor = (
            self.conv_coll.find(query)
            .sort("updated_at", DESCENDING)
            .limit(max(1, min(limit, 100)))
        )
        return [_doc_to_dict(d) for d in cursor if d is not None]

    def count_user_conversations(self, user_id: str) -> int:
        """Count total conversations owned strictly by authenticated user_id without pagination limit."""
        clean_uid = _validate_user_id(user_id)
        return self.conv_coll.count_documents({"user_id": clean_uid})

    def append_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        policy_id: str,
        role: str,
        content: str,
        evidence_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Append a dialogue message after verifying conversation ownership."""
        clean_uid = _validate_user_id(user_id)
        c_oid = _parse_object_id(conversation_id, "conversation_id")

        # Verify conversation ownership first
        conv = self.conv_coll.find_one({"_id": c_oid, "user_id": clean_uid})
        if conv is None:
            raise PermissionError("Access denied: Conversation does not belong to authenticated user.")

        now = datetime.now(timezone.utc)
        doc = {
            "user_id": clean_uid,
            "conversation_id": str(c_oid),
            "policy_id": policy_id.strip(),
            "role": role.strip(),
            "content": content,
            "evidence_metadata": evidence_metadata or {},
            "created_at": now,
        }
        res = self.msg_coll.insert_one(doc)
        # Update conversation recency
        self.conv_coll.update_one({"_id": c_oid}, {"$set": {"updated_at": now}})
        return str(res.inserted_id)

    def list_messages(self, user_id: str, conversation_id: str) -> list[dict[str, Any]]:
        """Retrieve chronological messages for a conversation owned by user_id."""
        clean_uid = _validate_user_id(user_id)
        c_oid = _parse_object_id(conversation_id, "conversation_id")

        # Confirm ownership
        conv = self.conv_coll.find_one({"_id": c_oid, "user_id": clean_uid})
        if conv is None:
            raise PermissionError("Access denied: Conversation does not belong to authenticated user.")

        cursor = self.msg_coll.find(
            {"conversation_id": str(c_oid), "user_id": clean_uid}
        ).sort("created_at", 1)
        return [_doc_to_dict(d) for d in cursor if d is not None]

    def delete_conversations_for_policy(self, user_id: str, policy_id: str) -> int:
        """Purge all conversations and associated dialogue messages for a deleted policy."""
        clean_uid = _validate_user_id(user_id)
        if not policy_id.strip():
            return 0
        clean_pid = policy_id.strip()
        candidates = [clean_pid]
        try:
            try:
                oid = _parse_object_id(clean_pid)
                p = self.conv_coll.database[COLL_POLICIES].find_one({"_id": oid, "user_id": clean_uid})
            except ValueError:
                p = self.conv_coll.database[COLL_POLICIES].find_one({"document_hash": clean_pid, "user_id": clean_uid})
            if p:
                if p.get("document_hash"):
                    candidates.append(p["document_hash"])
                if p.get("_id"):
                    candidates.append(str(p["_id"]))
        except Exception as exc:
            logger.debug("Dual identifier resolution warning: %s", exc)

        convs = list(self.conv_coll.find({"user_id": clean_uid, "policy_id": {"$in": candidates} if len(candidates) > 1 else clean_pid}))
        count = 0
        for c in convs:
            c_id = str(c["_id"])
            self.msg_coll.delete_many({"conversation_id": c_id, "user_id": clean_uid})
            self.conv_coll.delete_one({"_id": c["_id"], "user_id": clean_uid})
            count += 1
        return count

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a single conversation and its messages strictly scoped to user_id."""
        clean_uid = _validate_user_id(user_id)
        c_oid = _parse_object_id(conversation_id, "conversation_id")
        conv = self.conv_coll.find_one({"_id": c_oid, "user_id": clean_uid})
        if not conv:
            return False
        self.msg_coll.delete_many({"conversation_id": str(c_oid), "user_id": clean_uid})
        res = self.conv_coll.delete_one({"_id": c_oid, "user_id": clean_uid})
        return res.deleted_count > 0


class AnalysisRepository:
    """Repository for policy scenario evaluations and comparison results."""

    def __init__(self, db: Database[dict[str, Any]]) -> None:
        self.db = db
        self.coll = db[COLL_ANALYSIS_RECORDS]

    def save_analysis(
        self,
        *,
        user_id: str,
        policy_id: str,
        analysis_type: str,
        input_summary: dict[str, Any],
        result_summary: dict[str, Any],
        source_references: list[dict[str, Any]] | None = None,
    ) -> str:
        """Store an analysis audit record scoped strictly to authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        if not analysis_type.strip():
            raise ValueError("analysis_type is required.")

        now = datetime.now(timezone.utc)
        doc = {
            "user_id": clean_uid,
            "policy_id": policy_id.strip(),
            "analysis_type": analysis_type.strip(),
            "input_summary": input_summary,
            "result_summary": result_summary,
            "source_references": source_references or [],
            "created_at": now,
        }
        res = self.coll.insert_one(doc)
        return str(res.inserted_id)

    def list_analyses(
        self,
        user_id: str,
        policy_id: str | None = None,
        analysis_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List recent analysis records owned strictly by authenticated user_id."""
        clean_uid = _validate_user_id(user_id)
        query: dict[str, Any] = {"user_id": clean_uid}
        if policy_id and policy_id.strip():
            clean_pid = policy_id.strip()
            candidates = [clean_pid]
            try:
                try:
                    oid = _parse_object_id(clean_pid)
                    p = self.db[COLL_POLICIES].find_one({"_id": oid, "user_id": clean_uid})
                except ValueError:
                    p = self.db[COLL_POLICIES].find_one({"document_hash": clean_pid, "user_id": clean_uid})
                if p:
                    if p.get("document_hash"):
                        candidates.append(p["document_hash"])
                    if p.get("_id"):
                        candidates.append(str(p["_id"]))
            except Exception as exc:
                logger.debug("Dual identifier resolution warning: %s", exc)
            query["policy_id"] = {"$in": candidates} if len(candidates) > 1 else clean_pid

        if analysis_type and analysis_type.strip():
            query["analysis_type"] = analysis_type.strip()

        cursor = (
            self.coll.find(query)
            .sort("created_at", DESCENDING)
            .limit(max(1, min(limit, 50)))
        )
        return [_doc_to_dict(d) for d in cursor if d is not None]

    def count_user_analyses(self, user_id: str) -> int:
        """Count total analysis records owned strictly by authenticated user_id without pagination limit."""
        clean_uid = _validate_user_id(user_id)
        return self.coll.count_documents({"user_id": clean_uid})

    def delete_analyses_for_policy(self, user_id: str, policy_id: str) -> int:
        """Purge all analysis audit records referencing a deleted policy."""
        clean_uid = _validate_user_id(user_id)
        if not policy_id.strip():
            return 0
        clean_pid = policy_id.strip()
        candidates = [clean_pid]
        try:
            try:
                oid = _parse_object_id(clean_pid)
                p = self.db[COLL_POLICIES].find_one({"_id": oid, "user_id": clean_uid})
            except ValueError:
                p = self.db[COLL_POLICIES].find_one({"document_hash": clean_pid, "user_id": clean_uid})
            if p:
                if p.get("document_hash"):
                    candidates.append(p["document_hash"])
                if p.get("_id"):
                    candidates.append(str(p["_id"]))
        except Exception as exc:
            logger.debug("Dual identifier resolution warning: %s", exc)

        res = self.coll.delete_many({"user_id": clean_uid, "policy_id": {"$in": candidates} if len(candidates) > 1 else clean_pid})
        return res.deleted_count
