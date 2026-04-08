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
  isViewer: boolean;         // share-token anonymous access
  shareToken: string | null; // detected from URL ?share=...
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
      // Share token viewer — no auth call needed
      setIsLoading(false);
      return;
    }

    // Try to restore session from access token cookie
    fetchMe().finally(() => setIsLoading(false));
  }, [fetchMe]);

  const login = useCallback(async (editor_id: string, password: string, owner_id?: string) => {
    const res = await authApi.login({ editor_id, password, owner_id });
    setEditor(res.editor);
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setEditor(null);
    sessionStorage.removeItem('share_token');
    setShareToken(null);
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
