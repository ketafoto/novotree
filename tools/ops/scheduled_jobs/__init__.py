# The __init__.py file marks a directory as a Python package, enabling imports of modules inside it using dot notation
# (e.g., from tools.operational.scheduled_jobs import scheduled_jobs).
# Without __init__.py, relative and absolute imports within project may fail.
# They help with namespace and module resolution inside project — also required by `python -m <dotted.path>`,
# which is how the systemd unit novotree-backend-monitor.service invokes this package.
#
# Even an empty __init__.py (0 bytes) file suffices.
