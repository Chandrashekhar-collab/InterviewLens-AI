"""Rule-based adaptive question selection engine."""

from typing import List, Optional, Set
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AppException
from app.models.interview import Interview
from app.models.question import Question


class AdaptiveQuestionEngine:
    """Adaptive engine selecting the next interview question based on performance and categories."""

    # Explicit scoring thresholds
    THRESHOLD_STEP_UP: float = 75.0
    THRESHOLD_STEP_DOWN: float = 50.0

    DIFFICULTY_LEVELS: List[str] = ["easy", "medium", "hard"]

    # Category sequencing template for 'mixed' interviews
    MIXED_SEQUENCE: List[str] = [
        "behavioral",    # Q1: Icebreaker / Background
        "technical",     # Q2: Core Technical
        "technical",     # Q3: Technical Architecture / In-depth
        "communication", # Q4: Articulation / Stakeholder Interaction
        "presentation",  # Q5: Pitch / Trade-off Presentation
        "hr",            # Q6+: Culture / Future Vision
    ]

    @classmethod
    def calculate_next_difficulty(
        cls,
        current_difficulty: str,
        previous_score: Optional[float],
    ) -> str:
        """Compute the next target difficulty based on candidate's prior answer score.

        Scoring Rules:
        - Score >= 75.0: Step up difficulty (easy -> medium -> hard)
        - 50.0 <= Score < 75.0: Maintain current difficulty
        - Score < 50.0: Step down difficulty (hard -> medium -> easy)
        - None (First Question): Maintain base difficulty
        """
        curr = current_difficulty.lower()
        if curr not in cls.DIFFICULTY_LEVELS:
            curr = "medium"

        if previous_score is None:
            return curr

        idx = cls.DIFFICULTY_LEVELS.index(curr)

        if previous_score >= cls.THRESHOLD_STEP_UP:
            # Step up, capped at 'hard'
            next_idx = min(idx + 1, len(cls.DIFFICULTY_LEVELS) - 1)
        elif previous_score < cls.THRESHOLD_STEP_DOWN:
            # Step down, floored at 'easy'
            next_idx = max(idx - 1, 0)
        else:
            next_idx = idx

        return cls.DIFFICULTY_LEVELS[next_idx]

    @classmethod
    def determine_target_category(
        cls,
        interview_type: str,
        question_order_index: int,
    ) -> str:
        """Determine the target category for the next question."""
        itype = interview_type.lower()
        if itype != "mixed":
            return itype

        seq_idx = min(question_order_index - 1, len(cls.MIXED_SEQUENCE) - 1)
        return cls.MIXED_SEQUENCE[max(0, seq_idx)]

    @classmethod
    async def select_next_question(
        cls,
        db: AsyncSession,
        interview: Interview,
        previous_score: Optional[float] = None,
        previous_difficulty: Optional[str] = None,
    ) -> Question:
        """Select the optimal next question preventing duplicates within the interview."""
        # 1. Identify attempted question IDs
        attempted_ids: Set[uuid.UUID] = {
            iq.question_id for iq in interview.interview_questions
        }

        # 2. Determine target difficulty
        base_difficulty = previous_difficulty or interview.difficulty_level or "medium"
        target_difficulty = cls.calculate_next_difficulty(base_difficulty, previous_score)

        # 3. Determine target category
        next_order_index = len(interview.interview_questions) + 1
        target_category = cls.determine_target_category(
            interview_type=interview.interview_type,
            question_order_index=next_order_index,
        )

        # 4. Fetch candidate questions from database
        query = select(Question).where(
            Question.is_active == True,
            Question.id.not_in(attempted_ids) if attempted_ids else True,
        )
        result = await db.execute(query)
        available_questions = list(result.scalars().all())

        if not available_questions:
            raise AppException(
                status_code=400,
                message="No more available questions in question bank for this interview",
                code="NO_AVAILABLE_QUESTIONS",
            )

        # Tier 1 Match: Exact Category & Exact Difficulty
        match = next(
            (q for q in available_questions if q.category == target_category and q.difficulty == target_difficulty),
            None,
        )
        if match:
            return match

        # Tier 2 Match: Exact Category & Any Difficulty
        match = next(
            (q for q in available_questions if q.category == target_category),
            None,
        )
        if match:
            return match

        # Tier 3 Match: Target Difficulty & Any Category
        match = next(
            (q for q in available_questions if q.difficulty == target_difficulty),
            None,
        )
        if match:
            return match

        # Tier 4 Fallback: Any remaining non-attempted question
        return available_questions[0]
