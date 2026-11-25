"""Application settings and configuration management."""

import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings parsed from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General App Config
    APP_NAME: str = "InterviewLens AI Backend"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Security & JWT
    SECRET_KEY: str = "insecure-dev-secret-key-must-be-replaced-with-secure-random-bytes-min64chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./interviewlens.db"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Storage & Audio Settings
    STORAGE_DIR: str = "storage"
    RECORDINGS_DIR: str = "storage/recordings"
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB default limit
    ALLOWED_AUDIO_EXTENSIONS: List[str] = [".wav", ".mp3", ".m4a", ".webm"]

    # Speech Analysis Engine Settings
    WHISPER_MODEL_SIZE: str = "tiny"  # Lightweight for 8GB RAM development
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    SILENCE_ENERGY_THRESHOLD_DB: float = -35.0  # dB threshold for pause detection
    MIN_SILENCE_DURATION_SECONDS: float = 0.5   # 500ms min pause duration
    LONG_PAUSE_DURATION_SECONDS: float = 2.0    # 2s long pause threshold

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
