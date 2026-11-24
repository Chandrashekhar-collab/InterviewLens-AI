# InterviewLens AI — Backend Foundation & Adaptive Interview Engine

Welcome to the **InterviewLens AI** backend service. InterviewLens AI is an adaptive mock interview and presentation assessment platform. This repository contains the production-grade, asynchronous Python backend built with FastAPI, SQLAlchemy 2.0, SQLite, Alembic, JWT/Argon2id authentication, and an intelligent rule-based Adaptive Question Engine.

---

## 🚀 Key Features

### Milestone 1: Foundation & Authentication
* **Asynchronous Web Framework**: High-performance FastAPI application running on Uvicorn ASGI.
* **Declarative ORM**: SQLAlchemy 2.0 using `asyncio` with SQLite (via `aiosqlite`) for zero-daemon local development.
* **Database Migrations**: Fully managed Alembic environment supporting SQLite batch alterations.
* **Argon2id Password Hashing**: State-of-the-art memory-hard password hashing via `argon2-cffi`.
* **JWT Authentication**: Short-lived (15-minute) signed HMAC-SHA256 access tokens.
* **Refresh Token Rotation**: Opaque, cryptographically secure 64-byte refresh tokens stored exclusively as SHA-256 hashes, with single-use replay detection and instant revocation on logout.
* **Resource Conscious**: Optimized for 8 GB RAM developer laptops with minimal idle memory consumption (~45 MB).

### Milestone 2: Interview Configuration & Adaptive Question Engine
* **Interview Configuration**: Configurable target roles (`software_engineer`, `data_scientist`, etc.), focus types (`technical`, `behavioral`, `hr`, `communication`, `presentation`, `mixed`), difficulties (`easy`, `medium`, `hard`), and seniority levels (`entry`, `mid`, `senior`, `lead`).
* **Curated Question Bank**: Domain-vetted questions across 5 core categories with expected durations, keywords, and ideal answer rubrics.
* **Adaptive Difficulty Engine**: Dynamically steps up or down question difficulty in real time based on candidate performance on prior answers:
  * **Score $\ge$ 75.0**: Steps up difficulty (`easy` $\rightarrow$ `medium` $\rightarrow$ `hard`).
  * **50.0 $\le$ Score < 75.0**: Maintains current difficulty level.
  * **Score < 50.0**: Steps down difficulty (`hard` $\rightarrow$ `medium` $\rightarrow$ `easy`).
* **Duplicate Prevention**: Strict set exclusion guarantees that no question is ever repeated within the same interview session.
* **Category Balancing**: For `mixed` interviews, questions systematically cycle through Behavioral $\rightarrow$ Technical $\rightarrow$ Architecture $\rightarrow$ Communication $\rightarrow$ Presentation $\rightarrow$ HR.
* **State Machine & Ownership Protection**: Enforces strict status transitions (`draft` $\rightarrow$ `in_progress` $\rightarrow$ `completed`) with multi-tenant ownership guards.

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
│   │           ├── health.py       # Database & system health checks
│   │           └── interviews.py   # Creation, starting, current, next, complete
│   ├── core/
│   │   ├── security.py             # Argon2id hasher, JWT encoder/decoder
│   │   ├── exceptions.py           # Custom exceptions & RFC-compliant handler
│   │   └── logging.py              # Structured logging configuration
│   ├── db/
│   │   ├── base.py                 # DeclarativeBase, UUID & Timestamp mixins
│   │   ├── session.py              # Async engine & sessionmaker (PRAGMA foreign keys)
│   │   └── seed.py                 # Question bank seeder utility
│   ├── engines/
│   │   └── question_gen/
│   │       ├── adaptive_engine.py  # Performance-based adaptive difficulty selector
│   │       └── question_bank.py    # Curated seed question bank with rubrics
│   ├── models/
│   │   ├── user.py                 # User & RefreshToken models
│   │   ├── interview.py            # Interview session model
│   │   ├── question.py             # Question bank entity
│   │   └── interview_question.py   # Sequence and score junction model
│   ├── schemas/
│   │   ├── auth.py                 # Authentication Pydantic v2 schemas
│   │   └── interview.py            # Interview & question Pydantic v2 schemas
│   └── services/
│       ├── auth_service.py         # Authentication & token rotation logic
│       └── interview_service.py    # Interview lifecycle & adaptive sequencing
├── tests/
│   ├── conftest.py                 # In-memory SQLite async test fixtures
│   ├── unit/
│   │   ├── test_security.py        # Security & token unit tests
│   │   └── test_adaptive_engine.py # Adaptive difficulty & category unit tests
│   └── integration/
│       ├── test_auth_api.py        # Authentication endpoint integration tests
│       └── test_interviews_api.py  # Interview progression & state guard tests
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
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables
```powershell
Copy-Item .env.example .env
```

### 5. Apply Database Migrations
```powershell
python -m alembic upgrade head
```

### 6. Start Development Server
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive API documentation:
* Swagger UI: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
* ReDoc UI: [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)

---

## 🧪 Running Automated Tests

Run the complete test suite against an isolated in-memory database:

```powershell
python -m pytest tests -v
```

All 25 unit and integration tests run in ~7 seconds without altering local storage.

---

## 📡 API Usage Examples

### 1. Register & Login
```bash
# Register
curl -X POST "http://127.0.0.1:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "candidate@example.com", "password": "SecurePassword123!", "full_name": "Jordan Doe"}'

# Login
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "candidate@example.com", "password": "SecurePassword123!"}'
```

---

### 2. Configure a New Interview Session
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/interviews" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fullstack Software Engineer Mock",
    "target_role": "software_engineer",
    "interview_type": "mixed",
    "difficulty_level": "medium",
    "experience_level": "mid",
    "total_questions": 5
  }'
```
**Response (201 Created):**
```json
{
  "id": "7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4",
  "user_id": "e9b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "title": "Fullstack Software Engineer Mock",
  "target_role": "software_engineer",
  "interview_type": "mixed",
  "difficulty_level": "medium",
  "experience_level": "mid",
  "total_questions": 5,
  "status": "draft",
  "current_question_index": 0,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-11-24T17:30:00Z",
  "questions_answered_count": 0
}
```

---

### 3. Start Interview & Receive Question 1
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/interviews/7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4/start" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
**Response (200 OK):**
```json
{
  "order_index": 1,
  "total_questions": 5,
  "is_last_question": false,
  "question": {
    "id": "a1b2c3d4-1234-5678-abcd-0123456789ef",
    "category": "behavioral",
    "difficulty": "medium",
    "target_roles": ["general", "software_engineer"],
    "question_text": "Describe a situation where you had a significant technical disagreement with a team member. How did you handle it?",
    "expected_duration_seconds": 180
  }
}
```

---

### 4. Fetch Currently Active Question
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/interviews/7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4/questions/current" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

### 5. Advance to Next Adaptive Question
Submit candidate answer score (e.g. 88.0) to dynamically adjust difficulty:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/interviews/7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4/questions/next" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "previous_answer_score": 88.0
  }'
```
**Response (200 OK):**
```json
{
  "order_index": 2,
  "total_questions": 5,
  "is_last_question": false,
  "question": {
    "id": "d4c3b2a1-5678-1234-fedc-9876543210ab",
    "category": "technical",
    "difficulty": "hard",
    "target_roles": ["software_engineer", "systems_architect"],
    "question_text": "How would you design a distributed rate limiter that operates reliably across multiple stateless backend service instances?",
    "expected_duration_seconds": 240
  }
}
```

---

### 6. Conclude Interview Session
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/interviews/7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4/complete" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
**Response (200 OK):**
```json
{
  "id": "7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4",
  "status": "completed",
  "current_question_index": 5,
  "completed_at": "2026-11-24T17:45:00Z",
  "questions_answered_count": 5
}
```

---

## 🎯 Adaptive Engine Rules Reference

| Prior Answer Score | Difficulty Adjustment | Rationale |
|---|---|---|
| **$\ge$ 75.0** | **Step Up** (`easy` $\rightarrow$ `medium` $\rightarrow$ `hard`) | Demonstrates mastery; increases challenge to benchmark technical limits. |
| **50.0 – 74.9** | **Maintain** (Current Level) | Moderate competence; maintains current depth to consolidate assessment. |
| **< 50.0** | **Step Down** (`hard` $\rightarrow$ `medium` $\rightarrow$ `easy`) | Identifies knowledge boundaries; adjusts to foundational concepts. |
