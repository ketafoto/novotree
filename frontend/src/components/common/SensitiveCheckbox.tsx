/**
 * Shared "mark sensitive" checkbox affordance used wherever the Owner can flag a
 * record as special-category (GDPR Art. 9) data: the individual basic-info modal,
 * the notes editor, the event dialog, and the share-link modal. Gives all of them
 * one consistent look (amber warning box + alert icon) and the shared
 * explanation, so the Owner never has to guess what "sensitive" means.
 * See PRIVACY_DESIGN.md 3.7.
 */
import { AlertTriangle } from 'lucide-react';
import { SensitiveInfo } from './SensitiveInfo';
import { SENSITIVE_DATA_EXPLANATION } from '../../constants/sensitiveData';

interface SensitiveCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** The control's label, e.g. "Mark this event sensitive". */
  label: string;
  /** When true the box is locked checked (e.g. an inherently-religious event type). */
  locked?: boolean;
  /** Optional override of the explanatory line (defaults to the shared copy). */
  description?: string;
}

export function SensitiveCheckbox({
  checked,
  onChange,
  label,
  locked = false,
  description,
}: SensitiveCheckboxProps) {
  const active = checked || locked;
  return (
    <div className={`flex gap-3 p-3 rounded-lg border ${
      active ? 'bg-amber-50 border-amber-300' : 'bg-gray-50 border-gray-200'
    }`}>
      <AlertTriangle
        className={`w-5 h-5 flex-shrink-0 mt-0.5 ${active ? 'text-amber-600' : 'text-gray-400'}`}
        aria-hidden
      />
      <div className="space-y-1">
        <label className="flex items-center gap-2 text-sm font-semibold text-amber-900">
          <input
            type="checkbox"
            checked={active}
            disabled={locked}
            onChange={(e) => onChange(e.target.checked)}
          />
          {label} <SensitiveInfo />
        </label>
        <p className="text-xs text-amber-800">{description ?? SENSITIVE_DATA_EXPLANATION}</p>
      </div>
    </div>
  );
}
