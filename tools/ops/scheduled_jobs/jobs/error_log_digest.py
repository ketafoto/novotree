"""
Error-log digest job (PRIVACY_DESIGN.md section 3.4 - "email errors from logs").

Scans the novotree journald namespace for ERROR-level entries and emails a
digest to the privacy/support mailbox (PrivacySettings.privacy_contact_email).

Cadence: the backend-monitor timer fires every 15 min, but emailing every
15 min would be noise. This job self-throttles to ERROR_DIGEST_INTERVAL_HOURS
(/etc/novotree.env, default 3h) via a cursor file: each run reads journald
`--since` the last cursor, and only proceeds once that much time has elapsed.
The cursor doubles as the `--since` lower bound, so no error window is ever
skipped or double-reported.

Runs unconditionally every tick (see scheduled_jobs.UNCONDITIONAL_JOBS) - unlike
the backstop sweep, it must run while the backend is HEALTHY, since that is
exactly when the errors it reports occur.

SMTP reuse: this runs in-repo and can import the backend, so it reuses
backend.api._email.send_email (the same async SMTP helper the privacy-request
flow uses) via asyncio.run, rather than duplicating SMTP logic.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.api._email import send_email
from backend.config import _as_int, settings
from database.owner_info import DATASETS_DIR

logger = logging.getLogger("novotree.error_digest")

JOB_NAME = "error_log_digest"

# journald namespace novotree.service logs into (PRIVACY_DESIGN.md section 3.3).
# The name is owned by novospace vm-setup.py (LogNamespace=, unit + drop-in paths)
# and published into /etc/novotree.env as JOURNAL_NAMESPACE so this consumer
# reads the same value instead of re-hardcoding it. The systemd unit name
# matches the namespace by that same setup, so SERVICE_UNIT derives from it.
# Read errors with: journalctl --namespace <ns> -u <ns> -p err
#
JOURNAL_NAMESPACE = os.getenv("JOURNAL_NAMESPACE", "novotree")
SERVICE_UNIT = JOURNAL_NAMESPACE

# Self-throttle window (ERROR_DIGEST_INTERVAL_HOURS in /etc/novotree.env, default
# 3h). The backend-monitor timer ticks every 15 min; the digest only sends once
# this much time has passed, covering the whole interval since the last send. It
# can never fire faster than the timer regardless of how low this is set.
# _as_int mirrors the backend's parsing (blank/garbage -> default, floored at 1).
#
DIGEST_INTERVAL_SECONDS = _as_int(os.getenv("ERROR_DIGEST_INTERVAL_HOURS"), 3, minimum=1) * 3600

# Cursor file: ISO timestamp of the last digest send. This is job STATE, not a
# log, so it does not belong in /var/log; and the backend-monitor service is
# sandboxed (ProtectSystem=strict, ReadWritePaths=.../datasets in
# _backend_monitor.py), so datasets/ is the only path the process may write -
# /var/log would be read-only and the write would fail.
#
CURSOR_FILE = DATASETS_DIR / ".error_digest_cursor"

# journald timestamp format accepted by --since and emitted by the cursor.
#
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# Cap the body so a runaway error loop can't produce a multi-megabyte email.
#
MAX_DIGEST_LINES = 500

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _read_cursor() -> datetime | None:
    try:
        raw = CURSOR_FILE.read_text().strip()
    except FileNotFoundError:
        return None
    try:
        return datetime.strptime(raw, _TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("%s: unparsable cursor %r - treating as absent", JOB_NAME, raw)
        return None

def _write_cursor(when: datetime) -> None:
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_FILE.write_text(when.strftime(_TS_FORMAT))

def _collect_errors(since: datetime) -> list[str]:
    """Return ERROR-level journal lines for the novotree unit since `since`.

    journalctl prints in the local timezone, so we pass `since` as local time.
    Failures here (journalctl missing, permission denied) are logged and treated
    as "no errors" - the digest is best-effort and must not crash the runner.
    """
    since_local = since.astimezone().strftime(_TS_FORMAT)
    try:
        result = subprocess.run(
            [
                "journalctl",
                "--namespace", JOURNAL_NAMESPACE,
                "-u", SERVICE_UNIT,
                "-p", "err",
                "--since", since_local,
                "--no-pager",
                "-o", "short-iso",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("%s: journalctl unavailable (%s) - skipping", JOB_NAME, e)
        return []
    if result.returncode != 0:
        logger.warning(
            "%s: journalctl exited %d: %s",
            JOB_NAME, result.returncode, result.stderr.strip(),
        )
        return []
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # Drop journalctl's "-- No entries --" placeholder line.
    return [ln for ln in lines if not ln.startswith("-- ")]


def run() -> None:
    """Synchronous entry point invoked by scheduled_jobs.py every tick."""
    # Nothing to do without a way to deliver: skip before touching the cursor
    # or the journal, so a deployment with SMTP off costs ~nothing per tick and
    # never advances the cursor past errors it could not have emailed anyway.
    #
    if not settings.smtp_enabled:
        return

    now = _now()
    cursor = _read_cursor()

    # First-ever run: establish the cursor without emailing a backlog (an
    # unbounded "everything since boot" digest would be the first thing the
    # operator sees). Subsequent runs cover [cursor, now].
    #
    if cursor is None:
        _write_cursor(now)
        logger.info("%s: no cursor - initialised, first digest in ~3h", JOB_NAME)
        return

    if (now - cursor).total_seconds() < DIGEST_INTERVAL_SECONDS:
        return  # throttled - not enough time since the last digest

    errors = _collect_errors(cursor)

    # No errors this window: advance the cursor (the window was genuinely empty)
    # and stop.
    #
    if not errors:
        _write_cursor(now)
        logger.info("%s: no errors since %s", JOB_NAME, cursor.strftime(_TS_FORMAT))
        return

    truncated = len(errors) > MAX_DIGEST_LINES
    shown = errors[:MAX_DIGEST_LINES]
    header = (
        f"{len(errors)} error log entry(ies) from novotree "
        f"since {cursor.strftime(_TS_FORMAT)} UTC.\n"
    )
    if truncated:
        header += f"(showing the first {MAX_DIGEST_LINES})\n"
    body = header + "\n" + "\n".join(shown)
    subject = f"[NovoTree] {len(errors)} error log entry(ies)"

    sent = asyncio.run(send_email(settings.privacy_contact_email, subject, body))

    # Advance the cursor ONLY on a successful send. If delivery failed, leave the
    # cursor where it is so the next tick re-reads the same [cursor, now] window
    # and retries - errors are never silently dropped. Note: a persistent SMTP
    # failure therefore retries every timer tick (~15 min), not every interval,
    # until mail recovers; that is the intended "keep trying to deliver" posture.
    #
    if sent:
        _write_cursor(now)
        logger.info("%s: emailed %d error(s) to %s", JOB_NAME, len(errors),
                    settings.privacy_contact_email)
    else:
        logger.warning("%s: digest email failed - cursor held, will retry (%d error(s))",
                       JOB_NAME, len(errors))
