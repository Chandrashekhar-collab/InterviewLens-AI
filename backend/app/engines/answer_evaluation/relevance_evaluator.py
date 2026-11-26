"""Answer relevance evaluator measuring alignment with the asked question."""

from collections import Counter
import math
import re
from typing import Any, Dict, List

from app.engines.answer_evaluation.preprocessor import EvaluationPreprocessor, PreprocessedAnswer

_NON_ANSWER_PATTERNS = [
    re.compile(r"^(i\s+don'?t\s+know|no\s+idea|not\s+sure|pass|skip)\.?$", re.IGNORECASE),
]


class RelevanceEvaluator:
    """Measures topical relevance of an answer to the question prompt and domain vocabulary."""

    @classmethod
    def _cosine_similarity(cls, tokens_a: List[str], tokens_b: List[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        vec_a = Counter(t.rstrip("s") for t in tokens_a)
        vec_b = Counter(t.rstrip("s") for t in tokens_b)
        common = set(vec_a.keys()) & set(vec_b.keys())
        dot = sum(vec_a[k] * vec_b[k] for k in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @classmethod
    def evaluate(
        cls,
        preprocessed: PreprocessedAnswer,
        question_text: str,
        keywords: List[str],
        ideal_answer_rubric: str,
    ) -> Dict[str, Any]:
        """Compute relevance score (0-100) against question prompt and expected concepts."""
        if preprocessed.word_count == 0:
            return {"score": 0.0, "is_off_topic": True}

        for pat in _NON_ANSWER_PATTERNS:
            if pat.match(preprocessed.raw_text):
                return {"score": 5.0, "is_off_topic": True}

        reference_text = " ".join([
            question_text or "",
            " ".join(keywords or []),
            ideal_answer_rubric or "",
        ])
        ref_tokens = EvaluationPreprocessor.extract_content_tokens(
            EvaluationPreprocessor.tokenize(reference_text)
        )

        if not ref_tokens or not preprocessed.content_tokens:
            return {"score": 0.0, "is_off_topic": True}

        similarity = cls._cosine_similarity(preprocessed.content_tokens, ref_tokens)
        # Direct question-term overlap bonus
        q_tokens = set(
            t.rstrip("s")
            for t in EvaluationPreprocessor.extract_content_tokens(
                EvaluationPreprocessor.tokenize(question_text or "")
            )
        )
        a_tokens = set(t.rstrip("s") for t in preprocessed.content_tokens)
        q_overlap = (len(q_tokens & a_tokens) / len(q_tokens)) if q_tokens else 0.0

        # Scale heuristic similarity: >= 0.35 cosine similarity + question overlap -> high relevance
        combined = min(1.0, (similarity / 0.35) * 0.7 + min(1.0, q_overlap / 0.4) * 0.3)
        score = round(combined * 100.0, 2)

        return {
            "score": score,
            "is_off_topic": score < 25.0,
        }
