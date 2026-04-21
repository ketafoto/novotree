import logging
import sys
from contextvars import ContextVar

# Set by the request middleware for every incoming HTTP request.
# Value is "<editor_id>" or "anon" for unauthenticated / share-token requests.
request_user: ContextVar[str] = ContextVar("request_user", default="")


class _UserFilter(logging.Filter):
    """Injects the current request user into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        user = request_user.get("")
        record.user = f"[{user}] " if user else ""
        return True


def setup_logging():
    """Configure logging. Writes to stdout/stderr (captured by journald on Linux)."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.addFilter(_UserFilter())
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(user)s%(message)s'
    ))
    root_logger.addHandler(handler)
