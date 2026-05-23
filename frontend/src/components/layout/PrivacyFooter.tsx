import { Link } from 'react-router-dom';
import { isLocalApp } from '../../config/appMode';

/**
 * Global footer with the "Privacy / remove me" link required by
 * docs/PRIVACY_DESIGN.md §2.2. Rendered once at the App level so it appears
 * on every page — including share-link viewer routes that sit outside Layout.
 *
 * Hidden in the local desktop app: there the user is also the controller, so
 * the takedown flow has no second party to file against.
 *
 * The link prefills `?owner=<owner_id>` when a share-token session is active,
 * so the takedown form arrives populated for the most common case (viewer
 * recognizing themselves on a forwarded share link).
 */
export function PrivacyFooter() {
  if (isLocalApp) return null;

  const shareOwnerId = sessionStorage.getItem('share_owner_id');
  const takedownHref = shareOwnerId
    ? `/privacy/takedown?owner=${encodeURIComponent(shareOwnerId)}`
    : '/privacy/takedown';

  return (
    <footer className="border-t border-gray-200 bg-white text-xs text-gray-500">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-end gap-4">
        <Link to={takedownHref} className="hover:text-gray-700 underline">
          Privacy / remove me
        </Link>
      </div>
    </footer>
  );
}
