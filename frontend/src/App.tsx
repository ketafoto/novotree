import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './contexts/AuthContext';
import { Layout } from './components/layout/Layout';
import { PrivacyFooter } from './components/layout/PrivacyFooter';
import { ViewerNotice } from './components/ViewerNotice';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { typesApi } from './api/types';
import { isLocalApp } from './config/appMode';

// Auth pages (no layout wrapper) — kept eager: needed on first paint for unauthenticated users
import { LoginPage } from './pages/auth/LoginPage';
import { OwnerSignupPage } from './pages/auth/SignupPage';
import { SetPasswordPage } from './pages/auth/SetPasswordPage';
import { VerifyOwnerEmailPage } from './pages/auth/VerifyEmailPage';
import { VerifyContributorEmailPage } from './pages/auth/VerifyContributorEmailPage';

// Legal / privacy pages — kept eager: public routes with no heavy dependencies
import { PrivacyRequestPage } from './pages/legal/PrivacyRequestPage';
import { PrivacyPage } from './pages/legal/PrivacyPage';

// Lazy-load all authenticated pages to keep the initial bundle small
const PrivacyRequestsPage = lazy(() =>
  import('./pages/legal/PrivacyRequestsPage').then((m) => ({ default: m.PrivacyRequestsPage }))
);
const DashboardPage = lazy(() =>
  import('./pages/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const IndividualsListPage = lazy(() =>
  import('./pages/individuals/IndividualsListPage').then((m) => ({ default: m.IndividualsListPage }))
);
const IndividualDetailPage = lazy(() =>
  import('./pages/individuals/IndividualDetailPage').then((m) => ({ default: m.IndividualDetailPage }))
);
const IndividualFormPage = lazy(() =>
  import('./pages/individuals/IndividualFormPage').then((m) => ({ default: m.IndividualFormPage }))
);
const FamiliesListPage = lazy(() =>
  import('./pages/families/FamiliesListPage').then((m) => ({ default: m.FamiliesListPage }))
);
const FamilyDetailPage = lazy(() =>
  import('./pages/families/FamilyDetailPage').then((m) => ({ default: m.FamilyDetailPage }))
);
const FamilyFormPage = lazy(() =>
  import('./pages/families/FamilyFormPage').then((m) => ({ default: m.FamilyFormPage }))
);
const ExportPage = lazy(() =>
  import('./pages/export/ExportPage').then((m) => ({ default: m.ExportPage }))
);
const ImportPage = lazy(() =>
  import('./pages/import/ImportPage').then((m) => ({ default: m.ImportPage }))
);
const SettingsPage = lazy(() =>
  import('./pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);
const TreePage = lazy(() =>
  import('./pages/tree/TreePage').then((m) => ({ default: m.TreePage }))
);
const TreeOverviewPage = lazy(() =>
  import('./pages/tree/TreeOverviewPage').then((m) => ({ default: m.TreeOverviewPage }))
);
const UserManagerPage = lazy(() =>
  import('./pages/users/UserManagerPage').then((m) => ({ default: m.UserManagerPage }))
);

const PageFallback = <div className="flex items-center justify-center h-screen text-gray-500">Loading…</div>;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Always refetch on mount so edits made by other contributors are reflected
      // immediately. Only what the mounted components read is refetched, not the
      // whole cache. Static lookup tables override this below.
      staleTime: 0,
      retry: (failureCount, error) => {
        // Never retry 401 — the session is gone, retrying just delays the redirect
        if ((error as { response?: { status?: number } })?.response?.status === 401) return false;
        return failureCount < 1;
      },
    },
  },
});
queryClient.setQueryDefaults(['types'], {
  staleTime: Infinity,
  gcTime: 24 * 60 * 60 * 1000,
});

/**
 * Route adapter that renders IndividualDetailPage in read-only mode for
 * share-link viewers and full-edit mode for authenticated editors. Hardcoding
 * readOnly={false} on the route would let viewers see Delete / edit modals,
 * even though the backend gates writes (in production).
 */
function IndividualDetailRoute() {
  const { isViewer } = useAuth();
  return <IndividualDetailPage readOnly={isViewer} />;
}

function PrefetchTypes() {
  const { isAuthenticated, isLoading } = useAuth();
  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    void queryClient.prefetchQuery({ queryKey: ['types', 'sex'], queryFn: typesApi.getSexTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'events'], queryFn: typesApi.getEventTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'media'], queryFn: typesApi.getMediaTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'family-roles'], queryFn: typesApi.getFamilyRoles });
    void queryClient.prefetchQuery({ queryKey: ['types', 'family-types'], queryFn: typesApi.getFamilyTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'name-types'], queryFn: typesApi.getNameTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'date-approx'], queryFn: typesApi.getDateApproxTypes });
  }, [isAuthenticated, isLoading]);
  return null;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <AuthProvider>
          <PrefetchTypes />
          <div className="min-h-screen flex flex-col">
          <div className="flex-1 flex flex-col">
          <Suspense fallback={PageFallback}>
          <Routes>
            {/* ── Public auth pages (no Layout wrapper) ── */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/owner-signup" element={<OwnerSignupPage />} />
            <Route path="/set-password" element={<SetPasswordPage />} />
            <Route path="/verify-owner-email" element={<VerifyOwnerEmailPage />} />
            <Route path="/verify-contributor-email" element={<VerifyContributorEmailPage />} />

            {/* ── Public privacy pages (no auth, no Layout) ── */}
            <Route path="/privacy/request" element={<PrivacyRequestPage />} />
            <Route path="/legal/privacy" element={<PrivacyPage />} />

            {/* ── Viewer-accessible tree routes (share token or authenticated) ── */}
            <Route
              path="/tree"
              element={
                <ProtectedRoute allowViewer>
                  <TreeOverviewPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/individuals/:id/tree"
              element={
                <ProtectedRoute allowViewer>
                  <TreePage />
                </ProtectedRoute>
              }
            />
            {/* /individuals/:id is special: in the web/VM deployment it sits
                OUTSIDE Layout so share-link viewers can see an individual's
                page without the editor chrome (sidebar, etc.). In the local
                desktop app there are no viewers at all (single user, no auth),
                so we move it INSIDE Layout further down so the Header — and
                its Donate ♥ button — are visible. */}
            {!isLocalApp && (
              <Route
                path="/individuals/:id"
                element={
                  <ProtectedRoute allowViewer>
                    <div className="p-6">
                      <IndividualDetailRoute />
                    </div>
                  </ProtectedRoute>
                }
              />
            )}

            {/* ── Main app (authenticated editors only) ── */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardPage />} />

              {/* Individuals */}
              <Route path="individuals" element={<IndividualsListPage />} />
              <Route path="individuals/new" element={<IndividualFormPage />} />
              {/* Detail page lives here too in local mode (see comment above). */}
              {isLocalApp && (
                <Route path="individuals/:id" element={<IndividualDetailRoute />} />
              )}

              {/* Families */}
              <Route path="families" element={<FamiliesListPage />} />
              <Route path="families/new" element={<FamilyFormPage />} />
              <Route path="families/:id" element={<FamilyDetailPage />} />

              {/* Data Exchange — export for all editors, import for owners only */}
              <Route path="export" element={<ExportPage />} />
              <Route
                path="import"
                element={
                  <ProtectedRoute minRole="owner">
                    <ImportPage />
                  </ProtectedRoute>
                }
              />

              {/* Privacy — Owner-only privacy-requests triage queue */}
              <Route
                path="legal/privacy-requests"
                element={
                  <ProtectedRoute minRole="owner">
                    <PrivacyRequestsPage />
                  </ProtectedRoute>
                }
              />

              {/* Settings */}
              <Route path="settings" element={<SettingsPage />} />

              {/* User Manager — owners only */}
              <Route
                path="users"
                element={
                  <ProtectedRoute minRole="owner">
                    <UserManagerPage />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
          </div>
          <PrivacyFooter />
          <ViewerNotice />
          </div>

          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: { background: '#333', color: '#fff' },
              success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
              error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
