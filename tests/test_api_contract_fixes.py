"""Regression tests for the cross-layer contract and isolation defects.

Each test targets a failure mode that the original suite did not cover:
1. Mongo policy ids must resolve to the cached processed policy.
2. Cached uploads must be owner-scoped.
3. Manual-review flags must survive the API boundary.
4. Frontend-facing field names must match the API.
5. Offline registration must produce a working login.
6. Repository methods must tolerate fingerprint (non-ObjectId) ids.
7. Health checks must not orphan Mongo clients.
8. Retrieval stop words must be removed before plural normalization.
"""
from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.deps import cache_processed_policy, create_access_token
from backend.database.repositories import AnalysisRepository, ConversationRepository, PolicyRepository
from backend.main import app
from backend.qa.retrieval import extract_query_terms
from backend.qa.workflow import prepare_policy
from backend.services.auth_service import AuthService, AuthUser
import backend.api.comparison as comparison_module
import backend.api.policies as policies_module
import backend.api.qa as qa_module
import backend.database.client as db_client_module
import backend.llm.groq_client as groq_module

client = TestClient(app)


def make_pdf_bytes(text: str) -> bytes:
    """Generate a valid single-page text PDF."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 700), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def auth_headers(user_id: str = "contract_test_user") -> dict[str, str]:
    user = AuthUser(
        user_id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
    )
    return {"Authorization": f"Bearer {create_access_token(user)}"}


# -----------------------------------------------------------------------------
# 1. Policy cache identity and ownership
# -----------------------------------------------------------------------------
def test_policy_cache_resolves_mongo_alias_and_enforces_owner():
    policy = SimpleNamespace(fingerprint="fp_contract_cache_001")
    try:
        deps.cache_processed_policy(
            policy,
            user_id="contract_owner",
            alias="64b000000000000000000001",
        )

        assert deps.get_cached_policy("64b000000000000000000001", "contract_owner") is policy
        assert deps.get_cached_policy("fp_contract_cache_001", "contract_owner") is policy
        assert deps.get_cached_policy("64b000000000000000000001", "contract_intruder") is None
        assert policy not in deps.get_all_cached_policies("contract_intruder")

        assert deps.remove_cached_policy("64b000000000000000000001", "contract_intruder") is False
        assert deps.remove_cached_policy("64b000000000000000000001", "contract_owner") is True
        assert deps.get_cached_policy("64b000000000000000000001", "contract_owner") is None
    finally:
        deps.remove_cached_policy("64b000000000000000000001", "contract_owner")


class _FakePolicyRepository:
    """Minimal repository stub that returns a Mongo ObjectId string."""

    def __init__(self, db) -> None:
        self.db = db

    def save_policy_file(self, **kwargs) -> str:
        return "64b000000000000000000003"

    def get_policy_file(self, *args, **kwargs):
        return None

    def delete_policy_file(self, *args, **kwargs) -> bool:
        return False

    def save_policy_metadata(self, **kwargs) -> str:
        return "64b000000000000000000002"

    def list_user_policies(self, user_id: str, limit: int = 50):
        return []

    def get_policy(self, user_id: str, policy_id: str):
        return None

    def get_policy_by_hash(self, user_id: str, document_hash: str):
        return None

    def delete_policy(self, user_id: str, policy_id: str) -> bool:
        return False

    def delete_policy_by_hash(self, user_id: str, document_hash: str) -> bool:
        return False


def test_upload_mongo_id_resolves_and_is_not_visible_to_other_users(monkeypatch):
    """Reproduce the original upload bug: API returned an id the cache could not resolve."""
    monkeypatch.setattr(policies_module, "get_database", lambda: object())
    monkeypatch.setattr(policies_module, "PolicyRepository", _FakePolicyRepository)

    owner_headers = auth_headers("contract_alias_owner")
    other_headers = auth_headers("contract_alias_other")
    uploaded_name = "Alias-Upload-Contract-Test.pdf"
    pdf = make_pdf_bytes(
        "Cancer treatment is covered up to the sum insured. "
        "Room rent is capped at one percent of the sum insured per day."
    )

    try:
        res = client.post(
            "/api/v1/policies/upload",
            files={"file": (uploaded_name, pdf, "application/pdf")},
            headers=owner_headers,
        )
        assert res.status_code == 200
        policy_id = res.json()["id"]
        assert policy_id == "64b000000000000000000002"

        # The returned Mongo id must resolve for page/fact/Q&A lookups.
        page = client.get(
            f"/api/v1/policies/{policy_id}/pages/1", headers=owner_headers
        )
        assert page.status_code == 200
        assert "Cancer treatment" in page.json()["text"]

        # A different authenticated user must not resolve the same cached id.
        blocked = client.get(
            f"/api/v1/policies/{policy_id}/pages/1", headers=other_headers
        )
        assert blocked.status_code == 404

        listed = client.get("/api/v1/policies", headers=other_headers)
        assert listed.status_code == 200
        assert all(
            item.get("document_name") != uploaded_name
            for item in listed.json()["policies"]
        )
    finally:
        deps.remove_cached_policy("64b000000000000000000002", "contract_alias_owner")


# -----------------------------------------------------------------------------
# 2. Q&A manual-review contract
# -----------------------------------------------------------------------------
def test_qa_response_surfaces_manual_review_for_unverified_citation(monkeypatch):
    policy = prepare_policy(
        make_pdf_bytes("Cancer treatment is covered up to the sum insured."),
        "Manual-Review-Contract-Test.pdf",
    )
    cache_processed_policy(policy, user_id="contract_qa_owner")
    monkeypatch.setattr(qa_module, "get_database", lambda: None)

    payload = {
        "verdict": "covered",
        "answer": "Cancer is covered.",
        "citations": [
            {
                "chunk_id": "NOT-A-REAL-CHUNK",
                "quote": "this quotation does not exist anywhere in the policy",
            }
        ],
        "confidence": "high",
        "caveats": [],
    }

    class FakeGroqClient:
        def __init__(self, **kwargs):
            pass

        def complete_json(self, *, system_prompt, user_prompt, schema=None):
            return payload

    monkeypatch.setattr(groq_module, "GroqClient", FakeGroqClient)

    try:
        res = client.post(
            "/api/v1/qa/ask",
            json={"policy_id": policy.fingerprint, "question": "Is cancer covered?"},
            headers=auth_headers("contract_qa_owner"),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["manual_review_required"] is True
        assert data["citations_valid"] is False
        assert data["verdict"] == "depends"
        assert data["confidence"] == "low"
        assert data["warnings"]
        assert data["unverified_answer"] == "Cancer is covered."
    finally:
        deps.remove_cached_policy(policy.fingerprint, "contract_qa_owner")


# -----------------------------------------------------------------------------
# 3. Frontend/API field contracts
# -----------------------------------------------------------------------------
def test_page_and_fact_responses_use_frontend_field_names(monkeypatch):
    policy = prepare_policy(
        make_pdf_bytes("Cataract treatment is subject to a sub-limit of Rs. 40,000."),
        "Field-Contract-Test.pdf",
    )
    cache_processed_policy(policy)
    monkeypatch.setattr(policies_module, "get_database", lambda: None)

    page = client.get(
        f"/api/v1/policies/{policy.fingerprint}/pages/1",
        headers=auth_headers("contract_fields"),
    )
    assert page.status_code == 200
    page_data = page.json()
    assert "char_count" in page_data
    assert "character_count" not in page_data

    facts = client.get(
        f"/api/v1/policies/{policy.fingerprint}/facts",
        headers=auth_headers("contract_fields"),
    )
    assert facts.status_code == 200
    facts_data = facts.json()
    assert facts_data["total_facts"] == len(facts_data["facts"])


def test_comparison_response_matches_frontend_contract(monkeypatch):
    policy_a = prepare_policy(
        make_pdf_bytes("Room rent is capped at one percent of the sum insured."),
        "Comparison-Contract-A.pdf",
    )
    policy_b = prepare_policy(
        make_pdf_bytes("Room rent is capped at two percent of the sum insured."),
        "Comparison-Contract-B.pdf",
    )
    cache_processed_policy(policy_a)
    cache_processed_policy(policy_b)
    monkeypatch.setattr(comparison_module, "get_database", lambda: None)

    res = client.post(
        "/api/v1/comparison/compare",
        json={
            "policy_id_a": policy_a.fingerprint,
            "policy_id_b": policy_b.fingerprint,
            "continuous_months": 24,
            "member_age": 45,
        },
        headers=auth_headers("contract_compare"),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["policy_a_name"] == "Comparison-Contract-A.pdf"
    assert data["policy_b_name"] == "Comparison-Contract-B.pdf"
    assert isinstance(data["dimensions"], list)
    assert isinstance(data["gaps"], list)
    assert "protection_gaps" not in data
    assert "overall_verdict" not in data


def test_unknown_policy_detail_returns_404(monkeypatch):
    monkeypatch.setattr(policies_module, "get_database", lambda: None)
    res = client.get(
        "/api/v1/policies/definitely-not-a-real-policy",
        headers=auth_headers("contract_missing"),
    )
    assert res.status_code == 404


# -----------------------------------------------------------------------------
# 4. Authentication behaviour in offline mode
# -----------------------------------------------------------------------------
def test_offline_registration_can_be_used_to_log_in(monkeypatch):
    monkeypatch.setattr(db_client_module, "get_database", lambda *a, **k: None)
    service = AuthService()

    registration = service.register(
        "offline.contract@example.com", "SecurePass123!", "Offline Contract"
    )
    assert registration.success is True

    login = service.authenticate("offline.contract@example.com", "SecurePass123!")
    assert login.success is True
    assert login.user is not None
    assert login.user.email == "offline.contract@example.com"

    wrong = service.authenticate("offline.contract@example.com", "WrongPass123!")
    assert wrong.success is False


def test_builtin_admin_credentials_are_not_accepted(monkeypatch):
    monkeypatch.delenv("COVERSCOPE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COVERSCOPE_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(db_client_module, "get_database", lambda *a, **k: None)

    result = AuthService().authenticate(
        "admin@coverscope.internal", "Admin@CoverScope2026!"
    )
    assert result.success is False


# -----------------------------------------------------------------------------
# 5. Repository behaviour
# -----------------------------------------------------------------------------
def test_repository_tolerates_fingerprint_ids():
    db = MagicMock()
    coll = MagicMock()
    db.__getitem__.return_value = coll
    repo = PolicyRepository(db)

    coll.find_one.return_value = None
    assert repo.get_policy("user_a", "not-an-object-id") is None

    coll.delete_one.return_value.deleted_count = 0
    assert repo.delete_policy("user_a", "not-an-object-id") is False


def test_conversation_repository_lists_user_conversations():
    db = MagicMock()
    coll = MagicMock()
    db.__getitem__.return_value = coll
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = [
        {"_id": ObjectId(), "user_id": "user_a", "policy_id": "policy_1"}
    ]
    coll.find.return_value = cursor

    repo = ConversationRepository(db)
    conversations = repo.list_user_conversations("user_a", "policy_1", limit=5)

    assert len(conversations) == 1
    assert conversations[0]["id"]
    coll.find.assert_called_once_with({"user_id": "user_a", "policy_id": "policy_1"})


# -----------------------------------------------------------------------------
# 6. Mongo client lifecycle and retrieval stop words
# -----------------------------------------------------------------------------
def test_force_reconnect_closes_previous_client(monkeypatch):
    old_client = MagicMock()
    new_client = MagicMock()
    monkeypatch.setattr(db_client_module, "_CLIENT_INSTANCE", old_client)
    monkeypatch.setattr(db_client_module, "_CLIENT_URI", "mongodb://old")
    monkeypatch.setattr(
        db_client_module, "MongoClient", lambda *args, **kwargs: new_client
    )

    result = db_client_module.get_mongodb_client(
        "mongodb://new", force_reconnect=True
    )
    assert result is new_client
    old_client.close.assert_called_once()


def test_stop_words_are_removed_before_plural_normalization():
    terms = extract_query_terms("Does the policy cover diabetes?")
    assert "doe" not in terms
    assert "ha" not in terms
    assert "policy" in terms
    assert "cover" in terms

    has_terms = extract_query_terms("Has the policy paid?")
    assert "ha" not in has_terms
    assert "policy" in has_terms


def test_uploaded_policy_survives_cache_clear_and_server_restart():
    """Verify that an uploaded policy survives in-memory cache eviction and process restart."""
    import uuid
    user = AuthUser(
        user_id=f"usr_restart_{uuid.uuid4().hex[:8]}",
        email="restart.test@hospital.org",
        display_name="Restart Tester",
        role="policyholder",
    )
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    pdf_bytes = make_pdf_bytes(
        "SECTION 1: RESTART DURABILITY TEST POLICY\n"
        "This policy covers hospital surgical procedures up to Sum Insured of Rs 500,000.\n"
        "Specific diseases waiting period of 24 months shall apply for listed conditions."
    )

    # 1. Upload policy
    up_res = client.post(
        "/api/v1/policies/upload",
        files={"file": ("Restart-Durability-Policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert up_res.status_code == 200, up_res.text
    pol_id = up_res.json()["id"]

    # 2. Simulate complete server process restart by wiping in-memory caches
    deps._POLICY_MEMORY_CACHE.clear()
    deps._POLICY_ALIASES.clear()
    deps._POLICY_OWNERS.clear()

    # 3. Request library policies: the uploaded policy must be present
    list_res = client.get("/api/v1/policies", headers=headers)
    assert list_res.status_code == 200
    policies = list_res.json()["policies"]
    assert any(pol_id == p["id"] or p["document_name"] == "Restart-Durability-Policy.pdf" for p in policies)

    # 4. Request facts using the original policy_id: must restore from disk/db without 404
    facts_res = client.get(f"/api/v1/policies/{pol_id}/facts", headers=headers)
    assert facts_res.status_code == 200, facts_res.text
    assert facts_res.json()["total_facts"] >= 1

    # 5. Request page 1 text: must restore and succeed
    page_res = client.get(f"/api/v1/policies/{pol_id}/pages/1", headers=headers)
    assert page_res.status_code == 200
    assert "RESTART DURABILITY TEST" in page_res.json()["text"]


def test_gridfs_storage_and_zero_local_disk_exposure():
    """Verify uploaded documents are stored in MongoDB GridFS and never on local disk."""
    import uuid
    from pathlib import Path

    user_uid = f"usr_gridfs_{uuid.uuid4().hex[:8]}"
    user = AuthUser(
        user_id=user_uid,
        email="gridfs.tester@hospital.org",
        display_name="GridFS Tester",
        role="policyholder",
    )
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    secret_marker = f"CONFIDENTIAL_GRIDFS_TOKEN_{uuid.uuid4().hex}"
    pdf_bytes = make_pdf_bytes(
        f"SECTION 1: GRIDFS ZERO DISK EXPOSURE TEST\n"
        f"Identifier: {secret_marker}\n"
        "Coverage includes emergency care up to Sum Insured of Rs 1,000,000.\n"
        "Specific diseases waiting period of 24 months shall apply."
    )

    # 1. Upload policy via API
    up_res = client.post(
        "/api/v1/policies/upload",
        files={"file": ("GridFS-Security-Policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert up_res.status_code == 200, up_res.text
    pol_id = up_res.json()["id"]
    doc_hash = up_res.json()["document_hash"]

    # 2. Strict verification: NO file should exist on local disk under data/uploads for this user
    user_upload_dir = Path("data/uploads") / user_uid
    assert not user_upload_dir.exists() or len(list(user_upload_dir.glob("*.pdf"))) == 0, (
        f"Security violation: raw PDF file was written to local disk at {user_upload_dir}"
    )

    # 3. Verify file exists in MongoDB GridFS
    from backend.database.client import get_database
    db = get_database()
    if db is not None:
        repo = PolicyRepository(db)
        grid_data = repo.get_policy_file(user_uid, pol_id)
        assert grid_data is not None, "Policy was not stored in MongoDB GridFS"
        retrieved_bytes, ret_filename = grid_data
        assert len(retrieved_bytes) == len(pdf_bytes)
        assert ret_filename == "GridFS-Security-Policy.pdf"
        import pymupdf
        test_doc = pymupdf.open(stream=retrieved_bytes, filetype="pdf")
        assert secret_marker in test_doc[0].get_text()
        test_doc.close()

    # 4. Wipe in-memory caches to simulate server restart / cache clear
    deps._POLICY_MEMORY_CACHE.clear()
    deps._POLICY_ALIASES.clear()
    deps._POLICY_OWNERS.clear()

    # 5. Fetch facts via API: must resolve and restore directly from GridFS into memory
    facts_res = client.get(f"/api/v1/policies/{pol_id}/facts", headers=headers)
    assert facts_res.status_code == 200, facts_res.text
    assert facts_res.json()["total_facts"] >= 1

    # 6. Fetch page 1 text: must restore and succeed
    page_res = client.get(f"/api/v1/policies/{pol_id}/pages/1", headers=headers)
    assert page_res.status_code == 200
    assert secret_marker in page_res.json()["text"]

    # 7. Delete policy: must remove from memory, metadata collection, and GridFS
    del_res = client.delete(f"/api/v1/policies/{pol_id}", headers=headers)
    assert del_res.status_code == 200

    if db is not None:
        repo = PolicyRepository(db)
        assert repo.get_policy_file(user_uid, pol_id) is None
        assert repo.get_policy_file(user_uid, doc_hash) is None


def test_chat_history_and_analysis_audit_linkage_with_dual_ids():
    """Verify conversations and analyses can be retrieved using either Mongo ID or fingerprint, and cascade delete."""
    import uuid
    user_uid = f"usr_dual_{uuid.uuid4().hex[:8]}"
    user = AuthUser(
        user_id=user_uid,
        email="dual.test@hospital.org",
        display_name="Dual Tester",
        role="policyholder",
    )
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    pdf_bytes = make_pdf_bytes("Comprehensive care is covered up to Sum Insured Rs 500,000. 30 days initial waiting period applies.")
    up_res = client.post(
        "/api/v1/policies/upload",
        files={"file": ("Dual-ID-Test-Policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert up_res.status_code == 200
    mongo_id = up_res.json()["id"]
    doc_hash = up_res.json()["document_hash"]

    from backend.database.client import get_database
    db = get_database()
    if db is not None:
        c_repo = ConversationRepository(db)
        conv_id = c_repo.get_or_create_conversation(user_id=user_uid, policy_id=doc_hash, title="Test Chat")
        c_repo.append_message(user_id=user_uid, conversation_id=conv_id, policy_id=doc_hash, role="user", content="What is covered?")
        c_repo.append_message(user_id=user_uid, conversation_id=conv_id, policy_id=doc_hash, role="assistant", content="Comprehensive care is covered.", evidence_metadata={"verdict": "covered", "confidence": "high"})

        # Retrieve history using mongo_id
        hist_res = client.get(f"/api/v1/qa/history/{mongo_id}", headers=headers)
        assert hist_res.status_code == 200
        msgs = hist_res.json()["messages"]
        assert len(msgs) == 2

        # Save analysis under mongo_id and retrieve using doc_hash
        a_repo = AnalysisRepository(db)
        a_repo.save_analysis(
            user_id=user_uid,
            policy_id=mongo_id,
            analysis_type="scenario_evaluation",
            input_summary={"ailment": "fever"},
            result_summary={"verdict": "covered"},
        )
        analyses = a_repo.list_analyses(user_id=user_uid, policy_id=doc_hash)
        assert len(analyses) == 1

        # Delete policy
        del_res = client.delete(f"/api/v1/policies/{mongo_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify cascading deletion of conversation and analysis
        assert len(c_repo.list_user_conversations(user_uid, doc_hash)) == 0
        assert len(c_repo.list_user_conversations(user_uid, mongo_id)) == 0
        assert len(a_repo.list_analyses(user_uid, doc_hash)) == 0


def test_groq_client_handles_markdown_codeblock_and_preamble_json():
    """Verify GroqClient complete_json strips markdown code blocks and preamble text."""
    from backend.llm.groq_client import GroqClient
    from unittest.mock import MagicMock

    raw_markdown_response = (
        "Here is your answer in JSON format:\n\n"
        "```json\n"
        "{\n"
        '  "verdict": "covered",\n'
        '  "answer": "Treatment is covered under Section 2.",\n'
        '  "citations": [],\n'
        '  "confidence": "high",\n'
        '  "caveats": []\n'
        "}\n"
        "```\n\nHope this helps!"
    )
    fake_sdk = MagicMock()
    fake_choice = MagicMock()
    fake_choice.message.content = raw_markdown_response
    fake_sdk.chat.completions.create.return_value = MagicMock(choices=[fake_choice])

    client_llm = GroqClient(api_key="gsk_test_mock_key", sdk_client=fake_sdk)
    parsed = client_llm.complete_json(system_prompt="sys", user_prompt="user")
    assert parsed["verdict"] == "covered"
    assert parsed["confidence"] == "high"


def test_coordinate_exclusion_and_colon_list_extraction():
    """Verify coordinate exclusions ('X and Y are excluded') and colon lists extract all items."""
    from backend.domain.adapter import extract_candidate_facts
    from backend.domain.enums import FactCategory

    text_coords = "Exclusion terms: Alcoholism and substance abuse are excluded under this policy."
    policy_coords = prepare_policy(make_pdf_bytes(text_coords), "Coord-Exclusion.pdf")
    facts_coords = extract_candidate_facts(policy_coords)
    excl_props = [f.proposition.lower() for f in facts_coords if f.category == FactCategory.EXCLUSION]
    assert any("alcoholism" in p for p in excl_props)
    assert any("substance abuse" in p for p in excl_props)

    text_list = "The following are excluded: hazardous sports, cosmetic surgery, and rest cure."
    policy_list = prepare_policy(make_pdf_bytes(text_list), "List-Exclusion.pdf")
    facts_list = extract_candidate_facts(policy_list)
    list_props = [f.proposition.lower() for f in facts_list if f.category == FactCategory.EXCLUSION]
    assert any("hazardous sports" in p for p in list_props)
    assert any("cosmetic surgery" in p for p in list_props)
    assert any("rest cure" in p for p in list_props)


def test_claim_rehearsal_sublimit_and_dynamic_facts():
    """Verify claim rehearsal recognizes procedure sublimits and dynamic waiting periods from facts."""
    from backend.services.claim_rehearsal_service import evaluate_claim_rehearsal
    from backend.api.schemas import ClaimRehearsalRequest

    policy_text = (
        "Cataract surgery is subject to a specific sub-limit of Rs. 40,000 per eye. "
        "A specified disease waiting period of 12 months applies to cataract treatment."
    )
    policy = prepare_policy(make_pdf_bytes(policy_text), "Cataract-Sublimit.pdf")
    rehearsal_req = ClaimRehearsalRequest(
        policy_id=policy.fingerprint,
        treatment_description="Cataract surgery in left eye",
        estimated_expense=65000.0,
        policy_duration_months=18,
        member_age=55,
    )
    resp = evaluate_claim_rehearsal(policy, rehearsal_req)
    assert resp.financial_breakdown is not None
    # Sub-limit of 40,000 caps the payable amount; excess 25,000 is out-of-pocket
    assert any("40,000" in note for note in resp.financial_breakdown.calculation_notes)
    # 18 months duration satisfies the 12-month waiting period from the policy
    wp_cond = next((c for c in resp.relevant_conditions if "specific" in c["category"].lower()), None)
    assert wp_cond is not None
    assert wp_cond["status"] == "satisfied"
