import React, { createContext, useCallback, useContext, useState } from 'react';

/**
 * Whether special-category (GDPR Art. 9) data is revealed on screen, shared by
 * every surface that shows it: both tree views and the individual detail page.
 *
 * Scope is one browser session, which is what PRIVACY_DESIGN.md 3.7 specifies.
 * It previously lived in three separate `useState(false)` calls, one per page;
 * because those pages are lazily mounted and unmount on navigation, the toggle
 * reset on every navigation and the three surfaces disagreed with each other -
 * stricter than the design says, and the reason revealing sensitive data felt
 * like a per-visit chore.
 *
 * Backed by sessionStorage so it also survives a reload (the local app reloads
 * itself after switching tree or data folder) while still starting hidden in a
 * fresh session. Deliberately NOT localStorage: 3.7 promises the choice is not
 * persisted, and a new session must start from hidden.
 *
 * Still UI-only - a shoulder-surfing guard, never sent to the backend. Viewers
 * are filtered server-side per share token and never get the control at all.
 */

const STORAGE_KEY = 'novotree.showSensitive';

interface SensitiveViewContextType {
  showSensitive: boolean;
  setShowSensitive: (next: boolean) => void;
}

const SensitiveViewContext = createContext<SensitiveViewContextType | undefined>(undefined);

function readStored(): boolean {
  // Storage can throw (privacy modes, disabled cookies). Hidden is both the
  // documented default and the safe answer, so failure degrades to it.
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function SensitiveViewProvider({ children }: { children: React.ReactNode }) {
  const [showSensitive, setShown] = useState(readStored);

  const setShowSensitive = useCallback((next: boolean) => {
    setShown(next);
    try {
      if (next) {
        sessionStorage.setItem(STORAGE_KEY, '1');
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Non-fatal: the toggle still works for this mount, it just will not
      // survive a reload.
    }
  }, []);

  return (
    <SensitiveViewContext.Provider value={{ showSensitive, setShowSensitive }}>
      {children}
    </SensitiveViewContext.Provider>
  );
}

export function useSensitiveView() {
  const ctx = useContext(SensitiveViewContext);
  if (!ctx) throw new Error('useSensitiveView must be used within SensitiveViewProvider');
  return ctx;
}
