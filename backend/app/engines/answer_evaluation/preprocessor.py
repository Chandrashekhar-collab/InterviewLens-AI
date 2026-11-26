"""Text preprocessing utilities for deterministic answer evaluation."""

from dataclasses import dataclass
import re
from typing import List, Set

STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "done", "for", "from", "had",
    "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "me", "more", "most",
    "my", "no", "not", "of", "on", "or", "other", "our", "ours", "out", "over",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "up", "use", "used", "using", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "with", "would", "you", "your", "yours",
}

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]+")


@dataclass(frozen=True)
class PreprocessedAnswer:
    """Normalized representation of a candidate answer or reference text."""

    raw_text: str
    normalized_text: str
    tokens: List[str]
    content_tokens: List[str]
    sentences: List[str]
    word_count: int
    sentence_count: int


class EvaluationPreprocessor:
    """Deterministic text normalizer and tokenizer for answer evaluation."""

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Collapse whitespace and lowercase text while preserving punctuation for sentence splitting."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip().lower()

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """Extract lowercase alphanumeric/hyphenated word tokens."""
        if not text:
            return []
        return _TOKEN_PATTERN.findall(text.lower())

    @classmethod
    def extract_content_tokens(cls, tokens: List[str]) -> List[str]:
        """Filter stopwords and single-character noise tokens."""
        return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    @classmethod
    def split_sentences(cls, text: str) -> List[str]:
        """Split text into non-empty sentences."""
        if not text or not text.strip():
            return []
        parts = [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]
        return parts

    @classmethod
    def preprocess(cls, text: str) -> PreprocessedAnswer:
        """Run full preprocessing pipeline on an answer string."""
        raw = (text or "").strip()
        normalized = cls.normalize_text(raw)
        tokens = cls.tokenize(normalized)
        content_tokens = cls.extract_content_tokens(tokens)
        sentences = cls.split_sentences(raw)
        return PreprocessedAnswer(
            raw_text=raw,
            normalized_text=normalized,
            tokens=tokens,
            content_tokens=content_tokens,
            sentences=sentences,
            word_count=len(tokens),
            sentence_count=len(sentences),
        )
