import { X, GitBranch, User } from 'lucide-react';
import { sortEventsChronologically } from '../../utils/eventSort';
import type { TreeNode, TreeNodeName } from '../../types/models';

interface MobilePersonSheetProps {
  data: TreeNode;
  /** Disable the recenter button when this person is already the focus. */
  isFocus: boolean;
  /** Label for the primary action — varies by host page (recenter vs. open tree). */
  recenterLabel: string;
  onRecenter: () => void;
  onViewProfile: () => void;
  onClose: () => void;
}

const MOBILE_SHEET_NAME_LABELS: Record<string, string> = {
  birth: 'Birth name',
  maiden: 'Maiden name',
  married: 'Married name',
  aka: 'Also known as',
};

function getMobileSheetNameLabel(nameType?: string): string {
  if (!nameType?.trim()) return 'Name';
  const key = nameType.trim().toLowerCase();
  if (MOBILE_SHEET_NAME_LABELS[key]) return MOBILE_SHEET_NAME_LABELS[key];
  if (key.includes('maiden')) return 'Maiden name';
  if (key.includes('married')) return 'Married name';
  if (key.includes('aka') || key.includes('also known')) return 'Also known as';
  if (key.includes('birth')) return 'Birth name';
  return nameType;
}

function formatMobileSheetDate(exactDate?: string, approxDate?: string): string {
  if (exactDate) return exactDate;
  if (approxDate) return approxDate;
  return '';
}

/**
 * Bottom sheet shown on mobile when a person node is tapped.
 * Replaces the desktop hover-tooltip + click-to-recenter combo with
 * an explicit, touch-friendly UI.
 */
export function MobilePersonSheet({
  data,
  isFocus,
  recenterLabel,
  onRecenter,
  onViewProfile,
  onClose,
}: MobilePersonSheetProps) {
  const displayName = (data.display_name || '').trim();
  const names: TreeNodeName[] = (data.names ?? []).filter(
    (n) => (n.formatted || '').trim() && (n.formatted || '').trim() !== displayName,
  );
  const birthDate = formatMobileSheetDate(data.birth_date, data.birth_date_approx);
  const deathDate = formatMobileSheetDate(data.death_date, data.death_date_approx);
  const hasNames = names.length > 0;
  const hasBirth = birthDate || data.birth_place;
  const hasDeath = deathDate || data.death_place;
  const hasEvents = data.events.length > 0;
  const hasNotes = !!data.notes;
  const hasAnyContent = hasNames || hasBirth || hasDeath || hasEvents || hasNotes;

  return (
    <>
      <div
        className="fixed inset-0 z-[60] bg-black/30"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        className="fixed bottom-0 left-0 right-0 z-[70] bg-white rounded-t-2xl shadow-2xl max-h-[80vh] flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-gray-300" />
        </div>

        <div className="flex items-start justify-between px-4 pb-2 border-b border-gray-100">
          <div className="min-w-0 flex-1 pr-2">
            <p className="font-semibold text-base text-gray-900 truncate">
              {data.display_name}
            </p>
            {data.gedcom_id && (
              <p className="text-[11px] text-gray-400">{data.gedcom_id}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 -m-1.5 hover:bg-gray-100 rounded-lg"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm">
          {hasNames && (
            <div className="space-y-1">
              {names.map((n, idx) => (
                <div key={idx}>
                  <span className="font-medium text-gray-700">
                    {getMobileSheetNameLabel(n.name_type)}:
                  </span>
                  <span className="text-gray-600 ml-1">{n.formatted}</span>
                </div>
              ))}
            </div>
          )}

          {hasBirth && (
            <div>
              <span className="font-medium text-gray-700">Born</span>
              {birthDate && <span className="text-gray-500 ml-1">{birthDate}</span>}
              {data.birth_place && (
                <span className="text-gray-400 ml-1">— {data.birth_place}</span>
              )}
            </div>
          )}

          {hasDeath && (
            <div>
              <span className="font-medium text-gray-700">Died</span>
              {deathDate && <span className="text-gray-500 ml-1">{deathDate}</span>}
              {data.death_place && (
                <span className="text-gray-400 ml-1">— {data.death_place}</span>
              )}
            </div>
          )}

          {hasEvents && (
            <div className="space-y-1.5 pt-1">
              {sortEventsChronologically(data.events).map((event, idx) => {
                const date = formatMobileSheetDate(event.event_date, event.event_date_approx);
                return (
                  <div key={idx} className="flex gap-2">
                    <div className="flex-shrink-0 mt-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    </div>
                    <div className="min-w-0">
                      <span className="font-medium text-gray-700">
                        {date && <span className="text-gray-500 mr-1">{date}</span>}
                        {event.event_type}
                      </span>
                      {event.event_place && (
                        <p className="text-gray-400 truncate">{event.event_place}</p>
                      )}
                      {event.description && (
                        <p className="text-gray-400 italic">{event.description}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {hasNotes && (
            <p className="text-gray-500 italic whitespace-pre-line">{data.notes}</p>
          )}

          {!hasAnyContent && (
            <p className="text-gray-400 italic">No details recorded</p>
          )}
        </div>

        <div className="px-4 py-3 border-t border-gray-100 flex flex-col gap-2 bg-slate-50">
          <button
            onClick={onRecenter}
            disabled={isFocus}
            className="flex items-center justify-center gap-2 py-2.5 bg-emerald-600 text-white font-medium rounded-lg disabled:bg-gray-300 disabled:cursor-not-allowed active:bg-emerald-700"
          >
            <GitBranch className="w-4 h-4" />
            {recenterLabel}
          </button>
          <button
            onClick={onViewProfile}
            className="flex items-center justify-center gap-2 py-2.5 bg-white text-gray-700 font-medium rounded-lg border border-gray-300 active:bg-gray-50"
          >
            <User className="w-4 h-4" />
            View full profile
          </button>
        </div>
      </div>
    </>
  );
}
