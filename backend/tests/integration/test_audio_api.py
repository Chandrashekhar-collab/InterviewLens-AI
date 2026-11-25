"""Integration tests for audio recording upload, validation, access control, and speech analysis."""

import asyncio
import io
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.services.audio_service import AudioService
from tests.unit.test_speech_engine import generate_synthetic_wav_bytes


async def get_authenticated_headers(client: AsyncClient, email: str, name: str) -> dict:
    """Helper to register and login a user and return the Bearer authorization headers."""
    reg_payload = {
        "email": email,
        "password": "Password12345!",
        "full_name": name,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password12345!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_valid_audio_upload(client: AsyncClient):
    """Test 1: Verify valid WAV upload creates AudioRecording record."""
    headers = await get_authenticated_headers(client, "uploader@example.com", "Uploader User")

    # Create interview session first
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Audio Test Interview", "total_questions": 3},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0)
    files = {"file": ("response.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"interview_id": interview_id}

    response = await client.post("/api/v1/audio/upload", data=data, files=files, headers=headers)
    assert response.status_code == 201
    rec_data = response.json()

    assert rec_data["original_filename"] == "response.wav"
    assert rec_data["audio_format"] == "wav"
    assert rec_data["processing_status"] == "uploaded"
    assert rec_data["file_size_bytes"] == len(wav_bytes)
    assert "file_path" not in rec_data  # Internal path must never be exposed


@pytest.mark.asyncio
async def test_invalid_extension_upload(client: AsyncClient):
    """Test 2: Verify upload with invalid file extension is rejected with 400."""
    headers = await get_authenticated_headers(client, "inval_ext@example.com", "Invalid Ext")

    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Extension Guard", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    files = {"file": ("payload.exe", io.BytesIO(b"MZfakebinarycontent"), "application/octet-stream")}
    data = {"interview_id": interview_id}

    response = await client.post("/api/v1/audio/upload", data=data, files=files, headers=headers)
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_corrupted_magic_bytes_upload(client: AsyncClient):
    """Test 3: Verify file with .wav extension but corrupted content is rejected."""
    headers = await get_authenticated_headers(client, "corrupted@example.com", "Corrupted User")

    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Corrupted Guard", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    # Spoofed extension with non-WAV bytes
    files = {"file": ("fake.wav", io.BytesIO(b"FAKE_NOT_WAV_HEADER_DATA_PADDING"), "audio/wav")}
    data = {"interview_id": interview_id}

    response = await client.post("/api/v1/audio/upload", data=data, files=files, headers=headers)
    assert response.status_code == 400
    assert "invalid audio file content" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_oversized_audio_upload(client: AsyncClient):
    """Test 4: Verify oversized audio upload is rejected."""
    headers = await get_authenticated_headers(client, "oversized@example.com", "Oversized User")

    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Oversized Guard", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    # Mock settings.MAX_UPLOAD_SIZE_BYTES to 100 bytes for test
    with patch("app.services.audio_service.settings.MAX_UPLOAD_SIZE_BYTES", 100):
        wav_bytes = generate_synthetic_wav_bytes(duration_s=1.0)  # > 30KB
        files = {"file": ("oversized.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {"interview_id": interview_id}

        response = await client.post("/api/v1/audio/upload", data=data, files=files, headers=headers)
        assert response.status_code == 400
        assert "exceeds maximum limit" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_unauthorized_upload(client: AsyncClient):
    """Test 5: Verify upload without authentication is rejected with 401."""
    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.0)
    files = {"file": ("unauth.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"interview_id": "00000000-0000-0000-0000-000000000000"}

    response = await client.post("/api/v1/audio/upload", data=data, files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_another_user_recording(client: AsyncClient):
    """Test 6: Verify User B cannot access User A's recording (403 Forbidden)."""
    headers_a = await get_authenticated_headers(client, "owner_a@example.com", "Owner A")
    headers_b = await get_authenticated_headers(client, "intruder_b@example.com", "Intruder B")

    # User A creates interview and uploads recording
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "User A Interview", "total_questions": 2},
        headers=headers_a,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.5)
    files = {"file": ("private.wav", io.BytesIO(wav_bytes), "audio/wav")}
    upload_res = await client.post(
        "/api/v1/audio/upload",
        data={"interview_id": interview_id},
        files=files,
        headers=headers_a,
    )
    recording_id = upload_res.json()["id"]

    # User B attempts to access recording -> 403 Forbidden
    get_res = await client.get(f"/api/v1/audio/{recording_id}", headers=headers_b)
    assert get_res.status_code == 403

    # User B attempts to trigger analysis -> 403 Forbidden
    analyze_res = await client.post(f"/api/v1/audio/{recording_id}/analyze", headers=headers_b)
    assert analyze_res.status_code == 403


@pytest.mark.asyncio
async def test_speech_analysis_and_report_generation(client: AsyncClient):
    """Test 7, 8, 9, 10, 12: Verify full analysis execution, transcription, speed, fillers, and report."""
    headers = await get_authenticated_headers(client, "speech_user@example.com", "Speech Candidate")

    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Speech Analysis Mock", "total_questions": 3},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=3.0, freq_hz=220.0, silence_end_s=1.0)
    files = {"file": ("answer.wav", io.BytesIO(wav_bytes), "audio/wav")}
    upload_res = await client.post(
        "/api/v1/audio/upload",
        data={"interview_id": interview_id},
        files=files,
        headers=headers,
    )
    recording_id = upload_res.json()["id"]

    # Mock transcription result to avoid model download in tests
    mock_transcription = {
        "transcription": "Um, basically we should optimize the cache, like you know, for better latency.",
        "detected_language": "en",
        "segments": [{"start": 0.0, "end": 2.0, "text": "Um basically we should optimize the cache"}],
        "transcription_status": "completed",
        "transcription_duration_seconds": 0.45,
        "error_message": None,
    }

    with patch("app.engines.speech.analyzer.SpeechTranscriber.transcribe", return_value=mock_transcription):
        analyze_res = await client.post(f"/api/v1/audio/{recording_id}/analyze", headers=headers)
        assert analyze_res.status_code == 200
        report = analyze_res.json()

        assert report["recording_id"] == recording_id
        assert report["transcription"] == mock_transcription["transcription"]
        assert report["detected_language"] == "en"
        assert report["word_count"] == 13
        assert report["words_per_minute"] > 0.0
        assert report["total_filler_words"] >= 3  # "um", "basically", "like", "you know"
        assert report["pause_count"] >= 0
        assert report["processing_status"] == "completed"

    # Fetch transcript endpoint
    transcript_res = await client.get(f"/api/v1/audio/{recording_id}/transcript", headers=headers)
    assert transcript_res.status_code == 200
    assert transcript_res.json()["transcription"] == mock_transcription["transcription"]

    # Fetch report endpoint
    report_res = await client.get(f"/api/v1/audio/{recording_id}/report", headers=headers)
    assert report_res.status_code == 200
    assert report_res.json()["words_per_minute"] == report["words_per_minute"]


@pytest.mark.asyncio
async def test_transcription_failure_handling_in_pipeline(client: AsyncClient):
    """Test 6 & 11: Verify pipeline handles transcription failure gracefully without server error."""
    headers = await get_authenticated_headers(client, "fail_user@example.com", "Failure Candidate")

    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Failure Handing", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0)
    files = {"file": ("fail.wav", io.BytesIO(wav_bytes), "audio/wav")}
    upload_res = await client.post(
        "/api/v1/audio/upload",
        data={"interview_id": interview_id},
        files=files,
        headers=headers,
    )
    recording_id = upload_res.json()["id"]

    mock_failure = {
        "transcription": None,
        "detected_language": None,
        "segments": [],
        "transcription_status": "failed",
        "transcription_duration_seconds": 0.1,
        "error_message": "Audio decoder failed on corrupted frame",
    }

    with patch("app.engines.speech.analyzer.SpeechTranscriber.transcribe", return_value=mock_failure):
        analyze_res = await client.post(f"/api/v1/audio/{recording_id}/analyze", headers=headers)
        assert analyze_res.status_code == 200
        data = analyze_res.json()
        assert data["processing_status"] == "failed"
        assert "Audio decoder failed" in data["error_message"]
        assert data["word_count"] is None
        assert data["words_per_minute"] is None
        assert data["total_filler_words"] is None


@pytest.mark.asyncio
async def test_oversized_chunked_upload_stops_early_and_closes_file(client: AsyncClient, db_session, tmp_path):
    """Verify oversized uploads read in chunks, stop immediately at limit, close file, and leave no orphan."""
    headers = await get_authenticated_headers(client, "chunked_over@example.com", "Chunked User")
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Chunked Limit Test", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.0)  # ~44 KB
    assert len(wav_bytes) > 5000

    # Spy file-like object tracking chunk reads and close()
    class SpyUploadFile:
        def __init__(self, payload: bytes, filename: str):
            self._stream = io.BytesIO(payload)
            self.filename = filename
            self.read_calls = []
            self.bytes_read = 0
            self.closed = False

        async def read(self, size: int = -1) -> bytes:
            self.read_calls.append(size)
            data = self._stream.read(size)
            self.bytes_read += len(data)
            return data

        async def close(self) -> None:
            self.closed = True

    spy_file = SpyUploadFile(wav_bytes, "chunked_oversized.wav")

    # Fetch interview owner user_id from DB
    from sqlalchemy import select
    from app.models.interview import Interview
    import uuid

    res = await db_session.execute(select(Interview).where(Interview.id == uuid.UUID(interview_id)))
    interview = res.scalar_one()

    with (
        patch("app.services.audio_service.settings.MAX_UPLOAD_SIZE_BYTES", 300),
        patch("app.services.audio_service.settings.RECORDINGS_DIR", str(tmp_path)),
        patch.object(AudioService, "UPLOAD_CHUNK_SIZE", 128),
    ):
        with pytest.raises(Exception) as exc_info:
            await AudioService.upload_audio(
                db=db_session,
                user_id=interview.user_id,
                interview_id=interview.id,
                interview_question_id=None,
                file=spy_file,  # type: ignore[arg-type]
            )
        assert "exceeds maximum limit" in str(exc_info.value)

    # Stopped reading immediately once > 300 bytes were read (never read full ~44 KB file)
    assert spy_file.bytes_read <= 301
    assert len(spy_file.read_calls) >= 2
    assert all(0 < s <= 128 for s in spy_file.read_calls)
    assert spy_file.closed is True
    # No orphaned partial file left on disk
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_storage_cleanup_on_database_failure(client: AsyncClient, db_session, tmp_path):
    """Verify orphaned audio file is removed when DB commit fails, and cleanup errors are handled safely."""
    headers = await get_authenticated_headers(client, "db_fail@example.com", "DB Fail User")
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Cleanup Test", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.0)
    files = {"file": ("cleanup.wav", io.BytesIO(wav_bytes), "audio/wav")}

    with (
        patch("app.services.audio_service.settings.RECORDINGS_DIR", str(tmp_path)),
        patch.object(db_session, "commit", new=AsyncMock(side_effect=SQLAlchemyError("DB write failed"))),
    ):
        with pytest.raises(SQLAlchemyError):
            await client.post(
                "/api/v1/audio/upload",
                data={"interview_id": interview_id},
                files=files,
                headers=headers,
            )

    # File was written before commit, then cleaned up after commit failed
    assert list(tmp_path.iterdir()) == []

    # Also verify _cleanup_file handles unlink errors safely without raising
    with patch.object(Path, "exists", return_value=True), patch.object(
        Path, "unlink", side_effect=OSError("Permission denied")
    ):
        AudioService._cleanup_file(tmp_path / "locked.wav")


@pytest.mark.asyncio
async def test_speech_analysis_non_blocking_event_loop(client: AsyncClient, tmp_path):
    """Verify SpeechAnalysisPipeline.analyze_audio runs in a worker thread without blocking the event loop."""
    headers = await get_authenticated_headers(client, "nonblock@example.com", "Async User")
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Non-blocking Test", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.5)
    files = {"file": ("async_test.wav", io.BytesIO(wav_bytes), "audio/wav")}

    with patch("app.services.audio_service.settings.RECORDINGS_DIR", str(tmp_path)):
        upload_res = await client.post(
            "/api/v1/audio/upload",
            data={"interview_id": interview_id},
            files=files,
            headers=headers,
        )
        assert upload_res.status_code == 201
        recording_id = upload_res.json()["id"]

    main_thread_id = threading.get_ident()
    worker_thread_ids = []
    heartbeat_ticks = 0
    analysis_done = asyncio.Event()

    def slow_sync_pipeline(audio_path: str, audio_duration_seconds=None):
        worker_thread_ids.append(threading.get_ident())
        time.sleep(0.15)
        return {
            "transcription": "Hello world from worker thread.",
            "detected_language": "en",
            "transcription_status": "completed",
            "transcription_duration_seconds": 0.15,
            "segments": [{"start": 0.0, "end": 1.0, "text": "Hello world from worker thread."}],
            "word_count": 5,
            "speaking_duration_seconds": 1.5,
            "words_per_minute": 200.0,
            "total_filler_words": 0,
            "filler_words_breakdown": {},
            "filler_words_per_minute": 0.0,
            "pause_count": 0,
            "total_silence_seconds": 0.0,
            "average_pause_seconds": 0.0,
            "long_pause_count": 0,
            "average_pitch_hz": 150.0,
            "min_pitch_hz": 120.0,
            "max_pitch_hz": 180.0,
            "pitch_variation_hz": 15.0,
            "pitch_status": "completed",
            "processing_status": "completed",
            "error_message": None,
        }

    async def heartbeat():
        nonlocal heartbeat_ticks
        while not analysis_done.is_set():
            heartbeat_ticks += 1
            await asyncio.sleep(0.02)

    with patch("app.services.audio_service.SpeechAnalysisPipeline.analyze_audio", side_effect=slow_sync_pipeline):
        hb_task = asyncio.create_task(heartbeat())
        try:
            analyze_res = await client.post(f"/api/v1/audio/{recording_id}/analyze", headers=headers)
        finally:
            analysis_done.set()
            await hb_task

    assert analyze_res.status_code == 200
    assert analyze_res.json()["processing_status"] == "completed"
    assert len(worker_thread_ids) == 1
    assert worker_thread_ids[0] != main_thread_id
    # Event loop remained responsive while synchronous analysis ran on worker thread
    assert heartbeat_ticks >= 3
