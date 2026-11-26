"""Answer completeness and explanation-quality evaluator."""

import re
from typing import Any, Dict

from app.engines.answer_evaluation.preprocessor import PreprocessedAnswer

_REASONING_MARKERS = re.compile(
    r"\b(because|therefore|since|thus|for example|for instance|such as|"
    r"specifically|trade-?off|compared to|whereas|however|as a result|"
    r"which means|in order to|consequently)\b",
    re.IGNORECASE,
)


class CompletenessEvaluator:
    """Evaluates answer depth, explanation quality, and reasoning/example indicators."""

    # Target substantive word counts by question category
    CATEGORY_TARGET_WORDS: Dict[str, int] = {
        "technical": 75,
        "architecture": 75,
        "behavioral": 90,
        "presentation": 85,
        "communication": 65,
        "hr": 55,
    }

    @classmethod
    def evaluate(
        cls,
        preprocessed: PreprocessedAnswer,
        category: str,
        expected_duration_seconds: int = 120,
    ) -> Dict[str, Any]:
        """Compute completeness score (0-100) from depth, sentence structure, and reasoning."""
        if preprocessed.word_count == 0:
            return {
                "score": 0.0,
                "word_count": 0,
                "sentence_count": 0,
                "has_reasoning_or_examples": False,
                "needs_more_detail": True,
            }

        cat = (category or "technical").lower()
        base_target = cls.CATEGORY_TARGET_WORDS.get(cat, 70)
        # Lightly scale target for longer expected durations (>= 180s)
        if expected_duration_seconds >= 240:
            target_words = int(base_target * 1.2)
        elif expected_duration_seconds <= 90:
            target_words = int(base_target * 0.85)
        else:
            target_words = base_target

        length_ratio = min(1.0, preprocessed.word_count / max(target_words, 1))
        # Expect at least 3 distinct sentences for a well-elaborated response
        sentence_ratio = min(1.0, preprocessed.sentence_count / 3.0)

        reasoning_matches = _REASONING_MARKERS.findall(preprocessed.raw_text)
        has_reasoning = len(reasoning_matches) > 0
        reasoning_bonus = min(1.0, len(reasoning_matches) / 2.0)

        score = (length_ratio * 0.55 + sentence_ratio * 0.25 + reasoning_bonus * 0.20) * 100.0
        score = round(min(100.0, score), 2)

        return {
            "score": score,
            "word_count": preprocessed.word_count,
            "sentence_count": preprocessed.sentence_count,
            "has_reasoning_or_examples": has_reasoning,
            "needs_more_detail": preprocessed.word_count < max(25, target_words // 2),
        }
