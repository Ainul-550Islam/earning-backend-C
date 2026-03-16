import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  AlertRule Model → /api/alerts/rules/
// ─────────────────────────────────────────────────────────────────
export const alertRuleAPI = {
  // GET    /api/alerts/rules/
  list: (params = {}) =>
    client.get("/alerts/rules/", { params }),

  // GET    /api/alerts/rules/:id/
  detail: (id) =>
    client.get(`/alerts/rules/${id}/`),

  // ✅ FIXED: was /alerts/rules/ — backend url is /alerts/rules/create/
  create: (data) =>
    client.post("/alerts/rules/create/", data),

  // PATCH  /api/alerts/rules/:id/
  update: (id, data) =>
    client.patch(`/alerts/rules/${id}/`, data),

  // DELETE /api/alerts/rules/:id/
  delete: (id) =>
    client.delete(`/alerts/rules/${id}/`),

  // ✅ FIXED: was missing from urls.py — now added
  stats: () =>
    client.get("/alerts/rules/stats/"),

  // GET    /api/alerts/rules/?is_active=true
  active: (params = {}) =>
    client.get("/alerts/rules/", { params: { ...params, is_active: true } }),

  // GET    /api/alerts/rules/?severity=high&severity=critical
  highSeverity: (params = {}) =>
    client.get("/alerts/rules/", { params: { ...params, severity: ["high", "critical"] } }),

  // POST   /api/alerts/rules/:id/test/
  test: (id) =>
    client.post(`/alerts/rules/${id}/test/`),

  // ✅ FIXED: was PATCH to /rules/bulk_update_status/ — now PATCH to /rules/bulk-update-status/
  bulkUpdateStatus: (ids, is_active) =>
    client.patch("/alerts/rules/bulk-update-status/", { ids, is_active }),
};

// ─────────────────────────────────────────────────────────────────
//  AlertLog Model → /api/alerts/logs/
// ─────────────────────────────────────────────────────────────────
export const alertLogAPI = {
  // GET    /api/alerts/logs/
  list: (params = {}) =>
    client.get("/alerts/logs/", { params }),

  // ✅ FIXED: now exists in urls.py
  detail: (id) =>
    client.get(`/alerts/logs/${id}/`),

  // ✅ FIXED: was missing from urls.py — now added
  stats: () =>
    client.get("/alerts/logs/stats/"),

  // GET    /api/alerts/logs/?is_resolved=true
  resolved: (params = {}) =>
    client.get("/alerts/logs/", { params: { ...params, is_resolved: true } }),

  // GET    /api/alerts/logs/?is_resolved=false
  unresolved: (params = {}) =>
    client.get("/alerts/logs/", { params: { ...params, is_resolved: false } }),

  // POST   /api/alerts/logs/:id/resolve/
  // ✅ FIXED: backend now accepts both 'note' and 'resolution_note'
  resolve: (id, note = "") =>
    client.post(`/alerts/logs/${id}/resolve/`, { resolution_note: note }),

  // ✅ FIXED: method POST (was PATCH), url /logs/bulk-resolve/ (was /logs/bulk_resolve/)
  bulkResolve: (ids, note = "") =>
    client.post("/alerts/logs/bulk-resolve/", { ids, resolution_note: note }),
};

// ─────────────────────────────────────────────────────────────────
//  Notification Model → /api/alerts/notifications/
// ─────────────────────────────────────────────────────────────────
export const alertNotificationAPI = {
  list: (params = {}) =>
    client.get("/alerts/notifications/", { params }),

  detail: (id) =>
    client.get(`/alerts/notifications/${id}/`),

  stats: () =>
    client.get("/alerts/notifications/stats/"),

  retry: (id) =>
    client.post(`/alerts/notifications/${id}/retry/`),
};

// ─────────────────────────────────────────────────────────────────
//  AlertSchedule Model → /api/alerts/schedules/
// ─────────────────────────────────────────────────────────────────
export const alertScheduleAPI = {
  list: (params = {}) =>
    client.get("/alerts/schedules/", { params }),

  detail: (id) =>
    client.get(`/alerts/schedules/${id}/`),

  create: (data) =>
    client.post("/alerts/schedules/", data),

  update: (id, data) =>
    client.patch(`/alerts/schedules/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/schedules/${id}/`),

  activeNow: () =>
    client.get("/alerts/schedules/active_now/"),
};

// ─────────────────────────────────────────────────────────────────
//  AlertEscalation Model → /api/alerts/escalations/
// ─────────────────────────────────────────────────────────────────
export const alertEscalationAPI = {
  list: (params = {}) =>
    client.get("/alerts/escalations/", { params }),

  detail: (id) =>
    client.get(`/alerts/escalations/${id}/`),

  create: (data) =>
    client.post("/alerts/escalations/", data),

  update: (id, data) =>
    client.patch(`/alerts/escalations/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/escalations/${id}/`),

  escalate: (id, logId) =>
    client.post(`/alerts/escalations/${id}/escalate/${logId}/`),
};

// ─────────────────────────────────────────────────────────────────
//  AlertTemplate Model → /api/alerts/templates/
// ─────────────────────────────────────────────────────────────────
export const alertTemplateAPI = {
  list: (params = {}) =>
    client.get("/alerts/templates/", { params }),

  detail: (id) =>
    client.get(`/alerts/templates/${id}/`),

  create: (data) =>
    client.post("/alerts/templates/", data),

  update: (id, data) =>
    client.patch(`/alerts/templates/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/templates/${id}/`),

  preview: (id, channel, context = {}) =>
    client.post(`/alerts/templates/${id}/preview/`, { channel, context }),
};

// ─────────────────────────────────────────────────────────────────
//  AlertAnalytics Model → /api/alerts/analytics/
// ─────────────────────────────────────────────────────────────────
export const alertAnalyticsAPI = {
  list: (params = {}) =>
    client.get("/alerts/analytics/", { params }),

  detail: (id) =>
    client.get(`/alerts/analytics/${id}/`),

  latest: (days = 7) =>
    client.get("/alerts/analytics/latest/", { params: { days } }),

  generate: (date, force_regenerate = false) =>
    client.post("/alerts/analytics/generate/", { date, force_regenerate }),
};

// ─────────────────────────────────────────────────────────────────
//  AlertGroup Model → /api/alerts/groups/
// ─────────────────────────────────────────────────────────────────
export const alertGroupAPI = {
  list: (params = {}) =>
    client.get("/alerts/groups/", { params }),

  detail: (id) =>
    client.get(`/alerts/groups/${id}/`),

  create: (data) =>
    client.post("/alerts/groups/", data),

  update: (id, data) =>
    client.patch(`/alerts/groups/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/groups/${id}/`),

  sendAlert: (id) =>
    client.post(`/alerts/groups/${id}/send_alert/`),

  updateCache: (id) =>
    client.post(`/alerts/groups/${id}/update_cache/`),
};

// ─────────────────────────────────────────────────────────────────
//  AlertSuppression Model → /api/alerts/suppressions/
// ─────────────────────────────────────────────────────────────────
export const alertSuppressionAPI = {
  list: (params = {}) =>
    client.get("/alerts/suppressions/", { params }),

  detail: (id) =>
    client.get(`/alerts/suppressions/${id}/`),

  create: (data) =>
    client.post("/alerts/suppressions/", data),

  update: (id, data) =>
    client.patch(`/alerts/suppressions/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/suppressions/${id}/`),

  activeNow: () =>
    client.get("/alerts/suppressions/active_now/"),
};

// ─────────────────────────────────────────────────────────────────
//  SystemHealthCheck Model → /api/alerts/health-checks/
// ─────────────────────────────────────────────────────────────────
export const systemHealthCheckAPI = {
  list: (params = {}) =>
    client.get("/alerts/health-checks/", { params }),

  detail: (id) =>
    client.get(`/alerts/health-checks/${id}/`),

  create: (data) =>
    client.post("/alerts/health-checks/", data),

  update: (id, data) =>
    client.patch(`/alerts/health-checks/${id}/`, data),

  delete: (id) =>
    client.delete(`/alerts/health-checks/${id}/`),

  overallStatus: () =>
    client.get("/alerts/health-checks/overall_status/"),

  checksNeeded: () =>
    client.get("/alerts/health-checks/checks_needed/"),

  run: (id) =>
    client.post(`/alerts/health-checks/${id}/run/`),
};

// ─────────────────────────────────────────────────────────────────
//  AlertRuleHistory Model → /api/alerts/rule-history/
// ─────────────────────────────────────────────────────────────────
export const alertRuleHistoryAPI = {
  list: (params = {}) =>
    client.get("/alerts/rule-history/", { params }),

  detail: (id) =>
    client.get(`/alerts/rule-history/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  AlertDashboardConfig Model → /api/alerts/dashboard-config/
// ─────────────────────────────────────────────────────────────────
export const alertDashboardConfigAPI = {
  get: () =>
    client.get("/alerts/dashboard-config/"),

  update: (data) =>
    client.patch("/alerts/dashboard-config/", data),

  reset: () =>
    client.post("/alerts/dashboard-config/reset/"),
};

// ─────────────────────────────────────────────────────────────────
//  SystemMetrics Model → /api/alerts/system-metrics/
// ─────────────────────────────────────────────────────────────────
export const systemMetricsAPI = {
  list: (params = {}) =>
    client.get("/alerts/system-metrics/", { params }),

  latest: () =>
    client.get("/alerts/system-metrics/latest/"),
};