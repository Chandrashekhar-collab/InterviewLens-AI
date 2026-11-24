"""InterviewQuestion association entity linking an interview with chosen questions."""

from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import Boolean, Float, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.question import Question


class InterviewQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Junction entity recording sequential presentation and score per question in an interview."""

    __tablename__ = "interview_questions"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    is_answered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Relationships
    interview: Mapped["Interview"] = relationship(
        "Interview",
        back_populates="interview_questions",
    )
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="interview_questions",
    )

    def __repr__(self) -> str:
        return f"<InterviewQuestion id={self.id} interview_id={self.interview_id} order={self.order_index} answered={self.is_answered}>"
