import apiClient from './client';
import type { TreeData } from '../types/models';

export interface TreeParams {
  ancestor_depth?: number;
  descendant_depth?: number;
}

function getShareToken(): string | null {
  // Match the axios interceptor: URL first (initial share link), then sessionStorage
  // (persisted after in-app navigation away from the original share URL).
  return new URLSearchParams(window.location.search).get('share')
    ?? sessionStorage.getItem('share_token');
}

function injectShareToken(data: TreeData): TreeData {
  const shareToken = getShareToken();
  if (!shareToken) return data;
  return {
    ...data,
    nodes: data.nodes.map((n) => ({
      ...n,
      photo_url: n.photo_url ? `${n.photo_url}?share=${shareToken}` : n.photo_url,
      photos: n.photos?.map((p) => ({ ...p, url: `${p.url}?share=${shareToken}` })),
    })),
  };
}

export const treeApi = {
  getTree: async (individualId: number, params: TreeParams = {}): Promise<TreeData> => {
    const response = await apiClient.get<TreeData>(
      `/individuals/${individualId}/tree`,
      { params },
    );
    return injectShareToken(response.data);
  },

  getFullTree: async (): Promise<TreeData> => {
    const response = await apiClient.get<TreeData>('/tree/full');
    return injectShareToken(response.data);
  },
};
