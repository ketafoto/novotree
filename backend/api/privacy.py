"""
Privacy & legal-posture endpoints.

  GET /privacy/config — public subset of PrivacySettings, used by the frontend
                        to render legal text, banners, age thresholds, and
                        retention windows without hard-coding values.
  GET /privacy/policy — rendered privacy policy markdown + version string
                        (Tier 1 §2.3). Sourced from docs/legal/privacy.md.

The takedown / "remove me" feature lives in its own module
([backend/api/takedown.py](takedown.py)) — separated because it owns a router
of its own, an intake email path, and the SLA sweeper. Keeping privacy.py
focused on static legal-posture endpoints makes the boundary easy to extend.

Tier 1 §2.1 + §2.3 of docs/PRIVACY_DESIGN.md. No auth required — the values
exposed here are the same ones that appear in the public privacy policy.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import privacy_settings

router = APIRouter(prefix="/privacy", tags=["Privacy"])

# Privacy policy markdown is shipped in-repo at docs/legal/privacy.md.
# Resolved relative to this module so it works both in dev (running from a
# checkout) and when packaged. Read once at first request and cached for the
# process lifetime — matches the immutability posture of PrivacySettings
# itself, where edits require a service restart.
_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "legal" / "privacy.md"
_policy_cache: str | None = None


class PrivacyConfigResponse(BaseModel):
    deployment_mode: str
    allow_owner_signup: bool
    owner_signup_requires_approval: bool
    allow_contributor_signup: bool

    takedown_sla_days: int
    child_age_threshold_years: int

    backup_retention_days: int
    access_log_retention_days: int
    error_log_retention_days: int
    takedown_request_retention_months: int

    tos_version: str
    privacy_policy_version: str
    cookie_notice_version: str

    controller_name: str
    privacy_contact_email: str
    hosting_region: str

    analytics_enabled: bool


@router.get("/config", response_model=PrivacyConfigResponse)
def get_privacy_config() -> PrivacyConfigResponse:
    p = privacy_settings
    return PrivacyConfigResponse(
        deployment_mode=p.deployment_mode,
        allow_owner_signup=p.allow_owner_signup,
        owner_signup_requires_approval=p.owner_signup_requires_approval,
        allow_contributor_signup=p.allow_contributor_signup,
        takedown_sla_days=p.takedown_sla_days,
        child_age_threshold_years=p.child_age_threshold_years,
        backup_retention_days=p.backup_retention_days,
        access_log_retention_days=p.access_log_retention_days,
        error_log_retention_days=p.error_log_retention_days,
        takedown_request_retention_months=p.takedown_request_retention_months,
        tos_version=p.tos_version,
        privacy_policy_version=p.privacy_policy_version,
        cookie_notice_version=p.cookie_notice_version,
        controller_name=p.controller_name,
        privacy_contact_email=p.privacy_contact_email,
        hosting_region=p.hosting_region,
        analytics_enabled=p.analytics_enabled,
    )


class PrivacyPolicyResponse(BaseModel):
    version: str
    content_markdown: str


@router.get("/policy", response_model=PrivacyPolicyResponse)
def get_privacy_policy() -> PrivacyPolicyResponse:
    global _policy_cache
    if _policy_cache is None:
        try:
            _policy_cache = _POLICY_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Privacy policy is temporarily unavailable.",
            ) from exc
    return PrivacyPolicyResponse(
        version=privacy_settings.privacy_policy_version,
        content_markdown=_policy_cache,
    )
