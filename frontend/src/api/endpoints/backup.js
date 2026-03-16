import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  Backup Model → /api/backup/backups/
// ─────────────────────────────────────────────────────────────────
export const backupAPI = {
  // GET    /api/backup/backups/
  // params: { status, backup_type, storage_type, database_name,
  //           is_healthy, is_verified, retention_policy, is_permanent,
  //           created_by, page }
  list: (params = {}) =>
    client.get("/backup/backups/", { params }),

  // GET    /api/backup/backups/:id/
  detail: (id) =>
    client.get(`/backup/backups/${id}/`),

  // POST   /api/backup/backups/
  create: (data) =>
    client.post("/backup/backups/", data),

  // PATCH  /api/backup/backups/:id/
  update: (id, data) =>
    client.patch(`/backup/backups/${id}/`, data),

  // DELETE /api/backup/backups/:id/
  // triggers: backup_pre_delete signal → delete_backup_file()
  delete: (id) =>
    client.delete(`/backup/backups/${id}/`),

  // GET    /api/backup/backups/stats/
  // returns: { total, completed, failed, running, total_size, healthy_count }
  stats: () =>
    client.get("/backup/backups/stats/"),

  // POST   /api/backup/backups/:id/verify/
  // triggers: mark_as_verified() backend method
  // body: { notes, verification_method }
  verify: (id, notes = "", verification_method = "manual") =>
    client.post(`/backup/backups/${id}/verify/`, { notes, verification_method }),

  // POST   /api/backup/backups/:id/health_check/
  // triggers: check_health() → verify_backup_health_task (celery)
  checkHealth: (id) =>
    client.post(`/backup/backups/${id}/health_check/`),

  // POST   /api/backup/backups/:id/restore/
  // triggers: create_restoration_record() backend method
  // body: { restoration_type, tables, notes }
  restore: (id, data = {}) =>
    client.post(`/backup/backups/${id}/restore/`, data),

  // GET    /api/backup/backups/?status=completed&is_healthy=true  (HealthyBackupManager)
  healthy: (params = {}) =>
    client.get("/backup/backups/", { params: { ...params, status: "completed", is_healthy: true } }),

  // GET    /api/backup/backups/?is_expired=true  (ExpiredBackupManager)
  expired: (params = {}) =>
    client.get("/backup/backups/", { params: { ...params, is_expired: true } }),
};

// ─────────────────────────────────────────────────────────────────
//  BackupStorageLocation Model → /api/backup/storage-locations/
// ─────────────────────────────────────────────────────────────────
export const storageLocationAPI = {
  // GET    /api/backup/storage-locations/
  // params: { storage_type, status, is_default, page }
  list: (params = {}) =>
    client.get("/backup/storage-locations/", { params }),

  // GET    /api/backup/storage-locations/:id/
  detail: (id) =>
    client.get(`/backup/storage-locations/${id}/`),

  // POST   /api/backup/storage-locations/
  create: (data) =>
    client.post("/backup/storage-locations/", data),

  // PATCH  /api/backup/storage-locations/:id/
  update: (id, data) =>
    client.patch(`/backup/storage-locations/${id}/`, data),

  // DELETE /api/backup/storage-locations/:id/
  delete: (id) =>
    client.delete(`/backup/storage-locations/${id}/`),

  // POST   /api/backup/storage-locations/:id/update_space/
  // triggers: update_space_usage() backend method
  updateSpace: (id) =>
    client.post(`/backup/storage-locations/${id}/update_space/`),

  // POST   /api/backup/storage-locations/:id/test_connection/
  testConnection: (id) =>
    client.post(`/backup/storage-locations/${id}/test_connection/`),
};

// ─────────────────────────────────────────────────────────────────
//  BackupSchedule Model → /api/backup/schedules/
// ─────────────────────────────────────────────────────────────────
export const backupScheduleAPI = {
  // GET    /api/backup/schedules/
  // params: { frequency, is_active, is_paused, backup_type, page }
  list: (params = {}) =>
    client.get("/backup/schedules/", { params }),

  // GET    /api/backup/schedules/:id/
  detail: (id) =>
    client.get(`/backup/schedules/${id}/`),

  // POST   /api/backup/schedules/
  create: (data) =>
    client.post("/backup/schedules/", data),

  // PATCH  /api/backup/schedules/:id/
  update: (id, data) =>
    client.patch(`/backup/schedules/${id}/`, data),

  // DELETE /api/backup/schedules/:id/
  delete: (id) =>
    client.delete(`/backup/schedules/${id}/`),

  // POST   /api/backup/schedules/:id/pause/
  // triggers: pause() backend method
  pause: (id) =>
    client.post(`/backup/schedules/${id}/pause/`),

  // POST   /api/backup/schedules/:id/resume/
  // triggers: resume() backend method → recalculates next_run
  resume: (id) =>
    client.post(`/backup/schedules/${id}/resume/`),

  // POST   /api/backup/schedules/:id/execute/
  // triggers: execute_schedule() → execute_backup_schedule_task (celery)
  execute: (id) =>
    client.post(`/backup/schedules/${id}/execute/`),
};

// ─────────────────────────────────────────────────────────────────
//  BackupRestoration Model → /api/backup/restorations/
// ─────────────────────────────────────────────────────────────────
export const backupRestorationAPI = {
  // GET    /api/backup/restorations/
  // params: { status, restoration_type, backup, initiated_by, page }
  list: (params = {}) =>
    client.get("/backup/restorations/", { params }),

  // GET    /api/backup/restorations/:id/
  detail: (id) =>
    client.get(`/backup/restorations/${id}/`),

  // PATCH  /api/backup/restorations/:id/
  // body: { status, notes, verification_passed }
  update: (id, data) =>
    client.patch(`/backup/restorations/${id}/`, data),
};

// ─────────────────────────────────────────────────────────────────
//  BackupLog Model → /api/backup/logs/
// ─────────────────────────────────────────────────────────────────
export const backupLogAPI = {
  // GET    /api/backup/logs/
  // params: { level, category, action, source, backup,
  //           requires_attention, is_processed, is_archived, page }
  list: (params = {}) =>
    client.get("/backup/logs/", { params }),

  // GET    /api/backup/logs/:id/
  detail: (id) =>
    client.get(`/backup/logs/${id}/`),

  // GET    /api/backup/logs/stats/
  // returns: { total, errors, warnings, requiring_attention }
  stats: () =>
    client.get("/backup/logs/stats/"),

  // GET    /api/backup/logs/?level=error&level=critical  (get_error_logs)
  errors: (days = 7) =>
    client.get("/backup/logs/", { params: { level: ["error", "critical"], days } }),

  // GET    /api/backup/logs/?requires_attention=true&is_processed=false
  attention: () =>
    client.get("/backup/logs/", { params: { requires_attention: true, is_processed: false } }),

  // PATCH  /api/backup/logs/:id/mark_processed/
  // triggers: mark_as_processed() backend method
  markProcessed: (id) =>
    client.patch(`/backup/logs/${id}/mark_processed/`),

  // PATCH  /api/backup/logs/:id/archive/
  // triggers: archive() backend method
  archive: (id) =>
    client.patch(`/backup/logs/${id}/archive/`),

  // DELETE /api/backup/logs/cleanup/
  // triggers: cleanup_old_logs() backend classmethod
  // body: { days }
  cleanup: (days = 90) =>
    client.delete("/backup/logs/cleanup/", { data: { days } }),
};

// ─────────────────────────────────────────────────────────────────
//  RetentionPolicy Model → /api/backup/retention-policies/
// ─────────────────────────────────────────────────────────────────
export const retentionPolicyAPI = {
  list: () =>
    client.get("/backup/retention-policies/"),

  detail: (id) =>
    client.get(`/backup/retention-policies/${id}/`),

  create: (data) =>
    client.post("/backup/retention-policies/", data),

  update: (id, data) =>
    client.patch(`/backup/retention-policies/${id}/`, data),

  delete: (id) =>
    client.delete(`/backup/retention-policies/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  BackupNotificationConfig → /api/backup/notification-configs/
// ─────────────────────────────────────────────────────────────────
export const backupNotificationConfigAPI = {
  list: () =>
    client.get("/backup/notification-configs/"),

  detail: (id) =>
    client.get(`/backup/notification-configs/${id}/`),

  create: (data) =>
    client.post("/backup/notification-configs/", data),

  update: (id, data) =>
    client.patch(`/backup/notification-configs/${id}/`, data),

  delete: (id) =>
    client.delete(`/backup/notification-configs/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  DeltaBackupTracker Model → /api/backup/delta-trackers/
// ─────────────────────────────────────────────────────────────────
export const deltaTrackerAPI = {
  // GET    /api/backup/delta-trackers/
  // params: { parent_backup, child_backup, page }
  list: (params = {}) =>
    client.get("/backup/delta-trackers/", { params }),

  // GET    /api/backup/delta-trackers/:id/
  detail: (id) =>
    client.get(`/backup/delta-trackers/${id}/`),
};