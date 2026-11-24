"""Interview API endpoints for configuration, progression, and lifecycle control."""

from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.interview import (
    ActiveQuestionDetailResponse,
    InterviewCreateRequest,
    InterviewResponse,
    NextQuestionRequest,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["Interviews"])


@router.post(
    "",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new interview configuration",
)
async def create_interview(
    data: InterviewCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InterviewResponse:
    """Create a new interview session in 'draft' status."""
    interview = await InterviewService.create_interview(
        db=db,
        user_id=current_user.id,
        data=data,
    )
    return InterviewResponse(
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
        questions_answered_count=0,
    )


@router.get(
    "",
    response_model=List[InterviewResponse],
    status_code=status.HTTP_200_OK,
    summary="List all interview sessions for authenticated user",
)
async def list_interviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> List[InterviewResponse]:
    """Retrieve paginated interview sessions belonging to the current user."""
    interviews = await InterviewService.get_user_interviews(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [
        InterviewResponse(
            id=i.id,
            user_id=i.user_id,
            title=i.title,
            target_role=i.target_role,
            interview_type=i.interview_type,
            difficulty_level=i.difficulty_level,
            experience_level=i.experience_level,
            total_questions=i.total_questions,
            status=i.status,
            current_question_index=i.current_question_index,
            started_at=i.started_at,
            completed_at=i.completed_at,
            created_at=i.created_at,
            questions_answered_count=sum(1 for q in i.interview_questions if q.is_answered),
        )
        for i in interviews
    ]


@router.get(
    "/{interview_id}",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get interview session details",
)
async def get_interview(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InterviewResponse:
    """Retrieve details for a specific interview, verifying user ownership."""
    interview = await InterviewService.get_interview_by_id(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
    )
    return InterviewResponse(
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


@router.post(
    "/{interview_id}/start",
    response_model=ActiveQuestionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Start interview session and retrieve first question",
)
async def start_interview(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ActiveQuestionDetailResponse:
    """Transition interview from 'draft' to 'in_progress' and present Question 1."""
    return await InterviewService.start_interview(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
    )


@router.get(
    "/{interview_id}/questions/current",
    response_model=ActiveQuestionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the currently active unanswered question",
)
async def get_current_question(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ActiveQuestionDetailResponse:
    """Fetch the active question for an ongoing interview."""
    return await InterviewService.get_current_question(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
    )


@router.post(
    "/{interview_id}/questions/next",
    response_model=Union[ActiveQuestionDetailResponse, Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Advance to the next question using adaptive difficulty",
)
async def next_question(
    interview_id: uuid.UUID,
    data: Optional[NextQuestionRequest] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Union[ActiveQuestionDetailResponse, Dict[str, Any]]:
    """Submit previous answer score and dynamically load the next adaptive question."""
    req_data = data or NextQuestionRequest()
    next_q = await InterviewService.advance_to_next_question(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
        data=req_data,
    )
    if next_q is None:
        return {
            "completed": True,
            "message": "All interview questions answered. Interview session completed.",
        }
    return next_q


@router.post(
    "/{interview_id}/complete",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Explicitly conclude an interview session",
)
async def complete_interview(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InterviewResponse:
    """Conclude an in-progress interview session."""
    interview = await InterviewService.complete_interview(
        db=db,
        interview_id=interview_id,
        user_id=current_user.id,
    )
    return InterviewResponse(
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
