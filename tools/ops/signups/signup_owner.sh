#!/usr/bin/env bash
# Create or reset the first Owner/admin account (Linux/VM wrapper).
# Forwards all arguments to tools.ops.signups.signup_owner, run from the project
# root with the project venv if present.
#
# Examples:
#   tools/ops/signups/signup_owner.sh --email me@example.com
#   tools/ops/signups/signup_owner.sh --email me@example.com --password 'S3cret!!' --force
set -euo pipefail

# Project root = three levels up from this script (tools/ops/signups/ -> root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Pick a Python: project venv first, then PATH.
if [ -x "venv-linux/bin/python" ]; then
  PY="venv-linux/bin/python"
elif [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

exec "$PY" -m tools.ops.signups.signup_owner "$@"
