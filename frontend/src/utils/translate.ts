/**
 * Open Google Translate in a new tab with a sensible source/target pair
 * picked from the script of the input text.
 *
 * Cyrillic-dominant text → ru → en. Latin-dominant text → en → ru.
 * If both scripts appear, fall back to Google's auto-detect.
 */

const CYRILLIC_RE = /[Ѐ-ӿ]/g;
const LATIN_RE = /[A-Za-z]/g;

const TRANSLATE_BASE = 'https://translate.google.com/';

type Script = 'cyrillic' | 'latin' | 'auto';

function detectScript(text: string): Script {
  const cyrillic = (text.match(CYRILLIC_RE) ?? []).length;
  const latin = (text.match(LATIN_RE) ?? []).length;
  if (cyrillic === 0 && latin === 0) return 'auto';
  if (cyrillic > 0 && latin > 0) return 'auto';
  return cyrillic > latin ? 'cyrillic' : 'latin';
}

export function buildTranslateUrl(text: string): string {
  const script = detectScript(text);
  const [sl, tl] =
    script === 'cyrillic' ? ['ru', 'en']
    : script === 'latin' ? ['en', 'ru']
    : ['auto', 'en'];
  const params = new URLSearchParams({ sl, tl, text });
  return `${TRANSLATE_BASE}?${params.toString()}`;
}
