"""Authentication API endpoints for registration, login, token refresh, logout, and profile."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.auth import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Register a new candidate user with email uniqueness check and Argon2id hashing."""
    user = await AuthService.register_user(db=db, data=data)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue token pair",
)
async def login(
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate credentials and generate JWT access token with a rotatable refresh token."""
    user = await AuthService.authenticate_user(
        db=db,
        email=data.email,
        password=data.password,
    )
    return await AuthService.create_user_tokens(db=db, user=user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new token pair",
)
async def refresh_tokens(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Exchange a valid refresh token for a newly issued access token and rotated refresh token."""
    return await AuthService.rotate_refresh_token(
        db=db,
        raw_refresh_token=data.refresh_token,
    )


@router.post(
    "/logout",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Revoke active refresh token",
)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Revoke the provided refresh token to terminate session."""
    await AuthService.revoke_refresh_token(
        db=db,
        raw_refresh_token=data.refresh_token,
    )
    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve profile details for the currently authenticated user."""
    return UserResponse.model_validate(current_user)
