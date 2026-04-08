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

  // Dev mode: always allow
  if (isDevMode) return <>{children}</>;

  // Viewer (share token) access
  if (isViewer) {
    if (allowViewer || minRole === 'viewer') return <>{children}</>;
    // Viewers hitting protected routes go to tree (their allowed landing)
    return <Navigate to="/tree" replace />;
  }

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
