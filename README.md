# NovoTree — Collaborative genealogy tree

*Last updated: 2026-06-28*

Build and browse a family tree: individuals, relationships, dates, places, photos,
and notes, with GEDCOM import/export and privacy controls designed around GDPR.

NovoTree ships in two forms from the same codebase:

- **Windows desktop application** — runs entirely on your own machine. No account, no
  server, no internet after install. Your tree never leaves your computer.
- **Hosted SaaS** at [novospace.cz/novotree](https://novospace.cz/novotree) — multi-user,
  invite contributors, share view-only links.

[![GitHub release](https://img.shields.io/github/v/release/ketafoto/novotree)](https://github.com/ketafoto/novotree/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Support

If you find NovoTree useful, please consider supporting its development:

[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-%E2%99%A5-db61a2?logo=github)](https://github.com/sponsors/ketafoto)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/ketafoto)

*The desktop application stays fully offline — nothing leaves your machine through the app.
The badges above link to GitHub Sponsors and Ko-fi; clicking them opens those services
in your browser, where their respective privacy policies apply to the donation transaction.*

---

## Desktop application vs hosted SaaS

|                  | Hosted SaaS (`novospace.cz`)                       | Desktop application                                   |
| ---------------- | -------------------------------------------------- | ----------------------------------------------------- |
| Data location    | SQLite DB on an EU VM                              | A folder you choose on your own PC                    |
| Privacy          | Owner controls visibility; admin can see all data  | Only you can see anything                             |
| Internet         | Required                                           | Not required (after install)                          |
| Account / login  | Email + password; share links for viewers          | None — single user, no auth screen                    |
| Collaboration    | Invite contributors, share view-only links         | Single user only                                      |
| Updates          | Automatic                                          | Manual — install a new version to upgrade             |
| Backups          | Daily server snapshot, 30-day retention            | You choose — easiest is a OneDrive/iCloud/Dropbox folder |

**Privacy is the main reason to choose the desktop application.** Genealogy records
frequently contain sensitive information (adoptions, illnesses, identity documents);
the desktop application lets you build the same tree without uploading any of it.

See [docs/features/LOCAL_APP.md](docs/features/LOCAL_APP.md) for the full desktop-app guide.

---

## Windows — Installer

1. Download `novotree-X.Y.Z-setup.exe` from the [releases page](https://github.com/ketafoto/novotree/releases) and run it.
2. Follow the installer wizard — **no administrator rights required** (it installs to
   `%LocalAppData%\Programs\NovoTree`).
   - A **desktop shortcut** is created by default (uncheck if not wanted).
   - A **Start Menu entry** is always created.
3. On first launch, NovoTree asks **where to store your tree data**. Pick anywhere —
   Documents, an external drive, or a OneDrive/iCloud/Dropbox folder for automatic
   cloud backup. The choice is remembered; later launches skip the dialog.
4. To **quit**: close the NovoTree window — the background server shuts down automatically.

> The `.exe` is unsigned, so Windows SmartScreen may warn on first run
> (*More info -> Run anyway*). System requirements: Windows 10 or 11 (any edition);
> the WebView2 runtime ships with Windows since ~2021, so no separate download is needed.

To **change** where data lives later: Settings -> Locations -> **Change...** opens a
native folder picker, moves your data, and restarts the app.

---

## Development setup

NovoTree is a FastAPI (Python) backend with a React + Vite (TypeScript) frontend.

**Backend (Python 3.11 recommended):**

```powershell
# Windows (PowerShell)
python -m venv venv-win
.\venv-win\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
# Ubuntu / macOS
python3 -m venv venv-linux
source venv-linux/bin/activate
pip install -r requirements.txt
```

**Frontend (Node.js 20+):**

```bash
cd frontend
npm install
npm run dev          # Vite dev server
```

### Run the desktop launcher from source

```powershell
.\venv-win\Scripts\Activate.ps1
cd frontend; npm run build; cd ..      # the SPA must be built for static mounting
python -m backend.local_launcher
```

This starts uvicorn and opens the UI in a native pywebview window — the same path
the packaged `.exe` takes. The launcher logs to
`%LocalAppData%\NovoSpace\NovoTree\novotree.log`.

---

## Building the Windows installer

### 1. Install prerequisites (once)

```powershell
python -m venv venv-win
.\venv-win\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

Plus **Node.js 20+** (for the frontend build) and **Inno Setup 6** — the `--location`
flag is required, otherwise winget installs to an unresolvable path:

```powershell
winget install --id JRSoftware.InnoSetup `
    --location "C:\Program Files\Inno Setup 6" `
    --accept-package-agreements --accept-source-agreements
```

`build.ps1` auto-discovers `C:\Program Files\Inno Setup 6\ISCC.exe` — no PATH changes needed.

### 2. Build

The easiest way — run the build script from the repo root:

```powershell
.\installer\build.ps1
```

This runs the full four-step pipeline:

```powershell
python version.py                       # → installer/version.iss + installer/version_info.txt
cd frontend && npm run build            # → frontend/dist/ (the SPA bundle)
pyinstaller installer\novotree.spec     # → installer/dist/novotree.exe
& "C:\Program Files\Inno Setup 6\ISCC.exe" installer\novotree.iss
# → installer/Output/novotree-X.Y.Z-setup.exe
```

Iteration switches: `-SkipFrontend` (only Python changed), `-SkipFrontend -SkipPyInstaller`
(only the `.iss` changed). See [docs/features/LOCAL_APP.md](docs/features/LOCAL_APP.md)
for the full build reference and troubleshooting.

---

## Cutting a release

1. Bump `__version__` and `__date__` in [version.py](version.py).
2. Add a dated section to [CHANGELOG.md](CHANGELOG.md).
3. Build the installer: `.\installer\build.ps1`.
4. Commit, then tag and push: `git tag desktop-v1.0.0 && git push --tags`.
   The `desktop-` prefix distinguishes desktop-application releases from the
   continuously deployed SaaS.
5. Create a [GitHub Release](https://github.com/ketafoto/novotree/releases) from the
   tag, paste the changelog section as the notes, and upload
   `installer/Output/novotree-X.Y.Z-setup.exe` as the release asset.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) or the [GitHub Releases page](https://github.com/ketafoto/novotree/releases)
for the full version history.

---

## License

[MIT](LICENSE)
