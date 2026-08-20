import apiClient from './client';

export interface LocalAppInfo {
  data_dir: string;
  owner_id: string;            // active tree; its files live at <data_dir>/<owner_id>/
  editor_id: string;           // stamped into created_by on every row you add
  display_name: string;        // shown as "Added by ..."
  config_file: string;
  log_file: string;
}

export interface TreeInfo {
  owner_id: string;
  is_active: boolean;
  individuals: number | null;  // null = the tree's DB is missing or unreadable
  size_bytes: number;
  modified_at: string | null;  // ISO-8601 UTC
  share_links: number;         // share tokens pointing at this tree
}

export interface TreeListResponse {
  active: string;
  trees: TreeInfo[];
}

export interface TreeActionResponse {
  ok: boolean;
  active: string;
}

export interface DeleteTreeResponse {
  ok: boolean;
  deleted: string;
  remaining: number;
  purged: Record<string, number>;  // system.sqlite table -> rows removed
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

  /** Every tree under the current data folder. */
  listTrees: async (): Promise<TreeListResponse> => {
    const res = await apiClient.get<TreeListResponse>('/local/trees');
    return res.data;
  },

  /**
   * Open a different tree in the same data folder. Nothing moves on disk, but
   * the caller should still `window.location.reload()` so React Query drops
   * rows cached from the previous tree.
   */
  switchTree: async (ownerId: string): Promise<TreeActionResponse> => {
    const res = await apiClient.post<TreeActionResponse>('/local/switch-tree', {
      owner_id: ownerId,
    });
    return res.data;
  },

  /** Create an empty tree under the current data folder and switch to it. */
  createTree: async (ownerId: string): Promise<TreeActionResponse> => {
    const res = await apiClient.post<TreeActionResponse>('/local/create-tree', {
      owner_id: ownerId,
    });
    return res.data;
  },

  /**
   * Permanently delete a tree and its media. Irreversible, and refused for
   * the tree that is currently open.
   */
  deleteTree: async (ownerId: string): Promise<DeleteTreeResponse> => {
    const res = await apiClient.post<DeleteTreeResponse>('/local/delete-tree', {
      owner_id: ownerId,
    });
    return res.data;
  },

  /**
   * Set who is recorded as adding records. Applies to new rows only - existing
   * `created_by` values are deliberately left alone.
   */
  setIdentity: async (editorId: string, displayName: string): Promise<LocalAppInfo> => {
    const res = await apiClient.post<LocalAppInfo>('/local/identity', {
      editor_id: editorId,
      display_name: displayName,
    });
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
