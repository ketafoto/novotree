import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Modal } from './common/Modal';
import { useAuth } from '../contexts/AuthContext';
import { usePrivacyConfig } from '../hooks/usePrivacyConfig';
import { isLocalApp } from '../config/appMode';

/**
 * One-shot notice shown the first time a viewer opens a tree via a
 * `?share=<token>` URL. Text is the §9.3 draft in
 * docs/legal/PRIVACY_ANALYSIS.md and the requirement is §2.4 in
 * docs/legal/PRIVACY_DESIGN.md (M-16).
 *
 * Gating lives here, not at the call site — same pattern as PrivacyLinks.
 * The component is mounted unconditionally at the App level and decides
 * for itself whether to render. Hidden in the local desktop app (no
 * viewers there). Not gated on deployment_mode — viewer notices apply in
 * A, B, and C alike.
 *
 * Dismissed once per share token, scoped to the current cookie_notice_version
 * so a bumped version re-shows. The token is SHA-256 hashed before going
 * into sessionStorage so the raw token never appears under this key.
 */

const STORAGE_KEY_PREFIX = 'viewer_notice_dismissed';
const TOKEN_HASH_LEN = 16;

async function hashShareToken(token: string): Promise<string> {
  const bytes = new TextEncoder().encode(token);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, TOKEN_HASH_LEN);
}

function buildDismissalKey(tokenHash: string, version: string): string {
  return `${STORAGE_KEY_PREFIX}:${tokenHash}:${version}`;
}

export function ViewerNotice() {
  const { shareToken, isLoading } = useAuth();
  const { config } = usePrivacyConfig();

  const [dismissalKey, setDismissalKey] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const eligible =
    !isLocalApp &&
    !isLoading &&
    shareToken !== null &&
    config !== null;

  useEffect(() => {
    if (!eligible) {
      setDismissalKey(null);
      setOpen(false);
      return;
    }
    let cancelled = false;
    void hashShareToken(shareToken!).then((hash) => {
      if (cancelled) return;
      const key = buildDismissalKey(hash, config!.cookie_notice_version);
      setDismissalKey(key);
      setOpen(sessionStorage.getItem(key) === null);
    });
    return () => { cancelled = true; };
  }, [eligible, shareToken, config]);

  const dismiss = () => {
    if (dismissalKey) sessionStorage.setItem(dismissalKey, '1');
    setOpen(false);
  };

  if (!open) return null;

  return (
    <Modal open={open} onClose={dismiss} title="You are viewing a shared tree">
      <div className="space-y-4">
        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-300 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden />
          <div className="space-y-3 text-amber-900">
            <p>
              You are viewing a private family tree shared with you.
            </p>
            <p>
              Please do not redistribute, copy, or scrape its contents. The
              information here belongs to the families it describes.
            </p>
            <p>
              If you appear in this tree and want to be removed, use the{' '}
              <span className="font-semibold">Remove Me</span> link.
            </p>
          </div>
        </div>
        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={dismiss}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors"
          >
            Got it
          </button>
        </div>
      </div>
    </Modal>
  );
}
