"""Authentication API routes for user registration, login, profile, and logout."""
from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.api.deps import create_access_token, get_current_user
from backend.api.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from backend.services.auth_service import AuthService, AuthStatus, AuthUser

router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, response: Response, request: Request) -> AuthResponse:
    """Register a new user account with salted password in MongoDB Atlas."""
    res = auth_service.register(req.email, req.password, req.display_name)
    if not res.success or res.user is None:
        err = res.error_message or "Registration failed."
        status_code = status.HTTP_409_CONFLICT if res.status == AuthStatus.ACCOUNT_EXISTS else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err)

    token = create_access_token(res.user)
    # Set HttpOnly cookie for defense-in-depth
    is_secure = request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400,
        path="/",
        samesite="lax",
        secure=is_secure,
    )
    return AuthResponse(
        success=True,
        user=UserResponse(
            user_id=res.user.user_id,
            email=res.user.email,
            display_name=res.user.display_name,
            role=res.user.role,
        ),
        token=token,
        access_token=token,
        token_type="bearer",
        message=res.info_message,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, response: Response, request: Request) -> AuthResponse:
    """Authenticate existing credentials against MongoDB Atlas or configured admin."""
    res = auth_service.authenticate(req.email, req.password)
    if not res.success or res.user is None:
        err = res.error_message or "Invalid email or password."
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err)

    token = create_access_token(res.user)
    is_secure = request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400,
        path="/",
        samesite="lax",
        secure=is_secure,
    )
    return AuthResponse(
        success=True,
        user=UserResponse(
            user_id=res.user.user_id,
            email=res.user.email,
            display_name=res.user.display_name,
            role=res.user.role,
        ),
        token=token,
        access_token=token,
        token_type="bearer",
        message=res.info_message,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: AuthUser = Depends(get_current_user)) -> UserResponse:
    """Return profile for the active authenticated session."""
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
    )


@router.post("/logout")
def logout(response: Response, request: Request) -> dict[str, str]:
    """Clear session authentication cookie."""
    is_secure = request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production"
    response.delete_cookie(key="access_token", path="/", samesite="lax", secure=is_secure)
    return {"message": "Logged out successfully."}
