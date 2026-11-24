# InterviewLens AI — Backend Foundation & Authentication

Welcome to the **InterviewLens AI** backend service. InterviewLens AI is an adaptive mock interview and presentation assessment platform. This repository contains the production-grade, asynchronous Python backend built with FastAPI, SQLAlchemy 2.0, SQLite, Alembic, and JWT/Argon2id authentication.

---

## 🚀 Key Features (Milestone 1)

* **Asynchronous Web Framework**: High-performance FastAPI application running on Uvicorn ASGI.
* **Declarative ORM**: SQLAlchemy 2.0 using `asyncio` with SQLite (via `aiosqlite`) for zero-daemon local development.
* **Database Migrations**: Fully managed Alembic environment supporting SQLite batch alterations.
* **Argon2id Password Hashing**: State-of-the-art memory-hard password hashing via `argon2-cffi`.
* **JWT Authentication**: Short-lived (15-minute) signed HMAC-SHA256 access tokens.
* **Refresh Token Rotation**: Opaque, cryptographically secure 64-byte refresh tokens stored exclusively as SHA-256 hashes, with single-use replay detection and instant revocation on logout.
* **Automated OpenAPI Specs**: Interactive Swagger UI at `/api/v1/docs` and ReDoc at `/api/v1/redoc`.
* **Resource Conscious**: Optimized for 8 GB RAM developer laptops with minimal idle memory consumption (~45 MB).

---

## 📁 Architecture Overview

```
backend/
├── alembic/                         # Database migration scripts
│   ├── env.py                       # Async migration engine
│   └── versions/                    # Versioned schema migrations
├── app/
│   ├── main.py                     # FastAPI application factory & lifespan
│   ├── config.py                   # Pydantic Settings (.env loader)
│   ├── api/
│   │   ├── deps.py                 # Dependency injection (DB session, current user)
│   │   └── v1/
│   │       ├── api_router.py       # Master v1 router aggregation
│   │       └── endpoints/
│   │           ├── auth.py         # Register, login, refresh, logout, profile
│   │           └── health.py       # Database & system health checks
│   ├── core/
│   │   ├── security.py             # Argon2id hasher, JWT encoder/decoder
│   │   ├── exceptions.py           # Custom exceptions & RFC-compliant handler
│   │   └── logging.py              # Structured logging configuration
│   ├── db/
│   │   ├── base.py                 # DeclarativeBase, UUID & Timestamp mixins
│   │   └── session.py              # Async engine & sessionmaker (PRAGMA foreign keys)
│   ├── models/
│   │   └── user.py                 # User & RefreshToken SQLAlchemy models
│   ├── schemas/
│   │   └── auth.py                 # Pydantic v2 request & response schemas
│   └── services/
│       └── auth_service.py         # Authentication & token rotation business logic
├── tests/
│   ├── conftest.py                 # In-memory SQLite async test fixtures
│   ├── unit/                       # Security & token unit tests
│   └── integration/                # Full API endpoint integration tests
├── .env.example                    # Environment variable template
├── alembic.ini                     # Migration configuration
├── pytest.ini                      # Pytest discovery settings
├── pyproject.toml                  # Project packaging & tool configs
├── requirements.txt                # Production dependencies
└── requirements-dev.txt            # Development & testing dependencies
```

---

## 🛠️ Local Windows Setup Instructions

### 1. Prerequisites
* **Windows 10/11**
* **Python 3.11+** (Python 3.13 tested)
* **PowerShell**

### 2. Create Virtual Environment
From the `InterviewLens-AI/backend` folder:

```powershell
# Navigate to the backend directory
cd backend

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
# Install production and development dependencies
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables
Copy the template configuration file:
```powershell
Copy-Item .env.example .env
```

### 5. Apply Database Migrations
Initialize the local SQLite database schema using Alembic:
```powershell
python -m alembic upgrade head
```

### 6. Start Development Server
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
The server will be reachable at:
* API Root: `http://127.0.0.1:8000`
* Swagger UI: `http://127.0.0.1:8000/api/v1/docs`
* ReDoc UI: `http://127.0.0.1:8000/api/v1/redoc`

---

## 🧪 Running Automated Tests

Run the complete test suite against an isolated in-memory database:

```powershell
python -m pytest tests -v
```

All 13 unit and integration tests run in under 3 seconds without altering local storage.

---

## 📡 API Usage Examples

### 1. Health Check
```powershell
# Using PowerShell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get
```
```bash
# Using curl
curl -X GET "http://127.0.0.1:8000/api/v1/health"
```
**Response (200 OK):**
```json
{
  "status": "healthy",
  "app_name": "InterviewLens AI Backend",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected"
}
```

---

### 2. Register Candidate Account
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "candidate@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jordan Doe"
  }'
```
**Response (201 Created):**
```json
{
  "id": "e9b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "email": "candidate@example.com",
  "full_name": "Jordan Doe",
  "role": "candidate",
  "is_active": true,
  "created_at": "2026-11-24T15:30:00Z"
}
```

---

### 3. User Login
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "candidate@example.com",
    "password": "SecurePassword123!"
  }'
```
**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh_token": "a8B7c6D5e4F3...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### 4. Access Protected User Profile
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
**Response (200 OK):**
```json
{
  "id": "e9b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "email": "candidate@example.com",
  "full_name": "Jordan Doe",
  "role": "candidate",
  "is_active": true,
  "created_at": "2026-11-24T15:30:00Z"
}
```

---

### 5. Rotate Refresh Token
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<CURRENT_REFRESH_TOKEN>"
  }'
```
**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh_token": "new_b9C8d7E6f5...",
  "token_type": "bearer",
  "expires_in": 900
}
```
*Note: The previous refresh token is immediately invalidated and cannot be reused.*

---

### 6. User Logout
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/logout" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<CURRENT_REFRESH_TOKEN>"
  }'
```
**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

---

## 🔒 Security Best Practices Implemented

1. **Password Safety**: Uses Argon2id memory-hard hashing (`time_cost=2`, `memory_cost=64MB`, `parallelism=2`), preventing GPU brute-forcing.
2. **Token Security**: Raw refresh tokens are never persisted in the database; only their SHA-256 cryptographic digests are stored.
3. **Replay Protection**: Single-use token rotation guarantees that re-attempting to use an old refresh token returns `401 Unauthorized`.
4. **Isolated Schemas**: In-memory SQLite with `StaticPool` prevents any side effects or residual state between unit/integration test executions.
