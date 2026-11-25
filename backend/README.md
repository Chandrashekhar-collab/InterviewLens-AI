# InterviewLens AI — Backend Architecture & Speech Analysis Engine

Welcome to the **InterviewLens AI** backend service. InterviewLens AI is an adaptive mock interview and presentation assessment platform. This repository contains the asynchronous Python backend built with FastAPI, SQLAlchemy 2.0, SQLite, Alembic, JWT/Argon2id authentication, a rule-based Adaptive Question Engine, and a dedicated Speech Delivery Analysis Engine.

---

## 🚀 Key Features

### Milestone 1: Foundation & Authentication
* **Asynchronous Web Framework**: FastAPI application running on Uvicorn ASGI.
* **Declarative ORM**: SQLAlchemy 2.0 using `asyncio` with SQLite (via `aiosqlite`) for zero-daemon local development.
* **Database Migrations**: Managed Alembic environment supporting SQLite batch alterations.
* **Argon2id Password Hashing**: Memory-hard password hashing via `argon2-cffi`.
* **JWT Authentication**: Short-lived (15-minute) signed HMAC-SHA256 access tokens.
* **Refresh Token Rotation**: Opaque, cryptographically secure 64-byte refresh tokens stored exclusively as SHA-256 hashes, with single-use replay detection and instant revocation on logout.
* **Resource Conscious**: Configured for 8 GB RAM developer laptops without requiring heavy background services.

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

### Milestone 3: Audio Recording & Speech Analysis Engine
* **Secure Audio Ingestion**:
  * Supported formats: WAV, MP3, M4A, WebM.
  * Multi-layer validation: file extension checking, configurable upload size limit (default 25 MB), and binary magic-byte header inspection.
  * Streaming chunked upload: uploaded files are read in 64 KB chunks (`UPLOAD_CHUNK_SIZE`), reading stops immediately if `MAX_UPLOAD_SIZE_BYTES` is exceeded, and the upload handle is always closed.
  * Path traversal protection & orphan cleanup: uploads are assigned randomized UUID filenames outside static web roots, internal server file paths are never exposed in API responses, and partial or orphaned files are removed if storage or database persistence fails.
* **Non-Blocking Speech Analysis**:
  * Synchronous `SpeechAnalysisPipeline.analyze_audio()` execution runs in a worker thread via `asyncio.to_thread()` so the FastAPI event loop remains responsive, while SQLAlchemy `AsyncSession` operations remain strictly on the async event loop.
* **Speech-to-Text Transcription (`faster-whisper`)**:
  * Utilizes `faster-whisper` (CTranslate2) with `int8` compute type on CPU, returning full text and segment-level timestamps (`start`, `end`, `text`).
  * `AudioPreprocessor` normalizes audio into 16 kHz mono `float32` NumPy arrays (via `soundfile` / `PyAV` and `scipy.signal.resample_poly`), with a PyAV compatibility patch for `av.open(..., metadata_errors=...)`.
  * **Lazy Singleton Loading**: The model is never loaded on application startup; it initializes only on the first explicit transcription request, avoiding duplicate model instances in memory.
  * Model size is configurable via `.env` (`tiny` default for 8 GB RAM local development).
  * If transcription fails, transcript-derived metrics (`word_count`, `words_per_minute`, `total_filler_words`, `filler_words_per_minute`) are returned as `null` rather than misleading zeros.
* **Speaking Speed (WPM)**:
  * Words Per Minute calculated as: $\text{WPM} = \frac{\text{Word Count}}{\text{Duration in Minutes}}$.
  * Handles edge cases cleanly: empty transcripts and recordings under 1 second evaluate to 0.0 WPM without misleading scores.
* **Filler-Word Detection**:
  * Detects common disfluencies: *"um"*, *"uh"*, *"hmm"*, *"like"*, *"you know"*, *"basically"*, *"actually"*, *"I mean"*.
  * Regex word-boundary isolation prevents sub-word false positives (e.g., *"likely"*, *"umbrella"*).
  * Computes total filler count, frequency per minute, and individual breakdown dictionary while strictly preserving original transcript text.
* **Pause & Silence Detection**:
  * Energy-based frame RMS analysis with configurable decibel and duration thresholds (`min_silence_seconds=0.5s`, `long_pause_seconds=2.0s`).
  * Calculates total silence duration, pause count, average pause duration, and long pause count.
  * *Limitation note*: Energy-based silence detection can be influenced by microphone gain and ambient background noise.
* **Voice Pitch Analysis (`praat-parselmouth`)**:
  * Extracts physical fundamental frequency ($F_0$) metrics (mean, min, max, standard deviation) from voiced segments using Praat algorithms.
  * Audio with insufficient voiced segments returns `insufficient_voiced_segments` or `unavailable` gracefully without failing the request.
  * Strictly restricted to acoustic frequency measurements; never makes personality or emotional inferences.
* **Strict Separation of Concerns**: Speech delivery mechanics (speed, fluency, pauses, pitch) are analyzed independently of answer-content correctness.

---

## 📁 Architecture Overview

```text
backend/
├── alembic/                                # Database migration scripts
│   ├── env.py                              # Async migration engine
│   └── versions/                           # Versioned schema migrations
├── app/
│   ├── main.py                             # FastAPI application factory & lifespan
│   ├── config.py                           # Pydantic Settings (.env loader)
│   ├── api/
│   │   ├── deps.py                         # Dependency injection (DB session, current user)
│   │   └── v1/
│   │       ├── api_router.py               # Master v1 router aggregation
│   │       └── endpoints/
│   │           ├── auth.py                 # Register, login, refresh, logout, profile
│   │           ├── health.py               # Database & system health checks
│   │           ├── interviews.py           # Creation, starting, current, next, complete
│   │           └── audio.py                # Audio upload, analysis, metadata, transcript, report
│   ├── core/
│   │   ├── security.py                     # Argon2id hasher, JWT encoder/decoder
│   │   ├── exceptions.py                   # Custom exceptions & RFC-compliant handler
│   │   └── logging.py                      # Structured logging configuration
│   ├── db/
│   │   ├── base.py                         # DeclarativeBase, UUID & Timestamp mixins
│   │   ├── session.py                      # Async engine & sessionmaker (PRAGMA foreign keys)
│   │   └── seed.py                         # Question bank seeder utility
│   ├── engines/
│   │   ├── question_gen/
│   │   │   ├── adaptive_engine.py          # Performance-based adaptive difficulty selector
│   │   │   └── question_bank.py            # Curated seed question bank with rubrics
│   │   └── speech/
│   │       ├── audio_preprocessor.py       # 16 kHz mono float32 audio loader & resampler
│   │       ├── compat.py                   # PyAV compatibility patch for av.open
│   │       ├── transcriber.py              # faster-whisper INT8 lazy singleton transcriber
│   │       ├── speed_analyzer.py           # Speaking speed & Words Per Minute (WPM)
│   │       ├── filler_detector.py          # Word-boundary filler word detector
│   │       ├── silence_detector.py         # Frame-level energy pause & silence detector
│   │       ├── pitch_analyzer.py           # Parselmouth F0 fundamental frequency extractor
│   │       └── analyzer.py                 # Speech analysis orchestrator pipeline
│   ├── models/
│   │   ├── user.py                         # User & RefreshToken models
│   │   ├── interview.py                    # Interview session model
│   │   ├── question.py                     # Question bank entity
│   │   ├── interview_question.py           # Sequence and score junction model
│   │   ├── recording.py                    # Audio recording metadata & file model
│   │   └── speech_analysis.py              # Speech delivery metrics model
│   ├── schemas/
│   │   ├── auth.py                         # Authentication Pydantic v2 schemas
│   │   ├── interview.py                    # Interview & question Pydantic v2 schemas
│   │   └── audio.py                        # Audio & speech report Pydantic v2 schemas
│   └── services/
│       ├── auth_service.py                 # Authentication & token rotation logic
│       ├── interview_service.py            # Interview lifecycle & adaptive sequencing
│       └── audio_service.py                # Chunked upload, validation, cleanup & analysis
├── storage/
│   └── recordings/                         # Secure audio recordings directory (gitignored)
├── tests/
│   ├── conftest.py                         # In-memory SQLite async test fixtures
│   ├── unit/
│   │   ├── test_security.py                # Security & token unit tests
│   │   ├── test_adaptive_engine.py         # Adaptive difficulty & category unit tests
│   │   └── test_speech_engine.py           # Speed, filler, silence, pitch, compat unit tests
│   └── integration/
│       ├── test_auth_api.py                # Authentication endpoint integration tests
│       ├── test_interviews_api.py          # Interview progression & state guard tests
│       └── test_audio_api.py               # Audio upload, analysis, cleanup & report tests
├── .env.example                            # Environment variable template
├── alembic.ini                             # Migration configuration
├── pytest.ini                              # Pytest discovery settings
├── pyproject.toml                          # Project packaging & tool configs
├── requirements.txt                        # Production dependencies
└── requirements-dev.txt                    # Development & testing dependencies
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
python -m pytest -q
```

All 48 unit and integration tests pass (`48 passed` in the latest verified run) without downloading remote models.

---

## 📡 API Usage Examples

### Milestone 1: Authentication & Token Usage

#### Register & Login
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

Include the returned `access_token` in protected requests:
```bash
-H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

### Milestone 2: Interview Lifecycle & Adaptive Question Engine

#### 1. Configure a New Interview Session
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

#### 2. Start Interview & Receive Question 1
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

#### 3. Fetch Currently Active Question
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/interviews/7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4/questions/current" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

#### 4. Advance to Next Adaptive Question
Submit candidate answer score (e.g. `88.0`) to dynamically adjust difficulty:
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

#### 5. Conclude Interview Session
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

### Milestone 3: Audio & Speech Analysis API Examples

#### 1. Upload Candidate Audio Recording
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/upload" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "interview_id=7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4" \
  -F "file=@candidate_answer.wav"
```
**Response (201 Created):**
```json
{
  "id": "e2f1b4a3-7c8d-4912-b5e3-1a2b3c4d5e6f",
  "user_id": "e9b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "interview_id": "7b58c5f2-9cb8-4a9f-93d1-92b45e7f21a4",
  "interview_question_id": null,
  "original_filename": "candidate_answer.wav",
  "stored_filename": "c9d8e7f6-1234-5678-9abc-def012345678.wav",
  "audio_format": "wav",
  "file_size_bytes": 1048576,
  "duration_seconds": 32.5,
  "processing_status": "uploaded",
  "error_message": null,
  "created_at": "2026-11-24T19:50:00Z",
  "has_analysis": false
}
```

#### 2. Trigger Speech Delivery Analysis
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/e2f1b4a3-7c8d-4912-b5e3-1a2b3c4d5e6f/analyze" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
**Response (200 OK):**
```json
{
  "recording_id": "e2f1b4a3-7c8d-4912-b5e3-1a2b3c4d5e6f",
  "transcription": "Um, basically we should optimize our database queries with indexes, like you know, for better latency.",
  "detected_language": "en",
  "word_count": 16,
  "speaking_duration_seconds": 32.5,
  "words_per_minute": 29.5,
  "total_filler_words": 4,
  "filler_words_breakdown": {
    "um": 1,
    "basically": 1,
    "like": 1,
    "you know": 1,
    "uh": 0,
    "hmm": 0,
    "actually": 0,
    "i mean": 0
  },
  "filler_words_per_minute": 7.38,
  "pause_count": 3,
  "total_silence_seconds": 2.1,
  "average_pause_seconds": 0.7,
  "long_pause_count": 0,
  "average_pitch_hz": 218.4,
  "min_pitch_hz": 165.2,
  "max_pitch_hz": 268.0,
  "pitch_variation_hz": 24.1,
  "pitch_status": "measured",
  "processing_status": "completed",
  "error_message": null
}
```

#### 3. Get Segment-Level Transcript & Timestamps
Returns transcribed text along with segment-level timing entries (`start`, `end`, `text` per Whisper segment):
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/audio/e2f1b4a3-7c8d-4912-b5e3-1a2b3c4d5e6f/transcript" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

#### 4. Get Speech Delivery Report
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/audio/e2f1b4a3-7c8d-4912-b5e3-1a2b3c4d5e6f/report" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 🎯 Adaptive Engine Rules Reference

| Prior Answer Score | Difficulty Adjustment | Rationale |
|---|---|---|
| **$\ge$ 75.0** | **Step Up** (`easy` $\rightarrow$ `medium` $\rightarrow$ `hard`) | Demonstrates mastery; increases challenge to benchmark technical limits. |
| **50.0 – 74.9** | **Maintain** (Current Level) | Moderate competence; maintains current depth to consolidate assessment. |
| **< 50.0** | **Step Down** (`hard` $\rightarrow$ `medium` $\rightarrow$ `easy`) | Identifies knowledge boundaries; adjusts to foundational concepts. |

---

## ⚡ 8 GB RAM & Performance Considerations

* **Lazy Model Loading**: `faster-whisper` is loaded lazily on demand using a thread-safe singleton pattern (`SpeechTranscriber.get_model()`), so application startup does not load the transcription model into memory.
* **Quantized CPU Inference**: Models run on CPU with `int8` quantization (`WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, `WHISPER_MODEL_SIZE=tiny` by default) to reduce CPU and memory overhead on 8 GB RAM systems.
* **Non-Blocking Execution**: Synchronous audio analysis runs inside a worker thread via `asyncio.to_thread()`, keeping the async web server event loop responsive.
* **Deterministic Unit & Integration Tests**: Automated tests mock model inference or use small in-memory synthetic PCM waveforms, running completely offline without downloading model checkpoints.
* **Safe Storage**: Recordings are streamed in chunks, written with UUID filenames in `storage/recordings/` (ignored by git), and cleaned up automatically if persistence fails.
