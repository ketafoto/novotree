import apiClient from './client';

/**
 * Owner-scoped privacy-request triage (removal / access / correction).
 *
 * The public submission endpoint (POST /privacy/request) lives in
 * api/privacy.ts because it is reachable without auth and is paired with the
 * legal /privacy/config endpoint. The Owner-scoped triage endpoints in this
 * file all require an authenticated Owner session.
 *
 * See backend/api/privacy_requests.py and docs/legal/PRIVACY_DESIGN.md §2.7.
 */

export type PrivacyRequestType = 'removal' | 'access' | 'correction';

export type PrivacyRequestStatus = 'open' | 'acknowledged' | 'resolved' | 'escalated';

export interface PrivacyRequestRow {
  id: number;
  tree_owner_id: string;
  individual_id: string | null;
  request_type: PrivacyRequestType;
  requester_name: string;
  requester_email: string;
  requester_phone: string | null;
  message: string;
  status: PrivacyRequestStatus;
  created_at: string;
  resolved_at: string | null;
  reminder_sent_at: string | null;
  escalated_at: string | null;
}

const BASE_PATH = '/privacy/requests';

export const privacyRequestsApi = {
  list: async (includeResolved: boolean): Promise<PrivacyRequestRow[]> => {
    const res = await apiClient.get<PrivacyRequestRow[]>(BASE_PATH, {
      params: { include_resolved: includeResolved },
    });
    return res.data;
  },
  resolve: async (id: number): Promise<PrivacyRequestRow> => {
    const res = await apiClient.patch<PrivacyRequestRow>(`${BASE_PATH}/${id}`, {
      status: 'resolved',
    });
    return res.data;
  },
  remove: async (id: number): Promise<void> => {
    await apiClient.delete(`${BASE_PATH}/${id}`);
  },

  /**
   * TEST-ONLY. Shift created_at / resolved_at on a privacy-request row so
   * the SLA sweeper paths can be exercised without waiting weeks. The
   * backend returns 403 unless PRIVACY_ALLOW_TIMESTAMP_OVERRIDE=true is
   * set in its environment. Symbols are test_-prefixed throughout the
   * codepath; this method MUST stay out of any production UX surface.
   */
  test_overrideTimestamps: async (
    id: number,
    payload: { test_created_at?: string; test_resolved_at?: string },
  ): Promise<PrivacyRequestRow> => {
    const res = await apiClient.patch<PrivacyRequestRow>(
      `${BASE_PATH}/${id}/test_override`,
      payload,
    );
    return res.data;
  },
};
