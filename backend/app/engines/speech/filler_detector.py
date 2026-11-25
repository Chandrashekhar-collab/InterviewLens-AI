"""Filler-word detector identifying disfluencies in candidate speech."""

import re
from typing import Any, Dict, List, Optional

# Standard default dictionary of speech filler words and phrases
DEFAULT_FILLER_WORDS: List[str] = [
    "um",
    "uh",
    "hmm",
    "like",
    "you know",
    "basically",
    "actually",
    "i mean",
]


class FillerWordDetector:
    """Detects and counts filler words in transcripts using word-boundary matching."""

    def __init__(self, dictionary: Optional[List[str]] = None):
        self.dictionary = dictionary or DEFAULT_FILLER_WORDS
        # Compile word-boundary regex patterns
        self.patterns: Dict[str, re.Pattern] = {}
        for filler in self.dictionary:
            # Handle multi-word phrases vs single words
            words = [re.escape(w) for w in filler.strip().split()]
            pattern_str = r"\b" + r"\s+".join(words) + r"\b"
            self.patterns[filler.lower()] = re.compile(pattern_str, re.IGNORECASE)

    def analyze(
        self,
        transcript: str,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Analyze transcript for filler words.

        Returns:
        - total_filler_words: int
        - filler_words_breakdown: Dict[str, int]
        - filler_words_per_minute: float
        """
        if not transcript or not transcript.strip():
            return {
                "total_filler_words": 0,
                "filler_words_breakdown": {filler: 0 for filler in self.patterns},
                "filler_words_per_minute": 0.0,
            }

        breakdown: Dict[str, int] = {}
        total_count = 0

        for filler, pattern in self.patterns.items():
            matches = pattern.findall(transcript)
            count = len(matches)
            breakdown[filler] = count
            total_count += count

        # Calculate rate per minute if duration is available
        fillers_per_minute = 0.0
        if duration_seconds and duration_seconds >= 1.0:
            duration_minutes = duration_seconds / 60.0
            fillers_per_minute = round(total_count / duration_minutes, 2)

        return {
            "total_filler_words": total_count,
            "filler_words_breakdown": breakdown,
            "filler_words_per_minute": fillers_per_minute,
        }
