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

**Status overall: TIER 1 AND TIER 2 SHIPPED.** All of §2.1–§2.7 are
shipped: §2.1 (central privacy config), §2.2 (public privacy-request flow,
originally "takedown"), §2.3 (privacy policy page + footer link), §2.4
(viewer notice on first share-link load), §2.5 (per-share acknowledgement),
§2.6 (right-of-access export per Individual), §2.7 (public privacy-request
intake — the §2.2 form generalized to removal, access, and correction
under GDPR Art. 15-17). Mode A is defensible. Tier 2 (operational
hardening) is now complete: §3.1–§3.9 are all shipped (§3.8 children/minors
and §3.9 TreeView selection-mode prefill were the last two). The next work
is Tier 3 §4.1 — the lawyer review go/no-go gate, which must precede any
§4.2–§4.10 code.

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
  needs a privacy-request intake (removal / access / correction), viewer
  notice, audit trail, right-of-access export.
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
| Privacy-request SLA (removal / access / correction) | 30 days. |
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
| **SLA** | Service Level Agreement | A promised response time (e.g. privacy-request SLA = 30 days). |
| **SMTP** | Simple Mail Transfer Protocol | Email-sending backend. Required for verification, privacy-request notifications, contributor invites. |
| **ToS** | Terms of Service | The contract the Owner accepts at signup. |

The config block in §6 has its own inline glossary for the acronyms it uses; this section covers the body of the document.

---
### When to involve a lawyer

**Not blocking for Tier 1 or Tier 2.** Mode A is a hobby deployment with one
controller (the operator), no monetization, no analytics, no public signups,
and a documented privacy-request flow. The conservative defaults in §6 pick
the strictest EU thresholds, so the configuration is compliant in every
jurisdiction it might touch. A regulator complaint against a one-person
hobby tree that responds to privacy requests within 30 days is
realistically near-zero risk.

**Required before Tier 3 (Mode B or Mode C launch).** Once any of the following
becomes true, schedule a paid review:

- Contributor signup is enabled (`allow_contributor_signup = True`) — minimum
  trigger for Mode B.
- Owner signup is enabled in any form, gated or open (`allow_owner_signup = True`
  with or without `owner_signup_requires_approval`) — triggers full Mode C.
- An **embedded** payment integration is added — i.e. a checkout, donor
  receipt, donor wall, or any flow where money or donor PII passes through
  NovoTree's server or DB. **Pure link-out donate buttons** (a heart icon
  that opens GitHub Sponsors or Ko-fi in a new tab, NovoTree never sees the
  transaction) do NOT trigger Tier 3 — see §4.8.
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

> **Note on editability:** `PrivacySettings` is loaded from environment
> variables (`/etc/novotree.env`) at startup and is **read-only at runtime**.
> Changes today require editing the env file and `systemctl restart novotree`.
> An in-app admin UI for these values is a Mode-C concern — see §4.10.

### 2.2 Public takedown / "remove me" flow (M-04)

**Renamed in §2.7.** The intake form, table, endpoints, and Owner UI were
generalized from "takedown" to "privacy request" once §2.7 added the access
and correction request kinds. The original "removal" path described below
still works the same way — `request_type='removal'` is one of the three
options on the form, and is the only one §2.2 ever shipped. This section is
kept in present tense for the historical narrative; the current names are
those in §2.7.

Single highest risk-reduction action. Even in Mode A.

The form must serve two distinct requester populations — viewers who saw a
share link AND off-platform people who never did. See
[PRIVACY_ANALYSIS.md §1 → "Who files a privacy request"](PRIVACY_ANALYSIS.md#who-files-a-privacy-request--two-populations).
Consequence: takedown is **text-only** and reachable from a single public
URL. Any TreeView-driven "select individuals to remove" UI is a future
convenience for the viewer population only — never a substitute (a
TreeView selection mode that prefills the form is the Tier-2 follow-up
below).

- [x] New table `privacy_requests` (renamed from `takedown_requests` in §2.7)
      in [database/system_models.py](../database/system_models.py):
      `id`, `tree_owner_id`, `individual_id` (nullable), `request_type`,
      `requester_name`, `requester_email`, `requester_phone` (nullable),
      `message`, `status` (open / acknowledged / resolved / escalated),
      `created_at`, `resolved_at`, plus `reminder_sent_at` / `escalated_at`
      for sweeper idempotency.
- [x] Public endpoint `POST /privacy/request` (renamed from `/privacy/takedown`
      in §2.7) in
      [backend/api/privacy_requests.py](../backend/api/privacy_requests.py).
      Rate-limited by IP (5/hour) via
      [backend/api/_privacy_request_rate_limit.py](../backend/api/_privacy_request_rate_limit.py).
      No auth. Disabled in `is_local` (desktop) mode.
- [x] Email notification to the Owner on receipt; reminder at day 14;
      auto-escalate at `privacy_request_sla_days` (default 30). Sweep logic
      lives in
      [backend/api/_privacy_request_sweep.py](../backend/api/_privacy_request_sweep.py);
      shared SMTP helper extracted to
      [backend/api/_email.py](../backend/api/_email.py).
- [x] In-process scheduler started from FastAPI lifespan in
      [backend/main.py](../backend/main.py) — primary path.
- [x] Standalone backstop at
      [tools/ops/scheduled_jobs/](../tools/ops/scheduled_jobs/)
      driven by `novotree-backend-monitor.{service,timer}` on the VM. Runs
      only when the backend `/health` probe fails. DB-level claim columns
      make both paths safe to run concurrently.
- [x] Persistent **"Remove Me / Our Privacy"** link cluster rendered globally
      in [frontend/src/App.tsx](../frontend/src/App.tsx) via
      [PrivacyFooter.tsx](../frontend/src/components/layout/PrivacyFooter.tsx).
      Visible to viewers (share-token sessions) as well as owners. Hidden
      in `isLocalApp`. (Label "Remove Me" preserved verbatim post-§2.7;
      target URL now `/privacy/request`.)
- [x] Public privacy-request form page at `/privacy/request` (renamed from
      `/privacy/takedown` in §2.7) —
      [frontend/src/pages/legal/PrivacyRequestPage.tsx](../frontend/src/pages/legal/PrivacyRequestPage.tsx).
- [x] Owner-scoped triage queue: `GET /privacy/requests`,
      `PATCH /privacy/requests/{id}`, `DELETE /privacy/requests/{id}` in
      [backend/api/privacy_requests.py](../backend/api/privacy_requests.py).
      Owner sees only their own rows; allowed transition is
      `open|escalated → resolved`. Hard delete is allowed only on terminal
      rows (operator escape hatch before retention sweep). UI at
      [frontend/src/pages/legal/PrivacyRequestsPage.tsx](../frontend/src/pages/legal/PrivacyRequestsPage.tsx),
      reachable from the "Privacy requests" sidebar item.
- [x] Retention enforcement: sweep pass in
      [_privacy_request_sweep.py](../backend/api/_privacy_request_sweep.py)
      hard-deletes `resolved` / `escalated` rows older than
      `privacy_request_retention_months` (default 12). No separate cron —
      same sweep cadence as reminders / escalations.

**Cross-Owner admin triage deferred to Mode C.** The Owner-scoped queue
above is sufficient when the operator is the only Owner (Mode A) — they
*are* the admin for their own data. The admin endpoint that lets the
operator triage privacy requests *across all Owners* (needed once multiple
Owners exist on the server) is §4.9.

**Tier-2 follow-up:** TreeView selection mode that prefills the
privacy-request form with selected `individual_ids` for the viewer
population. See §3.9.

### 2.3 Privacy policy page + footer link (Phase 0.2-0.3 partial)

In Mode A the Owner is the operator — accepting one's own ToS is moot, and the
cookie notice banner is unnecessary (auth cookies are seen only by the operator;
viewers carry a strictly-necessary share token in `sessionStorage` covered by
ePrivacy 5(3) and addressed by the viewer notice in §2.5). What is needed in
Tier 1 is a privacy policy page that the privacy-request form can link to,
and a footer that exposes both.

- [x] Backend serves the policy markdown via
      `GET /privacy/policy` (read from
      [docs/legal/privacy.md](legal/privacy.md), versioned via
      `privacy_policy_version`). Endpoint lives in
      [backend/api/privacy.py](../backend/api/privacy.py).
- [x] Frontend renders it under
      [frontend/src/pages/legal/PrivacyPage.tsx](../frontend/src/pages/legal/PrivacyPage.tsx)
      at route `/legal/privacy`. Minimal in-tree markdown renderer in
      [renderPolicyMarkdown.tsx](../frontend/src/pages/legal/renderPolicyMarkdown.tsx)
      avoids adding a third-party markdown dependency on a public route.
- [x] Link pair on every page: **Remove me · Our Privacy** — extracted into
      [PrivacyLinks.tsx](../frontend/src/components/layout/PrivacyLinks.tsx)
      and used by both [PrivacyFooter.tsx](../frontend/src/components/layout/PrivacyFooter.tsx)
      (document-flow pages) and the Tree pages' top bar
      ([TreePage.tsx](../frontend/src/pages/tree/TreePage.tsx),
      [TreeOverviewPage.tsx](../frontend/src/pages/tree/TreeOverviewPage.tsx)).
      The Tree pages render as `fixed inset-0 z-50` fullscreen overlays that
      cover the global footer, so embedding the same links in their chrome
      is the only path that keeps the "Remove Me" affordance visible to
      share-link viewers — the population the link primarily exists for.
      Hidden in `isLocalApp` everywhere.

### 2.4 Viewer notice on first share-link load (M-16)

- [x] First load of `?share=<token>` shows a small notice with text from
      [PRIVACY_ANALYSIS.md §9.3](PRIVACY_ANALYSIS.md#93-viewer-notice-shown-on-first-share-link-load).
      Dismissed once per token (key =
      `viewer_notice_dismissed:<token_hash>:<cookie_notice_version>` in
      `sessionStorage`; the token is SHA-256 hashed so the raw share token
      never appears under this key, and the version suffix re-shows the
      notice when `cookie_notice_version` is bumped).
- [x] Component: [ViewerNotice.tsx](../frontend/src/components/ViewerNotice.tsx).
      Mounted at the App level in
      [frontend/src/App.tsx](../frontend/src/App.tsx); reads
      `shareToken` / `isLoading` from
      [AuthContext](../frontend/src/contexts/AuthContext.tsx) and
      `cookie_notice_version` from
      [usePrivacyConfig](../frontend/src/hooks/usePrivacyConfig.ts).
      Hidden in `isLocalApp` (no viewers there); not gated on
      `deployment_mode` — applies in Modes A, B, and C.

### 2.5 Per-share acknowledgement (M-03)

A defensive log of "I, the Owner, confirmed I had the right to share this tree"
each time a share link is created. Useful evidence if a relative forwards the
link further than intended and someone later complains.

- [x] New table `auth_share_consents` in
      [database/system_models.py](../database/system_models.py): `id`,
      `editor_id`, `tree_owner_id`, `share_token_id` (nullable, reserved for
      future extend flow), `accepted_at`, `accepted_ip`,
      `privacy_policy_version`. **Diverges from spec:** stores
      `privacy_policy_version` instead of `tos_version`. Mode A ships no
      ToS (Tier 3 §4.4); the privacy policy is the only legal document
      currently in force, and the modal's "respond within 30 days" promise
      is policy-driven. `tos_version` was a holdover from the original
      §9.4 draft assuming ToS existed at Tier 1.
- [x] Modal shown when Owner clicks "Create share link", text verbatim from
      [PRIVACY_ANALYSIS.md §9.4](PRIVACY_ANALYSIS.md#94-per-share-acknowledgement-shown-when-creating-or-extending-a-share-link).
      Component: [ShareConsentModal.tsx](../frontend/src/components/ShareConsentModal.tsx).
      Mounted in both share-token entry points:
      [UserManagerPage.tsx](../frontend/src/pages/users/UserManagerPage.tsx)
      (full ShareTokensTab) and
      [DashboardPage.tsx](../frontend/src/pages/dashboard/DashboardPage.tsx)
      (ShareLinksWidget). The "or extending" clause of §9.4 is **deferred** —
      no extend-visibility endpoint or UI action exists today (only
      Create and Revoke). When such an action is added, reuse the same
      modal and write a fresh `auth_share_consents` row (the nullable
      `share_token_id` already permits this).
- [x] Persist consent on submit. `POST /users/share-tokens` requires
      `acknowledgement: true` in the body and rejects with HTTP 400
      otherwise, writing the consent row in the same transaction as the
      share token. Client IP is captured via the shared helper at
      [backend/api/_client_ip.py](../backend/api/_client_ip.py), extracted
      from previously-duplicated copies in
      [backend/main.py](../backend/main.py) and
      [backend/api/privacy_requests.py](../backend/api/privacy_requests.py).

### 2.6 Right-of-access export per Individual (M-09, Phase 7)

- [x] Endpoint `GET /individuals/{id}/data-export` returning JSON of every
      field, event, media reference, and contributor attribution (`created_by` /
      `created_at`). Owner-only. Lives in
      [backend/api/individuals.py](../backend/api/individuals.py) (next to the
      resource — deviates from PRIVACY_ANALYSIS.md Phase 7.1 which pointed at
      `export.py`; that file is reserved for whole-tree GEDCOM export with
      different auth scope). Delivered as `application/json` with a
      `Content-Disposition: attachment` header. `_meta` block documents that
      `updated_by` / `updated_at` are deferred to Tier 3 §4.6 and that
      `FamilyMember` / `FamilyChild` join rows carry no per-link attribution
      today (parent Family's `created_by` is the proxy; see
      [docs/notes.txt](../notes.txt) under "Go contributors" for the column-add
      action item).
- [x] "Export data" button on Individual page
      ([IndividualDetailPage.tsx](../frontend/src/pages/individuals/IndividualDetailPage.tsx)).
      Hidden for viewers (share-token) and contributors — owner-only, mirroring
      the backend gate. Reuses the shared `saveBlob` helper used by the
      whole-tree GEDCOM export so the local desktop app gets a native SaveAs
      dialog without extra work.

**Scope and intake — what this section does and does not cover.** §2.6 ships
the *Owner-side machinery* for GDPR Art. 15 (right of access): the legal model
is that NovoTree is the processor and the Owner is the controller, so when a
data subject asks "what do you hold about me?", the Owner must answer — this
endpoint is the tool that makes the answer cheap to produce and uniformly
formatted. It is deliberately Owner-only; exposing the export to viewers
would publish other relatives' PII to anyone with a share link.

The matching *requester-side* intake channel is **not yet built**. Today a
data subject who wants their own data must either (a) write to
`privacy_contact_email` published in the privacy policy (§2.3), or (b) abuse
the §2.2 takedown form by typing "I want my data, not removal" into the
free-text message — neither is a deliberate access-request UX. §2.7 below
closes this gap by generalizing the §2.2 form into a single public
*privacy-request* intake that routes access, correction, and removal
requests through one URL, one mailbox, and one SLA — and uses this §2.6
endpoint to *fulfil* the access ones once the Owner triages them.

### 2.7 Public privacy-request intake (M-04 extension; GDPR Art. 15–17)

**Status:** BUILT. The §2.2 form, table, endpoints, and Owner UI were
generalized into a three-option (removal / access / correction) intake;
the renames listed below all landed. See `privacy_requests.py`,
`_privacy_request_sweep.py`, and the `PrivacyRequest` model.

**Why this exists.** §2.6 above ships the Owner-side export tool, but no
requester-facing UI exists for a data subject to *ask* for that export. The
takedown form (§2.2) handles erasure requests (Art. 17) from off-platform
people via a public URL with no auth; access requests (Art. 15) and
correction requests (Art. 16) have no equivalent entry point today. A
regulator's first question on an Art. 15 complaint is *"how could the
subject reach you to make the request?"* — the current answer is "find the
privacy contact email in the policy and write a free-form message," which
is the same answer §2.2 was built to *replace* for erasure.

**Design.** Promote the existing §2.2 form into a generic privacy-request
intake. One public URL, one table, one triage queue, one SLA — three
request kinds:

| `request_type` | GDPR article | Owner fulfillment path |
|---|---|---|
| `removal` (preserves §2.2 behavior) | Art. 17 | Owner deletes the records or marks resolved after manual action. |
| `access` | Art. 15 | Owner identifies the named Individual from the message text, clicks "Export data" (§2.6), forwards the JSON to `requester_email`, marks resolved. |
| `correction` | Art. 16 | Owner edits the records on the Individual page, marks resolved. |

**Why one table, not three.** All three request kinds share the same shape
(requester identity + message + kind + status), the same retention window
(default 12 months — see `privacy_request_retention_months`), the same SLA
(`privacy_request_sla_days`), the same triage queue UI, the same
email-the-Owner / day-14 reminder / SLA escalation machinery, and the same
hostile-population threat model (the form is public and rate-limited). A
second table would duplicate every one of those mechanisms for no benefit.

### Naming — internal rename, user-facing label preserved

Single user-facing affordance keeps its recognizable brand; everything
behind the form gets honest names. **No data-migration code is needed**
because the project has no production users yet (single-Owner dev,
backups + GEDCOM/JSON exports cover any local rows). A drop-and-recreate
on the `data.sqlite.system` table is the simplest path.

**Keep verbatim — user-visible:**

- Footer link label: **"Remove me"** in
  [PrivacyLinks.tsx](../frontend/src/components/layout/PrivacyLinks.tsx)
  /
  [PrivacyFooter.tsx](../frontend/src/components/layout/PrivacyFooter.tsx)
  and in the Tree pages' top bar.
- The systemd unit name on the VM: `novotree-backend-monitor.{service,timer}`.
  It is request-kind-agnostic; the unit watches backend `/health` and
  fires the standalone sweeper backstop regardless of what is in the
  queue. Do not rename — it would invalidate the deployed
  `novospace.git/scripts/deployment/` units and require a coordinated
  cut-over on the VM.

**Rename everything else (internal-only):**

| Today | After §2.7 |
|---|---|
| `takedown_requests` (table) | `privacy_requests` |
| `TakedownRequest` (SQLAlchemy model in [system_models.py](../database/system_models.py)) | `PrivacyRequest` |
| `POST /privacy/takedown` (public endpoint) | `POST /privacy/request` |
| `GET/PATCH/DELETE /takedown/*` (owner triage endpoints) | `GET/PATCH/DELETE /privacy/requests/*` (note: under `/privacy` namespace, not its own top-level) |
| `backend/api/takedown.py` | `backend/api/privacy_requests.py` |
| `backend/api/_takedown_sweep.py` | `backend/api/_privacy_request_sweep.py` |
| `backend/api/_takedown_rate_limit.py` | `backend/api/_privacy_request_rate_limit.py` |
| `tools/ops/scheduled_jobs/jobs/takedown_requests_monitor.py` | `tools/ops/scheduled_jobs/jobs/privacy_requests_monitor.py` |
| `frontend/src/api/takedown.ts` | `frontend/src/api/privacy_requests.ts` |
| `frontend/src/pages/legal/TakedownPage.tsx` (public form) | `frontend/src/pages/legal/PrivacyRequestPage.tsx` |
| `frontend/src/pages/legal/TakedownsPage.tsx` (owner triage) | `frontend/src/pages/legal/PrivacyRequestsPage.tsx` |
| `frontend/src/pages/legal/TestTakedownTimestampPanel.tsx` | `frontend/src/pages/legal/TestPrivacyRequestTimestampPanel.tsx` |
| `takedown_request_retention_months` (config key in [config.py](../backend/config.py)) | `privacy_request_retention_months` |
| `takedown_sla_days` (config key in [config.py](../backend/config.py); env `TAKEDOWN_SLA_DAYS`) | `privacy_request_sla_days` (env `PRIVACY_REQUEST_SLA_DAYS`) |
| Sidebar nav label "Takedowns" (in [Sidebar.tsx](../frontend/src/components/layout/Sidebar.tsx)) | "Privacy requests" |
| Tags in FastAPI routers (`tags=["Privacy"]` already today — no change needed there) | (unchanged) |

**SLA config-key decision at implementation time.** The original spec
proposed keeping `takedown_sla_days` verbatim to avoid forcing operators
to edit `/etc/novotree.env` on the VM, with an optional alternative to
rename + add a backward-compat env read. At implementation we chose the
**clean rename with no back-compat** because the project is pre-launch
and no operator has the old env key set. The new key is
`privacy_request_sla_days` (env `PRIVACY_REQUEST_SLA_DAYS`). The old env
var is not read at all — setting it would silently fall through to the
30-day default.

**Page route URL — also renamed.**

`/privacy/takedown` → `/privacy/request` for the public form;
`/legal/takedowns` (or wherever the owner-scoped triage page is mounted in
the frontend router) → `/legal/privacy-requests`. The footer link's *target
URL* moves with the rename — only the *label text* "Remove me" stays the
same. Acceptable here because the project is pre-launch; there are no
external bookmarks to break.

### Schema — drop and recreate

```python
# database/system_models.py — replaces TakedownRequest entirely.

class PrivacyRequest(SystemBase):
    """Public privacy request from a data subject (GDPR Art. 15-17).

    Submitted via the unauthenticated POST /privacy/request endpoint and
    reviewed by the tree owner. Supersedes the original takedown_requests
    table (§2.2); the rename happened in §2.7 once access and correction
    request kinds were added.
    """
    __tablename__ = "privacy_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tree_owner_id = Column(String, nullable=False)
    individual_id = Column(String, nullable=True)
    request_type = Column(String, nullable=False)  # 'removal' | 'access' | 'correction'
    requester_name = Column(String, nullable=False)
    requester_email = Column(String, nullable=False)
    requester_phone = Column(String, nullable=True)
    message = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(String, nullable=False)
    resolved_at = Column(String, nullable=True)
    reminder_sent_at = Column(String, nullable=True)
    escalated_at = Column(String, nullable=True)
```

`init_system_db()` runs `Base.metadata.create_all(engine)` on first boot;
since no production rows exist, the implementer can either:

- delete the existing `data.sqlite.system` file from the dev VM and let
  it recreate, OR
- inside `init_system_db()`, run a one-shot
  `DROP TABLE IF EXISTS takedown_requests` before `create_all` so the
  rename is idempotent across re-runs.

The second is friendlier (no manual file deletion step) and self-cleans
on every boot until the codebase is well past the rename. After 1–2
releases the `DROP TABLE` line can come out.

### Action items (sequential)

- [x] **Schema:** rename model class `TakedownRequest` → `PrivacyRequest`,
      table name `takedown_requests` → `privacy_requests`, add
      `request_type` column (NOT NULL, enum of three values, no default —
      every row must explicitly state its kind). Add the one-shot
      `DROP TABLE IF EXISTS takedown_requests` in `init_system_db()`.
- [x] **Backend rename pass:**
      `backend/api/takedown.py` → `privacy_requests.py`;
      `_takedown_sweep.py` → `_privacy_request_sweep.py`;
      `_takedown_rate_limit.py` → `_privacy_request_rate_limit.py`.
      Update imports in [backend/main.py](../backend/main.py) (router
      include block; `AUTH_ONLY_PATHS` set still needs `/privacy/request`
      and the new owner-triage prefix). Update FastAPI router prefixes:
      public router stays at `prefix="/privacy"` with `.post("/request")`;
      owner router moves from `prefix="/takedown"` to
      `prefix="/privacy/requests"`.
- [x] **Backend Pydantic:** add `request_type: Literal["removal", "access", "correction"]`
      to the request-creation schema. No default — the form must send it
      explicitly. The Pydantic enum value flows straight into the DB row.
- [x] **Backend email templates:** the sweep emitter in
      `_privacy_request_sweep.py` branches on `request_type` for subject
      and body. Subject template uses
      `REQUEST_KIND_LABEL = {"removal": "Removal", "access": "Access", "correction": "Correction"}`.
      Body text per kind lives next to the existing copy.
- [x] **Standalone backstop:** rename
      `tools/ops/scheduled_jobs/jobs/takedown_requests_monitor.py` →
      `privacy_requests_monitor.py`. Update the job registry in
      `tools/ops/scheduled_jobs/jobs/__init__.py`. The systemd unit
      `novotree-backend-monitor.{service,timer}` itself does NOT change —
      it invokes the package, not a specific job file.
- [x] **Config:** rename `takedown_request_retention_months` →
      `privacy_request_retention_months` AND `takedown_sla_days` →
      `privacy_request_sla_days` in [config.py](../backend/config.py).
      Env vars renamed correspondingly (`PRIVACY_REQUEST_RETENTION_MONTHS`,
      `PRIVACY_REQUEST_SLA_DAYS`). No back-compat — project is pre-launch.
- [x] **Frontend rename pass:** `api/takedown.ts` → `api/privacy_requests.ts`;
      `pages/legal/TakedownPage.tsx` → `PrivacyRequestPage.tsx`;
      `pages/legal/TakedownsPage.tsx` → `PrivacyRequestsPage.tsx`;
      `TestTakedownTimestampPanel.tsx` → `TestPrivacyRequestTimestampPanel.tsx`.
      Update all imports. Update router paths in
      [App.tsx](../frontend/src/App.tsx).
- [x] **Frontend form:** in the renamed `PrivacyRequestPage.tsx` add a
      `request_type` selector at the top, three radio options, no
      pre-selection — the user must pick. Plain-language labels (no
      GDPR article numbers); the privacy policy carries the legal text.
      Page title: *"Privacy request — remove, access, or correct your
      data"* (final copy lives in [PRIVACY_ANALYSIS.md §9.8](PRIVACY_ANALYSIS.md)).
- [x] **Footer labels:** keep "Remove me" verbatim in
      [PrivacyLinks.tsx](../frontend/src/components/layout/PrivacyLinks.tsx)
      and [PrivacyFooter.tsx](../frontend/src/components/layout/PrivacyFooter.tsx).
      Only the *target URL* changes from `/privacy/takedown` to
      `/privacy/request`. The label is now load-bearing in a way it was
      not before (it advertises one of three rights), which is the entire
      naming-discussion compromise. Bump the label *only* if a real user
      reports confusion — not pre-emptively.
- [x] **Owner triage UI:** in `PrivacyRequestsPage.tsx` show
      `request_type` as a column with a small badge. Three colors are
      used; no icons. For `access` rows, an inline "Open Individual"
      link is rendered if the requester's message contains a GEDCOM-shaped
      `I\d+` ID. A `request_type` filter in the queue header lets the
      Owner filter by kind during triage.
- [x] **Sidebar:** label "Takedowns" → "Privacy requests" in
      [Sidebar.tsx](../frontend/src/components/layout/Sidebar.tsx).
- [x] **Public form copy — PRIVACY_ANALYSIS.md §9.8:**
      replace §9.5 with a generalized version. Three short paragraphs
      naming the three options to the requester in plain language. Each
      paragraph references the relevant Art. only as a footnote-style
      parenthetical, not in the lead. Default radio = unselected (the
      form rejects submission until one is picked).
- [x] **Privacy policy update** ([privacy.md](privacy.md)):
      the "Your rights" section now names access, correction, and removal
      explicitly, all pointing at the same form URL. `privacy_policy_version`
      bumped to `1.1`. This is the *legal load-bearing* surface — the GDPR
      Art. 12-14 transparency obligation is discharged here, not in the
      footer label.
- [x] **Docs sweep:** grep for `takedown` across the whole repo and
      update prose references in:
      [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) (this file — §2.2 carries a
      "renamed in §2.7" note, status table updated),
      [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) (M-04, Phase 4 file
      pointers, "Who files a takedown" → "Who files a privacy request"),
      [docs/notes.txt](../notes.txt) (the "Test" section's
      "Takedown - deploy on VM" item),
      [docs/ops/DEPLOYMENT.md](../ops/DEPLOYMENT.md) (mentions of the
      sweeper),
      [docs/features/LOCAL_APP.md](../features/LOCAL_APP.md) (if it
      references the form).
      Keep the *historical* word "takedown" only where it accurately
      describes the original §2.2 scope or appears in commit history.

### What this does NOT do

- **It does not auto-export.** The Owner still triages access requests by
  hand and clicks "Export data" on the named Individual. Auto-fulfillment
  would require identity verification machinery that does not exist (and
  that, in Mode A's hostile-population threat model, would be the wrong
  trade-off — a stranger who guesses a relative's name is not entitled to
  the JSON, even if they correctly identify the Individual).
- **It does not change the SLA.** All three request kinds share the
  30-day GDPR Art. 12(3) SLA encoded in `privacy_request_sla_days` (the
  config key was renamed at implementation time — see the SLA decision
  paragraph above).
- **It does not replace `privacy_contact_email`.** The contact email
  remains the documented channel for everything that does not fit the
  form (regulator inquiries, journalist questions, complex multi-subject
  requests). The form is the path for *individual data subjects*.
- **It does not address the share-link viewer population separately.** The
  Tier-2 §3.9 selection-mode prefill (TreeView → form with
  `individual_ids` prefilled) already accommodates viewers; it stays
  scoped to removal at first and can be extended to access later if
  ever asked for.
- **It does not introduce identity verification.** The form trusts the
  requester's stated identity. The Owner is expected to use judgment
  before fulfilling an *access* request — for example, by replying to
  the stated email and asking a question only the real subject could
  answer. This matches §2.2's existing posture.
- **It does not migrate any rows.** Project is pre-launch; the rename is
  a destructive schema swap on a dev DB. If by the time §2.7 is built
  there are real `takedown_requests` rows on a deployed VM, the
  implementer must add a data-copy migration step before dropping —
  re-evaluate the "drop and recreate" decision at implementation time.

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

### 3.1 Enforce signup flags

The behavior is mode-agnostic — a False flag must reject the corresponding
endpoint regardless of deployment mode. The framing "disable signups in
Mode A" is just the motivating case: the flag defaults
(`allow_owner_signup=False` and `allow_contributor_signup=False` in Mode A;
contributor True in Mode B; both True in Mode C) already encode the
per-mode rule. This task is the runtime enforcement.

- [x] Reject `POST /auth/owner-signup` with HTTP 403 if
      `PrivacySettings.allow_owner_signup` is False. Gate is the first line
      of the handler (`_require_signup_enabled`), above the SMTP gate.
- [x] Reject `POST /auth/contributor-signup` with HTTP 403 if
      `PrivacySettings.allow_contributor_signup` is False. Same helper.
- [x] Hide signup links from frontend when disabled. Wired by ANDing
      `settings.allow_registration` with `privacy_settings.allow_owner_signup`
      in the `/auth/public-config` handler so the existing `signup_enabled`
      field flips automatically; SignupPage already consumes it (zero
      frontend change for the gate itself).
- [x] Consolidate `Settings.admin_email` (env var `ADMIN_EMAIL`) and
      `PrivacySettings.privacy_contact_email` (env var
      `PRIVACY_CONTACT_EMAIL`) — same mailbox, two homes, two env vars.
      `privacy_contact_email` chosen as the single source of truth;
      `Settings.admin_email` and the `ADMIN_EMAIL` env var deleted. Every
      consumer migrated: `/auth/public-config` (API field renamed
      `admin_email`→`contact_email`, frontend `adminEmail`→`contactEmail`
      across the hook + three auth pages), the privacy-request intake
      notification, and the sweep escalation fallback. `.env.public.example`
      renamed; no `ADMIN_EMAIL` existed in the deployment scripts.

### 3.2 Backup retention enforcement (M-10)

- [x] Update `vm-backup.py` (in `novospace.git/scripts/deployment/`) to
      delete backups older than `backup_retention_days` (default 30).
      Done: `vm-backup.py` reads `BACKUP_RETENTION_DAYS` (env, default 30,
      min 1 — the same value the backend reads from `/etc/novotree.env`)
      instead of the old hardcoded `KEEP_DAYS=30`; `--keep-days` overrides
      for manual runs. The backup cron (`vm-setup.py`) was moved to root's
      crontab so it can source the `root:root 600` `/etc/novotree.env` and
      pass the var through to the `novospace`-run script. Single source of
      truth; the dev wrapper inherits it via its subprocess call.
      `BACKUP_RETENTION_DAYS` added to `backend/.env.public.example` so a
      fresh deployment carries the value explicitly.
      A missing `/etc/novotree.env` at cron time is treated as
      **exceptional** (it should never happen in production — `vm-setup.py`
      step 6 writes it): the cron line logs an `ERROR` to
      `/var/log/novotree-backup.log` and `vm-backup.py --require-env` raises
      an ops alert via `notify_ops()`, then both fall back to 30 days so
      backups never silently stop. Emailing that alert to the operator is
      deferred to §3.4 (the `notify_ops()` seam is where it lands).
- [x] Document the 30-day window in the rendered privacy policy.
      Done: [privacy.md](privacy.md) already stated "30 days" (§6, §8 table,
      §8 prose); the §8 prose now notes the window is "30 days by default, and
      the value this deployment is configured with" so the static text does
      not silently drift if `backup_retention_days` is overridden.
      `privacy_policy_version` bumped 1.1 → 1.2.

### 3.3 Log scrubbing + retention (M-14)

- [x] Disable request-body logging in production
      ([backend/main.py](../backend/main.py),
      [backend/logging.py](../backend/logging.py)).
      Done: **verify-and-scrub**, not "remove a body logger" — none exists.
      The per-request middleware ([main.py](../backend/main.py) `owner_db_router`)
      emits a single access line of IP / method / path / HTTP-version / status
      via `access_logger.info`; it never logs the request body, and no other
      hot-path log line does either. The two PII-bearing spots were the signup
      logs in [auth.py](../backend/api/auth.py) (`owner_signup` /
      `contributor_signup`), which logged `{editor_id} <{email}>` at INFO —
      the email is now dropped, leaving `editor_id` (+ `owner_id` for
      contributors), the stable handle ops needs. The local-desktop save-as
      log in [local.py](../backend/api/local.py) records a byte count only
      (no content) and is left as-is.
- [x] Document log retention (14 / 30 days for access / error) in the privacy
      policy and in [novospace.git/docs/deployment.md](../../novospace.git/docs/deployment.md).
      Done. **Architectural note:** the backend funnels access logs and error
      logs into one stdout/journald stream under one unit (`novotree.service`),
      and journald retention is per-journal, not per-log-level. Per the chosen
      approach (option (a)), the VM applies a **single** journald window sized
      to `max(access, error) = 30d`, and the two config knobs
      (`access_log_retention_days` / `error_log_retention_days`) are
      reinterpreted/documented as **minimums** ("kept for at least N days").
      VM wiring lives in novospace `vm-setup.py`: `novotree.service` gains
      `LogNamespace=novotree`, and `/etc/systemd/journald@novotree.conf` sets
      `MaxRetentionSec` to the max of the two values **sourced from
      `/etc/novotree.env`** (the same single source of truth the backend reads
      — mirrors the §3.2 backup-retention pattern; no new hardcoded knob).
      The namespace scopes retention to novotree alone, leaving the host
      journal (Caddy, system units) untouched. `ACCESS_LOG_RETENTION_DAYS` /
      `ERROR_LOG_RETENTION_DAYS` added to `backend/.env.public.example` so a
      fresh deploy carries them explicitly. [privacy.md](privacy.md) §8 now
      states the windows as "at least 14/30 days" with a note that they track
      the configured value (mirroring §3.2); a "Log retention" section was
      added to novospace `docs/deployment.md`. `privacy_policy_version` bumped
      to **1.3** (note: §3.2 recorded a bump to 1.2, but both privacy.md and
      the config default were still 1.1 — only the §8 backup prose had landed;
      this change corrects that drift while bumping for the §8 log-retention edit).

### 3.4 Ops emails (notes.txt L258)

- [x] Email errors from logs + backup logs to admin. Operational, not strictly
      privacy work, but pairs with log scrubbing. Both halves email the
      consolidated ops mailbox `privacy_contact_email` (§3.1) — no new recipient
      env var was added.

  **Backup-log half (novospace `vm-backup.py`).** The §3.2 `notify_ops()` seam
  now emails as well as logging to stderr. A standalone sync SMTP sender
  (`_send_ops_email`) sources `SMTP_HOST/PORT/USER/PASSWORD/FROM` +
  `PRIVACY_CONTACT_EMAIL` from the environment — the script still can't import
  the backend, so it reads the same env the backend does (mirrors the §3.2
  `BACKUP_RETENTION_DAYS` pattern). It mirrors [_email.py](../../backend/api/_email.py)'s
  posture: returns False, never raises, so a failed alert can't break a backup;
  unset SMTP/recipient (dev, manual runs) falls back to the stderr line only.
  `notify_ops()` now fires for **backup failures** too (the `__main__` block
  wraps `do_backup()`), not just the §3.2 missing-`BACKUP_RETENTION_DAYS` case.
  **VM wiring:** the §3.2 backup cron sourced `/etc/novotree.env` but only
  forwarded `BACKUP_RETENTION_DAYS` across the `sudo -u novospace` boundary
  (`--preserve-env=`); novospace `vm-setup.py` now forwards the SMTP_* +
  `PRIVACY_CONTACT_EMAIL` vars too (single `BACKUP_CRON_PRESERVE_ENV_VARS` list)
  so the alert email actually has creds + a recipient on the production path.

  **Errors-from-logs half (backend-side, novotree).** A new scheduled job
  [error_log_digest.py](../../tools/ops/scheduled_jobs/jobs/error_log_digest.py)
  scans the `novotree` journald namespace (§3.3) for ERROR entries
  (`journalctl --namespace novotree -u novotree -p err --since <cursor>`) and
  emails a digest to `privacy_contact_email`, reusing the async
  [_email.py](../../backend/api/_email.py) `send_email` (no SMTP-logic dup). It
  is dispatched by the existing `novotree-backend-monitor` timer, but via a new
  `UNCONDITIONAL_JOBS` phase in
  [scheduled_jobs.py](../../tools/ops/scheduled_jobs/scheduled_jobs.py) that runs
  **before** the health gate — the SLA-sweep `BACKSTOP_JOBS` only run when the
  backend is *down*, but the digest must run while it is *up* (that is when
  errors occur). Dedup/firehose control is a self-throttle: a cursor file under
  `datasets/` records the last send; the job only emails once
  `ERROR_DIGEST_INTERVAL_HOURS` (env, default 3h) has elapsed, covering
  `[cursor, now]` so no window is skipped or double-reported. The first run just
  seeds the cursor (no boot-backlog email). No new systemd units.

  **Config knobs.** Two new env vars carried in `backend/.env.public.example`
  (→ `/etc/novotree.env` via vm-setup.py step 6): `ERROR_DIGEST_INTERVAL_HOURS`
  (default 3) and `JOURNAL_NAMESPACE` (default `novotree`). The namespace is
  *owned* by novospace `vm-setup.py` (it builds `LogNamespace=` and the
  `journald@<ns>` paths) and merely *published* into the env file so the digest
  job reads the same value instead of re-hardcoding it — mirrors the §3.2/§3.3
  "single source of truth in `/etc/novotree.env`" pattern. Neither is a privacy
  knob, so neither is disclosed in `privacy.md`.

> **Note — `privacy_policy_version`.** §3.4 is ops-only and changes no
> user-facing privacy prose, so the version is **not** bumped. This also
> corrects a stale claim above: the §3.3 entry narrates a bump "to 1.3", but
> neither [config.py](../../backend/config.py) (`PRIVACY_POLICY_VERSION` default)
> nor [privacy.md](privacy.md) (header) ever moved off **1.1** — only §3.3's §8
> *prose* edits (retention minimums) landed; the version label was never
> changed in code. Both files agree at 1.1 today. Per the operator's decision,
> the version stays at 1.1 until the project is actually deployed; do not bump
> it for §3.3's prose retroactively.

### 3.5 Admin triage — delivered via the Owner UI, not a CLI (notes.txt L211–212, L251)

A "ticket" here means a row in the `privacy_requests` table created by §2.2
+ §2.7. It is not a separate ticket-tracker product. "Triage" means the
operator reviewing rows where `status='open'` and choosing the next action
(forward to Owner / mark resolved / escalate / hide records, or for access
requests, run the §2.6 export and forward).

- [x] **Triage shipped as the Owner-facing privacy-request queue, superseding
      the originally-scoped admin CLI.** The item was first written as "a CLI is
      the canonical admin path in Mode A, because the in-app admin endpoint is
      deferred to Mode C (§4.9)". That premise was overtaken: the Owner-gated
      queue was built and it serves Mode A directly — in Mode A the operator
      *is* the only Owner, so the Owner UI is the operator's admin path; no
      separate CLI is needed.

  **Where it lives.** [PrivacyRequestsPage.tsx](../../frontend/src/pages/legal/PrivacyRequestsPage.tsx)
  (route `legal/privacy-requests`, in the sidebar) backed by `owner_router` in
  [privacy_requests.py](../../backend/api/privacy_requests.py), all gated by
  `Depends(require_owner)`:
    - **list open tickets** — `GET /privacy/requests` (returns open + escalated
      by default; `include_resolved` for the audit view);
    - **resolve a ticket** — `PATCH /privacy/requests/{id}` (`open → resolved`,
      `escalated → resolved`);
    - **force-delete on the Owner's behalf** — `DELETE /individuals/{id}`
      ([individuals.py](../../backend/api/individuals.py)) for the record, and
      `DELETE /privacy/requests/{id}` to close the ticket. SLA timing is the
      §2.7 / §3 sweep's concern (`_privacy_request_sweep.sweep_once`); the
      operator acts once a request is open/escalated.
    - For **access** requests, the §2.6 export
      (`GET /individuals/{id}/data-export`) produces the payload to forward.

  **The two items the UI does not cover, and why they are not CLI work:**
    - *list owners* — degenerate in Mode A (a single owner, `DEFAULT_OWNER_ID`).
      Enumerating owners only matters under Mode C, which has its own admin path
      (§4.9). Not a Mode-A gap.
    - *manual backup trigger* — an ops action, not an app feature: backups run
      from novospace `vm-backup.py` (daily cron installed by the deployer; a
      manual run is `sudo -u novospace … vm-backup.py`). Out of scope for an
      in-app admin surface.

  > **Note — bootstrap.** `notes.txt` (L211–212) still describes the
  > temp-`ALLOW_OWNER_SIGNUP` dance as the bootstrap "until the §3.5 admin CLI."
  > That CLI is not coming; the bootstrap flag-flip remains the documented way
  > to mint the first Owner account in `private` mode (it is account creation,
  > which the triage UI does not and should not do). The L251 musing
  > ("separate admin page, or better a CLI?") is resolved in favor of the
  > Owner UI.

### 3.6 Verify GEDCOM importer stamps `created_by`

Light future-proofing for Mode B / Mode C: if the importer leaves rows with
`created_by IS NULL`, switching out of Mode A later loses the historical
attribution to the Owner.

- [x] **Was a bug, not just a verify — now fixed.** The importer was leaving
      `created_by` / `created_at` NULL on *every* imported row (the exact
      attribution loss this item warns about). `owner_id` was not threaded
      below `import_for_owner` either. Fixed in
      [database/gedcom_import.py](../database/gedcom_import.py): `owner_id` is
      now threaded `import_for_owner -> import_gedcom -> _create_*` and the
      `Event` / `Media` build sites; a single `_stamp(row, owner_id, created_at)`
      helper stamps every imported `Individual`, `Family`, `Event`, `Media`,
      `IndividualName` row with `created_by = owner_id` and one shared
      `created_at` (reusing `database.models._now_iso()`, no duplicated format
      string). `FamilyMember` / `FamilyChild` are join rows with no attribution
      columns, so the parent `Family`'s `created_by` is the proxy (see section 2.6).
      The export never emits these internal columns into GEDCOM, so the
      round-trip stays lossless. Covered by the new regression test
      `TestImportStampsContributorAttribution` in
      [tests/database/test_database.py](../tests/database/test_database.py),
      which asserts no NULL `created_by` / `created_at` on any of the five row
      types and that `created_by == owner_id`. **Out of scope:** existing NULL
      rows from past imports are not back-filled (no migration), and column
      nullability is unchanged.

### 3.7 Special-category gating (M-05, Phase 6.1–6.2)

**Status: SHIPPED.** The viewer-exclusion half was Mode-A-relevant *today* —
[privacy.md](privacy.md) already promised sensitive fields are "excluded from
share links by default" — so this was an unkept live promise, not a deferrable
item. All three bullets landed in one pass.

- [x] **Tag sensitive data — two mechanisms.** (a) An inherently-religious
      **event-type allow-list** (`BAPM, BARM, BASM, BLES, CHR, CHRA, CONF, FCOM,
      ORDN`) is a single named constant `SENSITIVE_EVENT_CODES` in
      [database/models.py](../database/models.py), with an
      `event_is_sensitive(event)` helper (auto type OR manual flag). (b) A
      **manual per-record flag** the Owner sets by hand (the schema has no
      religion/ethnicity/health columns; that data is free text in notes and
      descriptions, which the user explicitly chose **not** to auto-scan). New
      nullable `Boolean` columns: `Individual.is_sensitive` (whole-person) +
      `Individual.notes_sensitive` (notes only), `Family.notes_sensitive`,
      `Event.is_sensitive`, `Media.is_sensitive`. Field-level granularity lets
      the Owner show a person's non-sensitive data while hiding only the
      sensitive parts.
- [x] **Owner "show sensitive" toggle** — per-session, Owner-only, default
      collapsed; one click reveals sensitive events, notes, and flagged media.
      **UI-only**: a shoulder-surfing guard, not access control, not persisted,
      never sent to the backend; viewers never get the toggle. Mounted on three
      surfaces so it is consistent wherever the Owner sees data:
      [IndividualDetailPage.tsx](../frontend/src/pages/individuals/IndividualDetailPage.tsx)
      (detail/edit view) and **both tree views**
      ([TreePage.tsx](../frontend/src/pages/tree/TreePage.tsx) per-individual,
      [TreeOverviewPage.tsx](../frontend/src/pages/tree/TreeOverviewPage.tsx) full
      tree) — on the tree, when off, the shared `hideSensitiveFromTree` helper
      strips sensitive events and notes AND drops whole-`is_sensitive` people
      *atomically* (the person plus every edge/couple referencing them, mirroring
      the backend's `_filter_excluded_individuals`), so React Flow never sees a
      dangling edge endpoint. The focus person is preserved even if sensitive so a
      per-individual tree never goes blank. The backend stamps `is_sensitive` /
      `notes_sensitive` on each `TreeNode` and `is_sensitive` on each
      `TreeNodeEvent` to drive it; mutating a sensitivity flag invalidates the
      `['tree']` query so the tree never shows a stale flag. The detail-page
      header also carries a visible whole-person **"Mark sensitive"** control (in
      addition to the Basic-Info modal checkbox) so flagging a person does not
      require hunting through a modal. All four "mark sensitive" checkboxes share
      one component (`SensitiveCheckbox`) for consistent look and copy. Covered by
      [hideSensitiveFromTree.test.ts](../frontend/tests/frontend/hideSensitiveFromTree.test.ts).
- [x] **Per-share-token `expose_sensitive` flag** (default False) on
      `AuthShareToken` ([database/system_models.py](../database/system_models.py)),
      set by the Owner in [ShareConsentModal.tsx](../frontend/src/components/ShareConsentModal.tsx).
      Server-side exclusion (a viewer never receives sensitive bytes) is enforced
      in [backend/api/tree.py](../backend/api/tree.py) (sensitive events dropped,
      `notes_sensitive` notes blanked, `is_sensitive` individuals omitted with
      their edges/couples) and [backend/api/media.py](../backend/api/media.py)
      (flagged media, and media of a sensitive individual, 404 / filtered).
      Exclusion keys off a new `get_viewer_context` dependency in
      [auth.py](../backend/api/auth.py) that distinguishes a share-token viewer
      from an editor and carries the token's `expose_sensitive`. **Full
      exclusion, no trace** (chosen over redaction): the viewer sees no
      placeholder. The Owner (non-share session) always sees everything.

**Explanatory affordance (the user's main addition).** The "what counts as
sensitive (religion, ethnicity, health, cause of death — GDPR Art. 9)" copy is a
single shared string `SENSITIVE_DATA_EXPLANATION` in
[frontend/src/constants/sensitiveData.ts](../frontend/src/constants/sensitiveData.ts),
surfaced via a reusable `SensitiveInfo` info icon at **all four** surfaces: the
show-sensitive toggle, every mark-sensitive checkbox (basic-info, notes, event,
photo), the Notes editor (a "think about sensitivity while typing" reminder),
and the share-link modal. Wording is reconciled with privacy.md:44 and M-05 —
not reinvented.

**Migration / back-fill posture.** No migration code (project is pre-production).
Columns are added to the model definitions only; `Base.metadata.create_all`
carries them on **fresh** DBs. Existing dev / VM owner DBs and the system DB are
**recreated** by the operator (stop service, drop tables / delete the sqlite
files, re-import GEDCOM from the Google Drive backup, recreate share tokens).
Existing rows are NULL = not-sensitive; no back-fill (mirrors §3.6's out-of-scope
back-fill). **`privacy_policy_version` is NOT bumped** (stays 1.1 until real
deployment, per §3.4's standing decision); privacy.md:44's "Sensitive fields"
promise already matches the shipped behavior, so no wording change was needed.

**Tests.** [tests/backend/test_sensitive_gating.py](../tests/backend/test_sensitive_gating.py)
asserts (per share token) that sensitive events (BAPM + manual), notes,
whole-person-flagged individuals, and flagged media are excluded when
`expose_sensitive` is False and included when True, and that the Owner session
always sees everything. `MINIMAL_GEDCOM` gained a BAPM event as a known sensitive
row.

### 3.8 Children data handling (M-06, Phase 6.3)

**Status: SHIPPED.** Like §3.7's viewer half, this was Mode-A-relevant *today* --
[privacy.md](privacy.md) (section 10, "Children's data") already promised all
three behaviors as in-force commitments ("minors are not exposed via share links
unless the Owner explicitly opts in per share link"), so this closed an unkept
live promise. All three bullets landed in one pass, plus the M-06 16th-birthday
re-confirm reminder.

- [x] **Detect minor + alive -- one shared helper.** `individual_is_minor(ind,
      threshold_years)` in [database/models.py](../database/models.py): exact
      `birth_date` within `child_age_threshold_years` of today AND `death_date`
      IS NULL. The threshold reads from
      `PrivacySettings.child_age_threshold_years` (default 16, already in
      [config.py](../backend/config.py) and published via `GET /privacy/config`).
      A frontend mirror `individualIsMinor()` lives in
      [sensitiveData.ts](../frontend/src/constants/sensitiveData.ts) (drives the
      upload-gate hint only; the server is the real gate). **Approx-only dates
      are NOT auto-detected** (we cannot prove age from "ABT 2015"; auto-hiding
      every undated person would gut the tree -- such cases use the manual
      `is_sensitive` path instead). The backend also stamps `is_minor` /
      `parental_consent` on each `TreeNode` so the frontend can mark + gate.
- [x] **Parental-consent photo-upload gate.** New nullable `Boolean`
      `Individual.parental_consent` (the Owner asserts they may store a minor's
      data). The authoritative gate is server-side: `_require_parental_consent`
      in [backend/api/media.py](../backend/api/media.py) rejects `POST
      /media/upload` and `/media/upload-file` with **403** for a living minor
      until consent is recorded. The frontend
      ([PhotoUploadDialog.tsx](../frontend/src/components/photo/PhotoUploadDialog.tsx))
      shows an "I have parental consent" checkbox that disables OK until ticked
      and persists `parental_consent`; the
      [IndividualDetailPage](../frontend/src/pages/individuals/IndividualDetailPage.tsx)
      also carries a standalone consent control (shown only `isOwner && isMinor`)
      next to the §3.7 "Mark sensitive" control.
- [x] **Per-share-token `expose_minors` flag** (default False) on
      `AuthShareToken` ([database/system_models.py](../database/system_models.py)),
      **independent of `expose_sensitive`** (a link can expose one category but
      not the other). When False, living minors are excluded **entirely** from
      the viewer payload -- their node, every edge/couple referencing them
      (reusing the existing `_filter_excluded_individuals` machinery in
      [tree.py](../backend/api/tree.py)), and their media
      ([media.py](../backend/api/media.py) `_media_hidden_from_viewer`, now ctx-
      driven and considering both categories). Set by the Owner in
      [ShareConsentModal.tsx](../frontend/src/components/ShareConsentModal.tsx)
      (second "Include minors" checkbox, default off); surfaced on each link via
      a `ShareMinorBadge` next to the sensitive badge. The Owner (non-share
      session) always sees minors -- there is no minor-hiding toggle for the
      Owner (unlike §3.7's show-sensitive toggle); minors are purely a
      share/viewer concern.

**16th-birthday re-confirm reminder (M-06 bullet 3).** New unconditional
scheduled job
[minor_consent_reminder.py](../tools/ops/scheduled_jobs/jobs/minor_consent_reminder.py)
(modeled on the §3.4 error-log digest): scans every owner tree via
`owner_info.list_owners()`, finds individuals who crossed the threshold (consent
recorded, `consent_reminder_sent_at` NULL, no longer a minor), emails the Owner
once to re-confirm, and stamps `consent_reminder_sent_at` for per-row
idempotency. Self-throttled by a cursor file to `MINOR_REMINDER_INTERVAL_HOURS`
(env, default 24); first run seeds the cursor (no boot backlog); SMTP-off
deployments skip cheaply.

**Explanatory affordance.** Reuses the §3.7 pattern: a `minorDataExplanation(N)`
helper in [sensitiveData.ts](../frontend/src/constants/sensitiveData.ts)
interpolates the threshold (never hardcodes 16) and is reconciled with
privacy.md section 10 and M-06 -- surfaced at the consent checkbox, the detail-
page consent control, and the share-link modal.

**Migration / back-fill posture (mirrors §3.6 / §3.7).** No migration code
(pre-production). New columns (`parental_consent`, `consent_reminder_sent_at` on
Individual; `expose_minors` on AuthShareToken) ride `Base.metadata.create_all`
on fresh DBs; the operator recreates existing dev/VM DBs. Existing rows are NULL
= not-consented / not-reminded; no back-fill. **`privacy_policy_version` is NOT
bumped** (stays 1.1 per §3.4's standing decision); privacy.md section 10 already
matches the shipped behavior, so no wording change was needed.

**Tests.**
[tests/backend/test_minor_gating.py](../tests/backend/test_minor_gating.py)
asserts the two `expose_*` flags are independent, that a living minor (node,
edges, media) is excluded when `expose_minors` is False and included when True,
that the Owner always sees minors, and that the upload gate returns 403 without
consent and clears with it; plus `individual_is_minor()` boundary unit tests
(exact-threshold, alive/dead, approx-only).

**Deferred (out of scope this pass).** `parental_consent` is NOT reset to NULL
when a person crosses the threshold (resetting would silently re-block uploads;
emailing once and recording it is lighter and reversible). The `re-crop`
endpoint is not gated (it replaces already-stored, already-consented content).
Approx-date individuals are not auto-detected as minors (see bullet 1).

### 3.9 TreeView selection-mode prefill for privacy requests (M-04 convenience)

Convenience-only enhancement of §2.2/§2.7 for the viewer requester
population. **Does not replace** the text-only privacy-request form —
population (b) in
[PRIVACY_ANALYSIS.md §1](PRIVACY_ANALYSIS.md#who-files-a-privacy-request--two-populations)
never reaches the UI. Scoped to `request_type='removal'` at first; can be
extended to access later if ever asked for.

- [x] TreeView selection mode: multi-check individuals on the tree. A "Select
      people" toggle in the tree chrome (both [TreePage.tsx](../frontend/src/pages/tree/TreePage.tsx)
      and [TreeOverviewPage.tsx](../frontend/src/pages/tree/TreeOverviewPage.tsx))
      flips clicks from re-center to check/uncheck; checked nodes get an emerald
      ring + badge. Selection state and the CTA href live in one shared hook,
      [useTreeSelection.ts](../frontend/src/hooks/useTreeSelection.ts), so the
      two pages do not duplicate it. Available to viewer and owner; hidden in the
      local app (no second party to address).
- [x] "Send privacy request for selected" CTA navigates to
      `/privacy/request` with `?owner=...&individual_ids=...&request_type=removal`.
      The href is built by `buildPrivacyRequestHref()` in
      [PrivacyLinks.tsx](../frontend/src/components/layout/PrivacyLinks.tsx)
      (next to the footer "Remove Me" link, so the param contract is defined
      once); `individual_ids` carries the selected nodes' GEDCOM ids.
- [x] PrivacyRequestPage prefills via the **message-pack** approach (no backend
      schema change): `parsePrefillParams()` in
      [PrivacyRequestPage.tsx](../frontend/src/pages/legal/PrivacyRequestPage.tsx)
      reads `individual_ids` + `request_type`, seeds the removal radio and a
      readable message ("Please remove my data ... for the following people: I1,
      I2."), and pre-fills the legacy single-id hint field with the first id.
      The owner-triage page already turns those I-ids in the message into
      "Open Individual" links, so no triage-UI change was needed. The shared
      param names live in
      [privacyRequestParams.ts](../frontend/src/constants/privacyRequestParams.ts)
      so producer and consumer cannot drift. Scope stays removal-only.

---

## 4. Tier 3 — Before enabling Mode B or Mode C

> **Everything in Tier 3 is conditional on completing §4.1 first.** Do not
> start any code in §4.2–§4.10 before the lawyer consultation. The whole point
> of §4.1 is to decide whether Mode B or Mode C is workable in your
> jurisdiction with acceptable obligations — if the answer is "no, not at this
> scale," all of the development effort below is wasted.

### What Mode B needs vs what Mode C needs

Tier 3 covers two destinations:

- **Mode B (contributors-only)** needs: §4.1 (lawyer), §4.5 (contributor ack),
  §4.6 (audit trail), §4.7 (hosting + DPA). It does NOT need §4.3 (owner
  self-unregister), §4.4 (owner ToS at signup), §4.8 (donate button),
  §4.9 (cross-Owner takedown admin), or §4.10 (PrivacySettings admin UI).
- **Mode C (public service, including gated/admin-approved owner signup)**
  needs all of §4.1–§4.10.

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
  | 3 | Privacy-request SLA exact days | |
  | 4 | Children's age threshold | |
  | 5 | DPO required at our scale? | |
  | 6 | International transfer mechanism | |
  | 7 | Cookie notice + button design acceptable to regulators? | |

- [ ] **Go / no-go decision recorded here:**
      ☐ GO Mode B (contributors-only) — proceed with §4.5, §4.6, §4.7.
      ☐ GO Mode C (public / gated owner signup) — proceed with §4.2–§4.10.
      ☐ NO-GO — keep NovoTree in Mode A indefinitely; close out Tier 3.
- [ ] After §4.2–§4.10 development is complete, schedule a short second
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
directory by hand. Reuses the privacy-request infrastructure from §2.2 +
§2.7 for the cascade machinery.

- [ ] New table `erasure_log` (timestamp, owner_id, scope = `owner` /
      `individual` / `media`, target_id, requester_kind = `owner` / `subject`,
      privacy_request_id nullable). Used by removal privacy requests and
      self-unregister.
- [ ] `DELETE /users/me` in [backend/api/users.py](../backend/api/users.py) —
      cascades: revoke all share tokens, delete contributors, drop owner's
      `data.sqlite` and media folder, write erasure_log row, clear cookies.
- [ ] Frontend "Delete my account and all my data" button on Settings →
      Profile, with type-the-word-DELETE confirmation.
- [ ] Admin equivalent endpoint for forced removal (used by §2.2 escalation).

### 4.4 Full Owner ToS at signup + cookie notice banner (Phase 1, M-01, M-12) — Mode C only

This section is also where the **ToS and Cookies markdown pages** are
deferred from Tier 1 §2.3. In Mode A and Mode B the operator does not
accept ToS from themselves and the cookie banner is unnecessary (only
strictly-necessary auth cookies are set; ePrivacy 5(3) exemption applies).
The pages and banner become meaningful only when a second Owner can sign
up — i.e. when this section is built.

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

### 4.8 Donate button (notes.txt L249)

Two distinct patterns with very different privacy postures. Read this section
before adding *any* donate UI in *any* mode.

**Pattern A — Link-out (mode-agnostic, no Tier 3 review needed).** A button
that opens GitHub Sponsors and/or Ko-fi in a new browser tab. NovoTree never
sees the transaction; the destination is the controller of all payment data;
no cookies are set on NovoTree's domain; no new sub-processor relationship is
created. The local desktop app already ships this pattern — see
[docs/features/LOCAL_APP.md §Donations](../features/LOCAL_APP.md#donations).

- Safe in Mode A, Mode B, Mode C, and the local app.
- Implementation: a `<DonateButton>` component that opens
  `https://github.com/sponsors/<handle>` and/or `https://ko-fi.com/<handle>`
  via `window.open(url, '_blank', 'noopener,noreferrer')`. Do NOT append donor
  email, name, or any identifier to the outbound URL — that would make
  NovoTree the originating controller of that PII transfer.
- One-line mention in the privacy policy under "Who we share with" is good
  hygiene but not legally required (no controller relationship to declare).
- Hint copy on the button ("opens github.com / ko-fi.com in a new tab") is
  defensive UX, not a legal requirement.

**Pattern B — Embedded payment integration (Mode C only).** A Stripe / PayPal
checkout rendered inside NovoTree, a donor wall that shows names, donor
receipts emailed by NovoTree, a thank-you page that reads order data, or any
flow where money or donor PII passes through NovoTree's server or DB.

- [ ] Pick provider (Stripe / PayPal). Payment provider becomes a sub-processor;
      list in privacy policy and sign their DPA.
- [ ] Update Mode C cookie banner: most embedded checkout scripts set
      non-essential cookies before user interaction. May force banner from
      notice-only to real Accept/Reject.
- [ ] Schedule a short follow-up lawyer session covering: donor-data
      retention, receipt/invoice obligations, charity-vs-gift framing in your
      jurisdiction.

### 4.9 Admin privacy-request triage endpoint and UI (M-04 extension) — Mode C only

In Mode A and Mode B the operator is the only Owner, and an admin endpoint
for privacy requests duplicates the Owner's own access (you can already see
your own requests by reading the notification email, and you triage by
editing your own data). Once multiple Owners exist on the server, the
operator needs a way to act over the head of a non-responsive Owner —
that is what this endpoint is for.

- [ ] `GET /admin/privacy-requests?status=open` to list rows across all Owners.
- [ ] `PATCH /admin/privacy-requests/{id}` accepting
      `{status: "acknowledged"|"resolved"|"escalated"}`, stamping
      `resolved_at` for terminal transitions.
- [ ] Auth gate: a real admin role (not "owner whose email matches
      `privacy_settings.privacy_contact_email`") — Mode C will need this
      distinction anyway.
- [ ] Admin UI page (minimum: list + status-change buttons). The Tier-2
      §3.5 admin CLI ships first; this is the web-UI version.

> The Tier-2 §3.5 admin CLI handles the Mode-A operator's needs (list,
> resolve, force-delete). It is sufficient until Mode C requires the
> in-app endpoint above.

### 4.10 Admin UI for `PrivacySettings` — Mode C only

Today the `PrivacySettings` dataclass in
[backend/config.py](../backend/config.py) is loaded from `/etc/novotree.env`
at startup and is read-only at runtime. Changes require editing the env file
and `systemctl restart novotree`. That is fine in Mode A — the operator owns
the shell, the restart drops only their own session, and the env file is
already the single source of truth.

It does not scale to Mode C. The operator will want to flip
`allow_owner_signup` to False the moment abuse spikes without dropping
in-flight sessions, rotate `privacy_contact_email` when staff changes, and
update `controller_name` / `dpo_email` without a deploy window. That is the
job of this admin UI.

**Design questions to resolve before building:**

- **Persistence model.** Env-only (today), DB-only, or env-default + DB-override?
  The last is most flexible but creates two sources of truth. Recommend
  DB-override with env as boot-time default.
- **Live reload.** Re-read settings on every request, or signal workers to
  reload on change? Either way: `PrivacySettings` stops being frozen.
- **Auto-version-bumping.** Changing legally-relevant fields
  (`privacy_request_sla_days`, `controller_name`, `child_age_threshold_years`)
  must auto-bump the matching `*_version` string and re-prompt users for
  acceptance. Today the versions are operator-edited; making them auto-bump
  on UI change means encoding the legal-relevance map somewhere.
- **Audit log.** Who changed what when. Regulators ask this question.
- **Field allow-list.** Not every field is safe to edit from the UI
  (`*_version` are protocol-level; `hosting_region` affects compliance
  posture — flipping it from "EEA" to anything else triggers new SCC / DPF
  obligations that can't be back-dated). Explicit allow-list in code, NOT
  "edit anything in the dataclass."

**Action items (sequential):**

- [ ] Pick persistence model and live-reload strategy (design doc).
- [ ] Add `settings_overrides` table to `database/system_models.py`
      (key/value/changed_by/changed_at).
- [ ] Replace `privacy_settings = load_privacy_settings()` module-level
      singleton with a function/dependency that merges env-defaults with
      DB-overrides on read.
- [ ] `GET /admin/settings` returning the merged view + per-field
      "source" (env or DB-override).
- [ ] `PATCH /admin/settings` with the field allow-list and auto-version-
      bumping for legally-relevant fields.
- [ ] Admin UI page under the same `/admin` route as §4.9.
- [ ] Audit log: every PATCH writes to `settings_audit_log`.
- [ ] Reuses the §4.9 admin-role gate — same operator audience, same auth.

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

    # SLA in days for a public privacy request (removal, access, or
    # correction) from a data subject. After this many days, admin
    # auto-escalates and (for removal) hides records on the Owner's behalf.
    # GDPR Art. 12(3) says "without undue delay, and in any event within
    # one month" — 30 days is the safe default.
    privacy_request_sla_days: int = 30

    # Age below which an Individual is treated as a minor and gets extra
    # protection (parental-consent gate on photo upload and share-link
    # exposure). GDPR Art. 8 lets each EU member state pick a threshold
    # between 13 and 16; we pick 16 so we are compliant everywhere.
    child_age_threshold_years: int = 16

    # --- retention windows ---

    # How long backups of owner data.sqlite files are kept before deletion.
    # Bounds the window in which a deleted record can resurface from backup.
    # Must be >= privacy_request_sla_days so erasure can propagate.
    backup_retention_days: int = 30

    # Web-server access logs (URL, status, IP). Short window — debugging and
    # abuse detection only.
    access_log_retention_days: int = 14

    # Application error logs and stack traces — kept longer because some
    # bugs only show up after a user reports them.
    error_log_retention_days: int = 30

    # How long we keep a privacy-request ticket (name + email + message text)
    # after it has been resolved. Long enough to prove we responded if a
    # regulator asks; short enough that we are not hoarding PII.
    privacy_request_retention_months: int = 12

    # --- legal-document versioning ---
    # When any of these strings change, users are re-prompted to accept on
    # next login. We do not silently update legal documents.
    tos_version: str = "1.0"            # ToS = Terms of Service
    privacy_policy_version: str = "1.0"
    cookie_notice_version: str = "1.0"

    # --- controller identity (privacy policy §1, §7) ---

    # "Data controller" is the GDPR Art. 4(7) term for the legal entity
    # responsible for deciding why and how personal data is processed. This
    # name appears in the privacy policy and in privacy-request responses.
    # Do not confuse with the internal "admin" role.
    controller_name: str = "NovoTree (operator: Igor Novoseltsev)"

    # Where data subjects email privacy questions and privacy-request
    # follow-ups. Must be a monitored mailbox.
    privacy_contact_email: str = "novospace.tree@gmail.com"

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
| `backend/api/privacy_requests.py` (Tier 1 §2.2 + §2.7) | Privacy-request SLA timer, retention windows |
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
| §4.8 Donate button — link-out (GitHub Sponsors / Ko-fi) | Allowed (mode-agnostic; same as Mode A and the local app) | Allowed |
| §4.8 Donate button — embedded payment (Stripe / PayPal) | Not allowed | Optional (adds sub-processor + may force consent-style cookie banner) |
| §4.9 Admin privacy-request triage endpoint + UI | Not required (operator IS the admin) | Required (multiple Owners; operator must act over Owner's head) |
| §4.10 Admin UI for `PrivacySettings` | Not required (env file + `systemctl restart` is fine) | Required (live toggle of signup flags / contact emails without restart) |
| `allow_owner_signup` flag | `False` | `True` |
| `owner_signup_requires_approval` flag | (n/a) | `True` (gated) or `False` (open) |
| `allow_contributor_signup` flag | `True` | `True` |

### Recommendation for "friends and family only"

If relatives only need to **add and edit information in your tree**, Mode B is
the cheapest path out of Mode A — skip §4.3, §4.4, and §4.8 Pattern B
(embedded payments), but still pay for §4.1 (lawyer) and build §4.5, §4.6,
§4.7. §4.8 Pattern A (link-out donate button) is allowed in any mode and
needs no Tier 3 work.

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
| 3 | Privacy-request SLA exact days | `privacy_request_sla_days = 30` | Config |
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
