import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { TreeDeciduous } from 'lucide-react';
import { authApi } from '../../api/auth';
import { useAuth } from '../../contexts/AuthContext';
import { usePublicConfig } from '../../hooks/usePublicConfig';

type State = 'verifying' | 'success' | 'error';

const ERROR_MESSAGES: Record<string, string> = {
  'Invalid or already used verification link': 'This verification link is invalid or has already been used.',
  'Verification link has expired — please sign up again': 'This verification link has expired. Please sign up again.',
};

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const { adminEmail } = usePublicConfig();
  const [state, setState] = useState<State>('verifying');
  const [errorMsg, setErrorMsg] = useState('Verification failed. The link may be invalid or expired.');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setErrorMsg('No verification token found in the link.');
      setState('error');
      return;
    }

    authApi.verifyEmail(token)
      .then(async () => {
        await refresh();
        setState('success');
        setTimeout(() => navigate('/'), 2000);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail ?? '';
        setErrorMsg(ERROR_MESSAGES[detail] ?? 'Verification failed. The link may be invalid or expired.');
        setState('error');
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-600 rounded-xl mb-6">
          <TreeDeciduous className="w-8 h-8 text-white" />
        </div>

        {state === 'verifying' && (
          <>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Verifying your email…</h1>
            <p className="text-gray-500 text-sm">Please wait.</p>
          </>
        )}

        {state === 'success' && (
          <>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Email verified!</h1>
            <p className="text-gray-500 text-sm">Your account is ready. Redirecting…</p>
          </>
        )}

        {state === 'error' && (
          <>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Verification failed</h1>
            <p className="text-gray-600 text-sm mb-4">{errorMsg}</p>
            <Link to="/signup" className="text-emerald-600 hover:underline text-sm">
              Sign up again
            </Link>
            {adminEmail && (
              <p className="text-xs text-gray-400 mt-4">
                Having trouble?{' '}
                <a href={`mailto:${adminEmail}`} className="text-emerald-600 hover:underline">
                  Contact the administrator
                </a>
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
