"""Comprehensive speech analysis pipeline integrating transcription, speed, fluency, pauses, and pitch."""

import logging
from typing import Any, Dict, Optional
from app.engines.speech.audio_preprocessor import AudioPreprocessor
from app.engines.speech.compat import apply_pyav_compatibility_patch
from app.engines.speech.filler_detector import FillerWordDetector
from app.engines.speech.pitch_analyzer import PitchAnalyzer
from app.engines.speech.silence_detector import SilenceDetector
from app.engines.speech.speed_analyzer import SpeakingSpeedAnalyzer
from app.engines.speech.transcriber import SpeechTranscriber

logger = logging.getLogger("interviewlens.speech.pipeline")

# Ensure PyAV patch is active
apply_pyav_compatibility_patch()


class SpeechAnalysisPipeline:
    """Master analytical orchestrator for speech delivery metrics."""

    def __init__(self):
        self.filler_detector = FillerWordDetector()
        self.silence_detector = SilenceDetector()

    def analyze_audio(
        self,
        audio_path: str,
        audio_duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute full acoustic and delivery analysis on a recorded audio file.

        Separation of Concerns:
        This engine evaluates speech mechanics (transcription, delivery pace, fillers, pauses, pitch).
        It does not evaluate technical correctness or domain semantic accuracy.
        """
        logger.info(f"Initiating speech analysis pipeline for: {audio_path}")

        # 1. Speech-to-Text Transcription (faster-whisper)
        transcription_res = SpeechTranscriber.transcribe(audio_path)
        transcription_status = transcription_res.get("transcription_status", "completed")
        transcript = transcription_res.get("transcription")
        detected_lang = transcription_res.get("detected_language")
        duration = audio_duration_seconds or transcription_res.get("transcription_duration_seconds") or 0.0

        # Physical acoustic measurements (silence and pitch)
        silence_res = self.silence_detector.analyze(audio_path)
        pitch_res = PitchAnalyzer.analyze(audio_path)

        # Guard against transcription failure:
        # Do NOT silently produce misleading zero scores for WPM, word count, or filler words
        if transcription_status != "completed" or transcript is None:
            logger.warning(
                f"Transcription failed for '{audio_path}': {transcription_res.get('error_message')}. "
                "Returning None for transcription-derived metrics to prevent misleading zero scores."
            )
            return {
                "transcription": None,
                "detected_language": None,
                "transcription_status": "failed",
                "transcription_duration_seconds": transcription_res.get("transcription_duration_seconds"),
                "segments": [],
                "word_count": None,
                "speaking_duration_seconds": duration if duration > 0 else None,
                "words_per_minute": None,
                "total_filler_words": None,
                "filler_words_breakdown": {},
                "filler_words_per_minute": None,
                "pause_count": silence_res.get("pause_count"),
                "total_silence_seconds": silence_res.get("total_silence_seconds"),
                "average_pause_seconds": silence_res.get("average_pause_seconds"),
                "long_pause_count": silence_res.get("long_pause_count"),
                "average_pitch_hz": pitch_res.get("average_pitch_hz"),
                "min_pitch_hz": pitch_res.get("min_pitch_hz"),
                "max_pitch_hz": pitch_res.get("max_pitch_hz"),
                "pitch_variation_hz": pitch_res.get("pitch_variation_hz"),
                "pitch_status": pitch_res.get("pitch_status", "unavailable"),
                "processing_status": "failed",
                "error_message": transcription_res.get("error_message") or "Speech transcription failed",
            }

        # 2. Speaking Speed Analysis (WPM)
        speed_res = SpeakingSpeedAnalyzer.calculate_wpm(
            transcript=transcript,
            duration_seconds=duration,
        )

        # 3. Filler-Word Detection
        filler_res = self.filler_detector.analyze(
            transcript=transcript,
            duration_seconds=duration,
        )

        return {
            "transcription": transcript,
            "detected_language": detected_lang,
            "transcription_status": "completed",
            "transcription_duration_seconds": transcription_res.get("transcription_duration_seconds"),
            "segments": transcription_res.get("segments", []),
            "word_count": speed_res["word_count"],
            "speaking_duration_seconds": speed_res["speaking_duration_seconds"],
            "words_per_minute": speed_res["words_per_minute"],
            "total_filler_words": filler_res["total_filler_words"],
            "filler_words_breakdown": filler_res["filler_words_breakdown"],
            "filler_words_per_minute": filler_res["filler_words_per_minute"],
            "pause_count": silence_res["pause_count"],
            "total_silence_seconds": silence_res["total_silence_seconds"],
            "average_pause_seconds": silence_res["average_pause_seconds"],
            "long_pause_count": silence_res["long_pause_count"],
            "average_pitch_hz": pitch_res["average_pitch_hz"],
            "min_pitch_hz": pitch_res["min_pitch_hz"],
            "max_pitch_hz": pitch_res["max_pitch_hz"],
            "pitch_variation_hz": pitch_res["pitch_variation_hz"],
            "pitch_status": pitch_res["pitch_status"],
            "processing_status": "completed",
            "error_message": None,
        }
