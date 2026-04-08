const mode = (import.meta.env.VITE_APP_MODE ?? 'admin').toLowerCase();

/** Dev mode: auth is bypassed — no login screen, auto-authenticated as owner. */
export const isDevMode = mode === 'admin';

/** @deprecated Use isDevMode instead */
export const appMode = mode === 'public' ? 'public' : 'admin';
/** @deprecated Use !isDevMode and role checks via useAuth() instead */
export const isPublicApp = false;
