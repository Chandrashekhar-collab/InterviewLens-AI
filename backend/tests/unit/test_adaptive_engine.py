"""Unit tests for the rule-based Adaptive Question Engine."""

from app.engines.question_gen.adaptive_engine import AdaptiveQuestionEngine


def test_adaptive_difficulty_step_up_on_high_score():
    """Verify score >= 75 steps up difficulty until capped at 'hard'."""
    # easy -> medium
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", 75.0) == "medium"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", 90.0) == "medium"

    # medium -> hard
    assert AdaptiveQuestionEngine.calculate_next_difficulty("medium", 80.0) == "hard"

    # hard -> hard (capped)
    assert AdaptiveQuestionEngine.calculate_next_difficulty("hard", 95.0) == "hard"


def test_adaptive_difficulty_maintain_on_moderate_score():
    """Verify score between 50 and 74.9 maintains current difficulty."""
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", 50.0) == "easy"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", 68.5) == "easy"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("medium", 65.0) == "medium"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("hard", 70.0) == "hard"


def test_adaptive_difficulty_step_down_on_low_score():
    """Verify score < 50 steps down difficulty until floored at 'easy'."""
    # hard -> medium
    assert AdaptiveQuestionEngine.calculate_next_difficulty("hard", 49.9) == "medium"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("hard", 20.0) == "medium"

    # medium -> easy
    assert AdaptiveQuestionEngine.calculate_next_difficulty("medium", 45.0) == "easy"

    # easy -> easy (floored)
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", 10.0) == "easy"


def test_adaptive_difficulty_initial_question():
    """Verify None score retains configured base difficulty."""
    assert AdaptiveQuestionEngine.calculate_next_difficulty("easy", None) == "easy"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("medium", None) == "medium"
    assert AdaptiveQuestionEngine.calculate_next_difficulty("hard", None) == "hard"


def test_determine_target_category():
    """Verify targeted vs mixed category sequence."""
    # Targeted interview types always return exact type
    assert AdaptiveQuestionEngine.determine_target_category("technical", 1) == "technical"
    assert AdaptiveQuestionEngine.determine_target_category("behavioral", 3) == "behavioral"
    assert AdaptiveQuestionEngine.determine_target_category("presentation", 2) == "presentation"

    # Mixed interview types follow structured sequence
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 1) == "behavioral"
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 2) == "technical"
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 3) == "technical"
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 4) == "communication"
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 5) == "presentation"
    assert AdaptiveQuestionEngine.determine_target_category("mixed", 6) == "hr"
