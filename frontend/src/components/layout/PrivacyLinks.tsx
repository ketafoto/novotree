import { Link } from 'react-router-dom';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { DonateLink } from '../common/DonateButton';

/**
 * The privacy-link cluster used by both [PrivacyFooter.tsx] (every page that
 * participates in the document flow) and the Tree pages' top-bar (where the
 * global footer would otherwise be hidden by the `fixed inset-0 z-50`
 * fullscreen overlay).
 *
 * Order is "Remove Me" first — the more important affordance for a viewer who
 * recognized themselves on a forwarded share link. The label is intentionally
 * preserved verbatim from §2.2: it advertises one of three rights (removal,
 * access, correction) but the brand recognition matters more than the
 * comprehensiveness — the form itself names all three options. "Our Privacy"
 * is the supporting context. In Mode A only, a small pink "Donate" link
 * follows, styled to match the privacy peers so it does not dominate them
 * (docs/legal/PRIVACY_DESIGN.md §4.8 Pattern A). Modes B and C deliberately
 * omit Donate — placement there requires the §4.1 lawyer review first.
 *
 * Hidden in the local desktop app via the caller — neither privacy link has
 * a second party to address when the user is also the controller. The local
 * app shows DonateButton in its Header instead.
 */
const PRIVACY_REQUEST_BASE_PATH = '/privacy/request';
const PRIVACY_POLICY_PATH = '/legal/privacy';
const SHARE_OWNER_STORAGE_KEY = 'share_owner_id';

export function privacyRequestHref(): string {
  const shareOwnerId = sessionStorage.getItem(SHARE_OWNER_STORAGE_KEY);
  return shareOwnerId
    ? `${PRIVACY_REQUEST_BASE_PATH}?owner=${encodeURIComponent(shareOwnerId)}`
    : PRIVACY_REQUEST_BASE_PATH;
}

interface PrivacyLinksProps {
  /** Optional extra classes for the surrounding span (spacing, text color). */
  className?: string;
}

export function PrivacyLinks({ className = '' }: PrivacyLinksProps) {
  const { config } = usePrivacyConfig();
  const showDonate = config?.deployment_mode === 'A' && !config.analytics_enabled;

  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <Link
        to={privacyRequestHref()}
        className="text-emerald-700 hover:text-emerald-800 underline"
      >
        Remove Me
      </Link>
      <span aria-hidden className="text-gray-300">/</span>
      <Link
        to={PRIVACY_POLICY_PATH}
        className="hover:text-gray-700 underline"
      >
        Our Privacy
      </Link>
      {showDonate && (
        <>
          <span aria-hidden className="text-gray-300">/</span>
          <DonateLink />
        </>
      )}
    </span>
  );
}
