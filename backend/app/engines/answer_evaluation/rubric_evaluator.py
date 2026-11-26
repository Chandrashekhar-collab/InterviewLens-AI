"""Rubric-based evaluation comparing candidate answers against ideal_answer_rubric."""

import re
from typing import Any, Dict, List

from app.engines.answer_evaluation.preprocessor import EvaluationPreprocessor, PreprocessedAnswer


class RubricEvaluator:
    """Evaluates how well an answer covers clauses and concepts in the question rubric."""

    @classmethod
    def _extract_rubric_clauses(cls, rubric: str) -> List[str]:
        """Split an ideal answer rubric into meaningful evaluation clauses."""
        if not rubric or not rubric.strip():
            return []
        # Split on sentence boundaries and semicolons
        raw_clauses = re.split(r"[.;]+", rubric)
        clauses = [c.strip() for c in raw_clauses if len(EvaluationPreprocessor.tokenize(c)) >= 3]
        return clauses

    @classmethod
    def evaluate(
        cls,
        preprocessed: PreprocessedAnswer,
        ideal_answer_rubric: str,
    ) -> Dict[str, Any]:
        """Score rubric coverage (0-100) using concept and clause token overlap."""
        clauses = cls._extract_rubric_clauses(ideal_answer_rubric)
        if not clauses:
            return {
                "score": 100.0 if preprocessed.word_count > 0 else 0.0,
                "matched_points": [],
                "missing_points": [],
                "coverage_ratio": 1.0 if preprocessed.word_count > 0 else 0.0,
            }

        answer_content_set = {t.rstrip("s") for t in preprocessed.content_tokens}
        if not answer_content_set:
            return {
                "score": 0.0,
                "matched_points": [],
                "missing_points": clauses,
                "coverage_ratio": 0.0,
            }

        matched_points: List[str] = []
        missing_points: List[str] = []
        clause_scores: List[float] = []

        for clause in clauses:
            clause_tokens = EvaluationPreprocessor.extract_content_tokens(
                EvaluationPreprocessor.tokenize(clause)
            )
            if not clause_tokens:
                continue
            clause_stems = {t.rstrip("s") for t in clause_tokens}
            overlap = len(clause_stems & answer_content_set) / len(clause_stems)
            # A clause is considered addressed if >= 30% of its core content tokens appear
            clause_score = min(1.0, overlap / 0.5)
            clause_scores.append(clause_score)
            if overlap >= 0.25:
                matched_points.append(clause)
            else:
                missing_points.append(clause)

        if not clause_scores:
            return {
                "score": 100.0 if preprocessed.word_count > 0 else 0.0,
                "matched_points": [],
                "missing_points": [],
                "coverage_ratio": 1.0 if preprocessed.word_count > 0 else 0.0,
            }

        avg_score = sum(clause_scores) / len(clause_scores)
        return {
            "score": round(avg_score * 100.0, 2),
            "matched_points": matched_points,
            "missing_points": missing_points,
            "coverage_ratio": round(len(matched_points) / len(clause_scores), 4),
        }
