"""Authentication service and credential validation boundary for CoverScope.

This service establishes a production-grade authentication contract for CoverScope.
It handles email format validation, credential verification rules, salted PBKDF2-SHA256
password hashing, MongoDB Atlas account management, and session contracts without
storing plaintext passwords.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

LOCAL_USERS_FILE = Path(__file__).resolve().parents[2] / "data" / "local_users.json"
_LOCAL_USERS_LOCK = threading.Lock()

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)
MIN_PASSWORD_LENGTH = 6


def hash_password(password: str) -> str:
    """Generate salted PBKDF2-SHA256 password hash."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, hashed: str | None) -> bool:
    """Verify password against salted PBKDF2-SHA256 hash."""
    if not hashed or "$" not in hashed:
        return False
    try:
        salt, dk_hex = hashed.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return hmac.compare_digest(computed.hex(), dk_hex)
    except Exception:
        return False


class AuthStatus(str, Enum):
    """Status outcomes from an authentication or validation attempt."""
    AUTHENTICATED = "authenticated"
    INVALID_CREDENTIALS = "invalid_credentials"
    MISSING_FIELDS = "missing_fields"
    INVALID_EMAIL = "invalid_email"
    PASSWORD_TOO_SHORT = "password_too_short"
    USER_NOT_FOUND = "user_not_found"
    ACCOUNT_EXISTS = "account_exists"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    ACCOUNT_LOCKED = "account_locked"


@dataclass(frozen=True)
class AuthUser:
    """An authenticated CoverScope user session identity."""
    user_id: str
    email: str
    display_name: str
    role: str = "policyholder"
    authenticated_at: float = 0.0


@dataclass(frozen=True)
class AuthResult:
    """Structured outcome of an authentication or credential submission."""
    success: bool
    status: AuthStatus
    user: AuthUser | None = None
    error_message: str | None = None
    info_message: str | None = None


class AuthService:
    """Authentication and credential verification service with persistent local fallback."""

    def __init__(self, *, provider_name: str | None = None) -> None:
        self.provider_name = provider_name or os.getenv("COVERSCOPE_AUTH_PROVIDER", "mongodb_local")
        self._local_users: dict[str, dict[str, Any]] = {}
        self._load_local_users()

    def _load_local_users(self) -> None:
        """Load registered accounts from persistent local storage."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            return
        try:
            if LOCAL_USERS_FILE.exists():
                with open(LOCAL_USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._local_users = data
                        logger.info("Loaded %d local user account(s) from %s", len(data), LOCAL_USERS_FILE)
        except Exception as exc:
            logger.warning("Could not load local users cache from %s: %s", LOCAL_USERS_FILE, exc)

    def _save_local_users(self) -> None:
        """Persist local accounts to disk atomically so they survive process restarts."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            return
        with _LOCAL_USERS_LOCK:
            try:
                LOCAL_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
                temp_file = LOCAL_USERS_FILE.with_suffix(f".tmp.{os.getpid()}_{int(time.time()*1000)}")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self._local_users, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                temp_file.replace(LOCAL_USERS_FILE)
            except Exception as exc:
                logger.warning("Could not persist local users to %s: %s", LOCAL_USERS_FILE, exc)

    @staticmethod
    def validate_email(email: str | None) -> tuple[bool, str | None]:
        """Validate email format, returning (is_valid, sanitized_email_or_none)."""
        if not email or not isinstance(email, str):
            return False, None
        cleaned = email.strip()
        if not cleaned:
            return False, None
        if not _EMAIL_REGEX.match(cleaned):
            return False, None
        return True, cleaned

    @staticmethod
    def validate_password_syntax(password: str | None) -> tuple[bool, str | None]:
        """Validate password format without logging or storing the secret."""
        if not password or not isinstance(password, str):
            return False, "Password is required."
        if len(password) < MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        return True, None

    @staticmethod
    def _deterministic_offline_uid(email: str) -> str:
        """Generate a stable, collision-resistant user id for offline session accounts."""
        h = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
        return f"usr_{h}"

    def register(
        self,
        email: str | None,
        password: str | None,
        display_name: str | None = None,
    ) -> AuthResult:
        """Register a new user account with salted password hash stored in MongoDB Atlas or local storage."""
        is_email_valid, clean_email = self.validate_email(email)
        if not is_email_valid or not clean_email:
            return AuthResult(
                success=False,
                status=AuthStatus.INVALID_EMAIL,
                error_message="Please enter a valid email address (e.g. name@domain.com).",
            )

        is_pw_valid, pw_err = self.validate_password_syntax(password)
        if not is_pw_valid:
            status = AuthStatus.PASSWORD_TOO_SHORT if pw_err and "characters" in pw_err else AuthStatus.MISSING_FIELDS
            return AuthResult(
                success=False,
                status=status,
                error_message=pw_err or "Please enter your password.",
            )

        name = (display_name or "").strip()
        if not name:
            name = clean_email.split("@")[0].replace(".", " ").title()

        normalized_email = clean_email.lower()

        # Check existing local cache first
        if normalized_email in self._local_users:
            return AuthResult(
                success=False,
                status=AuthStatus.ACCOUNT_EXISTS,
                error_message="An account with this email already exists. Please sign in.",
            )

        password_hash = hash_password(password)
        uid = self._deterministic_offline_uid(clean_email)

        # Attempt to persist in MongoDB Atlas when reachable
        try:
            from backend.database.client import get_database
            from backend.database.schema import COLL_USERS

            db = get_database()
            if db is not None:
                coll = db[COLL_USERS]
                existing = coll.find_one({"email": normalized_email})
                if existing:
                    return AuthResult(
                        success=False,
                        status=AuthStatus.ACCOUNT_EXISTS,
                        error_message="An account with this email already exists. Please sign in.",
                    )

                now = datetime.now(timezone.utc)
                doc = {
                    "auth_provider": "local_password",
                    "auth_provider_user_id": normalized_email,
                    "email": normalized_email,
                    "display_name": name,
                    "role": "policyholder",
                    "password_hash": password_hash,
                    "created_at": now,
                    "updated_at": now,
                }
                res = coll.insert_one(doc)
                uid = str(res.inserted_id)
        except Exception as exc:
            logger.warning(
                "MongoDB Atlas registration unavailable (%s); saving account to persistent local storage.",
                exc,
            )

        # Always save into persistent local store so user is never locked out across restarts
        self._local_users[normalized_email] = {
            "user_id": uid,
            "email": normalized_email,
            "display_name": name,
            "role": "policyholder",
            "password_hash": password_hash,
            "created_at": time.time(),
        }
        self._save_local_users()

        user = AuthUser(
            user_id=uid,
            email=clean_email,
            display_name=name,
            role="policyholder",
            authenticated_at=time.time(),
        )
        return AuthResult(
            success=True,
            status=AuthStatus.AUTHENTICATED,
            user=user,
            info_message=f"Account created successfully. Welcome, {user.display_name}!",
        )

    def authenticate(self, email: str | None, password: str | None) -> AuthResult:
        """Authenticate user credentials against admin config, persistent local store, or MongoDB Atlas."""
        is_email_valid, clean_email = self.validate_email(email)
        if not is_email_valid or not clean_email:
            return AuthResult(
                success=False,
                status=AuthStatus.INVALID_EMAIL,
                error_message="Please enter a valid email address (e.g. name@domain.com).",
            )

        is_pw_valid, pw_err = self.validate_password_syntax(password)
        if not is_pw_valid:
            status = AuthStatus.PASSWORD_TOO_SHORT if pw_err and "characters" in pw_err else AuthStatus.MISSING_FIELDS
            return AuthResult(
                success=False,
                status=status,
                error_message=pw_err or "Please enter your password.",
            )

        normalized_email = clean_email.lower()

        # 1. Check for administrator credentials (fast, non-blocking)
        admin_email = os.getenv("COVERSCOPE_ADMIN_EMAIL")
        admin_pass = os.getenv("COVERSCOPE_ADMIN_PASSWORD")

        if admin_email and admin_pass and normalized_email == admin_email.strip().lower():
            if password == admin_pass:
                name_part = clean_email.split("@")[0].replace(".", " ").title()
                user_id = self._deterministic_offline_uid(clean_email)

                user = AuthUser(
                    user_id=user_id,
                    email=clean_email,
                    display_name=name_part,
                    role="administrator",
                    authenticated_at=time.time(),
                )
                return AuthResult(
                    success=True,
                    status=AuthStatus.AUTHENTICATED,
                    user=user,
                    info_message=f"Welcome back, {user.display_name}!",
                )
            else:
                return AuthResult(
                    success=False,
                    status=AuthStatus.INVALID_CREDENTIALS,
                    error_message="Invalid password. Please verify your credentials.",
                )

        # 2. Check persistent local store first (instant, zero network latency)
        local_user = self._local_users.get(normalized_email)
        if local_user:
            if verify_password(password, local_user.get("password_hash")):
                uid = local_user.get("user_id") or self._deterministic_offline_uid(clean_email)
                user = AuthUser(
                    user_id=uid,
                    email=local_user.get("email", clean_email),
                    display_name=local_user.get("display_name", clean_email.split("@")[0].title()),
                    role=local_user.get("role", "policyholder"),
                    authenticated_at=time.time(),
                )
                return AuthResult(
                    success=True,
                    status=AuthStatus.AUTHENTICATED,
                    user=user,
                    info_message=f"Welcome back, {user.display_name}!",
                )
            return AuthResult(
                success=False,
                status=AuthStatus.INVALID_CREDENTIALS,
                error_message="Incorrect password. Please verify your credentials.",
            )

        # 3. Check for registered user in MongoDB Atlas
        db_error = False
        try:
            from backend.database.client import get_database
            from backend.database.schema import COLL_USERS

            db = get_database()
            if db is not None:
                coll = db[COLL_USERS]
                user_doc = coll.find_one({"email": normalized_email})
                if user_doc:
                    pw_hash = user_doc.get("password_hash")
                    if pw_hash and verify_password(password, pw_hash):
                        user = AuthUser(
                            user_id=str(user_doc["_id"]),
                            email=user_doc.get("email", clean_email),
                            display_name=user_doc.get("display_name", clean_email.split("@")[0].title()),
                            role=user_doc.get("role", "policyholder"),
                            authenticated_at=time.time(),
                        )
                        # Cache locally for offline resilience
                        self._local_users[normalized_email] = {
                            "user_id": str(user_doc["_id"]),
                            "email": normalized_email,
                            "display_name": user.display_name,
                            "role": user.role,
                            "password_hash": pw_hash,
                            "created_at": time.time(),
                        }
                        self._save_local_users()
                        return AuthResult(
                            success=True,
                            status=AuthStatus.AUTHENTICATED,
                            user=user,
                            info_message=f"Welcome back, {user.display_name}!",
                        )
                    return AuthResult(
                        success=False,
                        status=AuthStatus.INVALID_CREDENTIALS,
                        error_message="Incorrect password. Please verify your credentials.",
                    )
        except Exception as exc:
            db_error = True
            logger.warning("Database authentication lookup error: %s", exc)

        if db_error:
            return AuthResult(
                success=False,
                status=AuthStatus.PROVIDER_NOT_CONFIGURED,
                error_message=(
                    "Unable to connect to the cloud database (MongoDB Atlas connection/IP access error). "
                    "If you haven't created an account yet, please click 'Create an account' below to sign up."
                ),
            )

        # 4. Fallback when user is not found
        return AuthResult(
            success=False,
            status=AuthStatus.USER_NOT_FOUND,
            error_message=(
                "No account found with this email. "
                "Please click 'Create an account' below to sign up."
            ),
        )

    @staticmethod
    def get_password_reset_notice(email: str | None) -> str:
        """Provide honest password recovery notice."""
        is_valid, clean = AuthService.validate_email(email)
        if is_valid and clean:
            return (
                f"Password recovery requested for {clean}. "
                "Self-service password recovery is managed by your policy administrator. "
                "Please contact your administrator to reset your credentials."
            )
        return (
            "Self-service password recovery is managed by your organization or policy administrator. "
            "Please provide your registered email address or contact support."
        )
