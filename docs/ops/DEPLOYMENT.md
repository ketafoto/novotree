# NovoTree — Deployment

NovoTree is deployed as part of the **NovoSpace** stack on a single Hetzner VM
behind Cloudflare. The end-to-end provisioning, Caddy configuration, systemd
service, environment file, backup cron, Cloudflare networking, and analytics
setup all live in one place:

> **Production deployment guide:**
> [`novospace.git/docs/deployment.md`](../../novospace.git/docs/deployment.md)

This file covers only what is **NovoTree-specific** and worth keeping close to
the application code: the post-deploy smoke test and pointers to the
auth/contributor/privacy design docs.

---

## App mode variables (quick reference)

NovoTree reads two app-mode variables. Both default to `admin` if unset.
**Both must be a non-`admin` value in production** — if either is left as
`admin`, that layer bypasses authentication.

| Variable | Read by | When | Effect of `admin` |
|---|---|---|---|
| `NOVOTREE_APP_MODE` | Python backend (FastAPI) | At runtime | All API endpoints skip JWT validation; every request is auto-authenticated as the default owner. |
| `VITE_NOVOTREE_APP_MODE` | Vite | At build time (`npm run build`) | The login screen is omitted from the compiled React app. The value is baked into the JS bundle. |

Full env-var reference, generation of `JWT_SECRET_KEY`, and SMTP optionality
are covered in [novospace.git/docs/deployment.md → Environment file](../../novospace.git/docs/deployment.md#environment-file-etcnovotreeenv).

For the JWT cookie strategy, password policy, and signup flows see
[AUTH_SCHEMA_PROPOSAL.md](AUTH_SCHEMA_PROPOSAL.md).

---

## Frontend static assets

Anything under [frontend/public/](../../frontend/public/) is served verbatim
under the configured base path (see also [frontend/PUBLIC_DIR.md](../../frontend/PUBLIC_DIR.md)
for the public-vs-src-assets cheat sheet). There is no asset allowlist in
the deploy scripts — `npm run build` copies the entire `public/` tree into
`dist/`, and the deploy scripts then `cp -r dist/. → /var/www/novospace/novotree/`.

The two pieces of project-specific glue:

| Where | What it does |
|---|---|
| [vite.config.ts](../../frontend/vite.config.ts) `base` | Reads `VITE_BASE_PATH` at build time; defaults to `/` for `npm run dev`. |
| [scripts/deployment/vm-setup.py](../../../novospace.git/scripts/deployment/vm-setup.py) and [vm-update.py](../../../novospace.git/scripts/deployment/vm-update.py) | Run `npm run build` with `VITE_BASE_PATH=/novotree/`, then `rm -rf` the web root and `cp -r frontend/dist/.` into it. |

Concrete example — adding `frontend/public/donate/kofi2.png`:

1. File lands on the VM via `git pull` in `vm-update.py` step 1.
2. `npm run build` writes it to `frontend/dist/donate/kofi2.png`.
3. The recursive copy puts it at `/var/www/novospace/novotree/donate/kofi2.png`.
4. Caddy's `handle /novotree/*` block serves it as
   `https://novospace.cz/novotree/donate/kofi2.png`.
5. In code, reference it via `${import.meta.env.BASE_URL}donate/kofi2.png` —
   `BASE_URL` is the same `VITE_BASE_PATH` value, so the URL is correct in
   both `npm run dev` (`/donate/kofi2.png`) and prod (`/novotree/donate/kofi2.png`).

**Do** put static assets under `public/` when you want them shipped as-is
(images that aren't imported, robots.txt, favicons, third-party logos that
should be self-hosted to avoid referer leaks).

**Don't** put assets under `public/` if they should be hashed and
tree-shaken — those go under `frontend/src/assets/` and are `import`-ed.
Vite fingerprints those for cache-busting; `public/` files are served at
their original path with no cache-busting.

---

## Post-deploy smoke test

Once `novospace` is provisioned and `novotree.service` is running, verify the
app behaves correctly before sharing the URL.

### Owner / contributor flow

1. Open `https://novospace.cz/novotree/signup` and create the first owner
   account. Confirm the verification email arrives and the link resolves to a
   logged-in dashboard.
2. Add one Individual record. Confirm `created_by` is the owner's `editor_id`.
3. Log out. Log back in. Confirm the JWT cookies are reset and `/auth/me`
   returns the owner identity.
4. Create a share token in Settings. Open it in a private window.

### Viewer flow (share token)

1. With `?share=<token>` in the URL, open `/tree`. Confirm the graph renders.
2. Click an Individual node. Confirm the focused tree view opens.
3. Try `POST /api/individuals` with the share token in `sessionStorage`.
   Confirm the API rejects with HTTP 403 (write methods are blocked for
   share-token sessions).
4. Open `/api/individuals` without any auth. Confirm HTTP 401.

### Backend baseline

```bash
# VM, as igorn
curl -s https://novospace.cz/api/health        # → 200, {"status": "ok"} or similar
sudo systemctl status novotree                 # → active (running)
sudo journalctl -u novotree -n 50              # no startup errors
```

If any of the above fails, see
[novospace.git/docs/deployment.md → Debugging](../../novospace.git/docs/deployment.md#debugging).

---

## Related design documents

| Topic | Document |
|---|---|
| Auth model (Owner / Contributor / Viewer), JWT, share tokens, signup flows | [AUTH_SCHEMA_PROPOSAL.md](AUTH_SCHEMA_PROPOSAL.md) |
| Contributor permissions, lifecycle states, email notifications, auto-cleanup | [CONTRIBUTOR_FEATURE.md](CONTRIBUTOR_FEATURE.md) |
| Privacy concerns and mitigations (GDPR/ePrivacy posture, takedown flow, etc.) | [PRIVACY_ANALYSIS.md](PRIVACY_ANALYSIS.md) |
| Privacy implementation plan (tiered checklist, central config, status) | [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) |
| Tree visualization design | [TREE_VISUALIZATION_DESIGN.md](TREE_VISUALIZATION_DESIGN.md) |
| Frontend architecture | [FRONTEND_DESIGN.md](FRONTEND_DESIGN.md) |
