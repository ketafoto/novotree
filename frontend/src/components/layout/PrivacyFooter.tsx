import { isLocalApp } from '../../config/appMode';
import { PrivacyLinks } from './PrivacyLinks';

/**
 * Global footer with the privacy-link cluster (Remove Me / Our Privacy,
 * plus a Mode-A-only Donate link — see PrivacyLinks for the gating logic).
 *
 * Rendered once at the App level so it appears on every page that
 * participates in the document flow. The Tree pages render as a fullscreen
 * overlay (`fixed inset-0 z-50`) so they instead embed [PrivacyLinks]
 * directly in their top bar.
 *
 * Hidden in the local desktop app: there the user is also the controller,
 * so neither privacy link has a second party to address. The Donate button
 * is shown in the local app's Header instead — see Header.tsx.
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
