"""Unit tests for cryptographic security: Argon2id hashing and JWT token management."""

from datetime import timedelta
import pytest
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hashing_and_verification():
    """Test that passwords hash securely with Argon2id and verify correctly."""
    raw_password = "CandidateSecurePassword123!"
    hashed = hash_password(raw_password)

    # Hash should not equal plain password
    assert hashed != raw_password
    assert hashed.startswith("$argon2id$")

    # Correct password verifies
    assert verify_password(raw_password, hashed) is True

    # Incorrect password fails
    assert verify_password("WrongPassword123!", hashed) is False


def test_token_hash_consistency():
    """Test that token hashing produces consistent, non-reversible SHA-256 digests."""
    token = generate_secure_token()
    assert len(token) >= 64

    hash1 = hash_token(token)
    hash2 = hash_token(token)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_access_token_creation_and_decoding():
    """Test standard JWT creation and successful claim decoding."""
    user_id = "12345678-1234-5678-1234-567812345678"
    token = create_access_token(subject=user_id, role="candidate")

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "candidate"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_expired_access_token():
    """Test that expired tokens are cleanly rejected with UnauthorizedException."""
    user_id = "12345678-1234-5678-1234-567812345678"
    # Create token expired 5 minutes ago
    expired_token = create_access_token(
        subject=user_id,
        role="candidate",
        expires_delta=timedelta(minutes=-5),
    )

    with pytest.raises(UnauthorizedException) as exc_info:
        decode_access_token(expired_token)

    assert "expired" in exc_info.value.message.lower()


def test_tampered_access_token():
    """Test that tampered tokens fail signature validation."""
    user_id = "12345678-1234-5678-1234-567812345678"
    token = create_access_token(subject=user_id, role="candidate")

    # Alter token string
    tampered_token = token[:-4] + "fake"

    with pytest.raises(UnauthorizedException):
        decode_access_token(tampered_token)
