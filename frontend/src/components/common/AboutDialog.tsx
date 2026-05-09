import { useState } from 'react';
import { Info, Heart, Copy } from 'lucide-react';
import toast from 'react-hot-toast';
import { Modal } from './Modal';
import { Button } from './Button';

// Build-time version. Single source of truth: keep in sync with version.py
// at the repo root (the installer also reads __version__ from there).
const APP_VERSION = '0.1.0';
const SUPPORT_EMAIL = 'support@contact.novotree.cz';

interface AboutDialogProps {
  /** Optional override — caller can open a Donate modal after Close. */
  onOpenDonate?: () => void;
}

/**
 * About ⓘ button + modal shown in the local desktop app's header.
 * Mirrors novoface's pattern: small unobtrusive header button → modal
 * with the app name, version, support email, and a "Donate ♥" button
 * that defers to the caller (so we don't double-implement Donate here).
 *
 * Local-app only — gated by isLocalApp at the call site (Header.tsx).
 */
export function AboutDialog({ onOpenDonate }: AboutDialogProps) {
  const [open, setOpen] = useState(false);

  const handleCopyEmail = async () => {
    try {
      await navigator.clipboard.writeText(SUPPORT_EMAIL);
      toast.success('Email copied');
    } catch {
      toast.error('Copy failed');
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="About NovoTree"
        className="flex items-center justify-center w-9 h-9 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Info className="w-5 h-5" />
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="About NovoTree">
        <div className="text-center space-y-4 py-2">
          <div>
            <p className="text-2xl font-semibold text-emerald-700">NovoTree</p>
            <p className="text-sm text-gray-500 mt-1">v{APP_VERSION}</p>
          </div>
          <hr className="border-gray-200" />
          <p className="text-sm text-gray-600">
            A privacy-first genealogy app — your data stays on your machine.
          </p>
          <p className="text-xs text-gray-500">
            Contact:{' '}
            <span className="inline-flex items-center gap-1.5 align-middle">
              {/* Plain selectable text. Browsers/WebView2 sometimes treat <a>
                  as drag-only and swallow Ctrl+C; rendering the address as a
                  span with `select-text` keeps it copyable, and the small
                  copy-icon next to it is a one-click alternative. */}
              <span className="text-emerald-700 break-all select-text">
                {SUPPORT_EMAIL}
              </span>
              <button
                type="button"
                onClick={handleCopyEmail}
                title="Copy email"
                className="flex-shrink-0 p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
              >
                <Copy className="w-3 h-3" />
              </button>
            </span>
          </p>
          {onOpenDonate && (
            <div className="pt-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setOpen(false);
                  onOpenDonate();
                }}
              >
                <Heart className="w-4 h-4 mr-2 fill-current text-pink-600" />
                Donate
              </Button>
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}
