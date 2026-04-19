import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import { AuthProvider } from './contexts/AuthContext';
import { Layout } from './components/layout/Layout';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { typesApi } from './api/types';

// Auth pages (no layout wrapper)
import { LoginPage } from './pages/auth/LoginPage';
import { SignupPage } from './pages/auth/SignupPage';
import { SetPasswordPage } from './pages/auth/SetPasswordPage';
import { VerifyEmailPage } from './pages/auth/VerifyEmailPage';

// Main pages
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { IndividualsListPage } from './pages/individuals/IndividualsListPage';
import { IndividualDetailPage } from './pages/individuals/IndividualDetailPage';
import { IndividualFormPage } from './pages/individuals/IndividualFormPage';
import { FamiliesListPage } from './pages/families/FamiliesListPage';
import { FamilyDetailPage } from './pages/families/FamilyDetailPage';
import { FamilyFormPage } from './pages/families/FamilyFormPage';
import { BulkEditIndividualsPage } from './pages/bulk-edit/BulkEditIndividualsPage';
import { BulkEditFamiliesPage } from './pages/bulk-edit/BulkEditFamiliesPage';
import { ExportPage } from './pages/export/ExportPage';
import { ImportPage } from './pages/import/ImportPage';
import { SettingsPage } from './pages/settings/SettingsPage';

// Lazy-load heavy pages
const TreePage = lazy(() =>
  import('./pages/tree/TreePage').then((m) => ({ default: m.TreePage }))
);
const TreeOverviewPage = lazy(() =>
  import('./pages/tree/TreeOverviewPage').then((m) => ({ default: m.TreeOverviewPage }))
);
const UserManagerPage = lazy(() =>
  import('./pages/users/UserManagerPage').then((m) => ({ default: m.UserManagerPage }))
);

const TreeFallback = <div className="flex items-center justify-center h-screen text-gray-500">Loading tree…</div>;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});
queryClient.setQueryDefaults(['types'], {
  staleTime: Infinity,
  gcTime: 24 * 60 * 60 * 1000,
});
queryClient.setQueryDefaults(['tree'], {
  staleTime: 0,  // always refetch tree on mount so edits elsewhere are reflected immediately
});

function PrefetchTypes() {
  useEffect(() => {
    void queryClient.prefetchQuery({ queryKey: ['types', 'sex'], queryFn: typesApi.getSexTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'events'], queryFn: typesApi.getEventTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'media'], queryFn: typesApi.getMediaTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'family-roles'], queryFn: typesApi.getFamilyRoles });
    void queryClient.prefetchQuery({ queryKey: ['types', 'family-types'], queryFn: typesApi.getFamilyTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'name-types'], queryFn: typesApi.getNameTypes });
    void queryClient.prefetchQuery({ queryKey: ['types', 'date-approx'], queryFn: typesApi.getDateApproxTypes });
  }, []);
  return null;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PrefetchTypes />
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <AuthProvider>
          <Routes>
            {/* ── Public auth pages (no Layout wrapper) ── */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/set-password" element={<SetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />

            {/* ── Viewer-accessible tree routes (share token or authenticated) ── */}
            <Route
              path="/tree"
              element={
                <ProtectedRoute allowViewer>
                  <Suspense fallback={TreeFallback}><TreeOverviewPage /></Suspense>
                </ProtectedRoute>
              }
            />
            <Route
              path="/individuals/:id/tree"
              element={
                <ProtectedRoute allowViewer>
                  <Suspense fallback={TreeFallback}><TreePage /></Suspense>
                </ProtectedRoute>
              }
            />
            <Route
              path="/individuals/:id"
              element={
                <ProtectedRoute allowViewer>
                  <IndividualDetailPage readOnly={false} />
                </ProtectedRoute>
              }
            />

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
              <Route path="individuals/:id/edit" element={<IndividualFormPage />} />

              {/* Families */}
              <Route path="families" element={<FamiliesListPage />} />
              <Route path="families/new" element={<FamilyFormPage />} />
              <Route path="families/:id" element={<FamilyDetailPage />} />
              <Route path="families/:id/edit" element={<FamilyFormPage />} />

              {/* Bulk Edit */}
              <Route path="bulk-edit/individuals" element={<BulkEditIndividualsPage />} />
              <Route path="bulk-edit/families" element={<BulkEditFamiliesPage />} />

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

              {/* Settings */}
              <Route path="settings" element={<SettingsPage />} />

              {/* User Manager — owners only */}
              <Route
                path="users"
                element={
                  <ProtectedRoute minRole="owner">
                    <Suspense fallback={<div className="p-8 text-gray-500">Loading…</div>}>
                      <UserManagerPage />
                    </Suspense>
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>

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
