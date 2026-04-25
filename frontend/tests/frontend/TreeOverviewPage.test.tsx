/**
 * Regression test for the "Wanna contribute to this tree?" button on TreeOverviewPage.
 *
 * Bug: when a viewer opens the tree via a share link (?share=<token>), the contribute
 * button never appeared.  Root cause: AuthContext.useEffect checks isDevMode first and
 * calls fetchMe() in that branch, bypassing the getShareInfo() call that sets
 * viewerOwnerId.  In the test environment VITE_NOVOTREE_APP_MODE defaults to 'admin'
 * (isDevMode = true), so getShareInfo is never called, viewerOwnerId stays null,
 * ownerOwnerId = '', and the button is hidden.
 *
 * Fix: add  env: { VITE_NOVOTREE_APP_MODE: 'public' }  to vitest.config.ts so that
 * tests run in the same auth mode as production.  This ensures the viewer branch
 * (getShareInfo → viewerOwnerId) is exercised and the button appears.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AuthProvider } from '../../src/contexts/AuthContext';
import { TreeOverviewPage } from '../../src/pages/tree/TreeOverviewPage';

// ── API mocks ────────────────────────────────────────────────────────────────

vi.mock('../../src/api/auth', () => ({
  authApi: {
    // No active editor session — this is an anonymous viewer.
    me: vi.fn().mockRejectedValue({ response: { status: 401 } }),
    // Share-token resolves to a real owner.
    getShareInfo: vi.fn().mockResolvedValue({ owner_id: 'owner123', display_name: 'Test Owner' }),
    // Unused in this flow, but required by auth context shape.
    login: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  },
}));

vi.mock('../../src/api/tree', () => ({
  treeApi: {
    getFullTree: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
  },
}));

// ── Component mocks (jsdom-incompatible deps) ────────────────────────────────

vi.mock('../../src/components/tree/TreeCanvas', () => ({
  TreeCanvas: () => null,
}));

vi.mock('../../src/components/tree/TreeLegend', () => ({
  TreeLegend: () => null,
}));

vi.mock('../../src/components/tree/ExportControls', () => ({
  ExportControls: () => null,
}));

vi.mock('@xyflow/react', () => ({
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthProvider>
          <TreeOverviewPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  // Simulate the browser URL that a share link points to.
  window.history.pushState({}, '', '/tree?share=test-token');
});

afterEach(() => {
  window.history.pushState({}, '', '/');
  sessionStorage.clear();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe('TreeOverviewPage – viewer via share link', () => {
  it('shows "Wanna contribute to this tree?" button for share-token viewers', async () => {
    renderPage();

    // The button is gated on isViewer && ownerOwnerId.  Both are truthy only
    // after AuthContext resolves the share token via getShareInfo() — which
    // requires VITE_NOVOTREE_APP_MODE !== 'admin' (i.e. isDevMode = false).
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /wanna contribute to this tree/i }),
      ).toBeInTheDocument(),
    );
  });
});
