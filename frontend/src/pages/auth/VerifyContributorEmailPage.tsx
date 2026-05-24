import { useEffect, useRef, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { TreeDeciduous, Clock } from 'lucide-react';
import { authApi } from '../../api/auth';
import { usePublicConfig } from '../../hooks/usePublicConfig';

type State = 'verifying' | 'success' | 'error';

const ERROR_MESSAGES: Record<string, string> = {
  'Invalid or already used verification link': 'This verification link is invalid or has already been used.',
  'Verification link has expired — please sign up again': 'This verification link has expired. Please sign up again.',
};

export function VerifyContributorEmailPage() {
  const [searchParams] = useSearchParams();
  const { adminEmail } = usePublicConfig();
  const [state, setState] = useState<State>('verifying');
  const [errorMsg, setErrorMsg] = useState('Verification failed. The link may be invalid or expired.');
  // The token is single-use; React Strict Mode mounts effects twice in dev, so without
  // this guard the second call would 409 and overwrite the success state.
  const hasVerified = useRef(false);

  useEffect(() => {
    if (hasVerified.current) return;
    hasVerified.current = true;

    const token = searchParams.get('token');
    if (!token) {
      setErrorMsg('No verification token found in the link.');
      setState('error');
      return;
    }

    authApi.verifyContributorEmail(token)
      .then(() => {
        setState('success');
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail ?? '';
        setErrorMsg(ERROR_MESSAGES[detail] ?? 'Verification failed. The link may be invalid or expired.');
        setState('error');
      });
  }, []);

  return (
    <div className="flex-1 bg-gray-50 flex items-center justify-center p-4">
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
            <Clock className="w-10 h-10 text-amber-500 mx-auto mb-3" />
            <h1 className="text-xl font-bold text-gray-900 mb-2">Email verified!</h1>
            <p className="text-gray-600 text-sm mb-4">
              Your request has been submitted to the tree owner. You'll be notified
              by email once your access is approved — then you can log in.
            </p>
            <Link
              to="/login"
              className="inline-block text-sm text-emerald-600 hover:underline"
            >
              Go to login page
            </Link>
          </>
        )}

        {state === 'error' && (
          <>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Verification failed</h1>
            <p className="text-gray-600 text-sm mb-4">{errorMsg}</p>
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
