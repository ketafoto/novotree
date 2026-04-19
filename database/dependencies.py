# FastAPI dependency factories for per-request owner database access.
#
# Usage in endpoints:
#
#   from database.dependencies import get_tree_db, get_tree_owner_info
#
#   @router.get("/something")
#   def my_endpoint(
#       db: Session = Depends(get_tree_db),
#       session: EditorSession = Depends(require_editor),
#   ): ...
#
# For viewer endpoints that also accept share tokens, use get_viewer_db instead.
#
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from database import db as _db
from database.owner_info import OwnerInfo


def _db_for_owner(owner_id: str) -> Generator[Session, None, None]:
    yield from _db.get_db(owner_id)


def get_tree_db(session: "EditorSession") -> Generator[Session, None, None]:  # type: ignore[name-defined]
    """Dependency: yield a tree DB session scoped to the authenticated editor's owner."""
    yield from _db.get_db(session.owner_id)


def get_tree_owner_info(session: "EditorSession") -> OwnerInfo:  # type: ignore[name-defined]
    """Dependency: return the OwnerInfo for the authenticated editor's owner."""
    return _db.get_owner_info(session.owner_id)


def get_viewer_db(owner_id: str) -> Generator[Session, None, None]:
    """Dependency: yield a tree DB session for viewer access (owner_id from share token or JWT)."""
    yield from _db.get_db(owner_id)


def get_viewer_owner_info(owner_id: str) -> OwnerInfo:
    """Dependency: return OwnerInfo for viewer access."""
    return _db.get_owner_info(owner_id)
