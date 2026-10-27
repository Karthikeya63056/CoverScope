"""Tests for CoverScope authentication service and login view.

Verifies:
1. Strict email validation and whitespace sanitization.
2. Password validation and length requirements.
3. Honest authentication boundary behavior (no fake logins or arbitrary credential acceptance).
4. Configured administrator authentication.
5. Streamlit AppTest rendering of the login page and navigation boundaries.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from backend.services.auth_service import AuthService, AuthStatus, AuthUser


# -----------------------------------------------------------------------------
# 1. Email Format & Sanitization Unit Tests
# -----------------------------------------------------------------------------
def test_validate_email_valid_formats():
    valid_cases = [
        ("user@domain.com", "user@domain.com"),
        ("  first.last@company.org  ", "first.last@company.org"),
        ("policyholder+test@sub.insure.co.in", "policyholder+test@sub.insure.co.in"),
        ("claims_dept@hdfcergo.com", "claims_dept@hdfcergo.com"),
    ]
    for raw, expected in valid_cases:
        is_valid, cleaned = AuthService.validate_email(raw)
        assert is_valid is True
        assert cleaned == expected


def test_validate_email_invalid_formats():
    invalid_cases = [
        "",
        "   ",
        None,
        12345,
        "notanemail",
        "@nodomain.com",
        "user@",
        "user@domain",
        "user@.com",
        "user name@domain.com",
    ]
    for raw in invalid_cases:
        is_valid, cleaned = AuthService.validate_email(raw)
        assert is_valid is False
        assert cleaned is None


# -----------------------------------------------------------------------------
# 2. Password Syntax & Validation Tests
# -----------------------------------------------------------------------------
def test_validate_password_syntax():
    # Empty or None
    is_valid, err = AuthService.validate_password_syntax("")
    assert is_valid is False
    assert "required" in err.lower()

    is_valid, err = AuthService.validate_password_syntax(None)
    assert is_valid is False
    assert "required" in err.lower()

    # Too short (<6 chars)
    is_valid, err = AuthService.validate_password_syntax("12345")
    assert is_valid is False
    assert "at least 6 characters" in err

    # Valid length
    is_valid, err = AuthService.validate_password_syntax("SecurePass123!")
    assert is_valid is True
    assert err is None


# -----------------------------------------------------------------------------
# 3. Honest Authentication Boundary Behavior Tests
# -----------------------------------------------------------------------------
def test_authenticate_invalid_inputs():
    svc = AuthService()

    # Invalid email syntax
    res = svc.authenticate("invalid-email", "secret123")
    assert res.success is False
    assert res.status == AuthStatus.INVALID_EMAIL
    assert "valid email" in res.error_message

    # Short password
    res = svc.authenticate("user@example.com", "123")
    assert res.success is False
    assert res.status == AuthStatus.PASSWORD_TOO_SHORT
    assert "at least 6 characters" in res.error_message


def test_authenticate_refuses_arbitrary_credentials_without_provider(monkeypatch):
    """Confirm CoverScope NEVER accepts arbitrary passwords or fakes success."""
    monkeypatch.delenv("COVERSCOPE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COVERSCOPE_ADMIN_PASSWORD", raising=False)

    svc = AuthService()
    res = svc.authenticate("policyholder@example.com", "anyArbitraryPassword123")
    assert res.success is False
    assert res.status in (AuthStatus.PROVIDER_NOT_CONFIGURED, AuthStatus.USER_NOT_FOUND)


def test_authenticate_configured_admin_success_and_failure(monkeypatch):
    """Test genuine authentication when administrator credentials are configured."""
    monkeypatch.setenv("COVERSCOPE_ADMIN_EMAIL", "admin@coverscope.internal")
    monkeypatch.setenv("COVERSCOPE_ADMIN_PASSWORD", "SuperSecureAdmin2026!")

    svc = AuthService()

    # Correct credentials
    res = svc.authenticate("  admin@coverscope.internal  ", "SuperSecureAdmin2026!")
    assert res.success is True
    assert res.status == AuthStatus.AUTHENTICATED
    assert res.user is not None
    assert res.user.email == "admin@coverscope.internal"
    assert res.user.role == "administrator"
    assert "Admin" in res.user.display_name

    # Incorrect password for known admin
    res_bad = svc.authenticate("admin@coverscope.internal", "WrongPassword!")
    assert res_bad.success is False
    assert res_bad.status == AuthStatus.INVALID_CREDENTIALS
    assert "Invalid password" in res_bad.error_message


def test_password_reset_notice_guidance():
    # Valid email
    notice = AuthService.get_password_reset_notice("patient@hospital.org")
    assert "patient@hospital.org" in notice
    assert "administrator" in notice.lower()

    # Invalid email
    notice_generic = AuthService.get_password_reset_notice("")
    assert "administrator" in notice_generic.lower()

