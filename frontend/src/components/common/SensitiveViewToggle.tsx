/**
 * Owner-only status pill that toggles whether special-category (GDPR Art. 9)
 * data is revealed in the current view. The label names the CURRENT STATE
 * ("Sensitive data: Hidden" / "Shown") rather than a command, so it never
 * contradicts itself the way an eye icon + "Show sensitive" verb did. Clicking
 * flips the state; the (i) explains what counts as sensitive.
 *
 * UI-only: a shoulder-surfing guard, not access control, not persisted. Viewers
 * never see this control. See PRIVACY_DESIGN.md 3.7.
 */
import { Lock, Unlock } from 'lucide-react';
import { SensitiveInfo } from './SensitiveInfo';

interface SensitiveViewToggleProps {
  /** True when sensitive data is currently revealed in the view. */
  shown: boolean;
  onToggle: (next: boolean) => void;
  className?: string;
}

export function SensitiveViewToggle({ shown, onToggle, className }: SensitiveViewToggleProps) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!shown)}
      aria-pressed={shown}
      title={shown
        ? 'Sensitive data is currently shown on screen. Click to hide it. This affects only your view; it is not access control.'
        : 'Sensitive data is currently hidden on screen. Click to reveal it. This affects only your view; it is not access control.'}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium transition-colors ${
        shown
          ? 'bg-amber-50 border-amber-300 text-amber-800 hover:bg-amber-100'
          : 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100'
      } ${className ?? ''}`}
    >
      {shown ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
      Sensitive data: {shown ? 'Shown' : 'Hidden'}
      <SensitiveInfo />
    </button>
  );
}
