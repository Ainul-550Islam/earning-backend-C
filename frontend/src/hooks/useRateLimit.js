// src/hooks/useRateLimit.js
import { useState, useEffect, useCallback } from 'react';
import rateLimitAPI from '../api/endpoints/rateLimit';

const safeArr = d => Array.isArray(d) ? d : (d?.results ?? []);

// ─── 1. Dashboard ─────────────────────────────────────────
export const useRateLimitDashboard = (timeframe = '24h') => {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const res = await rateLimitAPI.getDashboard({ timeframe });
      setData(res.data);
    } catch(e) {
      setError(e?.response?.data?.detail || e?.message || 'Dashboard load failed');
    } finally { setLoading(false); }
  }, [timeframe]);

  useEffect(() => { fetch(); }, [fetch]);

  const d = data || {};
  const s = d.summary || {};
  return {
    data, loading, error, refetch: fetch,
    totalConfigs:   s.total_configs    || 0,
    activeConfigs:  s.active_configs   || 0,
    totalRequests:  s.total_requests   || 0,
    blockedRequests:s.blocked_requests || 0,
    blockRate:      s.block_rate       || 0,
    userStats:      d.user_statistics  || {},
    topConfigs:     d.top_configs      || [],
    recentBlocked:  d.recent_blocked   || [],
  };
};

// ─── 2. Configs ───────────────────────────────────────────
export const useConfigs = (initialParams = {}) => {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [params,  setParams]  = useState(initialParams);

  const fetch = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const res = await rateLimitAPI.getConfigs(params);
      setConfigs(safeArr(res.data));
    } catch(e) {
      setError(e?.response?.data?.detail || e?.message || 'Load failed');
    } finally { setLoading(false); }
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const list = safeArr(configs);
  return {
    configs: list, loading, error,
    setParams, refetch: fetch,
    activeCount:   list.filter(c => c.is_active).length,
    inactiveCount: list.filter(c => !c.is_active).length,
  };
};

// ─── 3. Logs ──────────────────────────────────────────────
export const useRateLimitLogs = (initialParams = {}) => {
  const [logs,    setLogs]    = useState([]);
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [params,  setParams]  = useState(initialParams);

  const fetch = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const timeframe = params.timeframe || '24h';
      const [logsRes, statsRes] = await Promise.allSettled([
        rateLimitAPI.getLogs(params),
        rateLimitAPI.getLogStats({ timeframe }),
      ]);
      // Fix 1: handle rejected cases explicitly
      if (logsRes.status  === 'fulfilled') {
        setLogs(safeArr(logsRes.value.data));
      } else {
        setError(logsRes.reason?.response?.data?.detail || logsRes.reason?.message || 'Logs load failed');
      }
      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      } else {
        // Stats failure is non-critical — log but don't override logs error
        console.warn('Rate limit stats fetch failed:', statsRes.reason?.message);
      }
    } catch(e) {
      setError(e?.response?.data?.detail || e?.message || 'Load failed');
    } finally { setLoading(false); }
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const list = safeArr(logs);
  return {
    logs: list, stats, loading, error,
    setParams, refetch: fetch,
    blockedCount:  list.filter(l => l.status === 'blocked').length,
    allowedCount:  list.filter(l => l.status === 'allowed').length,
    exceededCount: list.filter(l => l.status === 'exceeded').length,
  };
};

// ─── 4. User Profiles ─────────────────────────────────────
export const useUserProfiles = (initialParams = {}) => {
  const [profiles, setProfiles] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [params,   setParams]   = useState(initialParams);

  const fetch = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const res = await rateLimitAPI.getProfiles(params);
      setProfiles(safeArr(res.data));
    } catch(e) {
      setError(e?.response?.data?.detail || e?.message || 'Load failed');
    } finally { setLoading(false); }
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const list = safeArr(profiles);
  return {
    profiles: list, loading, error,
    setParams, refetch: fetch,
    premiumCount:    list.filter(p => p.is_premium).length,
    suspiciousCount: list.filter(p => (p.suspicion_score || 0) >= 50).length,
  };
};