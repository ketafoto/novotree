#!/usr/bin/env python3
"""Run frontend and backend test suites sequentially; exit on first failure."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

SUITES = [
    ("Frontend (npm test)", ["npm", "test"], REPO_ROOT / "frontend"),
    ("Backend (pytest)",    [sys.executable, "-m", "pytest"], REPO_ROOT / "tests"),
]


def run(label: str, cmd: list, cwd: Path) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, cwd=cwd, shell=(sys.platform == 'win32'))
    if result.returncode != 0:
        print(f"\n[FAIL] {label} exited with code {result.returncode}")
        sys.exit(result.returncode)


for label, cmd, cwd in SUITES:
    run(label, cmd, cwd)

print("\n[PASS] All test suites passed.")