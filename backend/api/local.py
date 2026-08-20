"""
Local-app endpoints.

  GET  /local/info             - read-only paths (data folder, config, log)
                                  plus the active tree id
  GET  /local/trees            - every tree under the current data folder
  POST /local/switch-tree      - open a different tree in the same folder
  POST /local/create-tree      - create an empty tree and switch to it
  POST /local/delete-tree      - permanently delete a tree that is not open
  POST /local/identity         - set who is recorded as adding records
  POST /local/pick-data-dir    - open a native folder picker, return chosen path
  POST /local/change-data-dir  - move data to chosen path, update config & DBs
                                  *at runtime* (no process restart)
  POST /local/open-in-explorer - open Windows Explorer at a given path
  POST /local/open-with-default - open a path with the OS default program
                                  (folder -> Explorer; file -> registered app
                                  for that extension, e.g. .log -> Notepad)
  POST /local/save-as          - open a SaveAs dialog and write request body
                                  to the chosen path (used for downloads -
                                  pywebview/WebView2 doesn't reliably show
                                  a SaveAs dialog for `<a download>` clicks)

Two axes, deliberately separate: the *data folder* is the root holding
system.sqlite and one subfolder per tree (changed by /change-data-dir, which
moves files); the *tree* is which of those subfolders is open (changed by
/switch-tree, which moves nothing).

All endpoints return 404 in any mode other than `local` - the web/VM
deployment neither has nor needs them.
"""

import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func

from backend import local_config
from backend.config import settings
from database import db
from database import owner_info  # full-module access - DATASETS_DIR / DEFAULT_OWNER_ID are rebindable
from database import system_models
from database.system_db import get_system_session, init_system_db, reset_system_db

logger = logging.getLogger("novotree.local")


class LocalAppInfo(BaseModel):
    data_dir: str        # SQLite databases + media - picked by the user on first run
    owner_id: str        # active tree; its files live at <data_dir>/<owner_id>/
    editor_id: str       # stamped into created_by on every row this user adds
    display_name: str    # shown as "Added by ..."
    config_file: str     # %AppData%\NovoSpace\NovoTree\config.json (remembers both choices)
    log_file: str        # rotating launcher log (max ~6 MB on disk)


class TreeInfo(BaseModel):
    owner_id: str                 # folder name under the data dir; also the tree's id
    is_active: bool               # currently open in this session
    individuals: Optional[int]    # None when the tree's DB is absent or unreadable
    size_bytes: int               # data.sqlite + media, for a rough size hint
    share_links: int              # share tokens in system.sqlite pointing at this tree
    modified_at: Optional[str]    # ISO-8601 UTC mtime of the newest file in the tree


class TreeListResponse(BaseModel):
    active: str
    trees: list[TreeInfo]


class TreeNameRequest(BaseModel):
    owner_id: str


class IdentityRequest(BaseModel):
    editor_id: str
    display_name: str


class TreeActionResponse(BaseModel):
    ok: bool
    active: str


class DeleteTreeResponse(BaseModel):
    ok: bool
    deleted: str
    remaining: int
    purged: dict[str, int]        # system.sqlite table -> rows removed with the tree


class PickDataDirResponse(BaseModel):
    path: Optional[str]  # None if the user cancelled the dialog


class ChangeDataDirRequest(BaseModel):
    new_path: str


class ChangeDataDirResponse(BaseModel):
    ok: bool
    moved_to: str
    items_moved: int


class OpenInExplorerRequest(BaseModel):
    path: str


class OpenWithDefaultRequest(BaseModel):
    path: str


router = APIRouter(prefix="/local", tags=["Local app"])


def _require_local() -> None:
    if not settings.is_local:
        raise HTTPException(status_code=404, detail="Not running as local desktop app")


@router.get("/info", response_model=LocalAppInfo)
def local_info() -> LocalAppInfo:
    _require_local()
    return LocalAppInfo(
        data_dir=str(owner_info.DATASETS_DIR),
        owner_id=owner_info.DEFAULT_OWNER_ID,
        editor_id=owner_info.EDITOR_ID,
        display_name=owner_info.EDITOR_DISPLAY_NAME,
        config_file=str(local_config.APP_CONFIG_FILE),
        log_file=str(local_config.LOG_FILE),
    )


@router.post("/pick-data-dir", response_model=PickDataDirResponse)
def pick_data_dir() -> PickDataDirResponse:
    """Open a native folder-picker dialog (pywebview's, NOT tkinter) and
    return the user's choice. Returns null if the user cancelled."""
    _require_local()
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(500, f"pywebview not available: {exc}")

    if not webview.windows:
        raise HTTPException(503, "No window available for the picker to attach to")

    initial = str(
        owner_info.DATASETS_DIR.parent
        if owner_info.DATASETS_DIR.parent.exists()
        else owner_info.DATASETS_DIR
    )
    try:
        result = webview.windows[0].create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=initial,
        )
    except Exception as exc:
        raise HTTPException(500, f"Folder picker failed: {exc}")

    chosen = result[0] if result else None
    return PickDataDirResponse(path=chosen)


@router.post("/change-data-dir", response_model=ChangeDataDirResponse)
def change_data_dir(req: ChangeDataDirRequest) -> ChangeDataDirResponse:
    """Move all data + media from the current data folder to `new_path`,
    rebind DATASETS_DIR in-process, re-init the system DB at the new path,
    and persist the choice in config.json — all WITHOUT restarting the app.
    The frontend reloads itself so React Query starts fresh against the new
    location."""
    _require_local()

    new_path = Path(req.new_path).expanduser().resolve()
    current = owner_info.DATASETS_DIR.resolve()

    # ── Validation ────────────────────────────────────────────────────────
    if new_path == current:
        raise HTTPException(400, "New path is the same as the current data folder")

    # Refuse moving into a sub-tree of the current path: it would mean copying
    # data into itself, which shutil.move handles unpredictably.
    try:
        new_path.relative_to(current)
        raise HTTPException(400, "Cannot move data into a subdirectory of itself")
    except ValueError:
        pass  # not a subpath — good

    new_path.mkdir(parents=True, exist_ok=True)

    # New path must be empty (we don't want to silently merge with arbitrary
    # other files the user has there). Hidden / dotfiles are tolerated.
    visible_existing = [p.name for p in new_path.iterdir() if not p.name.startswith(".")]
    if visible_existing:
        raise HTTPException(
            409,
            f"Target folder is not empty (found {len(visible_existing)} item(s): "
            f"{', '.join(visible_existing[:5])}{'…' if len(visible_existing) > 5 else ''}). "
            "Pick an empty folder.",
        )

    # ── Release SQLite file handles ───────────────────────────────────────
    # SQLAlchemy holds open connections; on Windows that prevents the .sqlite
    # file from being moved. Dispose all engines, then give Windows a beat to
    # actually release the handles (Defender re-scans tend to delay this).
    db.reset_engine()
    reset_system_db()
    time.sleep(0.5)

    # ── Move ──────────────────────────────────────────────────────────────
    moved_count = 0
    try:
        for item in current.iterdir():
            target = new_path / item.name
            _move_with_retry(item, target)
            moved_count += 1
    except Exception as exc:
        logger.exception("Move failed after %d items", moved_count)
        # Try to bring the system DB back up at the OLD path so the app stays
        # usable while the user resolves the half-moved state by hand.
        try:
            init_system_db()
        except Exception:
            logger.exception("Recovery init_system_db() also failed")
        raise HTTPException(
            500,
            f"Move failed after {moved_count} item(s): {exc}. "
            "Some files may already be in the new folder; resolve by hand.",
        )

    # ── Rebind DATASETS_DIR at runtime ────────────────────────────────────
    # owner_info.DATASETS_DIR is a module attribute; mutating it makes every
    # subsequent OwnerInfo() default to the new path. system_db reads
    # owner_info.DATASETS_DIR fresh inside init_system_db, so re-init picks up
    # the new location automatically. Update the env var for the same reason
    # /api/local/info reads it, and a hypothetical re-init would too.
    owner_info.DATASETS_DIR = new_path
    os.environ[local_config.ENV_DATA_DIR] = str(new_path)
    init_system_db()

    _persist_current()
    logger.info("data_dir changed: %s -> %s (%d items)", current, new_path, moved_count)

    return ChangeDataDirResponse(
        ok=True, moved_to=str(new_path), items_moved=moved_count,
    )


@router.get("/trees", response_model=TreeListResponse)
def list_trees() -> TreeListResponse:
    """Every tree under the current data folder, with enough detail for the
    user to tell them apart (row count, size, when it was last touched)."""
    _require_local()
    active = owner_info.DEFAULT_OWNER_ID

    names = owner_info.list_owners()
    if active not in names:
        names.append(active)

    share_links = _share_link_counts()
    return TreeListResponse(
        active=active,
        trees=[
            _describe_tree(name, active, share_links.get(name, 0))
            for name in sorted(names, key=str.lower)
        ],
    )


@router.post("/switch-tree", response_model=TreeActionResponse)
def switch_tree(req: TreeNameRequest) -> TreeActionResponse:
    """Open a different tree in the same data folder.

    Cheap next to /change-data-dir: nothing moves on disk. The engine pool is
    keyed by owner id, so the outgoing tree's engine simply stops being asked
    for, and the system DB is per data folder (not per tree) so it is left
    alone. As with /change-data-dir the caller should reload the SPA so React
    Query drops rows cached from the previous tree.
    """
    _require_local()
    name = _validate_tree_name(req.owner_id)

    if name == owner_info.DEFAULT_OWNER_ID:
        raise HTTPException(400, f"'{name}' is already the active tree")
    if not (owner_info.DATASETS_DIR / name).is_dir():
        raise HTTPException(404, f"No tree named '{name}' in the current data folder")

    _activate_tree(name)
    logger.info("tree switched -> %s", name)
    return TreeActionResponse(ok=True, active=name)


@router.post("/create-tree", response_model=TreeActionResponse)
def create_tree(req: TreeNameRequest) -> TreeActionResponse:
    """Create an empty tree under the current data folder and switch to it."""
    _require_local()
    name = _validate_tree_name(req.owner_id)

    # Case-insensitive: NTFS folds "Family" and "family" onto one directory,
    # so accepting both would quietly open one tree under two labels.
    #
    if name.lower() in {existing.lower() for existing in owner_info.list_owners()}:
        raise HTTPException(409, f"A tree named '{name}' already exists")

    _activate_tree(name)
    logger.info("tree created -> %s", name)
    return TreeActionResponse(ok=True, active=name)


@router.post("/delete-tree", response_model=DeleteTreeResponse)
def delete_tree(req: TreeNameRequest) -> DeleteTreeResponse:
    """Permanently delete a tree and everything in it.

    Irreversible - the folder is removed outright, not sent to the Recycle
    Bin. Refusing to delete the open tree is what makes that safe to expose:
    there is always exactly one active tree, so the last remaining tree can
    never be deleted, and the process is never left pointing at a folder that
    no longer exists.

    Also drops the tree's rows from system.sqlite. Without that a share link
    outlives the data it pointed at, and because OwnerInfo recreates missing
    directories the next request to resolve it silently rebuilds the tree as an
    empty folder instead of failing - so the "deleted" tree comes back.
    """
    _require_local()
    name = _validate_tree_name(req.owner_id)

    if name == owner_info.DEFAULT_OWNER_ID:
        raise HTTPException(
            400, f"'{name}' is the tree you have open. Open a different one first."
        )

    tree_dir = owner_info.DATASETS_DIR / name
    if not tree_dir.is_dir():
        raise HTTPException(404, f"No tree named '{name}' in the current data folder")

    # Drop the tree's engine first: a pooled SQLAlchemy connection keeps
    # data.sqlite open, and Windows refuses to remove a file that is.
    #
    db.reload_owner(name)
    try:
        _retry_on_lock(lambda: shutil.rmtree(tree_dir))
    except OSError as exc:
        logger.exception("delete failed for tree %s", name)
        raise HTTPException(500, f"Could not delete '{name}': {exc}")

    # After the rmtree, not before: the removal is the step that can fail on a
    # Windows lock, and purging first would strand a live tree with no share
    # links or contributor grants.
    #
    purged = _purge_tree_rows(name)

    logger.info("tree deleted -> %s (system rows purged: %s)", name, purged or "none")
    return DeleteTreeResponse(
        ok=True,
        deleted=name,
        remaining=len(owner_info.list_owners()),
        purged=purged,
    )


@router.post("/identity", response_model=LocalAppInfo)
def set_identity(req: IdentityRequest) -> LocalAppInfo:
    """Set who is recorded as adding records.

    Only affects rows written from now on: `created_by` is stamped at insert
    time and is deliberately not rewritten here, because that would silently
    reattribute history the user did not author under the new name.
    """
    _require_local()
    editor_id = _validate_editor_id(req.editor_id)
    display_name = req.display_name.strip() or editor_id

    owner_info.EDITOR_ID = editor_id
    owner_info.EDITOR_DISPLAY_NAME = display_name
    os.environ[local_config.ENV_EDITOR_ID] = editor_id
    os.environ[local_config.ENV_EDITOR_DISPLAY_NAME] = display_name
    _persist_current()

    logger.info("identity set -> %s (%s)", editor_id, display_name)
    return local_info()


@router.post("/save-as")
async def save_as(
    request: Request,
    suggested_filename: str = Query(..., min_length=1, max_length=255),
) -> dict:
    """Open a native SaveAs dialog and write the request body bytes to the
    chosen path. Used by the SPA's export flow because pywebview/WebView2
    don't reliably show a SaveAs dialog for `<a download>` clicks — the file
    just disappears into a default Downloads folder (or nowhere).

    The frontend POSTs the binary as the raw body; the suggested name comes
    in via query string so we don't have to fight multipart parsing.
    """
    _require_local()
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(500, f"pywebview not available: {exc}")

    if not webview.windows:
        raise HTTPException(503, "No window available for the save dialog")

    body = await request.body()
    if not body:
        raise HTTPException(400, "Empty body — nothing to save")

    try:
        result = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_filename,
        )
    except Exception as exc:
        raise HTTPException(500, f"Save dialog failed: {exc}")

    # pywebview returns either a string (single chosen path) or None if the
    # user cancelled. Some platform backends wrap it in a tuple; handle both.
    if not result:
        return {"saved": False, "path": None}
    target_str = result[0] if isinstance(result, (list, tuple)) else result

    target = Path(target_str)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    logger.info("save-as wrote %d bytes to %s", len(body), target)

    return {"saved": True, "path": str(target)}


@router.post("/open-in-explorer")
def open_in_explorer(req: OpenInExplorerRequest) -> dict:
    """Open Windows Explorer at the given path.

    - If `path` is an existing file, Explorer opens with the file selected.
    - If `path` is an existing directory, Explorer opens that directory.
    - Anything else → 400.
    """
    _require_local()
    target = Path(req.path).expanduser().resolve()

    if target.is_file():
        cmd = ["explorer", "/select,", str(target)]
    elif target.is_dir():
        cmd = ["explorer", str(target)]
    else:
        raise HTTPException(400, f"Path does not exist or is unreadable: {target}")

    try:
        # Note: explorer.exe returns exit code 1 on success (legacy Windows
        # behaviour). Don't check the return code — just fire and forget.
        subprocess.Popen(cmd, close_fds=True)
    except Exception as exc:
        raise HTTPException(500, f"Failed to launch Explorer: {exc}")

    return {"ok": True}


@router.post("/open-with-default")
def open_with_default(req: OpenWithDefaultRequest) -> dict:
    """Open `path` with the OS-registered default program (the same thing
    Windows does on a double-click). Folders open in File Explorer; .log
    opens in Notepad; .json in whatever the user has set, etc."""
    _require_local()
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(400, f"Path does not exist: {target}")

    try:
        # os.startfile is Windows-only. It calls ShellExecute under the
        # hood and is the canonical "double-click this for me" primitive.
        os.startfile(str(target))  # type: ignore[attr-defined]
    except AttributeError:
        # Non-Windows fallback (only relevant when running from source on
        # Linux/macOS — the packaged installer is Windows-only).
        opener = "xdg-open" if sys.platform.startswith("linux") else "open"
        subprocess.Popen([opener, str(target)], close_fds=True)
    except Exception as exc:
        raise HTTPException(500, f"Failed to open: {exc}")

    return {"ok": True}


# ── helpers ───────────────────────────────────────────────────────────────

def _retry_on_lock(action: Callable[[], None], attempts: int = 5, delay: float = 0.3) -> None:
    """Run `action`, retrying while Windows reports the target as locked.

    Antivirus can hold a file open for a fraction of a second after we close
    it; without the retry we'd surface that transient lock as a hard failure.
    Shared by the move (change-data-dir) and delete (delete-tree) paths.
    """
    last_exc: Optional[Exception] = None
    for _ in range(attempts):
        try:
            action()
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc


def _move_with_retry(src: Path, dst: Path) -> None:
    _retry_on_lock(lambda: shutil.move(str(src), str(dst)))


# Tree ids double as directory names under the data root, so the accepted
# charset is the intersection of "readable label" and "safe on NTFS": no path
# separators, no leading dot (which would hide the folder and make
# list_owners skip it), and none of the DOS device names Windows still
# refuses to create a directory for.
#
_TREE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")

# Mirrors the sanitising in auth._derive_editor_id (local part of the
# registration email, [A-Za-z0-9_-], capped at 32).
#
_EDITOR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_RESERVED_TREE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _validate_tree_name(name: str) -> str:
    cleaned = name.strip()
    if not _TREE_NAME_RE.match(cleaned):
        raise HTTPException(
            400,
            "A tree name must be 1-64 characters, start with a letter or digit, "
            "and use only letters, digits, spaces, hyphens and underscores.",
        )
    if cleaned.upper() in _RESERVED_TREE_NAMES:
        raise HTTPException(400, f"'{cleaned}' is a name Windows reserves for devices.")
    return cleaned


# Tables whose rows are scoped to a single tree, with the column naming it.
# Deleting a tree drops these because each is a pointer to data that no longer
# exists; a share token is the one that matters in practice, since it stays
# resolvable and would rebuild the tree as an empty folder.
#
# Two tree-referencing tables are deliberately absent:
#   AuthEditor     - an identity, not tree data. A data folder shared with a
#                    web install must not lose its login because a local tree
#                    was deleted.
#   PrivacyRequest - a compliance record with its own retention window
#                    (PRIVACY_DESIGN.md section 6). Purging it early would
#                    breach the policy the rest of this codebase enforces.
#
_TREE_SCOPED_ROWS = (
    (system_models.AuthShareToken, "owner_id"),
    (system_models.AuthShareConsent, "tree_owner_id"),
    (system_models.AuthEditorTree, "owner_id"),
    (system_models.AuthInvitation, "owner_id"),
    (system_models.AuthPendingContributor, "owner_id"),
    (system_models.AuthSetPasswordToken, "owner_id"),
)


def _purge_tree_rows(name: str) -> dict[str, int]:
    """Delete every system-DB row scoped to tree `name`.

    Returns table name -> rows removed, for logging and so the UI can say what
    went with the tree. Tables that had nothing are omitted.
    """
    session = get_system_session()
    try:
        removed: dict[str, int] = {}
        for model, column in _TREE_SCOPED_ROWS:
            count = session.query(model).filter(
                getattr(model, column) == name
            ).delete(synchronize_session=False)
            if count:
                removed[model.__tablename__] = count
        session.commit()
        return removed
    finally:
        session.close()


def _share_link_counts() -> dict[str, int]:
    """Share tokens per tree, in one query rather than one per listed tree."""
    session = get_system_session()
    try:
        rows = session.query(
            system_models.AuthShareToken.owner_id, func.count()
        ).group_by(system_models.AuthShareToken.owner_id).all()
        return {owner_id: count for owner_id, count in rows}
    finally:
        session.close()


def _validate_editor_id(value: str) -> str:
    """Same charset auth._derive_editor_id produces from a registration email,
    so an id copied from a hosted account is accepted verbatim and rows written
    offline carry the identical created_by."""
    cleaned = value.strip()
    if not _EDITOR_ID_RE.match(cleaned):
        raise HTTPException(
            400,
            "An editor id must be 1-32 characters and use only letters, digits, "
            "hyphens and underscores.",
        )
    return cleaned


def _persist_current() -> None:
    """Write the whole config from live module state. The data folder, the
    active tree and the editor identity are each changed by a different
    endpoint; rebuilding all of them from the globals is what stops a change
    to one from dropping another."""
    local_config.save(
        local_config.LocalConfig(
            data_dir=owner_info.DATASETS_DIR,
            owner_id=owner_info.DEFAULT_OWNER_ID,
            editor_id=owner_info.EDITOR_ID,
            display_name=owner_info.EDITOR_DISPLAY_NAME,
        )
    )


def _activate_tree(name: str) -> None:
    """Rebind the process to tree `name`, creating it if it does not exist.

    Mirrors the rebinding half of /change-data-dir: mutate the module global
    that every later OwnerInfo() reads, keep the env var in step for anything
    that re-reads it, then persist. get_engine() does the on-disk half --
    OwnerInfo creates <data dir>/<name>/media and the engine applies the
    schema plus lookup tables, so a brand-new tree is usable on return rather
    than half-built on the first request.
    """
    owner_info.DEFAULT_OWNER_ID = name
    os.environ[local_config.ENV_DEFAULT_OWNER_ID] = name
    db.get_engine(name)
    _persist_current()


def _describe_tree(name: str, active: str, share_links: int) -> TreeInfo:
    tree_dir = owner_info.DATASETS_DIR / name

    size = 0
    newest = 0.0
    if tree_dir.is_dir():
        for path in tree_dir.rglob("*"):
            if path.is_file():
                stat = path.stat()
                size += stat.st_size
                newest = max(newest, stat.st_mtime)

    return TreeInfo(
        owner_id=name,
        is_active=name == active,
        individuals=_count_individuals(tree_dir / "data.sqlite"),
        size_bytes=size,
        share_links=share_links,
        modified_at=(
            datetime.fromtimestamp(newest, tz=timezone.utc).isoformat()
            if newest
            else None
        ),
    )


def _count_individuals(db_file: Path) -> Optional[int]:
    """Row count read straight through sqlite3 in read-only mode.

    Deliberately not via SQLAlchemy: listing trees would otherwise put an
    engine in the pool for every tree the user is merely looking at, and would
    create the schema in trees they never open. A missing or corrupt file
    degrades to None ("unknown") instead of failing the whole listing.
    """
    if not db_file.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return conn.execute("SELECT COUNT(*) FROM main_individuals").fetchone()[0]
    except sqlite3.Error:
        return None
    finally:
        conn.close()
