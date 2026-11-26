"""Pydantic schemas for interview configuration, session management, and questions."""

from datetime import datetime
from typing import List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

InterviewTypeLiteral = Literal[
    "technical",
    "behavioral",
    "hr",
    "communication",
    "presentation",
    "mixed",
]

DifficultyLiteral = Literal["easy", "medium", "hard"]
ExperienceLiteral = Literal["entry", "mid", "senior", "lead"]
StatusLiteral = Literal["draft", "in_progress", "completed", "abandoned"]


class InterviewCreateRequest(BaseModel):
    """Schema for configuring a new interview session."""

    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Descriptive title for the interview session",
        examples=["Senior Backend Python Mock Interview"],
    )
    target_role: str = Field(
        "software_engineer",
        min_length=2,
        max_length=100,
        description="Target job title or profession",
        examples=["software_engineer"],
    )
    interview_type: InterviewTypeLiteral = Field(
        "mixed",
        description="Focus area: technical, behavioral, hr, communication, presentation, or mixed",
    )
    difficulty_level: DifficultyLiteral = Field(
        "medium",
        description="Base difficulty: easy, medium, or hard",
    )
    experience_level: ExperienceLiteral = Field(
        "mid",
        description="Target seniority level: entry, mid, senior, or lead",
    )
    total_questions: int = Field(
        5,
        ge=1,
        le=15,
        description="Total number of questions in this assessment (between 1 and 15)",
    )


class QuestionResponse(BaseModel):
    """Public representation of a question."""

    id: uuid.UUID
    category: str
    difficulty: str
    target_roles: List[str]
    question_text: str
    expected_duration_seconds: int

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionResponse(BaseModel):
    """Representation of an interview question link."""

    id: uuid.UUID
    interview_id: uuid.UUID
    question_id: uuid.UUID
    order_index: int
    is_answered: bool
    score: Optional[float] = None
    question: QuestionResponse

    model_config = ConfigDict(from_attributes=True)


class ActiveQuestionDetailResponse(BaseModel):
    """Details of the currently active question presented to the candidate."""

    interview_question_id: Optional[uuid.UUID] = None
    order_index: int
    total_questions: int
    is_last_question: bool
    question: QuestionResponse


class NextQuestionRequest(BaseModel):
    """Payload when advancing to the next adaptive question."""

    previous_answer_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Score of the answered question (0-100) to adjust adaptive difficulty",
        examples=[82.5],
    )


class InterviewResponse(BaseModel):
    """Detailed summary of an interview session."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    target_role: str
    interview_type: str
    difficulty_level: str
    experience_level: str
    total_questions: int
    status: str
    current_question_index: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    questions_answered_count: int = 0

    model_config = ConfigDict(from_attributes=True)
