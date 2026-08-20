# tests/backend/test_local_app.py - Desktop ("local" mode) app behaviour.
#
# Covers the three things the desktop app adds on top of the shared backend:
#   - multiple trees under one data folder (list / create / switch / delete)
#   - the editor identity that is stamped into created_by, kept separate from
#     the tree so one person is not a different author in every tree
#   - config.json, which remembers all of the above across launches
#
# Every test runs against a throwaway data folder and a throwaway config file,
# so nothing here touches the developer's real datasets/ or %LocalAppData%.
#

import dataclasses
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import local_config
from backend.api import local as local_api
from database import db, owner_info

_TREE = "Smith Family"
_OTHER_TREE = "Jones Family"
_PERSON = {"sex_code": "F", "names": [{"given_name": "Ada", "family_name": "Lovelace"}]}


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    """A TestClient running as the desktop app against a temp data folder.

    Rebinds the module globals the launcher would normally set from env vars at
    process start. They are module attributes precisely so the running app can
    switch tree without a restart, which is what makes this fixture possible.
    """
    from backend.config import settings
    from backend.main import app
    from database.system_db import init_system_db, reset_system_db

    data_dir = (tmp_path / "data").resolve()
    cfg_dir = tmp_path / "cfg"
    data_dir.mkdir()
    cfg_dir.mkdir()

    # Settings is a frozen dataclass, so flip the mode by swapping in a copy
    # rather than assigning to the field. Only backend.api.local's reference is
    # replaced: backend.main keeps the real (is_dev) settings, which is what
    # bypasses auth for the /individuals calls these tests make.
    #
    monkeypatch.setattr(local_api, "settings", dataclasses.replace(settings, app_mode="local"))
    monkeypatch.setattr(local_config, "APP_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(local_config, "APP_CONFIG_FILE", cfg_dir / "config.json")
    monkeypatch.setattr(local_config, "LOG_FILE", cfg_dir / "novotree.log")
    monkeypatch.setattr(owner_info, "DATASETS_DIR", data_dir)
    monkeypatch.setattr(owner_info, "DEFAULT_OWNER_ID", local_config.DEFAULT_OWNER_ID)
    monkeypatch.setattr(owner_info, "EDITOR_ID", local_config.DEFAULT_OWNER_ID)
    monkeypatch.setattr(owner_info, "EDITOR_DISPLAY_NAME", local_config.DEFAULT_OWNER_ID)

    db.reset_engine()
    reset_system_db()
    init_system_db()

    with TestClient(app) as client:
        yield client, data_dir, cfg_dir

    db.reset_engine()
    reset_system_db()


def _config(cfg_dir):
    return json.loads((cfg_dir / "config.json").read_text(encoding="utf-8-sig"))


def _created_by(data_dir, tree):
    """created_by values straight from a tree's SQLite file, bypassing the API
    so the assertion is about what was persisted, not what a response said."""
    con = sqlite3.connect(str(data_dir / tree / "data.sqlite"))
    try:
        return [r[0] for r in con.execute("SELECT created_by FROM main_individuals")]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Trees: list / create / switch
# ---------------------------------------------------------------------------

def test_starts_with_the_default_tree_active(local_app):
    client, _, _ = local_app
    body = client.get("/local/trees").json()

    assert body["active"] == local_config.DEFAULT_OWNER_ID
    assert [t["owner_id"] for t in body["trees"]] == [local_config.DEFAULT_OWNER_ID]
    assert body["trees"][0]["is_active"] is True


def test_create_tree_makes_it_active_and_usable(local_app):
    client, data_dir, _ = local_app
    res = client.post("/local/create-tree", json={"owner_id": _TREE})

    assert res.status_code == 200
    assert res.json()["active"] == _TREE
    # Created eagerly rather than on first request, so the tree is complete the
    # moment the endpoint returns.
    assert (data_dir / _TREE / "media").is_dir()
    assert (data_dir / _TREE / "data.sqlite").exists()


def test_switch_tree_changes_where_writes_land(local_app):
    client, data_dir, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    assert client.post("/individuals", json=_PERSON).status_code == 200

    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    client.post("/individuals", json=_PERSON)

    assert len(_created_by(data_dir, _TREE)) == 1
    assert len(_created_by(data_dir, local_config.DEFAULT_OWNER_ID)) == 1


def test_tree_listing_reports_per_tree_person_counts(local_app):
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/individuals", json=_PERSON)
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})

    counts = {t["owner_id"]: t["individuals"] for t in client.get("/local/trees").json()["trees"]}
    assert counts == {local_config.DEFAULT_OWNER_ID: 0, _TREE: 1}


@pytest.mark.parametrize(
    "name",
    ["../escape", "CON", ".hidden", "", "  ", "a" * 65, "bad/slash", "back\\slash"],
)
def test_invalid_tree_names_are_rejected(local_app, name):
    client, _, _ = local_app
    assert client.post("/local/create-tree", json={"owner_id": name}).status_code == 400


def test_duplicate_tree_name_is_rejected_case_insensitively(local_app):
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    # NTFS folds case, so "smith family" and "Smith Family" are one directory.
    res = client.post("/local/create-tree", json={"owner_id": _TREE.lower()})
    assert res.status_code == 409


def test_switching_to_the_active_or_a_missing_tree_is_refused(local_app):
    client, _, _ = local_app
    active = local_config.DEFAULT_OWNER_ID
    assert client.post("/local/switch-tree", json={"owner_id": active}).status_code == 400
    assert client.post("/local/switch-tree", json={"owner_id": "Nope"}).status_code == 404


# ---------------------------------------------------------------------------
# Trees: delete
# ---------------------------------------------------------------------------

def test_delete_tree_removes_it_from_disk(local_app):
    client, data_dir, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})

    res = client.post("/local/delete-tree", json={"owner_id": _TREE})

    assert res.status_code == 200
    assert res.json() == {"ok": True, "deleted": _TREE, "remaining": 1, "purged": {}}
    assert not (data_dir / _TREE).exists()


def test_delete_releases_the_trees_open_database(local_app):
    """Reading from a tree leaves a pooled SQLAlchemy connection holding
    data.sqlite open; Windows refuses to remove a locked file, so the delete
    path has to drop the engine first."""
    client, data_dir, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/individuals", json=_PERSON)
    client.get("/individuals")
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})

    assert _TREE in db._pool  # the engine really is open before we delete
    assert client.post("/local/delete-tree", json={"owner_id": _TREE}).status_code == 200
    assert not (data_dir / _TREE).exists()


def test_the_open_tree_cannot_be_deleted(local_app):
    """Which is also why the last remaining tree can never be deleted: there is
    always exactly one active tree."""
    client, data_dir, _ = local_app
    active = local_config.DEFAULT_OWNER_ID

    assert client.post("/local/delete-tree", json={"owner_id": active}).status_code == 400
    assert (data_dir / active).is_dir()


def test_deleting_a_missing_tree_is_a_404(local_app):
    client, _, _ = local_app
    assert client.post("/local/delete-tree", json={"owner_id": "Ghost"}).status_code == 404


def _seed_system_rows(tree):
    """Insert one row per tree-scoped system table, plus the two that must
    survive a delete (an account and a privacy request)."""
    from database import system_models as m
    from database.system_db import get_system_session

    now = "2026-01-01T00:00:00+00:00"
    session = get_system_session()
    try:
        session.add_all([
            m.AuthShareToken(owner_id=tree, token=f"tok-{tree}", label="Link", is_active=True,
                             expires_after_days=90, expose_sensitive=False,
                             expose_minors=False, created_at=now),
            m.AuthShareConsent(editor_id="someone", tree_owner_id=tree, share_token_id=1,
                               accepted_at=now, accepted_ip="127.0.0.1",
                               privacy_policy_version="1.1"),
            m.AuthEditorTree(editor_id="contrib", owner_id=tree, is_active=True),
            m.AuthInvitation(owner_id=tree, display_name="C", email="c@example.com",
                             status="pending", created_at=now),
            m.AuthPendingContributor(editor_id=f"pend-{tree}", owner_id=tree,
                                     email="p@example.com", display_name="P",
                                     password_hash="x", token=f"pt-{tree}",
                                     expires_at=now, created_at=now),
            m.AuthSetPasswordToken(editor_id="contrib", owner_id=tree, token=f"sp-{tree}",
                                   expires_at=now),
            # Must survive: identity and a compliance record.
            m.AuthEditor(editor_id=tree, display_name="Owner", email="o@example.com",
                         role="owner", owner_id=tree, password_hash="x", is_active=True,
                         created_at=now),
            m.PrivacyRequest(tree_owner_id=tree, request_type="removal", status="open",
                             requester_name="N", requester_email="n@example.com",
                             message="m", created_at=now),
        ])
        session.commit()
    finally:
        session.close()


def _system_counts(tree):
    from database import system_models as m
    from database.system_db import get_system_session

    session = get_system_session()
    try:
        def n(model, column):
            return session.query(model).filter(getattr(model, column) == tree).count()

        return {
            "share_tokens": n(m.AuthShareToken, "owner_id"),
            "consents": n(m.AuthShareConsent, "tree_owner_id"),
            "editor_trees": n(m.AuthEditorTree, "owner_id"),
            "invitations": n(m.AuthInvitation, "owner_id"),
            "pending_contributors": n(m.AuthPendingContributor, "owner_id"),
            "set_password_tokens": n(m.AuthSetPasswordToken, "owner_id"),
            "editors": n(m.AuthEditor, "owner_id"),
            "privacy_requests": n(m.PrivacyRequest, "tree_owner_id"),
        }
    finally:
        session.close()


def test_delete_purges_the_trees_system_rows(local_app):
    """A share link that outlives its tree stays resolvable, and because
    OwnerInfo recreates missing directories the tree would come back as an
    empty folder the moment one resolved."""
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    _seed_system_rows(_TREE)

    res = client.post("/local/delete-tree", json={"owner_id": _TREE})

    assert res.status_code == 200
    after = _system_counts(_TREE)
    assert after["share_tokens"] == 0
    assert after["consents"] == 0
    assert after["editor_trees"] == 0
    assert after["invitations"] == 0
    assert after["pending_contributors"] == 0
    assert after["set_password_tokens"] == 0


def test_delete_keeps_identity_and_compliance_rows(local_app):
    """auth_editors is an identity, not tree data - a data folder shared with a
    web install must not lose its login. privacy_requests have their own
    retention window (PRIVACY_DESIGN.md section 6)."""
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    _seed_system_rows(_TREE)

    client.post("/local/delete-tree", json={"owner_id": _TREE})

    after = _system_counts(_TREE)
    assert after["editors"] == 1
    assert after["privacy_requests"] == 1


def test_delete_reports_what_it_purged(local_app):
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    _seed_system_rows(_TREE)

    purged = client.post("/local/delete-tree", json={"owner_id": _TREE}).json()["purged"]

    assert purged["auth_share_tokens"] == 1
    # Tables with nothing to remove are omitted rather than reported as zero.
    assert all(count > 0 for count in purged.values())


def test_delete_does_not_touch_another_trees_rows(local_app):
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/create-tree", json={"owner_id": _OTHER_TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    _seed_system_rows(_TREE)
    _seed_system_rows(_OTHER_TREE)

    client.post("/local/delete-tree", json={"owner_id": _TREE})

    survivor = _system_counts(_OTHER_TREE)
    assert survivor["share_tokens"] == 1
    assert survivor["editor_trees"] == 1


def test_delete_with_no_system_rows_reports_nothing_purged(local_app):
    """The ordinary desktop case: local mode never writes to system.sqlite, so
    there is nothing to clean up."""
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})

    assert client.post("/local/delete-tree", json={"owner_id": _TREE}).json()["purged"] == {}


def test_tree_listing_reports_share_link_counts(local_app):
    client, _, _ = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})
    _seed_system_rows(_TREE)

    trees = {t["owner_id"]: t["share_links"] for t in client.get("/local/trees").json()["trees"]}
    assert trees == {local_config.DEFAULT_OWNER_ID: 0, _TREE: 1}


def test_delete_leaves_config_untouched(local_app):
    """config.json names the *active* tree, and the active tree cannot be
    deleted -- so a delete can never strand the config on a tree that is gone,
    and has nothing to clean up."""
    client, _, cfg_dir = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/switch-tree", json={"owner_id": local_config.DEFAULT_OWNER_ID})

    before = _config(cfg_dir)
    client.post("/local/delete-tree", json={"owner_id": _TREE})

    assert _config(cfg_dir) == before


# ---------------------------------------------------------------------------
# Editor identity
# ---------------------------------------------------------------------------

def test_records_are_stamped_with_the_editor_not_the_tree(local_app):
    """The regression multi-tree introduced: with identity fused to the tree,
    the same person authoring in two trees produced two different authors."""
    client, data_dir, _ = local_app
    client.post("/local/identity", json={"editor_id": "igor", "display_name": "Igor N"})

    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/individuals", json=_PERSON)
    client.post("/local/create-tree", json={"owner_id": _OTHER_TREE})
    client.post("/individuals", json=_PERSON)

    assert _created_by(data_dir, _TREE) == ["igor"]
    assert _created_by(data_dir, _OTHER_TREE) == ["igor"]


def test_display_name_survives_a_refresh(local_app):
    """Local mode has no AuthEditor row to resolve names against, so without a
    config-backed fallback the UI showed the session name on create and the
    bare editor id on the next read."""
    client, _, _ = local_app
    client.post("/local/identity", json={"editor_id": "igor", "display_name": "Igor N"})

    created = client.post("/individuals", json=_PERSON).json()
    refetched = client.get(f"/individuals/{created['id']}").json()

    assert created["created_by_display_name"] == "Igor N"
    assert refetched["created_by_display_name"] == "Igor N"


def test_identity_change_does_not_rewrite_existing_rows(local_app):
    client, data_dir, _ = local_app
    client.post("/local/identity", json={"editor_id": "old_me", "display_name": "Old"})
    client.post("/individuals", json=_PERSON)

    client.post("/local/identity", json={"editor_id": "new_me", "display_name": "New"})
    client.post("/individuals", json=_PERSON)

    assert _created_by(data_dir, local_config.DEFAULT_OWNER_ID) == ["old_me", "new_me"]


def test_identity_survives_switching_tree(local_app):
    client, _, cfg_dir = local_app
    client.post("/local/identity", json={"editor_id": "igor", "display_name": "Igor N"})
    client.post("/local/create-tree", json={"owner_id": _TREE})

    info = client.get("/local/info").json()
    assert (info["editor_id"], info["display_name"]) == ("igor", "Igor N")
    assert _config(cfg_dir)["editor_id"] == "igor"


@pytest.mark.parametrize("editor_id", ["has space", "bad/slash", "", "a" * 33, "dot.dot"])
def test_invalid_editor_ids_are_rejected(local_app, editor_id):
    client, _, _ = local_app
    res = client.post("/local/identity", json={"editor_id": editor_id, "display_name": "X"})
    assert res.status_code == 400


def test_blank_display_name_falls_back_to_the_editor_id(local_app):
    client, _, _ = local_app
    res = client.post("/local/identity", json={"editor_id": "igor", "display_name": "   "})
    assert res.json()["display_name"] == "igor"


# ---------------------------------------------------------------------------
# config.json
# ---------------------------------------------------------------------------

def test_config_records_every_choice(local_app):
    client, data_dir, cfg_dir = local_app
    client.post("/local/create-tree", json={"owner_id": _TREE})
    client.post("/local/identity", json={"editor_id": "igor", "display_name": "Igor N"})

    assert _config(cfg_dir) == {
        "data_dir": str(data_dir),
        "owner_id": _TREE,
        "editor_id": "igor",
        "display_name": "Igor N",
    }


def test_changing_the_tree_keeps_the_identity_and_vice_versa(local_app):
    """The two are written by different endpoints into one file; each writes
    the whole config from live state so neither can drop the other's field."""
    client, _, cfg_dir = local_app
    client.post("/local/identity", json={"editor_id": "igor", "display_name": "Igor N"})
    client.post("/local/create-tree", json={"owner_id": _TREE})

    after_tree_change = _config(cfg_dir)
    assert after_tree_change["editor_id"] == "igor"
    assert after_tree_change["owner_id"] == _TREE

    client.post("/local/identity", json={"editor_id": "someone", "display_name": "S"})
    assert _config(cfg_dir)["owner_id"] == _TREE


def test_legacy_configs_are_read_forward(local_app):
    """A config written before multi-tree / identity support must keep working:
    the tree defaults to the historical one and the editor to the tree id, so
    rows already written still resolve to the handle they carry."""
    _, data_dir, cfg_dir = local_app

    (cfg_dir / "config.json").write_text(
        json.dumps({"data_dir": str(data_dir)}), encoding="utf-8"
    )
    loaded = local_config.load()
    assert loaded.owner_id == local_config.DEFAULT_OWNER_ID
    assert loaded.editor_id == local_config.DEFAULT_OWNER_ID

    (cfg_dir / "config.json").write_text(
        json.dumps({"data_dir": str(data_dir), "owner_id": "aktiniya"}), encoding="utf-8"
    )
    loaded = local_config.load()
    assert loaded.editor_id == "aktiniya"
    assert loaded.display_name == "aktiniya"


def test_unreadable_config_reprompts_rather_than_crashing(local_app):
    _, _, cfg_dir = local_app
    (cfg_dir / "config.json").write_text("{ not json", encoding="utf-8")
    assert local_config.load() is None


# ---------------------------------------------------------------------------
# Mode gating
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/local/info", None),
        ("get", "/local/trees", None),
        ("post", "/local/switch-tree", {"owner_id": "x"}),
        ("post", "/local/create-tree", {"owner_id": "x"}),
        ("post", "/local/delete-tree", {"owner_id": "x"}),
        ("post", "/local/identity", {"editor_id": "x", "display_name": "X"}),
    ],
)
def test_local_endpoints_are_absent_outside_local_mode(local_app, monkeypatch, method, path, payload):
    """The web/VM deployment neither has nor needs these routes."""
    client, _, _ = local_app
    from backend.config import settings

    monkeypatch.setattr(
        local_api, "settings", dataclasses.replace(settings, app_mode="production")
    )
    res = getattr(client, method)(path, **({"json": payload} if payload else {}))
    assert res.status_code == 404
