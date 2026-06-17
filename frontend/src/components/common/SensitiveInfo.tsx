/**
 * Small info affordance explaining what counts as special-category (GDPR Art. 9)
 * data. Reused next to every place the Owner can mark data sensitive or toggle
 * the sensitive view, so the Owner never has to guess. Copy is the shared
 * SENSITIVE_DATA_EXPLANATION (PRIVACY_DESIGN.md 3.7).
 */
import { Info } from 'lucide-react';
import { SENSITIVE_DATA_EXPLANATION } from '../../constants/sensitiveData';

interface SensitiveInfoProps {
  className?: string;
}

export function SensitiveInfo({ className }: SensitiveInfoProps) {
  return (
    <span
      className={`inline-flex items-center cursor-help ${className ?? ''}`}
      title={SENSITIVE_DATA_EXPLANATION}
      aria-label={SENSITIVE_DATA_EXPLANATION}
    >
      <Info className="w-4 h-4 text-gray-400" aria-hidden />
    </span>
  );
}
