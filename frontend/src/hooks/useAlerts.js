import { useState, useEffect, useCallback } from "react";
import {
  alertRuleAPI,
  alertLogAPI,
  alertNotificationAPI,
  alertScheduleAPI,
  alertEscalationAPI,
  alertTemplateAPI,
  alertAnalyticsAPI,
  alertGroupAPI,
  alertSuppressionAPI,
  systemHealthCheckAPI,
  alertRuleHistoryAPI,
  alertDashboardConfigAPI,
  systemMetricsAPI,
} from "../api/endpoints/alerts";

// ─────────────────────────────────────────────────────────────────
//  useAlertRules → AlertRule model
// ─────────────────────────────────────────────────────────────────
export const useAlertRules = (initialFilters = {}) => {
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { is_active, alert_type, severity, page }

  const fetchRules = useCallback(async () => {
    try {
      setLoading(true);
      const [rulesRes, statsRes] = await Promise.all([
        alertRuleAPI.list(filters),
        alertRuleAPI.stats(),
      ]);
      setRules(rulesRes.data?.results ?? rulesRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createRule = async (formData) => {
    try {
      const { data } = await alertRuleAPI.create(formData);
      setRules((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateRule = async (id, formData) => {
    try {
      const { data } = await alertRuleAPI.update(id, formData);
      setRules((prev) => prev.map((r) => (r.id === id ? data : r)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers pre_delete signal → history log + cache clear
  const deleteRule = async (id) => {
    try {
      await alertRuleAPI.delete(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers test fire → creates AlertLog entry
  const test = async (id) => {
    try {
      const { data } = await alertRuleAPI.test(id);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers bulk_update_status() QuerySet method
  const bulkUpdateStatus = async (ids, is_active) => {
    try {
      await alertRuleAPI.bulkUpdateStatus(ids, is_active);
      setRules((prev) =>
        prev.map((r) => (ids.includes(r.id) ? { ...r, is_active } : r))
      );
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // ActiveAlertRuleManager → is_active=true
  const fetchActive = async () => {
    try {
      const { data } = await alertRuleAPI.active();
      setRules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // high_severity QuerySet → severity=high/critical
  const fetchHighSeverity = async () => {
    try {
      const { data } = await alertRuleAPI.highSeverity();
      setRules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchRules(); }, [fetchRules]);

  return {
    rules, stats, loading, error, filters, setFilters,
    createRule, updateRule, deleteRule, test, bulkUpdateStatus,
    fetchActive,       // ActiveAlertRuleManager
    fetchHighSeverity, // high_severity QuerySet
    refetch: fetchRules,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertLogs → AlertLog model
// ─────────────────────────────────────────────────────────────────
export const useAlertLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { rule, is_resolved, severity, escalation_level, page }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const [logsRes, statsRes] = await Promise.all([
        alertLogAPI.list(filters),
        alertLogAPI.stats(),
      ]);
      setLogs(logsRes.data?.results ?? logsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load alert logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const resolve = async (id, note = "") => {
    try {
      const { data } = await alertLogAPI.resolve(id, note);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers bulk_resolve() QuerySet method
  const bulkResolve = async (ids, note = "") => {
    try {
      await alertLogAPI.bulkResolve(ids, note);
      setLogs((prev) =>
        prev.map((l) => (ids.includes(l.id) ? { ...l, is_resolved: true } : l))
      );
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // ResolvedAlertManager → is_resolved=true
  const fetchResolved = async () => {
    try {
      const { data } = await alertLogAPI.resolved();
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // UnresolvedAlertManager → is_resolved=false
  const fetchUnresolved = async () => {
    try {
      const { data } = await alertLogAPI.unresolved();
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs, stats, loading, error, filters, setFilters,
    resolve, bulkResolve,
    fetchResolved,   // ResolvedAlertManager
    fetchUnresolved, // UnresolvedAlertManager
    refetch: fetchLogs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertNotifications → Notification model
// ─────────────────────────────────────────────────────────────────
export const useAlertNotifications = (initialFilters = {}) => {
  const [notifications, setNotifications] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, notification_type, alert_log, recipient, page }

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const [notifRes, statsRes] = await Promise.all([
        alertNotificationAPI.list(filters),
        alertNotificationAPI.stats(),
      ]);
      setNotifications(notifRes.data?.results ?? notifRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // triggers can_retry() check → resend
  const retry = async (id) => {
    try {
      const { data } = await alertNotificationAPI.retry(id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? data : n)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchNotifications(); }, [fetchNotifications]);

  return {
    notifications, stats, loading, error, filters, setFilters,
    retry,
    refetch: fetchNotifications,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertSchedules → AlertSchedule model
// ─────────────────────────────────────────────────────────────────
export const useAlertSchedules = (initialFilters = {}) => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchSchedules = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertScheduleAPI.list(filters);
      setSchedules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createSchedule = async (formData) => {
    try {
      const { data } = await alertScheduleAPI.create(formData);
      setSchedules((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateSchedule = async (id, formData) => {
    try {
      const { data } = await alertScheduleAPI.update(id, formData);
      setSchedules((prev) => prev.map((s) => (s.id === id ? data : s)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteSchedule = async (id) => {
    try {
      await alertScheduleAPI.delete(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers get_active_schedules() backend classmethod
  const fetchActiveNow = async () => {
    try {
      const { data } = await alertScheduleAPI.activeNow();
      setSchedules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

  return {
    schedules, loading, error, filters, setFilters,
    createSchedule, updateSchedule, deleteSchedule,
    fetchActiveNow, // get_active_schedules()
    refetch: fetchSchedules,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertEscalations → AlertEscalation model
// ─────────────────────────────────────────────────────────────────
export const useAlertEscalations = (initialFilters = {}) => {
  const [escalations, setEscalations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchEscalations = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertEscalationAPI.list(filters);
      setEscalations(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load escalations");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createEscalation = async (formData) => {
    try {
      const { data } = await alertEscalationAPI.create(formData);
      setEscalations((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateEscalation = async (id, formData) => {
    try {
      const { data } = await alertEscalationAPI.update(id, formData);
      setEscalations((prev) => prev.map((e) => (e.id === id ? data : e)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteEscalation = async (id) => {
    try {
      await alertEscalationAPI.delete(id);
      setEscalations((prev) => prev.filter((e) => e.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers escalate_alert(alert_log) backend method
  const escalate = async (escalationId, logId) => {
    try {
      const { data } = await alertEscalationAPI.escalate(escalationId, logId);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchEscalations(); }, [fetchEscalations]);

  return {
    escalations, loading, error, filters, setFilters,
    createEscalation, updateEscalation, deleteEscalation, escalate,
    refetch: fetchEscalations,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertGroups → AlertGroup model
// ─────────────────────────────────────────────────────────────────
export const useAlertGroups = (initialFilters = {}) => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchGroups = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertGroupAPI.list(filters);
      setGroups(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load alert groups");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createGroup = async (formData) => {
    try {
      const { data } = await alertGroupAPI.create(formData);
      setGroups((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateGroup = async (id, formData) => {
    try {
      const { data } = await alertGroupAPI.update(id, formData);
      setGroups((prev) => prev.map((g) => (g.id === id ? data : g)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteGroup = async (id) => {
    try {
      await alertGroupAPI.delete(id);
      setGroups((prev) => prev.filter((g) => g.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers send_group_alert() backend method
  const sendAlert = async (id) => {
    try {
      const { data } = await alertGroupAPI.sendAlert(id);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers update_cache() backend method
  const updateCache = async (id) => {
    try {
      await alertGroupAPI.updateCache(id);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchGroups(); }, [fetchGroups]);

  return {
    groups, loading, error, filters, setFilters,
    createGroup, updateGroup, deleteGroup, sendAlert, updateCache,
    refetch: fetchGroups,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertSuppressions → AlertSuppression model
// ─────────────────────────────────────────────────────────────────
export const useAlertSuppressions = (initialFilters = {}) => {
  const [suppressions, setSuppressions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchSuppressions = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertSuppressionAPI.list(filters);
      setSuppressions(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load suppressions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createSuppression = async (formData) => {
    try {
      const { data } = await alertSuppressionAPI.create(formData);
      setSuppressions((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateSuppression = async (id, formData) => {
    try {
      const { data } = await alertSuppressionAPI.update(id, formData);
      setSuppressions((prev) => prev.map((s) => (s.id === id ? data : s)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteSuppression = async (id) => {
    try {
      await alertSuppressionAPI.delete(id);
      setSuppressions((prev) => prev.filter((s) => s.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers get_active_suppressions() backend classmethod
  const fetchActiveNow = async () => {
    try {
      const { data } = await alertSuppressionAPI.activeNow();
      setSuppressions(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchSuppressions(); }, [fetchSuppressions]);

  return {
    suppressions, loading, error, filters, setFilters,
    createSuppression, updateSuppression, deleteSuppression,
    fetchActiveNow, // get_active_suppressions()
    refetch: fetchSuppressions,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useSystemHealthChecks → SystemHealthCheck model
// ─────────────────────────────────────────────────────────────────
export const useSystemHealthChecks = (initialFilters = {}) => {
  const [checks, setChecks] = useState([]);
  const [overallStatus, setOverallStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { check_type, status, is_active, page }

  const fetchChecks = useCallback(async () => {
    try {
      setLoading(true);
      const [checksRes, statusRes] = await Promise.all([
        systemHealthCheckAPI.list(filters),
        systemHealthCheckAPI.overallStatus(),
      ]);
      setChecks(checksRes.data?.results ?? checksRes.data);
      setOverallStatus(statusRes.data);
      // overallStatus: triggers get_overall_status() classmethod
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load health checks");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createCheck = async (formData) => {
    try {
      const { data } = await systemHealthCheckAPI.create(formData);
      setChecks((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateCheck = async (id, formData) => {
    try {
      const { data } = await systemHealthCheckAPI.update(id, formData);
      setChecks((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteCheck = async (id) => {
    try {
      await systemHealthCheckAPI.delete(id);
      setChecks((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers update_status() backend method → may trigger alert
  const run = async (id) => {
    try {
      const { data } = await systemHealthCheckAPI.run(id);
      setChecks((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchChecks(); }, [fetchChecks]);

  return {
    checks, overallStatus, loading, error, filters, setFilters,
    createCheck, updateCheck, deleteCheck, run,
    refetch: fetchChecks,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertAnalytics → AlertAnalytics model
// ─────────────────────────────────────────────────────────────────
export const useAlertAnalytics = (days = 7) => {
  const [analytics, setAnalytics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      // triggers get_latest_analytics() backend classmethod
      const { data } = await alertAnalyticsAPI.latest(days);
      setAnalytics(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [days]);

  // triggers generate_for_date() backend classmethod
  const generate = async (date, force_regenerate = false) => {
    try {
      const { data } = await alertAnalyticsAPI.generate(date, force_regenerate);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  return { analytics, loading, error, generate, refetch: fetchAnalytics };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertDashboardConfig → AlertDashboardConfig (OneToOne per user)
// ─────────────────────────────────────────────────────────────────
export const useAlertDashboardConfig = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertDashboardConfigAPI.get();
      setConfig(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard config");
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = async (formData) => {
    try {
      const { data } = await alertDashboardConfigAPI.update(formData);
      setConfig(data);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers reset_to_defaults() backend method
  const reset = async () => {
    try {
      const { data } = await alertDashboardConfigAPI.reset();
      setConfig(data);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  return { config, loading, error, updateConfig, reset, refetch: fetchConfig };
};

// ─────────────────────────────────────────────────────────────────
//  useSystemMetrics → SystemMetrics model
// ─────────────────────────────────────────────────────────────────
export const useSystemMetrics = () => {
  const [latest, setLatest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLatest = useCallback(async () => {
    try {
      setLoading(true);
      // triggers get_latest() backend classmethod
      const { data } = await systemMetricsAPI.latest();
      setLatest(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load system metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchLatest(); }, [fetchLatest]);

  return { latest, loading, error, refetch: fetchLatest };
};

// ─────────────────────────────────────────────────────────────────
//  useAlertRuleHistory → AlertRuleHistory model (read-only audit)
// ─────────────────────────────────────────────────────────────────
export const useAlertRuleHistory = (initialFilters = {}) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { rule, action, changed_by, page }

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await alertRuleHistoryAPI.list(filters);
      setHistory(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load rule history");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  return { history, loading, error, filters, setFilters, refetch: fetchHistory };
};