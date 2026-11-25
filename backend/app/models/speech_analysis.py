"""SpeechAnalysis SQLAlchemy model holding transcription, speed, fluency, and acoustic metrics."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.recording import AudioRecording


class SpeechAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Analysis results covering speech delivery, speed, filler words, pauses, and pitch."""

    __tablename__ = "speech_analyses"

    recording_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audio_recordings.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Transcription metrics
    transcription: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    detected_language: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    transcription_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, completed, failed
        nullable=False,
    )
    transcription_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    segments: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )

    # Speaking speed metrics
    word_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    speaking_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    words_per_minute: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Filler words metrics
    total_filler_words: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    filler_words_breakdown: Mapped[Optional[Dict[str, int]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    filler_words_per_minute: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Pause and silence metrics
    pause_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    total_silence_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    average_pause_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    long_pause_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Pitch metrics
    average_pitch_hz: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    min_pitch_hz: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    max_pitch_hz: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    pitch_variation_hz: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    pitch_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # measured, insufficient_voiced_segments, unavailable
        nullable=False,
    )

    # Status tracking
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, processing, completed, failed
        index=True,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    recording: Mapped["AudioRecording"] = relationship(
        "AudioRecording",
        back_populates="speech_analysis",
    )

    def __repr__(self) -> str:
        return f"<SpeechAnalysis id={self.id} recording_id={self.recording_id} wpm={self.words_per_minute}>"
