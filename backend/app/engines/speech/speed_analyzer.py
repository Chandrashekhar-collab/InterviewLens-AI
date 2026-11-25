"""Speaking speed analyzer calculating Words Per Minute (WPM)."""

import re
from typing import Any, Dict, Optional


class SpeakingSpeedAnalyzer:
    """Calculates spoken word count, speaking duration, and Words Per Minute (WPM)."""

    @classmethod
    def calculate_wpm(
        cls,
        transcript: str,
        duration_seconds: Optional[float],
    ) -> Dict[str, Any]:
        """Compute WPM from transcript and duration.

        Formula:
        WPM = Number of spoken words / (Speaking duration in minutes)

        Handles edge cases:
        - Empty or whitespace-only transcript -> 0 words, 0.0 WPM
        - Null or zero duration -> 0.0 WPM
        - Very short duration (< 1.0 second) -> 0.0 WPM (too short to reliably evaluate)
        """
        if not transcript or not transcript.strip():
            return {
                "word_count": 0,
                "speaking_duration_seconds": duration_seconds or 0.0,
                "words_per_minute": 0.0,
            }

        # Tokenize words, accounting for hyphenated words and contractions
        words = re.findall(r"\b[\w'-]+\b", transcript)
        word_count = len(words)

        if not duration_seconds or duration_seconds < 1.0:
            return {
                "word_count": word_count,
                "speaking_duration_seconds": duration_seconds or 0.0,
                "words_per_minute": 0.0,
            }

        duration_minutes = duration_seconds / 60.0
        wpm = round(word_count / duration_minutes, 1)

        return {
            "word_count": word_count,
            "speaking_duration_seconds": round(duration_seconds, 2),
            "words_per_minute": wpm,
        }
