const mode = (import.meta.env.VITE_NOVOTREE_APP_MODE ?? 'admin').toLowerCase();

/** Dev mode: auth is bypassed — no login screen, auto-authenticated as owner. */
export const isDevMode = mode === 'admin';

/**
 * Local installer build: the SPA is bundled into the desktop .exe.
 * Set by installer/build.ps1 only — the web/VM build leaves it unset.
 * Used to gate features that only make sense in the offline desktop app
 * (the Donate ♥ button, future "Move data folder…" dialog, etc.).
 *
 * Written as a direct literal comparison so Vite/Rollup can constant-fold
 * the value at build time and tree-shake the gated code paths out of the
 * web bundle — no donate strings, ko-fi URL, or sponsor handle should
 * appear in `frontend/dist/` for the web/VM deployment.
 */
export const isLocalApp = import.meta.env.VITE_NOVOTREE_INSTALLER === 'true';

/** @deprecated Use isDevMode instead */
export const appMode = mode === 'public' ? 'public' : 'admin';
/** @deprecated Use !isDevMode and role checks via useAuth() instead */
export const isPublicApp = false;
