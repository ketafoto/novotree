import { useState, type ReactNode } from 'react';
import { Heart } from 'lucide-react';
import { Modal } from './Modal';

/**
 * Donate ♥ pieces. Three exports:
 *
 *  - DonateButton: self-contained pink heart-button + modal. Used in the local
 *                  desktop app's Header where prominence is appropriate.
 *  - DonateLink:   plain pink underlined "Donate" anchor + modal. Used inside
 *                  PrivacyLinks in the Mode A web build so it sits next to
 *                  "Remove Me / Our Privacy" without dominating them.
 *  - DonateModal:  modal-only, controlled by the caller. Used by AboutDialog so
 *                  clicking "Donate" inside About opens this modal.
 *
 * All three render the same privacy disclaimer + GitHub Sponsors + Ko-fi links.
 * NovoTree never sees the transaction — this is Pattern A (link-out) in
 * docs/legal/PRIVACY_DESIGN.md §4.8. The Ko-fi logo is inline-hosted from
 * `public/donate/` so opening the modal does not leak a referer to ko-fi.com.
 *
 * Gated at call sites:
 *   - Local desktop app:    rendered in Header.tsx via `isLocalApp`.
 *   - 'private' web build:  rendered inside PrivacyLinks via deployment_mode.
 * The 'contributors' and 'public' modes deliberately do NOT show it —
 * placement requires the §4.1 lawyer review first.
 */

interface DonateModalProps {
  open: boolean;
  onClose: () => void;
}

function DonateModalContents() {
  return (
    <div className="space-y-4">
      <p className="text-gray-700">
        NovoTree is a one-person open-source project. If it's useful to
        you, a small donation helps keep development going.
      </p>
      <p className="text-sm text-gray-500">
        These links open in your browser. Donations are handled by GitHub
        Sponsors and Ko-fi; their privacy policies apply. NovoTree itself
        never sees the transaction.
      </p>
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <a
          href="https://github.com/sponsors/ketafoto"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 border border-pink-300 text-pink-600 hover:border-pink-500 hover:text-pink-700 hover:bg-pink-50 rounded-lg transition-colors font-medium"
        >
          <Heart className="w-4 h-4" fill="currentColor" />
          <span>GitHub Sponsors</span>
        </a>
        <a
          href="https://ko-fi.com/ketafoto"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center"
          aria-label="Buy Me a Coffee at ko-fi.com"
        >
          <img
            src={`${import.meta.env.BASE_URL}donate/kofi2.png`}
            alt="Buy Me a Coffee at ko-fi.com"
            height={36}
            style={{ border: 0, borderRadius: 6, height: 36 }}
          />
        </a>
      </div>
    </div>
  );
}

export function DonateModal({ open, onClose }: DonateModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Support NovoTree">
      <DonateModalContents />
    </Modal>
  );
}

interface DonateButtonProps {
  /** Render-prop trigger override (used by AboutDialog to nest a Donate button). */
  trigger?: (open: () => void) => ReactNode;
}

export function DonateButton({ trigger }: DonateButtonProps = {}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {trigger ? (
        trigger(() => setOpen(true))
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Support NovoTree development"
          className="flex items-center gap-2 px-3 py-1.5 border border-pink-300 text-pink-600 hover:border-pink-500 hover:text-pink-700 hover:bg-pink-50 rounded-lg transition-colors text-sm font-medium"
        >
          <Heart className="w-4 h-4" fill="currentColor" />
          <span>Donate</span>
        </button>
      )}
      <DonateModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/**
 * Plain text "Donate" link, sized to match peer links like Remove Me /
 * Our Privacy. Pink so it reads as a support affordance, underlined like its
 * neighbours so it reads as a link. Opens the same modal as DonateButton.
 */
export function DonateLink() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Support NovoTree development"
        className="text-pink-600 hover:text-pink-700 underline bg-transparent border-0 p-0 cursor-pointer"
        style={{ font: 'inherit' }}
      >
        Donate
      </button>
      <DonateModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
