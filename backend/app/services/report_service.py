"""Consolidated interview performance report service."""

from typing import Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.interview import Interview
from app.models.interview_question import InterviewQuestion
from app.models.recording import AudioRecording
from app.schemas.audio import SpeechReportResponse
from app.schemas.evaluation import AnswerEvaluationResponse
from app.schemas.interview import InterviewResponse
from app.schemas.report import (
    InterviewPerformanceReportResponse,
    QuestionPerformanceItem,
)
from app.services.audio_service import AudioService


class ReportService:
    """Builds consolidated interview performance reports from existing DB records."""

    @classmethod
    def _deduplicate(cls, items: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @classmethod
    async def generate_interview_report(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> InterviewPerformanceReportResponse:
        """Compile a consolidated interview performance report with ownership validation."""
        query = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.interview_questions).selectinload(InterviewQuestion.question),
                selectinload(Interview.interview_questions).selectinload(InterviewQuestion.answer_evaluation),
                selectinload(Interview.recordings).selectinload(AudioRecording.speech_analysis),
            )
        )
        res = await db.execute(query)
        interview = res.scalar_one_or_none()

        if not interview:
            raise NotFoundException("Interview session not found")
        if interview.user_id != user_id:
            raise ForbiddenException("You do not have access to this interview session")

        # Map latest recording with speech analysis per interview_question_id
        recording_by_iq: Dict[uuid.UUID, AudioRecording] = {}
        for rec in sorted(interview.recordings, key=lambda r: r.created_at):
            if rec.interview_question_id is not None:
                recording_by_iq[rec.interview_question_id] = rec

        question_reports: List[QuestionPerformanceItem] = []
        scored_values: List[float] = []
        fluency_values: List[float] = []
        all_strengths: List[str] = []
        all_weaknesses: List[str] = []
        all_suggestions: List[str] = []

        for iq in sorted(interview.interview_questions, key=lambda q: q.order_index):
            eval_obj = iq.answer_evaluation
            eval_schema = AnswerEvaluationResponse.model_validate(eval_obj) if eval_obj else None

            rec = recording_by_iq.get(iq.id)
            speech_schema: Optional[SpeechReportResponse] = None
            if rec and rec.speech_analysis:
                speech_schema = AudioService.build_speech_report(rec.id, rec.speech_analysis)
                if speech_schema.fluency_score is not None:
                    fluency_values.append(speech_schema.fluency_score)

            submitted_answer: Optional[str] = None
            if eval_obj and eval_obj.submitted_answer_text:
                submitted_answer = eval_obj.submitted_answer_text
            elif rec and rec.speech_analysis and rec.speech_analysis.transcription:
                submitted_answer = rec.speech_analysis.transcription

            if iq.score is not None:
                scored_values.append(iq.score)

            if eval_obj:
                all_strengths.extend(eval_obj.strengths or [])
                if eval_obj.missing_concepts:
                    all_weaknesses.append(
                        f"Q{iq.order_index} missing concepts: {', '.join(eval_obj.missing_concepts[:5])}"
                    )
                if eval_obj.star_evaluation and eval_obj.star_evaluation.get("missing_components"):
                    missing_star = ", ".join(
                        c.capitalize() for c in eval_obj.star_evaluation["missing_components"]
                    )
                    all_weaknesses.append(f"Q{iq.order_index} missing STAR components: {missing_star}")
                if eval_obj.relevance_score < 50.0:
                    all_weaknesses.append(f"Q{iq.order_index} low prompt relevance ({eval_obj.relevance_score:.1f}/100)")
                all_suggestions.extend(eval_obj.improvement_suggestions or [])

            if speech_schema and speech_schema.processing_status == "completed":
                if (speech_schema.filler_words_per_minute or 0.0) > 6.0:
                    all_suggestions.append(
                        f"Q{iq.order_index} delivery: reduce filler words ({speech_schema.filler_words_per_minute:.1f}/min)."
                    )
                if (speech_schema.long_pause_count or 0) >= 2:
                    all_suggestions.append(
                        f"Q{iq.order_index} delivery: minimize extended pauses ({speech_schema.long_pause_count} pauses >= 2s)."
                    )

            question_reports.append(
                QuestionPerformanceItem(
                    interview_question_id=iq.id,
                    order_index=iq.order_index,
                    question_id=iq.question_id,
                    category=iq.question.category if iq.question else "unknown",
                    difficulty=iq.question.difficulty if iq.question else "unknown",
                    question_text=iq.question.question_text if iq.question else "",
                    is_answered=iq.is_answered,
                    score=iq.score,
                    submitted_answer=submitted_answer,
                    answer_evaluation=eval_schema,
                    speech_analysis=speech_schema,
                )
            )

        overall_score = round(sum(scored_values) / len(scored_values), 2) if scored_values else None
        avg_fluency = round(sum(fluency_values) / len(fluency_values), 2) if fluency_values else None

        interview_summary = InterviewResponse(
            id=interview.id,
            user_id=interview.user_id,
            title=interview.title,
            target_role=interview.target_role,
            interview_type=interview.interview_type,
            difficulty_level=interview.difficulty_level,
            experience_level=interview.experience_level,
            total_questions=interview.total_questions,
            status=interview.status,
            current_question_index=interview.current_question_index,
            started_at=interview.started_at,
            completed_at=interview.completed_at,
            created_at=interview.created_at,
            questions_answered_count=sum(1 for q in interview.interview_questions if q.is_answered),
        )

        return InterviewPerformanceReportResponse(
            interview=interview_summary,
            overall_interview_score=overall_score,
            average_fluency_score=avg_fluency,
            total_questions_asked=len(interview.interview_questions),
            total_questions_answered=sum(1 for q in interview.interview_questions if q.is_answered),
            total_questions_evaluated=sum(1 for q in interview.interview_questions if q.answer_evaluation is not None),
            question_reports=question_reports,
            strengths=cls._deduplicate(all_strengths),
            weaknesses=cls._deduplicate(all_weaknesses),
            improvement_suggestions=cls._deduplicate(all_suggestions),
        )
