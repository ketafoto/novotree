# Owner configuration and path management.
#
# Each owner has a folder under datasets/<owner>/ containing:
# - data.sqlite  : SQLite database with tree data
# - data.ged     : GEDCOM file (for import/export)
# - media/       : Owner media files (photos, documents, etc.)
#
# Note:
# - "owner" is the application-side data holder.
# - A "viewer" is the web/browser caller and may gain edit permissions later.

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Union

# Project root directory (parent of database/ folder)
PROJECT_ROOT = Path(__file__).parent.parent


def _resolve_datasets_dir() -> Path:
    """Datasets root: NOVOTREE_DATA_DIR env var if set (used by the local
    desktop installer to point at the user's chosen data folder), otherwise
    the in-tree datasets/ dir used by web deployment and dev."""
    env = os.environ.get("NOVOTREE_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return PROJECT_ROOT / "datasets"


DATASETS_DIR = _resolve_datasets_dir()

# Default owner id (used when OwnerInfo is created without owner_id, and as
# the bypass-mode owner in NOVOTREE_APP_MODE=admin/local). Honors the
# NOVOTREE_DEFAULT_OWNER_ID env var so the desktop installer can pin it to
# "local" without touching the multi-user web deployment.
DEFAULT_OWNER_ID = os.environ.get("NOVOTREE_DEFAULT_OWNER_ID", "aktiniya")


@dataclass
class OwnerInfo:
    """Owner-specific paths and information."""

    owner_id: Optional[str] = None
    base_dir: Optional[Path] = field(default=None)
    gedcom_file: Optional[Union[str, Path]] = field(default=None)
    db_file: Optional[Union[str, Path]] = field(default=None)
    owner_dir: Path = field(default=None)  # type: ignore[assignment]
    media_dir: Path = field(default=None)  # type: ignore[assignment]
    create_dirs: bool = field(default=True)

    def __post_init__(self):
        if self.owner_id is None:
            self.owner_id = DEFAULT_OWNER_ID

        if self.base_dir is None:
            self.base_dir = DATASETS_DIR

        if self.owner_dir is None:
            self.owner_dir = self.base_dir / self.owner_id

        if self.db_file is None:
            self.db_file = self.owner_dir / "data.sqlite"
        elif isinstance(self.db_file, str):
            self.db_file = Path(self.db_file)

        if self.gedcom_file is None:
            self.gedcom_file = self.owner_dir / "data.ged"
        elif isinstance(self.gedcom_file, str):
            self.gedcom_file = Path(self.gedcom_file)

        if self.media_dir is None:
            self.media_dir = self.owner_dir / "media"

        if self.create_dirs:
            self.owner_dir.mkdir(parents=True, exist_ok=True)
            self.media_dir.mkdir(parents=True, exist_ok=True)


def list_owners() -> list[str]:
    """List all available owner ids."""
    if not DATASETS_DIR.exists():
        return []

    return sorted([
        d.name for d in DATASETS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])
