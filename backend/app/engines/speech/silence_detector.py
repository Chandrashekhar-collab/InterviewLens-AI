"""Pause and silence detector using frame-level energy analysis."""

import logging
from typing import Any, Dict, List, Tuple
import numpy as np
import soundfile as sf
from app.config import settings
from app.engines.speech.compat import apply_pyav_compatibility_patch

logger = logging.getLogger("interviewlens.speech.silence")

apply_pyav_compatibility_patch()


class SilenceDetector:
    """Detects pauses, hesitation gaps, and silence duration in audio files using RMS energy.

    Technical Limitations:
    Energy-based silence detection relies on amplitude thresholds. High background ambient
    noise or low microphone gain can shift the noise floor, occasionally impacting precision.
    To mitigate this, a relative dynamic baseline coupled with an absolute decibel floor is applied.
    """

    def __init__(
        self,
        energy_threshold_db: float = settings.SILENCE_ENERGY_THRESHOLD_DB,
        min_silence_seconds: float = settings.MIN_SILENCE_DURATION_SECONDS,
        long_pause_seconds: float = settings.LONG_PAUSE_DURATION_SECONDS,
    ):
        self.energy_threshold_db = energy_threshold_db
        self.min_silence_seconds = min_silence_seconds
        self.long_pause_seconds = long_pause_seconds

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """Detect silence intervals and calculate pause metrics.

        Returns:
        - pause_count: int
        - total_silence_seconds: float
        - average_pause_seconds: float
        - long_pause_count: int
        - pauses: List[Tuple[float, float]]  # (start_s, end_s)
        """
        try:
            data, sample_rate = sf.read(audio_path, dtype="float32")
        except Exception as exc:
            logger.warning(f"Soundfile could not read '{audio_path}' for silence detection: {exc}")
            # Fallback to AudioPreprocessor if soundfile fails directly
            try:
                from app.engines.speech.audio_preprocessor import AudioPreprocessor
                data, _ = AudioPreprocessor.load_audio(audio_path)
                sample_rate = AudioPreprocessor.TARGET_SAMPLE_RATE
            except Exception as prep_err:
                logger.error(f"Failed to load audio for silence detection: {prep_err}")
                return {
                    "pause_count": 0,
                    "total_silence_seconds": 0.0,
                    "average_pause_seconds": 0.0,
                    "long_pause_count": 0,
                    "pauses": [],
                }

        # Handle stereo -> mono
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        total_samples = len(data)
        if total_samples == 0 or sample_rate <= 0:
            return {
                "pause_count": 0,
                "total_silence_seconds": 0.0,
                "average_pause_seconds": 0.0,
                "long_pause_count": 0,
                "pauses": [],
            }

        frame_duration = 0.05  # 50 ms window
        hop_duration = 0.025   # 25 ms hop
        frame_len = int(sample_rate * frame_duration)
        hop_len = int(sample_rate * hop_duration)

        if total_samples < frame_len:
            return {
                "pause_count": 0,
                "total_silence_seconds": 0.0,
                "average_pause_seconds": 0.0,
                "long_pause_count": 0,
                "pauses": [],
            }

        # Calculate frame RMS values
        num_frames = 1 + (total_samples - frame_len) // hop_len
        rms_values = np.zeros(num_frames, dtype=np.float32)

        for i in range(num_frames):
            start = i * hop_len
            frame = data[start : start + frame_len]
            rms = np.sqrt(np.mean(frame**2) + 1e-9)
            rms_values[i] = rms

        # Convert to dB relative to full scale
        db_values = 20.0 * np.log10(rms_values + 1e-9)

        # Dynamic adaptive threshold:
        # 18 dB below speaker's 95th percentile volume, clamped within [-45 dB, -20 dB]
        p95_db = float(np.percentile(db_values, 95))
        dynamic_threshold = p95_db - 18.0
        effective_threshold = max(-45.0, min(-20.0, max(self.energy_threshold_db, dynamic_threshold)))

        is_silent = db_values < effective_threshold

        # Find contiguous silent segments
        pauses: List[Tuple[float, float]] = []
        in_silence = False
        silence_start_frame = 0

        for idx, silent in enumerate(is_silent):
            if silent and not in_silence:
                in_silence = True
                silence_start_frame = idx
            elif not silent and in_silence:
                in_silence = False
                duration = (idx - silence_start_frame) * hop_duration
                if duration >= self.min_silence_seconds:
                    start_sec = silence_start_frame * hop_duration
                    end_sec = idx * hop_duration
                    pauses.append((round(start_sec, 2), round(end_sec, 2)))

        # Handle segment extending to end of audio
        if in_silence:
            duration = (len(is_silent) - silence_start_frame) * hop_duration
            if duration >= self.min_silence_seconds:
                start_sec = silence_start_frame * hop_duration
                end_sec = len(is_silent) * hop_duration
                pauses.append((round(start_sec, 2), round(end_sec, 2)))

        total_silence = sum(end - start for start, end in pauses)
        pause_count = len(pauses)
        avg_pause = (total_silence / pause_count) if pause_count > 0 else 0.0
        long_pause_count = sum(1 for start, end in pauses if (end - start) >= self.long_pause_seconds)

        return {
            "pause_count": pause_count,
            "total_silence_seconds": round(total_silence, 2),
            "average_pause_seconds": round(avg_pause, 2),
            "long_pause_count": long_pause_count,
            "pauses": pauses,
        }
