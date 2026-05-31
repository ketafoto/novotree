import { useEffect, useState } from 'react';
import { authApi } from '../api/auth';

interface PublicConfigState {
  contactEmail: string | null;
  signupEnabled: boolean;
  loading: boolean;
}

export function usePublicConfig(): PublicConfigState {
  const [state, setState] = useState<PublicConfigState>({
    contactEmail: null,
    signupEnabled: true,  // optimistic — form stays visible until we know otherwise
    loading: true,
  });

  useEffect(() => {
    authApi.getPublicConfig()
      .then((cfg) => setState({
        contactEmail: cfg.contact_email,
        signupEnabled: cfg.signup_enabled,
        loading: false,
      }))
      .catch(() => setState((s) => ({ ...s, loading: false })));
  }, []);

  return state;
}
