import { useState, useEffect, useCallback } from "react";
import {
  backupAPI,
  storageLocationAPI,
  backupScheduleAPI,
  backupRestorationAPI,
  backupLogAPI,
  retentionPolicyAPI,
  backupNotificationConfigAPI,
  deltaTrackerAPI,
} from "../api/endpoints/backup";

// ─────────────────────────────────────────────────────────────────
//  useBackups → Backup model
// ─────────────────────────────────────────────────────────────────
export const useBackups = (initialFilters = {}) => {
  const [backups, setBackups] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, backup_type, storage_type, database_name,
  //            is_healthy, is_verified, retention_policy, is_permanent, page }

  const fetchBackups = useCallback(async () => {
    try {
      setLoading(true);
      const [backupsRes, statsRes] = await Promise.all([
        backupAPI.list(filters),
        backupAPI.stats(),
      ]);
      setBackups(backupsRes.data?.results ?? backupsRes.data);
      setStats(statsRes.data);
      // stats: { total, completed, failed, running, total_size, healthy_count }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load backups");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createBackup = async (formData) => {
    try {
      const { data } = await backupAPI.create(formData);
      setBackups((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateBackup = async (id, formData) => {
    try {
      const { data } = await backupAPI.update(id, formData);
      setBackups((prev) => prev.map((b) => (b.id === id ? data : b)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers pre_delete signal → delete_backup_file()
  const deleteBackup = async (id) => {
    try {
      await backupAPI.delete(id);
      setBackups((prev) => prev.filter((b) => b.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers mark_as_verified() backend method
  const verify = async (id, notes = "", method = "manual") => {
    try {
      const { data } = await backupAPI.verify(id, notes, method);
      setBackups((prev) => prev.map((b) => (b.id === id ? data : b)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers check_health() → celery task
  const checkHealth = async (id) => {
    try {
      await backupAPI.checkHealth(id);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers create_restoration_record() backend method
  const restore = async (id, restorationData = {}) => {
    try {
      const { data } = await backupAPI.restore(id, restorationData);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // HealthyBackupManager → status=completed & is_healthy=true
  const fetchHealthy = async () => {
    try {
      const { data } = await backupAPI.healthy();
      setBackups(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // ExpiredBackupManager → is_expired=true
  const fetchExpired = async () => {
    try {
      const { data } = await backupAPI.expired();
      setBackups(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchBackups(); }, [fetchBackups]);

  return {
    backups, stats, loading, error, filters, setFilters,
    createBackup, updateBackup, deleteBackup,
    verify, checkHealth, restore,
    fetchHealthy,  // HealthyBackupManager
    fetchExpired,  // ExpiredBackupManager
    refetch: fetchBackups,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useStorageLocations → BackupStorageLocation model
// ─────────────────────────────────────────────────────────────────
export const useStorageLocations = (initialFilters = {}) => {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchLocations = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await storageLocationAPI.list(filters);
      setLocations(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load storage locations");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createLocation = async (formData) => {
    try {
      const { data } = await storageLocationAPI.create(formData);
      setLocations((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateLocation = async (id, formData) => {
    try {
      const { data } = await storageLocationAPI.update(id, formData);
      setLocations((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteLocation = async (id) => {
    try {
      await storageLocationAPI.delete(id);
      setLocations((prev) => prev.filter((l) => l.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers update_space_usage() backend method
  const updateSpace = async (id) => {
    try {
      const { data } = await storageLocationAPI.updateSpace(id);
      setLocations((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const testConnection = async (id) => {
    try {
      const { data } = await storageLocationAPI.testConnection(id);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchLocations(); }, [fetchLocations]);

  return {
    locations, loading, error, filters, setFilters,
    createLocation, updateLocation, deleteLocation,
    updateSpace, testConnection,
    refetch: fetchLocations,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useBackupSchedules → BackupSchedule model
// ─────────────────────────────────────────────────────────────────
export const useBackupSchedules = (initialFilters = {}) => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { frequency, is_active, is_paused, backup_type, page }

  const fetchSchedules = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await backupScheduleAPI.list(filters);
      setSchedules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createSchedule = async (formData) => {
    try {
      const { data } = await backupScheduleAPI.create(formData);
      setSchedules((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateSchedule = async (id, formData) => {
    try {
      const { data } = await backupScheduleAPI.update(id, formData);
      setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteSchedule = async (id) => {
    try {
      await backupScheduleAPI.delete(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers pause() backend method → next_run=null
  const pause = async (id) => {
    try {
      const { data } = await backupScheduleAPI.pause(id);
      setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers resume() backend method → recalculates next_run
  const resume = async (id) => {
    try {
      const { data } = await backupScheduleAPI.resume(id);
      setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers execute_schedule() → celery task
  const execute = async (id) => {
    try {
      await backupScheduleAPI.execute(id);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

  return {
    schedules, loading, error, filters, setFilters,
    createSchedule, updateSchedule, deleteSchedule,
    pause, resume, execute,
    refetch: fetchSchedules,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useBackupRestorations → BackupRestoration model
// ─────────────────────────────────────────────────────────────────
export const useBackupRestorations = (initialFilters = {}) => {
  const [restorations, setRestorations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, restoration_type, backup, initiated_by, page }

  const fetchRestorations = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await backupRestorationAPI.list(filters);
      setRestorations(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load restorations");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const updateRestoration = async (id, formData) => {
    try {
      const { data } = await backupRestorationAPI.update(id, formData);
      setRestorations((prev) => prev.map((r) => (r.id === id ? data : r)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchRestorations(); }, [fetchRestorations]);

  return {
    restorations, loading, error, filters, setFilters,
    updateRestoration,
    refetch: fetchRestorations,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useBackupLogs → BackupLog model
// ─────────────────────────────────────────────────────────────────
export const useBackupLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { level, category, action, source, backup,
  //            requires_attention, is_processed, is_archived, page }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const [logsRes, statsRes] = await Promise.all([
        backupLogAPI.list(filters),
        backupLogAPI.stats(),
      ]);
      setLogs(logsRes.data?.results ?? logsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // triggers mark_as_processed() backend method
  const markProcessed = async (id) => {
    try {
      const { data } = await backupLogAPI.markProcessed(id);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers archive() backend method
  const archive = async (id) => {
    try {
      const { data } = await backupLogAPI.archive(id);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers cleanup_old_logs() backend classmethod
  const cleanup = async (days = 90) => {
    try {
      const { data } = await backupLogAPI.cleanup(days);
      await fetchLogs();
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // get_error_logs() → level=error/critical
  const fetchErrors = async (days = 7) => {
    try {
      const { data } = await backupLogAPI.errors(days);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // get_logs_requiring_attention()
  const fetchAttention = async () => {
    try {
      const { data } = await backupLogAPI.attention();
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs, stats, loading, error, filters, setFilters,
    markProcessed, archive, cleanup,
    fetchErrors,    // get_error_logs()
    fetchAttention, // get_logs_requiring_attention()
    refetch: fetchLogs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useRetentionPolicies → RetentionPolicy model
// ─────────────────────────────────────────────────────────────────
export const useRetentionPolicies = () => {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPolicies = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await retentionPolicyAPI.list();
      setPolicies(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load retention policies");
    } finally {
      setLoading(false);
    }
  }, []);

  const createPolicy = async (formData) => {
    try {
      const { data } = await retentionPolicyAPI.create(formData);
      setPolicies((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updatePolicy = async (id, formData) => {
    try {
      const { data } = await retentionPolicyAPI.update(id, formData);
      setPolicies((prev) => prev.map((p) => (p.id === id ? data : p)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deletePolicy = async (id) => {
    try {
      await retentionPolicyAPI.delete(id);
      setPolicies((prev) => prev.filter((p) => p.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchPolicies(); }, [fetchPolicies]);

  return { policies, loading, error, createPolicy, updatePolicy, deletePolicy, refetch: fetchPolicies };
};

// ─────────────────────────────────────────────────────────────────
//  useDeltaTrackers → DeltaBackupTracker model
// ─────────────────────────────────────────────────────────────────
export const useDeltaTrackers = (initialFilters = {}) => {
  const [trackers, setTrackers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { parent_backup, child_backup, page }

  const fetchTrackers = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await deltaTrackerAPI.list(filters);
      setTrackers(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load delta trackers");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchTrackers(); }, [fetchTrackers]);

  return { trackers, loading, error, filters, setFilters, refetch: fetchTrackers };
};