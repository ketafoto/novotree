import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { TreeDeciduous } from 'lucide-react';

import { privacyApi, type PrivacyPolicy } from '../../api/privacy';
import { renderPolicyMarkdown } from './renderPolicyMarkdown';
import { PolicyToc } from './PolicyToc';

/**
 * Public privacy policy page. Rendered from markdown served by
 * GET /privacy/policy (sourced from docs/legal/privacy.md in-repo).
 * Tier 1 §2.3 of docs/PRIVACY_DESIGN.md.
 *
 * Sits outside Layout — anyone (including share-link viewers and unauthenticated
 * visitors who followed the footer link from the takedown form) can read it.
 *
 * The TOC layout is currently behind a UI toggle so we can compare the two
 * shapes in production traffic before settling on one. Remove the toggle once
 * a decision is made — keep the chosen layout, drop the other branch and the
 * useState.
 */
type TocLayout = 'block' | 'sidebar';

export function PrivacyPage() {
  const [policy, setPolicy] = useState<PrivacyPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tocLayout, setTocLayout] = useState<TocLayout>('block');

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

  // Re-parse only when the markdown changes — heading slugs and content are
  // both products of one pass.
  const rendered = useMemo(
    () => (policy ? renderPolicyMarkdown(policy.content_markdown) : null),
    [policy],
  );

  // Container width depends on layout: the sidebar needs more horizontal room
  // so the prose column doesn't end up uncomfortably narrow.
  const containerMaxWidth = tocLayout === 'sidebar' ? 'max-w-6xl' : 'max-w-3xl';

  return (
    <div className="min-h-full bg-gray-50 py-10 px-4">
      <div className={`${containerMaxWidth} mx-auto bg-white rounded-lg shadow p-8 space-y-6`}>
        <header className="flex items-center justify-between gap-3 border-b border-gray-200 pb-4">
          <Link to="/" className="flex items-center gap-2 text-emerald-700 hover:text-emerald-800">
            <TreeDeciduous size={28} />
            <span className="text-lg font-semibold">NovoTree</span>
          </Link>
          <div className="flex items-center gap-4">
            <TocLayoutSwitcher value={tocLayout} onChange={setTocLayout} />
            {policy && (
              <span className="text-xs text-gray-500">Policy version {policy.version}</span>
            )}
          </div>
        </header>

        {error && <p className="text-red-600">{error}</p>}

        {!policy && !error && <p className="text-gray-500">Loading…</p>}

        {rendered && tocLayout === 'block' && (
          <>
            <PolicyToc headings={rendered.headings} variant="block" />
            <article className="text-gray-800 leading-relaxed">{rendered.content}</article>
          </>
        )}

        {rendered && tocLayout === 'sidebar' && (
          <div className="lg:grid lg:grid-cols-[1fr_15rem] lg:gap-8">
            <article className="text-gray-800 leading-relaxed min-w-0">
              {/* Mobile fallback: sidebar collapses to a top-of-doc block on
                  narrow screens so phone readers still get a ToC. */}
              <div className="lg:hidden">
                <PolicyToc headings={rendered.headings} variant="block" />
              </div>
              {rendered.content}
            </article>
            <aside className="hidden lg:block">
              <div className="sticky top-6">
                <PolicyToc headings={rendered.headings} variant="sidebar" />
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

interface TocLayoutSwitcherProps {
  value: TocLayout;
  onChange: (next: TocLayout) => void;
}

/**
 * Temporary UI toggle so the team can A/B the two ToC layouts side by side.
 * Will be removed once a layout is chosen — see PrivacyPage doc comment.
 */
function TocLayoutSwitcher({ value, onChange }: TocLayoutSwitcherProps) {
  return (
    <div className="inline-flex rounded-md border border-gray-200 bg-gray-50 text-xs">
      <button
        type="button"
        aria-pressed={value === 'block'}
        onClick={() => onChange('block')}
        className={`px-2.5 py-1 rounded-l-md transition-colors ${
          value === 'block'
            ? 'bg-white text-gray-900 font-medium shadow-sm'
            : 'text-gray-500 hover:text-gray-700'
        }`}
      >
        Top ToC
      </button>
      <button
        type="button"
        aria-pressed={value === 'sidebar'}
        onClick={() => onChange('sidebar')}
        className={`px-2.5 py-1 rounded-r-md transition-colors border-l border-gray-200 ${
          value === 'sidebar'
            ? 'bg-white text-gray-900 font-medium shadow-sm'
            : 'text-gray-500 hover:text-gray-700'
        }`}
      >
        Sidebar ToC
      </button>
    </div>
  );
}
