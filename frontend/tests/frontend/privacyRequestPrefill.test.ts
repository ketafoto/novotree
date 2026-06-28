/**
 * Unit tests for parsePrefillParams -- the query-param parser behind the
 * TreeView selection-mode prefill (PRIVACY_DESIGN.md 3.9). The tree CTA
 * navigates to /privacy/request?owner=...&individual_ids=I1,I2&request_type=removal;
 * this helper turns those params into the message text + radio default the form
 * seeds. Pure helper, so no rendering needed (mirrors hideSensitiveFromTree.test.ts).
 */

import { describe, it, expect } from 'vitest';
import {
  buildPrefillMessage,
  isDefaultMessage,
  parsePrefillParams,
} from '../../src/pages/legal/PrivacyRequestPage';

describe('parsePrefillParams', () => {
  it('parses individual_ids + request_type and builds a message naming the ids', () => {
    const out = parsePrefillParams('?individual_ids=I1,I2&request_type=removal&owner=foo');
    expect(out.individualIds).toEqual(['I1', 'I2']);
    expect(out.requestType).toBe('removal');
    expect(out.messagePrefill).toContain('I1, I2');
    expect(out.messagePrefill).toMatch(/remove/i);
  });

  it('words the prefilled message for the request type (access / correction)', () => {
    const access = parsePrefillParams('?individual_ids=I1&request_type=access');
    expect(access.messagePrefill).toMatch(/copy/i);
    expect(access.messagePrefill).not.toMatch(/remove/i);

    const correction = parsePrefillParams('?individual_ids=I1&request_type=correction');
    expect(correction.messagePrefill).toMatch(/correct/i);
    expect(correction.messagePrefill).not.toMatch(/remove/i);
  });

  it('defaults to removal wording when ids arrive without a request_type', () => {
    const out = parsePrefillParams('?individual_ids=I1');
    expect(out.requestType).toBeUndefined();
    expect(out.messagePrefill).toMatch(/remove/i);
  });

  it('returns no ids and no message prefill when individual_ids is absent', () => {
    const out = parsePrefillParams('?owner=foo');
    expect(out.individualIds).toEqual([]);
    expect(out.messagePrefill).toBeUndefined();
  });

  it('ignores an unknown request_type rather than crashing', () => {
    const out = parsePrefillParams('?individual_ids=I1&request_type=bogus');
    expect(out.requestType).toBeUndefined();
    // The ids still parse even when the type is dropped.
    expect(out.individualIds).toEqual(['I1']);
  });

  it('tolerates whitespace and trailing/empty commas in individual_ids', () => {
    const out = parsePrefillParams('?individual_ids=I1, , I2,');
    expect(out.individualIds).toEqual(['I1', 'I2']);
  });
});

// isDefaultMessage decides whether the radio change may re-word the message:
// only while it still holds an auto-generated default, never after the user
// has typed their own text.
describe('isDefaultMessage', () => {
  const people = 'I1, I2';

  it('treats an empty / whitespace-only message as a default (safe to re-word)', () => {
    expect(isDefaultMessage('', people)).toBe(true);
    expect(isDefaultMessage('   ', people)).toBe(true);
  });

  it('treats the generated default for ANY request type as a default', () => {
    expect(isDefaultMessage(buildPrefillMessage('removal', people), people)).toBe(true);
    expect(isDefaultMessage(buildPrefillMessage('access', people), people)).toBe(true);
    expect(isDefaultMessage(buildPrefillMessage('correction', people), people)).toBe(true);
  });

  it('treats user-edited text as NOT a default (must not be clobbered)', () => {
    expect(isDefaultMessage('My own words about I1.', people)).toBe(false);
    // A default for a different people-set is also the user's, not ours to touch.
    expect(isDefaultMessage(buildPrefillMessage('removal', 'I9'), people)).toBe(false);
  });
});
