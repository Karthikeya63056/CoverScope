"""Automated tests for CoverScope FastAPI REST API endpoints.

Covers:
1. Health and root endpoints.
2. Registration, login, profile, and JWT token validation.
3. Protected route access rejection when unauthenticated.
4. Policy upload and validation (PDF validation, size guards).
5. Document listing and detail endpoints.
6. Natural language Q&A with evidence grounding.
7. Deterministic scenario evaluation.
8. Dual policy comparison.
9. Dashboard summary aggregation.
"""
from __future__ import annotations

import io
from fastapi.testclient import TestClient
import pytest

from backend.api.deps import cache_processed_policy, create_access_token
from backend.main import app
from backend.qa.workflow import prepare_policy
from backend.services.auth_service import AuthUser

client = TestClient(app)


SAMPLE_PDF_TEXT = """
SECTION 1 - BENEFITS
The Company shall indemnify hospital room rent expenses up to 1% of Sum Insured per day.
Cataract treatment is subject to a specific sub-limit of Rs. 40,000 per eye.

SECTION 2 - WAITING PERIODS
A pre-existing disease (PED) shall be covered after thirty-six (36) months of continuous coverage.
A waiting period of 30 days shall apply to all illnesses from policy inception date.
Specified diseases listed in Annexure A shall be covered after twenty-four (24) months.

SECTION 3 - EXCLUSIONS
Treatment for alcoholism, drug abuse, and intentional self-injury is permanently excluded.
"""


def make_test_pdf_bytes(text: str = SAMPLE_PDF_TEXT) -> bytes:
    """Generate a valid single-page text-based PDF using PyMuPDF."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


@pytest.fixture
def auth_headers():
    """Generate valid authorization headers for a test user."""
    user = AuthUser(
        user_id="test_user_12345",
        email="developer@coverscope.internal",
        display_name="Developer User",
        role="policyholder",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_policy():
    """Create and cache a processed policy in memory."""
    pdf_bytes = make_test_pdf_bytes()
    policy = prepare_policy(pdf_bytes, "Sample-API-Policy.pdf")
    cache_processed_policy(policy)
    return policy


# -----------------------------------------------------------------------------
# 1. Health & Root Endpoints
# -----------------------------------------------------------------------------
def test_root_and_health_endpoints():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "healthy"
    assert "groq_model" in data
    assert "database" in data


# -----------------------------------------------------------------------------
# 2. Authentication & Authorization Enforcement
# -----------------------------------------------------------------------------
def test_protected_routes_reject_unauthenticated_requests():
    """Confirm API endpoints strictly require authentication."""
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401
    assert "Authentication required" in res_me.json()["detail"]

    res_dash = client.get("/api/v1/dashboard/summary")
    assert res_dash.status_code == 401

    res_policies = client.get("/api/v1/policies")
    assert res_policies.status_code == 401


def test_auth_me_with_valid_jwt(auth_headers):
    """Confirm /api/v1/auth/me returns the decoded authenticated user profile."""
    res = client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "test_user_12345"
    assert data["email"] == "developer@coverscope.internal"


def test_auth_registration_and_login_roundtrip():
    """Test full registration and login flow."""
    rand_email = "test.pilot@hospital.org"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": rand_email, "password": "SecurePassword2026!", "display_name": "Pilot User"},
    )
    # 200 on new user, or 409 if already registered
    assert reg_res.status_code in (200, 409)

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": rand_email, "password": "SecurePassword2026!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["success"] is True
    assert "token" in data
    assert data["user"]["email"] == rand_email


def test_login_with_invalid_password_returns_401():
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "developer@coverscope.internal", "password": "WrongPassword!"},
    )
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 3. Policy Ingestion & Management
# -----------------------------------------------------------------------------
def test_upload_policy_rejects_non_pdf(auth_headers):
    file_payload = {"file": ("malicious.exe", b"not a pdf", "application/octet-stream")}
    res = client.post("/api/v1/policies/upload", files=file_payload, headers=auth_headers)
    assert res.status_code == 400
    assert "Only PDF documents are supported" in res.json()["detail"]


def test_upload_valid_policy_pdf(auth_headers):
    pdf_bytes = make_test_pdf_bytes()
    file_payload = {"file": ("Uploaded-Test-Policy.pdf", pdf_bytes, "application/pdf")}
    res = client.post("/api/v1/policies/upload", files=file_payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["document_name"] == "Uploaded-Test-Policy.pdf"
    assert data["page_count"] >= 1
    assert "id" in data


def test_list_and_detail_policies(auth_headers, sample_policy):
    res_list = client.get("/api/v1/policies", headers=auth_headers)
    assert res_list.status_code == 200
    assert "policies" in res_list.json()

    res_detail = client.get(f"/api/v1/policies/{sample_policy.fingerprint}", headers=auth_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["document_name"] == sample_policy.filename
    assert detail["page_count"] == sample_policy.page_count


def test_page_text_endpoint(auth_headers, sample_policy):
    res = client.get(f"/api/v1/policies/{sample_policy.fingerprint}/pages/1", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["page_number"] == 1
    assert "BENEFITS" in data["text"]


def test_policy_facts_endpoint(auth_headers, sample_policy):
    res = client.get(f"/api/v1/policies/{sample_policy.fingerprint}/facts", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["policy_id"] == sample_policy.fingerprint
    assert isinstance(data["facts"], list)


# -----------------------------------------------------------------------------
# 4. Q&A and Evidence Grounding
# -----------------------------------------------------------------------------
def test_ask_question_with_mocked_groq(monkeypatch, auth_headers, sample_policy):
    """Test Q&A API returns verified citations and structured verdict."""
    payload = {
        "verdict": "excluded",
        "answer": "Alcoholism is permanently excluded under this policy.",
        "citations": [
            {
                "chunk_id": sample_policy.chunks[0].chunk_id,
                "quote": "Treatment for alcoholism, drug abuse, and intentional self-injury is permanently excluded.",
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

    import backend.llm.groq_client as groq_module
    monkeypatch.setattr(groq_module, "GroqClient", FakeGroqClient)

    req = {"policy_id": sample_policy.fingerprint, "question": "Is alcoholism covered?"}
    res = client.post("/api/v1/qa/ask", json=req, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "excluded"
    assert "alcoholism" in data["answer"].lower()
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["page_number"] == 1


# -----------------------------------------------------------------------------
# 5. Deterministic Scenario Analysis
# -----------------------------------------------------------------------------
def test_scenario_evaluate_api(auth_headers, sample_policy):
    req = {
        "policy_id": sample_policy.fingerprint,
        "ailment": "diabetes",
        "elapsed_months": 12,
        "member_age": 45,
    }
    res = client.post("/api/v1/scenarios/evaluate", json=req, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] in ("waiting_period_active", "insufficient_evidence")
    assert "headline" in data
    assert "explanation" in data


def test_scenario_history_api(auth_headers, sample_policy):
    # Unauthenticated rejected
    unauth_client = TestClient(app)
    res_unauth = unauth_client.get("/api/v1/scenarios/history")
    assert res_unauth.status_code == 401

    # Authenticated list
    res = client.get("/api/v1/scenarios/history", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Valid policy filter
    res_filter = client.get(
        f"/api/v1/scenarios/history?policy_id={sample_policy.fingerprint}",
        headers=auth_headers,
    )
    assert res_filter.status_code == 200
    assert isinstance(res_filter.json(), list)

    # Nonexistent policy filter
    res_404 = client.get(
        "/api/v1/scenarios/history?policy_id=nonexistent-policy-999",
        headers=auth_headers,
    )
    assert res_404.status_code == 404
    assert "not found or access denied" in res_404.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 6. Policy Comparison
# -----------------------------------------------------------------------------
def test_comparison_api(auth_headers, sample_policy):
    req = {
        "policy_id_a": sample_policy.fingerprint,
        "policy_id_b": sample_policy.fingerprint,
        "continuous_months": 24,
        "member_age": 45,
    }
    res = client.post("/api/v1/comparison/compare", json=req, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "dimensions" in data
    assert len(data["dimensions"]) >= 1


# -----------------------------------------------------------------------------
# 7. Dashboard Summary
# -----------------------------------------------------------------------------
def test_dashboard_summary_api(auth_headers):
    res = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_policies" in data
    assert "database_status" in data
    assert isinstance(data["recent_policies"], list)


def test_conversations_listing_and_deletion_api(auth_headers):
    # Test listing conversations
    res = client.get("/api/v1/qa/conversations", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Test deleting a nonexistent conversation ID gracefully returns success=False
    del_res = client.delete("/api/v1/qa/conversations/nonexistent_id", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is False
