import apiClient from './client';

/**
 * Public subset of backend PrivacySettings.
 * See docs/PRIVACY_DESIGN.md §2.1 + §6.
 */
export interface PrivacyConfig {
  deployment_mode: 'A' | 'B' | 'C';
  allow_owner_signup: boolean;
  owner_signup_requires_approval: boolean;
  allow_contributor_signup: boolean;

  takedown_sla_days: number;
  child_age_threshold_years: number;

  backup_retention_days: number;
  access_log_retention_days: number;
  error_log_retention_days: number;
  takedown_request_retention_months: number;

  tos_version: string;
  privacy_policy_version: string;
  cookie_notice_version: string;

  controller_name: string;
  privacy_contact_email: string;
  hosting_region: string;

  analytics_enabled: boolean;
}

export interface TakedownRequestPayload {
  tree_owner_id: string;
  individual_id?: string;
  requester_name: string;
  requester_email: string;
  requester_phone?: string;
  message: string;
}

export interface TakedownRequestAck {
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
  submitTakedown: async (payload: TakedownRequestPayload): Promise<TakedownRequestAck> => {
    const res = await apiClient.post<TakedownRequestAck>('/privacy/takedown', payload);
    return res.data;
  },
  getPolicy: async (): Promise<PrivacyPolicy> => {
    const res = await apiClient.get<PrivacyPolicy>('/privacy/policy');
    return res.data;
  },
};
