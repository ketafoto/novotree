import apiClient from './client';

/**
 * Owner-scoped takedown request triage.
 *
 * The public submission endpoint (POST /privacy/takedown) lives in
 * api/privacy.ts because it is reachable without auth and is paired with the
 * legal /privacy/config endpoint. The Owner-scoped triage endpoints in this
 * file all require an authenticated Owner session.
 *
 * See backend/api/takedown.py and docs/PRIVACY_DESIGN.md §2.2.
 */

export type TakedownStatus = 'open' | 'acknowledged' | 'resolved' | 'escalated';

export interface TakedownRow {
  id: number;
  tree_owner_id: string;
  individual_id: string | null;
  requester_name: string;
  requester_email: string;
  requester_phone: string | null;
  message: string;
  status: TakedownStatus;
  created_at: string;
  resolved_at: string | null;
  reminder_sent_at: string | null;
  escalated_at: string | null;
}

export const takedownApi = {
  list: async (includeResolved: boolean): Promise<TakedownRow[]> => {
    const res = await apiClient.get<TakedownRow[]>('/takedown', {
      params: { include_resolved: includeResolved },
    });
    return res.data;
  },
  resolve: async (id: number): Promise<TakedownRow> => {
    const res = await apiClient.patch<TakedownRow>(`/takedown/${id}`, {
      status: 'resolved',
    });
    return res.data;
  },
  remove: async (id: number): Promise<void> => {
    await apiClient.delete(`/takedown/${id}`);
  },
};
