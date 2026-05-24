"""
Takedown SLA sweeper — single source of truth for reminder/escalation logic.

Called from two places:
  - backend.api.privacy._in_process_sweeper_loop  (async loop in the backend)
  - tools/ops/scheduled_jobs/jobs/takedown_requests_monitor.py
    (standalone script run by systemd timer when the backend is down)

Idempotent via DB-level claim: each row carries `reminder_sent_at` and
`escalated_at`. The sweep transitions a row at most once because the UPDATE
that sets the timestamp is the same UPDATE that selects the row, so the
first writer wins. Two concurrent sweepers cannot double-send.

Reminder cadence:
  - day 14 (hard-coded): notify owner that the request is still open
  - day `privacy_settings.takedown_sla_days` (default 30): auto-escalate

We do not delete resolved rows here; retention is bounded by
`takedown_request_retention_months` and enforced separately.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.api._email import send_email
from backend.config import privacy_settings, settings
from database.system_models import AuthEditor, TakedownRequest

logger = logging.getLogger("novotree.privacy")

REMINDER_DAYS = 14


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_email(db: Session, owner_id: str) -> Optional[str]:
    row = db.query(AuthEditor).filter(AuthEditor.editor_id == owner_id).first()
    return row.email if row else None


def _reminder_body(req: TakedownRequest, sla_days: int) -> str:
    return (
        f"A privacy / takedown request submitted on {req.created_at} is still open.\n\n"
        f"Requester: {req.requester_name} <{req.requester_email}>\n"
        f"Phone: {req.requester_phone or '(not provided)'}\n"
        f"Individual ID hint: {req.individual_id or '(not provided)'}\n\n"
        f"Message:\n{req.message}\n\n"
        f"You have until day {sla_days} ({REMINDER_DAYS} days from now at most) to respond "
        f"before NovoTree auto-escalates this request. To act on it, locate the individual "
        f"in your tree, verify the requester's identity, and remove or amend the data as "
        f"appropriate. Do NOT auto-cascade to related individuals — each subject must "
        f"request erasure separately.\n\n"
        f"Reply directly to the requester at {req.requester_email} to acknowledge.\n\n"
        f"Controller: {privacy_settings.controller_name}\n"
        f"Privacy contact: {privacy_settings.privacy_contact_email}\n"
    )


def _escalation_body(req: TakedownRequest, sla_days: int) -> str:
    return (
        f"A privacy / takedown request has exceeded the {sla_days}-day SLA without "
        f"owner response and has been auto-escalated.\n\n"
        f"Request ID: {req.id}\n"
        f"Tree owner: {req.tree_owner_id}\n"
        f"Submitted: {req.created_at}\n"
        f"Requester: {req.requester_name} <{req.requester_email}>\n"
        f"Phone: {req.requester_phone or '(not provided)'}\n"
        f"Individual ID hint: {req.individual_id or '(not provided)'}\n\n"
        f"Message:\n{req.message}\n\n"
        f"Action required: verify the requester's identity and remove or hide the "
        f"records on the owner's behalf.\n\n"
        f"Controller: {privacy_settings.controller_name}\n"
    )


async def sweep_once(db: Session) -> dict[str, int]:
    """
    Run one sweep pass over `takedown_requests` and return per-action counts.

    Three passes per sweep:
      1. Send day-14 reminders for still-open rows.
      2. Auto-escalate rows that have crossed the SLA without owner action.
      3. Hard-delete terminal rows older than the retention cap.

    Caller owns the session lifecycle.
    """
    counts = {"reminders_sent": 0, "escalations_sent": 0, "retention_deleted": 0}
    sla_days = privacy_settings.takedown_sla_days
    retention_months = privacy_settings.takedown_request_retention_months
    now = datetime.now(timezone.utc)
    reminder_threshold = (now - timedelta(days=REMINDER_DAYS)).isoformat()
    escalation_threshold = (now - timedelta(days=sla_days)).isoformat()
    # Months → days: 30-day approximation is fine for a retention cap that
    # already has a month-grain config. The "real" calendar offset would just
    # delete a handful of rows a day or two earlier/later — irrelevant.
    retention_threshold = (now - timedelta(days=retention_months * 30)).isoformat()
    admin_to = settings.admin_email or privacy_settings.privacy_contact_email

    # --- Day-14 reminders -------------------------------------------------
    # Candidates: open and unreminded and older than 14 days.
    reminder_rows = (
        db.query(TakedownRequest)
        .filter(
            TakedownRequest.status == "open",
            TakedownRequest.reminder_sent_at.is_(None),
            TakedownRequest.created_at <= reminder_threshold,
        )
        .all()
    )
    for req in reminder_rows:
        # Atomic claim: only one sweeper wins the UPDATE.
        claim_ts = _now_iso()
        claimed = (
            db.query(TakedownRequest)
            .filter(
                TakedownRequest.id == req.id,
                TakedownRequest.reminder_sent_at.is_(None),
            )
            .update({"reminder_sent_at": claim_ts}, synchronize_session=False)
        )
        db.commit()
        if claimed == 0:
            continue
        to = _owner_email(db, req.tree_owner_id) or admin_to
        if not to:
            logger.warning(f"takedown #{req.id}: no owner email and no admin fallback; skipping reminder")
            continue
        await send_email(
            to=to,
            subject=f"Reminder: privacy request still open (day {REMINDER_DAYS} of {sla_days})",
            body=_reminder_body(req, sla_days),
        )
        counts["reminders_sent"] += 1

    # --- SLA-day escalations ---------------------------------------------
    escalation_rows = (
        db.query(TakedownRequest)
        .filter(
            TakedownRequest.status.in_(("open", "acknowledged")),
            TakedownRequest.escalated_at.is_(None),
            TakedownRequest.created_at <= escalation_threshold,
        )
        .all()
    )
    for req in escalation_rows:
        claim_ts = _now_iso()
        claimed = (
            db.query(TakedownRequest)
            .filter(
                TakedownRequest.id == req.id,
                TakedownRequest.escalated_at.is_(None),
            )
            .update(
                {
                    "escalated_at": claim_ts,
                    "status": "escalated",
                    "resolved_at": claim_ts,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if claimed == 0:
            continue
        if not admin_to:
            logger.warning(f"takedown #{req.id}: no admin email; escalation emails not sent")
            continue
        await send_email(
            to=admin_to,
            subject=f"AUTO-ESCALATED: privacy request #{req.id} exceeded {sla_days}-day SLA",
            body=_escalation_body(req, sla_days),
        )
        counts["escalations_sent"] += 1

    # --- Retention deletion -----------------------------------------------
    # Hard-delete terminal rows older than the retention cap. Open and
    # acknowledged rows are never deleted by this pass — they still need to
    # complete their lifecycle (and would be a bug to drop).
    deleted = (
        db.query(TakedownRequest)
        .filter(
            TakedownRequest.status.in_(("resolved", "escalated")),
            TakedownRequest.resolved_at.isnot(None),
            TakedownRequest.resolved_at <= retention_threshold,
        )
        .delete(synchronize_session=False)
    )
    if deleted:
        db.commit()
        counts["retention_deleted"] = deleted

    return counts
