import apiClient from './client';

export interface LocalAppInfo {
  data_dir: string;
  config_file: string;
  log_file: string;
}

export interface PickDataDirResponse {
  path: string | null;        // null = user cancelled the dialog
}

export interface ChangeDataDirResponse {
  ok: boolean;
  moved_to: string;
  items_moved: number;
}

/**
 * Local-app API. The backend returns 404 in any mode other than `local`,
 * so callers must guard with `isLocalApp` from `config/appMode.ts`.
 */
export const localApi = {
  info: async (): Promise<LocalAppInfo> => {
    const res = await apiClient.get<LocalAppInfo>('/local/info');
    return res.data;
  },

  /** Open a native folder-picker dialog. Returns null if the user cancelled. */
  pickDataDir: async (): Promise<PickDataDirResponse> => {
    const res = await apiClient.post<PickDataDirResponse>('/local/pick-data-dir');
    return res.data;
  },

  /**
   * Move all data + media to `newPath`, persist the choice in config.json,
   * and rebind DATASETS_DIR + system DB at runtime. No process restart;
   * the caller should `window.location.reload()` so React Query starts fresh
   * against the new location.
   */
  changeDataDir: async (newPath: string): Promise<ChangeDataDirResponse> => {
    const res = await apiClient.post<ChangeDataDirResponse>('/local/change-data-dir', {
      new_path: newPath,
    });
    return res.data;
  },

  /** Open Windows Explorer at the given path (file → selected; dir → opened). */
  openInExplorer: async (path: string): Promise<void> => {
    await apiClient.post('/local/open-in-explorer', { path });
  },

  /** Open `path` with the OS-registered default program (file → its
   *  default editor, dir → File Explorer). Same effect as a double-click. */
  openWithDefault: async (path: string): Promise<void> => {
    await apiClient.post('/local/open-with-default', { path });
  },
};
