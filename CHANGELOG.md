# Changelog

All notable changes to the **NovoTree desktop application** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This file tracks the downloadable Windows desktop app (`novotree-X.Y.Z-setup.exe`).
The hosted SaaS at novospace.cz runs continuously from the same codebase and is
not separately versioned here.

---

## [1.0.0] — 2026-06-28

First public release of the desktop application. NovoTree runs entirely on your
own machine: no account, no server, no internet connection required after install.
Your tree -- names, dates, photos, notes about living relatives -- never leaves
your computer.

### Added

**Genealogy tree**
- Build and browse a family tree: add individuals, relationships, dates, places, and notes
- Tree view that auto-fits to the browser window, plus a full-tree overview
- Per-individual edit pages with navigation back to the originating view
- Mobile-friendly layout

**GEDCOM import / export**
- Import existing genealogy data from a GEDCOM file (with media)
- Export your tree as a GEDCOM bundle -- the same format the hosted SaaS uses,
  so you can round-trip data between the desktop app and novospace.cz
- Exact dates parsed to real date values so standalone events bind correctly

**Privacy controls (GDPR-aware)**
- Mark individual data pieces as sensitive; hidden from view by default with a
  one-click "show all" toggle
- Child-data handling: warnings, an owner option to hide children, and a
  background reminder to seek consent when a child turns 16
- Per-individual data export to satisfy right-of-access requests

**Windows desktop application**
- Single self-contained `novotree.exe` (~30 MB) -- no Python or Node install needed
- Inno Setup installer; installs to `%LocalAppData%\Programs\NovoTree` with no admin rights required
- First-run dialog to choose where your tree data is stored (Documents, an external
  drive, or a OneDrive/iCloud/Dropbox folder for automatic cloud backup)
- Settings -> Locations -> "Change..." moves the data folder via a native picker and restarts the app
- Single-user mode: no login screen, no auth -- only you can see anything
- Donate button (GitHub Sponsors / Ko-fi) in the header; links open in your browser, the app never touches the transaction
- Desktop and Start Menu shortcuts (desktop shortcut optional during install)
- Near-instant uninstall; your data folder is preserved across uninstall and reinstall
- Safe upgrade-in-place: installing over an existing version replaces the old program file cleanly in a single pass (no slow separate uninstall step), and a note at setup start confirms the update is safe and leaves your tree data and database untouched

### Known limitations

- The `.exe` is unsigned -- Windows SmartScreen warns first-time users
- No auto-update yet (download and reinstall to upgrade)
- Windows only (no macOS / Linux installer)
- Single user only -- collaboration and share links are SaaS-only features

---

[1.0.0]: https://github.com/ketafoto/novotree/releases/tag/desktop-v1.0.0
