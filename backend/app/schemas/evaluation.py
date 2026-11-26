"""Pydantic v2 schemas for answer evaluation and feedback endpoints."""

from datetime import datetime
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextAnswerEvaluationRequest(BaseModel):
    """Request payload for submitting a candidate text answer for evaluation."""

    interview_id: uuid.UUID = Field(..., description="ID of the interview session")
    interview_question_id: uuid.UUID = Field(..., description="ID of the interview question being answered")
    answer_text: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Candidate's written answer text",
    )
    re_evaluate: bool = Field(
        False,
        description="Set true to explicitly overwrite an existing evaluation for this question",
    )

    @field_validator("answer_text")
    @classmethod
    def validate_non_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("answer_text must not be empty or whitespace only")
        return stripped


class AudioAnswerEvaluationRequest(BaseModel):
    """Optional request payload when evaluating an uploaded audio recording's transcript."""

    interview_question_id: Optional[uuid.UUID] = Field(
        None,
        description="Optional interview question ID if not already linked on upload",
    )
    re_evaluate: bool = Field(
        False,
        description="Set true to explicitly overwrite an existing evaluation for this question",
    )


class STARComponentResult(BaseModel):
    """STAR-method evaluation details for behavioral questions."""

    applicable: bool
    score: Optional[float] = None
    components: Optional[Dict[str, bool]] = None
    missing_components: List[str] = Field(default_factory=list)


class AnswerEvaluationResponse(BaseModel):
    """Detailed answer evaluation scores, evidence, and actionable feedback."""

    id: uuid.UUID
    user_id: uuid.UUID
    interview_id: uuid.UUID
    interview_question_id: uuid.UUID
    audio_recording_id: Optional[uuid.UUID] = None
    answer_source: str
    submitted_answer_text: Optional[str] = None

    relevance_score: float
    keyword_coverage_score: float
    rubric_coverage_score: float
    completeness_score: float
    structure_score: float
    overall_score: float

    dimension_weights: Dict[str, float] = Field(default_factory=dict)
    matched_keywords: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    star_evaluation: Optional[STARComponentResult] = None
    summary: Optional[str] = None
    evaluation_method: str

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewEvaluationHistoryResponse(BaseModel):
    """Summary and chronological history of answer evaluations for an interview."""

    interview_id: uuid.UUID
    total_evaluated: int
    average_score: Optional[float] = None
    evaluations: List[AnswerEvaluationResponse] = Field(default_factory=list)
