# Privacy Implementation Plan

> **Companion to [PRIVACY_HANDLING.md](PRIVACY_HANDLING.md).**
> That document is the *what and why* (concerns, mitigations, legal text).
> This document is the *when and how* — a tiered implementation checklist
> that tracks progress and provides enough context to resume work in a
> fresh conversation.

**Status overall: NOT STARTED.** Privacy implementation has not begun.
Foundation documents are in place; code work is queued behind other roadmap
items in [notes.txt](notes.txt).

---

## 1. Context for a fresh session

If you are picking this up from scratch, read in this order:

1. [PRIVACY_HANDLING.md](PRIVACY_HANDLING.md) — concerns inventory, mitigations,
   concern↔mitigation matrix, and draft legal texts.
2. This file — tiered checklist + central config draft + decisions made so far.
3. [AUTH_SCHEMA_PROPOSAL.md](AUTH_SCHEMA_PROPOSAL.md) — auth tables/endpoints
   that several privacy items extend.
4. [CONTRIBUTOR_FEATURE.md](CONTRIBUTOR_FEATURE.md) — contributor lifecycle
   that some privacy items add acknowledgements to.

### Key product framing — two real deployment modes

NovoTree has only two practical deployment modes:

- **Mode A — Private / read-only.** Single owner (the operator). Owner and
  contributor signups disabled. Share links to relatives still work; assume
  any link can be forwarded → effectively public. Therefore Mode A still
  needs takedown, viewer notice, audit trail, right-of-access export.
- **Mode B — Public service.** Open owner and contributor signups. Local-first
  desktop app is the headline privacy upgrade.

Tier 1 + Tier 2 below get Mode A defensible. Tier 3 unlocks Mode B.

### Decisions already made

| Decision | Value |
|---|---|
| Cookie posture | Strictly-necessary auth cookies only. **No** consent banner — only a notice. (ePrivacy Art. 5(3) exemption.) |
| Analytics provider | **Cloudflare Web Analytics** (cookieless, free). GA4 was previously embedded; **removed** from `frontend/index.html`, `novospace/index.html`, `novospace/novoface/index.html`. |
| Hosting | Hetzner CX22 (EEA, Falkenstein/Helsinki) behind Cloudflare Free. One US sub-processor (Cloudflare LLC) to disclose. |
| Audience legal context | Majority IL + US. Israel has EU adequacy decision (2011). US state laws lighter than GDPR. |
| Owner-as-controller framing | NovoTree = processor; Owner = data controller for the tree's contents (standard SaaS posture). |
| Children's age threshold | 16 (most conservative across EU member states). |
| Takedown SLA | 30 days. |
| Backup retention | 30 days. |

### Required action before Tier 1 work begins

- [ ] Pay for one hour of legal review with a lawyer in the operating
      jurisdiction. Use the open questions in
      [PRIVACY_HANDLING.md §10](PRIVACY_HANDLING.md#10-open-questions-for-legal-review)
      as the agenda. Item-by-item resolution feeds the texts and SLAs below.

---

## 2. Tier 1 — Now (Mode A hardening)

Goal: make the current shareable-link deployment defensible. Do not require
contributor signups or full ToS machinery. Roughly ordered by ratio of
risk-reduction to effort.

### 2.1 Central privacy config (foundational; everything else reads from it)

- [ ] Add `PrivacySettings` dataclass to [backend/config.py](../backend/config.py).
      Use the draft in §6 below verbatim.
- [ ] Add a `GET /privacy/config` endpoint that returns the public subset
      (age threshold, retention windows, controller name, contact email,
      `analytics_enabled`) so the frontend can render text without
      hard-coding values.
- [ ] Frontend hook `usePrivacyConfig()` in
      [frontend/src/api/](../frontend/src/api/) that fetches once and caches.

### 2.2 Public takedown / "remove me" flow (M-04)

Single highest risk-reduction action. Even in Mode A.

- [ ] New table `takedown_requests` in
      [database/system_models.py](../database/system_models.py):
      `id`, `tree_owner_id`, `individual_id` (nullable), `requester_name`,
      `requester_email`, `message`, `status` (open / acknowledged / resolved /
      escalated), `created_at`, `resolved_at`.
- [ ] Public endpoint `POST /privacy/takedown` in new
      [backend/api/privacy.py](../backend/api/privacy.py). Rate-limited by IP
      (5/hour). No auth.
- [ ] Email notification to the Owner on receipt; reminder at day 14;
      auto-escalate at `takedown_sla_days` (default 30). Use the existing
      SMTP plumbing in `backend/api/auth.py`.
- [ ] Admin endpoint `GET/PATCH /admin/takedown` to triage tickets. Admin
      can mark resolved or hide records on Owner's behalf if escalated.
- [ ] Persistent **"Privacy / remove me"** link in the layout footer for
      every shared view ([frontend/src/components/Layout.tsx](../frontend/src/components/Layout.tsx)).
- [ ] Public takedown form page at `/privacy/takedown`
      ([frontend/src/pages/legal/](../frontend/src/pages/legal/)).

### 2.3 Owner self-unregister + cascade delete (notes.txt L220 + erasure log)

Aligns the right-of-erasure mechanism for the Owner themselves with the
takedown infrastructure.

- [ ] New table `erasure_log` (timestamp, owner_id, scope = `owner` /
      `individual` / `media`, target_id, requester_kind = `owner` / `subject`,
      ticket_id nullable). Used by takedown and self-unregister.
- [ ] `DELETE /users/me` in [backend/api/users.py](../backend/api/users.py) —
      cascades: revoke all share tokens, delete contributors, drop owner's
      `data.sqlite` and media folder, write erasure_log row, clear cookies.
- [ ] Frontend "Delete my account and all my data" button on Settings →
      Profile, with type-the-word-DELETE confirmation.
- [ ] Admin equivalent endpoint for forced removal.

### 2.4 Privacy + ToS pages, footer link, cookie notice (Phase 0.2-0.4 + M-12)

- [ ] Backend serves markdown legal pages from `/legal/privacy`, `/legal/tos`,
      `/legal/cookies` (read from `docs/legal/*.md`, versioned via the config).
- [ ] Frontend renders them under `frontend/src/pages/legal/`.
- [ ] Footer link on every page: Privacy · Terms · Cookies · Privacy/remove me.
- [ ] Cookie notice banner — dismissible, persisted in `localStorage`. Single
      "Got it" button (no Accept/Reject — only strictly-necessary cookies are
      set). Text from
      [PRIVACY_HANDLING.md §9.6](PRIVACY_HANDLING.md#96-cookie-notice-banner-first-visit).
      Component: [frontend/src/components/CookieNotice.tsx](../frontend/src/components/CookieNotice.tsx) (new).

### 2.5 Viewer notice on first share-link load (M-16)

- [ ] First load of `?share=<token>` shows a small notice with text from
      [PRIVACY_HANDLING.md §9.3](PRIVACY_HANDLING.md#93-viewer-notice-shown-on-first-share-link-load).
      Dismissed once per token (key = `viewer_notice_dismissed:<token_hash>` in
      `sessionStorage`).
- [ ] Component: `ViewerNotice.tsx`. Hook into
      [frontend/src/contexts/AuthContext.tsx](../frontend/src/contexts/AuthContext.tsx).

### 2.6 Per-share acknowledgement (M-03)

CYA when relatives forward the link.

- [ ] New table `auth_share_consents`: `id`, `editor_id`, `tree_owner_id`,
      `share_token_id`, `accepted_at`, `accepted_ip`, `tos_version`.
- [ ] Modal shown when Owner clicks "Create share link" or extends visibility.
      Text from [PRIVACY_HANDLING.md §9.4](PRIVACY_HANDLING.md#94-per-share-acknowledgement-shown-when-creating-or-extending-a-share-link).
- [ ] Persist consent on submit. Do not let share tokens be created without it.

### 2.7 Audit trail completeness (M-11, Phase 2)

Required to answer "who added this about me?" queries — even with contributors
disabled, the Owner adds data over time.

- [ ] Add `updated_by`, `updated_at` columns to `Individual`,
      `IndividualName`, `Family`, `FamilyMember`, `FamilyChild`, `Event`,
      `Media` in [database/models.py](../database/models.py) and
      [database/schema.sql](../database/schema.sql).
- [ ] Lazy migration on `get_engine()` to add columns to existing
      `data.sqlite` files ([database/db.py](../database/db.py)).
- [ ] Stamp them in every UPDATE path:
      [backend/api/individuals.py](../backend/api/individuals.py),
      [backend/api/families.py](../backend/api/families.py),
      [backend/api/events.py](../backend/api/events.py),
      [backend/api/media.py](../backend/api/media.py).
- [ ] **Verify GEDCOM importer stamps `created_by = owner_id` on every
      imported row** (largest single PII inflow vector).
- [ ] "History" tab on Individual page showing creator + last editor.

### 2.8 Right-of-access export per Individual (M-09, Phase 7)

- [ ] Endpoint `GET /individuals/{id}/data-export` returning JSON of every
      field, event, media reference, contributor attribution. Owner-only.
- [ ] "Export this person's data" button on Individual page.

---

## 3. Tier 2 — Soon (operational + Mode A polish)

After Tier 1, Mode A is defensible. Tier 2 is hardening and operational
hygiene.

### 3.1 Disable signups in Mode A

- [ ] Reject `POST /auth/owner-signup` with HTTP 403 if
      `PrivacySettings.allow_owner_signup` is False.
- [ ] Reject `POST /auth/contributor-signup` with HTTP 403 if
      `PrivacySettings.allow_contributor_signup` is False.
- [ ] Hide signup links from frontend when disabled.

### 3.2 Backup retention enforcement (M-10)

- [ ] Update `vm-backup.py` (in `novospace.git/scripts/deployment/`) to
      delete backups older than `backup_retention_days` (default 30).
- [ ] Document the 30-day window in the rendered privacy policy.

### 3.3 Log scrubbing + retention (M-14)

- [ ] Disable request-body logging in production
      ([backend/main.py](../backend/main.py),
      [backend/logging.py](../backend/logging.py)).
- [ ] Document log retention (14 / 30 days for access / error) in the privacy
      policy and in [novospace.git/docs/deployment.md](../../novospace.git/docs/deployment.md).

### 3.4 Ops emails (notes.txt L221)

- [ ] Email errors from logs + backup logs to admin. Operational, not strictly
      privacy work, but pairs with log scrubbing.

### 3.5 Admin page or CLI (notes.txt L208–213)

- [ ] CLI is sufficient to start. User management + manual backup trigger +
      takedown ticket triage.

### 3.6 Special-category gating (M-05, Phase 6.1–6.2)

Defer if the current tree has none; do before going public.

- [ ] Tag sensitive event types (cause of death, religion, ethnicity, certain
      medical events).
- [ ] Hide sensitive fields behind a "show sensitive" toggle in the UI.
- [ ] Per-share-token flag `expose_sensitive` (default False) — sensitive
      fields excluded from viewer payload unless explicitly enabled.

### 3.7 Children data handling (M-06, Phase 6.3)

Defer if no minors in the tree; do before going public.

- [ ] Detect `birth_date` < `child_age_threshold_years` years ago AND
      `death_date` IS NULL.
- [ ] Photo upload disabled for minors unless Owner checks "I have parental
      consent."
- [ ] Minors not exposed to viewer payload unless Owner explicitly opts in
      per share token.

---

## 4. Tier 3 — Before going public (Mode B)

### 4.1 Local-first / desktop app (Phase 9, M-08)

**Single biggest privacy posture upgrade for the SaaS path.** Already on the
roadmap (notes.txt L251).

- [ ] Desktop installer that runs the FastAPI backend on `127.0.0.1`.
- [ ] Explicit "import from server / export to server" actions, not silent
      sync.
- [ ] EULA text reflecting the household-exemption posture (no controller
      duties for NovoTree in this mode — software-vendor only).

### 4.2 Full Owner ToS at signup (Phase 1, M-01)

- [ ] Add `tos_accepted_at`, `tos_version` columns to `auth_editors`.
- [ ] Required signup checkbox + backend rejection if absent.
- [ ] Re-acceptance prompt on login when `tos_version` increases.
- [ ] Flip `PrivacySettings.allow_owner_signup = True`.

### 4.3 Contributor acknowledgement (Phase 5.1, M-15)

- [ ] First-edit modal with text from
      [PRIVACY_HANDLING.md §9.2](PRIVACY_HANDLING.md#92-contributor-acknowledgement-shown-before-first-edit).
- [ ] Persist accepted (editor_id, tree_owner_id, accepted_at).
- [ ] Flip `PrivacySettings.allow_contributor_signup = True`.

### 4.4 Hosting and DPA (M-13)

- [ ] Confirm Hetzner region is EEA (Falkenstein or Helsinki).
- [ ] Sign Hetzner DPA (online, free).
- [ ] Sign Cloudflare DPA via dashboard.
- [ ] List both as sub-processors in the privacy policy.

### 4.5 Donate button (notes.txt L249)

- [ ] Pick provider (Stripe / PayPal). Note: payment provider becomes another
      sub-processor; document in privacy policy.

### 4.6 Lawyer review (close PRIVACY_HANDLING.md §10 open questions)

- [ ] Schedule paid review session.
- [ ] Update relevant texts (ToS, privacy policy, cookie banner) per advice.
- [ ] Resolve all 7 open questions with documented answers in this file.

---

## 5. Tier 4 — Later (not privacy-blocking)

| Item | Source |
|---|---|
| - [ ] UTF-8 / character handling decision | notes.txt L218 |
| - [ ] Mobile tree view | notes.txt L219 |
| - [ ] Voice CRUD with AI | notes.txt L256 — **flag**: introduces an AI provider as a sub-processor; triggers a fresh privacy review when scoped. |

---

## 6. Central privacy config — draft (not yet implemented)

When Tier 1 starts, copy this block into [backend/config.py](../backend/config.py).
Loaded from environment variables; defaults are the conservative choices
documented in [PRIVACY_HANDLING.md §10](PRIVACY_HANDLING.md#10-open-questions-for-legal-review).

```python
# Privacy & legal posture configuration.
# All values overridable via environment variables.
#
# Acronyms used in this file:
#   GDPR     — General Data Protection Regulation (EU 2016/679). EU privacy law.
#   ePrivacy — EU Directive 2002/58 (the "Cookie Law"). Governs cookies and
#              client-side storage independently of GDPR.
#   ToS      — Terms of Service. The contract the Owner accepts at signup.
#   SLA      — Service Level Agreement. A promised response time.
#   DPO      — Data Protection Officer. A formally-designated privacy contact.
#   EEA      — European Economic Area = EU + Iceland, Liechtenstein, Norway.
#              Data flowing inside the EEA is unrestricted.
#   SCC      — Standard Contractual Clauses. EU-approved contract template
#              for transferring personal data outside the EEA.
#   DPF      — EU-US Data Privacy Framework (July 2023). Lets certified US
#              companies receive EU personal data legally.
#   PII      — Personally Identifiable Information.

@dataclass(frozen=True)
class PrivacySettings:

    # --- deployment mode ---
    # "private" = single owner (you), no signups; "public" = open SaaS.
    deployment_mode: str = "private"

    # Whether NEW owners can self-register via the signup form.
    # Off in private mode; flipped on for public launch.
    allow_owner_signup: bool = False

    # Whether owners can invite Contributors who can edit the tree.
    # Off in private mode; on for public launch.
    allow_contributor_signup: bool = False

    # --- SLA = Service Level Agreement; thresholds ---

    # SLA in days for a "remove me" (takedown) request from a data subject.
    # After this many days, admin auto-escalates and hides records on the
    # Owner's behalf. GDPR Art. 12(3) says "without undue delay, and in any
    # event within one month" — 30 days is the safe default.
    takedown_sla_days: int = 30

    # Age below which an Individual is treated as a minor and gets extra
    # protection (parental-consent gate on photo upload and share-link
    # exposure). GDPR Art. 8 lets each EU member state pick a threshold
    # between 13 and 16; we pick 16 so we are compliant everywhere.
    child_age_threshold_years: int = 16

    # --- retention windows ---

    # How long backups of owner data.sqlite files are kept before deletion.
    # Bounds the window in which a deleted record can resurface from backup.
    # Must be >= takedown_sla_days so erasure can propagate.
    backup_retention_days: int = 30

    # Web-server access logs (URL, status, IP). Short window — debugging and
    # abuse detection only.
    access_log_retention_days: int = 14

    # Application error logs and stack traces — kept longer because some
    # bugs only show up after a user reports them.
    error_log_retention_days: int = 30

    # How long we keep a takedown ticket (name + email + complaint text)
    # after it has been resolved. Long enough to prove we responded if a
    # regulator asks; short enough that we are not hoarding PII.
    takedown_request_retention_months: int = 12

    # --- legal-document versioning ---
    # When any of these strings change, users are re-prompted to accept on
    # next login. We do not silently update legal documents.
    tos_version: str = "1.0"            # ToS = Terms of Service
    privacy_policy_version: str = "1.0"
    cookie_notice_version: str = "1.0"

    # --- controller identity (privacy policy §1, §7) ---

    # "Data controller" is the GDPR Art. 4(7) term for the legal entity
    # responsible for deciding why and how personal data is processed. This
    # name appears in the privacy policy and in takedown responses.
    # Do not confuse with the internal "admin" role.
    controller_name: str = "NovoTree (operator: Igor Novoseltsev)"

    # Where data subjects email privacy questions and takedown follow-ups.
    # Must be a monitored mailbox.
    privacy_contact_email: str = "aktiniya@gmail.com"

    # DPO = Data Protection Officer (GDPR Art. 37). MANDATORY only if we do
    # large-scale monitoring or large-scale special-category processing —
    # NovoTree at current scale does not qualify. Stays None until a lawyer
    # says otherwise; the field exists so we can fill it without code changes.
    dpo_email: str | None = None

    # Where the production VM lives. Determines which GDPR Chapter V rules
    # apply to international data transfers:
    #   "EEA"          → no extra rules.
    #   anything else  → must use SCC (Standard Contractual Clauses), or
    #                    DPF (EU-US Data Privacy Framework) for US providers,
    #                    or rely on an adequacy decision.
    hosting_region: str = "EEA"

    # --- analytics & cookies ---

    # If False: only strictly-necessary auth cookies are set. The cookie
    # banner is a simple NOTICE (no Accept/Reject buttons needed under
    # ePrivacy Directive Art. 5(3)). Cloudflare Web Analytics fits here.
    #
    # If True: a third-party analytics script that sets non-essential cookies
    # is loaded. This requires PRIOR opt-in consent — the banner becomes a
    # real CONSENT dialog with Accept and Reject buttons, and the analytics
    # script must not load until Accept is clicked.
    analytics_enabled: bool = False
```

### Where this config is read

| Reader | Purpose |
|---|---|
| `backend/api/auth.py` | Signup gate (allow_*_signup), ToS version comparison |
| `backend/api/privacy.py` (new in Tier 1) | Takedown SLA timer, retention windows |
| `backend/api/users.py` | Self-unregister flow |
| Frontend via `GET /privacy/config` | Banner copy, age threshold display, retention text |

---

## 7. Open questions awaiting legal review

From [PRIVACY_HANDLING.md §10](PRIVACY_HANDLING.md#10-open-questions-for-legal-review).
For each, we apply a conservative default in code and revisit after the lawyer
session.

| # | Question | Code-side default | Lives in |
|---|----------|-------------------|----------|
| 1 | Household exemption defensibility for friends-only mode | Treat any share link as non-household (CJEU *Lindqvist*). All Tier 1 mitigations apply once a share is created. | ToS text + per-share ack |
| 2 | Owner-as-controller vs joint controllers | Frame Owner as controller, NovoTree as processor in ToS. | ToS, privacy policy |
| 3 | Takedown SLA exact days | `takedown_sla_days = 30` | Config |
| 4 | Children's age threshold | `child_age_threshold_years = 16` (most conservative) | Config |
| 5 | DPO required at our scale? | `dpo_email = None`. Field exists for future fill-in without code change. | Config |
| 6 | International transfer mechanism | `hosting_region = "EEA"` to keep this question moot. Cloudflare disclosed under DPF. | Config + privacy policy |
| 7 | Cookie notice text + Accept-only button acceptable to regulators | Notice-only banner with "Got it" button (no Accept/Reject) — defensible under ePrivacy 5(3) for strictly-necessary cookies. Confirm acceptable in CNIL/ICO practice. | Banner component, privacy policy |

---

## 8. Status legend (use when ticking boxes)

```
- [ ]   not started
- [~]   in progress (PR open or branch active)
- [x]   merged / shipped
- [!]   blocked (add a one-line reason in the same line)
```

When updating, also bump the **Status overall** line at the top so a fresh
session can see at a glance how far along the work is.
