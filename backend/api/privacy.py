"""
Privacy & legal-posture endpoints.

  GET /privacy/config — public subset of PrivacySettings, used by the frontend
                        to render legal text, banners, age thresholds, and
                        retention windows without hard-coding values.

The takedown / "remove me" feature lives in its own module
([backend/api/takedown.py](takedown.py)) — separated because it owns a router
of its own, an intake email path, and the SLA sweeper. Keeping privacy.py
focused on static legal-posture endpoints (config now, /privacy/policy later)
makes the boundary easy to extend.

Tier 1 §2.1 of docs/PRIVACY_DESIGN.md. No auth required — the values exposed
here are the same ones that appear in the public privacy policy.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import privacy_settings

router = APIRouter(prefix="/privacy", tags=["Privacy"])


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
