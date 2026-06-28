import { useCallback, useMemo, useState } from 'react';
import type { TreeNode } from '../types/models';
import { buildPrivacyRequestHref } from '../components/layout/PrivacyLinks';

/**
 * Tree selection mode for the privacy-request convenience flow
 * (PRIVACY_DESIGN.md 3.9). A viewer (or owner) toggles "select people" mode,
 * multi-checks individuals on the tree, then jumps to a pre-filled
 * /privacy/request form for those people.
 *
 * Lives in one hook so TreePage and TreeOverviewPage share the same selection
 * state and CTA href logic rather than each maintaining its own (CLAUDE.md
 * no-duplication rule). Selection is keyed on the numeric node id (what the
 * tree click handlers and React Flow speak); the GEDCOM-id mapping needed for
 * the URL happens only when the href is built.
 */
export interface TreeSelection {
  selectMode: boolean;
  toggleSelectMode: () => void;
  exitSelectMode: () => void;
  selectedIds: Set<number>;
  selectedCount: number;
  toggleSelected: (id: number) => void;
  /**
   * The /privacy/request href for the current selection, mapping the selected
   * numeric ids to their GEDCOM ids via `nodes`. Nodes without a gedcom_id are
   * skipped (defensive -- every real node has one); if none map, the href
   * carries just the owner and request_type.
   */
  buildHref: (ownerId: string, nodes: TreeNode[]) => string;
}

export function useTreeSelection(): TreeSelection {
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const exitSelectMode = useCallback(() => {
    setSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  // Entering keeps any prior selection; exiting clears it (a stale checkmark
  // left from a previous session would be confusing on re-entry).
  const toggleSelectMode = useCallback(() => {
    setSelectMode((on) => {
      if (on) setSelectedIds(new Set());
      return !on;
    });
  }, []);

  const toggleSelected = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const buildHref = useCallback(
    (ownerId: string, nodes: TreeNode[]) => {
      const byId = new Map(nodes.map((n) => [n.id, n.gedcom_id]));
      const gedcomIds = [...selectedIds]
        .map((id) => byId.get(id))
        .filter((g): g is string => !!g);
      return buildPrivacyRequestHref({
        ownerId: ownerId || undefined,
        individualGedcomIds: gedcomIds,
      });
    },
    [selectedIds],
  );

  return useMemo(
    () => ({
      selectMode,
      toggleSelectMode,
      exitSelectMode,
      selectedIds,
      selectedCount: selectedIds.size,
      toggleSelected,
      buildHref,
    }),
    [selectMode, toggleSelectMode, exitSelectMode, selectedIds, toggleSelected, buildHref],
  );
}
