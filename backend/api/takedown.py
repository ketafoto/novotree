"""
Public takedown / "remove me from a tree" flow (Tier 1 §2.2 of
docs/PRIVACY_DESIGN.md).

Routes:
  POST   /privacy/takedown      — public, unauthenticated submission.
                                  Rate-limited per IP. Persists the request
                                  and emails the Owner.
  GET    /takedown              — Owner-scoped list of own takedown rows.
  PATCH  /takedown/{id}         — Owner-scoped status transition (open → resolved,
                                  escalated → resolved).
  DELETE /takedown/{id}         — Owner-scoped hard delete (escape hatch before
                                  the retention sweep removes the row).

Also exposes start/stop hooks for the in-process SLA sweeper that the FastAPI
lifespan in backend.main calls. Sweep logic lives in _takedown_sweep.py and is
shared with the standalone scheduled-jobs backstop in
tools/ops/scheduled_jobs/.

Why this lives in its own module (and not in privacy.py): privacy.py owns
static legal-posture endpoints (/privacy/config now, /privacy/policy later).
Takedown is a multi-endpoint feature with its own schemas, intake email,
sweeper, and Owner UI — keeping it next to /config grows the privacy module
along multiple unrelated axes.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.api._client_ip import get_client_ip
from backend.api._email import send_email
from backend.api._takedown_rate_limit import check_takedown_rate
from backend.api._takedown_sweep import sweep_once
from backend.api.auth import EditorSession, require_owner
from backend.config import privacy_settings, settings
from database.system_db import get_system_db, get_system_session
from database.system_models import AuthEditor, TakedownRequest

logger = logging.getLogger("novotree.privacy")

# Two routers — see backend.main for the rationale. The public submission
# endpoint sits behind /privacy/* (matches the form URL); the Owner-scoped
# triage endpoints sit behind /takedown/* (resource-style, mirrors /individuals,
# /families).
public_router = APIRouter(prefix="/privacy", tags=["Privacy"])
owner_router = APIRouter(prefix="/takedown", tags=["Privacy"])

# How often the in-process sweeper wakes up. The sweep is cheap (an indexed
# query and possibly a few emails) so an hour gives 24 attempts per day to
# notice a row that just crossed a threshold.
_SWEEPER_INTERVAL_SECONDS = 3600

# Cap on free-text fields. Prevents pathological payloads; the form enforces
# the same limits client-side.
_MAX_NAME_LEN = 200
_MAX_EMAIL_LEN = 320      # RFC 5321
_MAX_PHONE_LEN = 40
_MAX_MESSAGE_LEN = 4000
_MAX_INDIVIDUAL_ID_LEN = 64
_MAX_OWNER_ID_LEN = 64

# Light email shape check — full RFC 5322 validation would need email-validator;
# what we actually need is "this is plausibly an email so reply-to works." Junk
# addresses are caught downstream by the owner's verification step (see the
# intake email body) so we deliberately keep this loose.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Owner-allowed status transitions. The DB-level `status` column also accepts
# 'acknowledged' for future Mode-C admin use, but the Owner UI never produces
# that value — see docs/PRIVACY_DESIGN.md §4.9.
_OWNER_TERMINAL_TARGETS = {"resolved"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TakedownRequestPayload(BaseModel):
    tree_owner_id: str = Field(..., min_length=1, max_length=_MAX_OWNER_ID_LEN)
    individual_id: Optional[str] = Field(default=None, max_length=_MAX_INDIVIDUAL_ID_LEN)
    requester_name: str = Field(..., min_length=1, max_length=_MAX_NAME_LEN)
    requester_email: str = Field(..., min_length=3, max_length=_MAX_EMAIL_LEN)
    requester_phone: Optional[str] = Field(default=None, max_length=_MAX_PHONE_LEN)
    message: str = Field(..., min_length=10, max_length=_MAX_MESSAGE_LEN)

    @field_validator("requester_email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("not a valid email address")
        return v


class TakedownRequestAck(BaseModel):
    ok: bool
    id: int


class TakedownRow(BaseModel):
    id: int
    tree_owner_id: str
    individual_id: Optional[str]
    requester_name: str
    requester_email: str
    requester_phone: Optional[str]
    message: str
    status: str
    created_at: str
    resolved_at: Optional[str]
    reminder_sent_at: Optional[str]
    escalated_at: Optional[str]

    model_config = {"from_attributes": True}


class TakedownStatusUpdate(BaseModel):
    status: str = Field(..., description="Currently only 'resolved' is accepted from the Owner UI.")

    @field_validator("status")
    @classmethod
    def _allowed(cls, v: str) -> str:
        if v not in _OWNER_TERMINAL_TARGETS:
            raise ValueError(
                f"Owner may only transition to one of {sorted(_OWNER_TERMINAL_TARGETS)}; "
                f"other statuses are administrative."
            )
        return v


class TestTakedownTimestampOverride(BaseModel):
    """
    TEST-ONLY payload for shifting takedown timestamps. Used to exercise the
    SLA reminder / escalation / retention sweep paths without waiting weeks.

    Both fields are optional; at least one must be present. Each is ISO-8601
    UTC. Symbols on this code path are `test_`-prefixed so reviewers can grep
    them out cleanly — the path is gated by
    `privacy_settings.test_allow_timestamp_override` (env
    `PRIVACY_ALLOW_TIMESTAMP_OVERRIDE`) and must remain off in production.
    """
    test_created_at: Optional[str] = Field(default=None, description="ISO-8601 UTC")
    test_resolved_at: Optional[str] = Field(default=None, description="ISO-8601 UTC")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _takedown_intake_subject(req_id: int) -> str:
    return f"Privacy / takedown request #{req_id} received"


def _takedown_intake_body(req: TakedownRequest) -> str:
    return (
        f"A data subject has submitted a privacy / takedown request against your tree.\n\n"
        f"Request ID: {req.id}\n"
        f"Submitted: {req.created_at}\n"
        f"Requester: {req.requester_name} <{req.requester_email}>\n"
        f"Phone: {req.requester_phone or '(not provided)'}\n"
        f"Individual ID hint: {req.individual_id or '(not provided)'}\n\n"
        f"Message:\n{req.message}\n\n"
        f"You have {privacy_settings.takedown_sla_days} days to respond. "
        f"NovoTree does not auto-cascade — if the requester references children or "
        f"other relatives, use your judgement and verify each claim. If you cannot "
        f"confirm the requester's identity from the information provided, reply to "
        f"{req.requester_email} asking for proof (e.g. an ID showing the name) and "
        f"document your decision either way.\n\n"
        f"After acting on the request, mark it Resolved in your Privacy page so the "
        f"system does not auto-escalate at day {privacy_settings.takedown_sla_days}.\n\n"
        f"If you do not respond within {privacy_settings.takedown_sla_days} days, the "
        f"request will be auto-escalated to NovoTree admin who may hide the records on "
        f"your behalf.\n\n"
        f"Controller: {privacy_settings.controller_name}\n"
        f"Privacy contact: {privacy_settings.privacy_contact_email}\n"
    )


async def _notify_owner_of_takedown_request(req_id: int) -> None:
    """Background task fired after POST /privacy/takedown commit."""
    db = get_system_session()
    try:
        req = db.query(TakedownRequest).filter(TakedownRequest.id == req_id).first()
        if not req:
            logger.warning(f"takedown #{req_id} vanished before notification could be sent")
            return
        owner = db.query(AuthEditor).filter(AuthEditor.editor_id == req.tree_owner_id).first()
        owner_email = owner.email if owner else None
        admin_email = settings.admin_email
        recipients = [e for e in (owner_email, admin_email) if e]
        if not recipients:
            logger.warning(f"takedown #{req_id}: no owner email and no admin email; intake notification skipped")
            return
        subject = _takedown_intake_subject(req.id)
        body = _takedown_intake_body(req)
        for recipient in recipients:
            await send_email(recipient, subject, body)
    finally:
        db.close()


def _load_owned_or_404(db: Session, takedown_id: int, owner_id: str) -> TakedownRequest:
    row = (
        db.query(TakedownRequest)
        .filter(TakedownRequest.id == takedown_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Takedown not found")
    if row.tree_owner_id != owner_id:
        # Don't leak existence — 404, not 403.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Takedown not found")
    return row


# ---------------------------------------------------------------------------
# Public endpoint — submission
# ---------------------------------------------------------------------------

@public_router.post("/takedown", response_model=TakedownRequestAck, status_code=status.HTTP_201_CREATED)
def submit_takedown_request(
    payload: TakedownRequestPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_system_db),
) -> TakedownRequestAck:
    # Reject quickly when over quota — same 429 shape as the global limiter.
    ip = get_client_ip(request)
    if not settings.is_dev and not check_takedown_rate(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many takedown submissions from this address. Please try again later.",
        )

    # Verify the target owner exists. We do not reveal whether it does in the
    # response (avoiding owner enumeration via this endpoint), but if it
    # doesn't exist we still record the request so that legitimate complaints
    # against a since-deleted owner aren't silently dropped.
    owner_exists = (
        db.query(AuthEditor)
        .filter(AuthEditor.editor_id == payload.tree_owner_id, AuthEditor.role == "owner")
        .first()
        is not None
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    req = TakedownRequest(
        tree_owner_id=payload.tree_owner_id,
        individual_id=payload.individual_id,
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        requester_phone=payload.requester_phone,
        message=payload.message,
        status="open",
        created_at=now_iso,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    if not owner_exists:
        logger.warning(
            f"takedown #{req.id} targets unknown owner {payload.tree_owner_id!r}; "
            f"only admin will be notified"
        )

    background_tasks.add_task(_notify_owner_of_takedown_request, req.id)
    return TakedownRequestAck(ok=True, id=req.id)


# ---------------------------------------------------------------------------
# Owner-scoped endpoints — queue UI
# ---------------------------------------------------------------------------

@owner_router.get("", response_model=list[TakedownRow])
def list_my_takedowns(
    include_resolved: bool = False,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
) -> list[TakedownRow]:
    """List the current Owner's takedown requests.

    By default returns rows that still need attention (open + escalated). Pass
    `include_resolved=true` to also return terminal rows (resolved) for audit.
    Escalated rows are NOT hidden by this filter — they remain in the
    default view because they signal a missed SLA.
    """
    q = db.query(TakedownRequest).filter(TakedownRequest.tree_owner_id == session.owner_id)
    if not include_resolved:
        q = q.filter(TakedownRequest.status != "resolved")
    rows = q.order_by(TakedownRequest.created_at.desc()).all()
    return [TakedownRow.model_validate(r) for r in rows]


@owner_router.patch("/{takedown_id}", response_model=TakedownRow)
def update_my_takedown(
    takedown_id: int,
    payload: TakedownStatusUpdate,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
) -> TakedownRow:
    """Owner marks one of their takedown requests as resolved.

    Allowed transitions: `open → resolved`, `escalated → resolved`.
    Anything else is a 400 — Owners cannot un-resolve, escalate, or
    acknowledge from this endpoint.
    """
    row = _load_owned_or_404(db, takedown_id, session.owner_id)
    if row.status == "resolved":
        return TakedownRow.model_validate(row)  # idempotent — already there
    row.status = payload.status  # validated to be 'resolved' above
    row.resolved_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(row)
    return TakedownRow.model_validate(row)


def _test_parse_iso(value: str, field_name: str) -> datetime:
    """TEST-ONLY helper. Parse ISO-8601 and bound it to a sensible window."""
    try:
        # datetime.fromisoformat in 3.11+ accepts the trailing 'Z'; older
        # callers should be sending the same shape the DB stores.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}: not a valid ISO-8601 datetime",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    # Allow up to +1 day in the future so clock-skew accidents don't 400, but
    # reject obvious nonsense like "year 3000". Floor is the unix epoch.
    if parsed > now + timedelta(days=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}: too far in the future",
        )
    if parsed.year < 1970:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}: before unix epoch",
        )
    return parsed


@owner_router.patch("/{takedown_id}/test_override", response_model=TakedownRow)
def test_override_takedown_timestamps(
    takedown_id: int,
    payload: TestTakedownTimestampOverride,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
) -> TakedownRow:
    """
    TEST-ONLY. Shift `created_at` and/or `resolved_at` on the Owner's own
    takedown row, so the sweeper paths can be exercised without waiting.

    Gated by `privacy_settings.test_allow_timestamp_override` — returns 403
    unless `PRIVACY_ALLOW_TIMESTAMP_OVERRIDE=true` is set in the backend's
    environment. Must remain off in production.
    """
    if not privacy_settings.test_allow_timestamp_override:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Timestamp override is disabled. Enable PRIVACY_ALLOW_TIMESTAMP_OVERRIDE on test VMs only.",
        )
    if payload.test_created_at is None and payload.test_resolved_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of test_created_at or test_resolved_at",
        )
    row = _load_owned_or_404(db, takedown_id, session.owner_id)

    if payload.test_created_at is not None:
        new_created = _test_parse_iso(payload.test_created_at, "test_created_at")
        row.created_at = new_created.isoformat()
        # Reset the sweeper claim columns so a backdated row goes back into
        # eligibility — otherwise the reminder/escalation has already been
        # "claimed" and the sweeper would skip it.
        row.reminder_sent_at = None
        row.escalated_at = None

    if payload.test_resolved_at is not None:
        new_resolved = _test_parse_iso(payload.test_resolved_at, "test_resolved_at")
        row.resolved_at = new_resolved.isoformat()

    logger.warning(
        "TEST: timestamp override on takedown #%d by owner %s (created_at=%s, resolved_at=%s)",
        row.id,
        session.owner_id,
        payload.test_created_at,
        payload.test_resolved_at,
    )
    db.commit()
    db.refresh(row)
    return TakedownRow.model_validate(row)


@owner_router.delete("/{takedown_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_takedown(
    takedown_id: int,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
) -> None:
    """Hard-delete a takedown row.

    Intended escape hatch for the Owner before the retention sweeper
    (`takedown_request_retention_months`) removes the row automatically.
    Allowed only when the row is in a terminal state — deleting an open or
    escalated row would lose the SLA trail.
    """
    row = _load_owned_or_404(db, takedown_id, session.owner_id)
    if row.status not in ("resolved", "escalated"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resolve or wait for SLA escalation before deleting this takedown.",
        )
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# In-process SLA sweeper
# ---------------------------------------------------------------------------

_sweeper_task: Optional[asyncio.Task] = None


async def _in_process_sweeper_loop() -> None:
    logger.info("takedown sweeper: in-process loop started (interval=%ds)", _SWEEPER_INTERVAL_SECONDS)
    while True:
        try:
            db = get_system_session()
            try:
                counts = await sweep_once(db)
            finally:
                db.close()
            if counts["reminders_sent"] or counts["escalations_sent"] or counts["retention_deleted"]:
                logger.info(
                    "takedown sweeper: %d reminder(s), %d escalation(s), %d retention delete(s)",
                    counts["reminders_sent"],
                    counts["escalations_sent"],
                    counts["retention_deleted"],
                )
        except asyncio.CancelledError:
            logger.info("takedown sweeper: shutting down")
            raise
        except Exception:
            logger.exception("takedown sweeper: sweep raised; continuing")
        await asyncio.sleep(_SWEEPER_INTERVAL_SECONDS)


def start_in_process_sweeper() -> None:
    """Start the in-process sweeper task. Called from FastAPI lifespan startup."""
    global _sweeper_task
    if _sweeper_task is not None:
        return
    _sweeper_task = asyncio.create_task(_in_process_sweeper_loop())


async def stop_in_process_sweeper() -> None:
    """Cancel the sweeper task. Called from FastAPI lifespan shutdown."""
    global _sweeper_task
    if _sweeper_task is None:
        return
    _sweeper_task.cancel()
    try:
        await _sweeper_task
    except asyncio.CancelledError:
        pass
    _sweeper_task = None
