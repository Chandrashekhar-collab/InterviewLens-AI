"""Speech analysis engine package."""

from app.engines.speech.analyzer import SpeechAnalysisPipeline
from app.engines.speech.audio_preprocessor import AudioPreprocessor
from app.engines.speech.compat import apply_pyav_compatibility_patch
from app.engines.speech.filler_detector import FillerWordDetector
from app.engines.speech.pitch_analyzer import PitchAnalyzer
from app.engines.speech.silence_detector import SilenceDetector
from app.engines.speech.speed_analyzer import SpeakingSpeedAnalyzer
from app.engines.speech.transcriber import SpeechTranscriber

# Auto-apply compatibility patch on package import
apply_pyav_compatibility_patch()

__all__ = [
    "AudioPreprocessor",
    "apply_pyav_compatibility_patch",
    "SpeechTranscriber",
    "SpeakingSpeedAnalyzer",
    "FillerWordDetector",
    "SilenceDetector",
    "PitchAnalyzer",
    "SpeechAnalysisPipeline",
]
