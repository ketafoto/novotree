import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// If opened via a share link (?share=<token>), forward the token on every request
// so the backend can authenticate the viewer without a login session.
const shareToken = new URLSearchParams(window.location.search).get('share');
if (shareToken) {
  apiClient.interceptors.request.use((config) => {
    config.params = { ...config.params, share: shareToken };
    return config;
  });
}

export default apiClient;

