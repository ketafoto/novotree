# Auth System — As-Built (OVC Model)

> This document supersedes the original design proposal.  
> It describes the **Owner / Viewer / Contributor (OVC)** system that was implemented.

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

In `NOVOTREE_APP_MODE=admin` (local development), all auth is bypassed and the process acts as the default owner (`inovoseltsev`).

---

## Global Auth Database

`datasets/system.sqlite` — completely separate from each owner's `data.sqlite`.

```
project_root/
└── datasets/
    ├── system.sqlite              ← Global auth database (NEVER commit to git)
    ├── inovoseltsev/
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

#### `auth_invitations` — pending Contribute requests

| Column | Type | Notes |
|--------|------|-------|
| `owner_id` | TEXT | Which tree the visitor wants to join |
| `display_name` | TEXT | Supplied by the visitor |
| `email` | TEXT | Optional |
| `message` | TEXT | Optional note from the visitor |
| `status` | TEXT | `'pending'` \| `'approved'` \| `'rejected'` |
| `created_at` | TEXT | ISO-8601 UTC |
| `resolved_at` | TEXT | ISO-8601 UTC |

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
| POST | `/auth/signup` | — | Owner self-registration |
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
| POST | `/users/invitations` | **Public** | Submit Contribute request (no auth) |
| GET | `/users/invitations` | Owner | List all Contribute requests |
| POST | `/users/invitations/{id}/approve` | Owner | Approve request → create contributor + set-password token |
| POST | `/users/invitations/{id}/reject` | Owner | Reject request |

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

owner_id → db.reset_engine() + db.init_db_once(OwnerInfo(owner_id))
```

---

## Flows

### Owner signup
`POST /auth/signup` → creates `auth_editors` row (role=owner) → calls `init_db_once()` → sets JWT cookies → redirect to Dashboard.

### Contributor invitation
1. Visitor sees tree via share link → clicks "Contribute" button.
2. `POST /users/invitations` (public) — stores pending invitation.
3. Owner opens User Manager → "Requests" tab → clicks Approve.
4. `POST /users/invitations/{id}/approve` — creates placeholder `auth_editors` row + `auth_editor_trees` row + `auth_set_password_tokens` row.
5. If SMTP configured: invitation email sent automatically. Otherwise: owner copies the set-password link from the UI.
6. Contributor opens `/set-password?token=<token>` — chooses username, display name, password.
7. `POST /auth/set-password` — sets password, marks token used, issues JWT cookies → redirect to tree.

### Contributor login (multiple trees)
If a contributor has access to more than one owner tree, `POST /auth/login` returns HTTP 300 with the list of accessible `owner_ids`. The frontend shows a tree selector on step 2; the user picks one, and the login request is re-submitted with `owner_id`.

### Password reset (owner-initiated)
Owner opens User Manager → Contributors tab → Reset Password for a contributor.  
`POST /users/contributors/reset-password` → creates new `auth_set_password_tokens` row → emails link or shows it in UI.
