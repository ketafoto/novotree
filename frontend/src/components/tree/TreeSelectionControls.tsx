import { ListChecks, Send, X } from 'lucide-react';
import type { TreeSelection } from '../../hooks/useTreeSelection';

/**
 * The "select people" toggle + "Send privacy request for N selected" CTA shared
 * by TreePage and TreeOverviewPage (PRIVACY_DESIGN.md 3.9). Both pages mount
 * this with their `useTreeSelection()` object and an `onSend` that navigates to
 * the pre-filled /privacy/request form, so the chrome and its wording live in
 * one place rather than being copy-pasted across the two tree views.
 *
 * `variant` matches the surrounding chrome: 'desktop' renders compact pill-ish
 * buttons for the top toolbar; 'mobile' renders full-width buttons for the
 * hamburger drawer.
 */
interface TreeSelectionControlsProps {
  selection: TreeSelection;
  onSend: () => void;
  variant: 'desktop' | 'mobile';
}

export function TreeSelectionControls({
  selection,
  onSend,
  variant,
}: TreeSelectionControlsProps) {
  const { selectMode, toggleSelectMode, selectedCount } = selection;
  const canSend = selectMode && selectedCount > 0;

  if (variant === 'mobile') {
    return (
      <>
        <button
          onClick={toggleSelectMode}
          className={`w-full flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-lg border ${
            selectMode
              ? 'bg-emerald-600 text-white border-emerald-600 active:bg-emerald-700'
              : 'bg-white text-gray-700 border-gray-300 active:bg-gray-50'
          }`}
        >
          {selectMode ? <X className="w-4 h-4" /> : <ListChecks className="w-4 h-4" />}
          {selectMode ? 'Cancel selection' : 'Select people'}
        </button>
        {canSend && (
          <button
            onClick={onSend}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-lg active:bg-emerald-700"
          >
            <Send className="w-4 h-4" />
            Send privacy request for {selectedCount} selected
          </button>
        )}
      </>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={toggleSelectMode}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
          selectMode
            ? 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700'
            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
        }`}
        title="Select people to ask the tree owner to remove"
      >
        {selectMode ? <X className="w-3.5 h-3.5" /> : <ListChecks className="w-3.5 h-3.5" />}
        {selectMode ? 'Cancel' : 'Select people'}
      </button>
      {canSend && (
        <button
          onClick={onSend}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded-full hover:bg-emerald-700 transition-colors"
          title="Open a pre-filled privacy request for the selected people"
        >
          <Send className="w-3.5 h-3.5" />
          Send request for {selectedCount}
        </button>
      )}
    </div>
  );
}
