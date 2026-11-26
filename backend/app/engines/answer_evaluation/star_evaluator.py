"""STAR-method (Situation, Task, Action, Result) evaluator for behavioral questions."""

import re
from typing import Any, Dict, List

from app.engines.answer_evaluation.preprocessor import PreprocessedAnswer

_STAR_PATTERNS: Dict[str, re.Pattern[str]] = {
    "situation": re.compile(
        r"\b(situation|context|background|when i was|at my previous|in a previous|"
        r"during a project|on a team|faced a|there was a|we had a)\b",
        re.IGNORECASE,
    ),
    "task": re.compile(
        r"\b(task|my role|my responsibility|responsible for|tasked with|goal was|"
        r"objective|i needed to|we needed to|assigned to|challenge was)\b",
        re.IGNORECASE,
    ),
    "action": re.compile(
        r"\b(action|i took|i implemented|i designed|i built|i refactored|i led|"
        r"i coordinated|i analyzed|i resolved|i communicated|i proposed|"
        r"i created|i fixed|i investigated|steps i took)\b",
        re.IGNORECASE,
    ),
    "result": re.compile(
        r"\b(result|outcome|impact|eventually|as a result|consequently|reduced|"
        r"improved|increased|saved|delivered|launched|resolved the|achieved|"
        r"learned|retrospective)\b|\d+\s*%",
        re.IGNORECASE,
    ),
}

_COMPONENT_WEIGHTS: Dict[str, float] = {
    "situation": 20.0,
    "task": 20.0,
    "action": 35.0,
    "result": 25.0,
}


class STAREvaluator:
    """Evaluates STAR structure exclusively for behavioral interview questions."""

    APPLICABLE_CATEGORIES = {"behavioral"}

    @classmethod
    def is_applicable(cls, category: str) -> bool:
        """Return True only when STAR evaluation applies to the question category."""
        return (category or "").lower() in cls.APPLICABLE_CATEGORIES

    @classmethod
    def evaluate(cls, preprocessed: PreprocessedAnswer, category: str) -> Dict[str, Any]:
        """Evaluate STAR components if applicable; otherwise return applicable=False."""
        if not cls.is_applicable(category):
            return {
                "applicable": False,
                "score": None,
                "components": None,
                "missing_components": [],
            }

        text = preprocessed.raw_text
        components: Dict[str, bool] = {}
        missing: List[str] = []
        total_score = 0.0

        for comp, pattern in _STAR_PATTERNS.items():
            present = bool(pattern.search(text))
            components[comp] = present
            if present:
                total_score += _COMPONENT_WEIGHTS[comp]
            else:
                missing.append(comp)

        return {
            "applicable": True,
            "score": round(total_score, 2),
            "components": components,
            "missing_components": missing,
        }
