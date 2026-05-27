"""
SQLAlchemy ORM models for the global auth / system database (datasets/system.sqlite).

Tables:
- auth_editors             : all authenticated users (owners + contributors)
- auth_editor_trees        : contributor → owner_id access grants (many-to-many)
- auth_share_tokens        : viewer share links with rolling 90-day expiry
- auth_share_consents      : per-share-create acknowledgement audit log (Privacy §2.5)
- auth_pending_owners      : email-verification staging for owner signups (1-hour TTL)
- auth_pending_contributors: email-verification staging for contributor self-signups (24-hour TTL)
- auth_set_password_tokens : one-time tokens for contributor onboarding / password reset
- auth_invitations         : legacy invitation records (kept for data; no longer used by UI)
- takedown_requests        : public "remove me" requests (Privacy §2.2)
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
    message = Column(String, nullable=True)         # optional intro note from contributor signup

    created_at = Column(String, nullable=True)      # ISO-8601 UTC
    last_login_at = Column(String, nullable=True)   # ISO-8601 UTC


class AuthEditorTree(SystemBase):
    """
    Grants a contributor access to a specific owner's tree.
    is_active is per-tree: one owner can freeze a contributor without affecting other trees.
    """

    __tablename__ = "auth_editor_trees"
    __table_args__ = (
        UniqueConstraint("editor_id", "owner_id", name="uq_editor_tree"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    editor_id = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)  # per-tree freeze/unfreeze


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


class AuthShareConsent(SystemBase):
    """
    Per-share-create acknowledgement (Privacy §2.5, PRIVACY_ANALYSIS.md M-03 / §9.4).
    One row written every time an Owner confirms the share-link modal. Defensive
    audit log: evidence that the Owner accepted responsibility for what they
    shared at the moment the link was issued.

    `share_token_id` is nullable for forward-compatibility with a future
    "extend visibility" action that would re-acknowledge an existing token
    without creating a new one — not exercised today (no extend endpoint
    exists). `privacy_policy_version` records which policy version was in
    force at acceptance; preferred over `tos_version` because Mode A ships
    no ToS — the policy is the only legal document the modal text leans on.
    """

    __tablename__ = "auth_share_consents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    editor_id = Column(String, nullable=False)            # who clicked accept (always the Owner today)
    tree_owner_id = Column(String, nullable=False)        # which tree the share grants access to
    share_token_id = Column(Integer, nullable=True)       # FK→auth_share_tokens.id; NULL reserved for future extend flow
    accepted_at = Column(String, nullable=False)          # ISO-8601 UTC
    accepted_ip = Column(String, nullable=False)          # client IP at acceptance (best-effort, behind CF/proxy)
    privacy_policy_version = Column(String, nullable=False)


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


class TakedownRequest(SystemBase):
    """
    Public "remove me from a tree" request (GDPR Art. 17). Submitted via the
    unauthenticated POST /privacy/takedown endpoint and reviewed by the tree
    owner. See docs/PRIVACY_DESIGN.md §2.2 and PRIVACY_ANALYSIS.md M-04.

    Status transitions:
      open → acknowledged → resolved
      open → escalated  (auto, after takedown_sla_days)
    """

    __tablename__ = "takedown_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tree_owner_id = Column(String, nullable=False)        # which owner's tree the request targets
    individual_id = Column(String, nullable=True)         # optional pointer if requester knows the ID
    requester_name = Column(String, nullable=False)
    requester_email = Column(String, nullable=False)
    requester_phone = Column(String, nullable=True)       # optional; aids identity verification
    message = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")  # 'open'|'acknowledged'|'resolved'|'escalated'
    created_at = Column(String, nullable=False)           # ISO-8601 UTC
    resolved_at = Column(String, nullable=True)           # ISO-8601 UTC; set when status reaches resolved/escalated

    # Sweeper bookkeeping — see backend/api/privacy.py:_sweep_takedowns().
    # `RETURNING id` on UPDATE … WHERE … IS NULL gives first-writer-wins idempotency
    # so the in-process loop and the standalone scheduled-jobs backstop can both run
    # safely without double-sending mail.
    reminder_sent_at = Column(String, nullable=True)      # ISO-8601 UTC; day-14 reminder
    escalated_at = Column(String, nullable=True)          # ISO-8601 UTC; SLA-day auto-escalation


class AuthPendingContributor(SystemBase):
    """
    Temporary holding area for contributor self-signups awaiting email verification.
    After verification the row is promoted to an inactive auth_editors row (is_active=False)
    and an auth_editor_trees row granting access to the target owner's tree.
    The owner then sees the request in User Manager and can approve (activate) or reject (delete).
    Expires after 24 hours.
    """

    __tablename__ = "auth_pending_contributors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, nullable=False, unique=True)   # URL-safe random token (32 bytes)
    editor_id = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)        # already hashed at signup time
    owner_id = Column(String, nullable=False)             # which tree they want to contribute to
    message = Column(String, nullable=True)               # optional intro message
    expires_at = Column(String, nullable=False)           # ISO-8601 UTC; 24-hour TTL
    created_at = Column(String, nullable=False)           # ISO-8601 UTC
