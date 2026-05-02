import { Languages } from 'lucide-react';
import { buildTranslateUrl } from '../../utils/translate';

interface TranslateButtonProps {
  /** Static text, or a getter for live values (e.g. react-hook-form watch). */
  getText: string | (() => string | undefined);
  className?: string;
  title?: string;
}

export function TranslateButton({
  getText,
  className = '',
  title = 'Open in Google Translate',
}: TranslateButtonProps) {
  const handleClick = () => {
    const text = (typeof getText === 'function' ? getText() : getText) ?? '';
    const trimmed = text.trim();
    if (!trimmed) return;
    window.open(buildTranslateUrl(trimmed), '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title={title}
      className={`inline-flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-600 ${className}`}
    >
      <Languages className="w-3.5 h-3.5" />
      Translate
    </button>
  );
}
