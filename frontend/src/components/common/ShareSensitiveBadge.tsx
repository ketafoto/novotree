/**
 * Inline badges showing what a share link exposes, so the Owner can spot at a
 * glance which links carry special-category (GDPR Art. 9) data or minors (GDPR
 * Art. 8). Both reflect flags set at link creation (expose_sensitive /
 * expose_minors). See PRIVACY_DESIGN.md 3.7 / 3.8.
 */
import { Lock, Unlock } from 'lucide-react';

interface ShareExposeBadgeProps {
  /** True when the link exposes this category (shown), false when it is hidden. */
  exposed: boolean;
  shownLabel: string;
  hiddenLabel: string;
  shownTitle: string;
  hiddenTitle: string;
}

// One badge primitive; the sensitive / minor wrappers below just supply copy so
// the two stay visually identical and there is no duplicated markup.
//
function ShareExposeBadge({
  exposed,
  shownLabel,
  hiddenLabel,
  shownTitle,
  hiddenTitle,
}: ShareExposeBadgeProps) {
  return exposed ? (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-amber-300 bg-amber-50 text-amber-800 text-[10px] font-medium"
      title={shownTitle}
    >
      <Unlock className="w-3 h-3" />
      {shownLabel}
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-gray-200 bg-gray-50 text-gray-500 text-[10px] font-medium"
      title={hiddenTitle}
    >
      <Lock className="w-3 h-3" />
      {hiddenLabel}
    </span>
  );
}

export function ShareSensitiveBadge({ exposeSensitive }: { exposeSensitive: boolean }) {
  return (
    <ShareExposeBadge
      exposed={exposeSensitive}
      shownLabel="Sensitive shown"
      hiddenLabel="Sensitive hidden"
      shownTitle="This link exposes special-category (GDPR Art. 9) data — religion, ethnicity, health, cause of death."
      hiddenTitle="This link hides special-category (GDPR Art. 9) data — sensitive events, notes, people and photos are excluded."
    />
  );
}

export function ShareMinorBadge({ exposeMinors }: { exposeMinors: boolean }) {
  return (
    <ShareExposeBadge
      exposed={exposeMinors}
      shownLabel="Minors shown"
      hiddenLabel="Minors hidden"
      shownTitle="This link exposes living minors (GDPR Art. 8) — their record, connections and photos are visible."
      hiddenTitle="This link hides living minors (GDPR Art. 8) — they are excluded entirely from this link."
    />
  );
}
