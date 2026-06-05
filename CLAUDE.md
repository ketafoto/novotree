# Claude Code — Project Guidelines

> Companion to `novospace.git/CLAUDE.md`. The code-style rules below are shared
> across both repos; keep them in sync if either changes.

## Code style

- **No hardcoded string duplication.** If a string literal (username, path prefix, domain, etc.) appears more than once in a file, extract it into a named constant at the top before finishing the edit. Apply this proactively — do not wait to be asked.
- **No logic duplication.** If two functions share the same sequence of operations, extract a helper immediately — do not wait to be asked. Symmetric operations (backup/restore, encode/decode, pack/unpack) are a strong signal.
- **Explicit `dest=` on hyphenated argparse flags.** Any `add_argument("--foo-bar", ...)` whose long flag contains a hyphen must pass `dest="foo_bar"` explicitly, so the CLI-flag→attribute mapping is spelled out at the call site (argparse converts `-`→`_` silently otherwise). Keep the flag itself hyphenated (Unix convention); only the `dest` is added. Flags with no hyphen (`--restore`, `--owner`) and positionals don't need it.

## Git

- **Never commit automatically.** Always show the diff and wait for explicit user approval before running `git commit`. The user needs to verify changes before they land in history.
- **Short commit messages.** One concise line, no body. No `Co-Authored-By` trailer unless the user asks.
- **Keep executable scripts executable.** Scripts that ship with a shebang and `100755` mode (e.g. `tools/ops/*.py`, `database/gedcom_*.py`, `backend/run_dev_backend.py`, `tools/git-hooks/*`) must stay executable. After any commit touching them, verify with `git ls-files --stage <path>` that the mode is still `100755`; if it dropped to `100644`, run `git update-index --chmod=+x <file>` and commit immediately.
