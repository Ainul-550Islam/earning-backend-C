// src/hooks/useAnalytics.js
import { useState, useEffect, useCallback, useRef } from 'react';
import analyticsAPI from '../api/endpoints/analytics';


// ─── 1. Revenue Trend (Dashboard Chart) ───────────────────────────────────
export const useRevenueTrend = (initialParams = { period: 'daily', days: 7 }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchRevenue = useCallback(async () => {
    try {
      setLoading(true);
      const res = await analyticsAPI.getRevenueTrend(params);
      setData(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Revenue data load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchRevenue(); }, [fetchRevenue]);

  // Chart এর জন্য formatted data
  const chartData = data.map(item => ({
    date: item.period_start?.slice(0, 10),
    revenue: parseFloat(item.revenue_total || 0),
    profit: parseFloat(item.net_profit || 0),
    users: item.active_users || 0,
    withdrawals: parseFloat(item.total_withdrawals || 0),
  }));

  return { data, chartData, loading, error, setParams, refetch: fetchRevenue };
};


// ─── 2. Real-Time Metrics (Live Dashboard) ────────────────────────────────
export const useRealTimeMetrics = (intervalMs = 30000) => {
  const [metrics, setMetrics] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await analyticsAPI.getRealTimeMetrics();
      const raw = res.data.results || res.data;

      // metric_type অনুযায়ী group করা
      const grouped = {};
      raw.forEach(m => {
        grouped[m.metric_type] = m.value;
      });
      setMetrics(grouped);
      setLoading(false);
    } catch (err) {
      setError(err.response?.data?.message || 'Realtime metrics failed');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    // Auto-refresh every intervalMs
    intervalRef.current = setInterval(fetchMetrics, intervalMs);
    return () => clearInterval(intervalRef.current);
  }, [fetchMetrics, intervalMs]);

  return {
    metrics,
    // Shortcuts for Dashboard cards
    activeUsers: metrics['active_users'] || 0,
    revenuePerMinute: metrics['revenue_per_minute'] || 0,
    apiRequests: metrics['api_requests'] || 0,
    errorRate: metrics['error_rate'] || 0,
    loading, error,
    refetch: fetchMetrics,
  };
};


// ─── 3. Retention Analytics ───────────────────────────────────────────────
export const useRetention = (cohortType = 'weekly') => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await analyticsAPI.getRetentionAnalytics({ cohort_type: cohortType });
        setData(res.data.results || res.data);
      } catch (err) {
        setError(err.response?.data?.message || 'Retention data load failed');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [cohortType]);

  return { data, loading, error };
};


// ─── 4. Alert History ─────────────────────────────────────────────────────
export const useAlerts = (initialParams = { is_resolved: false }) => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const res = await analyticsAPI.getAlertHistory(params);
      setAlerts(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Alerts load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const resolveAlert = async (id, notes = '') => {
    await analyticsAPI.resolveAlert(id, notes);
    fetchAlerts();
  };

  return {
    alerts, loading, error,
    setParams, refetch: fetchAlerts,
    resolveAlert,
    criticalCount: alerts.filter(a => a.severity === 'critical').length,
    warningCount: alerts.filter(a => a.severity === 'warning').length,
  };
};


// ─── 5. Offer Performance ─────────────────────────────────────────────────
export const useOfferPerformance = (params = {}) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await analyticsAPI.getOfferPerformance(params);
        setData(res.data.results || res.data);
      } catch (err) {
        setError(err.response?.data?.message || 'Offer performance load failed');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  return { data, loading, error };
};


// ─── 6. Reports ───────────────────────────────────────────────────────────
export const useReports = () => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const res = await analyticsAPI.getReports();
      setReports(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Reports load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  const generateReport = async (data) => {
    setGenerating(true);
    try {
      await analyticsAPI.generateReport(data);
      fetchReports();
    } finally {
      setGenerating(false);
    }
  };

  return { reports, loading, generating, error, refetch: fetchReports, generateReport };
};


// ─── 7. Funnel Analytics ──────────────────────────────────────────────────
export const useFunnel = (funnelType = 'user_signup') => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await analyticsAPI.getFunnelAnalytics({ funnel_type: funnelType });
        setData(res.data.results?.[0] || res.data[0] || null);
      } catch (err) {
        setError(err.response?.data?.message || 'Funnel data load failed');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [funnelType]);

  return { data, loading, error };
};