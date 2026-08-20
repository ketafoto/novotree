"""
Persisted desktop-app configuration (config.json) and the on-disk paths it
lives at.

Shared by `backend/local_launcher.py` (reads the config at startup, writes it
after the first-run picker) and `backend/api/local.py` (rewrites it when the
user moves the data folder or switches trees). Both writers went through their
own copy of the "dump a dict to config.json" logic before this module existed,
which is how a second key can silently get dropped by whichever writer was not
updated -- keeping the schema in one place makes that impossible.

Deliberately dependency-free (json + pathlib + platformdirs) so the launcher
can import it before any FastAPI/env-var setup has happened.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "NovoTree"
APP_AUTHOR = "NovoSpace"

# %LocalAppData%\NovoSpace\NovoTree on Windows; ~/.config/NovoTree on Linux.
APP_CONFIG_DIR = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"

# Log file always lives next to the config (small, one place to look).
LOG_FILE = APP_CONFIG_DIR / "novotree.log"

# Suggested default data dir, but the user can pick anywhere.
DEFAULT_DATA_DIR = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)) / "datasets"

# Tree (owner) id used when config.json predates multi-tree support, and the
# name given to the tree created on a fresh install. Every tree lives at
# <data_dir>/<owner_id>/, so this is also a directory name.
DEFAULT_OWNER_ID = "local"

# Env vars the launcher exports before importing the FastAPI app, and that
# backend/api/local.py rewrites in-process when the user switches tree or
# moves the data folder. database/owner_info.py is the reader that turns them
# into DATASETS_DIR / DEFAULT_OWNER_ID; it spells the names itself rather than
# importing this module, which would point a database/ import at backend/.
#
ENV_APP_MODE = "NOVOTREE_APP_MODE"
ENV_DATA_DIR = "NOVOTREE_DATA_DIR"
ENV_DEFAULT_OWNER_ID = "NOVOTREE_DEFAULT_OWNER_ID"
ENV_EDITOR_ID = "NOVOTREE_EDITOR_ID"
ENV_EDITOR_DISPLAY_NAME = "NOVOTREE_EDITOR_DISPLAY_NAME"
ENV_CONFIG_FILE = "NOVOTREE_CONFIG_FILE"
ENV_LOG_FILE = "NOVOTREE_LOG_FILE"

_KEY_DATA_DIR = "data_dir"
_KEY_OWNER_ID = "owner_id"
_KEY_EDITOR_ID = "editor_id"
_KEY_DISPLAY_NAME = "display_name"

logger = logging.getLogger("novotree.local")


@dataclass(frozen=True)
class LocalConfig:
    data_dir: Path      # root holding system.sqlite + one subfolder per tree
    owner_id: str       # which tree under that root is currently open
    editor_id: str      # WHO is editing - stamped into created_by on every row
    display_name: str   # human name shown as "Added by ..."


def load() -> LocalConfig | None:
    """Read config.json, or None if it is absent/unreadable (-> re-prompt).

    Older configs are read forward rather than rejected: one written before
    multi-tree support has no `owner_id` (read as DEFAULT_OWNER_ID, the tree
    such an install already uses), and one written before the editor identity
    was split out has no `editor_id` (read as `owner_id`, which is what those
    installs actually stamped into created_by). Both defaults keep existing
    rows resolving to the handle they were written with.
    """
    if not APP_CONFIG_FILE.exists():
        return None
    try:
        # utf-8-sig tolerates a BOM if a Windows tool (PowerShell Out-File,
        # Notepad) writes the config; plain utf-8 would reject it.
        #
        raw = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("config.json unreadable (%s) - re-prompting", exc)
        return None

    data_dir = raw.get(_KEY_DATA_DIR)
    if not data_dir:
        return None
    owner_id = str(raw.get(_KEY_OWNER_ID) or DEFAULT_OWNER_ID)
    editor_id = str(raw.get(_KEY_EDITOR_ID) or owner_id)
    return LocalConfig(
        data_dir=Path(data_dir).expanduser(),
        owner_id=owner_id,
        editor_id=editor_id,
        display_name=str(raw.get(_KEY_DISPLAY_NAME) or editor_id),
    )


def save(config: LocalConfig) -> None:
    """Persist the whole config. Takes the dataclass rather than loose fields
    so a caller changing one thing cannot drop another -- the tree, the data
    folder and the editor identity are each changed by a different code path."""
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_FILE.write_text(
        json.dumps(
            {
                _KEY_DATA_DIR: str(config.data_dir),
                _KEY_OWNER_ID: config.owner_id,
                _KEY_EDITOR_ID: config.editor_id,
                _KEY_DISPLAY_NAME: config.display_name,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
