import apiClient from './client';

import type { PrivacyRequestType } from './privacy_requests';

/**
 * Public subset of backend PrivacySettings.
 * See docs/legal/PRIVACY_DESIGN.md §2.1 + §6.
 */
export interface PrivacyConfig {
  deployment_mode: 'private' | 'contributors' | 'public';
  allow_owner_signup: boolean;
  owner_signup_requires_approval: boolean;
  allow_contributor_signup: boolean;

  privacy_request_sla_days: number;
  child_age_threshold_years: number;

  backup_retention_days: number;
  access_log_retention_days: number;
  error_log_retention_days: number;
  privacy_request_retention_months: number;

  tos_version: string;
  privacy_policy_version: string;
  cookie_notice_version: string;

  controller_name: string;
  privacy_contact_email: string;
  hosting_region: string;

  analytics_enabled: boolean;

  /**
   * TEST-ONLY. When true, the Owner's privacy-requests queue page renders
   * timestamp-override inputs so the SLA reminder / escalation /
   * retention sweep paths can be exercised on a test VM without
   * waiting 30 days. Must remain false in production — see
   * backend PrivacySettings.test_allow_timestamp_override.
   */
  test_allow_timestamp_override: boolean;
}

export interface PrivacyRequestPayload {
  tree_owner_id: string;
  individual_id?: string;
  request_type: PrivacyRequestType;
  requester_name: string;
  requester_email: string;
  requester_phone?: string;
  message: string;
}

export interface PrivacyRequestAck {
  ok: boolean;
  id: number;
}

export interface PrivacyPolicy {
  version: string;
  content_markdown: string;
}

export const privacyApi = {
  getConfig: async (): Promise<PrivacyConfig> => {
    const res = await apiClient.get<PrivacyConfig>('/privacy/config');
    return res.data;
  },
  submitPrivacyRequest: async (payload: PrivacyRequestPayload): Promise<PrivacyRequestAck> => {
    const res = await apiClient.post<PrivacyRequestAck>('/privacy/request', payload);
    return res.data;
  },
  getPolicy: async (): Promise<PrivacyPolicy> => {
    const res = await apiClient.get<PrivacyPolicy>('/privacy/policy');
    return res.data;
  },
};
