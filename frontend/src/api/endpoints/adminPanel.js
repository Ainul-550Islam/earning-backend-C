// ============================================================
// src/api/endpoints.js
// Base → Django REST Framework
// Auth → JWT (Authorization: Bearer <token>)
// ============================================================

import axios from "axios";

// ──────────────────────────────────────────────────────────────
// AXIOS INSTANCE
// ──────────────────────────────────────────────────────────────
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

// ── Request interceptor: attach JWT ──
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: refresh token on 401 ──
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem("refresh_token");
        const { data } = await axios.post(
          `${api.defaults.baseURL}/auth/token/refresh/`,
          { refresh }
        );
        localStorage.setItem("access_token", data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        localStorage.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;


// ============================================================
// ① ADMIN ACTIONS
// Model: AdminAction
// ============================================================

/**
 * GET  /admin/actions/
 * Query params: action_type, admin, page, page_size
 */
export const getAdminActions = (params = {}) =>
  api.get("/admin/actions/", { params });

/**
 * GET  /admin/actions/:id/
 */
export const getAdminActionById = (id) =>
  api.get(`/admin/actions/${id}/`);

/**
 * POST /admin/actions/
 * body: { action_type, target_user, description, metadata? }
 */
export const createAdminAction = (payload) =>
  api.post("/admin/actions/", payload);

/**
 * GET  /admin/actions/stats/
 * Returns counts grouped by action_type for dashboard
 */
export const getAdminActionStats = () =>
  api.get("/admin/actions/stats/");

/**
 * DELETE /admin/actions/:id/
 */
export const deleteAdminAction = (id) =>
  api.delete(`/admin/actions/${id}/`);


// ============================================================
// ② REPORTS
// Model: Report
// ============================================================

/**
 * GET  /admin/reports/
 * Query params: report_type, status, generated_by, start_date, end_date, page
 */
export const getReports = (params = {}) =>
  api.get("/admin/reports/", { params });

/**
 * GET  /admin/reports/:id/
 */
export const getReportById = (id) =>
  api.get(`/admin/reports/${id}/`);

/**
 * POST /admin/reports/
 * body: { title, report_type, start_date, end_date, description? }
 */
export const createReport = (payload) =>
  api.post("/admin/reports/", payload);

/**
 * PATCH /admin/reports/:id/
 * body: partial fields
 */
export const updateReport = (id, payload) =>
  api.patch(`/admin/reports/${id}/`, payload);

/**
 * DELETE /admin/reports/:id/
 */
export const deleteReport = (id) =>
  api.delete(`/admin/reports/${id}/`);

/**
 * GET  /admin/reports/:id/download/
 * Returns report file download URL or blob
 */
export const downloadReport = (id) =>
  api.get(`/admin/reports/${id}/download/`, { responseType: "blob" });

/**
 * POST /admin/reports/:id/regenerate/
 * Re-generates report data & file
 */
export const regenerateReport = (id) =>
  api.post(`/admin/reports/${id}/regenerate/`);


// ============================================================
// ③ SYSTEM SETTINGS
// Model: SystemSettings (singleton)
// ============================================================

/**
 * GET  /admin/settings/
 * Returns the one SystemSettings instance
 */
export const getSystemSettings = () =>
  api.get("/admin/settings/");

/**
 * PATCH /admin/settings/
 * body: any subset of SystemSettings fields
 * Examples:
 *   updateSystemSettings({ maintenance_mode: true })
 *   updateSystemSettings({ min_withdrawal_amount: 200, max_withdrawal_amount: 20000 })
 */
export const updateSystemSettings = (payload) =>
  api.patch("/admin/settings/", payload);

/**
 * GET  /admin/settings/public/
 * Returns only public-safe settings for frontend (no SMTP, API keys, etc.)
 */
export const getPublicSettings = () =>
  api.get("/admin/settings/public/");

/**
 * POST /admin/settings/check-app-version/
 * body: { platform: "android"|"ios", version_code: number }
 * Returns update requirements
 */
export const checkAppVersion = (payload) =>
  api.post("/admin/settings/check-app-version/", payload);

/**
 * POST /admin/settings/toggle-maintenance/
 * body: { maintenance_mode: boolean, maintenance_message?: string }
 */
export const toggleMaintenance = (payload) =>
  api.post("/admin/settings/toggle-maintenance/", payload);

/**
 * POST /admin/settings/clear-cache/
 * Clears Django cache (calls cache.clear())
 */
export const clearSystemCache = () =>
  api.post("/admin/settings/clear-cache/");


// ============================================================
// ④ SITE NOTIFICATIONS
// Model: SiteNotification
// ============================================================

/**
 * GET  /admin/site-notifications/
 * Query params: notification_type, is_active, page
 */
export const getSiteNotifications = (params = {}) =>
  api.get("/admin/site-notifications/", { params });

/**
 * GET  /admin/site-notifications/:id/
 */
export const getSiteNotificationById = (id) =>
  api.get(`/admin/site-notifications/${id}/`);

/**
 * POST /admin/site-notifications/
 * body: { title, message, notification_type, is_active?, show_on_login?, start_date?, end_date?, priority? }
 */
export const createSiteNotification = (payload) =>
  api.post("/admin/site-notifications/", payload);

/**
 * PATCH /admin/site-notifications/:id/
 */
export const updateSiteNotification = (id, payload) =>
  api.patch(`/admin/site-notifications/${id}/`, payload);

/**
 * DELETE /admin/site-notifications/:id/
 */
export const deleteSiteNotification = (id) =>
  api.delete(`/admin/site-notifications/${id}/`);

/**
 * POST /admin/site-notifications/:id/toggle/
 * Flips is_active boolean on the server
 */
export const toggleSiteNotification = (id) =>
  api.post(`/admin/site-notifications/${id}/toggle/`);

/**
 * GET  /admin/site-notifications/active/
 * Returns currently active (is_active=true, within date range) notifications
 */
export const getActiveNotifications = () =>
  api.get("/admin/site-notifications/active/");


// ============================================================
// ⑤ SITE CONTENT
// Model: SiteContent
// ============================================================

/**
 * GET  /admin/site-contents/
 * Query params: content_type, is_active, language, page
 */
export const getSiteContents = (params = {}) =>
  api.get("/admin/site-contents/", { params });

/**
 * GET  /admin/site-contents/:id/
 */
export const getSiteContentById = (id) =>
  api.get(`/admin/site-contents/${id}/`);

/**
 * GET  /admin/site-contents/by-identifier/:identifier/
 * Fetch by slug identifier (e.g. "home-banner")
 */
export const getSiteContentByIdentifier = (identifier, lang = "en") =>
  api.get(`/admin/site-contents/by-identifier/${identifier}/`, {
    params: { language: lang },
  });

/**
 * POST /admin/site-contents/
 * body: { identifier, title, content, content_type, language?, meta_title?, meta_description?, order? }
 */
export const createSiteContent = (payload) =>
  api.post("/admin/site-contents/", payload);

/**
 * PATCH /admin/site-contents/:id/
 */
export const updateSiteContent = (id, payload) =>
  api.patch(`/admin/site-contents/${id}/`, payload);

/**
 * DELETE /admin/site-contents/:id/
 */
export const deleteSiteContent = (id) =>
  api.delete(`/admin/site-contents/${id}/`);

/**
 * POST /admin/site-contents/:id/toggle/
 * Flips is_active boolean
 */
export const toggleSiteContent = (id) =>
  api.post(`/admin/site-contents/${id}/toggle/`);

/**
 * POST /admin/site-contents/reorder/
 * body: { items: [{ id, order }] }
 * Bulk update ordering
 */
export const reorderSiteContents = (items) =>
  api.post("/admin/site-contents/reorder/", { items });


// ============================================================
// ⑥ DASHBOARD OVERVIEW STATS
// Aggregated endpoint for the Overview tab
// ============================================================

/**
 * GET  /admin/dashboard/stats/
 * Returns: total_users, revenue_today, pending_withdrawals,
 *          active_sessions, reports_count, fraud_flags
 */
export const getDashboardStats = () =>
  api.get("/admin/dashboard/stats/");

/**
 * GET  /admin/dashboard/revenue-chart/
 * Query params: days (default 7)
 * Returns: [{ date, amount }]
 */
export const getRevenueChart = (days = 7) =>
  api.get("/admin/dashboard/revenue-chart/", { params: { days } });

/**
 * GET  /admin/dashboard/system-health/
 * Returns: { api_uptime, db_usage, cache_usage }
 */
export const getSystemHealth = () =>
  api.get("/admin/dashboard/system-health/");