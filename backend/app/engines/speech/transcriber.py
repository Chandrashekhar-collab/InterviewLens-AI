"""Speech-to-text transcription engine using faster-whisper with lazy singleton loading."""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Union
import numpy as np

from app.config import settings
from app.engines.speech.audio_preprocessor import AudioPreprocessor
from app.engines.speech.compat import apply_pyav_compatibility_patch

logger = logging.getLogger("interviewlens.speech.transcriber")

# Ensure PyAV breaking change compatibility patch is active
apply_pyav_compatibility_patch()


class SpeechTranscriber:
    """Thread-safe lazy singleton for faster-whisper transcription."""

    _model: Optional[Any] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_model(cls) -> Any:
        """Lazily load the faster-whisper model only on first demand."""
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    # Re-verify compatibility patch
                    apply_pyav_compatibility_patch()
                    from faster_whisper import WhisperModel

                    logger.info(
                        f"Loading faster-whisper model '{settings.WHISPER_MODEL_SIZE}' "
                        f"on device='{settings.WHISPER_DEVICE}', compute_type='{settings.WHISPER_COMPUTE_TYPE}'..."
                    )
                    cls._model = WhisperModel(
                        model_size_or_path=settings.WHISPER_MODEL_SIZE,
                        device=settings.WHISPER_DEVICE,
                        compute_type=settings.WHISPER_COMPUTE_TYPE,
                    )
                    logger.info("faster-whisper model loaded successfully.")
        return cls._model

    @classmethod
    def transcribe(cls, audio_input: Union[str, np.ndarray]) -> Dict[str, Any]:
        """Transcribe an audio file path or preprocessed NumPy array into text with timing segments.

        Returns dictionary containing:
        - transcription: Optional[str]
        - detected_language: Optional[str]
        - segments: List[Dict[str, Any]]
        - transcription_status: str ("completed" or "failed")
        - transcription_duration_seconds: float
        - error_message: Optional[str]
        """
        start_time = time.perf_counter()
        # Guarantee PyAV patch is active
        apply_pyav_compatibility_patch()

        try:
            model = cls.get_model()

            # Preprocess audio into 16 kHz mono float32 array if file path is passed
            audio_data: Any = audio_input
            if isinstance(audio_input, str):
                try:
                    audio_data, _ = AudioPreprocessor.load_audio(audio_input)
                except Exception as prep_err:
                    logger.warning(
                        f"AudioPreprocessor failed for '{audio_input}': {prep_err}. "
                        "Falling back to direct model audio decoder."
                    )
                    audio_data = audio_input

            segments_gen, info = model.transcribe(
                audio_data,
                beam_size=1,  # fast greedy beam for low-resource CPU
                vad_filter=True,  # filter out pure silence to save cycles
            )

            segments_list: List[Dict[str, Any]] = []
            full_text_chunks: List[str] = []

            for seg in segments_gen:
                text = seg.text.strip()
                if text:
                    full_text_chunks.append(text)
                    segments_list.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": text,
                    })

            elapsed = round(time.perf_counter() - start_time, 2)
            transcribed_text = " ".join(full_text_chunks).strip()

            return {
                "transcription": transcribed_text,
                "detected_language": info.language if hasattr(info, "language") else "en",
                "segments": segments_list,
                "transcription_status": "completed",
                "transcription_duration_seconds": elapsed,
                "error_message": None,
            }

        except Exception as exc:
            elapsed = round(time.perf_counter() - start_time, 2)
            logger.error(f"Speech transcription failed for audio: {exc}", exc_info=True)
            return {
                "transcription": None,
                "detected_language": None,
                "segments": [],
                "transcription_status": "failed",
                "transcription_duration_seconds": elapsed,
                "error_message": str(exc),
            }
