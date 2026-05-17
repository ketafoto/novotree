# Privacy Implementation Plan

> **Companion to [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md).**
> This document is the *when and how* — a tiered implementation checklist
> (Tier 1 / 2 / 3) that tracks coding progress, the central `PrivacySettings`
> draft, and the deployment-mode taxonomy (Mode A / B / C).
> [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) is the *what and why* — the
> concerns inventory (C-NN), mitigation catalogue (M-NN), per-mode posture
> table, and draft legal texts. Items here reference the M-NN IDs defined
> there.
>
> If you are picking work up from scratch: read
> [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) first to understand the problem
> space, then this file to see what is built, in progress, or queued.

**Status overall: TIER 1 STARTED.** §2.1 (central privacy config) is shipped:
`PrivacySettings` dataclass, `GET /privacy/config` endpoint, and frontend
`usePrivacyConfig()` hook are in. Remaining Tier 1 items (§2.2–§2.6) are
queued — see the per-section checkboxes below.

---

## 1. Context for a fresh session

If you are picking this up from scratch, read in this order:

1. [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) — concerns inventory, mitigations,
   concern↔mitigation matrix, and draft legal texts.
2. This file — tiered checklist + central config draft + decisions made so far.
3. [AUTH_SCHEMA_PROPOSAL.md](AUTH_SCHEMA_PROPOSAL.md) — auth tables/endpoints
   that several privacy items extend.
4. [CONTRIBUTOR_FEATURE.md](CONTRIBUTOR_FEATURE.md) — contributor lifecycle
   that some privacy items add acknowledgements to.

### Key product framing — three deployment modes

NovoTree has three practical deployment modes:

- **Mode A — Private / read-only.** Single owner (the operator). Owner and
  contributor signups disabled. Share links to relatives still work; assume
  any link can be forwarded → effectively public. Therefore Mode A still
  needs takedown, viewer notice, audit trail, right-of-access export.
- **Mode B — Contributors-only.** Owner signup disabled; contributor signup
  enabled. The operator remains the only Owner / data controller for the
  tree's contents, but invites relatives to *edit* the same tree as
  Contributors. Reduces the legal surface vs. Mode C because no second
  data controller is created on the server, but still requires audit-trail
  completeness (multiple editors touch the same tree) and a contributor
  acknowledgement. A gated owner-signup variant (admin-approved relatives
  with their own trees) is NOT Mode B — it falls under Mode C below; see
  §6.5 for why.
- **Mode C — Public service.** Open owner and contributor signups (or any
  variant where multiple Owners exist on the server, including
  admin-approved gated signup). Local-first desktop app is the headline
  privacy upgrade.

Tier 1 + Tier 2 below get Mode A defensible. Tier 3 unlocks Mode B and Mode C.

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

### Glossary — acronyms used in this document

| Acronym | Expansion | Plain meaning here |
|---------|-----------|--------------------|
| **CCPA** | California Consumer Privacy Act | US state privacy law (California). Lighter than GDPR; covered by a GDPR-style privacy policy. |
| **CJEU** | Court of Justice of the European Union | EU's highest court. Cited for *Lindqvist* (C-101/01), which ruled that posting personal data on a webpage is processing, breaking the household exemption. |
| **CNIL** | Commission Nationale de l'Informatique et des Libertés | France's data-protection regulator. |
| **COPPA** | Children's Online Privacy Protection Act | US federal law on under-13 data. Our `child_age_threshold_years = 16` covers it. |
| **CYA** | Cover Your Ass | Defensive practice — a logged record that you took due care, useful if someone later complains. |
| **DPA** | Data Processing Agreement | Contract between controller and processor (e.g. NovoTree ↔ Hetzner) defining how the processor handles personal data. |
| **DPF** | EU-US Data Privacy Framework (July 2023) | Lets certified US companies (e.g. Cloudflare) receive EU personal data legally. |
| **DPO** | Data Protection Officer (GDPR Art. 37) | A formally-designated privacy contact. Mandatory only at large scale; we don't qualify. |
| **EEA** | European Economic Area | EU + Iceland, Liechtenstein, Norway. Data flowing inside the EEA is unrestricted. |
| **ePrivacy** | EU Directive 2002/58 (the "Cookie Law") | Governs cookies and client-side storage independently of GDPR. Art. 5(3) exempts strictly-necessary storage. |
| **GA / GA4** | Google Analytics (4) | Google's web analytics product. Removed from this project. |
| **GDPR** | General Data Protection Regulation (EU 2016/679) | EU privacy law. Applies to any EU/UK data subject regardless of where the service is hosted. |
| **ICO** | Information Commissioner's Office | UK's data-protection regulator. |
| **PII** | Personally Identifiable Information | Any data that can identify a living person (names, emails, photos, etc.). |
| **SaaS** | Software as a Service | Hosted product accessed over the network. NovoTree's public mode is a SaaS. |
| **SCC** | Standard Contractual Clauses | EU-approved contract template for transferring personal data outside the EEA. |
| **SLA** | Service Level Agreement | A promised response time (e.g. takedown SLA = 30 days). |
| **SMTP** | Simple Mail Transfer Protocol | Email-sending backend. Required for verification, takedown, contributor invites. |
| **ToS** | Terms of Service | The contract the Owner accepts at signup. |

The config block in §6 has its own inline glossary for the acronyms it uses; this section covers the body of the document.

---
### When to involve a lawyer

**Not blocking for Tier 1 or Tier 2.** Mode A is a hobby deployment with one
controller (the operator), no monetization, no analytics, no public signups,
and a documented takedown flow. The conservative defaults in §6 pick the
strictest EU thresholds, so the configuration is compliant in every jurisdiction
it might touch. A regulator complaint against a one-person hobby tree that
responds to takedowns within 30 days is realistically near-zero risk.

**Required before Tier 3 (Mode B or Mode C launch).** Once any of the following
becomes true, schedule a paid review:

- Contributor signup is enabled (`allow_contributor_signup = True`) — minimum
  trigger for Mode B.
- Owner signup is enabled in any form, gated or open (`allow_owner_signup = True`
  with or without `owner_signup_requires_approval`) — triggers full Mode C.
- A donate button or any payment integration is added.
- Analytics with non-essential cookies are introduced (`analytics_enabled = True`).
- Sensitive data is intentionally exposed via share tokens.

The agenda for that review is fixed: the seven open questions in
[PRIVACY_ANALYSIS.md §10](PRIVACY_ANALYSIS.md#10-open-questions-for-legal-review).
See §4.1 — it is the first and gating item in Tier 3.

## 2. Tier 1 — Now (Mode A hardening)

Goal: make the current shareable-link deployment defensible. Do not require
contributor signups or full ToS machinery. Roughly ordered by ratio of
risk-reduction to effort.

### 2.1 Central privacy config (foundational; everything else reads from it)

- [x] Add `PrivacySettings` dataclass to [backend/config.py](../backend/config.py).
      Use the draft in §6 below verbatim.
- [x] Add a `GET /privacy/config` endpoint that returns the public subset
      (age threshold, retention windows, controller name, contact email,
      `analytics_enabled`) so the frontend can render text without
      hard-coding values. Lives in [backend/api/privacy.py](../backend/api/privacy.py).
- [x] Frontend hook `usePrivacyConfig()` in
      [frontend/src/hooks/usePrivacyConfig.ts](../frontend/src/hooks/usePrivacyConfig.ts)
      that fetches once and caches (module-scoped promise). API typings in
      [frontend/src/api/privacy.ts](../frontend/src/api/privacy.ts).

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

### 2.3 Privacy policy page + footer link (Phase 0.2-0.3 partial)

In Mode A the Owner is the operator — accepting one's own ToS is moot, and the
cookie notice banner is unnecessary (auth cookies are seen only by the operator;
viewers carry a strictly-necessary share token in `sessionStorage` covered by
ePrivacy 5(3) and addressed by the viewer notice in §2.5). What is needed in
Tier 1 is a privacy policy page that the takedown form can link to, and a footer
that exposes both.

- [ ] Backend serves markdown for `/legal/privacy` (read from
      `docs/legal/privacy.md`, versioned via `privacy_policy_version`).
- [ ] Frontend renders it under `frontend/src/pages/legal/PrivacyPage.tsx`.
- [ ] Footer link on every page: Privacy · Privacy/remove me.
- [ ] (Cookies and ToS pages are deferred to Tier 3 — see §4.3.)

### 2.4 Viewer notice on first share-link load (M-16)

- [ ] First load of `?share=<token>` shows a small notice with text from
      [PRIVACY_ANALYSIS.md §9.3](PRIVACY_ANALYSIS.md#93-viewer-notice-shown-on-first-share-link-load).
      Dismissed once per token (key = `viewer_notice_dismissed:<token_hash>` in
      `sessionStorage`).
- [ ] Component: `ViewerNotice.tsx`. Hook into
      [frontend/src/contexts/AuthContext.tsx](../frontend/src/contexts/AuthContext.tsx).

### 2.5 Per-share acknowledgement (M-03)

A defensive log of "I, the Owner, confirmed I had the right to share this tree"
each time a share link is created or extended. Useful evidence if a relative
forwards the link further than intended and someone later complains.

- [ ] New table `auth_share_consents`: `id`, `editor_id`, `tree_owner_id`,
      `share_token_id`, `accepted_at`, `accepted_ip`, `tos_version`.
- [ ] Modal shown when Owner clicks "Create share link" or extends visibility.
      Text from [PRIVACY_ANALYSIS.md §9.4](PRIVACY_ANALYSIS.md#94-per-share-acknowledgement-shown-when-creating-or-extending-a-share-link).
- [ ] Persist consent on submit. Do not let share tokens be created without it.

### 2.6 Right-of-access export per Individual (M-09, Phase 7)

- [ ] Endpoint `GET /individuals/{id}/data-export` returning JSON of every
      field, event, media reference, and contributor attribution (`created_by` /
      `created_at`). Owner-only.
- [ ] "Export this person's data" button on Individual page.

### Notes on what is NOT in Tier 1 (and why)

| Item | Why deferred | Goes to |
|---|---|---|
| Owner self-unregister | In Mode A, owner = operator; deletion is a directory drop on the VM. | Tier 3 §4.2 |
| ToS pages + acceptance | Operator accepts no terms from themselves; meaningful only with multiple owners. | Tier 3 §4.3 |
| Cookie notice banner | Mode A has no non-essential cookies and no third-party owners to notify. | Tier 3 §4.3 |
| `updated_by` / `updated_at` audit columns | With single Owner, `created_by` (already stamped on every row) answers "who added this?" — always the Owner. Multi-editor audit becomes needed in Mode B (contributors) and Mode C. | Tier 3 §4.6 |
| "History" tab on Individual page | Same reason — uniform attribution in Mode A. | Tier 3 §4.6 |

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

### 3.5 Admin CLI (notes.txt L208–213)

A "ticket" here means a row in the `takedown_requests` table created by §2.2.
It is not a separate ticket-tracker product. "Triage" means the operator
reviewing rows where `status='open'` and choosing the next action (forward to
Owner / mark resolved / escalate / hide records).

- [ ] CLI is sufficient to start (no separate admin web page yet).
      Commands: list owners, manual backup trigger, list and resolve open
      `takedown_requests` rows, force-delete an Individual on Owner's behalf
      after the SLA expires.

### 3.6 Verify GEDCOM importer stamps `created_by`

Light future-proofing for Mode B / Mode C: if the importer leaves rows with
`created_by IS NULL`, switching out of Mode A later loses the historical
attribution to the Owner.

- [ ] One-time verification in [database/gedcom_import.py](../database/gedcom_import.py) —
      every imported `Individual`, `Family`, `Event`, `Media`, `IndividualName`
      row sets `created_by = owner_id` and `created_at = now`. Add a regression
      test if missing.

### 3.7 Special-category gating (M-05, Phase 6.1–6.2)

Defer if the current tree has none; do before going public.

- [ ] Tag sensitive event types (cause of death, religion, ethnicity, certain
      medical events).
- [ ] Hide sensitive fields behind a "show sensitive" toggle in the UI.
- [ ] Per-share-token flag `expose_sensitive` (default False) — sensitive
      fields excluded from viewer payload unless explicitly enabled.

### 3.8 Children data handling (M-06, Phase 6.3)

Defer if no minors in the tree; do before going public.

- [ ] Detect `birth_date` < `child_age_threshold_years` years ago AND
      `death_date` IS NULL.
- [ ] Photo upload disabled for minors unless Owner checks "I have parental
      consent."
- [ ] Minors not exposed to viewer payload unless Owner explicitly opts in
      per share token.

---

## 4. Tier 3 — Before enabling Mode B or Mode C

> **Everything in Tier 3 is conditional on completing §4.1 first.** Do not
> start any code in §4.2–§4.8 before the lawyer consultation. The whole point
> of §4.1 is to decide whether Mode B or Mode C is workable in your
> jurisdiction with acceptable obligations — if the answer is "no, not at this
> scale," all of the development effort below is wasted.

### What Mode B needs vs what Mode C needs

Tier 3 covers two destinations:

- **Mode B (contributors-only)** needs: §4.1 (lawyer), §4.5 (contributor ack),
  §4.6 (audit trail), §4.7 (hosting + DPA). It does NOT need §4.3 (owner
  self-unregister), §4.4 (owner ToS at signup), or §4.8 (donate button).
- **Mode C (public service, including gated/admin-approved owner signup)**
  needs all of §4.1–§4.8.

§6.5 explains why gated owner signup is Mode C, not Mode B, and contains the
side-by-side obligation table.

### 4.1 **Lawyer review — GATING. Do this first.**

This is a **go / no-go decision point**, not a wrap-up step. Schedule a paid
consultation with a privacy/data-protection specialist before writing any
Tier-3 code. The objective is to walk away with answers to all seven open
questions in
[PRIVACY_ANALYSIS.md §10](PRIVACY_ANALYSIS.md#10-open-questions-for-legal-review),
and a clear sense of whether the obligations match what you can sustain.

**Stop here if the answers make Mode B or Mode C impractical** (e.g. DPO
required at your scale, joint-controller framing forces you to vet every Owner
manually, local jurisdiction adds requirements you cannot meet). It is far
cheaper to pay one hour of legal time and decide *not* to build than to ship
and discover the obligations afterwards.

- [ ] Schedule paid consultation (1–2 hours, privacy/SaaS specialist).
      See guidance on finding one in §1 → "When to involve a lawyer".
- [ ] Bring the §10 list as the agenda. Document each answer here:

  | # | Question | Answer (fill after consultation) |
  |---|----------|----------------------------------|
  | 1 | Household exemption defensibility for friends-only mode | |
  | 2 | Owner-as-controller vs joint controllers | |
  | 3 | Takedown SLA exact days | |
  | 4 | Children's age threshold | |
  | 5 | DPO required at our scale? | |
  | 6 | International transfer mechanism | |
  | 7 | Cookie notice + button design acceptable to regulators? | |

- [ ] **Go / no-go decision recorded here:**
      ☐ GO Mode B (contributors-only) — proceed with §4.5, §4.6, §4.7.
      ☐ GO Mode C (public / gated owner signup) — proceed with §4.2–§4.8.
      ☐ NO-GO — keep NovoTree in Mode A indefinitely; close out Tier 3.
- [ ] After §4.2–§4.8 development is complete, schedule a short second
      session (~30 min) to review the final ToS, privacy policy, and cookie
      banner texts before launch.

### 4.2 Local-first / desktop app (Phase 9, M-08) — Mode C only

**Single biggest privacy posture upgrade for the SaaS path.** Already on the
roadmap (notes.txt L251).

- [ ] Desktop installer that runs the FastAPI backend on `127.0.0.1`.
- [ ] Explicit "import from server / export to server" actions, not silent
      sync.
- [ ] EULA text reflecting the household-exemption posture (no controller
      duties for NovoTree in this mode — software-vendor only).

### 4.3 Owner self-unregister + cascade delete (notes.txt L220 + erasure log) — Mode C only

Right-of-erasure for an Owner who is no longer the operator. Mode-C-only:
in Mode A and Mode B the operator is still the only Owner and deletes the
directory by hand. Reuses the takedown infrastructure from §2.2 for the
cascade machinery.

- [ ] New table `erasure_log` (timestamp, owner_id, scope = `owner` /
      `individual` / `media`, target_id, requester_kind = `owner` / `subject`,
      takedown_request_id nullable). Used by takedown and self-unregister.
- [ ] `DELETE /users/me` in [backend/api/users.py](../backend/api/users.py) —
      cascades: revoke all share tokens, delete contributors, drop owner's
      `data.sqlite` and media folder, write erasure_log row, clear cookies.
- [ ] Frontend "Delete my account and all my data" button on Settings →
      Profile, with type-the-word-DELETE confirmation.
- [ ] Admin equivalent endpoint for forced removal (used by §2.2 escalation).

### 4.4 Full Owner ToS at signup + cookie notice banner (Phase 1, M-01, M-12) — Mode C only

- [ ] Add `tos_accepted_at`, `tos_version` columns to `auth_editors`.
- [ ] Required signup checkbox + backend rejection if absent.
- [ ] Re-acceptance prompt on login when `tos_version` increases.
- [ ] Backend serves `/legal/tos` and `/legal/cookies` markdown pages
      (Privacy already shipped in Tier 1 §2.3).
- [ ] Footer link expanded: Privacy · Terms · Cookies · Privacy/remove me.
- [ ] Cookie notice banner — dismissible, persisted in `localStorage`, single
      "Got it" button. Text from
      [PRIVACY_ANALYSIS.md §9.6](PRIVACY_ANALYSIS.md#96-cookie-notice-banner-first-visit).
      Component: [frontend/src/components/CookieNotice.tsx](../frontend/src/components/CookieNotice.tsx) (new).
- [ ] Flip `PrivacySettings.allow_owner_signup = True`. If gated, also set
      `PrivacySettings.owner_signup_requires_approval = True` and wire the
      admin-approval flow (per §6.5).

> If `analytics_enabled` is later flipped to True (e.g. switching from
> Cloudflare Web Analytics to GA4 or any other tool that sets non-essential
> cookies), the banner here must be replaced with a real Accept/Reject consent
> dialog, and the analytics script gated until Accept is clicked.

### 4.5 Contributor acknowledgement (Phase 5.1, M-15) — Mode B and Mode C

- [ ] First-edit modal with text from
      [PRIVACY_ANALYSIS.md §9.2](PRIVACY_ANALYSIS.md#92-contributor-acknowledgement-shown-before-first-edit).
- [ ] Persist accepted (editor_id, tree_owner_id, accepted_at).
- [ ] Flip `PrivacySettings.allow_contributor_signup = True`.

### 4.6 Audit trail completeness (M-11, Phase 2) — Mode B and Mode C

Required as soon as multiple editors can touch the same tree (which happens
the moment Contributors are introduced in Mode B). With a single Owner the
existing `created_by` columns answer "who added this?" uniformly. This work
makes "who edited this last?" answerable, which becomes meaningful in Mode B.

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
- [ ] "History" tab on Individual page showing creator + last editor.
- [ ] Right-of-access export from §2.6 includes both `created_by` /
      `created_at` and `updated_by` / `updated_at` once these columns exist.

### 4.7 Hosting and DPA (M-13) — Mode B and Mode C

- [ ] Confirm Hetzner region is EEA (Falkenstein or Helsinki).
- [ ] Sign Hetzner DPA (online, free).
- [ ] Sign Cloudflare DPA via dashboard.
- [ ] List both as sub-processors in the privacy policy.

### 4.8 Donate button (notes.txt L249) — Mode C only

- [ ] Pick provider (Stripe / PayPal). Note: payment provider becomes another
      sub-processor; document in privacy policy.

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
documented in [PRIVACY_ANALYSIS.md §10](PRIVACY_ANALYSIS.md#10-open-questions-for-legal-review).

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
    # "A"  = single owner (you), no signups.
    # "B"  = contributors-only (you remain the only Owner; relatives
    #        can sign up as Contributors who edit your tree).
    # "C"  = public SaaS (open or admin-gated owner signup).
    deployment_mode: str = "A"

    # Whether NEW owners can self-register via the signup form.
    # Off in Mode A and Mode B; on in Mode C (with or without approval gating).
    allow_owner_signup: bool = False

    # If allow_owner_signup is True, this controls whether new owner
    # signups land in a pending state until an admin approves them.
    # See §6.5 — this is the "friends-and-family SaaS" gating switch.
    # Reduces abuse surface; does NOT downgrade the legal mode below Mode C.
    owner_signup_requires_approval: bool = True

    # Whether owners can invite Contributors who can edit the tree.
    # Off in Mode A; on in Mode B and Mode C.
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
| `backend/api/auth.py` | Signup gate (allow_*_signup, owner_signup_requires_approval), ToS version comparison |
| `backend/api/privacy.py` (new in Tier 1) | Takedown SLA timer, retention windows |
| `backend/api/users.py` | Self-unregister flow |
| Frontend via `GET /privacy/config` | Banner copy, age threshold display, retention text |

---

## 6.5 Mode B (contributors-only) vs Mode C (gated or open owner signup)

A common product instinct is: "I only want to share this with relatives and
friends, so I will add an admin approval step in front of owner signup — that
keeps it small and trusted, so surely it stays in Mode A or Mode B."

**It does not.** The legal mode is determined by *who is a data controller on
the server*, not by *how they got there*. The moment a second person can
create their own tree on your VM, you are hosting personal data on behalf of
another controller — and every Tier 3 obligation in §4 follows, regardless of
whether the second Owner was admin-approved or self-served.

Admin approval is an excellent **abuse mitigation** (small known user count,
manual sanity check, easy to revoke). It is not a legal classification.

### When approval helps vs. when it does not change the mode

| Scenario | Legal mode |
|---|---|
| Single Owner = operator. Share links only. | **Mode A** |
| Single Owner = operator. Relatives sign up as **Contributors** who edit the operator's tree. | **Mode B** |
| Relatives sign up to host **their own trees** on your VM, with admin approval. | **Mode C** (gated) |
| Relatives sign up to host **their own trees**, open self-service. | **Mode C** (open) |

### Obligation comparison: Mode B vs Mode C

Use this when deciding which Tier 3 destination to aim for. "Required" means
the obligation gates the launch of that mode.

| Obligation | Mode B (contributors-only) | Mode C (any owner signup) |
|---|---|---|
| §4.1 Lawyer review | Required | Required |
| Multiple data controllers on the server | No — operator is sole controller | Yes — each Owner is a separate controller |
| §4.2 Local-first / desktop app | Not required | Recommended (strongest mitigation) |
| §4.3 Owner self-unregister + cascade delete | Not required | Required |
| §4.4 Full Owner ToS at signup + cookie notice banner | Not required (no new Owners) | Required |
| §4.5 Contributor acknowledgement modal (M-15) | **Required** | Required |
| §4.6 Audit trail `updated_by` / `updated_at` (M-11) | **Required** (multiple editors share one tree) | Required |
| §4.7 Hetzner DPA + Cloudflare DPA | Required | Required |
| §4.8 Donate button infrastructure | Not required | Optional |
| `allow_owner_signup` flag | `False` | `True` |
| `owner_signup_requires_approval` flag | (n/a) | `True` (gated) or `False` (open) |
| `allow_contributor_signup` flag | `True` | `True` |

### Recommendation for "friends and family only"

If relatives only need to **add and edit information in your tree**, Mode B is
the cheapest path out of Mode A — skip §4.3, §4.4, §4.8, but still pay for
§4.1 (lawyer) and build §4.5, §4.6, §4.7.

If relatives genuinely need **their own separate trees** on your server, the
honest classification is Mode C (gated). The approval gate is worth doing for
abuse reasons, but do not let it create the illusion that the obligations
shrink.

---

## 7. Open questions awaiting legal review

From [PRIVACY_ANALYSIS.md §10](PRIVACY_ANALYSIS.md#10-open-questions-for-legal-review).
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
