"""
Regression tests for minor (GDPR Art. 8) handling (Privacy PRIVACY_DESIGN.md 3.8
/ M-06).

Two independent surfaces, mirroring the special-category gating in
test_sensitive_gating.py:

  - share-link viewer payload: a living minor (node, edges, media) is excluded
    when the token's expose_minors is False (the default) and included when
    True. This is independent of expose_sensitive -- a token may expose one
    category but not the other.
  - photo upload: POST /media/upload for a living minor is rejected with 403
    until the Owner records parental_consent on the individual.

The Owner (non-share session) always sees minors regardless -- there is no
minor-hiding toggle for the Owner; it is purely a share/viewer concern.

Backed by the full_client fixture (in-memory system + tree DB), which patches
settings to is_dev=False so the share-token code path runs. The default
child_age_threshold_years is 16.
"""

from datetime import date, datetime, timezone, timedelta

from database.models import Individual, IndividualName, Media, individual_is_minor
from database.system_models import AuthShareToken


_OWNER_ID = "owner1"  # the owner_id full_client registers the tree engine under


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _years_ago(years: int) -> date:
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # Feb 29 -> Mar 1
        return today.replace(year=today.year - years, day=1, month=3)


def _seed_share_token(SysSF, *, expose_sensitive: bool, expose_minors: bool) -> str:
    token = f"sharetok-{int(expose_sensitive)}{int(expose_minors)}"
    with SysSF() as s:
        s.add(AuthShareToken(
            owner_id=_OWNER_ID,
            token=token,
            label="test",
            is_active=True,
            expires_after_days=90,
            expose_sensitive=expose_sensitive,
            expose_minors=expose_minors,
            created_at=_now(),
            last_used_at=_now(),
        ))
        s.commit()
    return token


def _seed_tree():
    """Populate the pooled tree DB with an adult parent and a living minor child.

    Layout: ADULT (born 40y ago) is the focus/parent; MINOR (born 5y ago, alive)
    is their child, so an edge references the minor. The minor carries a photo so
    the media-exclusion path can be exercised. Returns the ids for assertions.
    """
    from database import db as tree_db_module
    from database.db import get_db as _get_db

    tree_db_module._seed_lookup_tables(tree_db_module._pool[_OWNER_ID][0])

    db_gen = _get_db(_OWNER_ID)
    db = next(db_gen)
    try:
        from database.models import Family, FamilyMember, FamilyChild

        adult = Individual(
            gedcom_id="I1",
            sex_code="M",
            birth_date=_years_ago(40),
            created_by=_OWNER_ID,
            created_at=_now(),
        )
        adult.names = [IndividualName(given_name="Adult", family_name="Parent", name_order=0)]

        minor = Individual(
            gedcom_id="I2",
            sex_code="F",
            birth_date=_years_ago(5),
            created_by=_OWNER_ID,
            created_at=_now(),
        )
        minor.names = [IndividualName(given_name="Minor", family_name="Child", name_order=0)]
        minor.media = [
            Media(file_path="minor.jpg", media_type_code="photo", age_on_photo=5,
                  created_by=_OWNER_ID, created_at=_now()),
        ]

        db.add_all([adult, minor])
        db.commit()
        db.refresh(adult)
        db.refresh(minor)

        family = Family(gedcom_id="F1", family_type="marriage",
                        created_by=_OWNER_ID, created_at=_now())
        db.add(family)
        db.commit()
        db.refresh(family)
        db.add(FamilyMember(family_id=family.id, individual_id=adult.id, role="parent"))
        db.add(FamilyChild(family_id=family.id, child_id=minor.id))
        db.commit()

        return {
            "adult_id": adult.id,
            "minor_id": minor.id,
            "minor_media_id": minor.media[0].id,
        }
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def _find_node(payload: dict, ind_id: int):
    return next((n for n in payload["nodes"] if n["id"] == ind_id), None)


# ---------------------------------------------------------------------------
# individual_is_minor() unit boundaries
# ---------------------------------------------------------------------------

class TestIsMinorHelper:
    def test_young_living_person_is_minor(self):
        ind = Individual(birth_date=_years_ago(5))
        assert individual_is_minor(ind, 16) is True

    def test_adult_is_not_minor(self):
        ind = Individual(birth_date=_years_ago(40))
        assert individual_is_minor(ind, 16) is False

    def test_deceased_young_person_is_not_minor(self):
        ind = Individual(birth_date=_years_ago(5), death_date=_years_ago(1))
        assert individual_is_minor(ind, 16) is False

    def test_exactly_threshold_is_not_minor(self):
        # Born exactly threshold years ago -> reached the threshold today -> adult.
        ind = Individual(birth_date=_years_ago(16))
        assert individual_is_minor(ind, 16) is False

    def test_just_under_threshold_is_minor(self):
        ind = Individual(birth_date=_years_ago(16) + timedelta(days=2))
        assert individual_is_minor(ind, 16) is True

    def test_approx_only_date_is_not_minor(self):
        # No exact birth_date -> cannot prove age -> not auto-detected.
        ind = Individual(birth_date=None, birth_date_approx="ABT 2015")
        assert individual_is_minor(ind, 16) is False


# ---------------------------------------------------------------------------
# Share-link viewer payload
# ---------------------------------------------------------------------------

class TestShareViewerExcludesMinors:
    def test_minor_hidden_when_not_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False, expose_minors=False)

        r = client.get(f"/tree/full?share={token}")
        assert r.status_code == 200
        payload = r.json()

        assert _find_node(payload, ids["adult_id"]) is not None
        # Minor omitted entirely, and no edge references them.
        assert _find_node(payload, ids["minor_id"]) is None
        for e in payload["edges"]:
            assert e["parent_id"] != ids["minor_id"]
            assert e["child_id"] != ids["minor_id"]

    def test_minor_included_when_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False, expose_minors=True)

        r = client.get(f"/tree/full?share={token}")
        assert r.status_code == 200
        payload = r.json()
        assert _find_node(payload, ids["minor_id"]) is not None


class TestExposeFlagsAreIndependent:
    """expose_sensitive and expose_minors gate different categories."""

    def test_sensitive_exposed_still_hides_minor(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=True, expose_minors=False)

        payload = client.get(f"/tree/full?share={token}").json()
        assert _find_node(payload, ids["minor_id"]) is None

    def test_minors_exposed_still_shows_minor(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False, expose_minors=True)

        payload = client.get(f"/tree/full?share={token}").json()
        assert _find_node(payload, ids["minor_id"]) is not None


class TestShareViewerMedia:
    def test_minor_media_excluded_when_not_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False, expose_minors=False)

        r = client.get(f"/media/{ids['minor_media_id']}?share={token}")
        assert r.status_code == 404

    def test_minor_media_included_when_exposed(self, full_client):
        client, SysSF = full_client
        ids = _seed_tree()
        token = _seed_share_token(SysSF, expose_sensitive=False, expose_minors=True)

        r = client.get(f"/media?individual_id={ids['minor_id']}&share={token}")
        assert r.status_code == 200
        returned_ids = {m["id"] for m in r.json()}
        assert ids["minor_media_id"] in returned_ids


# ---------------------------------------------------------------------------
# Owner (non-share session) always sees minors
# ---------------------------------------------------------------------------

class TestOwnerSeesMinors:
    def test_owner_full_tree_includes_minor(self, full_client):
        from tests.backend.test_share_consent import _owner_token, _seed_owner

        client, SysSF = full_client
        ids = _seed_tree()
        _seed_owner(SysSF)
        client.cookies.set("access_token", _owner_token())

        payload = client.get("/tree/full").json()
        assert _find_node(payload, ids["minor_id"]) is not None


# ---------------------------------------------------------------------------
# Parental-consent upload gate
# ---------------------------------------------------------------------------

class TestParentalConsentUploadGate:
    def _upload(self, client, individual_id: int):
        # 1x1 white JPEG is unnecessary -- the gate fires before file validation,
        # but send a small payload with an image content type so we reach it.
        files = {"file": ("p.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg", "image/jpeg")}
        data = {"individual_id": str(individual_id), "age_on_photo": "5", "is_default": "false"}
        return client.post("/media/upload", files=files, data=data)

    def test_upload_for_minor_without_consent_is_403(self, full_client):
        from tests.backend.test_share_consent import _owner_token, _seed_owner

        client, SysSF = full_client
        ids = _seed_tree()
        _seed_owner(SysSF)
        client.cookies.set("access_token", _owner_token())

        r = self._upload(client, ids["minor_id"])
        assert r.status_code == 403
        assert "consent" in r.json()["detail"].lower()

    def test_upload_for_minor_with_consent_passes_gate(self, full_client):
        from tests.backend.test_share_consent import _owner_token, _seed_owner

        client, SysSF = full_client
        ids = _seed_tree()
        _seed_owner(SysSF)
        client.cookies.set("access_token", _owner_token())

        # Record consent, then the gate must let the request through. The fake
        # JPEG bytes are not a decodable image, so a successful gate yields a
        # non-403 (the upload itself may 200 since the endpoint stores raw bytes).
        client.put(f"/individuals/{ids['minor_id']}", json={"parental_consent": True})

        r = self._upload(client, ids["minor_id"])
        assert r.status_code != 403

    def test_upload_for_adult_never_gated(self, full_client):
        from tests.backend.test_share_consent import _owner_token, _seed_owner

        client, SysSF = full_client
        ids = _seed_tree()
        _seed_owner(SysSF)
        client.cookies.set("access_token", _owner_token())

        r = self._upload(client, ids["adult_id"])
        assert r.status_code != 403
