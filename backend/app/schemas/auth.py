"""Authentication request and response validation schemas."""

from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., description="Unique email address for user login")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must contain at least 8 characters",
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full display name of the user",
    )


class UserLoginRequest(BaseModel):
    """Schema for standard JSON login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class TokenResponse(BaseModel):
    """Schema for authentication token pair response."""

    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str = Field(..., description="Opaque secure refresh token")
    token_type: str = Field("bearer", description="Token authorization type")
    expires_in: int = Field(..., description="Access token lifespan in seconds")


class RefreshTokenRequest(BaseModel):
    """Schema for rotating an existing refresh token."""

    refresh_token: str = Field(..., min_length=10, description="Active refresh token")


class LogoutRequest(BaseModel):
    """Schema for revoking a refresh token upon logout."""

    refresh_token: str = Field(..., min_length=10, description="Refresh token to revoke")


class UserResponse(BaseModel):
    """Schema for returning user profile details safely without sensitive data."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
