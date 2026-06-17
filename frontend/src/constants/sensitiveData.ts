// Shared copy and helpers for special-category (GDPR Art. 9) handling.
//
// Single source of truth for the "what counts as sensitive" explanation reused
// across the show-sensitive toggle, the mark-sensitive checkboxes, the notes
// editor, and the share-link modal. Wording is reconciled with
// docs/legal/privacy.md ("Sensitive fields" row) and PRIVACY_ANALYSIS.md M-05 /
// C-02 — do not reword in one place only. See PRIVACY_DESIGN.md 3.7.

/** One-line explanation of what is treated as special-category data. */
export const SENSITIVE_DATA_EXPLANATION =
  'Religion, ethnicity, health, and cause of death are treated as special-category ' +
  'data (GDPR Art. 9). Mark such records sensitive so they stay hidden behind the ' +
  '"show sensitive" toggle and are excluded from share links by default.';

/**
 * Explanation of how minors (GDPR Art. 8) are handled. The threshold is
 * interpolated from PrivacyConfig.child_age_threshold_years so the copy never
 * hardcodes the age. Reconciled with docs/legal/privacy.md ("Children's data")
 * and PRIVACY_ANALYSIS.md M-06 -- do not reword in one place only.
 * See PRIVACY_DESIGN.md 3.8.
 */
export function minorDataExplanation(thresholdYears: number): string {
  return (
    `Anyone under ${thresholdYears} is treated as a minor (GDPR Art. 8). ` +
    'Uploading their photos needs your confirmation that you have parental consent, ' +
    'and minors are excluded from share links unless you opt in per link.'
  );
}

/**
 * GEDCOM event codes that inherently reveal religion and so are always treated
 * as sensitive, regardless of any manual flag. Mirrors the backend
 * database.models.SENSITIVE_EVENT_CODES; the server is the real gate for
 * viewers, this client copy only drives the Owner's local show/hide.
 */
export const SENSITIVE_EVENT_CODES = new Set<string>([
  'BAPM', 'BARM', 'BASM', 'BLES', 'CHR', 'CHRA', 'CONF', 'FCOM', 'ORDN',
]);

/** True if an event is special-category: an inherently-religious type OR manually flagged. */
export function eventIsSensitive(event: { event_type_code: string; is_sensitive?: boolean }): boolean {
  return !!event.is_sensitive || SENSITIVE_EVENT_CODES.has(event.event_type_code);
}

/**
 * Client-side mirror of the backend database.models.individual_is_minor: a
 * living person born within thresholdYears of today. Drives the parental-consent
 * upload gate hint only; the server is the real gate. Like the backend, only an
 * exact birth_date counts -- an approximate-only date is treated as not a known
 * minor. A node already carrying is_minor from the backend should prefer that.
 */
export function individualIsMinor(
  person: { birth_date?: string; death_date?: string },
  thresholdYears: number,
): boolean {
  if (!person.birth_date || person.death_date) return false;
  const born = new Date(person.birth_date);
  if (Number.isNaN(born.getTime())) return false;
  const thresholdBirthday = new Date(born);
  thresholdBirthday.setFullYear(born.getFullYear() + thresholdYears);
  return new Date() < thresholdBirthday;
}

interface FilterableTreeEvent {
  is_sensitive?: boolean;
}

interface FilterableTreeNode {
  id: number;
  is_sensitive?: boolean;
  notes?: string;
  notes_sensitive?: boolean;
  events: FilterableTreeEvent[];
}

interface FilterableTreeData {
  nodes: FilterableTreeNode[];
  edges: Array<{ parent_id: number; child_id: number }>;
  couples: Array<{ partner_ids: number[] }>;
}

/**
 * Owner-side cosmetic filter for a tree payload, applied when the Owner's
 * "show sensitive" toggle is off:
 *   - whole-person `is_sensitive` individuals are dropped entirely (except the
 *     focus person, who is kept so navigating to their own tree is not blank),
 *     and any edge/couple referencing a dropped person is pruned too, so React
 *     Flow never sees a dangling edge endpoint;
 *   - on the remaining nodes, `is_sensitive` events are dropped and
 *     `notes_sensitive` notes are blanked.
 *
 * Presentation guard only — viewers are already filtered server-side per share
 * token (the backend never sends them sensitive bytes). Mirrors the backend's
 * _filter_excluded_individuals. See PRIVACY_DESIGN.md 3.7.
 */
export function hideSensitiveFromTree<T extends FilterableTreeData>(
  data: T,
  focusId?: number | null,
): T {
  const excluded = new Set<number>();
  for (const n of data.nodes) {
    if (n.is_sensitive && n.id !== focusId) excluded.add(n.id);
  }

  const nodes = data.nodes
    .filter((n) => !excluded.has(n.id))
    .map((n) => ({
      ...n,
      notes: n.notes_sensitive ? undefined : n.notes,
      events: n.events.filter((e) => !e.is_sensitive),
    }));

  if (excluded.size === 0) {
    return { ...data, nodes };
  }

  return {
    ...data,
    nodes,
    edges: data.edges.filter(
      (e) => !excluded.has(e.parent_id) && !excluded.has(e.child_id),
    ),
    couples: data.couples.filter(
      (c) => !c.partner_ids.some((id) => excluded.has(id)),
    ),
  };
}
