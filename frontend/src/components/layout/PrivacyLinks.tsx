import { Link } from 'react-router-dom';

/**
 * The "Remove me / Our Privacy" link pair used by both [PrivacyFooter.tsx]
 * (every page that participates in the document flow) and the Tree page
 * top-bar (where the global footer would otherwise be hidden by the
 * `fixed inset-0 z-50` fullscreen overlay).
 *
 * Order is "Remove me" first — it is the more important affordance for a
 * viewer who recognized themselves on a forwarded share link. "Our Privacy"
 * is the supporting context. Both are visually unobtrusive; the takedown
 * link gets a tiny coloured accent so it stands out from the chrome.
 *
 * Hidden in the local desktop app via the caller — neither link has a second
 * party to address when the user is also the controller.
 */
const TAKEDOWN_BASE_PATH = '/privacy/takedown';
const PRIVACY_POLICY_PATH = '/legal/privacy';
const SHARE_OWNER_STORAGE_KEY = 'share_owner_id';

export function takedownHref(): string {
  const shareOwnerId = sessionStorage.getItem(SHARE_OWNER_STORAGE_KEY);
  return shareOwnerId
    ? `${TAKEDOWN_BASE_PATH}?owner=${encodeURIComponent(shareOwnerId)}`
    : TAKEDOWN_BASE_PATH;
}

interface PrivacyLinksProps {
  /** Optional extra classes for the surrounding span (spacing, text color). */
  className?: string;
}

export function PrivacyLinks({ className = '' }: PrivacyLinksProps) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <Link
        to={takedownHref()}
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
    </span>
  );
}
