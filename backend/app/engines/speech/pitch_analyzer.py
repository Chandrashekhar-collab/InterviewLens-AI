"""Voice pitch analyzer using Parselmouth for fundamental frequency (F0) extraction."""

import logging
from typing import Any, Dict, Optional
import numpy as np

logger = logging.getLogger("interviewlens.speech.pitch")


class PitchAnalyzer:
    """Extracts acoustic pitch parameters (mean, min, max, standard deviation) using Praat/Parselmouth.

    Important:
    Pitch statistics represent physical acoustic frequency properties of vocal fold vibration.
    They do not infer personality, honesty, or subjective psychological states.
    """

    @classmethod
    def analyze(cls, audio_path: str) -> Dict[str, Any]:
        """Analyze voiced segments of audio to extract fundamental frequency (F0) metrics.

        Returns:
        - average_pitch_hz: Optional[float]
        - min_pitch_hz: Optional[float]
        - max_pitch_hz: Optional[float]
        - pitch_variation_hz: Optional[float]
        - pitch_status: str ("measured", "insufficient_voiced_segments", or "unavailable")
        """
        try:
            import parselmouth

            sound = parselmouth.Sound(audio_path)
            # Compute pitch with default human vocal range: 75 Hz to 500 Hz
            pitch = sound.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=500.0)
            pitch_values = pitch.selected_array["frequency"]

            # Filter unvoiced frames (frequency == 0 in Praat)
            voiced_frames = pitch_values[pitch_values > 0]

            if len(voiced_frames) < 5:
                return {
                    "average_pitch_hz": None,
                    "min_pitch_hz": None,
                    "max_pitch_hz": None,
                    "pitch_variation_hz": None,
                    "pitch_status": "insufficient_voiced_segments",
                }

            avg_pitch = float(np.mean(voiced_frames))
            min_pitch = float(np.min(voiced_frames))
            max_pitch = float(np.max(voiced_frames))
            std_pitch = float(np.std(voiced_frames))

            return {
                "average_pitch_hz": round(avg_pitch, 1),
                "min_pitch_hz": round(min_pitch, 1),
                "max_pitch_hz": round(max_pitch, 1),
                "pitch_variation_hz": round(std_pitch, 1),
                "pitch_status": "measured",
            }

        except Exception as exc:
            logger.warning(f"Parselmouth pitch analysis unavailable for '{audio_path}': {exc}")
            return {
                "average_pitch_hz": None,
                "min_pitch_hz": None,
                "max_pitch_hz": None,
                "pitch_variation_hz": None,
                "pitch_status": "unavailable",
            }
