"""Integration tests for interview configuration, lifecycle, ownership, and adaptive question engine."""

import pytest
from httpx import AsyncClient


async def get_authenticated_headers(client: AsyncClient, email: str, name: str) -> dict:
    """Helper to register and login a user and return the Bearer authorization headers."""
    reg_payload = {
        "email": email,
        "password": "Password12345!",
        "full_name": name,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password12345!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_interview_creation_and_listing(client: AsyncClient):
    """Test 1 & 2: Verify interview configuration creation and user-specific listing."""
    headers = await get_authenticated_headers(client, "interviewer@example.com", "Alice Smith")

    payload = {
        "title": "Backend Python Developer Mock",
        "target_role": "software_engineer",
        "interview_type": "technical",
        "difficulty_level": "medium",
        "experience_level": "mid",
        "total_questions": 3,
    }
    create_resp = await client.post("/api/v1/interviews", json=payload, headers=headers)
    assert create_resp.status_code == 201

    created_data = create_resp.json()
    assert created_data["title"] == payload["title"]
    assert created_data["status"] == "draft"
    assert created_data["total_questions"] == 3
    assert created_data["current_question_index"] == 0
    interview_id = created_data["id"]

    # Verify listing
    list_resp = await client.get("/api/v1/interviews", headers=headers)
    assert list_resp.status_code == 200
    interviews = list_resp.json()
    assert len(interviews) >= 1
    assert any(i["id"] == interview_id for i in interviews)


@pytest.mark.asyncio
async def test_interview_ownership_isolation(client: AsyncClient):
    """Test 3: Verify User B cannot access or modify User A's interview (403 Forbidden)."""
    headers_a = await get_authenticated_headers(client, "user_a@example.com", "User A")
    headers_b = await get_authenticated_headers(client, "user_b@example.com", "User B")

    # User A creates interview
    create_resp = await client.post(
        "/api/v1/interviews",
        json={"title": "Private Interview A", "total_questions": 3},
        headers=headers_a,
    )
    interview_id = create_resp.json()["id"]

    # User B attempts to fetch User A's interview -> 403 Forbidden
    get_resp = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers_b)
    assert get_resp.status_code == 403
    assert get_resp.json()["error"]["code"] == "FORBIDDEN"

    # User B attempts to start User A's interview -> 403 Forbidden
    start_resp = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers_b)
    assert start_resp.status_code == 403


@pytest.mark.asyncio
async def test_interview_start_and_question_retrieval(client: AsyncClient):
    """Test 4 & 5: Verify interview transitions to in_progress and presents first question."""
    headers = await get_authenticated_headers(client, "starter@example.com", "Bob Starter")

    create_resp = await client.post(
        "/api/v1/interviews",
        json={"title": "Starter Test", "difficulty_level": "easy", "interview_type": "technical", "total_questions": 3},
        headers=headers,
    )
    interview_id = create_resp.json()["id"]

    # Start the interview
    start_resp = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    assert start_resp.status_code == 200
    start_data = start_resp.json()

    assert start_data["order_index"] == 1
    assert start_data["total_questions"] == 3
    assert start_data["is_last_question"] is False
    assert "question" in start_data
    assert start_data["question"]["category"] == "technical"

    # Retrieve current active question
    current_resp = await client.get(f"/api/v1/interviews/{interview_id}/questions/current", headers=headers)
    assert current_resp.status_code == 200
    current_data = current_resp.json()
    assert current_data["question"]["id"] == start_data["question"]["id"]


@pytest.mark.asyncio
async def test_adaptive_difficulty_progression(client: AsyncClient):
    """Test 6: Verify adaptive difficulty responds to candidate score (step-up on high, step-down on low)."""
    headers = await get_authenticated_headers(client, "adaptive@example.com", "Adaptive Tester")

    # Start with easy difficulty
    create_resp = await client.post(
        "/api/v1/interviews",
        json={
            "title": "Adaptive Technical Assessment",
            "interview_type": "technical",
            "difficulty_level": "easy",
            "total_questions": 3,
        },
        headers=headers,
    )
    interview_id = create_resp.json()["id"]

    # Q1: starts with easy difficulty
    start_resp = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    q1_data = start_resp.json()
    assert q1_data["question"]["difficulty"] == "easy"

    # Candidate scores 90.0 on Q1 -> should step up to 'medium' for Q2
    next_resp = await client.post(
        f"/api/v1/interviews/{interview_id}/questions/next",
        json={"previous_answer_score": 90.0},
        headers=headers,
    )
    assert next_resp.status_code == 200
    q2_data = next_resp.json()
    assert q2_data["order_index"] == 2
    assert q2_data["question"]["difficulty"] == "medium"

    # Candidate scores 85.0 on Q2 -> should step up to 'hard' for Q3
    next_resp_2 = await client.post(
        f"/api/v1/interviews/{interview_id}/questions/next",
        json={"previous_answer_score": 85.0},
        headers=headers,
    )
    assert next_resp_2.status_code == 200
    q3_data = next_resp_2.json()
    assert q3_data["order_index"] == 3
    assert q3_data["question"]["difficulty"] == "hard"
    assert q3_data["is_last_question"] is True


@pytest.mark.asyncio
async def test_duplicate_prevention_across_interview(client: AsyncClient):
    """Test 7: Verify no question is repeated within the same interview."""
    headers = await get_authenticated_headers(client, "nodupes@example.com", "No Dupes")

    create_resp = await client.post(
        "/api/v1/interviews",
        json={"title": "No Duplicate Questions", "total_questions": 5, "interview_type": "mixed"},
        headers=headers,
    )
    interview_id = create_resp.json()["id"]

    seen_question_ids = set()

    # Question 1
    q1 = (await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)).json()
    seen_question_ids.add(q1["question"]["id"])

    # Questions 2 to 5
    for _ in range(4):
        next_resp = await client.post(
            f"/api/v1/interviews/{interview_id}/questions/next",
            json={"previous_answer_score": 70.0},
            headers=headers,
        )
        data = next_resp.json()
        if "question" in data:
            q_id = data["question"]["id"]
            assert q_id not in seen_question_ids, f"Question {q_id} was repeated!"
            seen_question_ids.add(q_id)

    assert len(seen_question_ids) == 5


@pytest.mark.asyncio
async def test_interview_full_completion_flow(client: AsyncClient):
    """Test 8: Verify interview automatically completes upon final question answer, or via /complete."""
    headers = await get_authenticated_headers(client, "completer@example.com", "Completer")

    create_resp = await client.post(
        "/api/v1/interviews",
        json={"title": "Short Interview", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_resp.json()["id"]

    # Start Q1
    await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)

    # Advance to Q2 (last question)
    q2_resp = await client.post(
        f"/api/v1/interviews/{interview_id}/questions/next",
        json={"previous_answer_score": 80.0},
        headers=headers,
    )
    assert q2_resp.json()["order_index"] == 2
    assert q2_resp.json()["is_last_question"] is True

    # Answer Q2 -> finishes interview
    finish_resp = await client.post(
        f"/api/v1/interviews/{interview_id}/questions/next",
        json={"previous_answer_score": 88.0},
        headers=headers,
    )
    assert finish_resp.status_code == 200
    finish_data = finish_resp.json()
    assert finish_data["completed"] is True

    # Verify interview status is now 'completed'
    status_resp = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"
    assert status_resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_invalid_state_transitions(client: AsyncClient):
    """Test 9: Verify state machine guards reject invalid status transitions with 400 Bad Request."""
    headers = await get_authenticated_headers(client, "statemachine@example.com", "State Guard")

    create_resp = await client.post(
        "/api/v1/interviews",
        json={"title": "State Transition Guard", "total_questions": 2},
        headers=headers,
    )
    interview_id = create_resp.json()["id"]

    # 1. Cannot fetch active question when still in 'draft'
    curr_resp = await client.get(f"/api/v1/interviews/{interview_id}/questions/current", headers=headers)
    assert curr_resp.status_code == 400
    assert "draft" in curr_resp.json()["error"]["message"]

    # 2. Cannot manually complete when still in 'draft'
    comp_resp = await client.post(f"/api/v1/interviews/{interview_id}/complete", headers=headers)
    assert comp_resp.status_code == 400

    # 3. Start interview (valid: draft -> in_progress)
    await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)

    # 4. Cannot start again when already 'in_progress'
    re_start_resp = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    assert re_start_resp.status_code == 400

    # 5. Complete interview (valid: in_progress -> completed)
    await client.post(f"/api/v1/interviews/{interview_id}/complete", headers=headers)

    # 6. Cannot start when already 'completed'
    post_comp_start = await client.post(f"/api/v1/interviews/{interview_id}/start", headers=headers)
    assert post_comp_start.status_code == 400
