"""
Authentication and user management API.

Terminology:
- editor: any authenticated user (owner or contributor)
- owner: an editor who owns a tree under datasets/<owner_id>/
- contributor: an editor invited to contribute to one or more owner trees
- viewer: anonymous read-only access via share token in URL

In NOVOTREE_APP_MODE=admin (local dev), all auth is bypassed — the default owner is
auto-resolved without requiring login.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from database.owner_info import DEFAULT_OWNER_ID
from database.system_db import get_system_db
from database.system_models import AuthEditor, AuthEditorTree, AuthPendingContributor, AuthPendingOwner, AuthSetPasswordToken

logger = logging.getLogger("novotree.auth")


router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class EditorResponse(BaseModel):
    editor_id: str
    display_name: str
    email: Optional[str] = None
    role: str           # 'owner' | 'contributor'
    owner_id: str       # which tree is active for this session
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    editor_id: str                   # accepts either username or email
    password: str
    owner_id: Optional[str] = None  # required for contributors with multiple trees


class OwnerSignupRequest(BaseModel):
    display_name: Optional[str] = None  # derived from email local part if omitted
    password: str
    email: str


class SetPasswordRequest(BaseModel):
    token: str
    editor_id: str          # contributor chooses username at this step
    display_name: str
    password: str
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    display_name: str


class TokenResponse(BaseModel):
    editor: EditorResponse


class SignupResponse(BaseModel):
    detail: str
    emailed: bool


class ContributorSignupRequest(BaseModel):
    display_name: Optional[str] = None
    email: str
    password: str
    owner_id: str        # which tree they want to contribute to
    message: Optional[str] = None


class PublicConfig(BaseModel):
    admin_email: Optional[str] = None
    signup_enabled: bool = True


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

_PASSWORD_HINT = (
    "Password must be at least 8 characters and contain uppercase, lowercase, and a digit."
)


def _derive_editor_id(email: str, db) -> str:
    """Derive a unique editor_id from the local part of an email address."""
    import re
    local = email.split("@")[0]
    base = re.sub(r"[^a-zA-Z0-9_-]", "_", local)[:32].strip("_") or "user"
    candidate = base
    counter = 1
    while db.query(AuthEditor).filter(AuthEditor.editor_id == candidate).first():
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def validate_password_strength(password: str) -> None:
    import re
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[0-9]", password)
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_PASSWORD_HINT)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Email verification helpers
# ---------------------------------------------------------------------------

_EMAIL_VERIFY_TOKEN_TTL_HOURS = 1
_CONTRIBUTOR_VERIFY_TOKEN_TTL_HOURS = 24


async def _send_verification_email(
    to: str,
    display_name: str,
    verify_url: str,
    role: str = "Owner",
    owner_display_name: Optional[str] = None,
) -> bool:
    if not settings.smtp_enabled:
        return False
    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to

        if role == "Contributor":
            msg["Subject"] = "Verify your Novotree contributor request"
            tree_line = f"Tree: {owner_display_name}\n" if owner_display_name else ""
            body = (
                f"Hello {display_name},\n\n"
                f"You signed up to contribute to a family tree on Novotree.\n\n"
                f"Role: Contributor\n"
                f"{tree_line}"
                f"\nClick the link below to verify your email. After verification, "
                f"the tree owner will review and approve your request before you can log in.\n\n"
                f"{verify_url}\n\n"
                f"This link expires in {_CONTRIBUTOR_VERIFY_TOKEN_TTL_HOURS} hours.\n\n"
                f"If you did not submit this request, you can ignore this email."
            )
        else:
            msg["Subject"] = "Verify your Novotree account"
            body = (
                f"Hello {display_name},\n\n"
                f"Click the link below to verify your email and complete account creation:\n\n"
                f"{verify_url}\n\n"
                f"This link expires in {_EMAIL_VERIFY_TOKEN_TTL_HOURS} hour.\n\n"
                f"If you did not create this account, you can ignore this email."
            )

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
        logger.warning(f"Failed to send verification email to {to}: {e}")
        return False


async def _send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True if sent, False if SMTP is disabled or fails."""
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


# ---------------------------------------------------------------------------
# Signup shared helpers
# ---------------------------------------------------------------------------

def _require_smtp_or_dev() -> None:
    """Raise 503 when signup is attempted and registration is not enabled."""
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account registration is currently unavailable — SMTP not configured.",
        )


def _check_email_conflict(db: Session, email: str) -> None:
    """Raise 409 when the email is already registered in auth_editors."""
    if db.query(AuthEditor).filter(AuthEditor.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )


def _validate_signup_credentials(db: Session, password: str, email: str) -> None:
    """Validate password strength and email uniqueness for any signup flow."""
    validate_password_strength(password)
    _check_email_conflict(db, email)


def _build_verify_url(request: Request, token: str, page_path: str) -> str:
    """
    Build an absolute verification URL for the given frontend page path.

    page_path is the path *without* the /novotree prefix, e.g. '/verify-owner-email'.
    In production the prefix is added; in dev it is omitted.
    When FRONTEND_BASE_URL is set (local dev with separate frontend port), use it
    directly with no prefix.
    """
    if settings.frontend_base_url:
        return f"{settings.frontend_base_url}{page_path}?token={token}"
    base = f"{request.url.scheme}://{request.url.netloc}"
    path = f"/novotree{page_path}" if not settings.is_dev else page_path
    return f"{base}{path}?token={token}"


def _consume_pending_token(db: Session, pending_model, token: str):
    """
    Look up a pending-signup row by token, check expiry and editor_id race condition.

    Returns the pending row on success.  On any failure deletes the row (where
    applicable), commits, and raises HTTPException.
    """
    pending = db.query(pending_model).filter(
        pending_model.token == token,
    ).first()
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or already used verification link")

    if datetime.now(timezone.utc) > datetime.fromisoformat(pending.expires_at):
        db.delete(pending)
        db.commit()
        raise HTTPException(status_code=400, detail="Verification link has expired — please sign up again")

    if db.query(AuthEditor).filter(AuthEditor.editor_id == pending.editor_id).first():
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{pending.editor_id}' was taken — please sign up again",
        )

    return pending


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"
_ACCESS_TOKEN_TYPE = "access"
_REFRESH_TOKEN_TYPE = "refresh"


def _issue_access_token(editor_id: str, owner_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {
        "sub": editor_id,
        "owner_id": owner_id,
        "role": role,
        "type": _ACCESS_TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def _issue_refresh_token(editor_id: str, owner_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)
    payload = {
        "sub": editor_id,
        "owner_id": owner_id,
        "role": role,
        "type": _REFRESH_TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    return payload


def _set_auth_cookies(response: Response, editor_id: str, owner_id: str, role: str) -> None:
    access = _issue_access_token(editor_id, owner_id, role)
    refresh = _issue_refresh_token(editor_id, owner_id, role)
    secure = settings.cookie_secure
    response.set_cookie(
        key="access_token", value=access,
        httponly=True, secure=secure, samesite="strict",
        max_age=settings.jwt_expiry_hours * 3600,
    )
    response.set_cookie(
        key="refresh_token", value=refresh,
        httponly=True, secure=secure, samesite="strict",
        max_age=settings.jwt_refresh_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


# ---------------------------------------------------------------------------
# Current editor resolution (FastAPI dependency)
# ---------------------------------------------------------------------------

class EditorSession:
    """Resolved editor identity for the current request."""
    def __init__(self, editor_id: str, owner_id: str, role: str,
                 display_name: str, email: Optional[str] = None):
        self.editor_id = editor_id
        self.owner_id = owner_id
        self.role = role
        self.display_name = display_name
        self.email = email

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_contributor(self) -> bool:
        return self.role == "contributor"


def _dev_session() -> EditorSession:
    """Auto-authenticated session for NOVOTREE_APP_MODE=admin."""
    return EditorSession(
        editor_id=DEFAULT_OWNER_ID,
        owner_id=DEFAULT_OWNER_ID,
        role="owner",
        display_name="Dev Owner",
    )


def get_current_editor(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_system_db),
) -> EditorSession:
    """Resolve the current editor from the access token cookie (or dev bypass)."""
    if settings.is_dev:
        return _dev_session()

    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = _decode_token(access_token, _ACCESS_TOKEN_TYPE)
    editor_id: str = payload["sub"]
    owner_id: str = payload["owner_id"]
    role: str = payload["role"]

    editor = db.query(AuthEditor).filter(
        AuthEditor.editor_id == editor_id,
        AuthEditor.is_active == True,
    ).first()
    if not editor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # For contributors, also check that their access to the specific tree in the JWT is not frozen
    if role == "contributor":
        link = db.query(AuthEditorTree).filter(
            AuthEditorTree.editor_id == editor_id,
            AuthEditorTree.owner_id == owner_id,
            AuthEditorTree.is_active == True,
        ).first()
        if not link:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access to this tree has been suspended")

    return EditorSession(
        editor_id=editor.editor_id,
        owner_id=owner_id,
        role=role,
        display_name=editor.display_name,
        email=editor.email,
    )


def require_owner(session: EditorSession = Depends(get_current_editor)) -> EditorSession:
    """Dependency: require owner role."""
    if not session.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return session


def require_editor(session: EditorSession = Depends(get_current_editor)) -> EditorSession:
    """Dependency: require owner OR contributor (any authenticated editor)."""
    return session  # get_current_editor already validates auth


def get_viewer_owner_id(
    share: Optional[str] = None,
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_system_db),
) -> str:
    """
    Resolve owner_id for read-only (viewer) access.
    Accepts either an authenticated editor session or a valid share token.
    Returns owner_id string.
    """
    if settings.is_dev:
        return DEFAULT_OWNER_ID

    # Try authenticated session first — reuse get_current_editor to enforce freeze checks
    if access_token:
        try:
            session = get_current_editor(access_token=access_token, db=db)
            return session.owner_id
        except HTTPException:
            pass

    # Try share token
    if share:
        from database.system_models import AuthShareToken
        from datetime import datetime, timezone, timedelta
        token_row = db.query(AuthShareToken).filter(
            AuthShareToken.token == share,
            AuthShareToken.is_active == True,
        ).first()
        if token_row:
            # Check rolling expiry
            anchor = token_row.last_used_at or token_row.created_at
            expiry = datetime.fromisoformat(anchor) + timedelta(days=token_row.expires_after_days)
            if datetime.now(timezone.utc) <= expiry:
                # Update last_used_at (rolling window)
                token_row.last_used_at = datetime.now(timezone.utc).isoformat()
                db.commit()
                return token_row.owner_id

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


# ---------------------------------------------------------------------------
# Tree database dependencies (per-request, owner-scoped)
# ---------------------------------------------------------------------------

def get_tree_db(session: EditorSession = Depends(get_current_editor)):
    """Dependency: yield a SQLAlchemy session for the authenticated editor's owner tree."""
    from database.db import get_db as _get_db
    yield from _get_db(session.owner_id)


def get_viewer_tree_db(owner_id: str = Depends(get_viewer_owner_id)):
    """Dependency: yield a SQLAlchemy session for viewer access (JWT or share token)."""
    from database.db import get_db as _get_db
    yield from _get_db(owner_id)


def get_tree_owner_info(session: EditorSession = Depends(get_current_editor)):
    """Dependency: return OwnerInfo for the authenticated editor's owner tree."""
    from database.db import get_owner_info as _get_owner_info
    return _get_owner_info(session.owner_id)


def get_viewer_owner_info(owner_id: str = Depends(get_viewer_owner_id)):
    """Dependency: return OwnerInfo for viewer access (JWT or share token)."""
    from database.db import get_owner_info as _get_owner_info
    return _get_owner_info(owner_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/me", response_model=EditorResponse)
def get_me(session: EditorSession = Depends(get_current_editor)):
    """Get current editor info."""
    return EditorResponse(
        editor_id=session.editor_id,
        display_name=session.display_name,
        email=session.email,
        role=session.role,
        owner_id=session.owner_id,
        is_active=True,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_system_db),
):
    """
    Login with email or username + password.

    When a second request with owner_id is sent (tree picker step), the role in the
    JWT reflects the relationship to the chosen tree: 'owner' if it's the editor's own
    tree, 'contributor' otherwise.
    """
    from sqlalchemy import or_
    editor = db.query(AuthEditor).filter(
        or_(AuthEditor.editor_id == body.editor_id, AuthEditor.email == body.editor_id),
    ).first()

    if not editor or not editor.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, editor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Build the full list of trees available to this editor.
    # For contributors, only include trees where the per-tree link is active.
    # Owners always have their own tree (global is_active governs owner access).
    own_tree_id = editor.owner_id if editor.role == "owner" else None

    if own_tree_id and not editor.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    contributor_trees = db.query(AuthEditorTree).filter(
        AuthEditorTree.editor_id == editor.editor_id,
    ).all()
    # Only include trees where this contributor's access is active
    contributor_tree_ids = [row.owner_id for row in contributor_trees if row.is_active]

    all_tree_ids: list[str] = (
        ([own_tree_id] if own_tree_id else []) +
        [t for t in contributor_tree_ids if t != own_tree_id]
    )

    if not all_tree_ids:
        # Distinguish: pending approval (never logged in) vs frozen (has login history).
        # last_login_at is the reliable discriminator — a pending contributor has never
        # successfully logged in, so it's always None regardless of link.is_active.
        is_frozen = editor.last_login_at is not None
        if is_frozen:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Your access has been suspended — contact the tree owner")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Your account is awaiting owner approval")

    if body.owner_id:
        # Tree picker step: validate the chosen tree is accessible and not frozen
        link = next((r for r in contributor_trees if r.owner_id == body.owner_id), None)
        if body.owner_id != own_tree_id and (link is None or not link.is_active):
            raise HTTPException(status_code=403, detail="Access to this tree not granted")
        if body.owner_id not in all_tree_ids:
            raise HTTPException(status_code=403, detail="Access to this tree not granted")
        owner_id = body.owner_id
    elif len(all_tree_ids) == 1:
        owner_id = all_tree_ids[0]
    else:
        # Multiple trees — return picker payload so the client can let the user choose.
        # Each entry carries the owner's display_name and the role this editor would get.
        owner_ids_set = {row.editor_id: row for row in db.query(AuthEditor).filter(
            AuthEditor.editor_id.in_(all_tree_ids)
        ).all()}
        trees_payload = [
            {
                "owner_id": tid,
                "display_name": owner_ids_set[tid].display_name if tid in owner_ids_set else tid,
                "role": "owner" if tid == own_tree_id else "contributor",
            }
            for tid in all_tree_ids
        ]
        raise HTTPException(
            status_code=status.HTTP_300_MULTIPLE_CHOICES,
            detail={"trees": trees_payload},
        )

    # Role for the chosen tree
    session_role = "owner" if owner_id == own_tree_id else "contributor"

    editor.last_login_at = datetime.now(timezone.utc).isoformat()
    db.commit()

    if session_role == "owner":
        from backend.api.users import cleanup_inactive_contributors  # lazy — avoids circular import
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        await cleanup_inactive_contributors(owner_id, db, base_url)

    _set_auth_cookies(response, editor.editor_id, owner_id, session_role)
    return TokenResponse(
        editor=EditorResponse(
            editor_id=editor.editor_id,
            display_name=editor.display_name,
            email=editor.email,
            role=session_role,
            owner_id=owner_id,
            is_active=editor.is_active,
            created_at=editor.created_at,
            last_login_at=editor.last_login_at,
        )
    )


@router.post("/owner-signup", response_model=SignupResponse, status_code=status.HTTP_202_ACCEPTED)
async def owner_signup(
    body: OwnerSignupRequest,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """
    Owner sign-up — step 1 of 2.

    Validates credentials and stores the signup in a pending table, then emails
    a verification link.  The account is not created until the user clicks the link.
    Returns 202 whether or not the email was sent (to avoid user enumeration).
    """
    _require_smtp_or_dev()
    _validate_signup_credentials(db, body.password, body.email)

    editor_id = _derive_editor_id(body.email, db)
    display_name = body.display_name or editor_id

    now = datetime.now(timezone.utc)
    db.query(AuthPendingOwner).filter(
        AuthPendingOwner.email == body.email
    ).delete(synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    pending = AuthPendingOwner(
        token=raw_token,
        editor_id=editor_id,
        display_name=display_name,
        email=body.email,
        password_hash=hash_password(body.password),
        expires_at=(now + timedelta(hours=_EMAIL_VERIFY_TOKEN_TTL_HOURS)).isoformat(),
        created_at=now.isoformat(),
    )
    db.add(pending)
    db.commit()

    verify_url = _build_verify_url(request, raw_token, "/verify-owner-email")
    logger.info(f"Owner signup pending email verification: {editor_id} <{body.email}>")

    emailed = await _send_verification_email(body.email, display_name, verify_url)
    if not emailed:
        logger.warning(f"Owner verification email not sent for {editor_id}. Link: {verify_url}")

    return SignupResponse(
        detail="Check your email for a verification link to complete account creation.",
        emailed=emailed,
    )


@router.post("/verify-owner-email", response_model=TokenResponse)
def verify_owner_email(
    token: str,
    response: Response,
    db: Session = Depends(get_system_db),
):
    """
    Owner sign-up — step 2 of 2.

    Validates the email verification token, promotes the pending signup to a real
    auth_editors row, initializes the owner's database, and issues JWT cookies.
    """
    pending = _consume_pending_token(db, AuthPendingOwner, token)

    now = datetime.now(timezone.utc).isoformat()
    editor = AuthEditor(
        editor_id=pending.editor_id,
        display_name=pending.display_name,
        email=pending.email,
        role="owner",
        password_hash=pending.password_hash,
        owner_id=pending.editor_id,
        is_active=True,
        created_at=now,
        last_login_at=now,
    )
    db.add(editor)
    db.delete(pending)
    db.commit()
    db.refresh(editor)

    from database.db import get_engine
    get_engine(editor.editor_id)

    logger.info(f"Owner email verified and account created: {editor.editor_id}")

    _set_auth_cookies(response, editor.editor_id, editor.editor_id, "owner")
    return TokenResponse(
        editor=EditorResponse(
            editor_id=editor.editor_id,
            display_name=editor.display_name,
            email=editor.email,
            role=editor.role,
            owner_id=editor.editor_id,
            is_active=editor.is_active,
            created_at=editor.created_at,
            last_login_at=editor.last_login_at,
        )
    )


async def _resend_verification(
    db: Session,
    request: Request,
    pending_model,
    email: str,
    ttl_hours: int,
    page_path: str,
    email_role: str = "Owner",
    owner_display_name: Optional[str] = None,
    log_tag: str = "",
) -> bool:
    """Shared resend logic for owner and contributor verification emails."""
    pending = db.query(pending_model).filter(pending_model.email == email).first()
    if not pending:
        return False

    pending.token = secrets.token_urlsafe(32)
    pending.expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    db.commit()

    verify_url = _build_verify_url(request, pending.token, page_path)
    emailed = await _send_verification_email(
        pending.email, pending.display_name, verify_url,
        role=email_role, owner_display_name=owner_display_name,
    )
    if not emailed:
        logger.warning(f"Resend {log_tag} verification email failed for {email}. Link: {verify_url}")
    return emailed


@router.post("/resend-owner-verification", response_model=SignupResponse)
async def resend_owner_verification(
    email: str,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """
    Resend the email verification link for a pending owner signup.
    Silently succeeds if the email is not found (to avoid enumeration).
    """
    emailed = await _resend_verification(
        db, request, AuthPendingOwner, email,
        ttl_hours=_EMAIL_VERIFY_TOKEN_TTL_HOURS,
        page_path="/verify-owner-email",
        log_tag="owner",
    )
    return SignupResponse(
        detail="If that email has a pending signup, a new verification link has been sent.",
        emailed=emailed,
    )


@router.post("/resend-contributor-verification", response_model=SignupResponse)
async def resend_contributor_verification(
    email: str,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """
    Resend the email verification link for a pending contributor signup.
    Silently succeeds if the email is not found (to avoid enumeration).
    """
    pending = db.query(AuthPendingContributor).filter(AuthPendingContributor.email == email).first()
    owner_display_name = None
    if pending:
        owner = db.query(AuthEditor).filter(AuthEditor.editor_id == pending.owner_id).first()
        owner_display_name = owner.display_name if owner else None

    emailed = await _resend_verification(
        db, request, AuthPendingContributor, email,
        ttl_hours=_CONTRIBUTOR_VERIFY_TOKEN_TTL_HOURS,
        page_path="/verify-contributor-email",
        email_role="Contributor",
        owner_display_name=owner_display_name,
        log_tag="contributor",
    )
    return SignupResponse(
        detail="If that email has a pending signup, a new verification link has been sent.",
        emailed=emailed,
    )


@router.post("/contributor-signup", response_model=SignupResponse, status_code=status.HTTP_202_ACCEPTED)
async def contributor_signup(
    body: ContributorSignupRequest,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """
    Contributor self-signup — step 1 of 2.

    Validates credentials, checks the target owner exists, then stores a pending row
    and emails a verification link.  The account is not created until the user clicks
    the link (step 2).  Returns 202 regardless to prevent user enumeration.
    """
    _require_smtp_or_dev()

    owner = db.query(AuthEditor).filter(
        AuthEditor.editor_id == body.owner_id,
        AuthEditor.role == "owner",
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Tree owner not found")

    _validate_signup_credentials(db, body.password, body.email)

    editor_id = _derive_editor_id(body.email, db)
    display_name = body.display_name or editor_id

    now = datetime.now(timezone.utc)
    db.query(AuthPendingContributor).filter(
        AuthPendingContributor.email == body.email,
        AuthPendingContributor.owner_id == body.owner_id,
    ).delete(synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    pending = AuthPendingContributor(
        token=raw_token,
        editor_id=editor_id,
        display_name=display_name,
        email=body.email,
        password_hash=hash_password(body.password),
        owner_id=body.owner_id,
        message=body.message,
        expires_at=(now + timedelta(hours=_CONTRIBUTOR_VERIFY_TOKEN_TTL_HOURS)).isoformat(),
        created_at=now.isoformat(),
    )
    db.add(pending)
    db.commit()

    verify_url = _build_verify_url(request, raw_token, "/verify-contributor-email")
    logger.info(f"Contributor signup pending email verification: {editor_id} <{body.email}> for owner {body.owner_id}")

    emailed = await _send_verification_email(
        body.email, display_name, verify_url,
        role="Contributor", owner_display_name=owner.display_name,
    )
    if not emailed:
        logger.warning(f"Contributor verification email not sent for {editor_id}. Link: {verify_url}")

    return SignupResponse(
        detail="Check your email for a verification link to complete your contributor request.",
        emailed=emailed,
    )


@router.post("/verify-contributor-email", response_model=TokenResponse)
def verify_contributor_email(
    token: str,
    db: Session = Depends(get_system_db),
):
    """
    Contributor self-signup — step 2 of 2.

    Validates the email verification token, creates an inactive AuthEditor row and
    an AuthEditorTree row.  The account is NOT activated and no cookies are issued —
    the contributor must wait for the owner to approve in User Manager.
    """
    pending = _consume_pending_token(db, AuthPendingContributor, token)

    now = datetime.now(timezone.utc).isoformat()
    editor = AuthEditor(
        editor_id=pending.editor_id,
        display_name=pending.display_name,
        email=pending.email,
        role="contributor",
        password_hash=pending.password_hash,
        owner_id=None,
        is_active=False,  # not active until owner approves
        created_at=now,
        message=pending.message,
    )
    db.add(editor)
    db.add(AuthEditorTree(editor_id=pending.editor_id, owner_id=pending.owner_id, is_active=False))
    db.delete(pending)
    db.commit()

    logger.info(f"Contributor email verified, awaiting owner approval: {editor.editor_id} for tree {pending.owner_id}")

    return TokenResponse(
        editor=EditorResponse(
            editor_id=editor.editor_id,
            display_name=editor.display_name,
            email=editor.email,
            role=editor.role,
            owner_id=pending.owner_id,
            is_active=False,
        )
    )


class ShareInfo(BaseModel):
    owner_id: str
    display_name: str


@router.get("/share-info", response_model=ShareInfo)
def get_share_info(
    share: str,
    db: Session = Depends(get_system_db),
):
    """Return owner_id and display_name for a share token (no auth required)."""
    from database.system_models import AuthShareToken
    from datetime import timedelta
    token_row = db.query(AuthShareToken).filter(
        AuthShareToken.token == share,
        AuthShareToken.is_active == True,
    ).first()
    if not token_row:
        raise HTTPException(status_code=404, detail="Share token not found or revoked")

    anchor = token_row.last_used_at or token_row.created_at
    expiry = datetime.fromisoformat(anchor) + timedelta(days=token_row.expires_after_days)
    if datetime.now(timezone.utc) > expiry:
        raise HTTPException(status_code=404, detail="Share token has expired")

    owner = db.query(AuthEditor).filter(AuthEditor.editor_id == token_row.owner_id).first()
    display_name = owner.display_name if owner else token_row.owner_id
    return ShareInfo(owner_id=token_row.owner_id, display_name=display_name)


@router.get("/public-config", response_model=PublicConfig)
def get_public_config():
    """Return public configuration for the frontend (no auth required)."""
    return PublicConfig(
        admin_email=settings.admin_email,
        signup_enabled=settings.allow_registration,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_system_db),
):
    """Exchange refresh token for a new access token (silent re-auth)."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = _decode_token(refresh_token, _REFRESH_TOKEN_TYPE)
    editor_id = payload["sub"]
    owner_id = payload["owner_id"]
    role = payload["role"]

    editor = db.query(AuthEditor).filter(
        AuthEditor.editor_id == editor_id,
        AuthEditor.is_active == True,
    ).first()
    if not editor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    _set_auth_cookies(response, editor_id, owner_id, role)
    return TokenResponse(
        editor=EditorResponse(
            editor_id=editor.editor_id,
            display_name=editor.display_name,
            email=editor.email,
            role=role,
            owner_id=owner_id,
            is_active=editor.is_active,
            created_at=editor.created_at,
            last_login_at=editor.last_login_at,
        )
    )


@router.post("/logout")
def logout(response: Response):
    """Clear auth cookies."""
    _clear_auth_cookies(response)
    return {"detail": "Logged out"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    session: EditorSession = Depends(get_current_editor),
    db: Session = Depends(get_system_db),
):
    """Change own password. Requires current password verification."""
    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == session.editor_id).first()
    if not editor or not editor.password_hash:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, editor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    validate_password_strength(body.new_password)
    editor.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": "Password changed successfully"}


@router.patch("/profile", response_model=EditorResponse)
def update_profile(
    body: UpdateProfileRequest,
    session: EditorSession = Depends(get_current_editor),
    db: Session = Depends(get_system_db),
):
    """Update own profile (display name)."""
    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == session.editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="User not found")

    editor.display_name = body.display_name
    db.commit()
    return EditorResponse(
        editor_id=editor.editor_id,
        display_name=editor.display_name,
        email=editor.email,
        role=editor.role,
        owner_id=editor.owner_id or editor.editor_id,
        is_active=editor.is_active,
        created_at=editor.created_at,
        last_login_at=editor.last_login_at,
    )


@router.post("/set-password", response_model=TokenResponse)
def set_password(
    body: SetPasswordRequest,
    response: Response,
    db: Session = Depends(get_system_db),
):
    """
    Complete contributor account setup via one-time token.
    Contributor chooses their editor_id and password here.
    """
    token_row = db.query(AuthSetPasswordToken).filter(
        AuthSetPasswordToken.token == body.token,
        AuthSetPasswordToken.used_at == None,
    ).first()
    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or already used token")

    expires = datetime.fromisoformat(token_row.expires_at)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Token has expired")

    # Check new editor_id is not taken
    existing = db.query(AuthEditor).filter(AuthEditor.editor_id == body.editor_id).first()
    if existing and existing.editor_id != token_row.editor_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.editor_id}' is already taken — please choose another",
        )

    # Get the pre-created editor row (placeholder created at approval time)
    editor = db.query(AuthEditor).filter(AuthEditor.editor_id == token_row.editor_id).first()
    if not editor:
        raise HTTPException(status_code=404, detail="Account not found")

    # Update editor with chosen username/password
    if body.editor_id != token_row.editor_id:
        # Rename: update all references
        db.query(AuthEditorTree).filter(
            AuthEditorTree.editor_id == token_row.editor_id
        ).update({"editor_id": body.editor_id})
        db.query(AuthSetPasswordToken).filter(
            AuthSetPasswordToken.editor_id == token_row.editor_id
        ).update({"editor_id": body.editor_id})
        editor.editor_id = body.editor_id

    validate_password_strength(body.password)
    editor.display_name = body.display_name
    editor.email = body.email
    editor.password_hash = hash_password(body.password)
    token_row.used_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(editor)

    # Determine owner_id for session (from token hint or first accessible tree)
    owner_id = token_row.owner_id
    if not owner_id:
        tree = db.query(AuthEditorTree).filter(
            AuthEditorTree.editor_id == editor.editor_id
        ).first()
        owner_id = tree.owner_id if tree else editor.editor_id

    # Only issue cookies if the account is active. Inactive contributors (awaiting owner
    # approval) must not receive a session — they'll get cookies after the owner activates.
    if editor.is_active:
        _set_auth_cookies(response, editor.editor_id, owner_id, editor.role)
    return TokenResponse(
        editor=EditorResponse(
            editor_id=editor.editor_id,
            display_name=editor.display_name,
            email=editor.email,
            role=editor.role,
            owner_id=owner_id,
            is_active=editor.is_active,
            created_at=editor.created_at,
        )
    )
