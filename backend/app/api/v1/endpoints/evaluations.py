"""Answer evaluation and interview feedback API endpoints."""

from typing import Optional
import uuid
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.evaluation import (
    AnswerEvaluationResponse,
    AudioAnswerEvaluationRequest,
    InterviewEvaluationHistoryResponse,
    TextAnswerEvaluationRequest,
)
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluations", tags=["Answer Evaluation & Feedback"])


@router.post(
    "/text",
    response_model=AnswerEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a candidate text answer for an interview question",
)
async def evaluate_text_answer(
    data: TextAnswerEvaluationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AnswerEvaluationResponse:
    """Evaluate a written answer using rubric, keyword, relevance, completeness, and STAR criteria."""
    evaluation = await EvaluationService.evaluate_text_answer(
        db=db,
        user_id=current_user.id,
        data=data,
    )
    return AnswerEvaluationResponse.model_validate(evaluation)


@router.post(
    "/audio/{recording_id}",
    response_model=AnswerEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a completed audio recording transcript",
)
async def evaluate_audio_transcript(
    recording_id: uuid.UUID,
    data: Optional[AudioAnswerEvaluationRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AnswerEvaluationResponse:
    """Evaluate the completed transcript of an uploaded audio recording without altering speech metrics."""
    evaluation = await EvaluationService.evaluate_audio_transcript(
        db=db,
        user_id=current_user.id,
        recording_id=recording_id,
        data=data,
    )
    return AnswerEvaluationResponse.model_validate(evaluation)


@router.get(
    "/interview/{interview_id}",
    response_model=InterviewEvaluationHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get answer evaluation history for an interview session",
)
async def get_interview_evaluation_history(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InterviewEvaluationHistoryResponse:
    """Retrieve all answer evaluations and average score for an owned interview."""
    evaluations = await EvaluationService.get_interview_evaluations(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
    )
    avg_score: Optional[float] = None
    if evaluations:
        avg_score = round(sum(e.overall_score for e in evaluations) / len(evaluations), 2)

    return InterviewEvaluationHistoryResponse(
        interview_id=interview_id,
        total_evaluated=len(evaluations),
        average_score=avg_score,
        evaluations=[AnswerEvaluationResponse.model_validate(e) for e in evaluations],
    )


@router.get(
    "/{evaluation_id}",
    response_model=AnswerEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific answer evaluation result",
)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AnswerEvaluationResponse:
    """Retrieve an answer evaluation by ID, enforcing user ownership."""
    evaluation = await EvaluationService.get_evaluation_by_id(
        db=db,
        evaluation_id=evaluation_id,
        user_id=current_user.id,
    )
    return AnswerEvaluationResponse.model_validate(evaluation)
