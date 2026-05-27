import apiClient from './client';
import type { Individual, IndividualCreate, IndividualUpdate } from '../types/models';

export interface ListParams {
  skip?: number;
  limit?: number;
}

export const individualsApi = {
  /**
   * List all individuals with pagination
   */
  list: async (params: ListParams = {}): Promise<Individual[]> => {
    const response = await apiClient.get<Individual[]>('/individuals', { params });
    return response.data;
  },

  /**
   * Get a single individual by ID
   */
  get: async (id: number): Promise<Individual> => {
    const response = await apiClient.get<Individual>(`/individuals/${id}`);
    return response.data;
  },

  /**
   * Create a new individual
   */
  create: async (data: IndividualCreate): Promise<Individual> => {
    const response = await apiClient.post<Individual>('/individuals', data);
    return response.data;
  },

  /**
   * Update an individual
   */
  update: async (id: number, data: IndividualUpdate): Promise<Individual> => {
    const response = await apiClient.put<Individual>(`/individuals/${id}`, data);
    return response.data;
  },

  /**
   * Delete an individual
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/individuals/${id}`);
  },

  /**
   * Delete all individuals and related families, events, media (owner-only).
   */
  deleteAll: async (): Promise<{ deleted: { individuals: number; families: number; events: number; media: number } }> => {
    const response = await apiClient.delete('/individuals/all');
    return response.data;
  },

  /**
   * Right-of-access export for one individual (privacy §2.6 / M-09). Owner-only.
   * Returns the raw response so the caller can read Content-Disposition before
   * passing the blob to saveBlob().
   */
  dataExport: async (id: number) => {
    return apiClient.get(`/individuals/${id}/data-export`, { responseType: 'blob' });
  },
};

