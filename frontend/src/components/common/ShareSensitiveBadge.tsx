/**
 * Inline badge showing whether a share link exposes special-category
 * (GDPR Art. 9) data, so the Owner can spot at a glance which links carry
 * sensitive information. Reflects the token's expose_sensitive flag set at
 * creation. See PRIVACY_DESIGN.md 3.7.
 */
import { Lock, Unlock } from 'lucide-react';

interface ShareSensitiveBadgeProps {
  exposeSensitive: boolean;
}

export function ShareSensitiveBadge({ exposeSensitive }: ShareSensitiveBadgeProps) {
  return exposeSensitive ? (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-amber-300 bg-amber-50 text-amber-800 text-[10px] font-medium"
      title="This link exposes special-category (GDPR Art. 9) data — religion, ethnicity, health, cause of death."
    >
      <Unlock className="w-3 h-3" />
      Sensitive shown
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-gray-200 bg-gray-50 text-gray-500 text-[10px] font-medium"
      title="This link hides special-category (GDPR Art. 9) data — sensitive events, notes, people and photos are excluded."
    >
      <Lock className="w-3 h-3" />
      Sensitive hidden
    </span>
  );
}
