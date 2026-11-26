"""Pydantic v2 schemas for consolidated interview performance reports."""

from typing import List, Optional
import uuid
from pydantic import BaseModel, Field

from app.schemas.audio import SpeechReportResponse
from app.schemas.evaluation import AnswerEvaluationResponse
from app.schemas.interview import InterviewResponse


class QuestionPerformanceItem(BaseModel):
    """Per-question breakdown combining prompt, answer, evaluation, and speech delivery."""

    interview_question_id: uuid.UUID
    order_index: int
    question_id: uuid.UUID
    category: str
    difficulty: str
    question_text: str
    is_answered: bool
    score: Optional[float] = None
    submitted_answer: Optional[str] = None
    answer_evaluation: Optional[AnswerEvaluationResponse] = None
    speech_analysis: Optional[SpeechReportResponse] = None


class InterviewPerformanceReportResponse(BaseModel):
    """Consolidated end-of-interview performance report for candidate & exhibition review."""

    interview: InterviewResponse
    overall_interview_score: Optional[float] = None
    average_fluency_score: Optional[float] = None
    total_questions_asked: int
    total_questions_answered: int
    total_questions_evaluated: int
    question_reports: List[QuestionPerformanceItem] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
