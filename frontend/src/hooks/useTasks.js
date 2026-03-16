// src/hooks/useTasks.js
import { useState, useEffect, useCallback } from 'react';
import tasksAPI from '../api/endpoints/tasks';


// ─── 1. Dashboard Stats ────────────────────────────────────────────────────
export const useTaskDashboardStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksAPI.getTaskDashboardStats();
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Stats load failed');
      setTasks([]); // Clear tasks on error to avoid stale data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, error, refetch: fetchStats };
};


// ─── 2. Tasks List ─────────────────────────────────────────────────────────
export const useTasks = (initialParams = {}) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);
  const [selected, setSelected] = useState([]);

  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksAPI.getTasks(params);
      setTasks(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Tasks load failed');
         setTasks([]); // Clear tasks on error to avoid stale data
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  // Bulk actions
  const bulkActivate = async () => {
    if (!selected.length) return;
    await tasksAPI.bulkActivate(selected);
    setSelected([]);
    fetchTasks();
  };

  const bulkDeactivate = async () => {
    if (!selected.length) return;
    await tasksAPI.bulkDeactivate(selected);
    setSelected([]);
    fetchTasks();
  };

  const deleteTask = async (taskId) => {
    await tasksAPI.deleteTask(taskId);
    fetchTasks();
  };

  return {
    tasks, loading, error,
    params, setParams,
    selected, setSelected,
    refetch: fetchTasks,
    bulkActivate, bulkDeactivate, deleteTask,
  };
};


// ─── 3. Task Completions ───────────────────────────────────────────────────
export const useTaskCompletions = (initialParams = {}) => {
  const [completions, setCompletions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchCompletions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksAPI.getCompletions(params);
      setCompletions(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Completions load failed');
        setCompletions([]); // Clear completions on error to avoid stale data
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchCompletions(); }, [fetchCompletions]);

  const verifyCompletion = async (completionId) => {
    await tasksAPI.verifyCompletion(completionId);
    fetchCompletions();
  };

  return {
    completions, loading, error,
    setParams, refetch: fetchCompletions,
    verifyCompletion,
  };
};


// ─── 4. Admin Profit Summary (Dashboard Revenue Card) ──────────────────────
export const useAdminProfit = (days = 30) => {
  const [summary, setSummary] = useState(null);
  const [dailyData, setDailyData] = useState([]);
  const [bySource, setBySource] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProfit = useCallback(async () => {
    try {
      setLoading(true);
      const [summaryRes, dailyRes, sourceRes] = await Promise.all([
        tasksAPI.getAdminProfitSummary(days),
        tasksAPI.getDailyProfit(days),
        tasksAPI.getProfitBySource(days),
      ]);
      setSummary(summaryRes.data);
      setDailyData(dailyRes.data);
      setBySource(sourceRes.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Profit data load failed');
        setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { fetchProfit(); }, [fetchProfit]);

  return {
    summary, dailyData, bySource,
    loading, error,
    refetch: fetchProfit,
  };
};


// ─── 5. Admin Ledger List ──────────────────────────────────────────────────
export const useAdminLedger = (initialParams = {}) => {
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchLedger = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksAPI.getAdminLedger(params);
      setLedger(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Ledger load failed');
        setLedger([]); // Clear ledger on error to avoid stale data
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchLedger(); }, [fetchLedger]);

  return { ledger, loading, error, setParams, refetch: fetchLedger };
};