import { useEffect, useState } from 'react';
import { authApi } from '../api/auth';

interface PublicConfigState {
  adminEmail: string | null;
  signupEnabled: boolean;
  loading: boolean;
}

export function usePublicConfig(): PublicConfigState {
  const [state, setState] = useState<PublicConfigState>({
    adminEmail: null,
    signupEnabled: true,  // optimistic — form stays visible until we know otherwise
    loading: true,
  });

  useEffect(() => {
    authApi.getPublicConfig()
      .then((cfg) => setState({
        adminEmail: cfg.admin_email,
        signupEnabled: cfg.signup_enabled,
        loading: false,
      }))
      .catch(() => setState((s) => ({ ...s, loading: false })));
  }, []);

  return state;
}
