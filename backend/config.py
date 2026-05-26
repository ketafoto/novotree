"""Runtime settings for deployment modes."""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import List


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int, minimum: int = 0) -> int:
    if value is None:
        return default
    try:
        return max(minimum, int(value))
    except ValueError:
        return default


def _parse_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# Modes that disable auth and run as a single-user instance.
# - "admin": local development bypass (laptop running the source tree)
# - "local": packaged desktop installer (one user, one tree, offline)
# Anything else (or unset) = full multi-user auth (web/VM deployment).
_AUTH_BYPASS_MODES = frozenset({"admin", "local"})


@dataclass(frozen=True)
class Settings:
    app_mode: str               # 'admin'/'local' = single-user; anything else = full auth
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

    # Allow owner/contributor signup even without SMTP configured.
    # Defaults to True in dev mode and whenever SMTP is configured.
    # Set ALLOW_SIGNUP_WITHOUT_SMTP=true to enable signup in public mode without SMTP
    # (verification links are printed to the backend log instead of emailed).
    allow_registration: bool

    # Absolute base URL of the frontend, used to build email verification links.
    # When set, the link is `{frontend_base_url}{page_path}?token=...` with no '/novotree'
    # prefix. Useful for local dev where the frontend (port 3000) and backend (port 8000)
    # run on different origins. Leave unset in production — the link is then derived from
    # the incoming request and the '/novotree' prefix is added automatically.
    frontend_base_url: str | None

    @property
    def is_dev(self) -> bool:
        """Auth-bypass single-user mode (admin dev OR packaged local installer).
        Used everywhere we want to skip JWT/share-token resolution and treat
        the request as the default owner."""
        return self.app_mode in _AUTH_BYPASS_MODES

    @property
    def is_local(self) -> bool:
        """Packaged desktop installer specifically (frontend served from same
        origin, datasets dir overridden via env var, no rate limiting)."""
        return self.app_mode == "local"

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


def load_settings() -> Settings:
    app_mode = os.getenv("NOVOTREE_APP_MODE", "admin").strip().lower()

    is_dev = app_mode in _AUTH_BYPASS_MODES
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
        allow_registration=_as_bool(os.getenv("ALLOW_SIGNUP_WITHOUT_SMTP"), default=is_dev or bool(os.getenv("SMTP_HOST"))),
        frontend_base_url=(os.getenv("FRONTEND_BASE_URL") or "").rstrip("/") or None,
    )


settings = load_settings()


# ---------------------------------------------------------------------------
# Privacy & legal posture configuration
# ---------------------------------------------------------------------------
#
# Source of truth: docs/PRIVACY_DESIGN.md §6.
# All values overridable via environment variables. Defaults are the
# conservative choices documented in docs/PRIVACY_ANALYSIS.md §10.
#
# Acronyms (full glossary in docs/PRIVACY_DESIGN.md §1):
#   GDPR  — EU General Data Protection Regulation
#   SLA   — Service Level Agreement (promised response time)
#   ToS   — Terms of Service
#   DPO   — Data Protection Officer (GDPR Art. 37)
#   EEA   — European Economic Area
#   PII   — Personally Identifiable Information


@dataclass(frozen=True)
class PrivacySettings:
    # --- deployment mode ---
    # "A" = single owner (operator), no signups.
    # "B" = contributors-only (operator is sole Owner; relatives sign up as
    #       Contributors who edit the operator's tree).
    # "C" = public SaaS (open or admin-gated owner signup).
    deployment_mode: str

    # Whether NEW owners can self-register. Off in Mode A and Mode B;
    # on in Mode C (with or without approval gating).
    allow_owner_signup: bool

    # If allow_owner_signup is True, controls whether new owner signups
    # land in a pending state until an admin approves them. See
    # docs/PRIVACY_DESIGN.md §6.5 — gating is an abuse mitigation; it does
    # NOT downgrade the legal mode below Mode C.
    owner_signup_requires_approval: bool

    # Whether owners can invite Contributors who can edit the tree.
    # Off in Mode A; on in Mode B and Mode C.
    allow_contributor_signup: bool

    # --- SLA thresholds ---

    # SLA in days for a "remove me" (takedown) request from a data subject.
    # GDPR Art. 12(3): "without undue delay, and in any event within one month".
    takedown_sla_days: int

    # Age below which an Individual is treated as a minor (parental-consent
    # gate on photo upload and share-link exposure). GDPR Art. 8 allows
    # 13–16; we pick 16 (strictest) so we are compliant everywhere.
    child_age_threshold_years: int

    # --- retention windows ---
    # Bounds the window in which a deleted record can resurface from backup.
    # Must be >= takedown_sla_days so erasure can propagate.
    backup_retention_days: int

    # Web-server access logs (URL, status, IP) — debugging and abuse detection.
    access_log_retention_days: int

    # Application error logs / stack traces — longer because some bugs only
    # surface after a user reports them.
    error_log_retention_days: int

    # How long we keep a takedown ticket (name + email + complaint text) after
    # it has been resolved. Long enough to prove we responded if a regulator
    # asks; short enough that we are not hoarding PII.
    takedown_request_retention_months: int

    # --- legal-document versioning ---
    # When any of these strings change, users are re-prompted to accept on
    # next login. We do not silently update legal documents.
    tos_version: str
    privacy_policy_version: str
    cookie_notice_version: str

    # --- controller identity (privacy policy §1, §7) ---

    # GDPR Art. 4(7) "data controller" — the legal entity deciding why and
    # how personal data is processed. Appears in the privacy policy and in
    # takedown responses. Not to be confused with the internal "admin" role.
    controller_name: str

    # Where data subjects email privacy questions and takedown follow-ups.
    # Must be a monitored mailbox.
    privacy_contact_email: str

    # DPO (GDPR Art. 37). Mandatory only at large scale — NovoTree does not
    # qualify. Field exists so we can fill it without code changes if a
    # lawyer says otherwise.
    dpo_email: str | None

    # Production VM region. Determines which GDPR Chapter V rules apply to
    # international data transfers ("EEA" → no extra rules).
    hosting_region: str

    # --- analytics & cookies ---
    # False  → strictly-necessary auth cookies only; banner is a NOTICE.
    # True   → third-party analytics with non-essential cookies → banner
    #          becomes a real CONSENT dialog (Accept/Reject) and the
    #          analytics script must not load until Accept is clicked.
    analytics_enabled: bool

    # --- TEST-ONLY: do NOT enable in production ---
    # When True, Owners can edit `created_at` / `resolved_at` on their own
    # takedown rows from the queue UI. This exists so the SLA reminder /
    # escalation / retention sweep paths can be exercised on a test VM
    # without waiting 30 days for each transition. In production this is
    # a data-integrity risk (an Owner could defeat the SLA by resetting
    # `created_at`), so the default is False and the flag is logged loudly
    # at startup when it flips on. Symbols implementing this path are
    # `test_`-prefixed throughout the codebase so they grep cleanly during
    # review.
    test_allow_timestamp_override: bool


def load_privacy_settings() -> PrivacySettings:
    mode = os.getenv("NOVOTREE_DEPLOYMENT_MODE", "A").strip().upper() or "A"
    if mode not in {"A", "B", "C"}:
        mode = "A"

    # Defaults derived from mode so that the dataclass is internally
    # consistent without requiring every env var to be set.
    default_allow_owner = mode == "C"
    default_allow_contributor = mode in {"B", "C"}

    return PrivacySettings(
        deployment_mode=mode,
        allow_owner_signup=_as_bool(os.getenv("ALLOW_OWNER_SIGNUP"), default=default_allow_owner),
        owner_signup_requires_approval=_as_bool(
            os.getenv("OWNER_SIGNUP_REQUIRES_APPROVAL"), default=True
        ),
        allow_contributor_signup=_as_bool(
            os.getenv("ALLOW_CONTRIBUTOR_SIGNUP"), default=default_allow_contributor
        ),
        takedown_sla_days=_as_int(os.getenv("TAKEDOWN_SLA_DAYS"), 30, minimum=1),
        child_age_threshold_years=_as_int(os.getenv("CHILD_AGE_THRESHOLD_YEARS"), 16, minimum=13),
        backup_retention_days=_as_int(os.getenv("BACKUP_RETENTION_DAYS"), 30, minimum=1),
        access_log_retention_days=_as_int(os.getenv("ACCESS_LOG_RETENTION_DAYS"), 14, minimum=1),
        error_log_retention_days=_as_int(os.getenv("ERROR_LOG_RETENTION_DAYS"), 30, minimum=1),
        takedown_request_retention_months=_as_int(
            os.getenv("TAKEDOWN_REQUEST_RETENTION_MONTHS"), 12, minimum=1
        ),
        tos_version=os.getenv("TOS_VERSION", "1.0"),
        privacy_policy_version=os.getenv("PRIVACY_POLICY_VERSION", "1.0"),
        cookie_notice_version=os.getenv("COOKIE_NOTICE_VERSION", "1.0"),
        controller_name=os.getenv(
            "CONTROLLER_NAME", "NovoTree (operator: Igor Novoseltsev)"
        ),
        privacy_contact_email=os.getenv("PRIVACY_CONTACT_EMAIL", "aktiniya@gmail.com"),
        dpo_email=os.getenv("DPO_EMAIL") or None,
        hosting_region=os.getenv("HOSTING_REGION", "EEA"),
        analytics_enabled=_as_bool(os.getenv("ANALYTICS_ENABLED"), default=False),
        test_allow_timestamp_override=_as_bool(
            os.getenv("PRIVACY_ALLOW_TIMESTAMP_OVERRIDE"), default=False
        ),
    )


privacy_settings = load_privacy_settings()

if privacy_settings.test_allow_timestamp_override:
    logging.getLogger("novotree.backend").warning(
        "PRIVACY_ALLOW_TIMESTAMP_OVERRIDE is ON — Owners can edit takedown "
        "timestamps from the UI. This is a TEST-ONLY flag and must NOT be "
        "set in production."
    )
