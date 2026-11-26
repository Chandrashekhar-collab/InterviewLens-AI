"""Master answer evaluation pipeline orchestrating all deterministic evaluation modules."""

from typing import Any, Dict, List

from app.engines.answer_evaluation.completeness_evaluator import CompletenessEvaluator
from app.engines.answer_evaluation.feedback_generator import FeedbackGenerator
from app.engines.answer_evaluation.keyword_evaluator import KeywordCoverageEvaluator
from app.engines.answer_evaluation.preprocessor import EvaluationPreprocessor
from app.engines.answer_evaluation.relevance_evaluator import RelevanceEvaluator
from app.engines.answer_evaluation.rubric_evaluator import RubricEvaluator
from app.engines.answer_evaluation.scoring import EVALUATION_METHOD_VERSION, ScoreCalculator
from app.engines.answer_evaluation.star_evaluator import STAREvaluator


class AnswerEvaluationPipeline:
    """Orchestrates deterministic, explainable answer evaluation out of 100."""

    @classmethod
    def evaluate(
        cls,
        answer_text: str,
        question_text: str,
        category: str,
        ideal_answer_rubric: str,
        keywords: List[str],
        expected_duration_seconds: int = 120,
    ) -> Dict[str, Any]:
        """Evaluate a candidate answer against question metadata and rubric."""
        preprocessed = EvaluationPreprocessor.preprocess(answer_text)

        relevance_res = RelevanceEvaluator.evaluate(
            preprocessed=preprocessed,
            question_text=question_text,
            keywords=keywords,
            ideal_answer_rubric=ideal_answer_rubric,
        )
        keyword_res = KeywordCoverageEvaluator.evaluate(
            preprocessed=preprocessed,
            keywords=keywords,
        )
        rubric_res = RubricEvaluator.evaluate(
            preprocessed=preprocessed,
            ideal_answer_rubric=ideal_answer_rubric,
        )
        completeness_res = CompletenessEvaluator.evaluate(
            preprocessed=preprocessed,
            category=category,
            expected_duration_seconds=expected_duration_seconds,
        )
        star_res = STAREvaluator.evaluate(
            preprocessed=preprocessed,
            category=category,
        )

        if star_res["applicable"] and star_res["score"] is not None:
            structure_score = star_res["score"]
        else:
            structure_score = ScoreCalculator.evaluate_general_structure(preprocessed)

        score_res = ScoreCalculator.calculate_overall_score(
            category=category,
            relevance_score=relevance_res["score"],
            keyword_coverage_score=keyword_res["score"],
            rubric_coverage_score=rubric_res["score"],
            completeness_score=completeness_res["score"],
            structure_score=structure_score,
        )

        feedback_res = FeedbackGenerator.generate(
            category=category,
            overall_score=score_res["overall_score"],
            relevance_res=relevance_res,
            keyword_res=keyword_res,
            rubric_res=rubric_res,
            completeness_res=completeness_res,
            star_res=star_res,
            structure_score=structure_score,
        )

        return {
            "relevance_score": relevance_res["score"],
            "keyword_coverage_score": keyword_res["score"],
            "rubric_coverage_score": rubric_res["score"],
            "completeness_score": completeness_res["score"],
            "structure_score": structure_score,
            "overall_score": score_res["overall_score"],
            "dimension_weights": score_res["weights"],
            "matched_keywords": keyword_res["matched_keywords"],
            "missing_concepts": feedback_res["missing_concepts"],
            "strengths": feedback_res["strengths"],
            "improvement_suggestions": feedback_res["improvement_suggestions"],
            "star_evaluation": star_res if star_res["applicable"] else None,
            "summary": feedback_res["summary"],
            "evaluation_method": EVALUATION_METHOD_VERSION,
        }
