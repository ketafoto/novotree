"""
User management API — share tokens, contributors, and contribution invitations.

All endpoints here are owner-only except:
  POST /users/invitations  — public (no auth), used by the Contribute button on shared trees
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import (
    EditorSession,
    hash_password,
    require_owner,
)
from backend.config import settings
from database.system_db import get_system_db
from database.system_models import (
    AuthEditor,
    AuthEditorTree,
    AuthInvitation,
    AuthSetPasswordToken,
    AuthShareToken,
)

logger = logging.getLogger("novotree.users")

router = APIRouter(prefix="/users", tags=["Users"])

_SET_PASSWORD_TOKEN_TTL_DAYS = 7  # set-password links expire after 7 days


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ShareTokenResponse(BaseModel):
    id: int
    owner_id: str
    token: str
    label: Optional[str] = None
    is_active: bool
    expires_after_days: int
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ShareTokenCreate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None  # frontend alias for label
    expires_after_days: int = 90


class ContributorResponse(BaseModel):
    editor_id: str
    display_name: str
    email: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SetActiveRequest(BaseModel):
    editor_id: str
    is_active: bool


class ResetPasswordRequest(BaseModel):
    editor_id: str


class ResetPasswordResponse(BaseModel):
    link: str
    emailed: bool


class InvitationResponse(BaseModel):
    id: int
    owner_id: str
    display_name: str
    email: Optional[str] = None
    message: Optional[str] = None
    status: str  # 'pending' | 'approved' | 'rejected'
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ContributeRequest(BaseModel):
    owner_id: str
    display_name: str
    email: Optional[str] = None
    message: Optional[str] = None


class ApproveResponse(BaseModel):
    link: str
    emailed: bool
    needs_set_password: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_password_link(request: Request, token: str) -> str:
    """Build an absolute URL for the set-password page."""
    base = f"{request.url.scheme}://{request.url.netloc}"
    # Frontend serves at /novotree/ in production; fall back to root in dev.
    path = "/novotree/set-password" if not settings.is_dev else "/set-password"
    return f"{base}{path}?token={token}"


async def _send_email(to: str, subject: str, body: str) -> bool:
    """
    Send an email via SMTP.  Returns True on success, False on failure.
    Caller should degrade gracefully (show the link in UI) if False.
    """
    if not settings.smtp_enabled:
        return False
    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send email to {to}: {e}")
        return False


def _make_set_password_token(
    db: Session, editor_id: str, owner_id: str
) -> str:
    """Create and persist a one-time set-password token. Returns the raw token string."""
    raw = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=_SET_PASSWORD_TOKEN_TTL_DAYS)).isoformat()
    row = AuthSetPasswordToken(
        token=raw,
        editor_id=editor_id,
        owner_id=owner_id,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()  # get the row persisted before commit in caller
    return raw


# ---------------------------------------------------------------------------
# Share token endpoints (owner only)
# ---------------------------------------------------------------------------

@router.get("/share-tokens", response_model=list[ShareTokenResponse])
def list_share_tokens(
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """List all share tokens for the authenticated owner's tree."""
    rows = db.query(AuthShareToken).filter(
        AuthShareToken.owner_id == session.owner_id,
        AuthShareToken.is_active == True,
    ).all()
    return rows


@router.post("/share-tokens", response_model=ShareTokenResponse, status_code=status.HTTP_201_CREATED)
def create_share_token(
    body: ShareTokenCreate,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Create a new viewer share token for the owner's tree."""
    label = body.label or body.description or None
    raw = secrets.token_urlsafe(32)
    row = AuthShareToken(
        owner_id=session.owner_id,
        token=raw,
        label=label,
        is_active=True,
        expires_after_days=max(1, body.expires_after_days),
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/share-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_token(
    token_id: int,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Deactivate (revoke) a share token. The token record is kept for audit."""
    row = db.query(AuthShareToken).filter(
        AuthShareToken.id == token_id,
        AuthShareToken.owner_id == session.owner_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    row.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Contributor endpoints (owner only)
# ---------------------------------------------------------------------------

@router.get("/contributors", response_model=list[ContributorResponse])
def list_contributors(
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """List all contributors who have access to the owner's tree."""
    editor_ids = [
        row.editor_id
        for row in db.query(AuthEditorTree).filter(
            AuthEditorTree.owner_id == session.owner_id
        ).all()
    ]
    if not editor_ids:
        return []
    editors = db.query(AuthEditor).filter(AuthEditor.editor_id.in_(editor_ids)).all()
    return editors


@router.post("/contributors/set-active", status_code=status.HTTP_204_NO_CONTENT)
def set_contributor_active(
    body: SetActiveRequest,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Activate or deactivate a contributor's account."""
    # Verify contributor belongs to this owner's tree
    link = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == body.editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")

    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == body.editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Editor not found")

    editor.is_active = body.is_active
    db.commit()


@router.post("/contributors/reset-password", response_model=ResetPasswordResponse)
async def reset_contributor_password(
    body: ResetPasswordRequest,
    request: Request,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """
    Generate a new set-password link for a contributor.
    Emails the link if SMTP is configured; otherwise returns it for the owner to share.
    """
    # Verify contributor belongs to this owner's tree
    link_row = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == body.editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link_row:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")

    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == body.editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Editor not found")

    raw_token = _make_set_password_token(db, editor.editor_id, session.owner_id)
    db.commit()

    link = _set_password_link(request, raw_token)
    emailed = False

    if editor.email and settings.smtp_enabled:
        emailed = await _send_email(
            to=editor.email,
            subject="Reset your Novotree password",
            body=(
                f"Hello {editor.display_name},\n\n"
                f"Your Novotree password has been reset. Click the link below to set a new password:\n\n"
                f"{link}\n\n"
                f"This link expires in {_SET_PASSWORD_TOKEN_TTL_DAYS} days.\n\n"
                f"If you did not request this, please contact the tree owner."
            ),
        )

    return ResetPasswordResponse(link=link, emailed=emailed)


# ---------------------------------------------------------------------------
# Invitation endpoints
# ---------------------------------------------------------------------------

@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def submit_contribute_request(
    body: ContributeRequest,
    db: Session = Depends(get_system_db),
):
    """
    Public endpoint — no auth required.
    A visitor clicks 'Contribute' and submits their details to request access.
    """
    # Sanity check: the owner_id must correspond to a real owner
    owner = db.query(AuthEditor).filter(
        AuthEditor.editor_id == body.owner_id,
        AuthEditor.role == "owner",
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    invitation = AuthInvitation(
        owner_id=body.owner_id,
        display_name=body.display_name,
        email=body.email,
        message=body.message,
        status="pending",
        created_at=_now(),
    )
    db.add(invitation)
    db.commit()
    return {"detail": "Contribution request submitted"}


@router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """List all contribution requests (pending + processed) for this owner's tree."""
    rows = db.query(AuthInvitation).filter(
        AuthInvitation.owner_id == session.owner_id,
    ).order_by(AuthInvitation.created_at.desc()).all()
    return rows


@router.post("/invitations/{invitation_id}/approve", response_model=ApproveResponse)
async def approve_invitation(
    invitation_id: int,
    request: Request,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """
    Approve a pending contribution request.

    - Creates a placeholder AuthEditor (contributor) if not already present.
    - Grants access to this owner's tree via AuthEditorTree.
    - Generates a set-password token and emails it (or returns the link).
    """
    inv = db.query(AuthInvitation).filter(
        AuthInvitation.id == invitation_id,
        AuthInvitation.owner_id == session.owner_id,
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.status != "pending":
        raise HTTPException(status_code=409, detail=f"Invitation is already {inv.status}")

    # Derive a safe placeholder editor_id from display_name
    base_id = inv.display_name.lower().replace(" ", "_")[:32]
    placeholder_id = base_id
    counter = 1
    while db.query(AuthEditor).filter(AuthEditor.editor_id == placeholder_id).first():
        placeholder_id = f"{base_id}_{counter}"
        counter += 1

    now = _now()

    # Create placeholder editor — password_hash stays NULL until set-password flow
    editor = AuthEditor(
        editor_id=placeholder_id,
        display_name=inv.display_name,
        email=inv.email,
        role="contributor",
        owner_id=None,
        password_hash=None,
        is_active=True,
        created_at=now,
    )
    db.add(editor)

    # Grant access to this owner's tree
    link_row = AuthEditorTree(editor_id=placeholder_id, owner_id=session.owner_id)
    db.add(link_row)

    # Mark invitation resolved
    inv.status = "approved"
    inv.resolved_at = now

    raw_token = _make_set_password_token(db, placeholder_id, session.owner_id)
    db.commit()

    link = _set_password_link(request, raw_token)
    emailed = False

    if inv.email and settings.smtp_enabled:
        emailed = await _send_email(
            to=inv.email,
            subject="You're invited to contribute to a Novotree family tree",
            body=(
                f"Hello {inv.display_name},\n\n"
                f"Your request to contribute to this family tree has been approved.\n\n"
                f"Click the link below to set up your account:\n\n"
                f"{link}\n\n"
                f"This link expires in {_SET_PASSWORD_TOKEN_TTL_DAYS} days.\n\n"
                f"Welcome aboard!"
            ),
        )

    return ApproveResponse(link=link, emailed=emailed, needs_set_password=True)


@router.post("/invitations/{invitation_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_invitation(
    invitation_id: int,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Reject a pending contribution request."""
    inv = db.query(AuthInvitation).filter(
        AuthInvitation.id == invitation_id,
        AuthInvitation.owner_id == session.owner_id,
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.status != "pending":
        raise HTTPException(status_code=409, detail=f"Invitation is already {inv.status}")

    inv.status = "rejected"
    inv.resolved_at = _now()
    db.commit()
