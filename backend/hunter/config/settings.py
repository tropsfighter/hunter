from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    youtube_api_key: str = Field(default="", description="YouTube Data API v3 key")
    hunter_db_path: Path = Field(
        default=_BACKEND_ROOT / "data" / "hunter.db",
        description="SQLite database file",
    )


def get_settings() -> Settings:
    return Settings()
