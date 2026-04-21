# Auth System — As-Built (OCV Model)

> This document supersedes the original design proposal.  
> It describes the **Owner / Contributor / Viewer (OCV)** system that was implemented.

---

## Table of Contents

1. [Roles](#roles)
2. [Global Auth Database](#global-auth-database)
3. [API Endpoints](#api-endpoints)
4. [Token Strategy](#token-strategy)
5. [Contributor Attribution](#contributor-attribution)
6. [Owner Resolution per Request](#owner-resolution-per-request)
7. [Flows](#flows)

---

## Roles

| Role | Description | Auth method |
|------|-------------|-------------|
| **Owner** | Owns a genealogy tree under `datasets/<owner_id>/`. Full read-write-delete access. Can invite contributors and manage share tokens. | Password + JWT (HttpOnly cookie) |
| **Contributor** | Invited editor. Can create and edit their own records; cannot delete or edit other contributors' records. Attributed via `created_by` / `created_at`. | Password + JWT (HttpOnly cookie) |
| **Viewer** | Anonymous read-only access via a share link (`?share=<token>`). No login required; no write access. | Share token in URL query string |

In `NOVOTREE_APP_MODE=admin` (local development), all auth is bypassed and the process acts as the default owner (`aktiniya`).

---

## Global Auth Database

`datasets/system.sqlite` — completely separate from each owner's `data.sqlite`.

```
project_root/
└── datasets/
    ├── system.sqlite              ← Global auth database (NEVER commit to git)
    ├── aktiniya/
    │   ├── data.sqlite            ← Owner genealogy data
    │   └── media/
    └── <other_owner>/
        ├── data.sqlite
        └── media/
```

### Tables

#### `auth_editors` — all authenticated users (owners + contributors)

| Column | Type | Notes |
|--------|------|-------|
| `editor_id` | TEXT PK | Chosen username (login name) |
| `display_name` | TEXT | Human-readable name |
| `email` | TEXT | Optional; used for SMTP invites |
| `role` | TEXT | `'owner'` or `'contributor'` |
| `owner_id` | TEXT | For owners: equals `editor_id`. For contributors: NULL (trees via `auth_editor_trees`). |
| `password_hash` | TEXT | bcrypt hash; NULL until set-password flow completes |
| `is_active` | BOOL | Owner can deactivate a contributor |
| `created_at` | TEXT | ISO-8601 UTC |
| `last_login_at` | TEXT | ISO-8601 UTC |

#### `auth_editor_trees` — contributor → tree access grants

| Column | Type | Notes |
|--------|------|-------|
| `editor_id` | TEXT | FK → auth_editors.editor_id |
| `owner_id` | TEXT | Which tree they can access |

UNIQUE on (`editor_id`, `owner_id`). A contributor can have access to multiple trees.

#### `auth_share_tokens` — viewer share links

| Column | Type | Notes |
|--------|------|-------|
| `token` | TEXT | URL-safe random token (32 bytes) |
| `owner_id` | TEXT | Which tree this opens |
| `label` | TEXT | Human-readable name (e.g. "Family reunion 2026") |
| `is_active` | BOOL | Owner can revoke |
| `expires_after_days` | INT | Default 90. Rolling expiry anchored on `last_used_at`. |
| `created_at` | TEXT | ISO-8601 UTC |
| `last_used_at` | TEXT | ISO-8601 UTC; updated on each use (rolling window) |

#### `auth_pending_contributors` — email-verification holding area for contributor signups

| Column | Type | Notes |
|--------|------|-------|
| `token` | TEXT | URL-safe random token (32 bytes), unique |
| `editor_id` | TEXT | Derived from email local part, unique |
| `display_name` | TEXT | |
| `email` | TEXT | |
| `password_hash` | TEXT | bcrypt hash, computed at signup time |
| `owner_id` | TEXT | Which tree they want to contribute to |
| `message` | TEXT | Optional note to the owner |
| `expires_at` | TEXT | ISO-8601 UTC; 24-hour TTL |
| `created_at` | TEXT | ISO-8601 UTC |

Row is deleted once the verification link is clicked and the account is promoted to `auth_editors` (inactive, awaiting owner approval).

#### `auth_pending_owners` — email-verification holding area for new owner signups

| Column | Type | Notes |
|--------|------|-------|
| `token` | TEXT | URL-safe random token (32 bytes), unique |
| `editor_id` | TEXT | Chosen username, unique |
| `display_name` | TEXT | |
| `email` | TEXT | |
| `password_hash` | TEXT | bcrypt hash, computed at signup time |
| `expires_at` | TEXT | ISO-8601 UTC; 1-hour TTL |
| `created_at` | TEXT | ISO-8601 UTC |

Row is deleted once the verification link is clicked and the account is promoted to `auth_editors`. Stale rows (expired but unclicked) are cleaned up on the next signup attempt for the same username or email.

#### `auth_set_password_tokens` — one-time onboarding / reset tokens

| Column | Type | Notes |
|--------|------|-------|
| `token` | TEXT | URL-safe random token (32 bytes) |
| `editor_id` | TEXT | Placeholder editor created at approval |
| `owner_id` | TEXT | Target tree hint (used to build session after set-password) |
| `expires_at` | TEXT | ISO-8601 UTC (7-day TTL) |
| `used_at` | TEXT | ISO-8601 UTC; NULL = not yet used |

---

## API Endpoints

### Authentication (`/auth/*`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/me` | Cookie | Return current editor identity |
| POST | `/auth/login` | — | Login with `editor_id` + `password`; sets HttpOnly cookies |
| POST | `/auth/owner-signup` | — | Owner self-registration — stores pending row and sends verification email |
| POST | `/auth/verify-owner-email?token=` | — | Complete owner signup after email verification |
| POST | `/auth/resend-owner-verification?email=` | — | Resend owner verification email |
| POST | `/auth/contributor-signup` | — | Contributor self-signup — stores pending row and sends verification email |
| POST | `/auth/verify-contributor-email?token=` | — | Complete contributor signup (creates inactive account, awaits owner approval) |
| POST | `/auth/refresh` | Refresh cookie | Silently re-issue access token |
| POST | `/auth/logout` | Cookie | Clear auth cookies |
| POST | `/auth/change-password` | Cookie | Change own password |
| POST | `/auth/set-password` | — | Complete contributor account setup via one-time token |

### User management (`/users/*`, owner-only except where noted)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/share-tokens` | Owner | List active share tokens |
| POST | `/users/share-tokens` | Owner | Create share token |
| DELETE | `/users/share-tokens/{id}` | Owner | Revoke share token |
| GET | `/users/contributors` | Owner | List contributors for this tree |
| POST | `/users/contributors/set-active` | Owner | Activate / deactivate contributor |
| POST | `/users/contributors/reset-password` | Owner | Generate new set-password link (emails if SMTP configured) |
| POST | `/users/contributors/{editor_id}/activate` | Owner | Approve pending contributor (sets active + sends notification) |
| DELETE | `/users/contributors/{editor_id}` | Owner | Delete contributor (only if no contributions) |
| GET | `/users/owner-info?owner_id=` | **Public** | Return `{owner_id, display_name}` for a tree owner |

---

## Password Policy

All new-password flows (signup, contributor set-password, change-password) enforce the same rules on both frontend (Zod) and backend (FastAPI):

| Rule | Value |
|------|-------|
| Minimum length | 8 characters |
| Uppercase letter | at least one (`[A-Z]`) |
| Lowercase letter | at least one (`[a-z]`) |
| Digit | at least one (`[0-9]`) |
| Special character | not required |

**Rationale for this project:** NovoTree is a private family genealogy app with invited contributors — not a financial or medical system. The audience includes non-technical family members for whom special-character requirements cause friction (forgotten passwords, lockouts) without meaningful security gain. NIST SP 800-63B explicitly recommends against mandatory complexity rules in favour of length; uppercase + lowercase + digit at 8 characters is a solid baseline against dictionary attacks for this threat model. If stricter security is ever needed, increasing the minimum length to 12 is more effective than adding a special-character requirement.

---

## Token Strategy

### Access + refresh cookie pair

| Cookie | Lifetime | Notes |
|--------|----------|-------|
| `access_token` | 8 h | JWT signed with `JWT_SECRET_KEY`. Payload: `sub` (editor_id), `owner_id`, `role`, `type`, `exp`. |
| `refresh_token` | 14 days | Same shape. Silent re-issue via `POST /auth/refresh`. |

Both cookies: `HttpOnly=true`, `Secure=true` (production), `SameSite=Strict`.  
No token is ever stored in `localStorage` or `sessionStorage` on the authenticated side.

### Share token (viewer)

`?share=<token>` passed as a URL query parameter.  
The frontend persists it in `sessionStorage` for the duration of the browser session.  
Backend middleware validates it on each request and applies a rolling 90-day expiry.  
All write methods (`POST/PUT/PATCH/DELETE`) are blocked for share-token sessions.

---

## Contributor Attribution

Every mutable table (`main_individuals`, `main_families`, `main_individual_names`, `main_events`, `main_media`) has:

| Column | Description |
|--------|-------------|
| `created_by` | `editor_id` of the creator |
| `created_at` | ISO-8601 UTC timestamp |

Contributors may only edit records where `created_by == their editor_id`. Owners may edit any record. Neither may be deleted by a contributor.

---

## Owner Resolution per Request

Every request carries its `owner_id` through FastAPI's dependency injection chain — there is no global active-owner state.

```
Request arrives
       │
       ├─ NOVOTREE_APP_MODE=admin → use DEFAULT_OWNER_ID (dev bypass)
       │
       ├─ access_token cookie present → decode JWT → extract owner_id
       │
       └─ ?share=<token> → look up in auth_share_tokens → extract owner_id
               │
               └─ (write methods blocked for share sessions)

owner_id → get_engine(owner_id)  ← cached in pool; created on first use
         → per-request Session   ← opened/closed within the request lifecycle
```

### Dependency chain (FastAPI)

```
get_current_editor()        ← decodes JWT, returns EditorSession(owner_id=...)
    └─ get_tree_db()        ← yields Session for owner's data.sqlite
    └─ get_tree_owner_info() ← returns OwnerInfo (paths for owner's files)

get_viewer_owner_id()       ← resolves owner_id from JWT or share token
    └─ get_viewer_tree_db() ← yields Session (read-only endpoints, tree/media)
    └─ get_viewer_owner_info()
```

Multiple owners can be served simultaneously — each request opens a session from its own engine. Engines are cached in `_pool: dict[str, Engine]` and never shared across owners.

---

## Flows

### Owner signup
1. `POST /auth/owner-signup` → validates credentials → creates `auth_pending_owners` row (1-hour TTL) → sends verification email → returns 202.
2. User clicks link in email → `POST /auth/verify-owner-email?token=<token>` → promotes pending row to `auth_editors` (role=owner) → calls `get_engine(owner_id)` to initialise the owner's DB → sets JWT cookies → redirect to Dashboard.

### Contributor self-signup
1. Visitor sees tree via share link → clicks "Wanna contribute to this tree?" button.
2. Fills in signup form (display name, email, password, optional message to owner).
3. `POST /auth/contributor-signup` — validates credentials, checks owner exists, creates `auth_pending_contributors` row (24-hour TTL) → sends verification email → returns 202.
4. Visitor clicks link in email → `POST /auth/verify-contributor-email?token=<token>` → creates inactive `auth_editors` row (role=contributor) + `auth_editor_trees` row. No cookies issued.
5. Visitor sees "Awaiting owner approval" screen.
6. Owner opens User Manager → Contributors tab → "Awaiting approval" section → clicks Approve.
7. `POST /users/contributors/{editor_id}/activate` → sets `is_active=True` → sends notification email to contributor.
8. Contributor logs in normally.

### Contributor login (multiple trees)
`POST /auth/login` checks how many trees the editor can access:
- **1 tree (owner or contributor)**: logs in directly, no picker.
- **Multiple trees**: returns HTTP 300 with `{trees: [{owner_id, display_name, role}]}`. Frontend shows tree picker; user selects one; login re-submitted with `owner_id`. Role in JWT reflects relationship to chosen tree (`owner` for own tree, `contributor` otherwise).

### Password reset (owner-initiated)
Owner opens User Manager → Contributors tab → Reset Password for a contributor.  
`POST /users/contributors/reset-password` → creates new `auth_set_password_tokens` row → emails link or shows it in UI.
