"""AnswerEvaluation SQLAlchemy model storing deterministic answer evaluation and feedback."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.interview_question import InterviewQuestion
    from app.models.recording import AudioRecording
    from app.models.user import User


class AnswerEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores content evaluation scores, STAR results, and feedback for an interview question answer."""

    __tablename__ = "answer_evaluations"

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
    interview_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    audio_recording_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audio_recordings.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Answer source & non-duplicated text storage
    answer_source: Mapped[str] = mapped_column(
        String(30),
        default="text",  # text or audio_transcript
        nullable=False,
    )
    submitted_answer_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,  # Populated for text submissions; NULL for audio_transcript to avoid duplication
    )

    # Dimension scores (0-100)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    keyword_coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    rubric_coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    structure_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Transparent weights, evidence, and feedback
    dimension_weights: Mapped[Dict[str, float]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    matched_keywords: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    missing_concepts: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    strengths: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    improvement_suggestions: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    star_evaluation: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    evaluation_method: Mapped[str] = mapped_column(
        String(50),
        default="heuristic-v1.0",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    interview: Mapped["Interview"] = relationship(
        "Interview",
        back_populates="answer_evaluations",
    )
    interview_question: Mapped["InterviewQuestion"] = relationship(
        "InterviewQuestion",
        back_populates="answer_evaluation",
    )
    audio_recording: Mapped[Optional["AudioRecording"]] = relationship("AudioRecording")

    def __repr__(self) -> str:
        return (
            f"<AnswerEvaluation id={self.id} interview_question_id={self.interview_question_id} "
            f"overall_score={self.overall_score}>"
        )
