"""
Minor-consent re-confirm reminder (PRIVACY_DESIGN.md section 3.8, M-06).

When an Individual the Owner recorded as a minor (with parental_consent given)
crosses the child_age_threshold_years line - i.e. they are no longer a minor -
the Owner is emailed once to re-confirm they may keep that person's data. At the
threshold age the person may become a data subject in their own right (GDPR Art.
8), so the consent the Owner asserted on their behalf warrants a fresh look.

Idempotency is per-individual: consent_reminder_sent_at is stamped on the row
when the reminder is emailed, so each crossing is reported exactly once
(mirrors the per-row cursor posture of the section 3.4 error-log digest, but
keyed on the individual rather than a file).

NOT done here (deferred): parental_consent is NOT reset to NULL on the crossing.
Resetting would silently re-block future uploads, which is a heavier and less
reversible action than M-06's "send the Owner a reminder" wording asks for;
emailing once and recording it leaves the Owner in control.

Cadence: dispatched by the same novotree-backend-monitor timer as the error-log
digest (every 15 min) via scheduled_jobs.UNCONDITIONAL_JOBS - it must run while
the backend is HEALTHY. A single cursor file self-throttles the whole scan to
MINOR_REMINDER_INTERVAL_HOURS (/etc/novotree.env, default 24h), since a person's
age does not change faster than that.

SMTP reuse: runs in-repo and reuses backend.api._email.send_email via
asyncio.run rather than duplicating SMTP logic.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from backend.api._email import send_email
from backend.config import _as_int, privacy_settings, settings
from database import db as tree_db
from database import models
from database.owner_info import DATASETS_DIR, list_owners
from database.system_db import get_system_session, init_system_db
from database.system_models import AuthEditor

logger = logging.getLogger("novotree.minor_consent_reminder")

JOB_NAME = "minor_consent_reminder"

# Self-throttle window (MINOR_REMINDER_INTERVAL_HOURS in /etc/novotree.env,
# default 24h). The backend-monitor timer ticks every 15 min; the scan only runs
# once this much time has passed. _as_int mirrors the backend's parsing
# (blank/garbage -> default, floored at 1).
#
SCAN_INTERVAL_SECONDS = _as_int(os.getenv("MINOR_REMINDER_INTERVAL_HOURS"), 24, minimum=1) * 3600

# Cursor file: ISO timestamp of the last scan. Job STATE, not a log, so it lives
# under datasets/ (the only path the sandboxed backend-monitor service may
# write) rather than /var/log. Same rationale as the error-log digest cursor.
#
CURSOR_FILE = DATASETS_DIR / ".minor_consent_cursor"

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


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


def _owner_recipient(sys_db, owner_id: str) -> str:
    """Email to notify for a tree: the owner's own address, falling back to the
    consolidated ops mailbox if the owner has no email on file."""
    editor = (
        sys_db.query(AuthEditor)
        .filter(AuthEditor.editor_id == owner_id)
        .first()
    )
    if editor and editor.email:
        return editor.email
    return privacy_settings.privacy_contact_email


def _newly_aged_out(owner_id: str) -> list[str]:
    """Display labels for individuals in one owner's tree who have crossed the
    minor threshold, had consent recorded, and have not yet been reminded.
    Stamps consent_reminder_sent_at as it collects them (one reminder each)."""
    threshold = privacy_settings.child_age_threshold_years
    db = next(tree_db.get_db(owner_id))
    try:
        candidates = (
            db.query(models.Individual)
            .filter(
                models.Individual.parental_consent.is_(True),
                models.Individual.consent_reminder_sent_at.is_(None),
                models.Individual.birth_date.isnot(None),
                models.Individual.death_date.is_(None),
            )
            .all()
        )
        labels: list[str] = []
        stamp = _now().isoformat()
        for ind in candidates:
            # Crossed the line: no longer a living minor by today's reckoning.
            if models.individual_is_minor(ind, threshold):
                continue
            ind.consent_reminder_sent_at = stamp
            names = sorted(
                ind.names,
                key=lambda n: (n.name_order if n.name_order is not None else 9999, n.id),
            )
            label = ind.gedcom_id or f"id={ind.id}"
            if names:
                label = f"{(names[0].given_name or '').strip()} {(names[0].family_name or '').strip()}".strip() or label
            labels.append(label)
        if labels:
            db.commit()
        return labels
    finally:
        db.close()


def run() -> None:
    """Synchronous entry point invoked by scheduled_jobs.py every tick."""
    # Without SMTP there is no way to deliver; skip before touching the cursor or
    # any DB so an SMTP-off deployment costs ~nothing per tick.
    #
    if not settings.smtp_enabled:
        return

    now = _now()
    cursor = _read_cursor()

    # First-ever run: seed the cursor without scanning, so the very first tick
    # after deploy does not email a backlog of every already-aged-out person.
    #
    if cursor is None:
        _write_cursor(now)
        logger.info("%s: no cursor - initialised, first scan in ~%dh",
                    JOB_NAME, SCAN_INTERVAL_SECONDS // 3600)
        return

    if (now - cursor).total_seconds() < SCAN_INTERVAL_SECONDS:
        return  # throttled - not enough time since the last scan

    init_system_db()
    sys_db = get_system_session()
    sent_any = False
    try:
        for owner_id in list_owners():
            labels = _newly_aged_out(owner_id)
            if not labels:
                continue
            recipient = _owner_recipient(sys_db, owner_id)
            threshold = privacy_settings.child_age_threshold_years
            subject = f"[NovoTree] {len(labels)} record(s) reached age {threshold}"
            body = (
                f"The following {len(labels)} person(s) in your tree have reached "
                f"age {threshold} and are no longer treated as minors:\n\n"
                + "\n".join(f"  - {label}" for label in labels)
                + "\n\nPlease re-confirm that you may continue to store their data. "
                "At this age a person may be a data subject in their own right "
                "(GDPR Art. 8).\n"
            )
            if asyncio.run(send_email(recipient, subject, body)):
                sent_any = True
                logger.info("%s: reminded %s about %d record(s)",
                            JOB_NAME, recipient, len(labels))
            else:
                logger.warning("%s: reminder email to %s failed", JOB_NAME, recipient)
    finally:
        sys_db.close()

    # Advance the cursor once the scan completes. Unlike the error-log digest
    # (which holds its cursor on a failed send to retry the same window), here
    # the per-row consent_reminder_sent_at stamp already guarantees no individual
    # is reported twice - a failed email simply means that row keeps its stamp and
    # will not be retried, which is the acceptable trade-off for a courtesy
    # reminder (the Owner can still act via the privacy-request flow).
    #
    _write_cursor(now)
    if not sent_any:
        logger.info("%s: no newly-aged-out records since %s",
                    JOB_NAME, cursor.strftime(_TS_FORMAT))
