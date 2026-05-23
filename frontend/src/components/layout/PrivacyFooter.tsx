import { isLocalApp } from '../../config/appMode';
import { PrivacyLinks } from './PrivacyLinks';

/**
 * Global footer with the "Remove me / Our Privacy" link pair
 * (docs/PRIVACY_DESIGN.md §2.2 + §2.3).
 *
 * Rendered once at the App level so it appears on every page that
 * participates in the document flow. The Tree pages render as a fullscreen
 * overlay (`fixed inset-0 z-50`) so they instead embed the same link pair
 * via [PrivacyLinks] directly in their top bar.
 *
 * Hidden in the local desktop app: there the user is also the controller,
 * so neither link has a second party to address (no takedown to file, no
 * controller-disclosure obligation to satisfy).
 */
export function PrivacyFooter() {
  if (isLocalApp) return null;

  return (
    <footer className="border-t border-gray-200 bg-white text-xs text-gray-500">
      <div className="px-4 py-3 flex items-center justify-center">
        <PrivacyLinks />
      </div>
    </footer>
  );
}
