# Contributor Permissions & Email Flows

This document describes the contributor access model: who can do what to the tree data,
how the contributor lifecycle is managed, and what emails are sent at each transition.

The underlying auth schema (tables, columns, JWT cookie strategy, signup endpoints)
is documented in [AUTH_SCHEMA_PROPOSAL.md](AUTH_SCHEMA_PROPOSAL.md). This document is
the source of truth for the contributor *behavior* — the lifecycle states, the
permission rules, and the email side-effects.

---

## 1. Roles

| Role | Description |
|------|-------------|
| **Owner** | The person who created the tree. Has full control over data and contributors. |
| **Contributor** | An authenticated user approved by the owner. Can add and edit their own records. |
| **Viewer** | Anonymous read-only access via a share token. No write capability. |

---

## 2. Contributor Lifecycle

```
 Sign-up request
       │
       ▼
   [PENDING]  ──── owner approves ────► [ACTIVE]
   (AuthEditor.is_active = False)        (both flags True)
   (AuthEditorTree.is_active = False)         │
                                              │ owner freezes
                                              │ or auto-freeze
                                              ▼
                                         [FROZEN]
                                   (AuthEditorTree.is_active = False,
                                    AuthEditor.is_active = True)
                                              │
                                              │ owner unfreezes
                                              ▼
                                         [ACTIVE] (again)
```

**Key distinction:** the login error message distinguishes PENDING from FROZEN:
- PENDING contributor (no login history) → "awaiting approval"
- FROZEN contributor (has login history) → "suspended"

Both states produce HTTP 403 on login; the UI shows the appropriate message.

**Immediate enforcement:** freezing a contributor invalidates their current session
immediately — `/auth/me` returns 401 without waiting for the JWT to expire.

---

## 3. CRUD Permissions

### Tree data (individuals, families, events, media)

| Action | Owner | Contributor |
|--------|-------|-------------|
| Create any record | ✅ | ✅ |
| Add event/media to any individual or family | ✅ | ✅ (even if created by owner) |
| Edit own records | ✅ | ✅ |
| Edit others' records | ✅ | ❌ → 403 |
| Delete own records | ✅ | ✅ |
| Delete others' records | ✅ | ❌ → 403 |

"Own" means the record's `created_by` field matches the contributor's `editor_id`.

### Contributor management (owner only)

| Action | Owner | Contributor |
|--------|-------|-------------|
| Approve pending contributor | ✅ | — |
| Freeze / unfreeze contributor | ✅ | — |
| Delete contributor (no contributions) | ✅ | — |
| Delete contributor with contributions | ❌ → 409 | — |

A contributor "has contributions" if they have at least one record in any of the four
tables: individuals, families, events, or media. The owner must manually remove those
records first before deleting the contributor account.

---

## 4. Email Notifications

All emails are sent only when SMTP is configured — i.e. when `SMTP_HOST` is set
in the environment file (the backend exposes this as the derived
`settings.smtp_enabled` property). In dev mode (`NOVOTREE_APP_MODE=admin`)
SMTP is typically not configured and emails are suppressed; one-time set-password
links are shown directly in the UI instead.

### 4.1 Manual transitions (triggered by owner action)

| Event | Recipient | Subject (approximate) |
|-------|-----------|----------------------|
| First approval (was PENDING) | Contributor | "Your Novotree contributor access has been approved" |
| Unfreeze (was FROZEN, now ACTIVE) | Contributor | "Your Novotree contributor access has been restored" |
| Freeze (was ACTIVE, now FROZEN) | Contributor | "Your Novotree contributor access has been suspended" |
| Delete (owner deletes account) | Contributor | "Your Novotree contributor access has been removed" |

**First approval vs. unfreeze:** both call the same `activate_contributor` endpoint, but
the email subject differs — "approved" if the contributor has never logged in (first
approval), "restored" if they have a login history (unfreeze).

### 4.2 Automatic cleanup (triggered on owner login)

The `cleanup_inactive_contributors` function runs every time an owner logs in and applies
two rules based on a **60-day inactivity window**:

| Rule | Condition | Action | Email sent |
|------|-----------|--------|------------|
| **Auto-freeze** | Contributor has contributions, but last edit is > 60 days ago, and account is currently active | Set `AuthEditorTree.is_active = False` | "Your contributor access has been automatically suspended due to 60 days of inactivity." |
| **Auto-delete** | Contributor has zero contributions and account is > 60 days old | Delete `AuthEditorTree` + `AuthEditor` rows | "Your contributor account has been automatically removed because no contributions were made within 60 days of account creation." |

Contributors who are still PENDING (never logged in) are skipped by the cleanup.

---

## 5. Data Model

```
AuthEditor                      AuthEditorTree
──────────────────────────      ────────────────────────────
editor_id   (PK)                editor_id  (FK → AuthEditor)
role        owner | contributor  owner_id   (FK → AuthEditor)
is_active   global flag         is_active  per-tree flag
last_login_at                   ──────────────────────────
```

Two separate `is_active` flags serve different purposes:

- `AuthEditor.is_active = False` → account disabled globally (used during PENDING state
  before first approval, so the login guard fires correctly).
- `AuthEditorTree.is_active = False` → access to a specific owner's tree revoked
  (FROZEN state). The global account remains active in case the contributor belongs to
  multiple trees.

---

## 6. Test Coverage

| Test class | What it verifies |
|------------|-----------------|
| `TestLoginMessages` | PENDING vs FROZEN error messages at login |
| `TestLinkInitialState` | `AuthEditorTree.is_active = False` at signup |
| `TestApproveEmail` | Email sent on approve / freeze / unfreeze / delete |
| `TestFreezeImmediateEnforcement` | Frozen session returns 401 without token expiry |
| `TestIndividualCreatedBy` | `created_by` attribution on create and list |
| `TestOwnerCannotDeleteContributorWithContributions` | 409 when contributor has any record type |
| `TestContributorCanAddRecords` | Contributor can create all record types |
| `TestContributorCanAddToOthersRecords` | Contributor can attach events/media to owner's records |
| `TestContributorEditOwnOnly` | Edit own → 200; edit other's → 403 (all 4 types) |
| `TestOwnerCanDeleteContributorsRecords` | Owner can delete any contributor record |
| `TestContributorDeleteOwnOnly` | Delete own → 200; delete other's → 403 (all 4 types) |

All tests live in `tests/backend/test_contributor.py`.
