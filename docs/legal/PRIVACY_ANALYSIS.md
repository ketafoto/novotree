# Privacy Analysis — Concerns, Mitigations, and Legal Text

> **Companion to [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md).**
> This document is the *what and why* — concerns inventory (C-NN),
> mitigation catalogue (M-NN), per-mode posture, and draft legal texts.
> [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) is the *when and how* — the
> tiered implementation checklist that tracks coding progress and
> references the M-NN items defined here.
>
> If you are picking work up from scratch: read this file first to
> understand the problem space, then [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md)
> to see what is built, in progress, or queued.

> **Disclaimer.** This document is engineering and product guidance, not legal advice.
> Before promoting NovoTree publicly to non-friends, the author should obtain a paid
> consultation with a lawyer in the operating jurisdiction (EU/UK in particular, since
> GDPR applies to any EU/UK data subject regardless of where the service is hosted).

---

## 1. TL;DR

NovoTree stores **personal data about identifiable people** — names, dates,
relationships, photos, life events, sometimes religion or cause of death. Many of
those people did **not** sign up for the service; their data is uploaded by an
Owner or a Contributor. This is the central legal exposure.

We address it with a layered model:

1. **Owner-as-controller** ToS — the Owner takes responsibility for the lawfulness
   of what they upload. NovoTree is the processor.
2. **Tiered visibility** — private by default; widening the audience requires an
   explicit acknowledgement each time.
3. **Subject-initiated privacy requests** — anyone who appears in any tree can
   request removal, access, or correction of their data via a public,
   low-friction flow.
4. **Local-first / private mode** — for users who want full control, the database
   stays on their machine and never reaches our server. This sidesteps controller
   liability for that mode entirely.
5. **Necessary-only cookies** — we use only authentication cookies. Notice required;
   opt-in consent banner is **not** required.

### Who files a privacy request — two populations

The privacy-request flow (M-04, §2.2 + §2.7 in
[PRIVACY_DESIGN.md](PRIVACY_DESIGN.md)) must serve two distinct requester
populations:

- **(a) Viewer-as-requester.** A relative or acquaintance who opened a share
  link, recognized themselves on the tree, and wants to be removed (or to
  ask what is held about them, or to correct an error). They have seen
  NovoTree's UI; in principle they could navigate it.
- **(b) Off-platform requester.** Someone who has never visited NovoTree but
  heard about the tree via word-of-mouth, a forwarded screenshot, a search
  engine snippet, or a printed PDF a relative gave them. They may not even
  know what NovoTree looks like.

Both populations are equally entitled to file under GDPR Art. 15–17. The
implication for design: the privacy-request form must be **text-only and
reachable from a single URL**. UI-driven identification (e.g. selecting
individuals inside the TreeView) cannot be the primary path, because
population (b) will never reach the UI. UI-assisted prefill for population
(a) is a convenience feature, not a substitute. See M-04 for the resulting
constraints on the form.

---

## 2. Glossary

| Term | Meaning |
|------|---------|
| **Data subject** | A living person whose data appears in a tree (Owner, Contributor, or anyone they describe). |
| **Controller** | The entity deciding *why* and *how* data is processed. Has the heaviest legal duties. |
| **Processor** | The entity processing data on behalf of a controller. Lighter duties, but a written DPA-equivalent is required. |
| **Household exemption** | GDPR Art. 2(2)(c): purely personal/household activity is outside GDPR. Lost the moment data is published or shared widely (CJEU *Lindqvist*, C-101/01). |
| **Special category data** | GDPR Art. 9: religion, ethnicity, health, sex life, biometrics, etc. Needs explicit consent or a narrow legal basis. |
| **Owner / Contributor / Viewer (OCV)** | NovoTree's three roles. See [AUTH_SCHEMA_PROPOSAL.md](../design/AUTH_SCHEMA_PROPOSAL.md). |

---

## 3. Concerns Inventory

Each concern has an ID (`C-NN`), a severity, the deployment modes it applies to,
and a short description.

### C-01 — Personal data of non-consenting living persons (HIGH; all modes)

An Owner or Contributor adds a *living* relative — name, birth date, photo,
events — without that person's knowledge or consent. Under GDPR this is processing
of personal data with no clear lawful basis once the household exemption no longer
applies (i.e. as soon as the tree is shared beyond the household).

### C-02 — Special-category data (HIGH; all modes)

Notes fields, baptism/burial events, cause of death, ethnicity, adoption status —
all qualify as Art. 9 special-category data. Stricter rules apply.

### C-03 — Children's data (HIGH; public mode especially)

Adding minors (their own children, nieces/nephews, friends' children) — GDPR Art. 8
sets parental consent thresholds (13–16 by member state). COPPA in the US for
under-13s. Risk of Owner uploading photos of *other people's* children.

### C-04 — Photo copyright (MEDIUM; all modes)

Copyright on a photo belongs to the photographer, not the subject. Old family
photos: copyright passed by inheritance, often unclear. Risk is mostly theoretical
for private trees but real for publicly-shared ones.

### C-05 — Image rights / right of publicity (MEDIUM; shared and public modes)

Distinct from GDPR. Germany (KunstUrhG §22), France (droit à l'image), some US
states grant subjects an independent right to control commercial use of their image.

### C-06 — Defamation / false light (LOW–MEDIUM; shared and public modes)

A Contributor adds a wrong or hostile claim about a living person ("X had an affair
in 1992"). Owner is not vetting every change.

### C-07 — Deceased persons (LOW; all modes — but jurisdiction-dependent)

GDPR generally does not cover the dead (Recital 27), but France, Italy, Denmark,
Spain extend protection. Image rights often survive death (varies).

### C-08 — Right of erasure / access (HIGH; shared and public modes)

A data subject (not necessarily a NovoTree user) demands their data be deleted or
shown to them. We currently have no mechanism for a non-user to make this request.

### C-09 — Subject discovery (MEDIUM; public mode)

A subject googles their name and finds themselves on a public tree they never
agreed to be on. This is the most likely complaint vector.

### C-10 — International data transfers (MEDIUM; public mode)

If the VM hosting `datasets/` is outside the EEA and EU subjects' data flows there,
GDPR Chapter V rules apply (SCCs, adequacy decisions, etc.).

### C-11 — Backup and retention (MEDIUM; all modes)

Backups created by `vm-backup.py` may persist deleted data indefinitely. The right
to erasure must propagate to backups within a reasonable window.

### C-12 — Cookies and client-side storage (LOW; all modes)

We set authentication cookies and use `sessionStorage` for the viewer share token.
ePrivacy Directive (the "Cookie Law") requires either consent or a notice depending
on cookie purpose. See section 7.

### C-13 — Contributor uploads on behalf of Owner (MEDIUM; shared and public modes)

The Contributor is editing data inside someone else's tree. Legally the Owner remains
the controller; the Contributor acts under the Owner's authority. This needs to be
explicit so a Contributor cannot later claim "I didn't know what I was uploading
into."

### C-14 — Lack of audit trail (MEDIUM; all modes)

Without a per-record `created_by` / `updated_by` log, neither Owner nor we can
respond to "who added this about me?" requests. Project already records `created_by`
and `created_at` on most tables (see [database/models.py](../../database/models.py)).
`updated_by` is not tracked.

### C-15 — Email-based identifiers leak (LOW; all modes)

Email addresses entered for invites/contacts qualify as personal data. They appear
in the auth DB and possibly in logs.

### C-16 — Logs and observability (LOW; all modes)

Server logs may capture personal data via request payloads, error messages, or
stack traces. Retention and access need a policy.

---

## 4. Mitigation Measures

Each measure has an ID (`M-NN`) and lists the concerns it covers.

### M-01 — Owner-as-controller ToS (covers C-01, C-02, C-04, C-05, C-06, C-13)

Owner accepts at signup that they are the controller for the tree's contents and
warrant they have the right to upload what they upload. NovoTree is the processor.
Standard SaaS posture (Dropbox, Google Drive). Combined with M-04, this is the
single most important measure.

### M-02 — Default-private trees (covers C-01, C-05, C-08, C-09)

A new tree is created with no share tokens. Visibility cannot be widened without
an explicit re-acknowledgement (M-03).

### M-03 — Per-share consent prompt (covers C-01, C-05, C-06, C-09)

Each time the Owner toggles visibility outward (creates a share token, increases
its scope, or extends expiry), show a modal:

> "I confirm I have permission from the living people shown in this tree, or they
> are deceased. I take responsibility for the contents I share."

Log the click with timestamp + IP into the auth DB.

### M-04 — Public privacy-request flow (covers C-01, C-05, C-08, C-09)

Every shared view exposes a small, persistent "Remove Me" link. It opens a
public form (renamed from "takedown" to "privacy request" in §2.7) with
three options: **removal**, **access** (send me a copy), or **correction**.
The form captures name, email, optional phone, request kind, and a
free-text description. Backend creates a privacy-request ticket, emails the
Owner with a 30-day SLA, and copies the admin (you). If the Owner does not
respond, admin can act on their behalf — for removal, this means hiding
the records.

This single flow addresses three of the highest-risk concerns at once and is the
strongest piece of evidence of "good faith effort" if a complaint reaches a
regulator.

**Form must be text-only and reachable from a single public URL.** §1 above
identifies two requester populations: (a) viewers who saw the tree, and (b)
off-platform people who never did. Because population (b) cannot use any
UI-driven identification flow (they have not opened the share link, may not
even have one), the privacy-request form must work entirely from typed
input. A TreeView selection mode that prefills the form is a fine
convenience for population (a) but is **never** the only path. The form is
the source of truth.

**Verification is not the form's job.** Per GDPR Art. 12(6), the controller
(Owner) may request additional information to confirm the requester's
identity when there are reasonable doubts. The form captures enough for the
Owner to attempt contact; the Owner exercises judgement during triage. Junk
name/email submissions are not the form's problem to reject — they are the
Owner's to verify before acting. The notification email to the Owner
instructs them accordingly.

**No auto-cascade.** The form takes at most a single `individual_id` hint;
removal of related individuals (children, partners, ancestors) is **not**
implied. Each data subject must file their own request. A parent asserting
parental authority over a minor child's record is a case the Owner
resolves manually during triage.

### M-05 — Special-category data gating (covers C-02)

Fields known to be Art. 9 (cause of death, religion, ethnicity, health-related
event types) are:
- Hidden by default in the UI behind a "show sensitive fields" toggle.
- Excluded from the publicly-shared view unless the Owner explicitly enables them
  per share token.

### M-06 — Children data handling (covers C-03)

When adding an Individual whose `birth_date` < 16 years ago AND `death_date` is
null:
- Photo upload disabled by default; Owner must check "I have parental consent."
- No data exposed in viewer mode unless Owner explicitly enables.
- Auto-revisit: when the child turns 16, send the Owner a reminder to re-confirm.

### M-07 — Subject email notification (covers C-01, C-08, C-09)

When an Owner adds a living individual and provides an email for them, offer a
one-click "let them know they were added" — sends a polite email with a link to
view their entry and a one-click "Remove Me" button.

Optional, not mandatory at create time (would discourage tree-building); but
**mandatory** before that individual's entry can be exposed to a public share token.

### M-08 — Local-first / private mode (covers C-01, C-08, C-09, C-10, C-11)

Already on the roadmap (notes.txt line 248). Genuine privacy posture: data stays
in the user's `data.sqlite` on their machine and never touches our server. The
household exemption applies cleanly. We become a software vendor, not a controller.

Implementation route: ship the desktop installer that runs the server locally on
`127.0.0.1`, with explicit "import from server / export to server" actions.

### M-09 — Right-of-access export (covers C-08)

Owner has a "download all data about person X" button on each Individual page,
producing a JSON or PDF. Used to fulfil access requests forwarded by Owner.

### M-10 — Backup retention policy + erasure propagation (covers C-11)

- Backups rotate every 30 days by default; older backups deleted.
- Erasure requests delete from live DB immediately and are tracked in an
  `erasure_log` table; backups are not edited (technically infeasible for SQLite
  archives), but they expire within 30 days.
- Document this clearly in the privacy policy.

### M-11 — Audit trail completeness (covers C-13, C-14)

Add `updated_by` and `updated_at` to mutable tables (Individuals, Names,
Families, Events, Media). Already partly there — just complete it. See section 8.

### M-12 — Strictly-necessary-cookie notice (covers C-12)

A persistent, dismissible banner on first visit:

> "NovoTree uses cookies that are strictly necessary to keep you logged in. We do
> not use analytics, advertising, or tracking cookies. [Learn more]."

No "Accept / Reject" buttons because there is nothing optional to consent to.
Under EU ePrivacy (Art. 5(3)) strictly-necessary cookies are exempt from the
consent requirement; only transparency is required.

If we ever add analytics, the banner becomes a real consent dialog.

### M-13 — EEA hosting + DPA with VM provider (covers C-10)

Host `datasets/` on an EEA region of the VM provider. Sign their DPA. Document
the choice in the privacy policy.

### M-14 — Log scrubbing + retention (covers C-15, C-16)

- Disable request body logging by default in production.
- Retain access logs 14 days; error logs 30 days.
- Email addresses appear in auth DB only; never in URL paths or query strings.

### M-15 — Contributor explicit acknowledgement (covers C-13)

Before the Contributor's first edit, show a one-time modal:

> "You are editing data in someone else's tree. Only add information you have the
> right to share. The Tree Owner is responsible for the tree's contents and may
> remove your contributions."

Accepted timestamp logged.

### M-16 — Viewer notice on first share-link load (covers C-09, C-12)

First load of a `?share=…` URL shows a small notice:

> "You are viewing a private family tree shared with you. Please do not
> redistribute or scrape it. If you appear here and want to be removed, click
> 'Privacy / remove me'."

Dismissed once per share token (persisted in `sessionStorage`).

---

## 5. Concern → Mitigation Matrix

| Concern | Mitigations |
|---------|-------------|
| C-01 Non-consenting living persons | M-01, M-02, M-03, M-04, M-07, M-08 |
| C-02 Special-category data | M-01, M-05 |
| C-03 Children's data | M-01, M-06 |
| C-04 Photo copyright | M-01 |
| C-05 Image rights | M-01, M-02, M-03, M-04 |
| C-06 Defamation | M-01, M-03, M-15 |
| C-07 Deceased persons | M-01 |
| C-08 Right of erasure / access | M-04, M-08, M-09, M-10 |
| C-09 Subject discovery | M-02, M-03, M-04, M-07, M-16 |
| C-10 International transfers | M-08, M-13 |
| C-11 Backup & retention | M-08, M-10 |
| C-12 Cookies | M-12, M-16 |
| C-13 Contributor uploads | M-01, M-11, M-15 |
| C-14 Audit trail | M-11 |
| C-15 Email leakage | M-14 |
| C-16 Logs | M-14 |

---

## 6. Per-Deployment-Mode Posture

NovoTree has three on-server deployment modes (Mode A / B / C) plus the
local-first desktop variant. See
[PRIVACY_DESIGN.md §1 "Key product framing"](PRIVACY_DESIGN.md#key-product-framing--three-deployment-modes)
and [§6.5](PRIVACY_DESIGN.md#65-mode-b-contributors-only-vs-mode-c-gated-or-open-owner-signup)
for the full taxonomy and the obligation-comparison table between Mode B and
Mode C (including why admin-approved gated owner signup is still Mode C).

| Mode | What it is | Household exemption applies? | NovoTree role | Required mitigations |
|------|-----------|------------------------------|---------------|----------------------|
| **Mode A — Private / single Owner** | Single Owner (the operator). No signups. Share links to relatives still work. | Yes for the Owner, but lost the moment a share link is created (CJEU *Lindqvist*) | Processor (low duty) | M-01, M-02, M-03, M-04, M-12, M-14, M-16 (Tier 1 + Tier 2 of PRIVACY_DESIGN.md) |
| **Mode B — Contributors-only** | Single Owner (the operator). Contributor signup enabled so relatives can edit the operator's tree. Owner signup disabled. | No (multiple editors, shared tree) | Processor | All of Mode A plus M-11, M-15 |
| **Mode C — Public / gated owner signup** | Owner signup enabled (open OR admin-gated). Each new Owner is a separate data controller hosted on your VM. | No | Joint controller / Processor depending on data | All of M-01 → M-16 |
| **Local-first / desktop install** | Backend runs on `127.0.0.1` on the user's machine; data never reaches the server. | Yes | Software vendor only | M-01 (in EULA), M-12 |

---

## 7. Cookies and Client-Side Storage

### What we set today

| Item | Type | Purpose | Strictly necessary? | Consent required? |
|------|------|---------|---------------------|-------------------|
| `access_token` | HttpOnly cookie, 15 min, `Secure`, `SameSite=Strict` | Carries JWT for the logged-in Owner / Contributor | Yes (auth) | No — notice only |
| `refresh_token` | HttpOnly cookie, 30 days, `Secure`, `SameSite=Strict` | Silent refresh of the access token | Yes (auth) | No — notice only |
| `share_token` in `sessionStorage` | Browser storage (per-tab) | Persists Viewer's share token after the share URL is opened | Yes (auth for Viewers) | No — notice only |

**No analytics, no advertising, no third-party cookies.** This is the case
today and should remain a product decision; introducing analytics changes the
legal posture and requires a real consent dialog.

### What we tell users

- A short paragraph in the Privacy Policy.
- A small dismissible banner on first visit (text in section 9.6).
- The same banner appears on the first viewer load of a share link (covers M-16).

### What we do NOT need

- A "Reject all" button.
- An IAB-style consent management platform.
- Per-cookie checkboxes.

(All of these become required if we add analytics or marketing pixels.)

---

## 8. Development Plan

Phased so each phase is independently shippable. Each task names the file(s)
likely to change so it can be picked up and coded directly.

### Phase 0 — Make the legals visible (no-code-mostly, blocking for "Go private")

| # | Task | Files |
|---|------|-------|
| 0.1 | Land this document. | [docs/PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) |
| 0.2 | Draft Privacy Policy + Terms of Service pages (text in section 9). | [frontend/src/pages/legal/](../../frontend/src/pages/legal/) (new), `backend/api/legal.py` (new, serves markdown) |
| 0.3 | Add ToS / privacy links to the footer of every page. | [frontend/src/components/layout/Layout.tsx](../../frontend/src/components/layout/Layout.tsx) |
| 0.4 | Cookie notice banner (dismissible, persisted in `localStorage`). | `frontend/src/components/CookieNotice.tsx` (new) |

### Phase 1 — Owner-as-controller ToS at signup (M-01)

| # | Task | Files |
|---|------|-------|
| 1.1 | Add `tos_accepted_at`, `tos_version` columns to `auth_editors`. | [database/system_models.py](../../database/system_models.py) |
| 1.2 | Signup form: required checkbox "I accept the Terms of Service and Privacy Policy" with link. | [frontend/src/pages/auth/SignupPage.tsx](../../frontend/src/pages/auth/SignupPage.tsx) |
| 1.3 | Backend rejects signup if not accepted; stores timestamp + ToS version. | [backend/api/auth.py](../../backend/api/auth.py) |
| 1.4 | Re-acceptance prompt on login if `tos_version` increased. | [backend/api/auth.py](../../backend/api/auth.py), [frontend/src/contexts/AuthContext.tsx](../../frontend/src/contexts/AuthContext.tsx) |

### Phase 2 — Audit trail completeness (M-11)

| # | Task | Files |
|---|------|-------|
| 2.1 | Add `updated_by`, `updated_at` to mutable tables. | [database/models.py](../../database/models.py), [database/schema.sql](../../database/schema.sql) |
| 2.2 | Migration to add columns to existing owner DBs (lazy on engine init). | [database/db.py](../../database/db.py) |
| 2.3 | Populate them in every UPDATE path. | [backend/api/individuals.py](../../backend/api/individuals.py), [backend/api/families.py](../../backend/api/families.py), [backend/api/events.py](../../backend/api/events.py), [backend/api/media.py](../../backend/api/media.py) |
| 2.4 | "History" tab on Individual page showing creator + last editor. | [frontend/src/pages/individuals/](../../frontend/src/pages/individuals/) |

### Phase 3 — Default-private + per-share acknowledgement (M-02, M-03)

| # | Task | Files |
|---|------|-------|
| 3.1 | New trees ship with zero share tokens (verify; should already be true). | [backend/api/auth.py](../../backend/api/auth.py) |
| 3.2 | "Create share link" button shows acknowledgement modal with text from §9.4. Click logged with timestamp + IP. | [frontend/src/pages/settings/](../../frontend/src/pages/settings/), [backend/api/auth.py](../../backend/api/auth.py) |
| 3.3 | New table `auth_share_consents` (`editor_id`, `tree_id`, `share_token_id`, `accepted_at`, `accepted_ip`, `tos_version`). | [database/system_models.py](../../database/system_models.py) |

### Phase 4 — Public privacy-request flow (M-04, §2.7)

| # | Task | Files |
|---|------|-------|
| 4.1 | Table `privacy_requests` (id, tree_owner_id, individual_id?, request_type, name, email, message, status, created_at, resolved_at). | [database/system_models.py](../../database/system_models.py) |
| 4.2 | Public endpoint `POST /privacy/request` (rate-limited, no auth). | [backend/api/privacy_requests.py](../../backend/api/privacy_requests.py) |
| 4.3 | Owner triage endpoints `GET/PATCH/DELETE /privacy/requests/*`. | [backend/api/privacy_requests.py](../../backend/api/privacy_requests.py) |
| 4.4 | Email Owner on new request; reminder at day 14; admin escalation at day 30. | [backend/api/_privacy_request_sweep.py](../../backend/api/_privacy_request_sweep.py) + [backend/api/_email.py](../../backend/api/_email.py) |
| 4.5 | "Remove Me / Our Privacy" link in viewer footer. | [frontend/src/components/layout/PrivacyLinks.tsx](../../frontend/src/components/layout/PrivacyLinks.tsx) |
| 4.6 | Public privacy-request form page (three options: removal / access / correction). | [frontend/src/pages/legal/PrivacyRequestPage.tsx](../../frontend/src/pages/legal/PrivacyRequestPage.tsx) |

### Phase 5 — Contributor & viewer acknowledgements (M-15, M-16)

| # | Task | Files |
|---|------|-------|
| 5.1 | First-edit modal for Contributors with text from §9.2. Persisted per (editor_id, tree_id). | `frontend/src/components/ContributorAck.tsx` (new), [backend/api/auth.py](../../backend/api/auth.py) |
| 5.2 | First-load notice for Viewers, dismissed once per share token. | [frontend/src/contexts/AuthContext.tsx](../../frontend/src/contexts/AuthContext.tsx), [frontend/src/components/ViewerNotice.tsx](../../frontend/src/components/ViewerNotice.tsx) (new) |

### Phase 6 — Special-category + children handling (M-05, M-06)

| # | Task | Files |
|---|------|-------|
| 6.1 | Mark sensitive fields (cause of death, religion, ethnicity, certain event types). Hide behind "show sensitive" toggle. | [frontend/src/pages/individuals/](../../frontend/src/pages/individuals/), [backend/api/events.py](../../backend/api/events.py) |
| 6.2 | Per-share-token flag `expose_sensitive` (default off). | [database/system_models.py](../../database/system_models.py) |
| 6.3 | Detect "minor + alive" individuals; require parental-consent checkbox to upload photo or expose to share. | [frontend/src/pages/individuals/](../../frontend/src/pages/individuals/), [backend/api/individuals.py](../../backend/api/individuals.py) |

### Phase 7 — Right-of-access export (M-09)

| # | Task | Files |
|---|------|-------|
| 7.1 | Endpoint `GET /individuals/{id}/data-export` returning JSON of every field, event, media link, contributor attribution. | [backend/api/export.py](../../backend/api/export.py) |
| 7.2 | "Export this person's data" button on Individual page. | [frontend/src/pages/individuals/](../../frontend/src/pages/individuals/) |

### Phase 8 — Backup retention + erasure log (M-10)

| # | Task | Files |
|---|------|-------|
| 8.1 | `vm-backup.py` rotates: keep 30 daily; delete older. | external `vm-backup.py` (in [novospace.git/scripts/deployment/](../../../novospace.git/scripts/deployment/)) |
| 8.2 | New `erasure_log` table. Every delete in response to a removal privacy request writes a row. | [database/models.py](../../database/models.py) |
| 8.3 | Document the 30-day backup window in the privacy policy. | [docs/PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md), the rendered policy |

### Phase 9 — Local-first / desktop mode (M-08; large; corresponds to notes.txt line 248)

Out of scope for this document beyond noting that it is the strongest privacy
posture and should be prioritised before promoting the SaaS publicly. Tracked
separately.

### Phase 10 — Logs and ops hygiene (M-14)

| # | Task | Files |
|---|------|-------|
| 10.1 | Disable request-body logging in production config. | [backend/main.py](../../backend/main.py), [backend/config.py](../../backend/config.py) |
| 10.2 | Document log retention (14 / 30 days) in privacy policy and in deployment notes. | [docs/DEPLOYMENT.md](../ops/DEPLOYMENT.md), the rendered policy |

---

## 9. Legal Text — Drafts for User Acceptance

These are **drafts**. A lawyer should review them before public launch.
Plain-language form is intentional — easier to read and harder to dispute.

### 9.1 Owner ToS (accepted at signup)

> **NovoTree Terms of Service**
>
> 1. **Your tree, your data.** When you create a tree, you decide what goes into
>    it. You are the *data controller* for the contents of your tree. NovoTree
>    only stores and serves what you put in.
>
> 2. **What you promise.** By using NovoTree, you confirm that:
>    - You will only add information about people who have agreed to be there,
>      or who are deceased.
>    - You have the right to upload any photo you upload.
>    - You will not add false, hostile, or defamatory information about anyone.
>    - You will not add data about other people's children without parental
>      consent.
>
> 3. **Sharing.** Your tree is private by default. If you create a share link,
>    you are responsible for who you give it to and what they do with it.
>
> 4. **Sensitive information.** Religion, ethnicity, health, cause of death,
>    and similar fields are treated as sensitive. They are hidden from share
>    links unless you explicitly enable them.
>
> 5. **Removal requests.** If a person who appears in your tree asks to be
>    removed, you have 30 days to comply. After that, NovoTree may hide their
>    records on your behalf.
>
> 6. **Account deletion.** You can delete your account and all your data at any
>    time. Backups are deleted within 30 days.
>
> 7. **What we do.** We store your data on our server, send authentication
>    cookies to your browser, and send you operational emails. We do not sell
>    your data, do not show advertising, and do not use analytics or tracking.
>
> 8. **No warranty.** NovoTree is provided as-is, without warranty. We are not
>    liable for indirect or consequential damages.
>
> 9. **Changes.** If we change these terms, we will ask you to accept them again.
>
> By creating an account I confirm I have read and accept these Terms of Service
> and the Privacy Policy.

### 9.2 Contributor Acknowledgement (shown before first edit)

> **You are editing someone else's tree.**
>
> The Tree Owner is responsible for the tree. You may add information about
> yourself and about people you have the right to write about. Please:
>
> - Do not add information about people who have not agreed to be there.
> - Do not upload photos you do not own.
> - Do not add false or hostile information about anyone.
>
> The Owner can edit, hide, or remove your contributions at any time. NovoTree
> may remove contributions in response to a privacy complaint.
>
> [I understand]

### 9.3 Viewer Notice (shown on first share-link load)

> **You are viewing a private family tree shared with you.**
>
> Please do not redistribute, copy, or scrape its contents. The information
> here belongs to the families it describes.
>
> If you appear in this tree and want to be removed, use the **Remove Me**
> link.
>
> [Got it]

### 9.4 Per-share Acknowledgement (shown when creating or extending a share link)

> **Sharing this tree.**
>
> By creating this share link, I confirm that:
>
> - I have permission from the living people in this tree, or they are deceased.
> - I take responsibility for what I share and who I share it with.
> - I will respond within 30 days to any removal request from a person who
>   appears here.
>
> [Cancel]   [Create share link]

### 9.5 Public Privacy-Request Form (no auth required)

This is the canonical copy for the three-option intake form introduced in
[PRIVACY_DESIGN.md §2.7](PRIVACY_DESIGN.md). The frontend
([PrivacyRequestPage.tsx](../../frontend/src/pages/legal/PrivacyRequestPage.tsx))
sources its strings from this section — keep them in sync.

> **Privacy request — remove, access, or correct your data**
>
> Use this form to ask the owner of this family tree to remove, send you a
> copy of, or correct information they hold about you. Pick one and describe
> your request below. We will email the owner; you should hear back within
> 30 days.
>
> **What would you like the tree owner to do?** *(required — pick one; no default)*
>
> - ○ Remove my data from this family tree. *(GDPR Art. 17)*
> - ○ Send me a copy of the data this tree holds about me. *(GDPR Art. 15)*
> - ○ Correct something this tree gets wrong about me. *(GDPR Art. 16)*
>
> - Tree owner (username) or tree URL: _______________________________________
> - Your name (as it appears on the tree, if you know): _______________________
> - Your email (so we can confirm receipt): __________________________________
> - Your phone (optional): ___________________________________________________
> - Individual ID (optional, if you know it): ________________________________
> - Describe your request: ___________________________________________________
>
> [Submit]
>
> *We will store this request only as long as needed to act on it (max 12 months).*

**Notes on copy.**

- GDPR article references are parenthetical, not in the lead — plain language
  first, legal citation second. The legal text lives in
  [privacy.md](privacy.md) §9 "Your rights".
- No pre-selected radio. The form rejects submission until one option is
  picked; this matches the backend Pydantic schema, which requires
  `request_type` with no default.
- Page title and intro paragraph stay identical to the JSX. Changing either
  side without updating the other will produce a confusing mismatch.

### 9.6 Cookie Notice Banner (first visit)

> **NovoTree uses cookies that are strictly necessary to keep you logged in.**
>
> We do not use analytics, advertising, or tracking cookies. We do not share
> data with third parties.
>
> [Got it]   [Learn more]

### 9.7 Privacy Policy — Outline (full text drafted in Phase 0.2)

The privacy policy lives at `/legal/privacy` and covers:

1. **Who we are** — NovoTree operator, contact email.
2. **What data we hold** — account data (email, password hash); tree data (as
   uploaded by Owners and Contributors).
3. **Why we hold it** — to provide the service.
4. **Lawful basis** — Art. 6(1)(b) contract for account data; Art. 6(1)(f)
   legitimate interest as processor for tree data on behalf of Owners.
5. **Cookies** — only strictly necessary; section 7 of this document is the
   source.
6. **Where the data lives** — VM region; backup region.
7. **Who we share with** — VM provider (DPA in place), email provider; nobody else.
8. **How long we keep it** — until account deletion + 30 days for backups; logs
   14 / 30 days.
9. **Your rights** — access, rectification, erasure, portability, complaint to
   a supervisory authority. How to exercise them: privacy-request form
   (removal / access / correction, §9.5) for non-users; account settings for
   Owners and Contributors.
10. **Changes** — versioned; users re-asked to accept on change.

---

## 10. Open Questions for Legal Review

Items above explicitly flagged for the lawyer:

1. Is the household exemption defensible for the friends-only mode, or should
   we treat *any* share link as crossing into controller territory? (CJEU
   *Lindqvist* suggests we should.)
2. Is "Owner-as-controller, NovoTree-as-processor" the right framing, or are we
   joint controllers under Art. 26?
3. Is the 30-day privacy-request SLA reasonable in the operating jurisdiction?
   Some regulators expect "without undue delay" interpreted as ~ 1 month.
4. Children's data thresholds vary (13 / 14 / 15 / 16 across EU). Pick one
   conservative threshold (16) or detect by user country.
5. Do we need a dedicated DPO (Data Protection Officer)? Likely no for current
   scale, but document the threshold under which we would.
6. International transfer mechanism — SCCs sufficient if VM provider is
   non-EEA, or do we move to EEA-only hosting?
7. Confirm the cookie-notice text and the absence of an "Accept / Reject"
   button is acceptable in CNIL / ICO / DPA practice (it is per the law; some
   regulators have published softer guidance).
