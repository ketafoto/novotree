import apiClient from './client';
import type {
  Editor,
  AuthResponse,
  LoginRequest,
  OwnerSignupRequest,
  SignupResponse,
  PublicConfig,
  SetPasswordRequest,
  ChangePasswordRequest,
  ShareToken,
  ShareTokenCreate,
  Contributor,
  ContributorSignupRequest,
  OwnerInfo,
} from '../types/models';

export const authApi = {
  me: async (): Promise<Editor> => {
    const res = await apiClient.get<Editor>('/auth/me');
    return res.data;
  },

  login: async (body: LoginRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/login', body);
    return res.data;
  },

  ownerSignup: async (body: OwnerSignupRequest): Promise<SignupResponse> => {
    const res = await apiClient.post<SignupResponse>('/auth/owner-signup', body);
    return res.data;
  },

  verifyOwnerEmail: async (token: string): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/verify-owner-email', null, { params: { token } });
    return res.data;
  },

  resendOwnerVerification: async (email: string): Promise<SignupResponse> => {
    const res = await apiClient.post<SignupResponse>('/auth/resend-owner-verification', null, { params: { email } });
    return res.data;
  },

  getPublicConfig: async (): Promise<PublicConfig> => {
    const res = await apiClient.get<PublicConfig>('/auth/public-config');
    return res.data;
  },

  getShareInfo: async (share: string): Promise<{ owner_id: string; display_name: string }> => {
    const res = await apiClient.get('/auth/share-info', { params: { share } });
    return res.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  refresh: async (): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/refresh');
    return res.data;
  },

  changePassword: async (body: ChangePasswordRequest): Promise<void> => {
    await apiClient.post('/auth/change-password', body);
  },

  updateProfile: async (display_name: string): Promise<void> => {
    await apiClient.patch('/auth/profile', { display_name });
  },

  setPassword: async (body: SetPasswordRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/set-password', body);
    return res.data;
  },

  contributorSignup: async (body: ContributorSignupRequest): Promise<SignupResponse> => {
    const res = await apiClient.post<SignupResponse>('/auth/contributor-signup', body);
    return res.data;
  },

  verifyContributorEmail: async (token: string): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/verify-contributor-email', null, { params: { token } });
    return res.data;
  },

  resendContributorVerification: async (email: string): Promise<SignupResponse> => {
    const res = await apiClient.post<SignupResponse>('/auth/resend-contributor-verification', null, { params: { email } });
    return res.data;
  },
};

export const usersApi = {
  // Share tokens
  listShareTokens: async (): Promise<ShareToken[]> => {
    const res = await apiClient.get<ShareToken[]>('/users/share-tokens');
    return res.data;
  },

  createShareToken: async (body: ShareTokenCreate): Promise<ShareToken> => {
    const res = await apiClient.post<ShareToken>('/users/share-tokens', body);
    return res.data;
  },

  revokeShareToken: async (id: number): Promise<void> => {
    await apiClient.delete(`/users/share-tokens/${id}`);
  },

  // Contributors
  listContributors: async (): Promise<Contributor[]> => {
    const res = await apiClient.get<Contributor[]>('/users/contributors');
    return res.data;
  },

  setContributorActive: async (editor_id: string, is_active: boolean): Promise<void> => {
    await apiClient.post('/users/contributors/set-active', { editor_id, is_active });
  },

  resetContributorPassword: async (editor_id: string): Promise<{ link: string; emailed: boolean }> => {
    const res = await apiClient.post<{ link: string; emailed: boolean }>(
      '/users/contributors/reset-password',
      { editor_id }
    );
    return res.data;
  },

  // Owner info (public)
  getOwnerInfo: async (owner_id: string): Promise<OwnerInfo> => {
    const res = await apiClient.get<OwnerInfo>('/users/owner-info', { params: { owner_id } });
    return res.data;
  },

  // Contributor management
  activateContributor: async (editor_id: string): Promise<void> => {
    await apiClient.post(`/users/contributors/${editor_id}/activate`);
  },

  deleteContributor: async (editor_id: string): Promise<void> => {
    await apiClient.delete(`/users/contributors/${editor_id}`);
  },
};
