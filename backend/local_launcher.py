"""
local_launcher.py — Desktop entrypoint for the packaged NovoTree app.

Runs only when NOVOTREE_APP_MODE=local (the installer build sets this).
Starts uvicorn in a daemon thread, mounts the bundled SPA as static files,
and shows the UI in a native pywebview window backed by WebView2 (Edge).

First run prompts the user to pick a data folder, and -- only when that
folder already holds trees -- which tree to open; both choices are persisted
to %AppData%\\NovoTree\\config.json so subsequent launches are silent.
Closing the window terminates the entire process - the daemon thread dies
with it, no orphaned server is left running.

Usage (development from source):
    python -m backend.local_launcher

Packaged usage:
    NovoTree.exe   (built via:  installer\\build.ps1)
"""

from __future__ import annotations

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
from typing import Protocol

from backend import local_config

# The config-file schema and the platformdirs paths live in local_config so
# this launcher and backend/api/local.py cannot drift on either.
#
APP_NAME = local_config.APP_NAME
_LOG_FILE = local_config.LOG_FILE


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
    local_config.APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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
    local_config.APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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


# ── First-run pickers ────────────────────────────────────────────────

def _existing_trees(data_dir: Path) -> list[str]:
    """Tree folders already present in `data_dir`.

    Standalone rather than database.owner_info.list_owners() because that
    module snapshots DATASETS_DIR from the environment at import time, and on
    this path the env var is not set yet -- importing it here would freeze the
    wrong root for the rest of the process.
    """
    if not data_dir.is_dir():
        return []
    return sorted(
        (child.name for child in data_dir.iterdir()
         if child.is_dir() and not child.name.startswith(".")),
        key=str.lower,
    )


def _prompt_tree(data_dir: Path) -> str:
    """Ask which tree to open when the chosen folder already holds some.

    A fresh folder holds none, so the ordinary first-run path shows no extra
    dialog and silently uses the default tree name. The dialog appears only
    when the user pointed the picker at a folder with existing data, where
    opening one of several trees unasked would be a guess.
    """
    trees = _existing_trees(data_dir)
    if not trees:
        return local_config.DEFAULT_OWNER_ID

    import tkinter as tk

    chosen = trees[0]

    root = tk.Tk()
    root.title(f"{APP_NAME} - choose tree")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk.Label(
        root,
        text=(
            f"This folder already holds {len(trees)} tree(s):\n{data_dir}\n\n"
            f"Which one should {APP_NAME} open?"
        ),
        justify="left",
    ).pack(anchor="w", padx=16, pady=12)

    listbox = tk.Listbox(root, height=min(len(trees), 10), width=48, exportselection=False)
    for tree in trees:
        listbox.insert(tk.END, tree)
    listbox.selection_set(0)
    listbox.pack(padx=16, fill="x")

    def confirm() -> None:
        nonlocal chosen
        selection = listbox.curselection()
        if selection:
            chosen = trees[selection[0]]
        root.destroy()

    tk.Button(root, text="Open this tree", command=confirm, width=18).pack(pady=12)
    listbox.bind("<Double-Button-1>", lambda _event: confirm())
    # Closing the window accepts the highlighted tree: there is no "no tree"
    # state to fall back to and the app cannot start without one.
    #
    root.protocol("WM_DELETE_WINDOW", confirm)
    root.mainloop()

    return chosen


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


def resolve_startup_config() -> local_config.LocalConfig:
    """Return the data folder and tree to open, prompting on first run."""
    persisted = local_config.load()
    if persisted is not None:
        persisted.data_dir.mkdir(parents=True, exist_ok=True)
        return persisted

    data_dir = _prompt_data_dir(local_config.DEFAULT_DATA_DIR)
    owner_id = _prompt_tree(data_dir)
    # Seed the editor identity from the tree id. For a folder adopted from a
    # web install that is the owner's real editor_id (both derive from the
    # registration email), so records added offline keep the same author as
    # the ones added online. The user can rename it in Settings afterwards.
    #
    config = local_config.LocalConfig(
        data_dir=data_dir, owner_id=owner_id, editor_id=owner_id, display_name=owner_id,
    )
    local_config.save(config)
    return config


# ── Server plumbing ──────────────────────────────────────────────────────────

def _log_extraction_cost() -> None:
    """Log how long the bootloader spent unpacking before Python started.

    Only meaningful in a --onefile build: sys._MEIPASS is created when
    extraction begins, so the gap to now is the blank period the user stares at
    before any of our code can draw anything. Nothing in Python can cover it -
    knowing its size is what decides whether PyInstaller's own Splash() is
    worth adding.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return
    try:
        logging.info(
            "bundle extraction took %.2fs before Python started",
            time.time() - os.path.getctime(bundle),
        )
    except OSError:
        logging.debug("could not read the extraction timestamp", exc_info=True)


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


# ── Startup splash ───────────────────────────────────────────────────────────
# The splash is PyInstaller's, drawn by the bootloader. That is the only place
# it can be: it has to be on screen during bundle extraction, which happens
# before Python exists, and it cannot live inside the WebView because nothing
# renders there until WebView2 has initialised - the end of the wait rather
# than the start of it.
#
# How long to wait for the SPA to report itself loaded before showing the
# window regardless. Only a backstop - the event normally fires in well under a
# second, and showing a not-quite-painted window beats an invisible app.
#
_UI_LOAD_TIMEOUT = 15.0


class _SplashLike(Protocol):
    """What main() needs from a splash, whichever implementation it got."""

    def start(self) -> None: ...
    def set_status(self, text: str) -> None: ...
    def close(self) -> None: ...


class _NoSplash:
    """Stand-in for when there is no bootloader splash to drive.

    Only reachable when running from source (`python -m backend.local_launcher`),
    where PyInstaller is not involved. Startup progress is in novotree.log
    either way, so a source run losing the splash costs nothing - and the
    alternative, a Tk window on a background thread, needs careful teardown to
    avoid aborting the process on exit and existed solely for that path.
    """

    def start(self) -> None:
        """Nothing to draw."""

    def set_status(self, text: str) -> None:
        """Progress is already going to the log."""

    def close(self) -> None:
        """Nothing to close."""


class _BootloaderSplash:
    """Drives PyInstaller's `pyi_splash` through the `_SplashLike` shape.

    The bootloader has already drawn this before Python starts, which is the
    whole point: it is the only thing that can cover bundle extraction. Once
    closed it cannot be reopened, so `close()` is deliberately final.
    """

    def __init__(self, module) -> None:
        self._module = module

    def start(self) -> None:
        """Nothing to do - it has been on screen since the bootloader ran."""

    def set_status(self, text: str) -> None:
        try:
            self._module.update_text(text)
        except Exception:
            logging.debug("splash status update failed", exc_info=True)

    def close(self) -> None:
        try:
            self._module.close()
        except Exception:
            logging.debug("splash close failed", exc_info=True)


def _make_splash() -> _SplashLike:
    """The bootloader's splash when there is one, otherwise a no-op."""
    try:
        import pyi_splash  # noqa: PLC0415  (exists only in a Splash() build)
    except ImportError:
        return _NoSplash()
    return _BootloaderSplash(pyi_splash)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()
    started = time.monotonic()
    logging.info("%s %s starting", APP_NAME, "(packaged)" if hasattr(sys, "_MEIPASS") else "(source)")
    _log_extraction_cost()

    # 1. Splash as early as possible. In a packaged build this is already on
    #    screen (the bootloader drew it during extraction); from source it is a
    #    Tk window that appears within milliseconds.
    splash = _make_splash()
    splash.start()

    # 2. First-run pickers (or load persisted choices). The pickers are modal Tk
    #    dialogs and the splash is a separate always-on-top window, so stand it
    #    down first rather than let it cover them. It cannot be reopened, which
    #    is fine: this happens once, and the user is busy with dialogs anyway.
    if local_config.load() is None:
        splash.close()
    config = resolve_startup_config()
    logging.info(
        "data_dir = %s, tree = %s, editor = %s (%s)",
        config.data_dir, config.owner_id, config.editor_id, config.display_name,
    )

    # 3. Configure backend via env vars BEFORE importing FastAPI app.
    #    backend.config.settings is loaded at import time, so the order matters.
    os.environ[local_config.ENV_APP_MODE] = "local"
    os.environ[local_config.ENV_DATA_DIR] = str(config.data_dir)
    os.environ[local_config.ENV_DEFAULT_OWNER_ID] = config.owner_id
    os.environ[local_config.ENV_EDITOR_ID] = config.editor_id
    os.environ[local_config.ENV_EDITOR_DISPLAY_NAME] = config.display_name

    # 4. Locate the SPA bundle early, so a broken build fails with a dialog
    #    rather than a splash that never advances.
    spa_dir = _frontend_dist_dir()
    if not spa_dir.exists():
        raise RuntimeError(
            f"Frontend bundle not found at {spa_dir}. "
            "Did the installer build skip the Vite step?"
        )

    try:
        # 5. Backend, then the window. Deliberately sequential: measured on this
        #    machine, WebView2 becomes usable in ~0.9s when it has the CPU to
        #    itself but 4-6s when a CPU-bound import is competing for the GIL.
        #    Overlapping the two therefore costs more than it saves, and an
        #    earlier attempt to run them in parallel made startup ~2.5s slower.
        splash.set_status("Loading application...")
        composite = _build_composite_app(spa_dir)
        logging.info("app imported (%.2fs)", time.monotonic() - started)

        splash.set_status("Starting local server...")
        import uvicorn  # noqa: PLC0415

        port = _pick_free_port()
        logging.info("uvicorn binding to 127.0.0.1:%d", port)
        server = uvicorn.Server(uvicorn.Config(
            composite, host="127.0.0.1", port=port,
            log_level="warning", access_log=False,
        ))
        threading.Thread(target=server.run, daemon=True, name="uvicorn").start()
        _wait_until_ready(port)
        logging.info("backend ready (%.2fs)", time.monotonic() - started)

        # 6. Open the window straight at the app URL. Pointing it at the real
        #    page from the start lets WebView2 fold the navigation into its own
        #    initialisation; navigating afterwards costs a second page-load
        #    cycle. The server is already listening, so this cannot race.
        #
        #    webview is imported here (not at module scope) so the WebView2
        #    backend isn't initialised on machines that only run dev unit tests.
        splash.set_status("Opening your tree...")
        import webview  # noqa: PLC0415

        window = webview.create_window(
            APP_NAME,
            f"http://127.0.0.1:{port}/",
            hidden=True,
            width=1400,
            height=900,
            min_size=(900, 600),
            background_color="#ffffff",
        )
        loaded = threading.Event()
        window.events.loaded += lambda *_: loaded.set()

        webview.start(_reveal_when_loaded, (window, splash, started, loaded))
    finally:
        # If anything above raised, the splash would otherwise sit on the user's
        # screen while the error dialog waits behind it.
        splash.close()

    # 7. Window closed - ask uvicorn to drain. The daemon thread dies with the
    #    process anyway, but a clean shutdown lets in-flight DB writes flush.
    logging.info("window closed - shutting down")
    server.should_exit = True


def _reveal_when_loaded(
    window, splash: _SplashLike, started: float, loaded: threading.Event
) -> None:
    """Show the window once the SPA has painted, then drop the splash.

    Runs on the thread pywebview starts after its GUI loop is alive. The window
    is created hidden so a blank white frame never covers the splash while the
    page loads; the timeout is a backstop so a page that never reports `loaded`
    still ends up visible rather than leaving an invisible app.
    """
    try:
        if not loaded.wait(timeout=_UI_LOAD_TIMEOUT):
            logging.warning(
                "SPA did not report 'loaded' within %.0fs - showing anyway",
                _UI_LOAD_TIMEOUT,
            )
        window.show()
        logging.info("UI on screen (%.2fs)", time.monotonic() - started)
    except Exception:
        logging.exception("failed to reveal the window")
    finally:
        splash.close()


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
