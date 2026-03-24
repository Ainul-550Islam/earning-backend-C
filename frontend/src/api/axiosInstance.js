// src/api/axiosInstance.js
import axios from "axios";
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
const TIMEOUT  = Number(import.meta.env.VITE_API_TIMEOUT) || 15_000;
const axiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: TIMEOUT,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});
// ── Request interceptor — attach token ────────────────────────────────────────
axiosInstance.interceptors.request.use(
  (config) => {
    try {
      // Auth endpoints এ token লাগবে না
      const skipAuth = ['/auth/login', '/auth/register', '/auth/token', '/token/refresh'];
      const isAuthUrl = skipAuth.some(path => (config.url || '').includes(path));
      if (!isAuthUrl) {
        const token = localStorage.getItem("adminAccessToken");
        if (token) config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // localStorage unavailable (SSR / incognito) — continue without token
    }
    return config;
  },
  (error) => Promise.reject(error),
);
// ── Response interceptor — token refresh + normalise errors ──────────────────
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    // 401 → try refresh once
    if (
      error.response?.status === 401 &&
      !original._retry &&
      original.url !== "/api/token/refresh/"
    ) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem("refresh_token");
        if (!refresh) throw new Error("no_refresh");
        const { data } = await axios.post(`${BASE_URL}/api/token/refresh/`, { refresh });
        localStorage.setItem("adminAccessToken", data.access ?? "");
        original.headers.Authorization = `Bearer ${data.access}`;
        return axiosInstance(original);
      } catch {
        localStorage.removeItem("adminAccessToken");
        localStorage.removeItem("refresh_token");
        window.dispatchEvent(new Event("auth:logout"));
        return Promise.reject(error);
      }
    }
    // Normalise error shape so callers always get error.message
    if (error.response?.data) {
      const d = error.response.data;
      error.message =
        d.detail || d.message || (typeof d === "string" ? d : JSON.stringify(d));
    }
    return Promise.reject(error);
  },
);
export default axiosInstance;
