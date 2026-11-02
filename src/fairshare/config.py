"""Runtime configuration, read from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///fairshare.db"
    secret_key: str = "dev-only-insecure-secret-change-me"  # noqa: S105
    session_cookie: str = "fairshare_session"

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            database_url=os.getenv("FAIRSHARE_DATABASE_URL", Settings.database_url),
            secret_key=os.getenv("FAIRSHARE_SECRET_KEY", Settings.secret_key),
            session_cookie=os.getenv("FAIRSHARE_SESSION_COOKIE", Settings.session_cookie),
        )
