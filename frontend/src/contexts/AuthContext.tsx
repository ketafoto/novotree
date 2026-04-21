import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi } from '../api/auth';
import type { Editor } from '../types/models';
import { isDevMode } from '../config/appMode';

interface AuthContextType {
  editor: Editor | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isOwner: boolean;
  isContributor: boolean;
  isViewer: boolean;              // share-token anonymous access
  shareToken: string | null;      // detected from URL ?share=...
  viewerOwnerId: string | null;   // owner_id resolved from share token
  login: (editor_id: string, password: string, owner_id?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/** Detect share token from URL query param (?share=...) */
function detectShareToken(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('share');
}

/** Persist share token in sessionStorage so it survives navigation within the same tab */
function getPersistedShareToken(): string | null {
  const fromUrl = detectShareToken();
  if (fromUrl) {
    sessionStorage.setItem('share_token', fromUrl);
    return fromUrl;
  }
  return sessionStorage.getItem('share_token');
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [editor, setEditor] = useState<Editor | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [viewerOwnerId, setViewerOwnerId] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    try {
      const data = await authApi.me();
      setEditor(data);
    } catch {
      setEditor(null);
    }
  }, []);

  useEffect(() => {
    const token = getPersistedShareToken();
    setShareToken(token);

    if (isDevMode) {
      // Dev bypass: auto-fetch identity (backend returns dev owner)
      fetchMe().finally(() => setIsLoading(false));
      return;
    }

    if (token) {
      // Share token viewer — resolve owner_id from the token
      authApi.getShareInfo(token)
        .then((info) => setViewerOwnerId(info.owner_id))
        .catch(() => {/* token may be expired; viewer access will fail naturally */})
        .finally(() => setIsLoading(false));
      return;
    }

    // Try to restore session from access token cookie
    fetchMe().finally(() => setIsLoading(false));
  }, [fetchMe]);

  // Poll /auth/me every 30 s so a frozen/deleted contributor is redirected to login
  // without needing a manual page refresh. Skip in dev mode and for share-token viewers.
  useEffect(() => {
    if (isDevMode || !editor) return;

    const checkSession = async () => {
      try {
        await authApi.me();
      } catch (err: unknown) {
        const httpStatus = (err as { response?: { status?: number } })?.response?.status;
        if (httpStatus === 401) {
          setEditor(null);
          window.location.href = '/novotree/login';
        }
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') checkSession();
    };

    const interval = setInterval(checkSession, 30_000);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [editor]);

  const login = useCallback(async (editor_id: string, password: string, owner_id?: string) => {
    const res = await authApi.login({ editor_id, password, owner_id });
    setEditor(res.editor);
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setEditor(null);
    sessionStorage.removeItem('share_token');
    setShareToken(null);
    setViewerOwnerId(null);
    window.location.href = '/novotree/login';
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await authApi.refresh();
      setEditor(res.editor);
    } catch {
      setEditor(null);
    }
  }, []);

  const isAuthenticated = isDevMode || editor !== null;
  const isViewer = !editor && shareToken !== null;
  const isOwner = editor?.role === 'owner';
  const isContributor = editor?.role === 'contributor';

  return (
    <AuthContext.Provider value={{
      editor,
      isLoading,
      isAuthenticated,
      isOwner: isOwner ?? false,
      isContributor: isContributor ?? false,
      isViewer,
      shareToken,
      viewerOwnerId,
      login,
      logout,
      refresh,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
