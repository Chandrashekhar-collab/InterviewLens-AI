"""Audio recording and speech analysis API endpoints."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.audio import (
    AudioRecordingResponse,
    SpeechReportResponse,
    TranscriptResponse,
)
from app.services.audio_service import AudioService

router = APIRouter(prefix="/audio", tags=["Audio & Speech Analysis"])


@router.post(
    "/upload",
    response_model=AudioRecordingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload candidate audio response recording",
)
async def upload_audio(
    interview_id: uuid.UUID = Form(..., description="ID of the interview session"),
    interview_question_id: Optional[uuid.UUID] = Form(None, description="Optional ID of specific question"),
    file: UploadFile = File(..., description="Audio file in WAV, MP3, M4A, or WebM format"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AudioRecordingResponse:
    """Upload and securely store an audio recording for speech analysis."""
    recording = await AudioService.upload_audio(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
        interview_question_id=interview_question_id,
        file=file,
    )
    return AudioRecordingResponse(
        id=recording.id,
        user_id=recording.user_id,
        interview_id=recording.interview_id,
        interview_question_id=recording.interview_question_id,
        original_filename=recording.original_filename,
        stored_filename=recording.stored_filename,
        audio_format=recording.audio_format,
        file_size_bytes=recording.file_size_bytes,
        duration_seconds=recording.duration_seconds,
        processing_status=recording.processing_status,
        error_message=recording.error_message,
        created_at=recording.created_at,
        has_analysis=False,
    )


@router.post(
    "/{recording_id}/analyze",
    response_model=SpeechReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger speech analysis pipeline for a recording",
)
async def analyze_recording(
    recording_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SpeechReportResponse:
    """Run transcription, speed, filler word, pause, and pitch analysis on an uploaded recording."""
    analysis = await AudioService.analyze_recording(
        db=db,
        recording_id=recording_id,
        user_id=current_user.id,
    )
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
        processing_status=analysis.processing_status,
        error_message=analysis.error_message,
    )


@router.get(
    "/{recording_id}",
    response_model=AudioRecordingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audio recording metadata and status",
)
async def get_recording(
    recording_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AudioRecordingResponse:
    """Retrieve metadata and current processing status for a recording."""
    recording = await AudioService.get_recording(
        db=db,
        recording_id=recording_id,
        user_id=current_user.id,
    )
    return AudioRecordingResponse(
        id=recording.id,
        user_id=recording.user_id,
        interview_id=recording.interview_id,
        interview_question_id=recording.interview_question_id,
        original_filename=recording.original_filename,
        stored_filename=recording.stored_filename,
        audio_format=recording.audio_format,
        file_size_bytes=recording.file_size_bytes,
        duration_seconds=recording.duration_seconds,
        processing_status=recording.processing_status,
        error_message=recording.error_message,
        created_at=recording.created_at,
        has_analysis=recording.speech_analysis is not None,
    )


@router.get(
    "/{recording_id}/transcript",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transcription and word-level timing segments",
)
async def get_transcript(
    recording_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TranscriptResponse:
    """Retrieve transcribed text and time segments for an analyzed recording."""
    return await AudioService.get_transcript(
        db=db,
        recording_id=recording_id,
        user_id=current_user.id,
    )


@router.get(
    "/{recording_id}/report",
    response_model=SpeechReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get structured speech delivery analysis report",
)
async def get_speech_report(
    recording_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SpeechReportResponse:
    """Retrieve comprehensive speech analysis covering pace, pauses, fillers, and pitch."""
    return await AudioService.get_report(
        db=db,
        recording_id=recording_id,
        user_id=current_user.id,
    )
