"""Runtime settings for deployment modes."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import List


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_mode: str               # 'admin' = dev bypass; anything else = full auth
    cors_origins: List[str]
    enable_api_docs: bool
    rate_limit_per_minute: int

    # JWT
    jwt_secret_key: str         # MUST be set in production via JWT_SECRET_KEY env var
    jwt_expiry_hours: int       # access token lifetime (default 8h)
    jwt_refresh_days: int       # refresh token lifetime (default 14 days)

    # SMTP (all optional — app degrades gracefully if not set)
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str | None

    # Support contact shown on auth pages (optional)
    admin_email: str | None

    # Whether to set Secure flag on auth cookies.
    # Defaults True in public mode (production uses HTTPS via Caddy).
    # Set COOKIE_SECURE=false to test public mode over plain HTTP on a dev VM.
    cookie_secure: bool

    @property
    def is_dev(self) -> bool:
        """Local development mode — auth bypassed."""
        return self.app_mode == "admin"

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


def load_settings() -> Settings:
    app_mode = os.getenv("NOVOTREE_APP_MODE", "admin").strip().lower()

    is_dev = app_mode == "admin"
    default_origins = (
        ["http://localhost:3000", "http://localhost:5173"]
        if is_dev
        else []
    )
    default_docs = is_dev

    raw_rate_limit = os.getenv("RATE_LIMIT_PER_MINUTE", "120")
    try:
        rate_limit_per_minute = max(10, int(raw_rate_limit))
    except ValueError:
        rate_limit_per_minute = 120

    # JWT secret: required in production; auto-generated (ephemeral) in dev
    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not jwt_secret:
        if not is_dev:
            raise RuntimeError(
                "JWT_SECRET_KEY env var must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        jwt_secret = secrets.token_hex(32)  # ephemeral dev key — sessions reset on restart

    raw_jwt_expiry = os.getenv("JWT_EXPIRY_HOURS", "8")
    try:
        jwt_expiry_hours = max(1, int(raw_jwt_expiry))
    except ValueError:
        jwt_expiry_hours = 8

    raw_refresh_days = os.getenv("JWT_REFRESH_DAYS", "14")
    try:
        jwt_refresh_days = max(1, int(raw_refresh_days))
    except ValueError:
        jwt_refresh_days = 14

    raw_smtp_port = os.getenv("SMTP_PORT", "587")
    try:
        smtp_port = int(raw_smtp_port)
    except ValueError:
        smtp_port = 587

    return Settings(
        app_mode=app_mode,
        cors_origins=_parse_csv(os.getenv("CORS_ORIGINS"), default_origins),
        enable_api_docs=_as_bool(os.getenv("ENABLE_API_DOCS"), default_docs),
        rate_limit_per_minute=rate_limit_per_minute,
        jwt_secret_key=jwt_secret,
        jwt_expiry_hours=jwt_expiry_hours,
        jwt_refresh_days=jwt_refresh_days,
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=smtp_port,
        smtp_user=os.getenv("SMTP_USER") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from=os.getenv("SMTP_FROM") or None,
        admin_email=os.getenv("ADMIN_EMAIL") or None,
        cookie_secure=_as_bool(os.getenv("COOKIE_SECURE"), default=not is_dev),
    )


settings = load_settings()
