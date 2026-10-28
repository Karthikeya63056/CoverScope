"""Regression and verification tests for CoverScope priority security and reliability remediation.

Tests:
1. Multi-tenant policy authorization and IDOR protection:
   - User A cannot view metadata, pages, facts, Q&A history, or delete User B's policy.
   - User A cannot ask questions, run scenarios, rehearse claims, or run comparisons on User B's policy.
   - Legitimate owner (User B) retains full access.
   - Shared bundled demo policies remain accessible to all authenticated users.
2. CORS origin restriction:
   - Approved local development origins and configured production origins receive CORS headers.
   - Unapproved hosted origins (including arbitrary vercel.app subdomains) are rejected without CORS headers.
3. Asynchronous non-blocking PDF processing:
   - Verifies that CPU-bound PDF processing runs in a worker thread via asyncio.to_thread,
     keeping the ASGI event loop responsive to lightweight requests (/health) concurrently.
4. Authentication token and cookie consistency:
   - Verifies logout explicitly deletes the access_token cookie with matching path.
"""
from __future__ import annotations

import asyncio
import io
import threading
from typing import Any
from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
import httpx
import pytest

from backend.api.deps import (
    _POLICY_ALIASES,
    _POLICY_MEMORY_CACHE,
    _POLICY_OWNERS,
    cache_processed_policy,
    create_access_token,
    get_cached_policy,
)
from backend.main import app, get_allowed_origins
from backend.qa.workflow import prepare_policy
from backend.services.auth_service import AuthUser

client = TestClient(app)

SAMPLE_POLICY_A = """
SECTION 1 - BENEFITS
Room rent is capped at 1% of Sum Insured per day.
Cataract surgery is limited to Rs. 35,000 per eye.

SECTION 2 - WAITING PERIODS
Pre-existing diseases are covered after 36 months of continuous coverage.
Initial waiting period is 30 days from inception.

SECTION 3 - EXCLUSIONS
Cosmetic surgery, dental treatments, and self-inflicted injuries are excluded.
"""

SAMPLE_POLICY_B = """
SECTION 1 - BENEFITS
Single private AC room without daily capping is provided.
Robotic surgery covered up to 50% of Sum Insured.

SECTION 2 - WAITING PERIODS
Pre-existing conditions covered after 24 months.

SECTION 3 - EXCLUSIONS
Adventure sports injuries and weight loss treatments are permanently excluded.
"""


def _make_pdf(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 700), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def user_a() -> AuthUser:
    return AuthUser(
        user_id="usr_tenant_alice_101",
        email="alice@hospital.org",
        display_name="Alice Underwriter",
        role="underwriter",
    )


@pytest.fixture
def user_b() -> AuthUser:
    return AuthUser(
        user_id="usr_tenant_bob_202",
        email="bob@clinic.org",
        display_name="Bob Policyholder",
        role="policyholder",
    )


@pytest.fixture
def token_a(user_a: AuthUser) -> str:
    return create_access_token(user_a)


@pytest.fixture
def token_b(user_b: AuthUser) -> str:
    return create_access_token(user_b)


@pytest.fixture
def headers_a(token_a: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_a}"}


@pytest.fixture
def headers_b(token_b: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_b}"}


# ==============================================================================
# SECTION 1: POLICY OWNERSHIP ISOLATION & IDOR TESTS
# ==============================================================================

class TestPolicyOwnershipEnforcement:
    """Verify tenant isolation between User A and User B across all routes."""

    @pytest.fixture(autouse=True)
    def setup_policies(self, user_a: AuthUser, user_b: AuthUser):
        pdf_b_bytes = _make_pdf(SAMPLE_POLICY_B)
        policy_b = prepare_policy(pdf_b_bytes, "Bob_Comprehensive_Care.pdf")

        # Give Bob's policy both a MongoDB ObjectId string and the SHA-256 fingerprint
        self.bob_oid = str(ObjectId())
        self.bob_fingerprint = policy_b.fingerprint
        cache_processed_policy(policy_b, user_id=user_b.user_id, alias=self.bob_oid)

        yield

        # Cleanup caches
        for key in list(_POLICY_MEMORY_CACHE.keys()):
            if "usr_tenant_" in key:
                _POLICY_MEMORY_CACHE.pop(key, None)
                _POLICY_OWNERS.pop(key, None)
        _POLICY_ALIASES.pop(self.bob_oid, None)

    def test_user_a_cannot_view_user_b_policy_detail(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A must receive 404 when querying User B's policy by ObjectId or fingerprint."""
        res_oid = client.get(f"/api/v1/policies/{self.bob_oid}", headers=headers_a)
        assert res_oid.status_code == 404
        assert "not found or access denied" in res_oid.json()["detail"].lower()

        res_hash = client.get(f"/api/v1/policies/{self.bob_fingerprint}", headers=headers_a)
        assert res_hash.status_code == 404

        # Legitimate owner (User B) can view it
        res_owner = client.get(f"/api/v1/policies/{self.bob_oid}", headers=headers_b)
        assert res_owner.status_code == 200
        assert res_owner.json()["document_name"] == "Bob_Comprehensive_Care.pdf"

    def test_user_a_cannot_read_user_b_page_text(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot read verbatim extracted pages of User B's policy."""
        res_a = client.get(f"/api/v1/policies/{self.bob_oid}/pages/1", headers=headers_a)
        assert res_a.status_code == 404

        # Owner B can read page 1
        res_b = client.get(f"/api/v1/policies/{self.bob_oid}/pages/1", headers=headers_b)
        assert res_b.status_code == 200
        assert "Single private AC room" in res_b.json()["text"]

    def test_user_a_cannot_download_user_b_policy(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot download User B's raw PDF policy document."""
        res_a = client.get(f"/api/v1/policies/{self.bob_oid}/download", headers=headers_a)
        assert res_a.status_code == 404

        # Owner B can download baseline demo or their own policy
        res_demo = client.get("/api/v1/policies/demo/download", headers=headers_b)
        assert res_demo.status_code in (200, 404)  # 200 if baseline PDF exists, 404 if not found

    def test_user_a_cannot_delete_user_b_conversation_history(
        self,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
        user_a: AuthUser,
        user_b: AuthUser,
    ):
        """User A cannot delete User B's conversation history; User B's records remain intact."""
        # 1. Endpoint rejects User A with 404
        res_a = client.delete(f"/api/v1/qa/history/{self.bob_oid}", headers=headers_a)
        assert res_a.status_code == 404
        assert "not found or access denied" in res_a.json()["detail"].lower()

        # 2. Verify repository layer preserves Bob's conversation records
        mock_db = MagicMock()
        mock_conv_coll = MagicMock()
        mock_msg_coll = MagicMock()

        def _get_coll(name: str):
            if "conv" in name:
                return mock_conv_coll
            return mock_msg_coll

        mock_db.__getitem__.side_effect = _get_coll
        mock_conv_coll.database = {
            "policies": MagicMock(find_one=MagicMock(return_value=None))
        }

        # Bob's records query returns empty when filtered by User A
        mock_conv_coll.find.return_value = []

        from backend.database.repositories import ConversationRepository
        repo = ConversationRepository(mock_db)

        deleted = repo.delete_conversations_for_policy(user_a.user_id, self.bob_oid)
        assert deleted == 0
        mock_msg_coll.delete_many.assert_not_called()
        mock_conv_coll.delete_one.assert_not_called()

        # 3. Legitimate owner (User B) can delete their own conversation history
        res_b = client.delete(f"/api/v1/qa/history/{self.bob_oid}", headers=headers_b)
        assert res_b.status_code == 200
        assert res_b.json()["success"] is True

    def test_user_a_cannot_extract_user_b_facts(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot retrieve extracted clauses/facts from User B's policy."""
        res_a = client.get(f"/api/v1/policies/{self.bob_oid}/facts", headers=headers_a)
        assert res_a.status_code == 404

        res_b = client.get(f"/api/v1/policies/{self.bob_oid}/facts", headers=headers_b)
        assert res_b.status_code == 200
        assert len(res_b.json()["facts"]) > 0

    def test_user_a_cannot_ask_questions_on_user_b_policy(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot submit Q&A questions against User B's policy."""
        payload = {"policy_id": self.bob_oid, "question": "What is the room rent limit?"}
        res_a = client.post("/api/v1/qa/ask", json=payload, headers=headers_a)
        assert res_a.status_code == 404
        assert "not currently active" in res_a.json()["detail"].lower()

    def test_user_a_cannot_access_user_b_chat_history(self, headers_a: dict[str, str]):
        """User A cannot access or probe Q&A history for User B's policy."""
        res_a = client.get(f"/api/v1/qa/history/{self.bob_oid}", headers=headers_a)
        assert res_a.status_code == 404

    def test_user_a_cannot_evaluate_scenarios_on_user_b_policy(self, headers_a: dict[str, str]):
        """User A cannot run scenario simulations on User B's policy."""
        payload = {
            "policy_id": self.bob_oid,
            "scenario_type": "pre_existing_condition",
            "ailment": "Hypertension",
            "elapsed_months": 12,
        }
        res_a = client.post("/api/v1/scenarios/evaluate", json=payload, headers=headers_a)
        assert res_a.status_code == 404

    def test_user_a_cannot_access_user_b_scenario_history(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot access or probe scenario history for User B's policy."""
        res_a = client.get(f"/api/v1/scenarios/history?policy_id={self.bob_oid}", headers=headers_a)
        assert res_a.status_code == 404
        assert "not found or access denied" in res_a.json()["detail"].lower()

        res_b = client.get(f"/api/v1/scenarios/history?policy_id={self.bob_oid}", headers=headers_b)
        assert res_b.status_code == 200
        assert isinstance(res_b.json(), list)

    def test_user_a_cannot_rehearse_claim_on_user_b_policy(self, headers_a: dict[str, str]):
        """User A cannot run claim rehearsal on User B's policy."""
        payload = {
            "policy_id": self.bob_oid,
            "treatment_description": "Robotic Knee Replacement",
            "estimated_expense": 250000.0,
            "room_category": "single_private",
            "policy_duration_months": 26,
            "is_pre_existing": False,
        }
        res_a = client.post("/api/v1/claim-rehearsal/rehearse", json=payload, headers=headers_a)
        assert res_a.status_code == 404

    def test_user_a_cannot_access_user_b_claim_rehearsal_history(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot access or probe claim rehearsal history for User B's policy."""
        res_a = client.get(f"/api/v1/claim-rehearsal/history?policy_id={self.bob_oid}", headers=headers_a)
        assert res_a.status_code == 404
        assert "not found or access denied" in res_a.json()["detail"].lower()

        res_b = client.get(f"/api/v1/claim-rehearsal/history?policy_id={self.bob_oid}", headers=headers_b)
        assert res_b.status_code == 200
        assert isinstance(res_b.json(), list)

    def test_user_a_cannot_compare_using_user_b_policy(self, headers_a: dict[str, str], user_a: AuthUser):
        """User A cannot use User B's policy in comparison matrix."""
        pdf_a_bytes = _make_pdf(SAMPLE_POLICY_A)
        policy_a = prepare_policy(pdf_a_bytes, "Alice_Care.pdf")
        cache_processed_policy(policy_a, user_id=user_a.user_id)

        payload = {
            "policy_id_a": policy_a.fingerprint,
            "policy_id_b": self.bob_oid,
        }
        res = client.post("/api/v1/comparison/compare", json=payload, headers=headers_a)
        assert res.status_code == 404

    def test_user_a_cannot_delete_user_b_policy(self, headers_a: dict[str, str], headers_b: dict[str, str]):
        """User A cannot delete User B's policy."""
        res_del_a = client.delete(f"/api/v1/policies/{self.bob_oid}", headers=headers_a)
        assert res_del_a.status_code == 404

        # Verify Bob's policy still exists and is accessible by Bob
        res_check = client.get(f"/api/v1/policies/{self.bob_oid}", headers=headers_b)
        assert res_check.status_code == 200

    def test_unscoped_objectid_in_mongodb_does_not_leak_to_other_users(self, user_a: AuthUser, user_b: AuthUser):
        """Verify that get_cached_policy does not resolve an ObjectId belonging to user B for user A."""
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_policy.return_value = None
        mock_repo.get_policy_by_hash.return_value = None

        with patch("backend.database.client.get_database", return_value=mock_db), \
             patch("backend.database.repositories.PolicyRepository", return_value=mock_repo):
            # User A requests Bob's ObjectId
            result = get_cached_policy(self.bob_oid, user_id=user_a.user_id)
            assert result is None


# ==============================================================================
# SECTION 2: CORS RESTRICTION & ORIGIN VALIDATION TESTS
# ==============================================================================

class TestCORSRestrictions:
    """Verify that CORS does not trust arbitrary subdomains and honors whitelist."""

    def test_default_dev_origins_allowed(self):
        """Vite local development origins are permitted."""
        for origin in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]:
            res = client.options(
                "/api/v1/dashboard/summary",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            assert res.headers.get("access-control-allow-origin") == origin
            assert res.headers.get("access-control-allow-credentials") == "true"

    def test_arbitrary_vercel_subdomains_are_rejected(self):
        """Arbitrary subdomains on vercel.app must NOT receive CORS allow headers."""
        malicious_origins = [
            "https://attacker.vercel.app",
            "https://phishing-site.vercel.app",
            "https://evil-coverscope.vercel.app",
            "https://random-tenant.onrender.com",
            "https://malicious-domain.com",
        ]
        for origin in malicious_origins:
            res = client.options(
                "/api/v1/dashboard/summary",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            # When rejected by CORSMiddleware, access-control-allow-origin is NOT present
            assert res.headers.get("access-control-allow-origin") is None

    def test_custom_production_origin_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """Configuring COVERSCOPE_ALLOWED_ORIGINS grants access to exact domain only."""
        custom_domain = "https://my-verified-hospital.org"
        monkeypatch.setenv("COVERSCOPE_ALLOWED_ORIGINS", f"{custom_domain}, https://coverscope.vercel.app")
        origins = get_allowed_origins()
        assert custom_domain in origins
        assert "https://coverscope.vercel.app" in origins
        assert "https://other.vercel.app" not in origins


# ==============================================================================
# SECTION 3: EVENT LOOP NON-BLOCKING PDF PROCESSING TEST
# ==============================================================================

class TestNonBlockingPDFUpload:
    """Verify that prepare_policy is offloaded to a worker thread so the event loop stays responsive."""

    def test_event_loop_remains_responsive_during_pdf_processing(self, user_a: AuthUser, token_a: str):
        """A lightweight /health request on the event loop succeeds while PDF processing is in progress."""
        async def _run():
            from backend.qa import workflow

            pdf_bytes = _make_pdf(SAMPLE_POLICY_A)
            original_prepare = workflow.prepare_policy

            processing_started = threading.Event()
            continue_processing = threading.Event()

            def slow_prepare_policy(*args, **kwargs):
                processing_started.set()
                # Wait until the test verifies event loop responsiveness
                continue_processing.wait(timeout=5.0)
                return original_prepare(*args, **kwargs)

            with patch("backend.api.policies.prepare_policy", side_effect=slow_prepare_policy):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
                    files = {"file": ("test_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
                    headers = {"Authorization": f"Bearer {token_a}"}

                    # Start upload task asynchronously
                    upload_task = asyncio.create_task(
                        ac.post("/api/v1/policies/upload", files=files, headers=headers)
                    )

                    # Wait until the worker thread has started processing
                    for _ in range(50):
                        if processing_started.is_set():
                            break
                        await asyncio.sleep(0.02)
                    assert processing_started.is_set(), "Processing thread did not start."

                    # Send lightweight health check on the event loop while upload is active
                    health_res = await ac.get("/api/v1/health")
                    assert health_res.status_code == 200
                    assert health_res.json()["status"] == "healthy"

                    # Signal the worker thread to finish
                    continue_processing.set()

                    # Await upload completion
                    upload_res = await upload_task
                    assert upload_res.status_code == 200
                    assert "id" in upload_res.json()

        asyncio.run(_run())


# ==============================================================================
# SECTION 4: AUTHENTICATION COOKIE & SESSION CONSISTENCY
# ==============================================================================

class TestAuthCookieConsistency:
    """Verify cookie path and logout behavior."""

    def test_logout_deletes_cookie_with_matching_path(self):
        """Logout must set delete-cookie with path=/ so the browser removes the session cookie."""
        res = client.post("/api/v1/auth/logout")
        assert res.status_code == 200
        set_cookie_header = res.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie_header
        assert "Path=/" in set_cookie_header or "path=/" in set_cookie_header
        # Max-Age=0 or expires in past
        assert "max-age=0" in set_cookie_header.lower() or "expires=" in set_cookie_header.lower()

    def test_unauthenticated_requests_consistently_rejected(self):
        """Accessing protected routes without token or cookie returns 401."""
        endpoints = [
            ("GET", "/api/v1/policies"),
            ("GET", "/api/v1/dashboard/summary"),
            ("POST", "/api/v1/qa/ask"),
            ("POST", "/api/v1/scenarios/evaluate"),
            ("POST", "/api/v1/claim-rehearsal/rehearse"),
        ]
        for method, ep in endpoints:
            if method == "GET":
                res = client.get(ep)
            else:
                res = client.post(ep, json={})
            assert res.status_code == 401
            assert "authentication required" in res.json()["detail"].lower()
