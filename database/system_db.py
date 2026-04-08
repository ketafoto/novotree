"""
Session management for the global system database (datasets/system.sqlite).

This database holds auth data — editors, share tokens, invitations, set-password
tokens — completely separate from each owner's genealogy data.sqlite.

Usage
-----
FastAPI dependency (in route functions):
    db: Session = Depends(get_system_db)

Outside FastAPI (e.g. middleware, lifespan):
    session = get_system_session()
    try:
        ...
    finally:
        session.close()
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .system_models import SystemBase

# datasets/ directory sits next to the database/ package
_DATASETS_DIR = Path(__file__).parent.parent / "datasets"
_SYSTEM_DB_FILE = _DATASETS_DIR / "system.sqlite"

_engine = None
_SystemSession: sessionmaker | None = None


def init_system_db() -> None:
    """
    Create datasets/system.sqlite and all auth tables if they don't exist.
    Safe to call multiple times (idempotent).
    """
    global _engine, _SystemSession

    _DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        f"sqlite:///{_SYSTEM_DB_FILE}",
        connect_args={"check_same_thread": False},
    )
    SystemBase.metadata.create_all(bind=_engine)
    _SystemSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_system_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a SQLAlchemy Session for the system database.

        db: Session = Depends(get_system_db)
    """
    if _SystemSession is None:
        raise RuntimeError("System database is not initialized. Call init_system_db() first.")

    session = _SystemSession()
    try:
        yield session
    finally:
        session.close()


def get_system_session() -> Session:
    """
    Return a bare Session for use outside FastAPI dependency injection
    (e.g. middleware, lifespan hooks).

    Caller is responsible for calling session.close().
    """
    if _SystemSession is None:
        raise RuntimeError("System database is not initialized. Call init_system_db() first.")
    return _SystemSession()


def reset_system_db() -> None:
    """
    Dispose the engine and clear internal state.
    Used in tests to get a clean slate.
    """
    global _engine, _SystemSession
    if _engine:
        _engine.dispose()
    _engine = None
    _SystemSession = None
