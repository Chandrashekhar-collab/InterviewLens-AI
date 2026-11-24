"""Integration tests covering registration, login, token rotation, logout, profile, and health-check."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoints(client: AsyncClient):
    """Test 9: Verify root and versioned health-check endpoints report healthy status."""
    # Test /health
    resp_root = await client.get("/health")
    assert resp_root.status_code == 200
    data_root = resp_root.json()
    assert data_root["status"] == "healthy"

    # Test /api/v1/health
    resp_v1 = await client.get("/api/v1/health")
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] == "healthy"
    assert data_v1["database"] == "connected"


@pytest.mark.asyncio
async def test_successful_registration(client: AsyncClient):
    """Test 1: Verify successful candidate user registration."""
    payload = {
        "email": "candidate@example.com",
        "password": "SecurePassword123!",
        "full_name": "Jordan Doe",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "candidate@example.com"
    assert data["full_name"] == "Jordan Doe"
    assert data["role"] == "candidate"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_duplicate_email_registration(client: AsyncClient):
    """Test 2: Verify duplicate email registration is rejected with 409 Conflict."""
    payload = {
        "email": "unique.user@example.com",
        "password": "SecurePassword123!",
        "full_name": "Unique User",
    }
    # Initial registration
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Duplicate registration attempt
    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_successful_login(client: AsyncClient):
    """Test 3: Verify successful login returns JWT access and refresh token pair."""
    # Register user first
    reg_payload = {
        "email": "login.test@example.com",
        "password": "ValidPassword123!",
        "full_name": "Login Test",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": "login.test@example.com",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900


@pytest.mark.asyncio
async def test_incorrect_password_login(client: AsyncClient):
    """Test 4: Verify login fails with 401 when password is incorrect."""
    reg_payload = {
        "email": "wrongpwd.test@example.com",
        "password": "CorrectPassword123!",
        "full_name": "Test User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrongpwd.test@example.com",
        "password": "WrongPassword999!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_access_token_validation_and_profile(client: AsyncClient):
    """Test 5 & 8: Verify access token validation and protected profile access."""
    # Register & Login
    user_data = {
        "email": "profile.test@example.com",
        "password": "Password12345!",
        "full_name": "Profile Owner",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # 1. Access without token should fail (401)
    unauth_resp = await client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    # 2. Access with invalid token should fail (401)
    invalid_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert invalid_resp.status_code == 401

    # 3. Access with valid token should succeed (200)
    auth_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert auth_resp.status_code == 200
    profile = auth_resp.json()
    assert profile["email"] == "profile.test@example.com"
    assert profile["full_name"] == "Profile Owner"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    """Test 6: Verify refresh token rotation issues a new pair and invalidates old token."""
    # Register & Login
    user_data = {
        "email": "rotation.test@example.com",
        "password": "Password12345!",
        "full_name": "Rotation Test",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    original_tokens = login_resp.json()
    old_refresh_token = original_tokens["refresh_token"]

    # Rotate refresh token
    rotate_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert rotate_resp.status_code == 200
    new_tokens = rotate_resp.json()
    new_access_token = new_tokens["access_token"]
    new_refresh_token = new_tokens["refresh_token"]

    # New tokens should be distinct
    assert new_refresh_token != old_refresh_token
    assert "access_token" in new_tokens

    # Verify new access token works for authenticated requests
    profile_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert profile_resp.status_code == 200

    # Old refresh token MUST be rejected upon replay attempt (Rotation Protection)
    replay_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert replay_resp.status_code == 401
    replay_data = replay_resp.json()
    assert replay_data["success"] is False
    assert replay_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_logout_and_revocation(client: AsyncClient):
    """Test 7: Verify logout revokes the refresh token."""
    user_data = {
        "email": "logout.test@example.com",
        "password": "Password12345!",
        "full_name": "Logout Test",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Perform logout
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out"

    # Attempting to refresh with the revoked token must fail (401)
    revoked_refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert revoked_refresh_resp.status_code == 401
