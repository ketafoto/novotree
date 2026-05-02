/**
 * Reject any non-Latin letter. Allows Latin (incl. accented), digits,
 * whitespace, punctuation, symbols. Rejects Cyrillic, Greek, Arabic, CJK, …
 *
 * Notes are exempt — they're deliberately bilingual and get a Translate
 * button instead. See utils/translate.ts.
 *
 * Two forms:
 *  - latinOnlyRule  → spread into register('name', { ...latinOnlyRule })
 *  - latinOnlyValidator → use as a zod .refine() predicate
 */

const NON_LATIN_LETTER = /[^\p{Script=Latin}\P{L}]/u;
const LATIN_ONLY_MESSAGE = 'Use Latin letters only (transliterate non-Latin names)';

export const isLatinOnly = (value: string | undefined) =>
  !value || !NON_LATIN_LETTER.test(value);

export const latinOnlyRule = {
  validate: (value: string | undefined) =>
    isLatinOnly(value) || LATIN_ONLY_MESSAGE,
};

export const latinOnlyRefine = {
  check: isLatinOnly,
  message: LATIN_ONLY_MESSAGE,
};
