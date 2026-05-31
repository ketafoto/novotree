"""
Regression tests for PRIVACY_DESIGN.md §3.1 — enforce signup flags.

The two self-signup endpoints must reject with HTTP 403 when the
corresponding PrivacySettings flag is False, regardless of deployment mode
(the flag, not the mode, is the gate). When the flag is True they fall
through to the existing signup flow (202 Accepted).

The flag gate sits ABOVE the SMTP-availability gate (_require_smtp_or_dev),
so these tests use the SMTP-enabled client to isolate the new behavior.
"""

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from backend.config import privacy_settings
from database.system_models import AuthEditor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PASSWORD = "Password1"  # 8+ chars, upper, lower, digit — passes strength check


def _privacy_settings_with(**overrides):
    """A frozen-dataclass copy of the real privacy_settings with flags flipped.

    PrivacySettings is frozen, so we cannot mutate it in place; replace()
    yields a variant we patch in for the duration of one test.
    """
    return replace(privacy_settings, **overrides)


def _make_owner(db, editor_id="owner1"):
    """Insert an active owner so contributor-signup's owner lookup succeeds."""
    from backend.api.auth import hash_password
    with db() as session:
        session.add(AuthEditor(
            editor_id=editor_id,
            display_name="Test Owner",
            email=f"{editor_id}@example.com",
            role="owner",
            owner_id=editor_id,
            password_hash=hash_password(_VALID_PASSWORD),
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()


# ---------------------------------------------------------------------------
# Owner signup gate
# ---------------------------------------------------------------------------

class TestOwnerSignupGate:
    def test_owner_signup_rejected_when_flag_false(self, system_db_client_smtp):
        """allow_owner_signup=False → 403, before any DB or SMTP work."""
        client, _db = system_db_client_smtp
        with patch("backend.api.auth.privacy_settings",
                   _privacy_settings_with(allow_owner_signup=False)):
            resp = client.post("/auth/owner-signup", json={
                "email": "new@example.com",
                "password": _VALID_PASSWORD,
            })
        assert resp.status_code == 403, resp.text
        assert "disabled" in resp.json()["detail"].lower()

    @patch("backend.api.auth.send_email", new_callable=AsyncMock, return_value=True)
    def test_owner_signup_allowed_when_flag_true(self, _mock_send, system_db_client_smtp):
        """allow_owner_signup=True → existing happy path (202 Accepted)."""
        client, _db = system_db_client_smtp
        with patch("backend.api.auth.privacy_settings",
                   _privacy_settings_with(allow_owner_signup=True)):
            resp = client.post("/auth/owner-signup", json={
                "email": "new@example.com",
                "password": _VALID_PASSWORD,
            })
        assert resp.status_code == 202, resp.text


# ---------------------------------------------------------------------------
# Contributor signup gate
# ---------------------------------------------------------------------------

class TestContributorSignupGate:
    def test_contributor_signup_rejected_when_flag_false(self, system_db_client_smtp):
        """allow_contributor_signup=False → 403, before owner lookup."""
        client, _db = system_db_client_smtp
        with patch("backend.api.auth.privacy_settings",
                   _privacy_settings_with(allow_contributor_signup=False)):
            resp = client.post("/auth/contributor-signup", json={
                "owner_id": "owner1",
                "email": "contrib@example.com",
                "password": _VALID_PASSWORD,
            })
        assert resp.status_code == 403, resp.text
        assert "disabled" in resp.json()["detail"].lower()

    @patch("backend.api.auth.send_email", new_callable=AsyncMock, return_value=True)
    def test_contributor_signup_allowed_when_flag_true(self, _mock_send, system_db_client_smtp):
        """allow_contributor_signup=True → existing happy path (202 Accepted)."""
        client, db = system_db_client_smtp
        _make_owner(db, editor_id="owner1")
        with patch("backend.api.auth.privacy_settings",
                   _privacy_settings_with(allow_contributor_signup=True)):
            resp = client.post("/auth/contributor-signup", json={
                "owner_id": "owner1",
                "email": "contrib@example.com",
                "password": _VALID_PASSWORD,
            })
        assert resp.status_code == 202, resp.text
