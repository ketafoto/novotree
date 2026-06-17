"""
User management API — share tokens and contributors.

All endpoints here are owner-only except:
  GET  /users/owner-info   — public, returns owner display_name for the contributor signup form
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api._client_ip import get_client_ip
from backend.api.auth import (
    EditorSession,
    hash_password,
    require_owner,
)
from backend.config import privacy_settings, settings
from database.system_db import get_system_db
from database.system_models import (
    AuthEditor,
    AuthEditorTree,
    AuthInvitation,
    AuthSetPasswordToken,
    AuthShareConsent,
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
    expose_sensitive: bool = False
    expose_minors: bool = False
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ShareTokenCreate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None  # frontend alias for label
    expires_after_days: int = 90
    # Per-share special-category (GDPR Art. 9) exposure (Privacy §3.7, M-05).
    # Default False: sensitive events, notes, flagged individuals and media are
    # excluded entirely from this link's viewer payload. The Owner opts in.
	#
    expose_sensitive: bool = False
    # Per-share minor (GDPR Art. 8) exposure (Privacy §3.8, M-06), independent of
    # expose_sensitive. Default False: living minors (node, edges, media) are
    # excluded entirely from this link's viewer payload. The Owner opts in.
	#
    expose_minors: bool = False
    # Per-share acknowledgement (Privacy §2.5, M-03). Must be True; the modal
    # in the UI sets it on submit. Backend rejects creation without it so the
    # consent row in auth_share_consents is the authoritative record that the
    # Owner saw and accepted the §9.4 text.
	#
    acknowledgement: bool = False


class ContributorResponse(BaseModel):
    editor_id: str
    display_name: str
    email: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    message: Optional[str] = None
    has_contributions: bool = False

    model_config = {"from_attributes": True}


class ContributorContributionItem(BaseModel):
    id: int
    label: str
    individual_id: Optional[int] = None
    family_id: Optional[int] = None


class ContributorContributions(BaseModel):
    individuals: list[ContributorContributionItem] = []
    families: list[ContributorContributionItem] = []
    events: list[ContributorContributionItem] = []
    media: list[ContributorContributionItem] = []


class OwnerInfoResponse(BaseModel):
    owner_id: str
    display_name: str


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
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("/owner-info", response_model=OwnerInfoResponse)
def get_owner_info(
    owner_id: str,
    db: Session = Depends(get_system_db),
):
    """Public — return the display name of an owner. Used by the contributor signup form."""
    owner = db.query(AuthEditor).filter(
        AuthEditor.editor_id == owner_id,
        AuthEditor.role == "owner",
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return OwnerInfoResponse(owner_id=owner.editor_id, display_name=owner.display_name)


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
    request: Request,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Create a new viewer share token for the owner's tree."""
    if not body.acknowledgement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Share-link acknowledgement is required.",
        )
    label = body.label or body.description or None
    raw = secrets.token_urlsafe(32)
    now = _now()
    row = AuthShareToken(
        owner_id=session.owner_id,
        token=raw,
        label=label,
        is_active=True,
        expires_after_days=max(1, body.expires_after_days),
        expose_sensitive=body.expose_sensitive,
        expose_minors=body.expose_minors,
        created_at=now,
    )
    db.add(row)
    db.flush()  # populate row.id for the consent FK
    db.add(AuthShareConsent(
        editor_id=session.editor_id,
        tree_owner_id=session.owner_id,
        share_token_id=row.id,
        accepted_at=now,
        accepted_ip=get_client_ip(request),
        privacy_policy_version=privacy_settings.privacy_policy_version,
    ))
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

def _has_contributions(editor_id: str, owner_id: str) -> bool:
    """Check if a contributor created any records in the owner's tree database."""
    try:
        from database.db import get_db as _get_db
        from database.models import Family, Individual, Event, Media
        db_gen = _get_db(owner_id)
        tree_db = next(db_gen)
        try:
            has = (
                tree_db.query(Individual).filter(Individual.created_by == editor_id).first() is not None
                or tree_db.query(Family).filter(Family.created_by == editor_id).first() is not None
                or tree_db.query(Event).filter(Event.created_by == editor_id).first() is not None
                or tree_db.query(Media).filter(Media.created_by == editor_id).first() is not None
            )
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
        return has
    except Exception:
        return True  # safe default — prevent accidental deletion


_INACTIVITY_MONTHS = 2
_INACTIVITY_DAYS = _INACTIVITY_MONTHS * 30


def _last_edit_time(editor_id: str, owner_id: str) -> Optional[datetime]:
    """Return the most recent created_at across all four contribution tables, or None."""
    try:
        from database.db import get_db as _get_db
        from database.models import Event, Family, Individual, Media
        from sqlalchemy import func as sa_func

        db_gen = _get_db(owner_id)
        tree_db = next(db_gen)
        try:
            candidates = []
            for model in (Individual, Family, Event, Media):
                row = (
                    tree_db.query(sa_func.max(model.created_at))
                    .filter(model.created_by == editor_id)
                    .scalar()
                )
                if row:
                    candidates.append(row)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
        if not candidates:
            return None
        latest_str = max(candidates)
        return datetime.fromisoformat(latest_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_contributions(editor_id: str, owner_id: str) -> ContributorContributions:
    """Return all records created by a contributor in the owner's tree."""
    try:
        from database.db import get_db as _get_db
        from database.models import Event, Family, Individual, IndividualName, Media

        db_gen = _get_db(owner_id)
        tree_db = next(db_gen)
        try:
            individuals = tree_db.query(Individual).filter(Individual.created_by == editor_id).all()
            ind_items = []
            for ind in individuals:
                name_row = (
                    tree_db.query(IndividualName)
                    .filter(IndividualName.individual_id == ind.id)
                    .order_by(IndividualName.name_order)
                    .first()
                )
                if name_row:
                    parts = [name_row.given_name, name_row.family_name]
                    label = " ".join(p for p in parts if p).strip()
                else:
                    label = ""
                ind_items.append(ContributorContributionItem(id=ind.id, label=label or f"Individual #{ind.id}"))

            families = tree_db.query(Family).filter(Family.created_by == editor_id).all()
            fam_items = [ContributorContributionItem(id=f.id, label=f"Family #{f.id}") for f in families]

            events = tree_db.query(Event).filter(Event.created_by == editor_id).all()
            ev_items = [
                ContributorContributionItem(
                    id=e.id,
                    label=e.event_type_code,
                    individual_id=e.individual_id,
                    family_id=e.family_id,
                )
                for e in events
            ]

            media = tree_db.query(Media).filter(Media.created_by == editor_id).all()
            media_items = [
                ContributorContributionItem(
                    id=m.id,
                    label=m.media_type_code or "file",
                    individual_id=m.individual_id,
                    family_id=m.family_id,
                )
                for m in media
            ]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
        return ContributorContributions(
            individuals=ind_items, families=fam_items, events=ev_items, media=media_items
        )
    except Exception:
        return ContributorContributions()


def _delete_contributions(editor_id: str, owner_id: str) -> None:
    """Delete all records created by a contributor from the owner's tree, including media files on disk."""
    from pathlib import Path
    from sqlalchemy import or_
    from database.db import get_db as _get_db
    from database.models import Event, Family, FamilyChild, FamilyMember, Individual, IndividualName, Media
    from database.owner_info import OwnerInfo

    owner_info = OwnerInfo(owner_id=owner_id, create_dirs=False)
    db_gen = _get_db(owner_id)
    tree_db = next(db_gen)
    try:
        ind_ids = [row[0] for row in tree_db.query(Individual.id).filter(Individual.created_by == editor_id).all()]
        fam_ids = [row[0] for row in tree_db.query(Family.id).filter(Family.created_by == editor_id).all()]

        # Collect all media files to delete from disk (contributor's own + any attached to their individuals/families)
        media_filter_clauses = [Media.created_by == editor_id]
        if ind_ids:
            media_filter_clauses.append(Media.individual_id.in_(ind_ids))
        if fam_ids:
            media_filter_clauses.append(Media.family_id.in_(fam_ids))
        for m in tree_db.query(Media).filter(or_(*media_filter_clauses)).all():
            if m.file_path:
                fp = Path(owner_info.media_dir) / m.file_path
                try:
                    fp.unlink(missing_ok=True)
                except OSError:
                    pass

        # Delete events: contributor's own + those on contributor's individuals/families
        event_filter_clauses = [Event.created_by == editor_id]
        if ind_ids:
            event_filter_clauses.append(Event.individual_id.in_(ind_ids))
        if fam_ids:
            event_filter_clauses.append(Event.family_id.in_(fam_ids))
        tree_db.query(Event).filter(or_(*event_filter_clauses)).delete(synchronize_session=False)

        # Delete media records (same scope as files above)
        tree_db.query(Media).filter(or_(*media_filter_clauses)).delete(synchronize_session=False)

        # Clean up contributor's individuals and their dependents
        if ind_ids:
            tree_db.query(IndividualName).filter(IndividualName.individual_id.in_(ind_ids)).delete(synchronize_session=False)
            tree_db.query(FamilyMember).filter(FamilyMember.individual_id.in_(ind_ids)).delete(synchronize_session=False)
            tree_db.query(FamilyChild).filter(FamilyChild.child_id.in_(ind_ids)).delete(synchronize_session=False)
            tree_db.query(Individual).filter(Individual.id.in_(ind_ids)).delete(synchronize_session=False)

        # Clean up contributor's families and their dependents
        if fam_ids:
            tree_db.query(FamilyMember).filter(FamilyMember.family_id.in_(fam_ids)).delete(synchronize_session=False)
            tree_db.query(FamilyChild).filter(FamilyChild.family_id.in_(fam_ids)).delete(synchronize_session=False)
            tree_db.query(Family).filter(Family.id.in_(fam_ids)).delete(synchronize_session=False)

        tree_db.commit()
    except Exception:
        tree_db.rollback()
        raise
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


async def cleanup_inactive_contributors(owner_id: str, db: Session, base_url: str) -> None:
    """
    Called on every owner login.  Enforces two inactivity rules:
      Rule 1 — Active contributor whose last edit is older than _INACTIVITY_DAYS: freeze.
      Rule 2 — Approved contributor (has_contributions=False) whose account is older
               than _INACTIVITY_DAYS: delete (they never contributed after being approved).
    Sends notification emails in both cases.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_INACTIVITY_DAYS)

    links = db.query(AuthEditorTree).filter(
        AuthEditorTree.owner_id == owner_id,
    ).all()

    for link in links:
        editor = db.query(AuthEditor).filter(
            AuthEditor.editor_id == link.editor_id,
        ).first()
        if not editor:
            continue

        # Skip editors who are still pending approval (never logged in)
        if editor.last_login_at is None:
            continue

        has_contrib = _has_contributions(link.editor_id, owner_id)

        if not has_contrib:
            # Rule 2: approved, never edited — delete if account old enough
            if editor.created_at:
                try:
                    created = datetime.fromisoformat(editor.created_at.replace("Z", "+00:00"))
                except ValueError:
                    created = None
                if created and created < cutoff:
                    email = editor.email
                    display_name = editor.display_name
                    db.delete(link)
                    db.delete(editor)
                    db.commit()
                    if email and settings.smtp_enabled:
                        await _send_email(
                            to=email,
                            subject="Your Novotree contributor account has been removed",
                            body=(
                                f"Hello {display_name},\n\n"
                                f"Your contributor access to the family tree has been automatically removed "
                                f"because no contributions were made within {_INACTIVITY_MONTHS} months "
                                f"of account creation.\n\n"
                                f"If you wish to contribute again, please sign up via the tree's share link.\n"
                            ),
                        )
                    logger.info("Auto-deleted inactive contributor %s (no contributions)", link.editor_id)
                    continue
        else:
            # Rule 1: has contributions — freeze if last edit is too old and still active
            if link.is_active:
                last_edit = _last_edit_time(link.editor_id, owner_id)
                if last_edit and last_edit < cutoff:
                    link.is_active = False
                    db.commit()
                    login_url = f"{base_url}{'/novotree/login' if not settings.is_dev else '/login'}"
                    if editor.email and settings.smtp_enabled:
                        await _send_email(
                            to=editor.email,
                            subject="Your Novotree contributor access has been suspended",
                            body=(
                                f"Hello {editor.display_name},\n\n"
                                f"Your contributor access to the family tree has been automatically suspended "
                                f"due to {_INACTIVITY_MONTHS} months of inactivity.\n\n"
                                f"Please contact the tree owner to restore your access.\n\n"
                                f"When access is restored, you can log in at: {login_url}\n"
                            ),
                        )
                    logger.info("Auto-frozen inactive contributor %s (last edit: %s)", link.editor_id, last_edit)


@router.get("/contributors", response_model=list[ContributorResponse])
def list_contributors(
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """List all contributors who have access to the owner's tree (active and inactive)."""
    editor_ids = [
        row.editor_id
        for row in db.query(AuthEditorTree).filter(
            AuthEditorTree.owner_id == session.owner_id
        ).all()
    ]
    if not editor_ids:
        return []
    link_map = {
        row.editor_id: row
        for row in db.query(AuthEditorTree).filter(
            AuthEditorTree.owner_id == session.owner_id,
            AuthEditorTree.editor_id.in_(editor_ids),
        ).all()
    }
    editors = db.query(AuthEditor).filter(AuthEditor.editor_id.in_(editor_ids)).all()
    result = []
    for ed in editors:
        link = link_map.get(ed.editor_id)
        # is_active for UI: pending approval uses global flag; frozen uses per-tree link flag
        is_active = ed.is_active and (link.is_active if link else False)
        contrib = ContributorResponse(
            editor_id=ed.editor_id,
            display_name=ed.display_name,
            email=ed.email,
            is_active=is_active,
            created_at=ed.created_at,
            last_login_at=ed.last_login_at,
            message=ed.message,
            has_contributions=_has_contributions(ed.editor_id, session.owner_id),
        )
        result.append(contrib)
    return result


@router.get("/contributors/{editor_id}/contributions", response_model=ContributorContributions)
def get_contributor_contributions(
    editor_id: str,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Return all records created by a contributor in the owner's tree."""
    link_row = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link_row:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")
    return _get_contributions(editor_id, session.owner_id)


@router.post("/contributors/set-active", status_code=status.HTTP_204_NO_CONTENT)
async def set_contributor_active(
    body: SetActiveRequest,
    request: Request,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """Freeze or unfreeze a contributor's access to this owner's tree (per-tree)."""
    link = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == body.editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")

    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == body.editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Editor not found")

    link.is_active = body.is_active
    db.commit()

    if editor.email and settings.smtp_enabled:
        login_url = (
            f"{request.url.scheme}://{request.url.netloc}"
            f"{'/novotree/login' if not settings.is_dev else '/login'}"
        )
        if body.is_active:
            await _send_email(
                to=editor.email,
                subject="Your Novotree contributor access has been restored",
                body=(
                    f"Hello {editor.display_name},\n\n"
                    f"Your contributor access to the family tree has been restored by the tree owner.\n\n"
                    f"You can log in again at: {login_url}\n"
                ),
            )
        else:
            await _send_email(
                to=editor.email,
                subject="Your Novotree contributor access has been suspended",
                body=(
                    f"Hello {editor.display_name},\n\n"
                    f"Your contributor access to the family tree has been temporarily suspended "
                    f"by the tree owner.\n\n"
                    f"If you believe this is a mistake, please contact the tree owner directly.\n\n"
                    f"When access is restored, you can log in at: {login_url}\n"
                ),
            )


@router.post("/contributors/{editor_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_contributor(
    editor_id: str,
    request: Request,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """
    Approve a pending contributor: set is_active=True and notify them by email.
    Also used to re-activate a previously frozen account.
    """
    link_row = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link_row:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")

    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Editor not found")

    was_frozen = not link_row.is_active and editor.last_login_at is not None
    link_row.is_active = True
    # Also ensure the global AuthEditor row is active (covers first-time approval)
    editor.is_active = True
    db.commit()

    login_url = (
        f"{request.url.scheme}://{request.url.netloc}"
        f"{'/novotree/login' if not settings.is_dev else '/login'}"
    )

    if editor.email and settings.smtp_enabled:
        if was_frozen:
            subject = "Your Novotree contributor access has been restored"
            body = (
                f"Hello {editor.display_name},\n\n"
                f"Your contributor access has been restored by the tree owner.\n\n"
                f"You can log in again at: {login_url}\n"
            )
        else:
            subject = "Your Novotree contributor access has been approved"
            message_line = f"\nYour note to the owner: \"{editor.message}\"\n" if editor.message else ""
            body = (
                f"Hello {editor.display_name},\n\n"
                f"Great news! The tree owner has approved your contributor access.{message_line}\n"
                f"You can now log in at: {login_url}\n\n"
                f"Welcome to the team!"
            )
        await _send_email(to=editor.email, subject=subject, body=body)


@router.delete("/contributors/{editor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contributor(
    editor_id: str,
    force: bool = False,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_system_db),
):
    """
    Delete a contributor account.
    Without force=true, blocked if the contributor has any contributions.
    With force=true, all their contributions (individuals, families, events, media) are deleted first.
    """
    link_row = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == editor_id,
        AuthEditorTree.owner_id == session.owner_id,
    ).first()
    if not link_row:
        raise HTTPException(status_code=404, detail="Contributor not found in your tree")

    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Editor not found")

    if _has_contributions(editor_id, session.owner_id):
        if not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete a contributor who has added data to the tree",
            )
        _delete_contributions(editor_id, session.owner_id)

    email = editor.email
    display_name = editor.display_name

    db.delete(link_row)
    db.delete(editor)
    db.commit()

    if email and settings.smtp_enabled:
        await _send_email(
            to=email,
            subject="Your Novotree contributor access has been removed",
            body=(
                f"Hello {display_name},\n\n"
                f"Your contributor access to the family tree has been removed by the owner.\n\n"
                f"If you believe this is a mistake, please contact the tree owner directly."
            ),
        )


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
        is_active=False,  # inactive until set-password completed; activate separately
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
