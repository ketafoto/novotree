"""
Regression tests for special-category (GDPR Art. 9) gating in the share-link
viewer payload (Privacy PRIVACY_DESIGN.md 3.7 / M-05).

The viewer surface for a share-token session is the tree payload (backend/api/tree.py)
and media (backend/api/media.py). These tests assert that, when a share token's
expose_sensitive flag is False (the default), the viewer sees no trace of:

  - sensitive EVENTS (inherently-religious types in SENSITIVE_EVENT_CODES, e.g.
    BAPM, AND events manually flagged is_sensitive),
  - sensitive NOTES (notes_sensitive blanks Individual.notes only),
  - a fully-sensitive INDIVIDUAL (is_sensitive omits the whole node + its edges),
  - sensitive MEDIA (manually flagged, or any media of a sensitive Individual);

and that flipping expose_sensitive to True includes all of it. The Owner
(non-share session) always sees everything regardless — the show-sensitive
toggle is UI-only and never reaches the backend.

Backed by the full_client fixture (in-memory system + tree DB), which patches
settings to is_dev=False so the share-token code path runs.
"""

from datetime import datetime, timezone, timedelta

from database.models import Event, Individual, IndividualName, Media
from database.system_models import AuthShareToken


_OWNER_ID = "owner1"  # the owner_id full_client registers the tree engine under


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_share_token(SysSF, expose_sensitive: bool) -> str:
    """Insert an active, non-expired share token for the test tree. Returns the raw token."""
    token = f"sharetok-{'expose' if expose_sensitive else 'hide'}"
    with SysSF() as s:
        s.add(AuthShareToken(
            owner_id=_OWNER_ID,
            token=token,
            label="test",
            is_active=True,
            expires_after_days=90,
            expose_sensitive=expose_sensitive,
            created_at=_now(),
            last_used_at=_now(),
        ))
        s.commit()
    return token


def _seed_tree():
    """Populate the pooled tree DB with two related individuals carrying assorted
    sensitive markers, and return the ids needed for assertions.

    Layout: FOCUS (the share link's focus person) has a BAPM (inherently
    sensitive) event, a manually is_sensitive OCCU event, a normal BIRT event,
    sensitive notes, a normal photo and a manually-sensitive photo. A second
    person SECRET is fully is_sensitive (whole-person exclusion) and is the
    FOCUS's child so an edge references them.
    """
    from database import db as tree_db_module
    from database.db import get_db as _get_db

    # full_client builds the tree engine with create_all only; the tree endpoints
    # read lookup_event_types directly, so seed the lookup tables here.
    tree_db_module._seed_lookup_tables(tree_db_module._pool[_OWNER_ID][0])

    db_gen = _get_db(_OWNER_ID)
    db = next(db_gen)
    try:
        focus = Individual(
            gedcom_id="I1",
            sex_code="M",
            notes="Catholic; converted 1990",
            notes_sensitive=True,
            created_by=_OWNER_ID,
            created_at=_now(),
        )
        focus.names = [IndividualName(given_name="Focus", family_name="Person", name_order=0)]
        focus.events = [
            Event(event_type_code="BIRT", event_place="Town", created_by=_OWNER_ID, created_at=_now()),
            Event(event_type_code="BAPM", event_place="Church", created_by=_OWNER_ID, created_at=_now()),
            Event(event_type_code="OCCU", description="secret job", is_sensitive=True,
                  created_by=_OWNER_ID, created_at=_now()),
        ]
        focus.media = [
            Media(file_path="ok.jpg", media_type_code="photo", age_on_photo=30,
                  created_by=_OWNER_ID, created_at=_now()),
            Media(file_path="secret.jpg", media_type_code="photo", age_on_photo=40,
                  is_sensitive=True, created_by=_OWNER_ID, created_at=_now()),
        ]

        secret = Individual(
            gedcom_id="I2",
            sex_code="F",
            is_sensitive=True,
            created_by=_OWNER_ID,
            created_at=_now(),
        )
        secret.names = [IndividualName(given_name="Secret", family_name="Person", name_order=0)]
        secret.media = [
            Media(file_path="secret_person.jpg", media_type_code="photo", age_on_photo=10,
                  created_by=_OWNER_ID, created_at=_now()),
        ]

        db.add_all([focus, secret])
        db.commit()
        db.refresh(focus)
        db.refresh(secret)

        ok_media_id = next(m.id for m in focus.media if m.file_path == "ok.jpg")
        secret_media_id = next(m.id for m in focus.media if m.file_path == "secret.jpg")
        secret_person_media_id = secret.media[0].id
        return {
            "focus_id": focus.id,
            "secret_id": secret.id,
            "ok_media_id": ok_media_id,
            "secret_media_id": secret_media_id,
            "secret_person_media_id": secret_person_media_id,
        }
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def _event_types(node: dict) -> set[str]:
    return {e["event_type"] for e in node["events"]}


def _find_node(payload: dict, ind_id: int):
    return next((n for n in payload["nodes"] if n["id"] == ind_id), None)


# ---------------------------------------------------------------------------
# Tree payload — viewer with a share token
# ---------------------------------------------------------------------------

class TestShareViewerExcludesSensitive:
    """expose_sensitive=False (default): the viewer sees no sensitive trace."""

    def test_full_tree_hides_sensitive_when_not_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False)

        r = client.get(f"/tree/full?share={token}")
        assert r.status_code == 200
        payload = r.json()

        focus = _find_node(payload, ids["focus_id"])
        assert focus is not None, "focus person should still be visible"

        # Sensitive events dropped (BAPM = inherently religious; OCCU here is
        # manually is_sensitive). Note: event_type is the human label, "Baptism".
        types = _event_types(focus)
        assert "Baptism" not in types
        assert "secret job" not in {e.get("description") for e in focus["events"]}
        # Non-sensitive birth event remains.
        assert "Birth" in types

        # Sensitive notes blanked.
        assert focus["notes"] is None

        # Fully-sensitive individual omitted entirely, and no edge references them.
        assert _find_node(payload, ids["secret_id"]) is None
        for e in payload["edges"]:
            assert e["parent_id"] != ids["secret_id"]
            assert e["child_id"] != ids["secret_id"]

    def test_focus_tree_hides_sensitive_when_not_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False)

        r = client.get(f"/individuals/{ids['focus_id']}/tree?share={token}")
        assert r.status_code == 200
        payload = r.json()
        focus = _find_node(payload, ids["focus_id"])
        assert focus is not None
        assert "Baptism" not in _event_types(focus)
        assert focus["notes"] is None


class TestShareViewerIncludesWhenExposed:
    """expose_sensitive=True: the viewer sees the sensitive data."""

    def test_full_tree_includes_sensitive_when_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=True)

        r = client.get(f"/tree/full?share={token}")
        assert r.status_code == 200
        payload = r.json()

        focus = _find_node(payload, ids["focus_id"])
        assert focus is not None
        types = _event_types(focus)
        assert "Baptism" in types
        assert "secret job" in {e.get("description") for e in focus["events"]}
        assert focus["notes"] == "Catholic; converted 1990"

        # Fully-sensitive individual present when exposed.
        assert _find_node(payload, ids["secret_id"]) is not None


# ---------------------------------------------------------------------------
# Media — viewer with a share token
# ---------------------------------------------------------------------------

class TestShareViewerMedia:
    def test_media_list_excludes_sensitive_when_not_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False)

        r = client.get(f"/media?individual_id={ids['focus_id']}&share={token}")
        assert r.status_code == 200
        returned_ids = {m["id"] for m in r.json()}
        assert ids["ok_media_id"] in returned_ids
        assert ids["secret_media_id"] not in returned_ids  # manually flagged photo

    def test_media_of_sensitive_individual_excluded(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False)

        # Direct fetch of a photo belonging to a fully-sensitive Individual 404s.
        r = client.get(f"/media/{ids['secret_person_media_id']}?share={token}")
        assert r.status_code == 404

    def test_media_included_when_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=True)

        r = client.get(f"/media?individual_id={ids['focus_id']}&share={token}")
        assert r.status_code == 200
        returned_ids = {m["id"] for m in r.json()}
        assert ids["secret_media_id"] in returned_ids


# ---------------------------------------------------------------------------
# Owner (non-share session) always sees everything — toggle is UI-only
# ---------------------------------------------------------------------------

class TestOwnerSeesEverything:
    def test_owner_full_tree_unfiltered(self, full_client):
        from tests.backend.test_share_consent import _owner_token, _seed_owner

        client, SysSF = full_client
        ids = _seed_tree()
        _seed_owner(SysSF)  # seeds editor_id == owner1 with an owner role
        client.cookies.set("access_token", _owner_token())

        r = client.get("/tree/full")
        assert r.status_code == 200
        payload = r.json()

        focus = _find_node(payload, ids["focus_id"])
        assert focus is not None
        assert "Baptism" in _event_types(focus)
        assert focus["notes"] == "Catholic; converted 1990"
        # Whole-person-sensitive individual is visible to the owner.
        assert _find_node(payload, ids["secret_id"]) is not None
