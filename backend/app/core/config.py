"""Runtime settings from environment variables. Business rules live in config/*.yaml instead."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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
    email_verification_ttl_hours: int = 48
    # After this many wrong passwords in a row, sign-in is refused for the lock period.
    login_max_failures: int = 5
    login_lock_minutes: int = 15

    # Fernet key for account numbers and documents (FR23.3). Required outside development;
    # in development a key is created in `backend/.dev-encryption-key` on first use.
    data_encryption_key: str | None = None
    # Where encrypted documents are kept until object storage is chosen (FR25.4).
    document_storage_dir: Path = REPO_ROOT / "backend" / ".documents"

    # Outgoing email (D24). "log" writes messages to the log (development); "smtp" sends
    # through any SMTP provider (Amazon SES, Postmark, SendGrid, Mailgun, Resend, Brevo).
    email_backend: Literal["log", "smtp"] = "log"
    # Empty: the SMTP account itself, shown as "<email_from_name> <SMTP_USERNAME>". Gmail
    # rewrites any From that is not the account or one of its verified aliases (D27).
    email_from: str | None = None
    email_from_name: str = "analysisACE"
    email_reply_to: str | None = None
    smtp_host: str | None = "smtp.gmail.com"
    # 587 with STARTTLS, or 465 with implicit TLS ("ssl"). "none" only for a local test server.
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_timeout_seconds: float = 15
    # Browser push (D26). Generate a pair with scripts/generate_vapid_keys.py; without one
    # push is off. The subject tells push services who to contact about this sender.
    webpush_public_key: str | None = None
    webpush_private_key: SecretStr | None = None
    webpush_subject: str = "mailto:support@analysisace.com"

    # Comma-separated addresses told when a scheduled job fails.
    ops_alert_emails: str = ""

    @property
    def ops_alert_email_list(self) -> list[str]:
        return [e.strip() for e in self.ops_alert_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
