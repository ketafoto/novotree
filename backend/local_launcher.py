"""
local_launcher.py — Desktop entrypoint for the packaged NovoTree app.

Runs only when NOVOTREE_APP_MODE=local (the installer build sets this).
Starts uvicorn in a daemon thread, mounts the bundled SPA as static files,
and shows the UI in a native pywebview window backed by WebView2 (Edge).

First run prompts the user to pick a data folder; the choice is persisted
to %AppData%\\NovoTree\\config.json so subsequent launches are silent.
Closing the window terminates the entire process — the daemon thread dies
with it, no orphaned server is left running.

Usage (development from source):
    python -m backend.local_launcher

Packaged usage:
    NovoTree.exe   (built via:  installer\\build.ps1)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

import platformdirs

APP_NAME = "NovoTree"
APP_AUTHOR = "NovoSpace"

# %AppData%\NovoTree on Windows; ~/.config/NovoTree on Linux.
APP_CONFIG_DIR = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"

# Suggested default data dir, but the user can pick anywhere.
DEFAULT_DATA_DIR = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)) / "datasets"

# Log file always lives next to the config (small, one place to look).
_LOG_FILE = APP_CONFIG_DIR / "novotree.log"


# ── stdio sanity (runs at import, before anything else needs it) ──────────────
# In a PyInstaller --windowed build (console=False), the bootloader sets
# sys.stdout / sys.stderr to None when there's no parent console. Any library
# that introspects them then crashes — uvicorn's default ColourizedFormatter
# calls sys.stdout.isatty() during logging config, which raises
# `AttributeError: 'NoneType' object has no attribute 'isatty'` and prevents
# the app from booting at all when launched by Inno Setup's "Run" checkbox
# (or any other console-less parent).
#
# Wire both streams to the log file so libraries can introspect AND write to
# them. When running from source, sys.stdout / sys.stderr are normal terminal
# handles and this is a no-op.
def _ensure_std_streams() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        sink = open(_LOG_FILE, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = sink
        if sys.stderr is None:
            sys.stderr = sink
    except OSError:
        # Last-ditch fallback: an in-memory text stream that has .isatty()
        # and won't raise on writes.
        import io as _io
        if sys.stdout is None:
            sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = _io.TextIOWrapper(_io.BytesIO(), encoding="utf-8")


_ensure_std_streams()


# ── Logging ───────────────────────────────────────────────────────────────────
# Route the `logging` module's output to a rotating file in APP_CONFIG_DIR so
# crashes are debuggable. Stdio itself was already wired by _ensure_std_streams
# above, so we don't touch sys.stderr here.

def _setup_logging() -> Path:
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(_LOG_FILE), maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return _LOG_FILE


# ── First-run data-dir picker ────────────────────────────────────────────────

def _load_persisted_data_dir() -> Path | None:
    if not APP_CONFIG_FILE.exists():
        return None
    try:
        # utf-8-sig tolerates a BOM if a Windows tool (PowerShell Out-File,
        # Notepad) writes the config; plain utf-8 would reject it.
        cfg = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8-sig"))
        path = cfg.get("data_dir")
        return Path(path).expanduser() if path else None
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("config.json unreadable (%s) — re-prompting", exc)
        return None


def _persist_data_dir(path: Path) -> None:
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_FILE.write_text(
        json.dumps({"data_dir": str(path)}, indent=2),
        encoding="utf-8",
    )


def _prompt_data_dir(default: Path) -> Path:
    """Show a tkinter folder picker. Falls back to the default if the user cancels."""
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showinfo(
        f"{APP_NAME} — choose data folder",
        f"Welcome to {APP_NAME}!\n\n"
        "Pick where your tree data should be stored.\n\n"
        f"Default: {default}\n\n"
        "Tip: use a OneDrive / Documents / external-drive folder if you "
        "want automatic cloud backup of your tree.",
    )
    chosen = filedialog.askdirectory(
        title=f"Choose {APP_NAME} data folder",
        initialdir=str(default.parent if not default.exists() else default),
        mustexist=False,
    )
    root.destroy()

    result = Path(chosen) if chosen else default
    result.mkdir(parents=True, exist_ok=True)
    return result


def resolve_data_dir() -> Path:
    """Return the user's data dir, prompting on first run."""
    persisted = _load_persisted_data_dir()
    if persisted is not None:
        persisted.mkdir(parents=True, exist_ok=True)
        return persisted

    chosen = _prompt_data_dir(DEFAULT_DATA_DIR)
    _persist_data_dir(chosen)
    return chosen


# ── Server plumbing ──────────────────────────────────────────────────────────

def _pick_free_port() -> int:
    """Bind to port 0 and let the OS hand back a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _frontend_dist_dir() -> Path:
    """Locate frontend/dist whether running from source OR a PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend" / "dist"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _build_composite_app(spa_dir: Path):
    """Compose: FastAPI under /api, SPA static files at /.

    Mirrors the production layout (where Caddy proxies /api/* to backend and
    serves the SPA bundle directly). Doing it in-process here means the
    bundled exe needs only one port and one process.

    Starlette's Mount does NOT propagate the inner app's lifespan, so we
    forward FastAPI's lifespan_context explicitly — without it, init_system_db
    never runs and every endpoint using get_system_db raises 500.
    """
    from starlette.applications import Starlette
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles

    # Defer the FastAPI import until env vars are set — settings() snapshots
    # NOVOTREE_APP_MODE etc. at module import time.
    from backend.main import app as api_app

    class SPAStaticFiles(StaticFiles):
        """StaticFiles + SPA fallback. Any non-/api path that doesn't match a
        real file in dist/ serves index.html instead of 404. Required because
        the React app uses BrowserRouter — deep links like /settings and
        /individuals/123 only exist in the browser; in-app navigation works
        fine because React Router intercepts client-side, but
        window.location.reload() (used after the "Move data folder" runtime
        config swap) hits the server at the current URL and 404s."""
        async def get_response(self, path, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code == 404:
                    return await super().get_response("index.html", scope)
                raise

    return Starlette(
        routes=[
            Mount("/api", app=api_app),
            Mount("/", app=SPAStaticFiles(directory=str(spa_dir), html=True)),
        ],
        lifespan=api_app.router.lifespan_context,
    )


def _wait_until_ready(port: int, timeout: float = 20.0) -> None:
    """Poll the health endpoint until uvicorn is serving or timeout."""
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(
        f"Backend did not become ready within {timeout}s — see {_LOG_FILE}"
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()
    logging.info("%s %s starting", APP_NAME, "(packaged)" if hasattr(sys, "_MEIPASS") else "(source)")

    # 1. First-run picker (or load persisted choice).
    data_dir = resolve_data_dir()
    logging.info("data_dir = %s", data_dir)

    # 2. Configure backend via env vars BEFORE importing FastAPI app.
    #    backend.config.settings is loaded at import time, so the order matters.
    os.environ["NOVOTREE_APP_MODE"] = "local"
    os.environ["NOVOTREE_DATA_DIR"] = str(data_dir)
    os.environ["NOVOTREE_DEFAULT_OWNER_ID"] = "local"
    # Surfaced read-only by the /api/local/info endpoint so the SPA's Settings
    # page can show the user where their data lives without recomputing paths.
    os.environ["NOVOTREE_CONFIG_FILE"] = str(APP_CONFIG_FILE)
    os.environ["NOVOTREE_LOG_FILE"] = str(_LOG_FILE)

    # 3. Compose ASGI app (API + static SPA).
    spa_dir = _frontend_dist_dir()
    if not spa_dir.exists():
        raise RuntimeError(
            f"Frontend bundle not found at {spa_dir}. "
            "Did the installer build skip the Vite step?"
        )
    composite = _build_composite_app(spa_dir)

    # 4. Start uvicorn in a daemon thread on a random free port.
    import uvicorn

    port = _pick_free_port()
    logging.info("uvicorn binding to 127.0.0.1:%d", port)
    config = uvicorn.Config(
        composite, host="127.0.0.1", port=port,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True, name="uvicorn").start()
    _wait_until_ready(port)
    logging.info("backend ready")

    # 5. Open the native window. webview.start() blocks until the window is closed.
    #    Imported here (not at top) so the WebView2 backend isn't initialised on
    #    machines that only run dev unit tests.
    import webview  # noqa: PLC0415

    webview.create_window(
        APP_NAME,
        f"http://127.0.0.1:{port}/",
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    webview.start()

    # 6. Window closed — ask uvicorn to drain. Daemon thread will be killed
    #    on process exit anyway, but a clean shutdown lets in-flight DB writes
    #    flush.
    logging.info("window closed — shutting down")
    server.should_exit = True


if __name__ == "__main__":
    try:
        main()
    except Exception:
        msg = traceback.format_exc()
        logging.critical("fatal startup error:\n%s", msg)
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                f"{APP_NAME} — startup error",
                f"{APP_NAME} failed to start.\n\nLog: {_LOG_FILE}\n\n{msg}",
            )
        except Exception:
            pass
        sys.exit(1)
