/**
 * Per-share acknowledgement modal (Privacy §2.5, PRIVACY_ANALYSIS.md §9.4).
 *
 * Shown when an Owner clicks "Create share link". Clicking the confirm
 * button IS the acknowledgement — backend writes one auth_share_consents
 * row in the same transaction as the share token. Cancel closes without
 * creating a token.
 *
 * Text is verbatim from PRIVACY_ANALYSIS.md §9.4. Treat the bullets as
 * legally-relevant copy: do not paraphrase without bumping
 * privacy_policy_version (the version stamped onto each consent row).
 */
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Modal } from './common/Modal';

interface ShareConsentModalProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  isSubmitting?: boolean;
}

export function ShareConsentModal({ open, onCancel, onConfirm, isSubmitting }: ShareConsentModalProps) {
  return (
    <Modal open={open} onClose={onCancel} title="Sharing this tree">
      <div className="space-y-4">
        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-300 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden />
          <div className="space-y-3 text-amber-900">
            <p>By creating this share link, I confirm that:</p>
            <ul className="list-disc list-outside pl-5 space-y-2">
              <li>I have permission from the living people in this tree, or they are deceased.</li>
              <li>I take responsibility for what I share and who I share it with.</li>
              <li>
                I will respond within 30 days to any removal request from a person who
                appears here.
              </li>
            </ul>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="inline-flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden />}
            Create share link
          </button>
        </div>
      </div>
    </Modal>
  );
}
