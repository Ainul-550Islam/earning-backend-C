// src/api/interceptors/response.js
export const setupResponseInterceptors = (instance) => {
  instance.interceptors.response.use(
    (response) => {
      return response;
    },
    (error) => {
      const status = error.response?.status;
      const originalRequest = error.config;

      // 302 Redirect (Django login redirect) → 401 এর মতো handle করো
      if (status === 302 || status === 401) {
        console.warn('Authentication required. Token missing or expired.');
        // Login redirect করার দরকার নেই এখন
        // শুধু error reject করো, component fallback handle করবে
        return Promise.reject({ ...error, isAuthError: true });
      }

      // 403 Forbidden
      if (status === 403) {
        console.warn('Access forbidden.');
        return Promise.reject({ ...error, isForbidden: true });
      }

      // 404
      if (status === 404) {
        console.warn(`API endpoint not found: ${originalRequest?.url}`);
        return Promise.reject(error);
      }

      // 500 Server Error
      if (status >= 500) {
        console.error('Server error:', error.response?.data);
        return Promise.reject(error);
      }

      return Promise.reject(error);
    }
  );
};


