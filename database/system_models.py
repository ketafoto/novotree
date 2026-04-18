"""
SQLAlchemy ORM models for the global auth / system database (datasets/system.sqlite).

Tables:
- auth_editors        : all authenticated users (owners + contributors)
- auth_editor_trees   : contributor → owner_id access grants (many-to-many)
- auth_share_tokens   : viewer share links with rolling 90-day expiry
- auth_invitations    : pending Contribute requests awaiting owner approval
- auth_set_password_tokens : one-time tokens for contributor onboarding / password reset
"""

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base


SystemBase = declarative_base()


class AuthEditor(SystemBase):
    """
    Every authenticated user — owners and contributors alike.

    role:
      - 'owner'       : owns a tree under datasets/<owner_id>/
      - 'contributor' : invited editor, granted access via AuthEditorTree rows
    """

    __tablename__ = "auth_editors"

    editor_id = Column(String, primary_key=True)  # chosen username
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, nullable=False, default="owner")  # 'owner' | 'contributor'

    # For owners: owner_id == editor_id (their own tree).
    # For contributors: NULL (their trees are in auth_editor_trees instead).
    owner_id = Column(String, nullable=True)

    password_hash = Column(String, nullable=True)  # NULL until set-password completed
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(String, nullable=True)      # ISO-8601 UTC
    last_login_at = Column(String, nullable=True)   # ISO-8601 UTC


class AuthEditorTree(SystemBase):
    """
    Grants a contributor access to a specific owner's tree.
    An owner can grant multiple contributors; a contributor can access multiple trees.
    """

    __tablename__ = "auth_editor_trees"
    __table_args__ = (
        UniqueConstraint("editor_id", "owner_id", name="uq_editor_tree"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    editor_id = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)


class AuthShareToken(SystemBase):
    """
    Viewer share link.  Accessing /tree?share=<token> opens the tree read-only
    without requiring a login.  Tokens have a rolling 90-day expiry.
    """

    __tablename__ = "auth_share_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String, nullable=False)        # which tree this token opens
    token = Column(String, nullable=False, unique=True)
    label = Column(String, nullable=True)            # human-readable name for the token
    is_active = Column(Boolean, nullable=False, default=True)
    expires_after_days = Column(Integer, nullable=False, default=90)

    created_at = Column(String, nullable=True)       # ISO-8601 UTC
    last_used_at = Column(String, nullable=True)     # ISO-8601 UTC (rolling anchor)


class AuthInvitation(SystemBase):
    """
    Pending 'Contribute' request submitted by a visitor.
    Owner sees these in the User Manager and can approve or reject.
    """

    __tablename__ = "auth_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String, nullable=False)        # which tree they want to contribute to
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    message = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # 'pending'|'approved'|'rejected'
    created_at = Column(String, nullable=True)       # ISO-8601 UTC
    resolved_at = Column(String, nullable=True)      # ISO-8601 UTC


class AuthSetPasswordToken(SystemBase):
    """
    One-time token emailed (or shown in UI) to a newly approved contributor.
    Also used for owner password-reset flows.
    """

    __tablename__ = "auth_set_password_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, nullable=False, unique=True)
    editor_id = Column(String, nullable=False)       # placeholder editor_id created at approval
    owner_id = Column(String, nullable=True)         # target tree (hint for session after set-password)
    expires_at = Column(String, nullable=False)      # ISO-8601 UTC
    used_at = Column(String, nullable=True)          # ISO-8601 UTC; NULL = not yet used


class AuthPendingOwner(SystemBase):
    """
    Temporary holding area for owner signups awaiting email verification.
    Row is deleted and promoted to auth_editors once the verification link is clicked.
    Expires after 1 hour — a background sweep or on-demand check removes stale rows.
    """

    __tablename__ = "auth_pending_owners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, nullable=False, unique=True)   # URL-safe random token (32 bytes)
    editor_id = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)        # already hashed at signup time
    expires_at = Column(String, nullable=False)           # ISO-8601 UTC; 1-hour TTL
    created_at = Column(String, nullable=False)           # ISO-8601 UTC
