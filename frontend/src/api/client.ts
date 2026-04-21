import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// If opened via a share link (?share=<token>), forward the token on read requests so the
// backend can authenticate the viewer. Only GET requests need it — writes always come from
// authenticated editors and must never carry the share param (backend blocks viewer writes).
const shareToken = new URLSearchParams(window.location.search).get('share');
if (shareToken) {
  apiClient.interceptors.request.use((config) => {
    if ((config.method ?? 'get').toLowerCase() === 'get') {
      config.params = { ...config.params, share: shareToken };
    }
    return config;
  });
}

// On any 401, the session is gone (deleted, frozen, or token expired) — redirect to login
// immediately so the user isn't left in a broken half-authenticated state.
// Skip the redirect for auth endpoints themselves (login/refresh) to let callers handle those.
const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/me'];
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const url: string = err?.config?.url ?? '';
    const status: number = err?.response?.status;
    if (status === 401 && !AUTH_ENDPOINTS.some((p) => url.includes(p))) {
      const isShareViewer = !!sessionStorage.getItem('share_token');
      if (!isShareViewer) {
        sessionStorage.removeItem('share_token');
        window.location.href = '/novotree/login';
      }
    }
    return Promise.reject(err);
  },
);

export default apiClient;

