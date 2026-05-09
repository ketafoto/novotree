"""
Local-app endpoints.

  GET  /local/info             — read-only paths (data folder, config, log)
  POST /local/pick-data-dir    — open a native folder picker, return chosen path
  POST /local/change-data-dir  — move data to chosen path, update config & DBs
                                  *at runtime* (no process restart)
  POST /local/open-in-explorer — open Windows Explorer at a given path
  POST /local/open-with-default — open a path with the OS default program
                                  (folder → Explorer; file → registered app
                                  for that extension, e.g. .log → Notepad)
  POST /local/save-as          — open a SaveAs dialog and write request body
                                  to the chosen path (used for downloads —
                                  pywebview/WebView2 doesn't reliably show
                                  a SaveAs dialog for `<a download>` clicks)

All endpoints return 404 in any mode other than `local` — the web/VM
deployment neither has nor needs them.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from backend.config import settings
from database import db
from database import owner_info  # full-module access — DATASETS_DIR is rebindable
from database.system_db import init_system_db, reset_system_db

logger = logging.getLogger("novotree.local")


class LocalAppInfo(BaseModel):
    data_dir: str        # SQLite databases + media — picked by the user on first run
    config_file: str     # %AppData%\NovoSpace\NovoTree\config.json (remembers the data_dir choice)
    log_file: str        # rotating launcher log (max ~6 MB on disk)


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
        # The launcher exports these so we don't have to recompute platformdirs
        # paths here (and risk drifting from the launcher's actual choices).
        config_file=os.environ.get("NOVOTREE_CONFIG_FILE", ""),
        log_file=os.environ.get("NOVOTREE_LOG_FILE", ""),
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
    os.environ["NOVOTREE_DATA_DIR"] = str(new_path)
    init_system_db()

    # ── Persist the new choice ────────────────────────────────────────────
    config_file = os.environ.get("NOVOTREE_CONFIG_FILE", "")
    if not config_file:
        raise HTTPException(500, "NOVOTREE_CONFIG_FILE env var is not set")
    Path(config_file).write_text(
        json.dumps({"data_dir": str(new_path)}, indent=2),
        encoding="utf-8",
    )
    logger.info("data_dir changed: %s -> %s (%d items)", current, new_path, moved_count)

    return ChangeDataDirResponse(
        ok=True, moved_to=str(new_path), items_moved=moved_count,
    )


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

def _move_with_retry(src: Path, dst: Path, attempts: int = 5, delay: float = 0.3) -> None:
    """shutil.move with a small retry loop. On Windows, antivirus can hold
    a file open for a fraction of a second after we close it; without the
    retry we'd surface that transient lock as a hard failure."""
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            shutil.move(str(src), str(dst))
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
