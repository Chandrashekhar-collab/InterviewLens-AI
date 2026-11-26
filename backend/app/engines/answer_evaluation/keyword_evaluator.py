"""Keyword and expected concept coverage evaluator."""

import re
from typing import Any, Dict, List

from app.engines.answer_evaluation.preprocessor import EvaluationPreprocessor, PreprocessedAnswer


class KeywordCoverageEvaluator:
    """Evaluates presence of expected question keywords/concepts in a candidate answer.

    Note: Keyword matching measures whether expected terminology appears in the
    response; it does not by itself prove deep technical correctness.
    """

    @classmethod
    def _keyword_matches(cls, keyword: str, normalized_text: str, token_set: set[str]) -> bool:
        """Check whether a keyword or short phrase appears in the normalized answer."""
        kw_norm = EvaluationPreprocessor.normalize_text(keyword)
        if not kw_norm:
            return False

        # Exact word/phrase boundary match
        pattern = re.compile(r"(?<!\w)" + re.escape(kw_norm) + r"(?!\w)")
        if pattern.search(normalized_text):
            return True

        # Light plural/hyphen tolerance for single or multi-word keywords
        kw_tokens = EvaluationPreprocessor.extract_content_tokens(
            EvaluationPreprocessor.tokenize(kw_norm)
        )
        if not kw_tokens:
            return False

        if len(kw_tokens) == 1:
            kt = kw_tokens[0]
            return any(t == kt or t.rstrip("s") == kt.rstrip("s") for t in token_set)

        # For multi-word concepts, require all content tokens to be present
        return all(
            any(t == kt or t.rstrip("s") == kt.rstrip("s") for t in token_set)
            for kt in kw_tokens
        )

    @classmethod
    def evaluate(
        cls,
        preprocessed: PreprocessedAnswer,
        keywords: List[str],
    ) -> Dict[str, Any]:
        """Compute keyword coverage score (0-100) and matched/missing lists."""
        clean_keywords = [kw.strip() for kw in (keywords or []) if kw and kw.strip()]
        if not clean_keywords:
            return {
                "score": 100.0 if preprocessed.word_count > 0 else 0.0,
                "matched_keywords": [],
                "missing_keywords": [],
                "coverage_ratio": 1.0 if preprocessed.word_count > 0 else 0.0,
            }

        token_set = set(preprocessed.tokens)
        matched: List[str] = []
        missing: List[str] = []

        for kw in clean_keywords:
            if cls._keyword_matches(kw, preprocessed.normalized_text, token_set):
                matched.append(kw)
            else:
                missing.append(kw)

        ratio = len(matched) / len(clean_keywords)
        score = round(ratio * 100.0, 2)

        return {
            "score": score,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "coverage_ratio": round(ratio, 4),
        }
