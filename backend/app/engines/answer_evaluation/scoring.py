"""Category-aware dimension weighting and overall score calculation."""

import re
from typing import Any, Dict

from app.engines.answer_evaluation.preprocessor import PreprocessedAnswer

EVALUATION_METHOD_VERSION = "heuristic-v1.0"

# Category aliases (e.g. architecture questions use technical evaluation weights)
CATEGORY_ALIASES: Dict[str, str] = {
    "architecture": "technical",
}

# Category-specific evaluation weights (each row sums strictly to 1.00)
CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "technical": {
        "relevance": 0.20,
        "keyword_coverage": 0.30,
        "rubric_coverage": 0.30,
        "completeness": 0.15,
        "structure": 0.05,
    },
    "behavioral": {
        "relevance": 0.20,
        "keyword_coverage": 0.15,
        "rubric_coverage": 0.20,
        "completeness": 0.15,
        "structure": 0.30,  # Uses STAR-method score
    },
    "hr": {
        "relevance": 0.25,
        "keyword_coverage": 0.15,
        "rubric_coverage": 0.25,
        "completeness": 0.20,
        "structure": 0.15,
    },
    "communication": {
        "relevance": 0.25,
        "keyword_coverage": 0.15,
        "rubric_coverage": 0.20,
        "completeness": 0.20,
        "structure": 0.20,
    },
    "presentation": {
        "relevance": 0.20,
        "keyword_coverage": 0.20,
        "rubric_coverage": 0.25,
        "completeness": 0.15,
        "structure": 0.20,
    },
}

_STRUCTURE_TRANSITIONS = re.compile(
    r"\b(first|firstly|second|secondly|finally|in summary|to summarize|"
    r"on the other hand|additionally|moreover|overall|in conclusion|"
    r"step\s+\d+|pros and cons|trade-?offs?)\b",
    re.IGNORECASE,
)


class ScoreCalculator:
    """Computes structure score (for non-STAR categories) and weighted overall score."""

    @classmethod
    def get_weights(cls, category: str) -> Dict[str, float]:
        """Return the normalized weight mapping for a question category."""
        cat = (category or "technical").lower()
        canonical = CATEGORY_ALIASES.get(cat, cat)
        return dict(CATEGORY_WEIGHTS.get(canonical, CATEGORY_WEIGHTS["technical"]))

    @classmethod
    def evaluate_general_structure(cls, preprocessed: PreprocessedAnswer) -> float:
        """Score logical organization (0-100) for non-behavioral questions."""
        if preprocessed.word_count == 0:
            return 0.0
        sentence_score = min(1.0, preprocessed.sentence_count / 3.0) * 60.0
        transition_hits = len(_STRUCTURE_TRANSITIONS.findall(preprocessed.raw_text))
        transition_score = min(1.0, transition_hits / 2.0) * 40.0
        return round(min(100.0, sentence_score + transition_score), 2)

    @classmethod
    def calculate_overall_score(
        cls,
        category: str,
        relevance_score: float,
        keyword_coverage_score: float,
        rubric_coverage_score: float,
        completeness_score: float,
        structure_score: float,
    ) -> Dict[str, Any]:
        """Compute weighted overall score (0-100) using category-specific weights."""
        weights = cls.get_weights(category)
        overall = (
            relevance_score * weights["relevance"]
            + keyword_coverage_score * weights["keyword_coverage"]
            + rubric_coverage_score * weights["rubric_coverage"]
            + completeness_score * weights["completeness"]
            + structure_score * weights["structure"]
        )
        return {
            "overall_score": round(max(0.0, min(100.0, overall)), 2),
            "weights": weights,
        }
