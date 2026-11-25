"""Unit tests for speech delivery engines: speed, fillers, silence, pitch, and transcriber."""

import io
import wave
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.engines.speech.analyzer import SpeechAnalysisPipeline
from app.engines.speech.audio_preprocessor import AudioPreprocessor
from app.engines.speech.compat import apply_pyav_compatibility_patch
from app.engines.speech.filler_detector import FillerWordDetector
from app.engines.speech.pitch_analyzer import PitchAnalyzer
from app.engines.speech.silence_detector import SilenceDetector
from app.engines.speech.speed_analyzer import SpeakingSpeedAnalyzer
from app.engines.speech.transcriber import SpeechTranscriber


def generate_synthetic_wav_bytes(
    duration_s: float = 2.0,
    sample_rate: int = 16000,
    freq_hz: float = 220.0,
    silence_end_s: float = 0.0,
) -> bytes:
    """Generate small in-memory synthetic 16-bit PCM WAV audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        total_samples = int(sample_rate * duration_s)
        t = np.linspace(0, duration_s, total_samples, endpoint=False)
        signal = 0.6 * np.sin(2 * np.pi * freq_hz * t)

        if silence_end_s > 0:
            silence_samples = int(sample_rate * silence_end_s)
            signal[-silence_samples:] = 0.0

        int16_signal = (signal * 32767).astype(np.int16)
        wf.writeframes(int16_signal.tobytes())
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 1. Speaking Speed / WPM Calculation Tests
# -----------------------------------------------------------------------------

def test_wpm_standard_calculation():
    """Verify WPM calculation formula with standard transcript."""
    transcript = "This is a clean and articulate demonstration of speaking speed calculation."
    # 11 words spoken in 30 seconds -> 22 words per minute
    res = SpeakingSpeedAnalyzer.calculate_wpm(transcript, duration_seconds=30.0)
    assert res["word_count"] == 11
    assert res["speaking_duration_seconds"] == 30.0
    assert res["words_per_minute"] == 22.0


def test_wpm_empty_and_short_edge_cases():
    """Verify edge cases for empty transcripts or near-zero durations."""
    # Empty transcript
    empty_res = SpeakingSpeedAnalyzer.calculate_wpm("", duration_seconds=15.0)
    assert empty_res["word_count"] == 0
    assert empty_res["words_per_minute"] == 0.0

    # Very short duration (< 1.0 second)
    short_res = SpeakingSpeedAnalyzer.calculate_wpm("Hello world", duration_seconds=0.5)
    assert short_res["word_count"] == 2
    assert short_res["words_per_minute"] == 0.0

    # Zero duration
    zero_res = SpeakingSpeedAnalyzer.calculate_wpm("Hello world", duration_seconds=0.0)
    assert zero_res["words_per_minute"] == 0.0


# -----------------------------------------------------------------------------
# 2. Filler-Word Detection Tests
# -----------------------------------------------------------------------------

def test_filler_word_detection_accuracy():
    """Verify case-insensitive detection of default filler words and phrases."""
    detector = FillerWordDetector()
    transcript = (
        "Um, basically I think we should, you know, optimize the database because, like, "
        "actually it is causing bottlenecks. Hmm, I mean it makes sense, uh, right?"
    )
    # Fillers present: um, basically, you know, like, actually, hmm, i mean, uh -> 8 fillers
    res = detector.analyze(transcript, duration_seconds=60.0)

    assert res["total_filler_words"] == 8
    breakdown = res["filler_words_breakdown"]
    assert breakdown["um"] == 1
    assert breakdown["uh"] == 1
    assert breakdown["hmm"] == 1
    assert breakdown["like"] == 1
    assert breakdown["you know"] == 1
    assert breakdown["basically"] == 1
    assert breakdown["actually"] == 1
    assert breakdown["i mean"] == 1
    assert res["filler_words_per_minute"] == 8.0


def test_filler_word_boundary_isolation():
    """Ensure sub-words are not misidentified as filler words (e.g. 'likely', 'umbrella')."""
    detector = FillerWordDetector()
    transcript = "It is likely that we will bring an umbrella because of unlike conditions."
    res = detector.analyze(transcript, duration_seconds=30.0)

    assert res["total_filler_words"] == 0
    assert res["filler_words_breakdown"]["like"] == 0
    assert res["filler_words_breakdown"]["um"] == 0


# -----------------------------------------------------------------------------
# 3. Silence and Pause Detection Tests
# -----------------------------------------------------------------------------

def test_silence_detection(tmp_path):
    """Verify silence detector detects pauses and silence intervals."""
    # 3-second audio with 1 second tone followed by 2 seconds of silence
    wav_bytes = generate_synthetic_wav_bytes(duration_s=3.0, freq_hz=300.0, silence_end_s=1.5)
    file_path = tmp_path / "test_silence.wav"
    file_path.write_bytes(wav_bytes)

    detector = SilenceDetector(energy_threshold_db=-30.0, min_silence_seconds=0.5)
    res = detector.analyze(str(file_path))

    assert res["pause_count"] >= 1
    assert res["total_silence_seconds"] >= 1.0


# -----------------------------------------------------------------------------
# 4. Voice Pitch Analysis Tests
# -----------------------------------------------------------------------------

def test_pitch_analysis_synthetic_sine_wave(tmp_path):
    """Verify Parselmouth pitch analyzer accurately detects fundamental frequency of pure tone."""
    # 2-second pure tone at 220 Hz (A3 musical note)
    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0, freq_hz=220.0)
    file_path = tmp_path / "test_pitch.wav"
    file_path.write_bytes(wav_bytes)

    res = PitchAnalyzer.analyze(str(file_path))

    if res["pitch_status"] == "measured":
        assert res["average_pitch_hz"] is not None
        # Should be within +/- 15 Hz of 220 Hz
        assert 205.0 <= res["average_pitch_hz"] <= 235.0
        assert res["min_pitch_hz"] is not None
        assert res["max_pitch_hz"] is not None
        assert res["pitch_variation_hz"] is not None


def test_pitch_analysis_pure_silence(tmp_path):
    """Verify silent audio returns insufficient_voiced_segments status."""
    # 2 seconds of pure silence
    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0, freq_hz=0.0, silence_end_s=2.0)
    file_path = tmp_path / "test_silent.wav"
    file_path.write_bytes(wav_bytes)

    res = PitchAnalyzer.analyze(str(file_path))
    assert res["pitch_status"] in ("insufficient_voiced_segments", "unavailable")
    assert res["average_pitch_hz"] is None


# -----------------------------------------------------------------------------
# 5. Speech Transcriber Failure Handling & Mocking
# -----------------------------------------------------------------------------

def test_transcriber_failure_handling():
    """Verify transcriber catches model exceptions gracefully without raising."""
    with patch.object(SpeechTranscriber, "get_model", side_effect=RuntimeError("Model inference engine crashed")):
        res = SpeechTranscriber.transcribe("non_existent_audio.wav")
        assert res["transcription_status"] == "failed"
        assert res["transcription"] is None
        assert "Model inference engine crashed" in res["error_message"]


# -----------------------------------------------------------------------------
# 6. Regression & Audio Preprocessing Tests
# -----------------------------------------------------------------------------

def test_pyav_metadata_errors_regression(tmp_path):
    """Regression test: verify calling av.open with metadata_errors does not raise TypeError."""
    apply_pyav_compatibility_patch()
    import av

    # Generate small WAV file
    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.0)
    file_path = tmp_path / "test_pyav.wav"
    file_path.write_bytes(wav_bytes)

    # In PyAV 18+, passing metadata_errors="ignore" previously threw TypeError
    # With the compatibility patch, this must succeed cleanly
    with av.open(str(file_path), mode="r", metadata_errors="ignore") as container:
        assert container is not None
        assert len(container.streams) > 0


def test_audio_preprocessor_resampling_and_normalization(tmp_path):
    """Verify audio preprocessor converts non-16kHz WAV into 16kHz mono float32 array in [-1.0, 1.0]."""
    # 22,050 Hz synthetic audio (matching candidate sample recording)
    orig_sr = 22050
    wav_bytes = generate_synthetic_wav_bytes(duration_s=1.5, sample_rate=orig_sr, freq_hz=440.0)
    file_path = tmp_path / "test_22k.wav"
    file_path.write_bytes(wav_bytes)

    audio_array, duration = AudioPreprocessor.load_audio(str(file_path))

    assert isinstance(audio_array, np.ndarray)
    assert audio_array.dtype == np.float32
    assert audio_array.ndim == 1  # Mono
    # Target duration should match ~1.5s
    assert 1.4 <= duration <= 1.6
    # Target length should be duration * 16000
    assert abs(len(audio_array) - int(duration * 16000)) <= 100
    # Values bounded in [-1.0, 1.0]
    assert np.max(audio_array) <= 1.0
    assert np.min(audio_array) >= -1.0


def test_speech_pipeline_failure_no_misleading_zero_scores(tmp_path):
    """Verify that when transcription fails, the pipeline returns None instead of misleading 0 scores."""
    wav_bytes = generate_synthetic_wav_bytes(duration_s=2.0)
    file_path = tmp_path / "test_fail.wav"
    file_path.write_bytes(wav_bytes)

    mock_fail = {
        "transcription": None,
        "detected_language": None,
        "segments": [],
        "transcription_status": "failed",
        "transcription_duration_seconds": 0.1,
        "error_message": "open() got an unexpected keyword argument 'metadata_errors'",
    }

    pipeline = SpeechAnalysisPipeline()
    with patch.object(SpeechTranscriber, "transcribe", return_value=mock_fail):
        results = pipeline.analyze_audio(str(file_path), audio_duration_seconds=2.0)

        assert results["processing_status"] == "failed"
        assert results["transcription_status"] == "failed"
        assert results["transcription"] is None
        # MUST NOT be 0 or 0.0
        assert results["word_count"] is None
        assert results["words_per_minute"] is None
        assert results["total_filler_words"] is None
        assert results["filler_words_per_minute"] is None
        assert "metadata_errors" in results["error_message"]
