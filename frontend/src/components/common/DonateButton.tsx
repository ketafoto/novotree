import { useState, type ReactNode } from 'react';
import { Heart } from 'lucide-react';
import { Modal } from './Modal';

/**
 * Donate ♥ pieces shown in the local desktop app's header. Two exports:
 *
 *  - DonateButton: self-contained heart-button + modal (drop-in for the header).
 *  - DonateModal:  modal-only, controlled by the caller. Used by AboutDialog so
 *                  clicking "Donate" inside About opens this modal.
 *
 * Both render a privacy disclaimer + GitHub Sponsors + Ko-fi links. The links
 * open in the user's default browser, not inside the pywebview window.
 *
 * Local-app-only — gated by isLocalApp at the call site (Header.tsx).
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
            src="https://storage.ko-fi.com/cdn/kofi2.png?v=3"
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
