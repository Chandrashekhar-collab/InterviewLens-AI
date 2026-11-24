"""Question SQLAlchemy model for curated interview questions."""

from typing import TYPE_CHECKING, Any, List
from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview_question import InterviewQuestion


class Question(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Question bank entity holding prompts, rubrics, and classification metadata."""

    __tablename__ = "questions"

    category: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=False,
    )
    target_roles: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    expected_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=120,
        nullable=False,
    )
    ideal_answer_rubric: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    keywords: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    interview_questions: Mapped[List["InterviewQuestion"]] = relationship(
        "InterviewQuestion",
        back_populates="question",
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} category={self.category} difficulty={self.difficulty}>"
