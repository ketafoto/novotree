import { useEffect, useState } from 'react';
import { privacyApi, PrivacyConfig } from '../api/privacy';

// Single shared promise — every consumer of usePrivacyConfig waits on the
// same network request, and a successful fetch is cached for the rest of
// the session. The config is effectively immutable per deployment.
let cached: Promise<PrivacyConfig> | null = null;

function loadOnce(): Promise<PrivacyConfig> {
  if (cached === null) {
    cached = privacyApi.getConfig().catch((err) => {
      cached = null;  // allow a retry on next mount after a failure
      throw err;
    });
  }
  return cached;
}

interface PrivacyConfigState {
  config: PrivacyConfig | null;
  loading: boolean;
  error: Error | null;
}

export function usePrivacyConfig(): PrivacyConfigState {
  const [state, setState] = useState<PrivacyConfigState>({
    config: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    loadOnce()
      .then((config) => {
        if (!cancelled) setState({ config, loading: false, error: null });
      })
      .catch((err: Error) => {
        if (!cancelled) setState({ config: null, loading: false, error: err });
      });
    return () => { cancelled = true; };
  }, []);

  return state;
}
