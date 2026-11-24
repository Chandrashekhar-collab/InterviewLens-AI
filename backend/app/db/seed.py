"""Database seeder to populate the curated question bank."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.engines.question_gen.question_bank import SEED_QUESTIONS
from app.models.question import Question


async def seed_question_bank(db: AsyncSession) -> int:
    """Populate database with curated seed questions if currently empty."""
    count_query = select(func.count(Question.id))
    result = await db.execute(count_query)
    current_count = result.scalar_one()

    if current_count > 0:
        return current_count

    logger.info("Seeding initial question bank...")
    seeded_instances = []
    for q_data in SEED_QUESTIONS:
        question = Question(
            category=q_data["category"],
            difficulty=q_data["difficulty"],
            target_roles=q_data["target_roles"],
            question_text=q_data["question_text"],
            expected_duration_seconds=q_data["expected_duration_seconds"],
            ideal_answer_rubric=q_data["ideal_answer_rubric"],
            keywords=q_data["keywords"],
            is_active=True,
        )
        seeded_instances.append(question)
        db.add(question)

    await db.commit()
    logger.info(f"Successfully seeded {len(seeded_instances)} questions.")
    return len(seeded_instances)
