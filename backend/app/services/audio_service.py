"""Audio service managing secure uploads, file validation, storage, and speech analysis execution."""

import asyncio
import os
from pathlib import Path
from typing import Optional, Tuple
import uuid
import wave
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.logging import logger
from app.engines.speech.analyzer import SpeechAnalysisPipeline
from app.models.interview import Interview
from app.models.interview_question import InterviewQuestion
from app.models.recording import AudioRecording
from app.models.speech_analysis import SpeechAnalysis
from app.schemas.audio import (
    AudioRecordingResponse,
    SpeechReportResponse,
    TranscriptResponse,
)


class AudioService:
    """Service handling audio file validation, storage, ownership, and analytical orchestration."""

    UPLOAD_CHUNK_SIZE: int = 64 * 1024  # 64 KB chunks for streaming uploads

    @classmethod
    def validate_audio_extension(cls, filename: str) -> Tuple[str, str]:
        """Validate audio file extension and return (ext, normalized_format_name)."""
        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
            allowed_str = ", ".join(settings.ALLOWED_AUDIO_EXTENSIONS)
            raise BadRequestException(
                f"Unsupported audio format '{ext}'. Allowed formats are: {allowed_str}"
            )
        return ext, ext.lstrip(".").lower()

    @classmethod
    def validate_magic_bytes(cls, ext: str, header: bytes) -> None:
        """Validate minimum header length and format-specific magic bytes."""
        if len(header) < 12:
            raise BadRequestException("Audio file is too small or corrupted")

        is_valid = False
        if ext == ".wav":
            # RIFF header with WAVE chunk
            if header.startswith(b"RIFF") and b"WAVE" in header[:12]:
                is_valid = True
        elif ext == ".mp3":
            # ID3 tag or MPEG audio sync frame
            if (
                header.startswith(b"ID3")
                or header.startswith(b"\xff\xfb")
                or header.startswith(b"\xff\xf3")
                or header.startswith(b"\xff\xf2")
            ):
                is_valid = True
        elif ext == ".m4a":
            # ISO Base Media File / QuickTime with ftyp
            if b"ftyp" in header[4:12]:
                is_valid = True
        elif ext == ".webm":
            # EBML header
            if header.startswith(b"\x1a\x45\xdf\xa3"):
                is_valid = True

        if not is_valid:
            raise BadRequestException(
                f"Corrupted or invalid audio file content for format '{ext}'"
            )

    @classmethod
    def validate_audio_file(cls, filename: str, content: bytes) -> str:
        """Validate file extension, file size, and magic byte headers.

        Supported formats: WAV, MP3, M4A, WebM.
        """
        # 1. Extension validation
        ext, format_name = cls.validate_audio_extension(filename)

        # 2. Size limit validation
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            raise BadRequestException(
                f"Audio file size exceeds maximum limit of {max_mb:.0f} MB"
            )

        # 3. Magic byte inspection
        cls.validate_magic_bytes(ext, content[:12])

        return format_name

    @classmethod
    def _cleanup_file(cls, file_path: Optional[Path]) -> None:
        """Safely remove an audio file from storage if it exists, logging cleanup errors."""
        if file_path is None:
            return
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as cleanup_exc:
            logger.error(
                f"Failed to clean up orphaned audio file '{file_path}': {cleanup_exc}",
                exc_info=True,
            )

    @classmethod
    def extract_audio_duration(cls, file_path: str) -> Optional[float]:
        """Attempt to extract audio duration in seconds from audio file header."""
        # Method 1: soundfile (fast, reliable for uncompressed/wav/flac)
        try:
            import soundfile as sf
            info = sf.info(file_path)
            if info.duration > 0:
                return round(float(info.duration), 2)
        except Exception:
            pass

        # Method 2: wave module for standard WAV
        try:
            with wave.open(file_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return round(float(frames / rate), 2)
        except Exception:
            pass

        # Method 3: mutagen
        try:
            import mutagen
            audio = mutagen.File(file_path)
            if audio is not None and audio.info and audio.info.length > 0:
                return round(float(audio.info.length), 2)
        except Exception:
            pass

        return None

    @classmethod
    async def upload_audio(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        interview_id: uuid.UUID,
        interview_question_id: Optional[uuid.UUID],
        file: UploadFile,
    ) -> AudioRecording:
        """Upload, validate, and securely store an audio recording."""
        # Verify interview ownership
        interview_query = select(Interview).where(Interview.id == interview_id)
        interview_res = await db.execute(interview_query)
        interview = interview_res.scalar_one_or_none()

        if not interview:
            raise NotFoundException("Interview session not found")
        if interview.user_id != user_id:
            raise ForbiddenException("You do not own this interview session")

        # Verify interview question link if provided
        if interview_question_id:
            iq_query = select(InterviewQuestion).where(
                InterviewQuestion.id == interview_question_id,
                InterviewQuestion.interview_id == interview_id,
            )
            iq_res = await db.execute(iq_query)
            iq = iq_res.scalar_one_or_none()
            if not iq:
                raise NotFoundException("Interview question not found or does not belong to this interview")

        # Read and validate in chunks so large files are never buffered in full
        filename = file.filename or "recording.wav"
        max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
        max_mb = max_bytes / (1024 * 1024)
        target_file_path: Optional[Path] = None

        try:
            ext, format_name = cls.validate_audio_extension(filename)

            header_buffer = bytearray()
            total_bytes = 0

            # Read enough bytes to validate minimum size and magic header without exceeding limit
            while len(header_buffer) < 12:
                remaining = max_bytes - total_bytes
                to_read = min(cls.UPLOAD_CHUNK_SIZE, max(remaining + 1, 1))
                chunk = await file.read(to_read)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise BadRequestException(
                        f"Audio file size exceeds maximum limit of {max_mb:.0f} MB"
                    )
                header_buffer.extend(chunk)

            cls.validate_magic_bytes(ext, bytes(header_buffer[:12]))

            # Ensure safe storage directory exists outside web root
            storage_path = Path(settings.RECORDINGS_DIR).resolve()
            storage_path.mkdir(parents=True, exist_ok=True)

            # Generate unique storage filename to prevent path traversal
            unique_filename = f"{uuid.uuid4()}{ext}"
            target_file_path = storage_path / unique_filename

            # Stream remaining chunks directly to disk while enforcing size limit
            with open(target_file_path, "wb") as f:
                f.write(header_buffer)
                while True:
                    remaining = max_bytes - total_bytes
                    to_read = min(cls.UPLOAD_CHUNK_SIZE, max(remaining + 1, 1))
                    chunk = await file.read(to_read)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise BadRequestException(
                            f"Audio file size exceeds maximum limit of {max_mb:.0f} MB"
                        )
                    f.write(chunk)

            # Measure audio duration
            duration = cls.extract_audio_duration(str(target_file_path))

            # Create AudioRecording model
            recording = AudioRecording(
                user_id=user_id,
                interview_id=interview_id,
                interview_question_id=interview_question_id,
                original_filename=file.filename or unique_filename,
                stored_filename=unique_filename,
                file_path=str(target_file_path),
                audio_format=format_name,
                file_size_bytes=total_bytes,
                duration_seconds=duration,
                processing_status="uploaded",
            )

            db.add(recording)
            await db.commit()
            await db.refresh(recording)
            return recording

        except Exception:
            try:
                await db.rollback()
            except Exception as rollback_exc:
                logger.error(f"Database rollback failed after upload error: {rollback_exc}", exc_info=True)
            cls._cleanup_file(target_file_path)
            raise
        finally:
            try:
                await file.close()
            except Exception as close_exc:
                logger.warning(f"Failed to close uploaded audio file handle: {close_exc}")

    @classmethod
    async def get_recording(
        cls,
        db: AsyncSession,
        recording_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AudioRecording:
        """Fetch recording by ID and verify authenticated user ownership."""
        query = (
            select(AudioRecording)
            .where(AudioRecording.id == recording_id)
            .options(selectinload(AudioRecording.speech_analysis))
        )
        res = await db.execute(query)
        recording = res.scalar_one_or_none()

        if not recording:
            raise NotFoundException("Audio recording not found")
        if recording.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this recording")

        return recording

    @classmethod
    async def analyze_recording(
        cls,
        db: AsyncSession,
        recording_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeechAnalysis:
        """Execute speech delivery analysis pipeline on the recording."""
        recording = await cls.get_recording(db=db, recording_id=recording_id, user_id=user_id)

        # Verify file exists on disk
        if not os.path.exists(recording.file_path):
            recording.processing_status = "failed"
            recording.error_message = "Audio recording file missing from storage"
            await db.commit()
            raise NotFoundException("Audio file is missing from storage")

        recording.processing_status = "processing"
        await db.commit()

        # Execute analytical pipeline in a worker thread to avoid blocking the async event loop.
        # Pass only plain scalar values; keep AsyncSession operations strictly on the event loop.
        audio_path = recording.file_path
        audio_duration_seconds = recording.duration_seconds
        pipeline = SpeechAnalysisPipeline()
        try:
            results = await asyncio.to_thread(
                pipeline.analyze_audio,
                audio_path=audio_path,
                audio_duration_seconds=audio_duration_seconds,
            )

            # Update duration if was previously null
            if recording.duration_seconds is None and results.get("speaking_duration_seconds"):
                recording.duration_seconds = results["speaking_duration_seconds"]

            # Save or update SpeechAnalysis entity
            if recording.speech_analysis:
                analysis = recording.speech_analysis
                for key, val in results.items():
                    if hasattr(analysis, key):
                        setattr(analysis, key, val)
            else:
                analysis = SpeechAnalysis(
                    recording_id=recording.id,
                    **results,
                )
                db.add(analysis)

            recording.processing_status = results.get("processing_status", "completed")
            recording.error_message = results.get("error_message")

            await db.commit()
            await db.refresh(analysis)
            return analysis

        except Exception as exc:
            logger.error(f"Speech analysis failed for recording {recording_id}: {exc}", exc_info=True)
            recording.processing_status = "failed"
            recording.error_message = str(exc)
            await db.commit()
            raise

    @classmethod
    async def get_transcript(
        cls,
        db: AsyncSession,
        recording_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TranscriptResponse:
        """Retrieve transcription text and timing segments for a recording."""
        recording = await cls.get_recording(db=db, recording_id=recording_id, user_id=user_id)

        if not recording.speech_analysis:
            raise NotFoundException(
                "Transcript not available. Recording has not been analyzed yet."
            )

        analysis = recording.speech_analysis
        return TranscriptResponse(
            recording_id=recording.id,
            transcription=analysis.transcription,
            detected_language=analysis.detected_language,
            transcription_status=analysis.transcription_status,
            transcription_duration_seconds=analysis.transcription_duration_seconds,
            word_count=analysis.word_count,
            segments=analysis.segments or [],
        )

    @classmethod
    def compute_fluency_score(cls, analysis: SpeechAnalysis) -> Optional[float]:
        """Compute a deterministic 0-100 speech fluency score from pace, fillers, and long pauses."""
        if analysis.processing_status != "completed" or analysis.words_per_minute is None:
            return None

        score = 100.0
        wpm = analysis.words_per_minute
        if wpm == 0.0:
            return 0.0
        if wpm < 110.0:
            score -= min(30.0, (110.0 - wpm) * 0.4)
        elif wpm > 160.0:
            score -= min(25.0, (wpm - 160.0) * 0.35)

        filler_wpm = analysis.filler_words_per_minute or 0.0
        score -= min(35.0, filler_wpm * 3.0)

        long_pauses = analysis.long_pause_count or 0
        score -= min(25.0, long_pauses * 5.0)

        return round(max(0.0, min(100.0, score)), 2)

    @classmethod
    def build_speech_report(
        cls,
        recording_id: uuid.UUID,
        analysis: SpeechAnalysis,
    ) -> SpeechReportResponse:
        """Build a SpeechReportResponse from a SpeechAnalysis ORM entity."""
        return SpeechReportResponse(
            recording_id=recording_id,
            transcription=analysis.transcription,
            detected_language=analysis.detected_language,
            word_count=analysis.word_count,
            speaking_duration_seconds=analysis.speaking_duration_seconds,
            words_per_minute=analysis.words_per_minute,
            total_filler_words=analysis.total_filler_words,
            filler_words_breakdown=analysis.filler_words_breakdown or {},
            filler_words_per_minute=analysis.filler_words_per_minute,
            pause_count=analysis.pause_count,
            total_silence_seconds=analysis.total_silence_seconds,
            average_pause_seconds=analysis.average_pause_seconds,
            long_pause_count=analysis.long_pause_count,
            average_pitch_hz=analysis.average_pitch_hz,
            min_pitch_hz=analysis.min_pitch_hz,
            max_pitch_hz=analysis.max_pitch_hz,
            pitch_variation_hz=analysis.pitch_variation_hz,
            pitch_status=analysis.pitch_status,
            fluency_score=cls.compute_fluency_score(analysis),
            processing_status=analysis.processing_status,
            error_message=analysis.error_message,
        )

    @classmethod
    async def get_report(
        cls,
        db: AsyncSession,
        recording_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeechReportResponse:
        """Retrieve complete structured speech delivery report."""
        recording = await cls.get_recording(db=db, recording_id=recording_id, user_id=user_id)

        if not recording.speech_analysis:
            raise NotFoundException(
                "Speech delivery report not available. Recording has not been analyzed yet."
            )

        return cls.build_speech_report(recording.id, recording.speech_analysis)
