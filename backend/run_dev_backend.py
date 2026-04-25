#!/usr/bin/env python3
"""
Start the backend uvicorn server, optionally loading a named env file.

Usage:
    python run_dev_backend.py           # admin mode — dev bypass, no login required
    python run_dev_backend.py auth-on   # full auth flow (loads backend/.env.dev-auth-on)
"""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()


def load_env_file(path: Path) -> None:
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if key:
            os.environ[key] = value


mode = sys.argv[1] if len(sys.argv) > 1 else None

if mode:
    env_file = REPO_ROOT / "backend" / f".env.dev-{mode}"
    if not env_file.exists():
        print(f"Error: env file not found: {env_file}")
        print(f"Expected: backend/.env.dev-{mode}")
        sys.exit(1)
    load_env_file(env_file)
    print(f"[run_dev_backend] mode: {mode}  (loaded {env_file.name})")
else:
    print("[run_dev _backend] mode: admin (dev bypass auth, no env file loaded)")

subprocess.run(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload"],
    cwd=str(REPO_ROOT),
)
