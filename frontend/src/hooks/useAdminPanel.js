// ============================================================
// src/hooks/useAdminPanel.js
// All hooks for the Admin Panel in one file
// Uses: React Query v5  (@tanstack/react-query)
// ============================================================

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import {
  // Admin Actions
  getAdminActions,
  getAdminActionById,
  createAdminAction,
  getAdminActionStats,
  deleteAdminAction,
  // Reports
  getReports,
  getReportById,
  createReport,
  updateReport,
  deleteReport,
  downloadReport,
  regenerateReport,
  // System Settings
  getSystemSettings,
  updateSystemSettings,
  getPublicSettings,
  checkAppVersion,
  toggleMaintenance,
  clearSystemCache,
  // Site Notifications
  getSiteNotifications,
  getSiteNotificationById,
  createSiteNotification,
  updateSiteNotification,
  deleteSiteNotification,
  toggleSiteNotification,
  getActiveNotifications,
  // Site Content
  getSiteContents,
  getSiteContentById,
  getSiteContentByIdentifier,
  createSiteContent,
  updateSiteContent,
  deleteSiteContent,
  toggleSiteContent,
  reorderSiteContents,
  // Dashboard
  getDashboardStats,
  getRevenueChart,
  getSystemHealth,
} from "../api/endpoints";


// ──────────────────────────────────────────────────────────────
// QUERY KEY CONSTANTS  (avoids typo bugs)
// ──────────────────────────────────────────────────────────────
export const QK = {
  ADMIN_ACTIONS:       "admin_actions",
  ADMIN_ACTION:        "admin_action",
  ADMIN_ACTION_STATS:  "admin_action_stats",
  REPORTS:             "reports",
  REPORT:              "report",
  SETTINGS:            "system_settings",
  PUBLIC_SETTINGS:     "public_settings",
  NOTIFICATIONS:       "site_notifications",
  NOTIFICATION:        "site_notification",
  ACTIVE_NOTIFICATIONS:"active_notifications",
  CONTENTS:            "site_contents",
  CONTENT:             "site_content",
  DASHBOARD_STATS:     "dashboard_stats",
  REVENUE_CHART:       "revenue_chart",
  SYSTEM_HEALTH:       "system_health",
};


// ============================================================
// ① ADMIN ACTIONS HOOKS
// ============================================================

/**
 * useAdminActions
 * Fetches paginated + filtered admin action log
 *
 * @param {object} filters  — { action_type, admin, page, page_size }
 *
 * Usage:
 *   const { data, isLoading } = useAdminActions({ action_type: "user_ban" });
 */
export function useAdminActions(filters = {}) {
  return useQuery({
    queryKey: [QK.ADMIN_ACTIONS, filters],
    queryFn:  () => getAdminActions(filters).then((r) => r.data),
    staleTime: 30_000,
    placeholderData: (prev) => prev, // smooth pagination (RQ v5)
  });
}

/**
 * useAdminAction
 * Single admin action detail
 */
export function useAdminAction(id) {
  return useQuery({
    queryKey: [QK.ADMIN_ACTION, id],
    queryFn:  () => getAdminActionById(id).then((r) => r.data),
    enabled:  !!id,
  });
}

/**
 * useAdminActionStats
 * Counts by action_type for charts
 */
export function useAdminActionStats() {
  return useQuery({
    queryKey: [QK.ADMIN_ACTION_STATS],
    queryFn:  () => getAdminActionStats().then((r) => r.data),
    staleTime: 60_000,
  });
}

/**
 * useCreateAdminAction
 * Creates a new admin action log entry
 *
 * Usage:
 *   const { mutate } = useCreateAdminAction();
 *   mutate({ action_type: "user_ban", target_user: 42, description: "..." });
 */
export function useCreateAdminAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => createAdminAction(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.ADMIN_ACTIONS] });
      qc.invalidateQueries({ queryKey: [QK.ADMIN_ACTION_STATS] });
      toast.success("Admin action logged successfully");
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || "Failed to log action");
    },
  });
}

/**
 * useDeleteAdminAction
 */
export function useDeleteAdminAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteAdminAction(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.ADMIN_ACTIONS] });
      toast.success("Action log deleted");
    },
    onError: () => toast.error("Failed to delete action"),
  });
}


// ============================================================
// ② REPORTS HOOKS
// ============================================================

/**
 * useReports
 *
 * @param {object} filters — { report_type, status, generated_by, start_date, end_date, page }
 *
 * Usage:
 *   const { data, isLoading } = useReports({ report_type: "revenue", status: "completed" });
 *   data.results → report list
 *   data.count   → total count
 */
export function useReports(filters = {}) {
  return useQuery({
    queryKey: [QK.REPORTS, filters],
    queryFn:  () => getReports(filters).then((r) => r.data),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

/**
 * useReport
 */
export function useReport(id) {
  return useQuery({
    queryKey: [QK.REPORT, id],
    queryFn:  () => getReportById(id).then((r) => r.data),
    enabled:  !!id,
  });
}

/**
 * useCreateReport
 *
 * Usage:
 *   const { mutate, isPending } = useCreateReport();
 *   mutate({ title: "Jan Revenue", report_type: "revenue", start_date: "2024-01-01", end_date: "2024-01-31" });
 */
export function useCreateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => createReport(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.REPORTS] });
      toast.success("Report generation started!");
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || "Failed to create report");
    },
  });
}

/**
 * useUpdateReport
 *
 * Usage:
 *   const { mutate } = useUpdateReport();
 *   mutate({ id: 3, payload: { status: "completed" } });
 */
export function useUpdateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateReport(id, payload).then((r) => r.data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: [QK.REPORTS] });
      qc.invalidateQueries({ queryKey: [QK.REPORT, id] });
      toast.success("Report updated");
    },
    onError: () => toast.error("Failed to update report"),
  });
}

/**
 * useDeleteReport
 */
export function useDeleteReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteReport(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.REPORTS] });
      toast.success("Report deleted");
    },
    onError: () => toast.error("Failed to delete report"),
  });
}

/**
 * useDownloadReport
 * Triggers file download in the browser
 *
 * Usage:
 *   const { mutate } = useDownloadReport();
 *   mutate({ id: 1, filename: "january-revenue.pdf" });
 */
export function useDownloadReport() {
  return useMutation({
    mutationFn: ({ id }) => downloadReport(id),
    onSuccess: (response, { filename = "report" }) => {
      const url  = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href  = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Download started");
    },
    onError: () => toast.error("Download failed"),
  });
}

/**
 * useRegenerateReport
 */
export function useRegenerateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => regenerateReport(id).then((r) => r.data),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: [QK.REPORTS] });
      qc.invalidateQueries({ queryKey: [QK.REPORT, id] });
      toast.success("Report regeneration started");
    },
    onError: () => toast.error("Failed to regenerate report"),
  });
}


// ============================================================
// ③ SYSTEM SETTINGS HOOKS
// ============================================================

/**
 * useSystemSettings
 * Fetches the singleton SystemSettings object
 *
 * Usage:
 *   const { data: settings, isLoading } = useSystemSettings();
 *   settings.maintenance_mode
 *   settings.min_withdrawal_amount
 */
export function useSystemSettings() {
  return useQuery({
    queryKey: [QK.SETTINGS],
    queryFn:  () => getSystemSettings().then((r) => r.data),
    staleTime: 5 * 60_000,         // 5 min — settings don't change often
  });
}

/**
 * usePublicSettings
 * Safe to call without admin auth (used on public pages)
 */
export function usePublicSettings() {
  return useQuery({
    queryKey: [QK.PUBLIC_SETTINGS],
    queryFn:  () => getPublicSettings().then((r) => r.data),
    staleTime: 10 * 60_000,
  });
}

/**
 * useUpdateSystemSettings
 * Partial update (PATCH) the singleton settings
 *
 * Usage:
 *   const { mutate } = useUpdateSystemSettings();
 *   mutate({ min_withdrawal_amount: 200, max_withdrawal_amount: 15000 });
 *   mutate({ enable_bkash: false });
 */
export function useUpdateSystemSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => updateSystemSettings(payload).then((r) => r.data),
    onSuccess: (data) => {
      qc.setQueryData([QK.SETTINGS], data);   // optimistic cache update
      toast.success("Settings saved successfully");
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || "Failed to save settings");
    },
  });
}

/**
 * useToggleMaintenance
 * Quick toggle for maintenance mode
 *
 * Usage:
 *   const { mutate } = useToggleMaintenance();
 *   mutate({ maintenance_mode: true, maintenance_message: "Back in 30 min" });
 */
export function useToggleMaintenance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => toggleMaintenance(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.SETTINGS] });
      toast.success("Maintenance mode updated");
    },
    onError: () => toast.error("Failed to toggle maintenance"),
  });
}

/**
 * useCheckAppVersion
 *
 * Usage:
 *   const { mutate } = useCheckAppVersion();
 *   mutate({ platform: "android", version_code: 24 });
 */
export function useCheckAppVersion() {
  return useMutation({
    mutationFn: (payload) => checkAppVersion(payload).then((r) => r.data),
  });
}

/**
 * useClearSystemCache
 *
 * Usage:
 *   const { mutate, isPending } = useClearSystemCache();
 *   mutate();
 */
export function useClearSystemCache() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearSystemCache().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries();           // refresh everything
      toast.success("System cache cleared!");
    },
    onError: () => toast.error("Cache clear failed"),
  });
}


// ============================================================
// ④ SITE NOTIFICATIONS HOOKS
// ============================================================

/**
 * useSiteNotifications
 *
 * @param {object} filters — { notification_type, is_active, page }
 *
 * Usage:
 *   const { data } = useSiteNotifications({ is_active: true });
 */
export function useSiteNotifications(filters = {}) {
  return useQuery({
    queryKey: [QK.NOTIFICATIONS, filters],
    queryFn:  () => getSiteNotifications(filters).then((r) => r.data),
    staleTime: 30_000,
  });
}

/**
 * useSiteNotification — single item
 */
export function useSiteNotification(id) {
  return useQuery({
    queryKey: [QK.NOTIFICATION, id],
    queryFn:  () => getSiteNotificationById(id).then((r) => r.data),
    enabled:  !!id,
  });
}

/**
 * useActiveNotifications
 * For public-facing banner / popup display
 */
export function useActiveNotifications() {
  return useQuery({
    queryKey: [QK.ACTIVE_NOTIFICATIONS],
    queryFn:  () => getActiveNotifications().then((r) => r.data),
    refetchInterval: 60_000,          // auto-refresh every 1 min
  });
}

/**
 * useCreateSiteNotification
 *
 * Usage:
 *   const { mutate } = useCreateSiteNotification();
 *   mutate({ title: "Promo!", message: "2× points week", notification_type: "PROMOTION", priority: 8 });
 */
export function useCreateSiteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => createSiteNotification(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.NOTIFICATIONS] });
      qc.invalidateQueries({ queryKey: [QK.ACTIVE_NOTIFICATIONS] });
      toast.success("Notification created");
    },
    onError: (err) => toast.error(err.response?.data?.detail || "Failed to create notification"),
  });
}

/**
 * useUpdateSiteNotification
 *
 * Usage:
 *   const { mutate } = useUpdateSiteNotification();
 *   mutate({ id: 2, payload: { priority: 10 } });
 */
export function useUpdateSiteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateSiteNotification(id, payload).then((r) => r.data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: [QK.NOTIFICATIONS] });
      qc.invalidateQueries({ queryKey: [QK.NOTIFICATION, id] });
      qc.invalidateQueries({ queryKey: [QK.ACTIVE_NOTIFICATIONS] });
      toast.success("Notification updated");
    },
    onError: () => toast.error("Update failed"),
  });
}

/**
 * useDeleteSiteNotification
 */
export function useDeleteSiteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteSiteNotification(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.NOTIFICATIONS] });
      qc.invalidateQueries({ queryKey: [QK.ACTIVE_NOTIFICATIONS] });
      toast.success("Notification deleted");
    },
    onError: () => toast.error("Delete failed"),
  });
}

/**
 * useToggleSiteNotification
 * Optimistic UI toggle
 *
 * Usage:
 *   const { mutate } = useToggleSiteNotification();
 *   mutate(notificationId);
 */
export function useToggleSiteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => toggleSiteNotification(id).then((r) => r.data),
    // optimistic update
    onMutate: async (id) => {
      // Cancel all queries with NOTIFICATIONS prefix (handles [QK.NOTIFICATIONS, filters])
      await qc.cancelQueries({ queryKey: [QK.NOTIFICATIONS], exact: false });
      // Snapshot all matching cache entries
      const prevEntries = qc.getQueriesData({ queryKey: [QK.NOTIFICATIONS], exact: false });
      // Optimistically update all cached pages
      qc.setQueriesData({ queryKey: [QK.NOTIFICATIONS], exact: false }, (old) => {
        if (!old?.results) return old;
        return {
          ...old,
          results: old.results.map((n) =>
            n.id === id ? { ...n, is_active: !n.is_active } : n
          ),
        };
      });
      return { prevEntries };
    },
    onError: (_, __, ctx) => {
      // Restore all snapshotted cache entries
      ctx?.prevEntries?.forEach(([key, data]) => qc.setQueryData(key, data));
      toast.error("Toggle failed");
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: [QK.NOTIFICATIONS], exact: false });
      qc.invalidateQueries({ queryKey: [QK.ACTIVE_NOTIFICATIONS] });
    },
  });
}


// ============================================================
// ⑤ SITE CONTENT HOOKS
// ============================================================

/**
 * useSiteContents
 *
 * @param {object} filters — { content_type, is_active, language, page }
 *
 * Usage:
 *   const { data } = useSiteContents({ content_type: "BANNER", is_active: true });
 */
export function useSiteContents(filters = {}) {
  return useQuery({
    queryKey: [QK.CONTENTS, filters],
    queryFn:  () => getSiteContents(filters).then((r) => r.data),
    staleTime: 60_000,
  });
}

/**
 * useSiteContent — single item by id
 */
export function useSiteContent(id) {
  return useQuery({
    queryKey: [QK.CONTENT, id],
    queryFn:  () => getSiteContentById(id).then((r) => r.data),
    enabled:  !!id,
  });
}

/**
 * useSiteContentByIdentifier
 *
 * Usage:
 *   const { data } = useSiteContentByIdentifier("home-banner");
 *   const { data } = useSiteContentByIdentifier("about-page", "bn");
 */
export function useSiteContentByIdentifier(identifier, lang = "en") {
  return useQuery({
    queryKey: [QK.CONTENT, identifier, lang],
    queryFn:  () => getSiteContentByIdentifier(identifier, lang).then((r) => r.data),
    enabled:  !!identifier,
    staleTime: 5 * 60_000,
  });
}

/**
 * useCreateSiteContent
 *
 * Usage:
 *   const { mutate } = useCreateSiteContent();
 *   mutate({ identifier: "eid-banner", title: "Eid Promo", content: "<h1>...</h1>", content_type: "BANNER" });
 */
export function useCreateSiteContent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => createSiteContent(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.CONTENTS] });
      toast.success("Content created");
    },
    onError: (err) => toast.error(err.response?.data?.detail || "Failed to create content"),
  });
}

/**
 * useUpdateSiteContent
 *
 * Usage:
 *   const { mutate } = useUpdateSiteContent();
 *   mutate({ id: 1, payload: { title: "Updated Banner", is_active: true } });
 */
export function useUpdateSiteContent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateSiteContent(id, payload).then((r) => r.data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: [QK.CONTENTS] });
      qc.invalidateQueries({ queryKey: [QK.CONTENT, id] });
      toast.success("Content updated");
    },
    onError: () => toast.error("Update failed"),
  });
}

/**
 * useDeleteSiteContent
 */
export function useDeleteSiteContent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteSiteContent(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.CONTENTS] });
      toast.success("Content deleted");
    },
    onError: () => toast.error("Delete failed"),
  });
}

/**
 * useToggleSiteContent
 * Optimistic UI toggle (same pattern as notifications)
 */
export function useToggleSiteContent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => toggleSiteContent(id).then((r) => r.data),
    onMutate: async (id) => {
      // Cancel all queries with CONTENTS prefix (handles [QK.CONTENTS, filters])
      await qc.cancelQueries({ queryKey: [QK.CONTENTS], exact: false });
      const prevEntries = qc.getQueriesData({ queryKey: [QK.CONTENTS], exact: false });
      qc.setQueriesData({ queryKey: [QK.CONTENTS], exact: false }, (old) => {
        if (!old?.results) return old;
        return {
          ...old,
          results: old.results.map((c) =>
            c.id === id ? { ...c, is_active: !c.is_active } : c
          ),
        };
      });
      return { prevEntries };
    },
    onError: (_, __, ctx) => {
      ctx?.prevEntries?.forEach(([key, data]) => qc.setQueryData(key, data));
      toast.error("Toggle failed");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: [QK.CONTENTS], exact: false }),
  });
}

/**
 * useReorderSiteContents
 *
 * Usage:
 *   const { mutate } = useReorderSiteContents();
 *   mutate([{ id: 1, order: 3 }, { id: 3, order: 1 }]);
 */
export function useReorderSiteContents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items) => reorderSiteContents(items).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QK.CONTENTS] });
      toast.success("Order saved");
    },
    onError: () => toast.error("Reorder failed"),
  });
}


// ============================================================
// ⑥ DASHBOARD HOOKS
// ============================================================

/**
 * useDashboardStats
 * Auto-refreshes every 30s for live feel
 *
 * Usage:
 *   const { data: stats } = useDashboardStats();
 *   stats.total_users
 *   stats.revenue_today
 *   stats.pending_withdrawals
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: [QK.DASHBOARD_STATS],
    queryFn:  () => getDashboardStats().then((r) => r.data),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}

/**
 * useRevenueChart
 *
 * @param {number} days — default 7
 *
 * Usage:
 *   const { data } = useRevenueChart(14);
 *   data → [{ date: "2024-01-15", amount: 12400 }, ...]
 */
export function useRevenueChart(days = 7) {
  return useQuery({
    queryKey: [QK.REVENUE_CHART, days],
    queryFn:  () => getRevenueChart(days).then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

/**
 * useSystemHealth
 * Auto-refreshes every 60s
 *
 * Usage:
 *   const { data: health } = useSystemHealth();
 *   health.api_uptime   → 99.8
 *   health.db_usage     → 87.2
 *   health.cache_usage  → 45.1
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: [QK.SYSTEM_HEALTH],
    queryFn:  () => getSystemHealth().then((r) => r.data),
    refetchInterval: 60_000,
  });
}