# Public Read-Only Deployment — SUPERSEDED

> **This document describes the old two-server deployment model (`APP_MODE=public`) which has been replaced.**
>
> The current deployment model uses a **single server** with full OCV (Owner / Viewer / Contributor) auth. See [DEPLOYMENT.md](../DEPLOYMENT.md) for the current guide.

---

## What changed

| Old model | Current model |
|-----------|--------------|
| Separate local (edit) + public (read-only) servers | Single server, all access controlled via auth |
| `APP_MODE=public` enforces read-only | Read-only is per-session: Viewers use a share token (`?share=<token>`) |
| No login for the public site | Owners and contributors log in; viewers get a share link |
| Data published via export → import pipeline | No publish step; owners edit live data |
| `VITE_APP_MODE=public` frontend flag | `APP_MODE=admin` for local dev bypass; anything else = full auth |

---

## What is still relevant from this document

### Security baseline checklist (still applies)

- Expose only ports 80/443 publicly; restrict SSH to key auth.
- Enable unattended OS security updates.
- Keep dependency updates regular (`pip`, `npm`).
- Monitor logs and set alerting for repeated 4xx/5xx spikes.
- Use Caddy (or nginx) in front of the backend for TLS termination.

### Smoke test after deploy (still applies)

- Open `/tree` (with a valid share token or as a logged-in user) and verify the graph renders.
- Click a person node and verify the focused tree opens.
- Confirm `POST/PUT/DELETE` API calls are rejected for share-token sessions (HTTP 403).
- Confirm unauthenticated requests to protected API endpoints return HTTP 401.

---

## Current deployment

See [DEPLOYMENT.md](../DEPLOYMENT.md) for:
- Dedicated `novotree` system user setup
- Directory layout and permissions
- systemd service configuration with security hardening
- Caddy TLS with automatic Let's Encrypt certificates
- JWT secret generation
- SMTP (optional) configuration
- First-run owner signup
- SQLite backup cron
