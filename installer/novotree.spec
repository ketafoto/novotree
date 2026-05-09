# novotree.spec — PyInstaller build spec for the NovoTree desktop installer.
#
# Build (from the repo root):
#   pip install -r requirements.txt   (pulls pywebview + platformdirs)
#   pip install pyinstaller
#   cd frontend && npm run build       (produces frontend/dist/)
#   pyinstaller installer\novotree.spec --workpath installer\build --distpath installer\dist
#
# Output: installer/dist/novotree.exe  (--onefile, no console window)
#
# Or run the full pipeline:  .\installer\build.ps1
#
# Notes:
# - This is a --onefile build: the entire bundle is packed into a single
#   `novotree.exe` (~25 MB on Windows). On launch PyInstaller's bootloader
#   extracts the bundle into a temp directory under sys._MEIPASS, runs the
#   app from there, and cleans up on exit. The launcher's _frontend_dist_dir()
#   already handles sys._MEIPASS, so no code changes are needed.
#   Trade-off vs --onedir: every launch pays a ~2-3 second extraction cost
#   on a modern SSD; in exchange, install AND uninstall handle one big file
#   instead of ~10 000 small ones — the uninstall UX difference is dramatic
#   (~1 s vs ~60 s with Windows Defender re-scanning each file).
# - pywebview on Windows uses WebView2 (Edge), pre-installed on Windows 10/11
#   since ~2021. No extra runtime bundling required.
# - The whole frontend/dist/ tree is shipped as data, mounted by the launcher
#   as StaticFiles at "/".
# - database/schema.sql is included for reference / GEDCOM scripts that read
#   it directly; the runtime tables come from SQLAlchemy models.
# - All source paths are derived from SPECPATH (the directory containing this
#   spec file), so the spec is location-independent — moving installer/ would
#   not require any path edits here.

import os as _os
import sys as _sys

# SPECPATH = installer/  →  PROJECT_ROOT = repo root
PROJECT_ROOT = _os.path.dirname(SPECPATH)
_sys.path.insert(0, PROJECT_ROOT)
from version import __version__  # noqa: E402, F401  (imported for build-time validation)

from PyInstaller.utils.hooks import collect_all, collect_submodules


def _root(*parts: str) -> str:
    """Absolute path under the repo root."""
    return _os.path.join(PROJECT_ROOT, *parts)


block_cipher = None

# ── Collect data + binaries for packages with non-Python assets ──────────────
wv_datas,  wv_binaries,  wv_hidden  = collect_all("webview")

a = Analysis(
    [_root("backend", "local_launcher.py")],
    pathex=[PROJECT_ROOT],
    binaries=wv_binaries,
    datas=[
        # SPA bundle — served at "/" by the launcher
        (_root("frontend", "dist"),         "frontend/dist"),
        # Schema reference (used by import/export tools)
        (_root("database", "schema.sql"),   "database"),
        # Branding + version source
        (_root("installer", "novotree.ico"), "."),
        (_root("version.py"),                "."),
    ] + wv_datas,
    hiddenimports=[
        # pywebview Windows backend
        "webview.platforms.winforms",
        # FastAPI / Starlette internals occasionally missed by static analysis
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # Auth/crypto stack
        "bcrypt",
        "jose",
        "jose.backends.cryptography_backend",
        # Email (used only when SMTP is configured — not in local mode, but
        # imported unconditionally by backend.api.auth)
        "aiosmtplib",
        # Misc
        "platformdirs",
    ] + wv_hidden
      # Pull every backend / database submodule so dynamic FastAPI routing works
      + collect_submodules("backend")
      + collect_submodules("database"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim bundle — never imported at runtime
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "sphinx",
        "pandas",
        "numpy.testing",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile EXE: binaries + zipfiles + datas are packed INTO the exe instead
# of being collected to a sibling _internal/ directory. This is the change
# that produces a single-file bundle. (For onedir, exclude_binaries=True and
# a separate COLLECT() block is used; we don't want that here.)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="novotree",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,     # default temp dir (cleaned on exit)
    console=False,           # no black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=_root("installer", "version_info.txt"),  # generated by:  python version.py
    icon=_root("installer", "novotree.ico"),
)
