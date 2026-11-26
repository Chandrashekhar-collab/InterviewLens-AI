"""Service layer orchestrating answer evaluation, persistence, and interview integration."""

from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.engines.answer_evaluation import AnswerEvaluationPipeline
from app.models.answer_evaluation import AnswerEvaluation
from app.models.interview import Interview
from app.models.interview_question import InterviewQuestion
from app.models.recording import AudioRecording
from app.schemas.evaluation import (
    AudioAnswerEvaluationRequest,
    TextAnswerEvaluationRequest,
)


class EvaluationService:
    """Handles answer evaluation for text submissions and completed audio transcripts."""

    ALLOWED_INTERVIEW_STATUSES = {"in_progress"}

    @classmethod
    async def _get_owned_interview(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        result = await db.execute(select(Interview).where(Interview.id == interview_id))
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundException("Interview session not found")
        if interview.user_id != user_id:
            raise ForbiddenException("You do not have access to this interview session")
        return interview

    @classmethod
    async def _get_interview_question(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        interview_question_id: uuid.UUID,
    ) -> InterviewQuestion:
        query = (
            select(InterviewQuestion)
            .where(
                InterviewQuestion.id == interview_question_id,
                InterviewQuestion.interview_id == interview_id,
            )
            .options(
                selectinload(InterviewQuestion.question),
                selectinload(InterviewQuestion.answer_evaluation),
            )
        )
        result = await db.execute(query)
        iq = result.scalar_one_or_none()
        if not iq or not iq.question:
            raise NotFoundException("Interview question not found for this interview session")
        return iq

    @classmethod
    async def _persist_evaluation(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        interview: Interview,
        iq: InterviewQuestion,
        answer_text: str,
        answer_source: str,
        audio_recording_id: Optional[uuid.UUID],
        re_evaluate: bool,
    ) -> AnswerEvaluation:
        if iq.answer_evaluation is not None and not re_evaluate:
            raise BadRequestException(
                "This interview question has already been evaluated. Set re_evaluate=true to re-evaluate."
            )

        eval_result = AnswerEvaluationPipeline.evaluate(
            answer_text=answer_text,
            question_text=iq.question.question_text,
            category=iq.question.category,
            ideal_answer_rubric=iq.question.ideal_answer_rubric,
            keywords=iq.question.keywords or [],
            expected_duration_seconds=iq.question.expected_duration_seconds,
        )

        stored_text = answer_text if answer_source == "text" else None

        if iq.answer_evaluation is not None:
            evaluation = iq.answer_evaluation
            evaluation.audio_recording_id = audio_recording_id
            evaluation.answer_source = answer_source
            evaluation.submitted_answer_text = stored_text
            for key, value in eval_result.items():
                if hasattr(evaluation, key):
                    setattr(evaluation, key, value)
        else:
            evaluation = AnswerEvaluation(
                user_id=user_id,
                interview_id=interview.id,
                interview_question_id=iq.id,
                audio_recording_id=audio_recording_id,
                answer_source=answer_source,
                submitted_answer_text=stored_text,
                **eval_result,
            )
            db.add(evaluation)

        # Integrate evaluation score with InterviewQuestion for adaptive progression
        iq.is_answered = True
        iq.score = eval_result["overall_score"]

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(evaluation)
        return evaluation

    @classmethod
    async def evaluate_text_answer(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: TextAnswerEvaluationRequest,
    ) -> AnswerEvaluation:
        """Evaluate a candidate's text answer for a specific interview question."""
        interview = await cls._get_owned_interview(db=db, interview_id=data.interview_id, user_id=user_id)
        if interview.status not in cls.ALLOWED_INTERVIEW_STATUSES:
            raise BadRequestException(
                f"Cannot evaluate answers when interview is in '{interview.status}' status"
            )

        iq = await cls._get_interview_question(
            db=db,
            interview_id=interview.id,
            interview_question_id=data.interview_question_id,
        )

        return await cls._persist_evaluation(
            db=db,
            user_id=user_id,
            interview=interview,
            iq=iq,
            answer_text=data.answer_text,
            answer_source="text",
            audio_recording_id=None,
            re_evaluate=data.re_evaluate,
        )

    @classmethod
    async def evaluate_audio_transcript(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        recording_id: uuid.UUID,
        data: Optional[AudioAnswerEvaluationRequest] = None,
    ) -> AnswerEvaluation:
        """Evaluate the completed speech-to-text transcript of an uploaded audio recording."""
        query = (
            select(AudioRecording)
            .where(AudioRecording.id == recording_id)
            .options(
                selectinload(AudioRecording.speech_analysis),
                selectinload(AudioRecording.interview),
            )
        )
        result = await db.execute(query)
        recording = result.scalar_one_or_none()

        if not recording:
            raise NotFoundException("Audio recording not found")
        if recording.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this recording")

        interview = recording.interview
        if not interview or interview.user_id != user_id:
            raise ForbiddenException("You do not have access to the linked interview session")

        if interview.status not in cls.ALLOWED_INTERVIEW_STATUSES:
            raise BadRequestException(
                f"Cannot evaluate answers when interview is in '{interview.status}' status"
            )

        target_iq_id = (
            data.interview_question_id
            if data is not None and data.interview_question_id is not None
            else recording.interview_question_id
        )
        if target_iq_id is None:
            raise BadRequestException(
                "Audio recording is not linked to an interview question; provide interview_question_id."
            )

        iq = await cls._get_interview_question(
            db=db,
            interview_id=interview.id,
            interview_question_id=target_iq_id,
        )

        speech_analysis = recording.speech_analysis
        if (
            speech_analysis is None
            or speech_analysis.transcription_status != "completed"
            or not (speech_analysis.transcription or "").strip()
        ):
            raise BadRequestException(
                "Audio recording does not have a completed, non-empty transcription ready for evaluation."
            )

        re_evaluate = data.re_evaluate if data is not None else False

        return await cls._persist_evaluation(
            db=db,
            user_id=user_id,
            interview=interview,
            iq=iq,
            answer_text=speech_analysis.transcription,
            answer_source="audio_transcript",
            audio_recording_id=recording.id,
            re_evaluate=re_evaluate,
        )

    @classmethod
    async def get_evaluation_by_id(
        cls,
        db: AsyncSession,
        evaluation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AnswerEvaluation:
        """Retrieve a single answer evaluation with strict user ownership enforcement."""
        result = await db.execute(
            select(AnswerEvaluation).where(AnswerEvaluation.id == evaluation_id)
        )
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            raise NotFoundException("Answer evaluation not found")
        if evaluation.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this evaluation")
        return evaluation

    @classmethod
    async def get_interview_evaluations(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[AnswerEvaluation]:
        """Retrieve all answer evaluations for an owned interview ordered by question sequence."""
        await cls._get_owned_interview(db=db, interview_id=interview_id, user_id=user_id)

        query = (
            select(AnswerEvaluation)
            .join(InterviewQuestion, AnswerEvaluation.interview_question_id == InterviewQuestion.id)
            .where(
                AnswerEvaluation.interview_id == interview_id,
                AnswerEvaluation.user_id == user_id,
            )
            .order_by(InterviewQuestion.order_index.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())
