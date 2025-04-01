# config/settings.py
from typing import Final

class Settings:
    """Clss for storing application settings."""
    TABLE_FORMAT: Final[str] = "pretty"
    MIN_SEGMENT_DURATION: Final[float] = 5.0
    MAX_WORKERS: Final[int] = 4

settings = Settings()