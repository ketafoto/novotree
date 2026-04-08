"""
Authentication and user management API.

Terminology:
- editor: any authenticated user (owner or contributor)
- owner: an editor who owns a tree under datasets/<owner_id>/
- contributor: an editor invited to contribute to one or more owner trees
- viewer: anonymous read-only access via share token in URL

In APP_MODE=admin (local dev), all auth is bypassed — the default owner is
auto-resolved without requiring login.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from database.system_db import get_system_db
from database.system_models import AuthEditor, AuthEditorTree, AuthSetPasswordToken

logger = logging.getLogger("gedcom.auth")

# Default owner used in dev bypass mode
DEFAULT_OWNER_ID = "inovoseltsev"

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
    editor_id: str
    password: str
    owner_id: Optional[str] = None  # required for contributors with multiple trees


class SignupRequest(BaseModel):
    editor_id: str
    display_name: str
    password: str
    email: Optional[str] = None


class SetPasswordRequest(BaseModel):
    token: str
    editor_id: str          # contributor chooses username at this step
    display_name: str
    password: str
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    editor: EditorResponse


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


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
    secure = not settings.is_dev
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
    """Auto-authenticated session for APP_MODE=admin."""
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

    # Try authenticated session first
    if access_token:
        try:
            payload = _decode_token(access_token, _ACCESS_TOKEN_TYPE)
            return payload["owner_id"]
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
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_system_db),
):
    """Login with editor_id + password. Returns editor info and sets HttpOnly cookies."""
    editor = db.query(AuthEditor).filter(
        AuthEditor.editor_id == body.editor_id,
        AuthEditor.is_active == True,
    ).first()

    if not editor or not editor.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, editor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Determine owner_id for this session
    if editor.role == "owner":
        owner_id = editor.owner_id or editor.editor_id
    else:
        # Contributor: resolve which tree to open
        trees = db.query(AuthEditorTree).filter(
            AuthEditorTree.editor_id == editor.editor_id
        ).all()
        accessible = [t.owner_id for t in trees]

        if not accessible:
            raise HTTPException(status_code=403, detail="No trees available for this contributor")

        if body.owner_id:
            if body.owner_id not in accessible:
                raise HTTPException(status_code=403, detail="Access to this tree not granted")
            owner_id = body.owner_id
        elif len(accessible) == 1:
            owner_id = accessible[0]
        else:
            # Multiple trees — client must send owner_id in a second request
            raise HTTPException(
                status_code=status.HTTP_300_MULTIPLE_CHOICES,
                detail={"trees": accessible},
            )

    # Update last login
    editor.last_login_at = datetime.now(timezone.utc).isoformat()
    db.commit()

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
            last_login_at=editor.last_login_at,
        )
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    response: Response,
    db: Session = Depends(get_system_db),
):
    """
    Owner sign-up. Creates auth_editors row and initializes the owner's database.
    Reuses existing datasets/<owner_id>/ folder if present (safe for inovoseltsev).
    """
    # Uniqueness check
    existing = db.query(AuthEditor).filter(AuthEditor.editor_id == body.editor_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.editor_id}' is already taken",
        )

    now = datetime.now(timezone.utc).isoformat()
    editor = AuthEditor(
        editor_id=body.editor_id,
        display_name=body.display_name,
        email=body.email,
        role="owner",
        password_hash=hash_password(body.password),
        owner_id=body.editor_id,
        is_active=True,
        created_at=now,
        last_login_at=now,
    )
    db.add(editor)
    db.commit()
    db.refresh(editor)

    # Initialize owner's genealogy database (safe — CREATE TABLE IF NOT EXISTS)
    from database.db import init_db_once
    from database.owner_info import OwnerInfo
    init_db_once(OwnerInfo(owner_id=body.editor_id))

    logger.info(f"Owner signed up: {body.editor_id}")

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

    editor.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": "Password changed successfully"}


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
