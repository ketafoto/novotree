import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { TreeDeciduous } from 'lucide-react';

import { privacyApi, type PrivacyPolicy } from '../../api/privacy';
import { renderPolicyMarkdown } from './renderPolicyMarkdown';

/**
 * Public privacy policy page. Rendered from markdown served by
 * GET /privacy/policy (sourced from docs/legal/privacy.md in-repo).
 * Tier 1 §2.3 of docs/PRIVACY_DESIGN.md.
 *
 * Sits outside Layout — anyone (including share-link viewers and unauthenticated
 * visitors who followed the footer link from the takedown form) can read it.
 */
export function PrivacyPage() {
  const [policy, setPolicy] = useState<PrivacyPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    privacyApi
      .getPolicy()
      .then((p) => {
        if (!cancelled) setPolicy(p);
      })
      .catch(() => {
        if (!cancelled) {
          setError('The privacy policy is temporarily unavailable. Please try again later.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-full bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto bg-white rounded-lg shadow p-8 space-y-6">
        <header className="flex items-center justify-between gap-3 border-b border-gray-200 pb-4">
          <Link to="/" className="flex items-center gap-2 text-emerald-700 hover:text-emerald-800">
            <TreeDeciduous size={28} />
            <span className="text-lg font-semibold">NovoTree</span>
          </Link>
          {policy && (
            <span className="text-xs text-gray-500">Policy version {policy.version}</span>
          )}
        </header>

        {error && <p className="text-red-600">{error}</p>}

        {!policy && !error && (
          <p className="text-gray-500">Loading…</p>
        )}

        {policy && (
          <article className="text-gray-800 leading-relaxed">
            {renderPolicyMarkdown(policy.content_markdown)}
          </article>
        )}

        <footer className="border-t border-gray-200 pt-4 text-sm text-gray-500 flex gap-4">
          <Link to="/privacy/takedown" className="text-emerald-700 underline hover:text-emerald-800">
            Privacy / remove me
          </Link>
        </footer>
      </div>
    </div>
  );
}
