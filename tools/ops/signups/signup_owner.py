"""Create (or reset) the first Owner/admin account directly in the system DB.

Production signup helper: mints an Owner account without enabling owner signup
(no flag-flipping, no email verification). Use it to register yourself on a
fresh deployment, or after erasing datasets/system.sqlite.

It writes the same row the email-verification signup flow produces
(see backend/api/auth.py verify_owner_email): role='owner', owner_id == editor_id,
is_active=True, a bcrypt password hash; then initializes the owner's data.sqlite.

Run from the project root with the project venv, e.g.:
    python -m tools.ops.signups.signup_owner --email me@example.com
    python -m tools.ops.signups.signup_owner --email me@example.com --password 'S3cret!!' --force
Password is read interactively if --password is omitted.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.api import auth
from database import db
from database import owner_info
from database import system_db
from database import system_models


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_datasets_dir(datasets_dir: str | None) -> Path:
    """Point the data layer at the datasets directory to write into.

    With no override, this is exactly what the running backend uses:
    $NOVOTREE_DATA_DIR if set, else the in-tree <project_root>/datasets (see
    database/owner_info.py). An explicit --datasets-dir rebinds it the same way
    the local desktop app's "change data folder" does (backend/api/local.py),
    so init_system_db() and get_engine() both target the chosen location.
    Returns the resolved system.sqlite path for confirmation.
    """
    if datasets_dir:
        new_path = Path(datasets_dir).expanduser().resolve()
        owner_info.DATASETS_DIR = new_path
        os.environ["NOVOTREE_DATA_DIR"] = str(new_path)
    return owner_info.DATASETS_DIR / "system.sqlite"


def _derive_editor_id(email: str) -> str:
    """Mirror auth._derive_editor_id's base derivation (local part, sanitized).

    Uniqueness against existing rows is enforced by the caller, which already
    holds an open system session; this only produces the base candidate.
    """
    local = email.split("@")[0]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", local)[:32].strip("_") or "user"


def signup_owner(
    email: str,
    password: str,
    display_name: str | None,
    force: bool,
    datasets_dir: str | None = None,
) -> str:
    """Create or (with force) reset an Owner account. Returns the editor_id."""
    # validate_password_strength raises FastAPI's HTTPException (it is shared with
    # the web signup flow); translate it into a clean CLI error.
    try:
        auth.validate_password_strength(password)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        raise SystemExit(f"Weak password: {detail}")

    # Resolve and announce the target DB so the operator can confirm the script
    # is writing to the same datasets/ the service reads (a common footgun if
    # NOVOTREE_DATA_DIR differs between shells).
    system_db_path = _resolve_datasets_dir(datasets_dir)
    print(f"Using system DB: {system_db_path}")

    system_db.init_system_db()
    session = system_db.get_system_session()
    try:
        candidate = _derive_editor_id(email)

        existing_by_email = session.query(system_models.AuthEditor).filter(
            system_models.AuthEditor.email == email
        ).first()
        existing_by_id = session.query(system_models.AuthEditor).filter(
            system_models.AuthEditor.editor_id == candidate
        ).first()
        existing = existing_by_email or existing_by_id

        if existing and not force:
            raise SystemExit(
                f"An account already exists (editor_id='{existing.editor_id}', "
                f"email='{existing.email}'). Re-run with --force to reset its password."
            )

        if existing:
            existing.password_hash = auth.hash_password(password)
            existing.is_active = True
            # Keep role/owner_id as-is for an existing owner; only repair if missing.
            if existing.role != "owner":
                existing.role = "owner"
            if not existing.owner_id:
                existing.owner_id = existing.editor_id
            session.commit()
            owner_editor_id = existing.editor_id
            action = "reset"
        else:
            # editor_id must be unique even when derived; bump a suffix if taken.
            unique_id = candidate
            suffix = 1
            while session.query(system_models.AuthEditor).filter(
                system_models.AuthEditor.editor_id == unique_id
            ).first():
                unique_id = f"{candidate}_{suffix}"
                suffix += 1

            now = _now_iso()
            session.add(system_models.AuthEditor(
                editor_id=unique_id,
                display_name=display_name or unique_id,
                email=email,
                role="owner",
                owner_id=unique_id,
                password_hash=auth.hash_password(password),
                is_active=True,
                created_at=now,
                last_login_at=now,
            ))
            session.commit()
            owner_editor_id = unique_id
            action = "created"
    finally:
        session.close()

    # Initialize the owner's per-tree data.sqlite (and lookup tables).
    db.get_engine(owner_editor_id)
    print(f"Owner account {action}: editor_id='{owner_editor_id}', email='{email}'.")
    return owner_editor_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or reset the first Owner/admin account (no signup flags needed)."
    )
    # Arguments alphabetical by long flag (CLAUDE.md).
    parser.add_argument(
        "--datasets-dir",
        dest="datasets_dir",
        default=None,
        help="Datasets directory to write into. Defaults to the same location the "
             "backend uses ($NOVOTREE_DATA_DIR, else <project_root>/datasets). "
             "Pass this only if the service stores data elsewhere.",
    )
    parser.add_argument(
        "--display-name",
        dest="display_name",
        default=None,
        help="Display name. Defaults to the editor_id derived from the email.",
    )
    parser.add_argument("--email", required=True, help="Owner login email.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="If the account already exists, reset its password instead of failing.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Owner password. Omit to be prompted interactively (recommended).",
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Owner password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            raise SystemExit(1)

    signup_owner(
        email=args.email,
        password=password,
        display_name=args.display_name,
        force=args.force,
        datasets_dir=args.datasets_dir,
    )


if __name__ == "__main__":
    main()
