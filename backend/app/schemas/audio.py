"""Pydantic schemas for audio recording management and speech analysis reporting."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class AudioRecordingResponse(BaseModel):
    """Public representation of an uploaded audio recording without internal paths."""

    id: uuid.UUID
    user_id: uuid.UUID
    interview_id: uuid.UUID
    interview_question_id: Optional[uuid.UUID] = None
    original_filename: str
    stored_filename: str
    audio_format: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    processing_status: str
    error_message: Optional[str] = None
    created_at: datetime
    has_analysis: bool = False

    model_config = ConfigDict(from_attributes=True)


class TranscriptResponse(BaseModel):
    """Transcription text and word-level segment timings."""

    recording_id: uuid.UUID
    transcription: Optional[str] = None
    detected_language: Optional[str] = None
    transcription_status: str
    transcription_duration_seconds: Optional[float] = None
    word_count: Optional[int] = None
    segments: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SpeechReportResponse(BaseModel):
    """Complete speech delivery assessment report covering pace, fluency, pauses, and pitch."""

    recording_id: uuid.UUID
    transcription: Optional[str] = None
    detected_language: Optional[str] = None

    # Delivery & Pace
    word_count: Optional[int] = None
    speaking_duration_seconds: Optional[float] = None
    words_per_minute: Optional[float] = None

    # Disfluency & Filler Words
    total_filler_words: Optional[int] = None
    filler_words_breakdown: Dict[str, int] = Field(default_factory=dict)
    filler_words_per_minute: Optional[float] = None

    # Silence & Hesitation
    pause_count: Optional[int] = None
    total_silence_seconds: Optional[float] = None
    average_pause_seconds: Optional[float] = None
    long_pause_count: Optional[int] = None

    # Pitch & Acoustic Frequency
    average_pitch_hz: Optional[float] = None
    min_pitch_hz: Optional[float] = None
    max_pitch_hz: Optional[float] = None
    pitch_variation_hz: Optional[float] = None
    pitch_status: str = "pending"

    # Derived Fluency Score (0-100)
    fluency_score: Optional[float] = None

    # Status
    processing_status: str
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
