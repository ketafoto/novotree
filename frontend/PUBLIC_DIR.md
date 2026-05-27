# `frontend/public/` — what it is and how it ships

> This file documents the sibling [public/](./public/) folder. It lives one
> level up because Vite copies everything inside `public/` verbatim into
> `dist/`, so a README placed there would become a public production URL.

Static assets under [frontend/public/](./public/) are served verbatim under
the configured base path. There is **no allowlist** in the deploy scripts —
anything you add to that folder is shipped to production.

- **Dev:** served at `/<filename>` (e.g. `/donate/kofi2.png`).
- **Prod:** served at `/novotree/<filename>` (Caddy's `handle /novotree/*`).
- Reference in code via `${import.meta.env.BASE_URL}<filename>` so both
  environments resolve correctly.

## When to use `public/` vs `src/assets/`

| Goal | Where |
|---|---|
| Image, font, or doc served at a known URL (favicons, robots.txt, self-hosted third-party logos) | [public/](./public/) |
| Hashed, cache-busted asset that is `import`-ed from a component | `src/assets/` |

Files in `public/` are **not** fingerprinted — they keep their original
filenames and have no cache-busting. If you replace one, expect CDN/browser
caches to hold the old version until they expire.

## Deploy mechanics

See [docs/ops/DEPLOYMENT.md → Frontend static assets](../docs/ops/DEPLOYMENT.md#frontend-static-assets)
for the full chain (`git pull` → `npm run build` → `cp -r dist/.` → Caddy).
Working example: `donate/kofi2.png` referenced by
[DonateButton.tsx](./src/components/common/DonateButton.tsx).
