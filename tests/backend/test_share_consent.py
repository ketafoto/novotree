"""
Regression tests for the per-share-create acknowledgement gate
(Privacy §2.5 / M-03).

Guards against three silent-regression failure modes on
`POST /users/share-tokens`:

  1. The acknowledgement gate is enforced — missing/false rejects with 400
     and writes NEITHER a token NOR a consent row.
  2. A valid create writes both rows atomically with the correct linkage
     (consent.share_token_id == token.id, consent.editor_id ==
     authenticated owner, consent.tree_owner_id == owner_id,
     consent.privacy_policy_version == config value, accepted_at /
     accepted_ip populated).
  3. The 400 path is genuinely a-rollback, not a "token saved but consent
     missing" partial commit — easy to break if someone refactors the
     transaction.
"""

from datetime import datetime, timezone
from jose import jwt as jose_jwt

from backend.api.auth import _ACCESS_TOKEN_TYPE, _ALGORITHM, hash_password
from backend.config import privacy_settings, settings
from database.system_models import AuthEditor, AuthShareConsent, AuthShareToken


# ---------------------------------------------------------------------------
# Local fixtures (kept inline; the helpers in test_contributor.py aren't
# shared via conftest and copying two short functions is cheaper than
# refactoring an unrelated test module).
# ---------------------------------------------------------------------------

_OWNER_ID = "owner1"


def _seed_owner(session_factory) -> None:
    with session_factory() as session:
        session.add(AuthEditor(
            editor_id=_OWNER_ID,
            display_name="Test Owner",
            email=f"{_OWNER_ID}@example.com",
            role="owner",
            owner_id=_OWNER_ID,
            password_hash=hash_password("ownerpass"),
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()


def _owner_token() -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    payload = {
        "sub": _OWNER_ID,
        "owner_id": _OWNER_ID,
        "role": "owner",
        "type": _ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def _post_create(client, body: dict):
    client.cookies.set("access_token", _owner_token())
    return client.post("/users/share-tokens", json=body)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestShareConsentGate:
    """The acknowledgement field gates token creation."""

    def test_missing_acknowledgement_rejected_400_and_no_rows_written(self, system_db_client):
        client, SF = system_db_client
        _seed_owner(SF)

        r = _post_create(client, {"label": "no-ack"})

        assert r.status_code == 400
        assert "acknowledgement" in r.json()["detail"].lower()
        with SF() as s:
            assert s.query(AuthShareToken).count() == 0
            assert s.query(AuthShareConsent).count() == 0

    def test_false_acknowledgement_rejected_400_and_no_rows_written(self, system_db_client):
        client, SF = system_db_client
        _seed_owner(SF)

        r = _post_create(client, {"label": "false-ack", "acknowledgement": False})

        assert r.status_code == 400
        with SF() as s:
            assert s.query(AuthShareToken).count() == 0
            assert s.query(AuthShareConsent).count() == 0


class TestShareConsentRowWrite:
    """A valid create writes the consent row with correct linkage."""

    def test_consent_row_written_with_correct_fields(self, system_db_client):
        client, SF = system_db_client
        _seed_owner(SF)

        r = _post_create(client, {"label": "happy-path", "acknowledgement": True})
        assert r.status_code == 201

        with SF() as s:
            tokens = s.query(AuthShareToken).all()
            consents = s.query(AuthShareConsent).all()
            assert len(tokens) == 1
            assert len(consents) == 1

            tok = tokens[0]
            con = consents[0]
            assert con.share_token_id == tok.id
            assert con.editor_id == _OWNER_ID
            assert con.tree_owner_id == _OWNER_ID
            assert con.privacy_policy_version == privacy_settings.privacy_policy_version
            assert con.accepted_at is not None
            assert con.accepted_ip  # populated; TestClient yields "testclient" or similar

    def test_each_create_writes_one_consent_row(self, system_db_client):
        """No accidental dedup / over-insert: 3 creates → exactly 3 consents."""
        client, SF = system_db_client
        _seed_owner(SF)

        for i in range(3):
            r = _post_create(client, {"label": f"link-{i}", "acknowledgement": True})
            assert r.status_code == 201

        with SF() as s:
            tokens = s.query(AuthShareToken).order_by(AuthShareToken.id).all()
            consents = s.query(AuthShareConsent).order_by(AuthShareConsent.id).all()
            assert len(tokens) == 3
            assert len(consents) == 3
            # Each consent points to its matching token, one-for-one.
            assert [c.share_token_id for c in consents] == [t.id for t in tokens]
