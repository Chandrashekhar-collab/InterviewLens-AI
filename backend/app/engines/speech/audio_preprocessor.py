"""Audio preprocessor for format normalization and resampling to 16 kHz mono float32."""

import logging
import math
from typing import Optional, Tuple
import numpy as np

from app.engines.speech.compat import apply_pyav_compatibility_patch

logger = logging.getLogger("interviewlens.speech.preprocessor")

# Ensure compatibility patch is loaded before any audio operations
apply_pyav_compatibility_patch()


class AudioPreprocessor:
    """Preprocesses arbitrary audio formats (WAV, MP3, M4A, WebM) into 16 kHz mono float32 NumPy arrays."""

    TARGET_SAMPLE_RATE = 16000

    @classmethod
    def load_audio(
        cls,
        audio_path: str,
        target_sr: int = TARGET_SAMPLE_RATE,
    ) -> Tuple[np.ndarray, float]:
        """Load audio, convert to mono, resample to target_sr, and normalize to [-1.0, 1.0].

        Returns:
            Tuple of (audio_array: np.ndarray [float32], duration_seconds: float)
        """
        # Ensure PyAV compatibility patch is active
        apply_pyav_compatibility_patch()

        data: Optional[np.ndarray] = None
        sr: int = 0

        # Method 1: soundfile (fastest and cleanest for WAV, FLAC, OGG)
        try:
            import soundfile as sf
            data, sr = sf.read(audio_path, dtype="float32")
        except Exception as sf_err:
            logger.debug(f"soundfile failed to read '{audio_path}': {sf_err}, falling back to PyAV")

        # Method 2: PyAV (supports MP3, M4A, WebM, AAC, etc.)
        if data is None or sr <= 0:
            try:
                import av
                with av.open(audio_path, mode="r") as container:
                    audio_stream = next((s for s in container.streams if s.type == "audio"), None)
                    if audio_stream is None:
                        raise ValueError(f"No audio stream found in file: {audio_path}")

                    resampler = av.audio.resampler.AudioResampler(
                        format="flt",
                        layout="mono",
                        rate=target_sr,
                    )
                    chunks = []
                    for frame in container.decode(audio_stream):
                        for resampled_frame in resampler.resample(frame):
                            chunks.append(resampled_frame.to_ndarray().flatten())
                    # Flush resampler
                    for resampled_frame in resampler.resample(None):
                        chunks.append(resampled_frame.to_ndarray().flatten())

                    if chunks:
                        data = np.concatenate(chunks).astype(np.float32)
                        sr = target_sr
            except Exception as av_err:
                logger.error(f"PyAV failed to decode audio from '{audio_path}': {av_err}")
                raise ValueError(f"Could not decode audio from '{audio_path}': {av_err}") from av_err

        if data is None or len(data) == 0:
            raise ValueError(f"Audio file '{audio_path}' contains no audio samples.")

        # Ensure mono: downmix multi-channel audio
        if data.ndim > 1:
            data = np.mean(data, axis=-1)

        # Resample to target_sr if required (when read via soundfile at a non-16kHz rate)
        if sr != target_sr:
            data = cls.resample_audio(data, orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        # Normalize float range
        data = np.clip(data, -1.0, 1.0).astype(np.float32)
        duration = round(float(len(data) / target_sr), 2)

        return data, duration

    @staticmethod
    def resample_audio(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample 1D audio array from orig_sr to target_sr using polyphase filtering."""
        if orig_sr == target_sr:
            return data.astype(np.float32)

        try:
            import scipy.signal
            gcd = math.gcd(target_sr, orig_sr)
            up = target_sr // gcd
            down = orig_sr // gcd
            resampled = scipy.signal.resample_poly(data, up=up, down=down)
            return resampled.astype(np.float32)
        except Exception as exc:
            logger.warning(f"scipy.signal.resample_poly failed: {exc}, using linear interpolation fallback")
            orig_len = len(data)
            target_len = int(orig_len * target_sr / orig_sr)
            resampled = np.interp(
                np.linspace(0, orig_len, target_len, endpoint=False),
                np.arange(orig_len),
                data,
            )
            return resampled.astype(np.float32)
