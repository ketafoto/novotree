import { Link } from 'react-router-dom';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { DonateLink } from '../common/DonateButton';
import {
  PARAM_INDIVIDUAL_IDS,
  PARAM_OWNER,
  PARAM_REQUEST_TYPE,
  REQUEST_TYPE_REMOVAL,
} from '../../constants/privacyRequestParams';

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

interface PrivacyRequestHrefParams {
  /** Tree owner username the request is filed against; omitted if unknown. */
  ownerId?: string;
  /**
   * GEDCOM-shaped ids (e.g. ["I1", "I2"]) of the people the request concerns.
   * When non-empty, a removal request_type is implied (the only kind the tree
   * selection CTA emits today -- see PRIVACY_DESIGN.md 3.9).
   */
  individualGedcomIds?: string[];
}

/**
 * Build the /privacy/request URL with whatever context we have. Single place
 * the query-param contract (PARAM_*) is assembled, so the footer "Remove Me"
 * link and the tree selection-mode CTA cannot disagree about param names.
 */
export function buildPrivacyRequestHref({
  ownerId,
  individualGedcomIds,
}: PrivacyRequestHrefParams): string {
  const params = new URLSearchParams();
  if (ownerId) params.set(PARAM_OWNER, ownerId);
  if (individualGedcomIds && individualGedcomIds.length > 0) {
    params.set(PARAM_INDIVIDUAL_IDS, individualGedcomIds.join(','));
    params.set(PARAM_REQUEST_TYPE, REQUEST_TYPE_REMOVAL);
  }
  const query = params.toString();
  return query ? `${PRIVACY_REQUEST_BASE_PATH}?${query}` : PRIVACY_REQUEST_BASE_PATH;
}

export function privacyRequestHref(): string {
  const shareOwnerId = sessionStorage.getItem(SHARE_OWNER_STORAGE_KEY);
  return buildPrivacyRequestHref({ ownerId: shareOwnerId ?? undefined });
}

interface PrivacyLinksProps {
  /** Optional extra classes for the surrounding span (spacing, text color). */
  className?: string;
}

export function PrivacyLinks({ className = '' }: PrivacyLinksProps) {
  const { config } = usePrivacyConfig();
  const showDonate = config?.deployment_mode === 'private' && !config.analytics_enabled;

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
