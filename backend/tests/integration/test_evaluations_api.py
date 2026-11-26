"""Integration tests for Milestone 4 answer evaluation, audio transcript evaluation, and adaptive integration."""

import io
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.answer_evaluation import AnswerEvaluation
from app.models.interview_question import InterviewQuestion
from tests.unit.test_speech_engine import generate_synthetic_wav_bytes


async def get_authenticated_headers(client: AsyncClient, email: str, name: str) -> dict:
    """Register and login a user and return Bearer authorization headers."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password12345!", "full_name": name},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password12345!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_text_answer_submission_retrieval_and_history(client: AsyncClient):
    """Verify text answer evaluation, single-evaluation retrieval, and interview history."""
    headers = await get_authenticated_headers(client, "eval_text@example.com", "Eval Text User")

    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Technical Eval Interview",
            "interview_type": "technical",
            "difficulty_level": "easy",
            "total_questions": 2,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    assert start_res.status_code == 200
    iq_id = start_res.json()["interview_question_id"]
    assert iq_id is not None

    eval_res = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_id,
            "answer_text": (
                "SQL relational databases enforce ACID properties with rigid schemas and transactions, "
                "whereas NoSQL databases use BASE consistency, flexible schemas, and horizontal scaling "
                "for high-velocity unstructured workloads. For example, financial ledgers use SQL."
            ),
        },
        headers=headers,
    )
    assert eval_res.status_code == 201
    data = eval_res.json()
    evaluation_id = data["id"]

    assert data["answer_source"] == "text"
    assert data["audio_recording_id"] is None
    assert data["overall_score"] > 0.0
    assert data["star_evaluation"] is None  # Technical question should not use STAR
    assert len(data["strengths"]) >= 1
    assert data["evaluation_method"] == "heuristic-v1.0"

    # Duplicate evaluation without re_evaluate=true is rejected
    dup_res = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_id,
            "answer_text": "Second attempt",
        },
        headers=headers,
    )
    assert dup_res.status_code == 400
    assert "already been evaluated" in dup_res.json()["error"]["message"]

    # Explicit re_evaluate=true updates the single evaluation record in place
    re_eval_res = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_id,
            "answer_text": "SQL uses ACID transactions.",
            "re_evaluate": True,
        },
        headers=headers,
    )
    assert re_eval_res.status_code == 201
    re_data = re_eval_res.json()
    assert re_data["id"] == evaluation_id
    assert re_data["overall_score"] != data["overall_score"]

    # Retrieve single evaluation
    get_res = await client.get(f"/api/v1/evaluations/{evaluation_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == evaluation_id

    # Retrieve interview evaluation history
    hist_res = await client.get(f"/api/v1/evaluations/interview/{interview_id}", headers=headers)
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["interview_id"] == interview_id
    assert hist["total_evaluated"] == 1
    assert hist["average_score"] == re_data["overall_score"]
    assert len(hist["evaluations"]) == 1


@pytest.mark.asyncio
async def test_audio_transcript_evaluation_and_missing_transcript_handling(client: AsyncClient, tmp_path):
    """Verify evaluating a completed audio transcript and rejecting missing/failed transcripts."""
    headers = await get_authenticated_headers(client, "eval_audio@example.com", "Eval Audio User")

    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Behavioral Audio Eval",
            "interview_type": "behavioral",
            "difficulty_level": "medium",
            "total_questions": 2,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_id = start_res.json()["interview_question_id"]

    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0)
    with patch("app.services.audio_service.settings.RECORDINGS_DIR", str(tmp_path)):
        upload_res = await client.post(
            "/api/v1/audio/upload",
            data={"interview_id": interview_id, "interview_question_id": iq_id},
            files={"file": ("answer.wav", io.BytesIO(wav_bytes), "audio/wav")},
            headers=headers,
        )
    assert upload_res.status_code == 201
    recording_id = upload_res.json()["id"]

    # 1. Evaluating before transcription exists -> 400
    missing_res = await client.post(f"/api/v1/evaluations/audio/{recording_id}", headers=headers)
    assert missing_res.status_code == 400
    assert "completed, non-empty transcription" in missing_res.json()["error"]["message"]

    # 2. Run speech analysis with mocked Whisper transcription
    mock_transcription = {
        "transcription": (
            "At my previous company during a critical launch, my responsibility was to resolve "
            "a disagreement with a teammate. I coordinated a technical design review and listened "
            "to their concerns. As a result, we reached a compromise and shipped on time."
        ),
        "detected_language": "en",
        "segments": [{"start": 0.0, "end": 2.0, "text": "At my previous company..."}],
        "transcription_status": "completed",
        "transcription_duration_seconds": 0.3,
        "error_message": None,
    }
    with patch("app.engines.speech.analyzer.SpeechTranscriber.transcribe", return_value=mock_transcription):
        analyze_res = await client.post(f"/api/v1/audio/{recording_id}/analyze", headers=headers)
        assert analyze_res.status_code == 200

    # 3. Evaluate the completed audio transcript
    eval_res = await client.post(f"/api/v1/evaluations/audio/{recording_id}", headers=headers)
    assert eval_res.status_code == 201
    eval_data = eval_res.json()

    assert eval_data["answer_source"] == "audio_transcript"
    assert eval_data["audio_recording_id"] == recording_id
    assert eval_data["submitted_answer_text"] is None  # No transcript duplication
    assert eval_data["star_evaluation"] is not None
    assert eval_data["star_evaluation"]["applicable"] is True
    assert eval_data["overall_score"] > 0.0


@pytest.mark.asyncio
async def test_evaluation_ownership_and_invalid_relationships(client: AsyncClient):
    """Verify 401/403 access controls and 400/404 guards for invalid interview/question states."""
    headers_a = await get_authenticated_headers(client, "eval_owner_a@example.com", "Owner A")
    headers_b = await get_authenticated_headers(client, "eval_intruder_b@example.com", "Intruder B")

    # Draft interview cannot be evaluated
    int_a = await client.post(
        "/api/v1/interviews",
        json={"title": "Owner A Interview", "interview_type": "technical", "total_questions": 2},
        headers=headers_a,
    )
    interview_a_id = int_a.json()["id"]

    draft_eval = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_a_id,
            "interview_question_id": str(uuid.uuid4()),
            "answer_text": "Draft attempt",
        },
        headers=headers_a,
    )
    assert draft_eval.status_code == 400

    # Start interview A and evaluate Q1
    start_a = await client.post(f"/api/v1/interviews/{interview_a_id}/start", headers=headers_a)
    iq_a_id = start_a.json()["interview_question_id"]

    # Invalid question ID for interview A -> 404
    bad_iq = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_a_id,
            "interview_question_id": str(uuid.uuid4()),
            "answer_text": "Valid text",
        },
        headers=headers_a,
    )
    assert bad_iq.status_code == 404

    ok_eval = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_a_id,
            "interview_question_id": iq_a_id,
            "answer_text": "ACID and REST stateless GET PUT DELETE idempotent API design.",
        },
        headers=headers_a,
    )
    assert ok_eval.status_code == 201
    eval_id = ok_eval.json()["id"]

    # Unauthenticated -> 401
    unauth = await client.get(f"/api/v1/evaluations/{eval_id}")
    assert unauth.status_code == 401

    # User B cannot access User A's evaluation or history -> 403
    assert (await client.get(f"/api/v1/evaluations/{eval_id}", headers=headers_b)).status_code == 403
    assert (await client.get(f"/api/v1/evaluations/interview/{interview_a_id}", headers=headers_b)).status_code == 403

    # User B cannot submit an evaluation or apply a score to User A's interview -> 403
    cross_submit = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_a_id,
            "interview_question_id": iq_a_id,
            "answer_text": "Unauthorized overwrite attempt",
            "re_evaluate": True,
        },
        headers=headers_b,
    )
    assert cross_submit.status_code == 403


@pytest.mark.asyncio
async def test_adaptive_engine_integration_uses_evaluated_score(client: AsyncClient, db_session):
    """Verify evaluated score persisted on InterviewQuestion drives adaptive difficulty progression."""
    headers = await get_authenticated_headers(client, "adaptive_eval@example.com", "Adaptive Eval")

    # Start at 'medium' technical interview
    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Adaptive Integration Test",
            "interview_type": "technical",
            "difficulty_level": "medium",
            "total_questions": 3,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = start_res.json()["interview_question_id"]
    q1 = start_res.json()["question"]
    assert q1["difficulty"] == "medium"

    # Submit a weak answer ("I don't know.") -> score < 50 -> next question should step down to 'easy'
    eval_res = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_1_id,
            "answer_text": "I don't know.",
        },
        headers=headers,
    )
    assert eval_res.status_code == 201
    assert eval_res.json()["overall_score"] < 50.0

    # Verify InterviewQuestion.score was populated
    res = await db_session.execute(select(InterviewQuestion).where(InterviewQuestion.id == uuid.UUID(iq_1_id)))
    iq_1 = res.scalar_one()
    assert iq_1.score == eval_res.json()["overall_score"]
    assert iq_1.is_answered is True

    # Advance to Q2 WITHOUT passing previous_answer_score explicitly
    next_res = await client.post(
        f"/api/v1/interviews/{interview_id}/questions/next",
        json={},
        headers=headers,
    )
    assert next_res.status_code == 200
    assert next_res.json()["question"]["difficulty"] == "easy"


@pytest.mark.asyncio
async def test_adaptive_engine_step_up_and_maintain_thresholds(client: AsyncClient):
    """Verify >= 75 steps difficulty up and 50-74.9 maintains difficulty via evaluation scores."""
    headers = await get_authenticated_headers(client, "adaptive_up@example.com", "Adaptive Up")

    # 1. Start at 'easy' technical -> evaluate strong answer (>= 75) -> step up to 'medium'
    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Adaptive Step-Up & Maintain",
            "interview_type": "technical",
            "difficulty_level": "easy",
            "total_questions": 3,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = start_res.json()["interview_question_id"]
    assert start_res.json()["question"]["difficulty"] == "easy"

    # Patch pipeline output to deterministic 82.0 (>= 75.0) for Q1
    with patch(
        "app.services.evaluation_service.AnswerEvaluationPipeline.evaluate",
        return_value={
            "relevance_score": 85.0,
            "keyword_coverage_score": 80.0,
            "rubric_coverage_score": 82.0,
            "completeness_score": 80.0,
            "structure_score": 85.0,
            "overall_score": 82.0,
            "dimension_weights": {"relevance": 0.2, "keyword_coverage": 0.3, "rubric_coverage": 0.3, "completeness": 0.15, "structure": 0.05},
            "matched_keywords": ["ACID"],
            "missing_concepts": [],
            "strengths": ["Strong coverage."],
            "improvement_suggestions": ["Keep it up."],
            "star_evaluation": None,
            "summary": "Score 82.0",
            "evaluation_method": "heuristic-v1.0",
        },
    ):
        eval_1 = await client.post(
            "/api/v1/evaluations/text",
            json={"interview_id": interview_id, "interview_question_id": iq_1_id, "answer_text": "Strong answer."},
            headers=headers,
        )
        assert eval_1.status_code == 201
        assert eval_1.json()["overall_score"] == 82.0

    q2_res = await client.post(f"/api/v1/interviews/{interview_id}/questions/next", json={}, headers=headers)
    assert q2_res.status_code == 200
    assert q2_res.json()["question"]["difficulty"] == "medium"
    iq_2_id = q2_res.json()["interview_question_id"]

    # 2. Evaluate moderate answer (62.0 in 50-74.9) -> maintain 'medium'
    with patch(
        "app.services.evaluation_service.AnswerEvaluationPipeline.evaluate",
        return_value={
            "relevance_score": 65.0,
            "keyword_coverage_score": 60.0,
            "rubric_coverage_score": 62.0,
            "completeness_score": 60.0,
            "structure_score": 65.0,
            "overall_score": 62.0,
            "dimension_weights": {"relevance": 0.2, "keyword_coverage": 0.3, "rubric_coverage": 0.3, "completeness": 0.15, "structure": 0.05},
            "matched_keywords": ["Redis"],
            "missing_concepts": ["TTL"],
            "strengths": ["Partial coverage."],
            "improvement_suggestions": ["Add TTL details."],
            "star_evaluation": None,
            "summary": "Score 62.0",
            "evaluation_method": "heuristic-v1.0",
        },
    ):
        eval_2 = await client.post(
            "/api/v1/evaluations/text",
            json={"interview_id": interview_id, "interview_question_id": iq_2_id, "answer_text": "Moderate answer."},
            headers=headers,
        )
        assert eval_2.status_code == 201
        assert eval_2.json()["overall_score"] == 62.0

    q3_res = await client.post(f"/api/v1/interviews/{interview_id}/questions/next", json={}, headers=headers)
    assert q3_res.status_code == 200
    assert q3_res.json()["question"]["difficulty"] == "medium"


@pytest.mark.asyncio
async def test_evaluation_validation_completed_guard_rollback_and_missing_eval_safety(
    client: AsyncClient, db_session
):
    """Verify empty/invalid payloads, invalid recording ID, completed interview guard, rollback, and missing eval safety."""
    headers = await get_authenticated_headers(client, "guard_eval@example.com", "Guard Eval")

    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Guard & Rollback Interview",
            "interview_type": "technical",
            "difficulty_level": "medium",
            "total_questions": 2,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = start_res.json()["interview_question_id"]

    # 1. Empty & whitespace answer submission -> 422
    for bad_text in ["", "   "]:
        empty_res = await client.post(
            "/api/v1/evaluations/text",
            json={
                "interview_id": interview_id,
                "interview_question_id": iq_1_id,
                "answer_text": bad_text,
            },
            headers=headers,
        )
        assert empty_res.status_code == 422

    # 2. Invalid request payload (malformed UUID / missing field) -> 422
    bad_payload = await client.post(
        "/api/v1/evaluations/text",
        json={"interview_id": "not-a-uuid", "interview_question_id": iq_1_id},
        headers=headers,
    )
    assert bad_payload.status_code == 422

    # 3. Invalid recording ID -> 404
    bad_rec = await client.post(f"/api/v1/evaluations/audio/{uuid.uuid4()}", headers=headers)
    assert bad_rec.status_code == 404

    # 4. Missing evaluation handled safely when advancing to next question
    next_res = await client.post(f"/api/v1/interviews/{interview_id}/questions/next", json={}, headers=headers)
    assert next_res.status_code == 200
    assert next_res.json()["question"]["difficulty"] == "medium"
    iq_2_id = next_res.json()["interview_question_id"]

    # 5. Complete interview -> subsequent answer evaluations must be rejected with 400
    complete_res = await client.post(f"/api/v1/interviews/{interview_id}/complete", headers=headers)
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "completed"

    after_complete = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_2_id,
            "answer_text": "Trying to answer after completion.",
        },
        headers=headers,
    )
    assert after_complete.status_code == 400
    assert "completed" in after_complete.json()["error"]["message"]


@pytest.mark.asyncio
async def test_database_rollback_on_evaluation_commit_failure(client: AsyncClient, db_session):
    """Verify database session rolls back cleanly and persists no partial record on commit failure."""
    headers = await get_authenticated_headers(client, "rollback_eval@example.com", "Rollback User")
    create_int = await client.post(
        "/api/v1/interviews",
        json={"title": "Rollback Test", "interview_type": "technical", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = start_res.json()["interview_question_id"]

    with patch.object(db_session, "commit", new=AsyncMock(side_effect=SQLAlchemyError("Simulated commit failure"))):
        with pytest.raises(SQLAlchemyError):
            await client.post(
                "/api/v1/evaluations/text",
                json={
                    "interview_id": interview_id,
                    "interview_question_id": iq_1_id,
                    "answer_text": "ACID transactions and relational schemas.",
                },
                headers=headers,
            )

    eval_rows = (
        await db_session.execute(
            select(AnswerEvaluation).where(AnswerEvaluation.interview_question_id == uuid.UUID(iq_1_id))
        )
    ).scalars().all()
    assert eval_rows == []


@pytest.mark.asyncio
async def test_re_evaluation_rollback_and_adaptive_latest_score(client: AsyncClient, db_session):
    """Verify re_evaluate=true rollback preserves original score and successful re-eval drives adaptive engine."""
    headers = await get_authenticated_headers(client, "reeval_flow@example.com", "ReEval User")
    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Re-evaluate Flow Test",
            "interview_type": "technical",
            "difficulty_level": "medium",
            "total_questions": 2,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]
    start_res = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = start_res.json()["interview_question_id"]

    # 1. Initial weak evaluation (< 50)
    first_res = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_1_id,
            "answer_text": "I don't know.",
        },
        headers=headers,
    )
    assert first_res.status_code == 201
    first_data = first_res.json()
    assert first_data["overall_score"] < 50.0

    # 2. Failed re_evaluate=true commit -> rolls back and preserves original evaluation & InterviewQuestion.score
    with patch.object(db_session, "commit", new=AsyncMock(side_effect=SQLAlchemyError("Re-eval commit error"))):
        with pytest.raises(SQLAlchemyError):
            await client.post(
                "/api/v1/evaluations/text",
                json={
                    "interview_id": interview_id,
                    "interview_question_id": iq_1_id,
                    "answer_text": "Should roll back.",
                    "re_evaluate": True,
                },
                headers=headers,
            )

    persisted_eval = (
        await db_session.execute(
            select(AnswerEvaluation).where(AnswerEvaluation.interview_question_id == uuid.UUID(iq_1_id))
        )
    ).scalar_one()
    assert persisted_eval.id == uuid.UUID(first_data["id"])
    assert persisted_eval.overall_score == first_data["overall_score"]

    iq_row = (
        await db_session.execute(select(InterviewQuestion).where(InterviewQuestion.id == uuid.UUID(iq_1_id)))
    ).scalar_one()
    assert iq_row.score == first_data["overall_score"]

    # 3. Successful re_evaluate=true with high score (>= 75) -> updates in place & steps difficulty up to 'hard'
    with patch(
        "app.services.evaluation_service.AnswerEvaluationPipeline.evaluate",
        return_value={
            "relevance_score": 88.0,
            "keyword_coverage_score": 85.0,
            "rubric_coverage_score": 84.0,
            "completeness_score": 82.0,
            "structure_score": 80.0,
            "overall_score": 85.0,
            "dimension_weights": {"relevance": 0.2, "keyword_coverage": 0.3, "rubric_coverage": 0.3, "completeness": 0.15, "structure": 0.05},
            "matched_keywords": ["Redis", "TTL"],
            "missing_concepts": [],
            "strengths": ["Comprehensive re-evaluated answer."],
            "improvement_suggestions": ["Consider edge cases."],
            "star_evaluation": None,
            "summary": "Score 85.0",
            "evaluation_method": "heuristic-v1.0",
        },
    ):
        re_res = await client.post(
            "/api/v1/evaluations/text",
            json={
                "interview_id": interview_id,
                "interview_question_id": iq_1_id,
                "answer_text": "Detailed Redis caching and invalidation answer.",
                "re_evaluate": True,
            },
            headers=headers,
        )
    assert re_res.status_code == 201
    assert re_res.json()["id"] == first_data["id"]
    assert re_res.json()["overall_score"] == 85.0

    # Adaptive engine uses the latest valid score (85.0 >= 75) -> steps up from 'medium' to 'hard'
    next_res = await client.post(f"/api/v1/interviews/{interview_id}/questions/next", json={}, headers=headers)
    assert next_res.status_code == 200
    assert next_res.json()["question"]["difficulty"] == "hard"


@pytest.mark.asyncio
async def test_multi_question_history_and_no_sensitive_fields_exposed(client: AsyncClient):
    """Verify multi-question history ordering, average score, and absence of sensitive fields."""
    headers = await get_authenticated_headers(client, "hist_eval@example.com", "History User")

    create_int = await client.post(
        "/api/v1/interviews",
        json={
            "title": "History Order Test",
            "interview_type": "technical",
            "difficulty_level": "easy",
            "total_questions": 2,
        },
        headers=headers,
    )
    interview_id = create_int.json()["id"]

    q1 = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    iq_1_id = q1.json()["interview_question_id"]
    e1 = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_1_id,
            "answer_text": "SQL uses ACID transactions and relational schemas.",
        },
        headers=headers,
    )
    assert e1.status_code == 201

    q2 = await client.post(f"/api/v1/interviews/{interview_id}/questions/next", json={}, headers=headers)
    iq_2_id = q2.json()["interview_question_id"]
    e2 = await client.post(
        "/api/v1/evaluations/text",
        json={
            "interview_id": interview_id,
            "interview_question_id": iq_2_id,
            "answer_text": "REST APIs are stateless and use GET PUT DELETE idempotently.",
        },
        headers=headers,
    )
    assert e2.status_code == 201

    hist_res = await client.get(f"/api/v1/evaluations/interview/{interview_id}", headers=headers)
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["total_evaluated"] == 2
    expected_avg = round((e1.json()["overall_score"] + e2.json()["overall_score"]) / 2, 2)
    assert hist["average_score"] == expected_avg
    assert [ev["interview_question_id"] for ev in hist["evaluations"]] == [iq_1_id, iq_2_id]

    raw_text = hist_res.text.lower()
    for sensitive in ("hashed_password", "file_path", "secret_key"):
        assert sensitive not in raw_text
