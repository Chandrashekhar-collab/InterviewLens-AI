"""Authentication service managing user registration, credentials verification, and token rotation."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenResponse, UserRegisterRequest


class AuthService:
    """Service layer encapsulating all authentication business logic."""

    @staticmethod
    async def register_user(db: AsyncSession, data: UserRegisterRequest) -> User:
        """Register a new user with duplicate email protection and Argon2id hashing."""
        normalized_email = data.email.lower().strip()

        # Check if email is already taken
        query = select(User).where(User.email == normalized_email)
        result = await db.execute(query)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise ConflictException("An account with this email address already exists")

        # Hash password and create user
        hashed_pwd = hash_password(data.password)
        new_user = User(
            email=normalized_email,
            hashed_password=hashed_pwd,
            full_name=data.full_name.strip(),
            role="candidate",
            is_active=True,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Verify user credentials and return user object if valid."""
        normalized_email = email.lower().strip()
        query = select(User).where(User.email == normalized_email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise ForbiddenException("Account is currently disabled")

        return user

    @staticmethod
    async def create_user_tokens(db: AsyncSession, user: User) -> TokenResponse:
        """Issue short-lived JWT access token and persist a hashed refresh token."""
        # 1. JWT Access Token
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
        )

        # 2. Opaque Refresh Token
        raw_refresh_token = generate_secure_token()
        hashed_refresh_token = hash_token(raw_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token_entry = RefreshToken(
            user_id=user.id,
            token_hash=hashed_refresh_token,
            expires_at=expires_at,
            is_revoked=False,
        )

        db.add(refresh_token_entry)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> TokenResponse:
        """Rotate an existing refresh token: revoke used token and issue new token pair."""
        token_hash = hash_token(raw_refresh_token)

        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(query)
        token_record = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not token_record or token_record.is_revoked:
            raise UnauthorizedException("Invalid or revoked refresh token")

        # Compare timezone-aware datetimes
        token_expiry = token_record.expires_at
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)

        if token_expiry < now:
            raise UnauthorizedException("Refresh token has expired")

        # Revoke the used token immediately
        token_record.is_revoked = True

        # Fetch associated user
        user_query = select(User).where(User.id == token_record.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            raise UnauthorizedException("User account associated with token is invalid or disabled")

        # Generate new token pair
        new_access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
        )

        new_raw_refresh_token = generate_secure_token()
        new_token_hash = hash_token(new_raw_refresh_token)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
            is_revoked=False,
        )

        db.add(new_refresh_record)
        await db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def revoke_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> None:
        """Revoke a refresh token on logout."""
        token_hash = hash_token(raw_refresh_token)

        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(query)
        token_record = result.scalar_one_or_none()

        if token_record and not token_record.is_revoked:
            token_record.is_revoked = True
            await db.commit()
