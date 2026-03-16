import { useState, useEffect, useCallback } from "react";
import {
  auditLogAPI,
  auditLogConfigAPI,
  auditLogArchiveAPI,
  auditDashboardAPI,
  auditAlertRuleAPI,
} from "../api/endpoints/auditLogs";

// ─────────────────────────────────────────────────────────────────
//  useAuditLogs → AuditLog model
// ─────────────────────────────────────────────────────────────────
export const useAuditLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { action, level, user, user_ip, resource_type,
  //            success, country, archived, start_date, end_date, page }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const [logsRes, statsRes] = await Promise.all([
        auditLogAPI.list(filters),
        auditLogAPI.stats(),
      ]);
      setLogs(logsRes.data?.results ?? logsRes.data);
      setStats(statsRes.data);
      // stats: { total, by_action, by_level, success_rate, errors_today }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // triggers get_changes() backend method
  // returns: { field: { old, new, changed } }
  const getChanges = async (id) => {
    try {
      const { data } = await auditLogAPI.getChanges(id);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const archive = async (id) => {
    try {
      const { data } = await auditLogAPI.archive(id);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const cleanup = async (retention_days = 365) => {
    try {
      const { data } = await auditLogAPI.cleanup(retention_days);
      await fetchLogs();
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // level=ERROR/CRITICAL filter
  const fetchErrors = async (params = {}) => {
    try {
      const { data } = await auditLogAPI.errors(params);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // level=SECURITY filter
  const fetchSecurity = async (params = {}) => {
    try {
      const { data } = await auditLogAPI.security(params);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs, stats, loading, error, filters, setFilters,
    getChanges, archive, cleanup,
    fetchErrors,    // ERROR + CRITICAL logs
    fetchSecurity,  // SECURITY level logs
    refetch: fetchLogs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAuditLogConfigs → AuditLogConfig model
// ─────────────────────────────────────────────────────────────────
export const useAuditLogConfigs = (initialFilters = {}) => {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchConfigs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await auditLogConfigAPI.list(filters);
      setConfigs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load configs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createConfig = async (formData) => {
    try {
      const { data } = await auditLogConfigAPI.create(formData);
      setConfigs((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateConfig = async (id, formData) => {
    try {
      const { data } = await auditLogConfigAPI.update(id, formData);
      setConfigs((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteConfig = async (id) => {
    try {
      await auditLogConfigAPI.delete(id);
      setConfigs((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const toggle = async (id, enabled) => {
    try {
      const { data } = await auditLogConfigAPI.toggle(id, enabled);
      setConfigs((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  return {
    configs, loading, error, filters, setFilters,
    createConfig, updateConfig, deleteConfig, toggle,
    refetch: fetchConfigs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAuditLogArchives → AuditLogArchive model
// ─────────────────────────────────────────────────────────────────
export const useAuditLogArchives = (initialFilters = {}) => {
  const [archives, setArchives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { start_date, end_date, page }

  const fetchArchives = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await auditLogArchiveAPI.list(filters);
      setArchives(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load archives");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const deleteArchive = async (id) => {
    try {
      await auditLogArchiveAPI.delete(id);
      setArchives((prev) => prev.filter((a) => a.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchArchives(); }, [fetchArchives]);

  return {
    archives, loading, error, filters, setFilters,
    deleteArchive,
    refetch: fetchArchives,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAuditDashboards → AuditDashboard model
// ─────────────────────────────────────────────────────────────────
export const useAuditDashboards = () => {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboards = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await auditDashboardAPI.list();
      setDashboards(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboards");
    } finally {
      setLoading(false);
    }
  }, []);

  const createDashboard = async (formData) => {
    try {
      const { data } = await auditDashboardAPI.create(formData);
      setDashboards((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateDashboard = async (id, formData) => {
    try {
      const { data } = await auditDashboardAPI.update(id, formData);
      setDashboards((prev) => prev.map((d) => (d.id === id ? data : d)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteDashboard = async (id) => {
    try {
      await auditDashboardAPI.delete(id);
      setDashboards((prev) => prev.filter((d) => d.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchDashboards(); }, [fetchDashboards]);

  return {
    dashboards, loading, error,
    createDashboard, updateDashboard, deleteDashboard,
    refetch: fetchDashboards,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAuditAlertRules → AuditAlertRule model
// ─────────────────────────────────────────────────────────────────
export const useAuditAlertRules = (initialFilters = {}) => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { enabled, severity, action, page }

  const fetchRules = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await auditAlertRuleAPI.list(filters);
      setRules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createRule = async (formData) => {
    try {
      const { data } = await auditAlertRuleAPI.create(formData);
      setRules((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateRule = async (id, formData) => {
    try {
      const { data } = await auditAlertRuleAPI.update(id, formData);
      setRules((prev) => prev.map((r) => (r.id === id ? data : r)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteRule = async (id) => {
    try {
      await auditAlertRuleAPI.delete(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const toggle = async (id, enabled) => {
    try {
      const { data } = await auditAlertRuleAPI.toggle(id, enabled);
      setRules((prev) => prev.map((r) => (r.id === id ? data : r)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchRules(); }, [fetchRules]);

  return {
    rules, loading, error, filters, setFilters,
    createRule, updateRule, deleteRule, toggle,
    refetch: fetchRules,
  };
};