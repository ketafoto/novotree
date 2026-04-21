"""
Tests for request-scoped logging infrastructure.

Covers:
  - _UserFilter injects per-request username into every log record
  - uvicorn.access logger propagates through root handler after app startup
"""

import logging


class TestLogUserInjection:

    def test_filter_injects_username_into_record(self):
        """_UserFilter sets record.user = '[username] ' when request_user is non-empty."""
        from backend.logging import _UserFilter, request_user

        request_user.set("alice")
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        f = _UserFilter()
        f.filter(record)

        assert record.user == "[alice] "  # type: ignore[attr-defined]

    def test_filter_empty_user_produces_empty_string(self):
        """_UserFilter sets record.user = '' when request_user is not set."""
        from backend.logging import _UserFilter, request_user

        request_user.set("")
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        f = _UserFilter()
        f.filter(record)

        assert record.user == ""  # type: ignore[attr-defined]

    def test_uvicorn_access_logger_suppressed_after_startup(self, system_db_client):
        """After app lifespan starts, uvicorn.access INFO is suppressed — we emit our own."""
        uvicorn_access = logging.getLogger("uvicorn.access")
        assert uvicorn_access.level >= logging.WARNING
        assert uvicorn_access.propagate is False

    def test_root_handler_has_user_filter_and_format(self):
        """Root logging handler must have _UserFilter and a %(user)s format string.

        This verifies the full plumbing: _UserFilter injects request_user into every
        record, and the formatter is configured to emit it, so usernames appear on
        every log line including those propagated from uvicorn.access.
        """
        from backend.logging import _UserFilter

        root = logging.getLogger()
        assert root.handlers, "Root logger must have at least one handler"

        handler = root.handlers[0]
        user_filters = [f for f in handler.filters if isinstance(f, _UserFilter)]
        assert user_filters, "Root handler must have _UserFilter attached"

        fmt = handler.formatter._fmt if handler.formatter else ""  # type: ignore[union-attr]
        assert "%(user)s" in fmt, f"Formatter must contain %(user)s, got: {fmt!r}"
