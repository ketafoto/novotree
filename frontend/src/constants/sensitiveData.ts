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
