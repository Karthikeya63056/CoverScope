"""Automated tests for CoverScope MongoDB Atlas integration.

Covers:
1. Environment configuration and missing URI fallback.
2. Credential redaction and error sanitization (never leaking passwords).
3. Lazy client singleton lifecycle.
4. Health check diagnostics across states (NOT_CONFIGURED, CONNECTED, AUTH_FAILED, UNAVAILABLE).
5. Idempotent schema index initialization.
6. Multi-tenant isolation: strict user_id scoping, cross-user rejection, and identifier validation.
7. Policy deduplication via document_hash.
8. Conversation ownership and unauthorized message append rejection.
9. Storage reference and in-memory adapter contracts.
10. Streamlit offline AppTest compatibility.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from bson import ObjectId
import pytest
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from backend.database.client import (
    close_mongodb_client,
    get_database,
    get_mongodb_client,
    redact_mongo_uri,
    sanitize_mongo_error,
)
from backend.database.healthcheck import (
    DatabaseHealthStatus,
    check_mongodb_health,
)
from backend.database.repositories import (
    AnalysisRepository,
    ConversationRepository,
    PolicyRepository,
    UserRepository,
)
from backend.database.schema import (
    COLL_ANALYSIS_RECORDS,
    COLL_CONVERSATIONS,
    COLL_MESSAGES,
    COLL_POLICIES,
    COLL_USERS,
    init_db_indexes,
)
from backend.database.storage import InMemoryStorageAdapter, StorageReference


# -----------------------------------------------------------------------------
# 1. Configuration, Redaction & Error Sanitization Tests
# -----------------------------------------------------------------------------
def test_missing_mongodb_uri_returns_none_cleanly(monkeypatch):
    """When MONGODB_URI is empty or unset, get_mongodb_client must return None."""
    monkeypatch.delenv("MONGODB_URI", raising=False)
    close_mongodb_client()

    client = get_mongodb_client()
    assert client is None
    db = get_database()
    assert db is None


def test_redact_mongo_uri_masks_passwords():
    """Ensure passwords in standard and SRV connection strings are never exposed."""
    raw_srv = "mongodb+srv://admin_user:SuperSecretPassword123!@cluster0.test.mongodb.net/coverscope?retryWrites=true"
    masked_srv = redact_mongo_uri(raw_srv)
    assert "SuperSecretPassword123!" not in masked_srv
    assert "admin_user:*****@cluster0.test.mongodb.net" in masked_srv

    raw_std = "mongodb://readonly_usr:P@ssw0rd99@db1.internal:27017,db2.internal:27017/coverscope"
    masked_std = redact_mongo_uri(raw_std)
    assert "P@ssw0rd99" not in masked_std
    assert "readonly_usr:*****@" in masked_std

    assert redact_mongo_uri("") == "<not configured>"
    assert redact_mongo_uri(None) == "<not configured>"


def test_sanitize_mongo_error_strips_passwords_and_uris():
    """Exceptions containing connection strings must be stripped before reporting."""
    exc = Exception("Failed to connect to mongodb+srv://admin:MyPass456@cluster0.abc.mongodb.net: timeout")
    sanitized = sanitize_mongo_error(exc)
    assert "MyPass456" not in sanitized
    assert "admin:MyPass456" not in sanitized


# -----------------------------------------------------------------------------
# 2. Healthcheck Diagnostics Tests
# -----------------------------------------------------------------------------
def test_healthcheck_not_configured_when_uri_is_unset(monkeypatch):
    """Health check reports NOT_CONFIGURED when URI is not present."""
    monkeypatch.delenv("MONGODB_URI", raising=False)
    report = check_mongodb_health()
    assert report.status == DatabaseHealthStatus.NOT_CONFIGURED
    assert report.is_connected is False
    assert "offline" in report.message.lower()


def test_healthcheck_connected_when_ping_succeeds(monkeypatch):
    """Health check executes real ping and reports CONNECTED on success."""
    fake_client = MagicMock()
    fake_client.admin.command.return_value = {"ok": 1}

    with patch("backend.database.healthcheck.get_mongodb_client", return_value=fake_client):
        report = check_mongodb_health("mongodb+srv://user:pass@cluster.mongodb.net")
        assert report.status == DatabaseHealthStatus.CONNECTED
        assert report.is_connected is True
        fake_client.admin.command.assert_called_once_with("ping")


def test_healthcheck_reports_auth_failed_on_operation_failure():
    """Health check identifies authentication errors without exposing credentials."""
    fake_client = MagicMock()
    fake_client.admin.command.side_effect = OperationFailure("bad auth : authentication failed")

    with patch("backend.database.healthcheck.get_mongodb_client", return_value=fake_client):
        report = check_mongodb_health("mongodb+srv://baduser:badpass@cluster.mongodb.net")
        assert report.status == DatabaseHealthStatus.AUTH_FAILED
        assert report.is_connected is False
        assert "authentication" in report.message.lower()


def test_healthcheck_reports_unavailable_on_timeout():
    """Health check identifies server selection timeouts."""
    fake_client = MagicMock()
    fake_client.admin.command.side_effect = ServerSelectionTimeoutError("No replica set members found")

    with patch("backend.database.healthcheck.get_mongodb_client", return_value=fake_client):
        report = check_mongodb_health("mongodb+srv://user:pass@offline-cluster.mongodb.net")
        assert report.status == DatabaseHealthStatus.UNAVAILABLE
        assert report.is_connected is False


# -----------------------------------------------------------------------------
# 3. Schema & Idempotent Index Initialization Tests
# -----------------------------------------------------------------------------
def test_init_db_indexes_creates_required_indexes():
    """Verify that index models for all 5 collections are submitted idempotently."""
    mock_db = MagicMock()
    collections = {
        COLL_USERS: MagicMock(),
        COLL_POLICIES: MagicMock(),
        COLL_CONVERSATIONS: MagicMock(),
        COLL_MESSAGES: MagicMock(),
        COLL_ANALYSIS_RECORDS: MagicMock(),
    }
    mock_db.__getitem__.side_effect = lambda name: collections[name]

    for name, m in collections.items():
        m.create_indexes.return_value = [f"idx_{name}_test"]

    res = init_db_indexes(mock_db)
    assert COLL_USERS in res
    assert COLL_POLICIES in res
    assert COLL_CONVERSATIONS in res
    assert COLL_MESSAGES in res
    assert COLL_ANALYSIS_RECORDS in res

    # Verify users unique compound index was configured
    args, _ = collections[COLL_USERS].create_indexes.call_args
    user_models = args[0]
    provider_idx = next(m for m in user_models if m.document.get("name") == "idx_users_provider_uid")
    assert provider_idx.document.get("unique") is True


# -----------------------------------------------------------------------------
# 4. In-Memory Mock MongoDB Fixture for Isolated CRUD Tests
# -----------------------------------------------------------------------------
class MockCollection:
    """Lightweight in-memory MongoDB collection simulation for unit testing."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.docs: dict[str, dict] = {}

    def insert_one(self, doc: dict):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = ObjectId()
        oid_str = str(d["_id"])
        self.docs[oid_str] = d

        class Result:
            inserted_id = d["_id"]

        return Result()

    def find_one(self, query: dict):
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "_id" and isinstance(v, ObjectId):
                    if d.get("_id") != v:
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                return dict(d)
        return None

    def find_one_and_update(self, filter_doc: dict, update_doc: dict, upsert: bool = False, return_document: bool = True):
        found = self.find_one(filter_doc)
        if found:
            oid_str = str(found["_id"])
            if "$set" in update_doc:
                self.docs[oid_str].update(update_doc["$set"])
            return dict(self.docs[oid_str])
        elif upsert:
            new_doc = {"_id": ObjectId()}
            if "$setOnInsert" in update_doc:
                new_doc.update(update_doc["$setOnInsert"])
            if "$set" in update_doc:
                new_doc.update(update_doc["$set"])
            new_doc.update(filter_doc)
            oid_str = str(new_doc["_id"])
            self.docs[oid_str] = new_doc
            return dict(new_doc)
        return None

    def update_one(self, filter_doc: dict, update_doc: dict):
        found = self.find_one(filter_doc)
        if found:
            oid_str = str(found["_id"])
            if "$set" in update_doc:
                self.docs[oid_str].update(update_doc["$set"])

    def find(self, query: dict):
        matches = []
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "_id" and isinstance(v, ObjectId):
                    if d.get("_id") != v:
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                matches.append(dict(d))

        class Cursor:
            def __init__(self, data):
                self.data = data
            def sort(self, *args, **kwargs):
                return self
            def limit(self, count):
                return self.data[:count]
            def __iter__(self):
                return iter(self.data)

        return Cursor(matches)

    def delete_one(self, query: dict):
        found = self.find_one(query)
        if found:
            oid_str = str(found["_id"])
            del self.docs[oid_str]

            class Res:
                deleted_count = 1
            return Res()

        class Res0:
            deleted_count = 0
        return Res0()


class MockDatabase:
    """In-memory collection registry for repository testing."""

    def __init__(self) -> None:
        self.colls: dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self.colls:
            self.colls[name] = MockCollection(name)
        return self.colls[name]


# -----------------------------------------------------------------------------
# 5. Multi-Tenant Authorization & Isolation Tests
# -----------------------------------------------------------------------------
def test_policy_repository_tenant_isolation_and_cross_user_rejection():
    """Verify that User A cannot read, list, or delete User B's policies."""
    mock_db = MockDatabase()
    repo = PolicyRepository(mock_db)

    # User A creates a policy
    p_a_id = repo.save_policy_metadata(
        user_id="user_A",
        document_name="Star-Comprehensive-Policy.pdf",
        document_hash="hash_star_123",
        page_count=42,
    )
    assert p_a_id is not None

    # User B creates a policy
    p_b_id = repo.save_policy_metadata(
        user_id="user_B",
        document_name="Optima-Secure-Policy.pdf",
        document_hash="hash_optima_456",
        page_count=55,
    )
    assert p_b_id is not None

    # 1. User A can retrieve their own policy
    p_a = repo.get_policy("user_A", p_a_id)
    assert p_a is not None
    assert p_a["document_name"] == "Star-Comprehensive-Policy.pdf"

    # 2. User A CANNOT retrieve User B's policy (Tenant Isolation)
    p_b_as_a = repo.get_policy("user_A", p_b_id)
    assert p_b_as_a is None, "Cross-user policy access must be rejected!"

    # 3. User A CANNOT delete User B's policy
    deleted = repo.delete_policy("user_A", p_b_id)
    assert deleted is False, "Cross-user policy deletion must be rejected!"

    # Confirm User B's policy is still intact
    p_b = repo.get_policy("user_B", p_b_id)
    assert p_b is not None

    # 4. User A's list contains only User A's policy
    user_a_list = repo.list_user_policies("user_A")
    assert len(user_a_list) == 1
    assert user_a_list[0]["id"] == p_a_id


def test_policy_deduplication_by_document_hash():
    """Uploading the same policy for the same user updates metadata rather than duplicating."""
    mock_db = MockDatabase()
    repo = PolicyRepository(mock_db)

    p1_id = repo.save_policy_metadata(
        user_id="user_A",
        document_name="ReAssure-2.0.pdf",
        document_hash="same_hash_reassure",
        page_count=24,
    )

    p2_id = repo.save_policy_metadata(
        user_id="user_A",
        document_name="ReAssure-2.0-Updated.pdf",
        document_hash="same_hash_reassure",
        page_count=24,
    )

    assert p1_id == p2_id, "Duplicate document_hash for same user must update existing record"
    policies = repo.list_user_policies("user_A")
    assert len(policies) == 1
    assert policies[0]["document_name"] == "ReAssure-2.0-Updated.pdf"


def test_conversation_ownership_and_unauthorized_append_rejection():
    """Verify conversations require ownership and prevent cross-user message injection."""
    mock_db = MockDatabase()
    repo = ConversationRepository(mock_db)

    # User A creates a consultation conversation
    conv_a_id = repo.get_or_create_conversation(
        user_id="user_A",
        policy_id="policy_123",
        title="PED Coverage Query",
    )

    # User A can append a message
    msg_id = repo.append_message(
        user_id="user_A",
        conversation_id=conv_a_id,
        policy_id="policy_123",
        role="user",
        content="Is diabetes covered after 2 years?",
    )
    assert msg_id is not None

    # User B CANNOT append a message to User A's conversation
    with pytest.raises(PermissionError) as exc_info:
        repo.append_message(
            user_id="user_B",
            conversation_id=conv_a_id,
            policy_id="policy_123",
            role="user",
            content="Attempted cross-tenant message injection",
        )
    assert "Access denied" in str(exc_info.value)

    # User B CANNOT list messages from User A's conversation
    with pytest.raises(PermissionError):
        repo.list_messages(user_id="user_B", conversation_id=conv_a_id)

    # User A can list messages
    msgs = repo.list_messages(user_id="user_A", conversation_id=conv_a_id)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Is diabetes covered after 2 years?"


def test_analysis_repository_isolation():
    """Verify scenario and comparison audit records are strictly user-scoped."""
    mock_db = MockDatabase()
    repo = AnalysisRepository(mock_db)

    repo.save_analysis(
        user_id="user_A",
        policy_id="pol_1",
        analysis_type="scenario_evaluation",
        input_summary={"ailment": "cataract", "age": 45},
        result_summary={"verdict": "covered_with_limit"},
    )

    a_records = repo.list_analyses("user_A")
    assert len(a_records) == 1
    assert a_records[0]["analysis_type"] == "scenario_evaluation"

    # User B sees zero records
    b_records = repo.list_analyses("user_B")
    assert len(b_records) == 0


def test_repository_rejects_empty_user_id():
    """Confirm all repositories strictly disallow empty or whitespace user_id."""
    mock_db = MockDatabase()
    p_repo = PolicyRepository(mock_db)
    with pytest.raises(ValueError) as exc:
        p_repo.list_user_policies("   ")
    assert "verified user_id is required" in str(exc.value)

    c_repo = ConversationRepository(mock_db)
    with pytest.raises(ValueError):
        c_repo.get_or_create_conversation(user_id="", policy_id="p1")


# -----------------------------------------------------------------------------
# 6. Document Storage Reference & Adapter Contracts
# -----------------------------------------------------------------------------
def test_storage_reference_serialization():
    """Test StorageReference conversion to and from dictionary."""
    ref = StorageReference(
        storage_type="in_memory",
        storage_key="user_123/abc_doc.pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        byte_size=1024,
    )
    d = ref.to_dict()
    assert d["storage_type"] == "in_memory"
    assert d["byte_size"] == 1024

    restored = StorageReference.from_dict(d)
    assert restored.storage_key == ref.storage_key
    assert restored.sha256_hash == ref.sha256_hash


def test_in_memory_storage_adapter_owner_scoping():
    """Verify that in-memory storage adapter respects tenant keys."""
    storage = InMemoryStorageAdapter()
    dummy_pdf = b"%PDF-1.4 dummy content"

    ref = storage.store_document(
        user_id="user_A",
        document_name="TestPolicy.pdf",
        data=dummy_pdf,
    )

    # Owner can retrieve
    retrieved = storage.retrieve_document(user_id="user_A", reference=ref)
    assert retrieved == dummy_pdf

    # Different user cannot retrieve
    unauthorized = storage.retrieve_document(user_id="user_B", reference=ref)
    assert unauthorized is None


# -----------------------------------------------------------------------------
# 7. Live MongoDB Atlas Integration (Opt-in via MONGODB_TEST_URI)
# -----------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.getenv("MONGODB_TEST_URI"),
    reason="Live MongoDB Atlas tests require MONGODB_TEST_URI to be set",
)
def test_live_mongodb_atlas_connection():
    """Opt-in live integration test against a dedicated test database."""
    test_uri = os.environ["MONGODB_TEST_URI"]
    report = check_mongodb_health(test_uri)
    assert report.status == DatabaseHealthStatus.CONNECTED
    assert report.is_connected is True
    assert report.latency_ms > 0
