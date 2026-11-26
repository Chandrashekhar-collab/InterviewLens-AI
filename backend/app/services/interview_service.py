"""Interview service managing interview creation, lifecycle transitions, and question flow."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.db.seed import seed_question_bank
from app.engines.question_gen.adaptive_engine import AdaptiveQuestionEngine
from app.models.interview import Interview
from app.models.interview_question import InterviewQuestion
from app.schemas.interview import (
    ActiveQuestionDetailResponse,
    InterviewCreateRequest,
    NextQuestionRequest,
    QuestionResponse,
)


class InterviewService:
    """Service layer managing interview sessions and adaptive progression."""

    @staticmethod
    def _to_utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    async def create_interview(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: InterviewCreateRequest,
    ) -> Interview:
        """Create a new interview configuration session in draft status."""
        interview = Interview(
            user_id=user_id,
            title=data.title.strip(),
            target_role=data.target_role.strip().lower(),
            interview_type=data.interview_type,
            difficulty_level=data.difficulty_level,
            experience_level=data.experience_level,
            total_questions=data.total_questions,
            status="draft",
            current_question_index=0,
        )
        db.add(interview)
        await db.commit()
        await db.refresh(interview)
        return interview

    @classmethod
    async def get_user_interviews(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Interview]:
        """List all interviews belonging to the specified user."""
        query = (
            select(Interview)
            .where(Interview.user_id == user_id)
            .options(
                selectinload(Interview.interview_questions),
            )
            .order_by(Interview.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_interview_by_id(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Fetch an interview by ID with strict ownership validation."""
        query = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.interview_questions).selectinload(InterviewQuestion.question),
            )
        )
        result = await db.execute(query)
        interview = result.scalar_one_or_none()

        if not interview:
            raise NotFoundException("Interview session not found")

        if interview.user_id != user_id:
            raise ForbiddenException("You do not have access to this interview session")

        return interview

    @classmethod
    async def start_interview(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ActiveQuestionDetailResponse:
        """Transition interview to 'in_progress', seed bank if needed, and select Question #1."""
        interview = await cls.get_interview_by_id(db=db, interview_id=interview_id, user_id=user_id)

        if interview.status != "draft":
            raise BadRequestException(
                f"Cannot start interview in '{interview.status}' status (must be 'draft')"
            )

        # Ensure question bank is seeded with curated seed questions
        await seed_question_bank(db)

        # Select initial question based on configured difficulty and interview type
        first_question = await AdaptiveQuestionEngine.select_next_question(
            db=db,
            interview=interview,
            previous_score=None,
            previous_difficulty=interview.difficulty_level,
        )

        # Update state
        interview.status = "in_progress"
        interview.started_at = cls._to_utc_now()
        interview.current_question_index = 1

        iq = InterviewQuestion(
            interview_id=interview.id,
            question_id=first_question.id,
            order_index=1,
            is_answered=False,
        )
        db.add(iq)
        await db.commit()
        await db.refresh(interview)

        return ActiveQuestionDetailResponse(
            interview_question_id=iq.id,
            order_index=1,
            total_questions=interview.total_questions,
            is_last_question=(interview.total_questions == 1),
            question=QuestionResponse.model_validate(first_question),
        )

    @classmethod
    async def get_current_question(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ActiveQuestionDetailResponse:
        """Retrieve the currently active unanswered question."""
        interview = await cls.get_interview_by_id(db=db, interview_id=interview_id, user_id=user_id)

        if interview.status != "in_progress":
            raise BadRequestException(
                f"Interview is not in progress (current status: '{interview.status}')"
            )

        current_iq = next(
            (iq for iq in interview.interview_questions if iq.order_index == interview.current_question_index),
            None,
        )

        if not current_iq or not current_iq.question:
            raise NotFoundException("No active question found for this interview step")

        return ActiveQuestionDetailResponse(
            interview_question_id=current_iq.id,
            order_index=current_iq.order_index,
            total_questions=interview.total_questions,
            is_last_question=(current_iq.order_index == interview.total_questions),
            question=QuestionResponse.model_validate(current_iq.question),
        )

    @classmethod
    async def advance_to_next_question(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
        data: NextQuestionRequest,
    ) -> Optional[ActiveQuestionDetailResponse]:
        """Mark current question answered, compute adaptive difficulty, and load next question."""
        interview = await cls.get_interview_by_id(db=db, interview_id=interview_id, user_id=user_id)

        if interview.status != "in_progress":
            raise BadRequestException(
                f"Interview is not in progress (current status: '{interview.status}')"
            )

        # Mark current question answered
        current_iq = next(
            (iq for iq in interview.interview_questions if iq.order_index == interview.current_question_index),
            None,
        )

        prev_difficulty = None
        effective_previous_score = data.previous_answer_score
        if current_iq:
            current_iq.is_answered = True
            if data.previous_answer_score is not None:
                current_iq.score = data.previous_answer_score
            elif current_iq.score is not None:
                # Reuse score persisted by the Milestone 4 answer evaluation engine
                effective_previous_score = current_iq.score
            if current_iq.question:
                prev_difficulty = current_iq.question.difficulty

        # Check if interview is finished
        if interview.current_question_index >= interview.total_questions:
            interview.status = "completed"
            interview.completed_at = cls._to_utc_now()
            await db.commit()
            return None

        # Select next question adaptively
        next_order_index = interview.current_question_index + 1
        next_question = await AdaptiveQuestionEngine.select_next_question(
            db=db,
            interview=interview,
            previous_score=effective_previous_score,
            previous_difficulty=prev_difficulty,
        )

        interview.current_question_index = next_order_index
        new_iq = InterviewQuestion(
            interview_id=interview.id,
            question_id=next_question.id,
            order_index=next_order_index,
            is_answered=False,
        )
        db.add(new_iq)
        await db.commit()

        return ActiveQuestionDetailResponse(
            interview_question_id=new_iq.id,
            order_index=next_order_index,
            total_questions=interview.total_questions,
            is_last_question=(next_order_index == interview.total_questions),
            question=QuestionResponse.model_validate(next_question),
        )

    @classmethod
    async def complete_interview(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Explicitly conclude an active interview session."""
        interview = await cls.get_interview_by_id(db=db, interview_id=interview_id, user_id=user_id)

        if interview.status == "completed":
            return interview

        if interview.status != "in_progress":
            raise BadRequestException(
                f"Cannot complete interview with status '{interview.status}' (must be 'in_progress')"
            )

        interview.status = "completed"
        interview.completed_at = cls._to_utc_now()
        await db.commit()
        await db.refresh(interview)
        return interview

    @classmethod
    async def abandon_interview(
        cls,
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Transition an active or draft interview to 'abandoned' status."""
        interview = await cls.get_interview_by_id(db=db, interview_id=interview_id, user_id=user_id)

        if interview.status == "abandoned":
            return interview

        if interview.status == "completed":
            raise BadRequestException("Cannot abandon an interview that is already completed")

        interview.status = "abandoned"
        await db.commit()
        await db.refresh(interview)
        return interview
