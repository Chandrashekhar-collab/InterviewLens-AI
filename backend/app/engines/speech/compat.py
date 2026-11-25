"""Compatibility layer for third-party audio dependencies."""

import logging

logger = logging.getLogger("interviewlens.speech.compat")


def apply_pyav_compatibility_patch() -> None:
    """Fix PyAV 18+ breaking change removing metadata_errors from av.open.

    faster-whisper <= 1.2.1 hardcodes metadata_errors="ignore" in decode_audio().
    In PyAV 18.0.0 and 19.0.0+, metadata_errors was removed, causing:
    TypeError: open() got an unexpected keyword argument 'metadata_errors'.

    This patch wraps av.open to gracefully strip metadata_errors if unsupported.
    """
    try:
        import av

        if getattr(av, "_metadata_errors_patched", False):
            return

        original_open = av.open

        def safe_av_open(*args, **kwargs):
            kwargs.pop("metadata_errors", None)
            return original_open(*args, **kwargs)

        av.open = safe_av_open
        av._metadata_errors_patched = True
        logger.debug("Applied PyAV metadata_errors compatibility patch.")
    except ImportError:
        pass


# Apply patch immediately upon module import
apply_pyav_compatibility_patch()
