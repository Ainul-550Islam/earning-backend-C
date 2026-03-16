// src/hooks/useSecurity.js
import { useState, useEffect, useCallback } from 'react';
import securityAPI from '../api/endpoints/security';


// ─── 1. Security Dashboard ────────────────────────────────────────────────────
export const useSecurityDashboard = () => {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      // ✅ correct endpoint: /api/security/dashboards/overview/
      const res = await securityAPI.getDashboard();
      setDashboard(res.data);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Security dashboard load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const d = dashboard || {};
  const summary     = d.summary     || {};
  const riskAnalysis= d.risk_analysis|| {};

  return {
    dashboard,
    loading, error,
    refetch: fetchDashboard,
    // shortcuts
    totalThreats:     d.active_threats || summary.total_threats || 0,
    threatsBlocked:   d.blocked_today  || summary.threats_blocked || 0,
    threatsPending:   d.risk_alerts    || 0,
    highRiskUsers:    riskAnalysis.high_risk_users     || 0,
    criticalRiskUsers:riskAnalysis.critical_risk_users || 0,
    totalUsers:       d.total_devices  || 0,
    blockedIPs:       d.blocked_ips    || 0,
  };
};


// ─── 2. Security Logs ─────────────────────────────────────────────────────────
export const useSecurityLogs = (initialParams = {}) => {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      // ✅ stats endpoint: /api/security/security-logs/statistics/
      const [logsRes, statsRes] = await Promise.allSettled([
        securityAPI.getLogs(params),
        securityAPI.getLogStats(),
      ]);
      if (logsRes.status  === 'fulfilled') setLogs(logsRes.value.data?.results || logsRes.value.data || []);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Security logs load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs, stats, loading, error,
    setParams, refetch: fetchLogs,
    criticalLogs: (Array.isArray(logs) ? logs : []).filter(l => l.severity === 'critical'),
  };
};


// ─── 3. Devices ───────────────────────────────────────────────────────────────
export const useDevices = (initialParams = {}) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchDevices = useCallback(async () => {
    try {
      setLoading(true);
      const res = await securityAPI.getDevices(params);
      setDevices(res.data.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Devices load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const flagDevice = async (id, data) => {
    await securityAPI.flagDevice(id, data);
    fetchDevices();
  };

  const arr = Array.isArray(devices) ? devices : [];
  return {
    devices, loading, error,
    setParams, refetch: fetchDevices,
    flagDevice,
    suspiciousCount: arr.filter(d => (d.risk_score || 0) >= 50).length,
    rootedCount:     arr.filter(d => d.is_rooted).length,
    emulatorCount:   arr.filter(d => d.is_emulator).length,
  };
};


// ─── 4. User Bans ─────────────────────────────────────────────────────────────
export const useUserBans = (initialParams = { is_active_ban: true }) => {
  const [bans, setBans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [banning, setBanning] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchBans = useCallback(async () => {
    try {
      setLoading(true);
      const res = await securityAPI.getBans(params);
      setBans(res.data.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Bans load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchBans(); }, [fetchBans]);

  const banUser = async (data) => {
    setBanning(true);
    try {
      await securityAPI.banUser(data);
      fetchBans();
    } finally {
      setBanning(false);
    }
  };

  const unbanUser = async (id, reason = '') => {
    await securityAPI.unbanUser(id, reason);
    fetchBans();
  };

  const arr = Array.isArray(bans) ? bans : [];
  return {
    bans, loading, banning, error,
    setParams, refetch: fetchBans,
    banUser, unbanUser,
    permanentBans: arr.filter(b => b.is_permanent).length,
    temporaryBans: arr.filter(b => !b.is_permanent).length,
  };
};


// ─── 5. IP Blacklist ──────────────────────────────────────────────────────────
export const useIPBlacklist = (initialParams = { is_active: true }) => {
  const [ips, setIPs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      // ✅ stats: /api/security/ip-blacklist/stats/
      const [listRes, statsRes] = await Promise.allSettled([
        securityAPI.getBlacklist(params),
        securityAPI.getBlacklistStats(),
      ]);
      if (listRes.status  === 'fulfilled') setIPs(listRes.value.data?.results || listRes.value.data || []);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'IP blacklist load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const blockIP = async (data) => {
    await securityAPI.blockIP(data);
    fetchAll();
  };

  const unblockIP = async (id, reason = '') => {
    await securityAPI.unblockIP(id, reason);
    fetchAll();
  };

  const arr = Array.isArray(ips) ? ips : [];
  return {
    ips, stats, loading, error,
    setParams, refetch: fetchAll,
    blockIP, unblockIP,
    criticalIPs: arr.filter(ip =>
      ip.threat_level === 'critical' || ip.threat_level === 'confirmed_attacker'
    ),
  };
};


// ─── 6. Audit Trail ───────────────────────────────────────────────────────────
export const useAuditTrail = (initialParams = {}) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const res = await securityAPI.getAuditTrail(params);
      setLogs(res.data.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Audit trail load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return { logs, loading, error, setParams, refetch: fetchLogs };
};


// ─── 7. Maintenance Mode ──────────────────────────────────────────────────────
export const useMaintenance = () => {
  const [maintenance, setMaintenance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMaintenance = useCallback(async () => {
    try {
      setLoading(true);
      const res = await securityAPI.getMaintenanceStatus();
      const data = res.data?.results?.[0] || (Array.isArray(res.data) ? res.data[0] : res.data) || null;
      setMaintenance(data);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Maintenance status load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchMaintenance(); }, [fetchMaintenance]);

  const startMaintenance = async (data) => {
    await securityAPI.startMaintenance(data);
    fetchMaintenance();
  };

  const endMaintenance = async (id) => {
    await securityAPI.endMaintenance(id);
    fetchMaintenance();
  };

  return {
    maintenance,
    isMaintenanceActive: maintenance?.is_active || false,
    loading, error,
    refetch: fetchMaintenance,
    startMaintenance, endMaintenance,
  };
};


// ─── 8. Sessions ─────────────────────────────────────────────────────────────
export const useSessions = (initialParams = { is_active: true }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await securityAPI.getSessions(params);
      setSessions(res.data.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.message || err.response?.data?.detail || 'Sessions load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const terminateSession = async (id, reason = '') => {
    await securityAPI.terminateSession(id, reason);
    fetchSessions();
  };

  const arr = Array.isArray(sessions) ? sessions : [];
  return {
    sessions, loading, error,
    setParams, refetch: fetchSessions,
    terminateSession,
    compromisedSessions: arr.filter(s => s.is_compromised),
  };
};