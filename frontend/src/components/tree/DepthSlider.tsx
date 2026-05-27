import { useState, useCallback } from 'react';
import { Lock, Unlock } from 'lucide-react';

interface DepthSliderProps {
  ancestorDepth: number;
  descendantDepth: number;
  maxAncestorDepth: number;
  maxDescendantDepth: number;
  onAncestorDepthChange: (depth: number) => void;
  onDescendantDepthChange: (depth: number) => void;
}

/**
 * Two independent sliders for ancestor/descendant depth with a "Lock" checkbox.
 * When locked, moving either slider moves the other symmetrically.
 */
export function DepthSlider({
  ancestorDepth,
  descendantDepth,
  maxAncestorDepth,
  maxDescendantDepth,
  onAncestorDepthChange,
  onDescendantDepthChange,
}: DepthSliderProps) {
  const [locked, setLocked] = useState(true);

  const handleAncestorChange = useCallback(
    (value: number) => {
      onAncestorDepthChange(value);
      if (locked) {
        onDescendantDepthChange(Math.min(value, maxDescendantDepth));
      }
    },
    [locked, maxDescendantDepth, onAncestorDepthChange, onDescendantDepthChange],
  );

  const handleDescendantChange = useCallback(
    (value: number) => {
      onDescendantDepthChange(value);
      if (locked) {
        onAncestorDepthChange(Math.min(value, maxAncestorDepth));
      }
    },
    [locked, maxAncestorDepth, onAncestorDepthChange, onDescendantDepthChange],
  );

  return (
    <div className="flex items-center gap-3">
      {/* Ancestor slider */}
      <div className="flex items-center gap-2">
        <label className="text-[11px] font-medium text-slate-600 whitespace-nowrap">
          Ancestors
        </label>
        <input
          type="range"
          min={0}
          max={maxAncestorDepth}
          value={ancestorDepth}
          onChange={(e) => handleAncestorChange(Number(e.target.value))}
          className="w-24 h-1.5 accent-emerald-600"
        />
        <span className="text-[11px] text-slate-500 w-9 text-right tabular-nums">
          {ancestorDepth} / {maxAncestorDepth}
        </span>
      </div>

      {/* Lock toggle */}
      <button
        onClick={() => setLocked(!locked)}
        className={`p-1 rounded-md transition-colors ${
          locked
            ? 'text-emerald-700 hover:bg-emerald-100'
            : 'text-slate-400 hover:bg-slate-200'
        }`}
        title={locked ? 'Sliders locked (symmetric)' : 'Sliders unlocked (independent)'}
      >
        {locked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
      </button>

      {/* Descendant slider */}
      <div className="flex items-center gap-2">
        <label className="text-[11px] font-medium text-slate-600 whitespace-nowrap">
          Descendants
        </label>
        <input
          type="range"
          min={0}
          max={maxDescendantDepth}
          value={descendantDepth}
          onChange={(e) => handleDescendantChange(Number(e.target.value))}
          className="w-24 h-1.5 accent-emerald-600"
        />
        <span className="text-[11px] text-slate-500 w-9 text-right tabular-nums">
          {descendantDepth} / {maxDescendantDepth}
        </span>
      </div>
    </div>
  );
}
