import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info } from 'lucide-react';

export const FAMILY_TYPE_DESCRIPTIONS: Array<{ code: string; text: string }> = [
  { code: 'Marriage', text: 'State-registered union.' },
  { code: 'Civil Union', text: 'Legal union with marriage-like rights.' },
  { code: 'Domestic Partnership', text: 'Registered cohabitation; fewer rights.' },
  { code: 'Common-Law Marriage', text: 'Long-term cohabitation, no ceremony.' },
  { code: 'Other', text: 'Any other arrangement.' },
];

const POPOVER_WIDTH = 320;

export const FamilyTypeInfoButton = () => {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        buttonRef.current?.contains(target) ||
        popoverRef.current?.contains(target)
      ) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleToggle = () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const margin = 8;
      const maxLeft = window.innerWidth - POPOVER_WIDTH - margin;
      setPos({
        top: rect.bottom + 4,
        left: Math.min(rect.left, Math.max(margin, maxLeft)),
      });
    }
    setOpen((o) => !o);
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleToggle}
        className="text-gray-400 hover:text-gray-600 cursor-help"
        aria-label="Family type help"
      >
        <Info className="w-4 h-4" />
      </button>
      {open && createPortal(
        <div
          ref={popoverRef}
          style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
          className="fixed z-[200] rounded-md border border-gray-200 bg-white p-3 text-xs text-gray-700 shadow-lg"
        >
          <div className="font-medium text-gray-800 mb-2">Family Type</div>
          <ul className="space-y-1.5">
            {FAMILY_TYPE_DESCRIPTIONS.map((d) => (
              <li key={d.code}>
                <span className="font-medium text-gray-800">{d.code}:</span> {d.text}
              </li>
            ))}
          </ul>
        </div>,
        document.body
      )}
    </>
  );
};
