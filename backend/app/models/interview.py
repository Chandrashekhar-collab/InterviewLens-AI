"""Interview session SQLAlchemy model."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview_question import InterviewQuestion
    from app.models.user import User


class Interview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Interview session entity tracking candidate session state and parameters."""

    __tablename__ = "interviews"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    target_role: Mapped[str] = mapped_column(
        String(100),
        default="software_engineer",
        nullable=False,
    )
    interview_type: Mapped[str] = mapped_column(
        String(50),
        default="mixed",
        nullable=False,
    )
    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )
    experience_level: Mapped[str] = mapped_column(
        String(20),
        default="mid",
        nullable=False,
    )
    total_questions: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",  # draft, in_progress, completed, abandoned
        index=True,
        nullable=False,
    )
    current_question_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="interviews",
    )
    interview_questions: Mapped[List["InterviewQuestion"]] = relationship(
        "InterviewQuestion",
        back_populates="interview",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InterviewQuestion.order_index",
    )

    def __repr__(self) -> str:
        return f"<Interview id={self.id} title={self.title} status={self.status}>"
