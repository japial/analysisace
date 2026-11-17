"""Runtime settings from environment variables. Business rules live in config/*.yaml instead."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://analysisace:change-me@localhost:5432/analysisace"
    cors_origins: str = "http://localhost:3000"
    # Directory holding shariah.yaml, zakat.yaml and the other versioned rule files.
    config_dir: Path = REPO_ROOT / "config"

    # Public address of the web app, used in links inside emails.
    web_base_url: str = "http://localhost:3000"
    session_ttl_days: int = 30
    password_reset_ttl_minutes: int = 60
    # After this many wrong passwords in a row, sign-in is refused for the lock period.
    login_max_failures: int = 5
    login_lock_minutes: int = 15

    # Fernet key for account numbers and documents (FR23.3). Required outside development;
    # in development a key is created in `backend/.dev-encryption-key` on first use.
    data_encryption_key: str | None = None
    # Where encrypted documents are kept until object storage is chosen (FR25.4).
    document_storage_dir: Path = REPO_ROOT / "backend" / ".documents"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
