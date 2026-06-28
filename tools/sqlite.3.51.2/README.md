# SQLite command-line tools (v3.51.2, Windows x64)

Official precompiled SQLite tools, vendored here so they travel with the repo --
no per-machine reinstall when you move to another folder or PC. They are **manual
ops/diagnostic tools**, not a runtime dependency: the application and the test
suite use Python's built-in `sqlite3` module, never these executables.

## Contents

| File | What it is |
| --- | --- |
| `sqlite3.exe` | The SQLite CLI shell (`sqlite3 file.db`, `.schema`, `.dump`, ...). |
| `sqldiff.exe` | Shows the differences between two SQLite databases. |
| `sqlite3_analyzer.exe` | Reports space usage / page statistics for a database file. |
| `sqlite3_rsync.exe` | Efficiently syncs a SQLite DB between two locations (rsync-style). |

## Provenance

- **Version:** 3.51.2 (matches the directory name).
- **Source:** the official "Precompiled Binaries for Windows" bundles on
  <https://sqlite.org/download.html>
  (`sqlite-tools-win-x64-*.zip` for the shell/diff/analyzer; `sqlite3_rsync`
  ships in the same tools family).
- **License:** SQLite is in the public domain (<https://sqlite.org/copyright.html>).

## Upgrading

Download the newer `sqlite-tools-win-x64-*.zip` from the link above, replace these
`.exe` files, and rename the directory to the new version (`sqlite.<X.Y.Z>`) so the
folder name stays the single source of truth for which version is vendored.
