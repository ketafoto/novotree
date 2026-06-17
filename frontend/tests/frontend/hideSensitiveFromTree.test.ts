/**
 * Unit tests for hideSensitiveFromTree — the Owner-side cosmetic filter behind
 * the tree "show sensitive" toggle (PRIVACY_DESIGN.md 3.7).
 *
 * Regression context: an earlier version stripped only events/notes and left
 * whole-`is_sensitive` people in the node list. When such a person was dropped
 * elsewhere, their edges/couples dangled and React Flow rendered inconsistently
 * (a node could vanish and not return on toggle). The fix makes exclusion
 * atomic: drop the person AND every edge/couple referencing them, while always
 * keeping the focus person so a per-individual tree never goes blank.
 */

import { describe, it, expect } from 'vitest';
import { hideSensitiveFromTree } from '../../src/constants/sensitiveData';

interface TestTree {
  focus_id: number | null;
  nodes: Array<{
    id: number;
    is_sensitive?: boolean;
    notes?: string;
    notes_sensitive?: boolean;
    events: Array<{ event_type: string; is_sensitive?: boolean }>;
  }>;
  edges: Array<{ parent_id: number; child_id: number; family_id: number }>;
  couples: Array<{ family_id: number; partner_ids: number[] }>;
}

function sample(): TestTree {
  return {
    focus_id: 1,
    nodes: [
      {
        id: 1,
        notes: 'Catholic',
        notes_sensitive: true,
        events: [
          { event_type: 'Birth', is_sensitive: false },
          { event_type: 'Baptism', is_sensitive: true },
        ],
      },
      { id: 2, events: [] },                       // normal relative
      { id: 3, is_sensitive: true, events: [] },   // whole-person sensitive relative
    ],
    edges: [
      { parent_id: 2, child_id: 1, family_id: 10 },
      { parent_id: 3, child_id: 1, family_id: 11 }, // references sensitive person 3
    ],
    couples: [
      { family_id: 10, partner_ids: [2, 4] },
      { family_id: 11, partner_ids: [3, 5] },       // references sensitive person 3
    ],
  };
}

describe('hideSensitiveFromTree', () => {
  it('drops sensitive events and blanks sensitive notes on kept nodes', () => {
    const out = hideSensitiveFromTree(sample(), 1);
    const focus = out.nodes.find((n) => n.id === 1)!;
    expect(focus.events.map((e) => e.event_type)).toEqual(['Birth']); // Baptism removed
    expect(focus.notes).toBeUndefined(); // sensitive notes blanked
  });

  it('removes a whole-person-sensitive relative and prunes their edges and couples', () => {
    const out = hideSensitiveFromTree(sample(), 1);
    expect(out.nodes.find((n) => n.id === 3)).toBeUndefined();
    // No edge or couple may reference the removed person (no dangling endpoints).
    expect(out.edges.some((e) => e.parent_id === 3 || e.child_id === 3)).toBe(false);
    expect(out.couples.some((c) => c.partner_ids.includes(3))).toBe(false);
    // The unrelated edge/couple survive.
    expect(out.edges.some((e) => e.family_id === 10)).toBe(true);
    expect(out.couples.some((c) => c.family_id === 10)).toBe(true);
  });

  it('keeps the focus person even when they are sensitive (tree must not go blank)', () => {
    const tree = sample();
    tree.nodes[0].is_sensitive = true; // focus (id 1) is now sensitive
    const out = hideSensitiveFromTree(tree, 1);
    expect(out.nodes.find((n) => n.id === 1)).toBeDefined();
  });

  it('drops every sensitive person when there is no focus (full tree)', () => {
    const out = hideSensitiveFromTree(sample(), null);
    // Person 3 is sensitive and there is no focus to protect, so it is removed;
    // person 1 (focus in the per-tree case) is NOT sensitive here, so it stays.
    expect(out.nodes.find((n) => n.id === 3)).toBeUndefined();
    expect(out.nodes.find((n) => n.id === 1)).toBeDefined();
  });

  it('leaves edges/couples untouched when nothing is whole-person sensitive', () => {
    const tree = sample();
    tree.nodes[2].is_sensitive = false; // person 3 no longer sensitive
    const out = hideSensitiveFromTree(tree, 1);
    expect(out.nodes).toHaveLength(3);
    expect(out.edges).toHaveLength(2);
    expect(out.couples).toHaveLength(2);
  });
});
