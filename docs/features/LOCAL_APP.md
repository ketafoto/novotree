# NovoTree — Local App

The **local app** is the same NovoTree codebase shipped as a Windows installer
that runs entirely on your own machine. No account, no server, no internet
connection required after install.

This document has two parts:

- [**For users**](#for-users) — what the local app gives you, where your data
  lives, how to install / move data / uninstall, and how it differs from the
  hosted SaaS at novospace.cz.
- [**For developers**](#for-developers) — how the installer is built, what
  files do what, and how to ship a new version.

---

## For users

### Local app vs SaaS — what's different

|                      | Hosted SaaS (`novospace.cz`)                             | Local app                                                |
| -------------------- | -------------------------------------------------------- | -------------------------------------------------------- |
| Data location        | Single SQLite DB on a Hetzner VM (EU)                    | A folder you choose on your own PC                       |
| Privacy              | Owner controls visibility; admin can see all data        | Only you can see anything                                |
| Internet             | Required                                                 | Not required (after install)                             |
| Account / login      | Email + password; share links for viewers                | None — single user, no auth screen                       |
| Collaboration        | Owner can invite contributors and share view-only links  | Single user only                                         |
| Updates              | Automatic (you always run the latest)                    | Manual — install a new version when you want to upgrade  |
| Backups              | Daily server snapshot, 30-day retention                  | You choose — easiest is to put the data folder in        |
|                      |                                                          | OneDrive/iCloud/Dropbox or copy it manually              |
| Cost                 | Free during development                                  | Free                                                     |

**The privacy difference is the main reason to use the local app.** Your tree
— including names, dates, photos, notes about living relatives — never leaves
your computer. Genealogy records frequently contain sensitive information
(adoptions, illnesses, identity documents) that some users prefer not to
upload anywhere. The local app lets you build the same tree without making
that tradeoff.

### Installation

1. Download `novotree-X.Y.Z-setup.exe`.
2. Double-click. **No admin rights are required** — the installer goes into
   `%LocalAppData%\Programs\NovoTree`.
3. On first launch, NovoTree asks **where to store your tree data**. Pick
   anywhere — Documents, an external drive, or a OneDrive/iCloud/Dropbox
   folder if you want automatic cloud backup.
4. The choice is remembered. Subsequent launches skip the dialog.

System requirements:

- Windows 10 or 11 (any edition)
- ~35 MB free disk for the app (a single `novotree.exe`), plus space for your tree (typically tens of MB)
- WebView2 runtime — pre-installed on Windows since ~2021, no separate download

Startup is a touch slower than a "normal" Windows app — the first launch in a session takes 2–3 s while Windows extracts the embedded Python runtime and the SPA bundle to a temp folder. After that, the app responds instantly. Closing and reopening within the same session also costs ~2 s. This is the deliberate trade-off for an instantly-uninstallable single-file bundle (uninstall takes ~3 s instead of ~3 minutes); for a tool you open occasionally, it's the right balance.

### Where your data lives

Two folders matter:

| Folder | What's in it | Default location |
| --- | --- | --- |
| **Data folder** | Your tree(s), photos, GEDCOM exports | `<your choice>\local\data.sqlite`, `<your choice>\local\media\…` |
| **Config folder** | The remembered data-folder path, plus a rotating debug log capped at 6 MB total (see below) | `%LocalAppData%\NovoSpace\NovoTree\config.json`, `…\novotree.log` |

The data folder is what you back up. The config folder is small (<1 MB,
mostly the rotating log) and is recreated automatically if deleted.

To **change** where data lives:

1. Quit NovoTree.
2. Move the data folder to its new location.
3. Edit `%LocalAppData%\NovoSpace\NovoTree\config.json` so the `data_dir`
   field points to the new path. Or delete `config.json` to be re-prompted on
   next launch.

A built-in "Move data folder…" UI is on the roadmap but not yet shipped.

### Moving data between local and SaaS

Use the existing **GEDCOM + media export/import** in either direction. The
local app and the hosted SaaS share the same export/import code, so a bundle
exported from one imports cleanly into the other. No special sync protocol —
just an export/import round-trip when you want to move.

### Donations

The local app's header has a small **Donate ♥** button. NovoTree is a
one-person open-source project; the button opens a dialog with **GitHub
Sponsors** and **Ko-fi** links if you'd like to support development. The
links open in your default browser — NovoTree never touches the
transaction.

In the **Mode A** web build a lightweight pink "Donate" link is added to
the privacy-link cluster (*Remove Me / Our Privacy / Donate*), so it appears
in the global footer and in the Tree pages' top bar alongside the takedown
link. It opens the same modal as the local-app heart button. In Modes B
and C the Donate link is deliberately omitted — placement there requires
the §4.1 lawyer review (see
[docs/legal/PRIVACY_DESIGN.md §4.8](../legal/PRIVACY_DESIGN.md) Pattern A
vs. Pattern B for the legal framing).

### Uninstalling

Add/Remove Programs → NovoTree → Uninstall. **Your data folder is not
touched** — uninstall only removes the app itself. If you want a clean slate,
delete the data folder manually after uninstall.

---

## For developers

### Architecture in one paragraph

A `NovoTree.exe` produced by PyInstaller starts a uvicorn-hosted ASGI app on
a random local port (127.0.0.1). The ASGI app is a thin Starlette wrapper:
the existing FastAPI backend is mounted under `/api`, and the bundled Vite
SPA build is served as static files at `/`. A pywebview window (WebView2 on
Windows) opens against that URL. Closing the window terminates the process.
Three env vars switch the same backend between web/dev/local mode without
forking the code.

The bundle is built in PyInstaller `--onefile` mode — everything (Python
runtime, all dependencies, the SPA `dist/`, the SQL schema, the icon)
is packed into a single `novotree.exe` (~30 MB). On launch, PyInstaller's
bootloader extracts the bundle into a temp directory under `sys._MEIPASS`,
runs the app from there, and cleans up on exit. The launcher's
`_frontend_dist_dir()` already handles `sys._MEIPASS`, so no code changes
were needed to switch from `--onedir` to `--onefile`. The reason we chose
`--onefile`: it makes uninstall almost instant (one file vs ~10 000), at
the cost of a 2–3 s extraction on each launch — see the user-facing
"System requirements" section above for the trade-off rationale.

```
┌─────────────────────────  novotree.exe  ────────────────────────┐
│                                                                 │
│   pywebview window  ──────►  http://127.0.0.1:<random>/         │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  Starlette composite (in uvicorn daemon thread)          │  │
│   │                                                          │  │
│   │  Mount("/api", FastAPI app)   ◄── same backend code      │  │
│   │                                   as web/VM deployment   │  │
│   │  Mount("/",   StaticFiles(frontend/dist, html=True))     │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│   SQLite files at <user-chosen data dir>/local/data.sqlite      │
│                   …and …/system.sqlite                          │
└─────────────────────────────────────────────────────────────────┘
```

### App-mode env vars

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOVOTREE_APP_MODE` | `admin` | `admin` = dev bypass, `local` = packaged installer (also bypass), anything else = full multi-user auth (web/VM). |
| `NOVOTREE_DATA_DIR` | `<repo>/datasets` | Override the SQLite + media root. Set by the launcher to the user's chosen folder. |
| `NOVOTREE_DEFAULT_OWNER_ID` | `aktiniya` | Owner id used in bypass mode. Launcher pins this to `local`. |
| `VITE_NOVOTREE_APP_MODE` | `admin` | **Build-time** variable — bakes "show login screen" into the SPA bundle. The local installer build pins it to `admin`; the VM deployment sets it to a non-`admin` value to render the login. |
| `VITE_NOVOTREE_INSTALLER` | unset | **Build-time** variable — set to `"true"` only by `installer/build.ps1`. Reveals desktop-app-only UI (Donate ♥ in the header, future "Move data folder…" dialog). Read in the SPA via `isLocalApp` from `src/config/appMode.ts`. |

The web/VM deployment leaves the runtime env vars unset (so the auth path
runs as it does today). The local installer's launcher sets all three at
process start, before importing the FastAPI app — this matters because
`backend.config.settings` snapshots them at module-load time.

See also [DEPLOYMENT.md](DEPLOYMENT.md) for the full env reference used on
the VM.

### File map

Everything specific to the local installer, in load-bearing order:

| Path | What it does |
| --- | --- |
| `version.py` | Single source of truth for `__version__`. Run with `python version.py` to regenerate `installer/version.iss` and `installer/version_info.txt`. |
| `backend/local_launcher.py` | Desktop entrypoint. Resolves the data folder (first-run picker if needed), sets the three env vars, builds the Starlette composite, runs uvicorn in a daemon thread, opens the pywebview window, shuts down on close. |
| `installer/build.ps1` | Build orchestrator (4 steps). Run from the repo root: `.\installer\build.ps1`. Switches: `-SkipFrontend`, `-SkipPyInstaller`. |
| `installer/novotree.spec` | PyInstaller spec. Location-independent — paths derive from `SPECPATH`, so the spec can move without breaking. |
| `installer/novotree.iss` | Inno Setup 6 script. Produces `installer/Output/novotree-X.Y.Z-setup.exe`. |
| `installer/novotree.ico` | Branding asset. Used for the setup wizard, the .exe, the Start Menu shortcut, and the desktop shortcut. |
| `installer/version.iss` *(generated)* | One-line `#define MyAppVersion "X.Y.Z"`. Regenerated by `version.py`. **Gitignored.** |
| `installer/version_info.txt` *(generated)* | Windows VERSIONINFO resource embedded in the .exe by PyInstaller. **Gitignored.** |
| `installer/build/` *(generated)* | PyInstaller intermediate cache. Kept across builds for speed. **Gitignored.** |
| `installer/dist/` *(generated)* | PyInstaller bundle output. Cleaned after each successful build. **Gitignored.** |
| `installer/Output/` *(generated)* | Final `novotree-X.Y.Z-setup.exe` lands here. The capital `O` is the Inno Setup compiler's default name for its output directory (`OutputDir=Output` in the `.iss`); we keep the convention so the path matches what every Inno Setup tutorial and example uses. **Gitignored.** |

Frontend pieces that are local-only:

| File | Purpose |
| --- | --- |
| `frontend/src/config/appMode.ts` | Exposes `isLocalApp` (true when `VITE_NOVOTREE_INSTALLER=true`). Use this flag to gate any future desktop-only UI. |
| `frontend/src/components/common/DonateButton.tsx` | Heart-button + modal with GitHub Sponsors / Ko-fi links. Imported by `Header.tsx`, rendered conditionally on `isLocalApp`. |
| `frontend/src/api/local.ts` | Typed client for the `/api/local/*` endpoints (`info`, `pickDataDir`, `changeDataDir`). |
| `frontend/src/pages/settings/LocalAppInfoCard.tsx` | Settings-page card showing the data folder, config file and log file paths read-only, with a "Change…" button that opens the native folder picker, moves the data, and restarts the app. |

Other local-only UI choices (all gated by `isLocalApp`, all tree-shaken from the web bundle):

- `Header.tsx`: editor name + Logout button hidden — there's only one synthetic `local` user with no real session, and clicking Logout would land on a non-existent `/login` route.
- `Sidebar.tsx`: User Manager nav item hidden, footer (editor name + Sign out) hidden — same reasoning.
- `App.tsx`: `/individuals/:id` is moved INSIDE `<Layout>`. In the web build it lives outside Layout so share-link viewers can see an individual without the editor sidebar; in local mode there are no viewers ever, and the move is what gives the page its Header (and Donate ♥).
- `SettingsPage.tsx`: renders `<LocalAppInfoCard />` at the top of the page in local mode only.

Backend changes that the local mode relies on:

| File | Change |
| --- | --- |
| `backend/config.py` | `is_dev` now true for both `admin` and `local` modes; new `is_local` property. |
| `database/owner_info.py` | `DATASETS_DIR` and `DEFAULT_OWNER_ID` honor the env vars above. |
| `database/system_db.py` | Imports `DATASETS_DIR` from `owner_info` instead of redefining its own copy of the path — single source of truth. |
| `backend/api/auth.py` | Imports `DEFAULT_OWNER_ID` from `owner_info` instead of hardcoding `"aktiniya"` here too — single source of truth. |

### Build prerequisites (one-time setup)

You only need this if you're producing a new installer.

1. **Python venv** at `venv-win/` (the script looks for it by absolute path):
   ```powershell
   python -m venv venv-win
   .\venv-win\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install pyinstaller
   ```
   You only need to **activate** the venv for that one-time `pip install`. Day-to-day, `build.ps1` invokes the venv's `python.exe` directly via absolute path — no activation needed. The Microsoft Store Python works, but its MSIX virtualization redirects writes under `%LocalAppData%\Packages\…`, which makes dev-mode launcher testing confusing — prefer python.org Python if you can.
2. **Node.js 20+** — for `npm run build` (Vite). `winget install OpenJS.NodeJS.LTS` if missing.
3. **Inno Setup 6** — pin to a known location so `build.ps1` can find it:
   ```powershell
   winget install --id JRSoftware.InnoSetup `
       --location "C:\Program Files\Inno Setup 6" `
       --accept-package-agreements --accept-source-agreements
   ```
   `build.ps1` probes `C:\Program Files\Inno Setup 6\` and `C:\Program Files (x86)\Inno Setup 6\` automatically — no `PATH` edits needed.

### Building the installer

From the repo root (any shell — venv activation **not** required; the script
resolves `venv-win\Scripts\python.exe` by absolute path and sets
`PYTHONNOUSERSITE=1` so a stray PyInstaller in the base interpreter's
user-site cannot leak into the bundle):

```powershell
.\installer\build.ps1
```

This runs four steps. Each step's failure stops the pipeline:

1. `python version.py` → regenerate `installer/version.iss` + `installer/version_info.txt`.
2. `npm run build` in `frontend/` (with `VITE_NOVOTREE_APP_MODE=admin` pinned for this command only) → `frontend/dist/`.
3. `pyinstaller installer\novotree.spec --workpath installer\build --distpath installer\dist` → `installer/dist/novotree/novotree.exe`.
4. `iscc installer\novotree.iss` → `installer/Output/novotree-X.Y.Z-setup.exe`.

End result: a single ~25 MB `.exe` you can hand to a user.

#### Switches for faster iteration

Both switches are escape hatches for re-using a previous step's output. They
only save time — they cannot magically make a stale build correct.

| Switch | Skips step | When it's safe to use | What goes into the resulting `.exe` if you misuse it |
| --- | --- | --- | --- |
| `-SkipFrontend` | Step 2 (`npm run build`) | You changed only Python (backend / launcher / spec) and `frontend/dist/` is up-to-date with current frontend source. | The bundled SPA is **whatever was in `frontend/dist/` last time it was built**. If you forgot to rebuild after a frontend change, the `.exe` ships an old UI that may mismatch newer backend APIs. |
| `-SkipPyInstaller` *(implies `-SkipFrontend` is also set in practice)* | Steps 2 + 3 | You're iterating on `installer/novotree.iss` only — tweaking install path, shortcuts, license text, etc. | The `.exe` re-packs whatever is in `installer/dist/novotree/` from the previous run. If Python or frontend changed since then, those changes are NOT in the new `.exe`. |

```powershell
# Iterating on backend Python only — keep the existing SPA bundle
.\installer\build.ps1 -SkipFrontend

# Iterating on the .iss script only — keep the existing PyInstaller output
.\installer\build.ps1 -SkipFrontend -SkipPyInstaller
```

**One gotcha worth knowing:** after a *successful* run, `build.ps1` deletes
`installer/dist/novotree/` (it's just an intermediate, the real artifact is
the `.exe` in `installer/Output/`). So `-SkipPyInstaller` is only useful
*after a failure* in step 4 (Inno Setup), or *between* successful runs if
you reach in and re-run pyinstaller manually. If you've successfully built
and want to re-tweak the `.iss`, you have to re-run pyinstaller too.

**When in doubt, drop the switches and run the full pipeline.** A cold full
build takes ~60 s; the switches save 30–40 s of that. The only time it's
worth optimising is when you're iterating fast on the `.iss`.

### Cutting a new version

1. Edit `__version__` in `version.py` (and `__date__` for the release date).
2. Run `.\installer\build.ps1`.
3. The output filename includes the version: `novotree-1.2.3-setup.exe`.
4. Tag the commit if you ship: `git tag local-v1.2.3 && git push --tags`.

### Running the launcher from source (without packaging)

Useful while developing the launcher itself:

```powershell
.\venv-win\Scripts\Activate.ps1
cd frontend; npm run build; cd ..      # SPA must exist for static mounting
python -m backend.local_launcher
```

The launcher writes its log to `%LocalAppData%\NovoSpace\NovoTree\novotree.log`
— tail that file to debug startup issues. If pywebview's WebView2 backend
fails to initialise, the error lands there.

**Log rotation.** The launcher uses Python's `RotatingFileHandler` with
`maxBytes = 2 MB` and `backupCount = 2`. Once `novotree.log` reaches 2 MB,
it is renamed to `novotree.log.1` (and the previous `.1` becomes `.2`); the
oldest is dropped. So the on-disk total is capped at **3 files × 2 MB ≈
6 MB**, and the log can never grow without bound. The active log level is
`INFO`, which produces a few lines per startup plus access logs on every
HTTP request — a single user typically generates a few KB per session, so
the cap is rarely approached. To change the cap, edit `_setup_logging()` in
`backend/local_launcher.py`.

### Common pitfalls

- **Microsoft Store Python redirects writes.** If `python -m backend.local_launcher` runs but the config + log files seem invisible to other tools, you're hitting MSIX virtualization. Real path: `%LocalAppData%\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\Local\NovoSpace\NovoTree\`. The packaged `novotree.exe` does not have this problem — it runs as a normal Win32 process.
- **Inno Setup not on PATH is fine.** `build.ps1` probes both `Program Files\Inno Setup 6` and `Program Files (x86)\Inno Setup 6`; no PATH munging needed.
- **`config.json` written by Notepad/PowerShell may have a UTF-8 BOM.** The launcher tolerates it (uses `utf-8-sig`), so either is fine.
- **The FastAPI "lifespan" hook does not run automatically when the app is mounted under another app.** A bit of background:
  - **What "lifespan" means here.** FastAPI lets you register code that runs *once when the server starts* and *once when it stops*. That's its "lifespan" — like a `setUp` / `tearDown` for the whole app. NovoTree uses it to call `init_system_db()` (creates `system.sqlite` and its auth tables) before any HTTP request can land.
  - **Why mounting breaks it.** In local mode the launcher does NOT run the FastAPI app directly. It builds a tiny outer Starlette app whose only job is to route URLs:
    ```python
    Starlette(routes=[
        Mount("/api", app=api_app),                             # FastAPI under /api
        Mount("/",   app=StaticFiles(directory=spa_dir)),       # SPA at /
    ])
    ```
    Uvicorn now talks to the OUTER Starlette app. It calls *that* app's lifespan — but Starlette's `Mount` does not forward lifespan events to the apps you mount inside it. The inner FastAPI app never gets its "server is starting" signal, so `init_system_db()` is never called, and the very first request that needs the system DB raises *"System database is not initialized"* (HTTP 500).
  - **What the launcher does about it.** It reaches into the FastAPI app, pulls out its lifespan callable, and hands it to the outer Starlette app as its OWN lifespan:
    ```python
    Starlette(routes=[...], lifespan=api_app.router.lifespan_context)
    ```
    Now uvicorn calls the FastAPI lifespan via the outer app, `init_system_db()` runs at startup, and every request works. If you ever rewrap or swap out the outer app, remember to keep this line — the symptom of forgetting it is "everything looks fine until the first DB-touching request 500s".
- **`backend.config.settings` is loaded once at import time.** All env vars must be set before `from backend.main import app`. The launcher does this in the right order; if you move things around, keep that invariant.
- **`AttributeError: module 'pyimod02_importers' has no attribute 'PyiFrozenImporter'` on first launch of the installed `.exe`.** This is the symptom of an OLD PyInstaller (pre-6.x, when the class was called `PyiFrozenImporter`) sneaking into the bundle alongside the venv's modern PyInstaller (where the class was renamed `PyiFrozenFinder`). The historical cause: the user has a **second, older PyInstaller installed in the Microsoft Store Python's user-site directory** (`%LocalAppData%\Packages\PythonSoftwareFoundation.Python.3.11_…\LocalCache\local-packages\Python311\site-packages\PyInstaller\`), and the build script accidentally picks up *its* `pyinstaller.exe` from PATH instead of the venv's.

  **`build.ps1` is hardened against this** — it pins the interpreter to `$RepoRoot\venv-win\Scripts\python.exe` via an absolute path, runs PyInstaller as `python -m PyInstaller`, and sets `PYTHONNOUSERSITE=1` so even subprocesses ignore the base interpreter's user-site. Two visible signs that the protection is working:
  - The script fails fast with a clear "venv-win not found" error if you haven't created the venv.
  - A successful build produces a `setup.exe` of ≈25 MB. If you ever see a build balloon to ≈40 MB, the protection has been bypassed somehow (perhaps because someone bypassed `build.ps1` and ran `pyinstaller` directly from PATH).

  If you ever do see the symptom anyway, the diagnostic is:
  ```powershell
  & "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe" -m pip show pyinstaller
  ```
  If that prints version info, there's a shadow install. Uninstall it via the base Python (not the venv's):
  ```powershell
  & "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe" -m pip uninstall -y pyinstaller pyinstaller-hooks-contrib
  ```
  Belt-and-suspenders: `build.ps1` already shouldn't pick it up, but removing it eliminates the variable.

- **`AttributeError: 'NoneType' object has no attribute 'isatty'` during startup.** Symptom: a "NovoTree failed to start" dialog with a `ValueError: Unable to configure formatter 'default'` chained onto an `isatty` AttributeError, originating in `uvicorn/logging.py`. Cause: in a PyInstaller `--windowed` build (no console window), the bootloader sets `sys.stdout` and `sys.stderr` to `None` when launched without a parent console (e.g., via Inno Setup's "Run NovoTree" checkbox after install, or just by double-clicking the shortcut). uvicorn's default `ColourizedFormatter` calls `sys.stdout.isatty()` during config and crashes on `None`. The launcher's `_ensure_std_streams()` runs at import time and wires both streams to the log file before anything else touches them — see `backend/local_launcher.py`. If you ever swap log libraries or add a new dependency that does the same `None`-stdio crash, repoint that library at the log file the same way.

  *Why this didn't surface during dev:* launching the bundle from a shell (`./novotree.exe`, bash `&`) inherits stdio from the shell, so `sys.stdout` is a real handle. Only console-less launches (Inno's `[Run]`, double-click, Start Menu) trigger the bug. **Always test the postinstall launch path, not just bash launches.**

- **Uninstall progress bar appears frozen at ~33 %.** Inno Setup's progress bar is keyed on file count, not bytes. With the `--onefile` bundle the install dir holds just three files (`novotree.exe` ~30 MB + `unins000.dat` + `unins000.exe`); deleting the 30 MB `.exe` takes 10–15 s on its own because Windows Defender re-scans it before deletion, but counts as one tick on the bar. Result: bar jumps to 33 %, sits there for ~15 s, jumps to 100 %, "uninstall complete" — users assume the installer is hung and force-kill it. Mitigation in `installer/novotree.iss` `[Code]`: a `CurUninstallStepChanged` handler overrides `UninstallProgressForm.StatusLabel.Caption` so the user sees **why** the wait exists ("Removing NovoTree application files (~30 MB) — Windows Defender re-scans before deletion, this can take 10-15 seconds."). The bar still appears frozen — we deliberately do NOT touch `ProgressBar.Style`. The marquee-style setter is not bridged into Inno Setup's Pascal Script (only `Position`/`Min`/`Max`/`State` are), and assigning to it compiles but raises *"Runtime error: Could not call proc"* at uninstall time. The status text is the available honest UX.

### What this v1 deliberately does NOT include

- Code signing (the `.exe` is unsigned — Windows SmartScreen will warn first-time users).
- Auto-update (manual download + reinstall).
- ~~A built-in "Move data folder…" UI~~ — shipped: Settings → Locations → "Change…" opens a native folder picker, moves the data, and restarts the app.
- macOS / Linux installers (Windows-first).
- Server import/export *sync* — round-tripping is via the existing GEDCOM bundle export/import.
