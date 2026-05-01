import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { LoadingPage } from './Spinner';
import { isDevMode } from '../../config/appMode';

type MinRole = 'viewer' | 'contributor' | 'owner';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** Minimum role required. Default 'contributor' (blocks pure viewers from write pages). */
  minRole?: MinRole;
  /** If true, viewers (share token) are allowed in addition to authenticated editors. */
  allowViewer?: boolean;
}

export function ProtectedRoute({
  children,
  minRole = 'contributor',
  allowViewer = false,
}: ProtectedRouteProps) {
  const { isLoading, isAuthenticated, isOwner, isViewer } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingPage />;

  // Viewer (share token) access — checked BEFORE the dev-mode bypass so
  // share-link viewers stay confined to viewer-allowed routes regardless of
  // dev/auth-on/public mode. Without this ordering, a dev-mode viewer could
  // navigate into editor-only routes via the bypass below.
  if (isViewer) {
    if (allowViewer || minRole === 'viewer') return <>{children}</>;
    // Viewers hitting protected routes go to tree (their allowed landing)
    return <Navigate to="/tree" replace />;
  }

  // Dev mode: always allow (editors only — viewer case handled above)
  if (isDevMode) return <>{children}</>;

  // Not authenticated at all
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Role checks for authenticated editors
  if (minRole === 'owner' && !isOwner) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
