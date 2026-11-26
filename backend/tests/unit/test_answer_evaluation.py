"""Unit tests for the deterministic Milestone 4 Answer Evaluation Engine."""

import pytest

from app.engines.answer_evaluation import (
    AnswerEvaluationPipeline,
    CATEGORY_WEIGHTS,
    CompletenessEvaluator,
    EvaluationPreprocessor,
    FeedbackGenerator,
    KeywordCoverageEvaluator,
    RelevanceEvaluator,
    RubricEvaluator,
    ScoreCalculator,
    STAREvaluator,
)


def test_answer_preprocessing():
    """Verify whitespace normalization, tokenization, stopword filtering, and sentence splitting."""
    raw = "  SQL databases use ACID transactions!   NoSQL scales horizontally.  "
    prep = EvaluationPreprocessor.preprocess(raw)

    assert prep.word_count == 8
    assert prep.sentence_count == 2
    assert "sql" in prep.tokens
    assert "acid" in prep.content_tokens
    assert "use" not in prep.content_tokens  # stopword filtered


def test_keyword_coverage_evaluation():
    """Verify exact, plural-tolerant, and missing keyword tracking."""
    prep = EvaluationPreprocessor.preprocess(
        "Relational SQL databases enforce ACID transactions and rigid schemas, whereas NoSQL supports horizontal scaling."
    )
    keywords = ["ACID", "relational", "schema", "horizontal scaling", "NoSQL", "graph"]
    res = KeywordCoverageEvaluator.evaluate(prep, keywords)

    assert "ACID" in res["matched_keywords"]
    assert "relational" in res["matched_keywords"]
    assert "schema" in res["matched_keywords"]
    assert "horizontal scaling" in res["matched_keywords"]
    assert "NoSQL" in res["matched_keywords"]
    assert res["missing_keywords"] == ["graph"]
    assert res["score"] == pytest.approx((5 / 6) * 100.0, abs=0.1)


def test_rubric_evaluation():
    """Verify rubric clause matching rewards answers covering rubric points."""
    rubric = (
        "Candidates should define ACID properties in SQL and BASE in NoSQL. "
        "They should discuss schema rigidity vs flexibility and horizontal scaling."
    )
    strong_prep = EvaluationPreprocessor.preprocess(
        "SQL databases guarantee ACID properties with rigid schemas, while NoSQL systems "
        "favor BASE availability, flexible schemas, and horizontal scaling."
    )
    weak_prep = EvaluationPreprocessor.preprocess("Databases store data on disk.")

    strong_res = RubricEvaluator.evaluate(strong_prep, rubric)
    weak_res = RubricEvaluator.evaluate(weak_prep, rubric)

    assert strong_res["score"] > weak_res["score"]
    assert strong_res["score"] >= 70.0
    assert len(weak_res["missing_points"]) >= 1


def test_relevance_scoring():
    """Verify on-topic answers score significantly higher than off-topic or non-answers."""
    q_text = "Explain the key differences between SQL and NoSQL databases."
    keywords = ["SQL", "NoSQL", "ACID", "schema"]
    rubric = "Discuss ACID properties, schema flexibility, and scaling trade-offs."

    on_topic = EvaluationPreprocessor.preprocess(
        "SQL databases use structured schemas and ACID transactions, while NoSQL databases "
        "offer flexible schemas and horizontal scaling."
    )
    non_answer = EvaluationPreprocessor.preprocess("I don't know.")

    on_res = RelevanceEvaluator.evaluate(on_topic, q_text, keywords, rubric)
    off_res = RelevanceEvaluator.evaluate(non_answer, q_text, keywords, rubric)

    assert on_res["score"] >= 60.0
    assert on_res["is_off_topic"] is False
    assert off_res["score"] < 20.0
    assert off_res["is_off_topic"] is True


def test_completeness_scoring():
    """Verify detailed answers with reasoning markers score higher than terse answers."""
    terse = EvaluationPreprocessor.preprocess("Use Redis.")
    detailed = EvaluationPreprocessor.preprocess(
        "In a distributed system, caching with Redis reduces database read load because frequently "
        "accessed items are served from memory. For example, in cache-aside, the application checks "
        "the cache first and falls back to the database on a miss. Therefore, setting an appropriate "
        "TTL and preventing cache stampedes are important trade-offs for consistency."
    )

    terse_res = CompletenessEvaluator.evaluate(terse, category="technical", expected_duration_seconds=180)
    detailed_res = CompletenessEvaluator.evaluate(detailed, category="technical", expected_duration_seconds=180)

    assert terse_res["needs_more_detail"] is True
    assert terse_res["has_reasoning_or_examples"] is False
    assert detailed_res["has_reasoning_or_examples"] is True
    assert detailed_res["score"] > terse_res["score"] + 40.0


def test_star_evaluation_only_for_behavioral():
    """Verify STAR evaluation runs for behavioral questions and is skipped for technical questions."""
    behavioral_answer = EvaluationPreprocessor.preprocess(
        "At my previous company during a major release, my responsibility was to resolve a database bottleneck. "
        "I analyzed the slow queries and implemented composite indexes. As a result, API latency improved by 45%."
    )
    beh_res = STAREvaluator.evaluate(behavioral_answer, category="behavioral")
    tech_res = STAREvaluator.evaluate(behavioral_answer, category="technical")

    assert beh_res["applicable"] is True
    assert beh_res["score"] == 100.0
    assert beh_res["components"] == {
        "situation": True,
        "task": True,
        "action": True,
        "result": True,
    }
    assert beh_res["missing_components"] == []

    assert tech_res["applicable"] is False
    assert tech_res["score"] is None
    assert tech_res["components"] is None


def test_architecture_category_maps_to_technical_scoring():
    """Verify architecture questions use technical weights and do not invoke STAR evaluation."""
    arch_weights = ScoreCalculator.get_weights("architecture")
    assert arch_weights == CATEGORY_WEIGHTS["technical"]

    result = AnswerEvaluationPipeline.evaluate(
        answer_text=(
            "We should use a distributed Redis rate limiter with Sliding Window counters and atomic Lua scripts "
            "because stateless instances need centralized coordination and 429 Retry-After headers."
        ),
        question_text="Design a distributed rate limiter across stateless backend instances.",
        category="architecture",
        ideal_answer_rubric="Evaluate algorithms, centralized Redis Lua scripts, and 429 responses.",
        keywords=["Sliding Window", "Redis", "Lua script", "429"],
        expected_duration_seconds=240,
    )
    assert result["dimension_weights"] == CATEGORY_WEIGHTS["technical"]
    assert result["star_evaluation"] is None
    assert result["overall_score"] > 0.0


@pytest.mark.parametrize(
    "category",
    ["technical", "behavioral", "hr", "communication", "presentation", "architecture"],
)
def test_all_categories_have_valid_weights_and_bounded_scores(category: str):
    """Verify every question bank category and architecture has 100% weights and 0-100 bounded scores."""
    weights = ScoreCalculator.get_weights(category)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)

    for sample in [
        "",
        "Short.",
        "Bananas grow on tropical trees and have yellow peels.",
        "We discussed trade-offs and communication with the team.",
        (
            "In my previous project, my responsibility was to improve system reliability. "
            "I implemented Redis caching, composite indexes, and clear stakeholder communication. "
            "For example, we reduced latency by 40% because we eliminated redundant queries."
        ),
    ]:
        res = AnswerEvaluationPipeline.evaluate(
            answer_text=sample,
            question_text="Explain how you handled a complex system or team challenge.",
            category=category,
            ideal_answer_rubric="Discuss trade-offs, communication, caching, and measurable outcomes.",
            keywords=["Redis", "caching", "communication", "latency"],
            expected_duration_seconds=180,
        )
        for field in (
            "relevance_score",
            "keyword_coverage_score",
            "rubric_coverage_score",
            "completeness_score",
            "structure_score",
            "overall_score",
        ):
            assert 0.0 <= res[field] <= 100.0, f"{field} out of bounds for {category}"


def test_empty_short_irrelevant_partial_and_detailed_answer_progression():
    """Verify monotonic quality ordering and accurate feedback across answer quality levels."""
    q_text = "How does caching work in a distributed system, and how do you handle invalidation?"
    rubric = "Cover Redis, cache-aside, write-through, TTL invalidation, and cache stampede prevention."
    keywords = ["Redis", "cache-aside", "write-through", "TTL", "invalidation"]

    empty_res = AnswerEvaluationPipeline.evaluate("", q_text, "technical", rubric, keywords)
    short_res = AnswerEvaluationPipeline.evaluate("Use cache.", q_text, "technical", rubric, keywords)
    irrelevant_res = AnswerEvaluationPipeline.evaluate(
        "My favorite hobby is mountain biking on weekends because fresh air is relaxing.",
        q_text,
        "technical",
        rubric,
        keywords,
    )
    partial_res = AnswerEvaluationPipeline.evaluate(
        "We use Redis for caching and set a TTL so old keys expire.",
        q_text,
        "technical",
        rubric,
        keywords,
    )
    detailed_res = AnswerEvaluationPipeline.evaluate(
        "In distributed systems, Redis supports cache-aside and write-through patterns. "
        "For example, with cache-aside the service checks Redis first and loads from the database on a miss, "
        "then sets a TTL for invalidation. Therefore, write-through trades higher write latency for stronger consistency.",
        q_text,
        "technical",
        rubric,
        keywords,
    )

    assert empty_res["overall_score"] == 0.0
    assert irrelevant_res["overall_score"] < partial_res["overall_score"] < detailed_res["overall_score"]
    assert short_res["overall_score"] < detailed_res["overall_score"]
    assert "Redis" in detailed_res["matched_keywords"]
    assert len(irrelevant_res["missing_concepts"]) == len(keywords)
    assert any("more" in s.lower() or "missing" in s.lower() for s in short_res["improvement_suggestions"])


def test_overall_score_calculation_and_weights():
    """Verify category weights sum to 1.0 and overall score matches weighted sum."""
    for category, weights in CATEGORY_WEIGHTS.items():
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6), f"Weights for {category} must sum to 1.0"

    res = ScoreCalculator.calculate_overall_score(
        category="technical",
        relevance_score=80.0,
        keyword_coverage_score=90.0,
        rubric_coverage_score=70.0,
        completeness_score=60.0,
        structure_score=100.0,
    )
    # 80*0.20 + 90*0.30 + 70*0.30 + 60*0.15 + 100*0.05 = 16 + 27 + 21 + 9 + 5 = 78.0
    assert res["overall_score"] == 78.0


def test_feedback_generation_and_pipeline_integration():
    """Verify end-to-end pipeline generates evidence-backed strengths, missing concepts, and suggestions."""
    result = AnswerEvaluationPipeline.evaluate(
        answer_text=(
            "At my previous role during a sprint, I needed to align two engineers who disagreed on caching. "
            "I organized a design review to compare Redis and in-memory caching."
        ),
        question_text="Describe a situation where you had a technical disagreement with a team member.",
        category="behavioral",
        ideal_answer_rubric="Explain the situation, your task, the actions you took to resolve it, and the measurable result.",
        keywords=["disagreement", "design review", "compromise", "outcome"],
        expected_duration_seconds=180,
    )

    assert 0.0 <= result["overall_score"] <= 100.0
    assert result["star_evaluation"] is not None
    assert result["star_evaluation"]["applicable"] is True
    assert "result" in result["star_evaluation"]["missing_components"]
    assert "compromise" in result["missing_concepts"]
    assert any("STAR" in s for s in result["improvement_suggestions"])
    assert len(result["strengths"]) >= 1
    assert result["evaluation_method"] == "heuristic-v1.0"
