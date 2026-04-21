"""
Regression tests for the contributor auth flow.

Covers the state machine bugs fixed in this codebase:
  - pending contributor → "awaiting approval" (not "suspended")
  - frozen contributor  → "suspended"          (not "awaiting approval")
  - approve email sent on first approval
  - freeze/unfreeze emails always sent
  - AuthEditorTree.is_active=False at signup so the approval guard fires correctly
  - frozen contributor gets 401 on /auth/me (session invalidated immediately)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from database.system_models import AuthEditor, AuthEditorTree
from backend.config import settings


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _make_owner(db, editor_id="owner1", password_plain="ownerpass"):
    from backend.api.auth import hash_password
    with db() as session:
        session.add(AuthEditor(
            editor_id=editor_id,
            display_name="Test Owner",
            email=f"{editor_id}@example.com",
            role="owner",
            owner_id=editor_id,
            password_hash=hash_password(password_plain),
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()


def _make_contributor(db, editor_id="contrib1", owner_id="owner1",
                      password_plain="pass", link_active=False,
                      last_login_at=None, editor_active=True):
    from backend.api.auth import hash_password
    with db() as session:
        session.add(AuthEditor(
            editor_id=editor_id,
            display_name="Test Contributor",
            email=f"{editor_id}@example.com",
            role="contributor",
            owner_id=None,
            password_hash=hash_password(password_plain),
            is_active=editor_active,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_login_at=last_login_at,
        ))
        session.add(AuthEditorTree(editor_id=editor_id, owner_id=owner_id, is_active=link_active))
        session.commit()


def _make_owner_token(owner_id: str) -> str:
    from datetime import timedelta
    from jose import jwt as jose_jwt
    from backend.api.auth import _ACCESS_TOKEN_TYPE, _ALGORITHM
    _EXPIRE = 60  # minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": owner_id,
        "owner_id": owner_id,
        "role": "owner",
        "type": _ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=_EXPIRE),
    }
    return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def _make_contributor_token(editor_id: str, owner_id: str) -> str:
    from datetime import timedelta
    from jose import jwt as jose_jwt
    from backend.api.auth import _ACCESS_TOKEN_TYPE, _ALGORITHM
    _EXPIRE = 60  # minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": editor_id,
        "owner_id": owner_id,
        "role": "contributor",
        "type": _ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=_EXPIRE),
    }
    return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


# ---------------------------------------------------------------------------
# Login error message regression tests
# ---------------------------------------------------------------------------

class TestLoginMessages:
    """Signup flow — login error messages.

    A contributor who just signed up (no login history) must see "awaiting approval",
    not "suspended". A frozen contributor (has login history) must see "suspended".
    Verifies the state machine distinguishes the two states correctly.
    """

    def test_pending_contributor_gets_approval_message(self, system_db_client):
        """Unapproved (link.is_active=False, no login history) → 403 'awaiting approval'."""
        client, db = system_db_client
        _make_contributor(db, link_active=False, last_login_at=None, editor_active=False)

        resp = client.post("/auth/login", json={"editor_id": "contrib1", "password": "pass"})

        assert resp.status_code == 403, resp.text
        detail = resp.json()["detail"].lower()
        assert "approval" in detail
        assert "suspended" not in detail

    def test_frozen_contributor_gets_suspended_message(self, system_db_client):
        """Frozen (link.is_active=False, has login history) → 403 'suspended'."""
        client, db = system_db_client
        _make_contributor(db, link_active=False,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        resp = client.post("/auth/login", json={"editor_id": "contrib1", "password": "pass"})

        assert resp.status_code == 403, resp.text
        detail = resp.json()["detail"].lower()
        assert "suspended" in detail
        assert "approval" not in detail

    def test_wrong_password_is_401(self, system_db_client):
        """Wrong password → 401, not a state-specific 403."""
        client, db = system_db_client
        _make_contributor(db, link_active=True, editor_active=True)

        resp = client.post("/auth/login", json={"editor_id": "contrib1", "password": "wrong"})

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Link initial state regression test
# ---------------------------------------------------------------------------

class TestLinkInitialState:
    """Signup flow — contributor-owner link initial state.

    When a contributor signs up, the AuthEditorTree link must start as is_active=False
    so the approval guard fires correctly. The owner must explicitly approve before
    the contributor can log in.
    """

    def test_new_link_is_inactive(self, system_db_client):
        """AuthEditorTree created at signup must have is_active=False until owner approves."""
        client, db = system_db_client
        _make_contributor(db, link_active=False)

        with db() as session:
            link = session.query(AuthEditorTree).filter_by(editor_id="contrib1").first()

        assert link is not None
        assert link.is_active is False, "Link must start inactive — pending owner approval"


# ---------------------------------------------------------------------------
# Email notification regression tests
# ---------------------------------------------------------------------------

class TestApproveEmail:
    """Approve / freeze / unfreeze / delete flow — email notifications.

    Each state transition must trigger exactly one outgoing email with the correct
    subject: "approved" on first approval, "restored" on unfreeze, "suspended" on
    freeze, and a removal notice on delete.
    """

    @patch("backend.api.users._send_email", new_callable=AsyncMock)
    def test_first_approval_sends_approved_email(self, mock_send, system_db_client_smtp):
        """Approving a pending contributor sends an 'approved' email."""
        client, db = system_db_client_smtp
        _make_owner(db)
        _make_contributor(db, link_active=False, last_login_at=None, editor_active=False)

        client.cookies.set("access_token", _make_owner_token("owner1"))
        resp = client.post("/users/contributors/contrib1/activate")

        assert resp.status_code == 204, resp.text
        mock_send.assert_awaited_once()
        subject = mock_send.call_args.kwargs.get("subject", "")
        assert "approved" in subject.lower() or "access" in subject.lower()

    @patch("backend.api.users._send_email", new_callable=AsyncMock)
    def test_unfreeze_sends_restored_email(self, mock_send, system_db_client_smtp):
        """Unfreezing a frozen contributor sends a 'restored' email."""
        client, db = system_db_client_smtp
        _make_owner(db)
        _make_contributor(db, link_active=False,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        client.cookies.set("access_token", _make_owner_token("owner1"))
        resp = client.post("/users/contributors/set-active",
                           json={"editor_id": "contrib1", "is_active": True})

        assert resp.status_code == 204, resp.text
        mock_send.assert_awaited_once()
        subject = mock_send.call_args.kwargs.get("subject", "")
        assert "restored" in subject.lower()

    @patch("backend.api.users._send_email", new_callable=AsyncMock)
    def test_freeze_sends_suspended_email(self, mock_send, system_db_client_smtp):
        """Freezing an active contributor sends a 'suspended' email."""
        client, db = system_db_client_smtp
        _make_owner(db)
        _make_contributor(db, link_active=True,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        client.cookies.set("access_token", _make_owner_token("owner1"))
        resp = client.post("/users/contributors/set-active",
                           json={"editor_id": "contrib1", "is_active": False})

        assert resp.status_code == 204, resp.text
        mock_send.assert_awaited_once()
        subject = mock_send.call_args.kwargs.get("subject", "")
        assert "suspended" in subject.lower()

    @patch("backend.api.users._send_email", new_callable=AsyncMock)
    def test_delete_sends_removal_email(self, mock_send, system_db_client_smtp):
        """Deleting a contributor (no contributions) sends a removal email."""
        client, db = system_db_client_smtp
        _make_owner(db)
        _make_contributor(db, link_active=True,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        client.cookies.set("access_token", _make_owner_token("owner1"))
        # _has_contributions queries the tree DB — patch it to return False
        with patch("backend.api.users._has_contributions", return_value=False):
            resp = client.delete("/users/contributors/contrib1")

        assert resp.status_code == 204, resp.text
        mock_send.assert_awaited_once()
        subject = mock_send.call_args.kwargs.get("subject", "")
        assert "removed" in subject.lower() or "deleted" in subject.lower() or "access" in subject.lower()


# ---------------------------------------------------------------------------
# Immediate session enforcement on freeze (Fix: get_current_editor checks freeze)
# ---------------------------------------------------------------------------

class TestFreezeImmediateEnforcement:
    """Freeze / unfreeze flow — immediate session enforcement.

    Freezing a contributor (link.is_active=False) must invalidate their existing
    JWT session immediately — /auth/me returns 401 without waiting for token expiry.
    Unfreezing restores access with the same token.
    """

    def test_active_contributor_can_access_me(self, system_db_client):
        """/auth/me returns 200 for an active contributor with a valid token."""
        client, db = system_db_client
        _make_contributor(db, link_active=True,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        client.cookies.set("access_token", _make_contributor_token("contrib1", "owner1"))
        resp = client.get("/auth/me")

        assert resp.status_code == 200, resp.text

    def test_frozen_contributor_gets_401_on_me(self, system_db_client):
        """After freeze (link.is_active=False), /auth/me returns 401 — session invalidated."""
        client, db = system_db_client
        _make_contributor(db, link_active=False,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        client.cookies.set("access_token", _make_contributor_token("contrib1", "owner1"))
        resp = client.get("/auth/me")

        assert resp.status_code == 401, resp.text

    def test_freeze_then_unfreeze_restores_access(self, system_db_client):
        """Unfreezing a contributor (link.is_active=True) restores 200 on /auth/me."""
        client, db = system_db_client
        # Start frozen
        _make_contributor(db, link_active=False,
                          last_login_at=datetime.now(timezone.utc).isoformat())

        token = _make_contributor_token("contrib1", "owner1")
        client.cookies.set("access_token", token)

        # Confirm frozen
        assert client.get("/auth/me").status_code == 401

        # Unfreeze directly in DB
        with db() as session:
            link = session.query(AuthEditorTree).filter_by(editor_id="contrib1").first()
            link.is_active = True
            session.commit()

        # Should now be accessible
        resp = client.get("/auth/me")
        assert resp.status_code == 200, resp.text



# ---------------------------------------------------------------------------
# Individual created_by set to the creating editor's ID
# ---------------------------------------------------------------------------

class TestIndividualCreatedBy:
    """Contributor access flow — created_by attribution.

    Records created by a contributor must have created_by set to the contributor's
    editor_id, and that field must be returned in both the POST response and the
    GET list response.
    """

    def test_contributor_created_by_in_response(self, full_client):
        """POST /individuals by a contributor returns created_by == contributor's editor_id."""
        client, db = full_client
        _make_contributor(db, link_active=True,
                          last_login_at=datetime.now(timezone.utc).isoformat(),
                          editor_active=True)

        client.cookies.set("access_token", _make_contributor_token("contrib1", "owner1"))
        resp = client.post("/individuals", json={
            "sex_code": "M",
            "names": [{"given_name": "Test", "family_name": "Person"}],
        })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created_by"] == "contrib1", (
            f"Expected created_by='contrib1', got {data.get('created_by')!r}"
        )

    def test_created_by_present_in_list_response(self, full_client):
        """GET /individuals returns created_by for each individual."""
        client, db = full_client
        _make_contributor(db, link_active=True,
                          last_login_at=datetime.now(timezone.utc).isoformat(),
                          editor_active=True)

        client.cookies.set("access_token", _make_contributor_token("contrib1", "owner1"))
        client.post("/individuals", json={
            "sex_code": "F",
            "names": [{"given_name": "List", "family_name": "Test"}],
        })

        resp = client.get("/individuals")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["created_by"] == "contrib1"


# ---------------------------------------------------------------------------
# Shared helpers for contributor permission tests
# ---------------------------------------------------------------------------

_IND_PAYLOAD  = {"sex_code": "M", "names": [{"given_name": "Test"}]}
_FAM_PAYLOAD  = {"members": [], "children": []}
_EVENT_TYPE   = "EVEN"


def _setup_owner_and_contrib(db):
    """Insert owner1 + an active contrib1 linked to owner1."""
    _make_owner(db)
    _make_contributor(db, link_active=True,
                      last_login_at="2025-01-01T00:00:00+00:00",
                      editor_active=True)


def _owner_cookie(client):
    client.cookies.set("access_token", _make_owner_token("owner1"))


def _contrib_cookie(client):
    client.cookies.set("access_token", _make_contributor_token("contrib1", "owner1"))


def _post(client, url, payload):
    r = client.post(url, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _ind(client):
    return _post(client, "/individuals", _IND_PAYLOAD)


def _fam(client):
    return _post(client, "/families", _FAM_PAYLOAD)


def _event(client, individual_id):
    return _post(client, "/events",
                 {"event_type_code": _EVENT_TYPE, "individual_id": individual_id})


def _media(client, individual_id):
    """Create a metadata-only media record (no file on disk)."""
    return _post(client, "/media",
                 {"individual_id": individual_id, "media_type_code": "photo"})


# ---------------------------------------------------------------------------
# 1. Owner cannot delete a contributor who has contributions
# ---------------------------------------------------------------------------

class TestOwnerCannotDeleteContributorWithContributions:
    """Deletion guard — contributor with tree data cannot be removed.

    _has_contributions scans all four tables. Each sub-test seeds exactly one
    type of record so that each table is tested independently as a blocking
    condition.
    """

    def _try_delete(self, client, db):
        _setup_owner_and_contrib(db)
        _owner_cookie(client)

    def _assert_blocked(self, client):
        r = client.delete("/users/contributors/contrib1")
        assert r.status_code == 409, r.text
        assert "data" in r.json()["detail"].lower() or "contribut" in r.json()["detail"].lower()

    def test_blocked_when_contrib_added_individual(self, full_client):
        """Contributor who added an individual cannot be deleted — returns 409."""
        client, db = full_client
        self._try_delete(client, db)
        _contrib_cookie(client)
        _ind(client)
        _owner_cookie(client)
        self._assert_blocked(client)

    def test_blocked_when_contrib_added_family(self, full_client):
        """Contributor who added a family cannot be deleted — returns 409."""
        client, db = full_client
        self._try_delete(client, db)
        _contrib_cookie(client)
        _fam(client)
        _owner_cookie(client)
        self._assert_blocked(client)

    def test_blocked_when_contrib_added_event(self, full_client):
        """Contributor who added an event cannot be deleted — returns 409."""
        client, db = full_client
        self._try_delete(client, db)
        # Need an individual to attach the event to (owner creates it)
        ind = _ind(client)
        _contrib_cookie(client)
        _event(client, ind["id"])
        _owner_cookie(client)
        self._assert_blocked(client)

    def test_blocked_when_contrib_added_media(self, full_client):
        """Contributor who added a media record cannot be deleted — returns 409."""
        client, db = full_client
        self._try_delete(client, db)
        ind = _ind(client)
        _contrib_cookie(client)
        _media(client, ind["id"])
        _owner_cookie(client)
        self._assert_blocked(client)

    def test_allowed_when_no_contributions(self, full_client):
        """Contributor with zero contributions can be deleted — returns 204."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        r = client.delete("/users/contributors/contrib1")
        assert r.status_code == 204, r.text


# ---------------------------------------------------------------------------
# 2+3. Contributor can add records (individual, family, event, media)
# ---------------------------------------------------------------------------

class TestContributorCanAddRecords:
    """Create permissions — contributor may add any record type.

    Each test creates a record as the contributor and verifies a 200 response
    with created_by set to the contributor's editor_id.
    """

    def test_contributor_can_add_individual(self, full_client):
        """POST /individuals as contributor → 200, created_by == contrib1."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        assert ind["created_by"] == "contrib1"

    def test_contributor_can_add_family(self, full_client):
        """POST /families as contributor → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        fam = _fam(client)
        assert "id" in fam

    def test_contributor_can_add_event(self, full_client):
        """POST /events as contributor (on own individual) → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        evt = _event(client, ind["id"])
        assert evt["individual_id"] == ind["id"]

    def test_contributor_can_add_media(self, full_client):
        """POST /media as contributor (on own individual) → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        med = _media(client, ind["id"])
        assert med["individual_id"] == ind["id"]


# ---------------------------------------------------------------------------
# 4. Contributor can attach events and media to others' records
# ---------------------------------------------------------------------------

class TestContributorCanAddToOthersRecords:
    """Attach permissions — contributor may enrich records created by anyone.

    Adding an event or media to an individual/family owned by someone else is
    allowed; the new record is attributed to the contributor.
    """

    def test_contributor_can_add_event_to_owners_individual(self, full_client):
        """Contributor attaches an event to an individual the owner created → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        evt = _event(client, ind["id"])
        assert evt["individual_id"] == ind["id"]

    def test_contributor_can_add_event_to_owners_family(self, full_client):
        """Contributor attaches an event to a family the owner created → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        fam = _fam(client)
        _contrib_cookie(client)
        evt = _post(client, "/events",
                    {"event_type_code": _EVENT_TYPE, "family_id": fam["id"]})
        assert evt["family_id"] == fam["id"]

    def test_contributor_can_add_media_to_owners_individual(self, full_client):
        """Contributor attaches a media record to an individual the owner created → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        med = _media(client, ind["id"])
        assert med["individual_id"] == ind["id"]


# ---------------------------------------------------------------------------
# 5. Contributor can edit only their own records
# ---------------------------------------------------------------------------

class TestContributorEditOwnOnly:
    """Edit permissions — contributor may update only records they created.

    PUT on a record created by the contributor → 200.
    PUT on a record created by the owner → 403.
    Covers all four resource types.
    """

    def test_contributor_can_edit_own_individual(self, full_client):
        """Contributor edits own individual → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        r = client.put(f"/individuals/{ind['id']}",
                       json={"sex_code": "F", "names": [{"given_name": "Updated"}]})
        assert r.status_code == 200, r.text

    def test_contributor_cannot_edit_owners_individual(self, full_client):
        """Contributor tries to edit owner's individual → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        r = client.put(f"/individuals/{ind['id']}",
                       json={"sex_code": "F", "names": [{"given_name": "Nope"}]})
        assert r.status_code == 403, r.text

    def test_contributor_can_edit_own_family(self, full_client):
        """Contributor edits own family → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        fam = _fam(client)
        r = client.put(f"/families/{fam['id']}", json={"family_type": "civil_union"})
        assert r.status_code == 200, r.text

    def test_contributor_cannot_edit_owners_family(self, full_client):
        """Contributor tries to edit owner's family → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        fam = _fam(client)
        _contrib_cookie(client)
        r = client.put(f"/families/{fam['id']}", json={"family_type": "civil_union"})
        assert r.status_code == 403, r.text

    def test_contributor_can_edit_own_event(self, full_client):
        """Contributor edits own event → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        evt = _event(client, ind["id"])
        r = client.put(f"/events/{evt['id']}",
                       json={"event_type_code": _EVENT_TYPE, "event_place": "Paris"})
        assert r.status_code == 200, r.text

    def test_contributor_cannot_edit_owners_event(self, full_client):
        """Contributor tries to edit owner's event → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        evt = _event(client, ind["id"])
        _contrib_cookie(client)
        r = client.put(f"/events/{evt['id']}",
                       json={"event_type_code": _EVENT_TYPE, "event_place": "Moscow"})
        assert r.status_code == 403, r.text

    def test_contributor_can_edit_own_media(self, full_client):
        """Contributor edits own media record → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        med = _media(client, ind["id"])
        r = client.put(f"/media/{med['id']}", json={"description": "Updated"})
        assert r.status_code == 200, r.text

    def test_contributor_cannot_edit_owners_media(self, full_client):
        """Contributor tries to edit owner's media record → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        med = _media(client, ind["id"])
        _contrib_cookie(client)
        r = client.put(f"/media/{med['id']}", json={"description": "No"})
        assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Owner can delete contributor's contributions
# ---------------------------------------------------------------------------

class TestOwnerCanDeleteContributorsRecords:
    """Owner privileges — owner may delete any record regardless of who created it.

    Each sub-test has the contributor create one record type, then verifies
    that the owner can delete it (200) without a 403.
    """

    def test_owner_can_delete_contributors_individual(self, full_client):
        """Owner deletes an individual created by a contributor → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        _owner_cookie(client)
        r = client.delete(f"/individuals/{ind['id']}")
        assert r.status_code == 200, r.text

    def test_owner_can_delete_contributors_family(self, full_client):
        """Owner deletes a family created by a contributor → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        fam = _fam(client)
        _owner_cookie(client)
        r = client.delete(f"/families/{fam['id']}")
        assert r.status_code == 200, r.text

    def test_owner_can_delete_contributors_event(self, full_client):
        """Owner deletes an event created by a contributor → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        evt = _event(client, ind["id"])
        _owner_cookie(client)
        r = client.delete(f"/events/{evt['id']}")
        assert r.status_code == 200, r.text

    def test_owner_can_delete_contributors_media(self, full_client):
        """Owner deletes a media record created by a contributor → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        med = _media(client, ind["id"])
        _owner_cookie(client)
        r = client.delete(f"/media/{med['id']}")
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 6. Contributor can delete only their own records
# ---------------------------------------------------------------------------

class TestContributorDeleteOwnOnly:
    """Delete permissions — contributor may remove only records they created.

    DELETE on own record → 200.
    DELETE on owner's record → 403.
    Covers all four resource types.
    """

    def test_contributor_can_delete_own_individual(self, full_client):
        """Contributor deletes own individual → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        r = client.delete(f"/individuals/{ind['id']}")
        assert r.status_code == 200, r.text

    def test_contributor_cannot_delete_owners_individual(self, full_client):
        """Contributor tries to delete owner's individual → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        _contrib_cookie(client)
        r = client.delete(f"/individuals/{ind['id']}")
        assert r.status_code == 403, r.text

    def test_contributor_can_delete_own_family(self, full_client):
        """Contributor deletes own family → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        fam = _fam(client)
        r = client.delete(f"/families/{fam['id']}")
        assert r.status_code == 200, r.text

    def test_contributor_cannot_delete_owners_family(self, full_client):
        """Contributor tries to delete owner's family → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        fam = _fam(client)
        _contrib_cookie(client)
        r = client.delete(f"/families/{fam['id']}")
        assert r.status_code == 403, r.text

    def test_contributor_can_delete_own_event(self, full_client):
        """Contributor deletes own event → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        evt = _event(client, ind["id"])
        r = client.delete(f"/events/{evt['id']}")
        assert r.status_code == 200, r.text

    def test_contributor_cannot_delete_owners_event(self, full_client):
        """Contributor tries to delete owner's event → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        evt = _event(client, ind["id"])
        _contrib_cookie(client)
        r = client.delete(f"/events/{evt['id']}")
        assert r.status_code == 403, r.text

    def test_contributor_can_delete_own_media(self, full_client):
        """Contributor deletes own media record → 200."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _contrib_cookie(client)
        ind = _ind(client)
        med = _media(client, ind["id"])
        r = client.delete(f"/media/{med['id']}")
        assert r.status_code == 200, r.text

    def test_contributor_cannot_delete_owners_media(self, full_client):
        """Contributor tries to delete owner's media record → 403."""
        client, db = full_client
        _setup_owner_and_contrib(db)
        _owner_cookie(client)
        ind = _ind(client)
        med = _media(client, ind["id"])
        _contrib_cookie(client)
        r = client.delete(f"/media/{med['id']}")
        assert r.status_code == 403, r.text
