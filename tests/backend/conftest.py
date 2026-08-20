# tests/backend/conftest.py - Backend-specific test fixtures
#
# Test Configuration:
# - Uses tests/backend/<test_module>/temp/ as "datasets" folder
# - Database is reset between tests
#

import pytest
from pathlib import Path

# unittest.mock: standard-library tools for replacing real objects with fakes during tests.
# MagicMock: a fake object that accepts any attribute/method without complaining — used to
#            build a fake `settings` (m.is_dev, m.smtp_enabled, etc.) without instantiating
#            the real Settings class.
# patch: context manager that temporarily swaps a named object in a module with a fake,
#        then restores the original on exit — used to inject the mock settings into every
#        module that imports it for the duration of one test.
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import db
from database.system_models import SystemBase
from tests.conftest import get_test_owner
from tests.backend.db_utils import DatabaseUtils, IndividualVerifier, FamilyVerifier


# ---------------------------------------------------------------------------
# Datasets isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _isolate_datasets_dir(tmp_path_factory):
    """Point the datasets root at a throwaway directory for every backend test.

    Backend tests never read the real datasets/ - they build their trees in
    in-memory SQLite or in a module temp dir. But a request whose owner has no
    engine in the pool makes owner_db_router materialise datasets/<owner>/, and
    the contributor fixtures authenticate as "owner1" without registering one.
    That left a stray datasets/owner1/ in the working tree after every run.
    Repointing the root keeps any such write inside pytest's tmp area.

    Session-scoped, so monkeypatch (function-scoped) is not available; the
    original value is restored by hand.
    """
    from database import owner_info

    original = owner_info.DATASETS_DIR
    owner_info.DATASETS_DIR = tmp_path_factory.mktemp("datasets")
    try:
        yield
    finally:
        owner_info.DATASETS_DIR = original


# ---------------------------------------------------------------------------
# Auth client fixtures shared by test_auth_contributor and test_logging
# ---------------------------------------------------------------------------

def _prod_settings(smtp_enabled: bool = False):
    """MagicMock of settings with is_dev=False and real JWT key."""
    from backend.config import settings as real_settings
    m = MagicMock()
    m.is_dev = False
    m.app_mode = "production"
    m.jwt_secret_key = real_settings.jwt_secret_key
    m.cookie_secure = False
    m.smtp_enabled = smtp_enabled
    m.smtp_from = "test@example.com"
    m.rate_limit_per_minute = 99999
    return m


def _make_system_db_client(smtp_enabled: bool):
    from backend.main import app
    from database import db as tree_db
    from database.system_db import get_system_db

    # Clear any stale tree DB engine left by a previous test — the app has a global
    # engine pool and could accidentally use it even though this test doesn't need it.
    #
    tree_db.reset_engine()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single shared connection — required for in-memory SQLite
    )
    SystemBase.metadata.create_all(bind=engine)
    SF = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_system_db():
        session = SF()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_system_db] = override_get_system_db

    mock_s = _prod_settings(smtp_enabled=smtp_enabled)

    with patch("backend.api.auth.settings", mock_s), \
         patch("backend.main.settings", mock_s), \
         patch("backend.api.users.settings", mock_s):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, SF

    app.dependency_overrides.pop(get_system_db, None)
    engine.dispose()
    tree_db.reset_engine()


@pytest.fixture()
def system_db_client_smtp():
    """TestClient backed by an in-memory system DB with SMTP enabled.

    Initializes only the system DB (AuthEditor, AuthEditorTree). No tree/owner DB.
    Settings patched to is_dev=False. Use when tests need to assert on outgoing emails.
    """
    yield from _make_system_db_client(smtp_enabled=True)


@pytest.fixture()
def system_db_client():
    """TestClient backed by an in-memory system DB, SMTP off.

    Initializes only the system DB (AuthEditor, AuthEditorTree). No tree/owner DB.
    Settings patched to is_dev=False so the production auth guard fires.
    """
    yield from _make_system_db_client(smtp_enabled=False)


@pytest.fixture()
def full_client(tmp_path):
    """TestClient backed by both the system DB and the tree DB.

    Use when a test exercises contributor auth AND tree data in the same request
    (e.g. verifying created_by attribution on /individuals). Both databases are
    isolated in-memory SQLite instances. Settings patched to is_dev=False.
    Yields (client, system_db_factory).

    The tree engine is also registered in the db pool under owner_id "owner1"
    so that internal helpers like _has_contributions() see the same data.
    """
    from backend.main import app
    from database import db as tree_db_module
    from database.system_db import get_system_db
    from database.owner_info import OwnerInfo
    from backend.api.auth import get_tree_db, get_tree_owner_info, get_viewer_owner_info
    from database.models import Base as TreeBase

    tree_db_module.reset_engine()

    sys_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SystemBase.metadata.create_all(bind=sys_engine)
    SysSF = sessionmaker(autocommit=False, autoflush=False, bind=sys_engine)

    tree_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TreeBase.metadata.create_all(bind=tree_engine)
    TreeSF = sessionmaker(autocommit=False, autoflush=False, bind=tree_engine)

    # Register in the module-level pool so _has_contributions() and other
    # internal helpers that call db.get_db("owner1") directly use this engine.
    tree_db_module._pool["owner1"] = (tree_engine, TreeSF)

    # Provide a writable media dir backed by pytest's tmp_path.
    test_owner_info = OwnerInfo(owner_id="owner1", base_dir=tmp_path)

    def _sys_db():
        session = SysSF()
        try:
            yield session
        finally:
            session.close()

    def _tree_db():
        session = TreeSF()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_system_db] = _sys_db
    app.dependency_overrides[get_tree_db] = _tree_db
    app.dependency_overrides[get_tree_owner_info] = lambda: test_owner_info
    app.dependency_overrides[get_viewer_owner_info] = lambda: test_owner_info

    mock_s = _prod_settings(smtp_enabled=False)

    with patch("backend.api.auth.settings", mock_s), \
         patch("backend.main.settings", mock_s), \
         patch("backend.api.users.settings", mock_s):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, SysSF

    app.dependency_overrides.pop(get_system_db, None)
    app.dependency_overrides.pop(get_tree_db, None)
    app.dependency_overrides.pop(get_tree_owner_info, None)
    app.dependency_overrides.pop(get_viewer_owner_info, None)
    sys_engine.dispose()
    tree_engine.dispose()
    tree_db_module.reset_engine()


# ---------------------------------------------------------------------------
# Tree-DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def test_owner(request):
    """Provide OwnerInfo for the test module."""
    test_module_path = Path(request.fspath)
    return get_test_owner(test_module_path)


@pytest.fixture(scope="function")
def tree_db_client(test_owner):
    """TestClient backed by the tree DB initialized for the test module.

    Initializes only the tree DB (individuals, families, etc.) — no system DB.
    Settings are not patched; uses the real application configuration.
    """
    # Reset any existing engine state
    db.reset_engine()

    # Initialize DB engine for test owner
    db.init_db_once(test_owner)

    # IMPORTANT: import 'app' after engine initialization!
    # Otherwise it will try to use the default owner's database
    from backend.main import app
    from backend.api.auth import get_tree_owner_info, get_viewer_owner_info

    # Override owner-info dependencies so media paths resolve to the test temp dir
    app.dependency_overrides[get_tree_owner_info] = lambda: test_owner
    app.dependency_overrides[get_viewer_owner_info] = lambda: test_owner

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_tree_owner_info, None)
    app.dependency_overrides.pop(get_viewer_owner_info, None)

    # Reset engine after test
    db.reset_engine()


@pytest.fixture(scope="function")
def db_utils(test_owner, tree_db_client):
    """Provide DatabaseUtils instance for database verification."""
    return DatabaseUtils(test_owner.db_file)


@pytest.fixture(scope="function")
def individual_verifier(db_utils):
    """Provide IndividualVerifier instance."""
    return IndividualVerifier(db_utils)


@pytest.fixture(scope="function")
def family_verifier(db_utils):
    """Provide FamilyVerifier instance."""
    return FamilyVerifier(db_utils)


@pytest.fixture
def sample_individual_data():
    """Reusable sample individual data for creating records."""
    return {
        "sex_code": "M",
        "birth_date": "1980-01-15",
        "birth_place": "Jasnaya Polyana, USSR",
        "death_date": None,
        "death_place": None,
        "notes": "Test individual",
        "names": [
            {
                "given_name": "Vasya",
                "family_name": "Pryanik"
            }
        ]
    }
