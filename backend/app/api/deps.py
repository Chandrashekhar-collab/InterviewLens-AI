"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator
import uuid
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# HTTPBearer security scheme: presents a simple Bearer token field in Swagger UI
http_bearer = HTTPBearer(
    auto_error=True,
    description="Enter your JWT access token directly: e.g. `<access_token>`",
)

# Backward-compatibility alias
oauth2_scheme = http_bearer


async def get_db_session(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields the active database session."""
    yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Dependency that extracts and authenticates the current user from JWT access token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Malformed authentication token")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid user identifier in token")

    query = select(User).where(User.id == user_uuid)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User associated with this token does not exist")

    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    return user
