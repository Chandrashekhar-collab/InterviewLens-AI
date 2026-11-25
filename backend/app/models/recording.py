"""AudioRecording SQLAlchemy model for uploaded candidate answers."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.interview_question import InterviewQuestion
    from app.models.speech_analysis import SpeechAnalysis
    from app.models.user import User


class AudioRecording(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores audio file metadata, storage location, and processing status."""

    __tablename__ = "audio_recordings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    interview_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    audio_format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",  # uploaded, processing, completed, failed
        index=True,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="recordings",
    )
    interview: Mapped["Interview"] = relationship(
        "Interview",
        back_populates="recordings",
    )
    interview_question: Mapped[Optional["InterviewQuestion"]] = relationship(
        "InterviewQuestion",
    )
    speech_analysis: Mapped[Optional["SpeechAnalysis"]] = relationship(
        "SpeechAnalysis",
        back_populates="recording",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<AudioRecording id={self.id} status={self.processing_status} format={self.audio_format}>"
