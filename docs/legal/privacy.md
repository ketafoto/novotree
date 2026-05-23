# NovoTree Privacy Policy

_Last updated: 2026-05-23 (version 1.0)_

This policy explains what information NovoTree holds about you, why, and how
to exercise your rights. It is written in plain language so a non-lawyer can
read it; the legal basis for each section is cited where relevant.

## 1. Who we are

NovoTree is a small, non-commercial family-tree service operated by
**Igor Novoseltsev** as the data controller.

- **Privacy contact:** [aktiniya@gmail.com](mailto:aktiniya@gmail.com)
- **Where to send removal requests:** the [Privacy — remove me](/privacy/takedown)
  form. The contact email above is for follow-up questions.

There is no dedicated Data Protection Officer (GDPR Art. 37) — NovoTree does
not operate at the scale that requires one.

## 2. Who is the controller for what

NovoTree distinguishes two kinds of data:

- **Account data** (your login email, password hash, role). NovoTree is the
  data controller for this.
- **Tree contents** (names, dates, relationships, photos, life events of the
  people in a family tree). The **Tree Owner** — the person who created the
  tree — is the data controller for these contents. NovoTree is a processor
  acting on the Owner's behalf, in the same posture as Dropbox or Google
  Drive for files you upload.

If your data appears in a tree you did not create, your request goes
primarily to that tree's Owner. NovoTree forwards the request and steps in
if the Owner does not respond within the SLA below.

## 3. What data we hold and why

| Category | Examples | Why |
|---|---|---|
| Account data | login email, password hash, role | To let you log in and to attribute edits |
| Tree contents | names, dates, places, relationships, photos, life events, notes | The service is a family-tree editor; this is the data you came here to record |
| Sensitive fields | religion, ethnicity, cause of death, health-related events | Treated as GDPR Art. 9 special-category data — hidden behind a "show sensitive" toggle and excluded from share links by default |
| Operational | server logs (URL, status, IP), error logs | Debugging and abuse detection |
| Takedown requests | name, email, message, optional phone | To act on the request and to prove we did, if a regulator asks |

NovoTree does **not** use analytics that set cookies, does **not** show
advertising, and does **not** sell data to anyone.

## 4. Lawful basis

| Data | Lawful basis (GDPR Art. 6) |
|---|---|
| Account data | (b) Contract — needed to provide the service |
| Tree contents | (f) Legitimate interest, as processor acting on the Owner's instructions. The Owner bears the (a) consent / (f) legitimate-interest determination for each individual they record |
| Operational logs | (f) Legitimate interest — running and securing the service |
| Takedown requests | (c) Legal obligation — fulfilling rights under GDPR Art. 12–17 |

## 5. Cookies and client-side storage

NovoTree only sets strictly-necessary cookies and storage:

| Item | Type | Lifetime | Purpose |
|---|---|---|---|
| `access_token` | HttpOnly cookie | 15 min | Keeps you logged in |
| `refresh_token` | HttpOnly cookie | 30 days | Silent refresh of the access token |
| `share_token` | `sessionStorage` (per tab) | Until tab closed | Lets a share-link viewer browse the tree they were sent |

Under the ePrivacy Directive Art. 5(3), strictly-necessary storage is exempt
from the consent requirement; only transparency is required. You will see a
short notice, not an Accept / Reject dialog. If we ever add analytics or
similar cookies, the notice will become a real consent dialog.

We use **Cloudflare Web Analytics**, which is cookieless and does not
fingerprint visitors.

## 6. Where the data lives

- **Application servers and primary storage:** Hetzner, Falkenstein / Helsinki
  (within the European Economic Area).
- **CDN and DNS:** Cloudflare (US-headquartered; certified under the EU-US
  Data Privacy Framework).
- **Backups:** the same EEA region as primary storage. Retained for **30
  days**, then deleted.

No personal data is transferred outside the EEA except via Cloudflare under
the DPF — which is the only US sub-processor we use.

## 7. Who we share data with

- **Hetzner** — infrastructure provider (EEA), bound by a DPA.
- **Cloudflare** — CDN, DNS, and cookieless analytics, bound by a DPA and
  certified under the EU-US Data Privacy Framework.
- **Email provider** — operational and verification emails. Bound by the
  provider's standard DPA.

We do not share data with any other third party. We have never received,
and do not anticipate, government data requests.

## 8. How long we keep it

| Data | Retention |
|---|---|
| Account data | Until you ask us to delete it |
| Tree contents | Until you (or the Tree Owner) delete it |
| Backups | 30 days |
| Web access logs | 14 days |
| Application error logs | 30 days |
| Resolved takedown requests | 12 months |

Backups can briefly retain data that has been deleted from the live
database. The 30-day window bounds how long a deleted record can resurface
from backup; we never restore individual records from backup unless we are
recovering from a service incident.

## 9. Your rights

If you are a person whose data appears on NovoTree — whether or not you have
an account — you have the right to:

- **Access** the data we hold about you.
- **Rectification** of inaccurate data.
- **Erasure** ("right to be forgotten").
- **Portability** in a machine-readable format.
- **Lodge a complaint** with your local supervisory authority.

### How to exercise these rights

- **You are not a NovoTree account holder.** Use the
  [Privacy — remove me](/privacy/takedown) form. We forward the request to
  the relevant Tree Owner, who has **30 days** to respond. If they do not,
  NovoTree will hide the records on your behalf.
- **You are an Owner or Contributor.** Use the in-app settings, or write to
  the privacy contact above.

The Tree Owner may ask you for additional information to verify your
identity before acting on a request — this is permitted by GDPR Art. 12(6)
and protects you from impersonation.

## 10. Children's data

NovoTree treats anyone under **16 years old** as a minor. Photo uploads of
minors require the Tree Owner to confirm they have parental consent, and
minors are not exposed via share links unless the Owner explicitly opts in
per share link.

If you believe a minor's data appears on NovoTree without proper consent,
use the takedown form above — these requests are prioritised.

## 11. Changes to this policy

When this policy changes substantively, the version number at the top of
the page is bumped. If you have a NovoTree account, you will be asked to
re-accept on next login. The policy is not silently updated.

---

_This document is engineering and product guidance for a small hobby
deployment. A paid legal review is scheduled before any larger launch (see
the project's `PRIVACY_DESIGN.md` §4.1)._
