import { useAuth } from '../contexts/AuthContext';
import { usePrivacyConfig } from './usePrivacyConfig';

/**
 * Whether to offer the "contribute to this tree" affordance to the current user.
 *
 * Two gates, both required:
 *   1. The user is a share-token viewer with a resolved owner (the only
 *      population the contribute CTA targets — owners/contributors already
 *      have accounts).
 *   2. The deployment allows contributor self-signup
 *      (PrivacySettings.allow_contributor_signup — off in the default
 *      'private' mode). Mirrors the backend 403 gate on
 *      POST /auth/contributor-signup (PRIVACY_DESIGN.md §3.1).
 *
 * Conservative: returns false until the privacy config has loaded AND the flag
 * is true, so the affordance never flashes in the common disabled case.
 *
 * Used by both tree views (TreePage, TreeOverviewPage) so the gate lives in
 * one place.
 */
export function useCanContribute(): boolean {
  const { isViewer, editor, viewerOwnerId } = useAuth();
  const { config } = usePrivacyConfig();

  const ownerOwnerId = editor?.owner_id ?? viewerOwnerId ?? '';
  return isViewer && !!ownerOwnerId && config?.allow_contributor_signup === true;
}
