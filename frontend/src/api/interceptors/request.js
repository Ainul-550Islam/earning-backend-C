// src/api/interceptors/request.js
export const setupRequestInterceptors = (instance) => {
  instance.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('adminAccessToken');
      if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
      }
      // token না থাকলে header ছাড়াই request যাবে
      // component নিজেই fallback data handle করবে
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );
};