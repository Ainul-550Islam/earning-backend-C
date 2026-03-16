import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  AuditLog Model → /api/audit_logs/logs/
// ─────────────────────────────────────────────────────────────────
export const auditLogAPI = {
  // GET    /api/audit_logs/logs/
  // params: { action, level, user, user_ip, resource_type, resource_id,
  //           success, country, archived, start_date, end_date, page }
  list: (params = {}) =>
    client.get("/audit_logs/logs/", { params }),

  // GET    /api/audit_logs/logs/:id/
  detail: (id) =>
    client.get(`/audit_logs/logs/${id}/`),

  // GET    /api/audit_logs/logs/stats/
  // returns: { total, by_action, by_level, by_user, success_rate, errors_today }
  stats: () =>
    client.get("/audit_logs/logs/stats/"),

  // GET    /api/audit_logs/logs/:id/changes/
  // triggers: get_changes() backend method → { field: { old, new, changed } }
  getChanges: (id) =>
    client.get(`/audit_logs/logs/${id}/changes/`),

  // GET    /api/audit_logs/logs/?level=ERROR&level=CRITICAL
  errors: (params = {}) =>
    client.get("/audit_logs/logs/", { params: { ...params, level: ["ERROR", "CRITICAL"] } }),

  // GET    /api/audit_logs/logs/?action=SUSPICIOUS_LOGIN&action=BRUTE_FORCE_ATTEMPT&action=IP_BLOCK
  security: (params = {}) =>
    client.get("/audit_logs/logs/", {
      params: {
        ...params,
        level: "SECURITY",
      },
    }),

  // PATCH  /api/audit_logs/logs/:id/archive/
  archive: (id) =>
    client.patch(`/audit_logs/logs/${id}/archive/`),

  // DELETE /api/audit_logs/logs/cleanup/
  // body: { retention_days }
  cleanup: (retention_days = 365) =>
    client.delete("/audit_logs/logs/cleanup/", { data: { retention_days } }),
};

// ─────────────────────────────────────────────────────────────────
//  AuditLogConfig Model → /api/audit_logs/configs/
// ─────────────────────────────────────────────────────────────────
export const auditLogConfigAPI = {
  // GET    /api/audit_logs/configs/
  list: (params = {}) =>
    client.get("/audit_logs/configs/", { params }),

  // GET    /api/audit_logs/configs/:id/
  detail: (id) =>
    client.get(`/audit_logs/configs/${id}/`),

  // POST   /api/audit_logs/configs/
  // body: { action, enabled, log_level, log_request_body,
  //         log_response_body, retention_days, notify_admins }
  create: (data) =>
    client.post("/audit_logs/configs/", data),

  // PATCH  /api/audit_logs/configs/:id/
  update: (id, data) =>
    client.patch(`/audit_logs/configs/${id}/`, data),

  // DELETE /api/audit_logs/configs/:id/
  delete: (id) =>
    client.delete(`/audit_logs/configs/${id}/`),

  // PATCH  /api/audit_logs/configs/:id/toggle/
  // body: { enabled }
  toggle: (id, enabled) =>
    client.patch(`/audit_logs/configs/${id}/toggle/`, { enabled }),
};

// ─────────────────────────────────────────────────────────────────
//  AuditLogArchive Model → /api/audit_logs/archives/
// ─────────────────────────────────────────────────────────────────
export const auditLogArchiveAPI = {
  // GET    /api/audit_logs/archives/
  // params: { start_date, end_date, page }
  list: (params = {}) =>
    client.get("/audit_logs/archives/", { params }),

  // GET    /api/audit_logs/archives/:id/
  detail: (id) =>
    client.get(`/audit_logs/archives/${id}/`),

  // DELETE /api/audit_logs/archives/:id/
  delete: (id) =>
    client.delete(`/audit_logs/archives/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  AuditDashboard Model → /api/audit_logs/dashboards/
// ─────────────────────────────────────────────────────────────────
export const auditDashboardAPI = {
  // GET    /api/audit_logs/dashboards/
  list: (params = {}) =>
    client.get("/audit_logs/dashboards/", { params }),

  // GET    /api/audit_logs/dashboards/:id/
  detail: (id) =>
    client.get(`/audit_logs/dashboards/${id}/`),

  // POST   /api/audit_logs/dashboards/
  // body: { name, description, filters, columns, refresh_interval, is_default }
  create: (data) =>
    client.post("/audit_logs/dashboards/", data),

  // PATCH  /api/audit_logs/dashboards/:id/
  update: (id, data) =>
    client.patch(`/audit_logs/dashboards/${id}/`, data),

  // DELETE /api/audit_logs/dashboards/:id/
  delete: (id) =>
    client.delete(`/audit_logs/dashboards/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  AuditAlertRule Model → /api/audit_logs/alert-rules/
// ─────────────────────────────────────────────────────────────────
export const auditAlertRuleAPI = {
  // GET    /api/audit_logs/alert-rules/
  // params: { enabled, severity, action, page }
  list: (params = {}) =>
    client.get("/audit_logs/alert-rules/", { params }),

  // GET    /api/audit_logs/alert-rules/:id/
  detail: (id) =>
    client.get(`/audit_logs/alert-rules/${id}/`),

  // POST   /api/audit_logs/alert-rules/
  // body: { name, condition, action, action_config, severity, cooldown_minutes }
  create: (data) =>
    client.post("/audit_logs/alert-rules/", data),

  // PATCH  /api/audit_logs/alert-rules/:id/
  update: (id, data) =>
    client.patch(`/audit_logs/alert-rules/${id}/`, data),

  // DELETE /api/audit_logs/alert-rules/:id/
  delete: (id) =>
    client.delete(`/audit_logs/alert-rules/${id}/`),

  // PATCH  /api/audit_logs/alert-rules/:id/toggle/
  // body: { enabled }
  toggle: (id, enabled) =>
    client.patch(`/audit_logs/alert-rules/${id}/toggle/`, { enabled }),
};