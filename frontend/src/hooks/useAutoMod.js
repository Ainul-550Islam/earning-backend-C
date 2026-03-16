// src/hooks/useAutoMod.js
import { useState, useCallback, useEffect, useRef } from 'react';
import { ruleApi, submissionApi, scanApi, botApi, dashboardApi } from '../api/endpoints/AutoMod';

const safeArr = (d) => Array.isArray(d) ? d : (d?.results ?? d?.items ?? []);
export const errMsg = (e) => {
  if (!e) return 'Unknown error';
  const d = e?.response?.data;
  if (!d) return e.message || 'Error';
  if (typeof d === 'string') return d;
  if (d.detail) return d.detail;
  if (d.error)  return d.error;
  return Object.entries(d).map(([k,v]) => `${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
};

function useSafeCall() {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  return useCallback(fn => (...args) => {
    const p = fn(...args);
    return p?.then ? p.catch(e => { if (!mounted.current) return; throw e; }) : p;
  }, []);
}

function useList(fetcher, deps=[]) {
  const [data,    setData]    = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [total,   setTotal]   = useState(0);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  const fetch = useCallback(async (params={}) => {
    setLoading(true); setError(null);
    try {
      const res = await fetcher(params);
      if (!mounted.current) return;
      const arr = safeArr(res.data);
      setData(arr);
      setTotal(res.data?.count ?? arr.length);
      return arr;
    } catch(e) {
      if (!mounted.current) return;
      setError(errMsg(e)); throw e;
    }
    finally { if (mounted.current) setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { fetch(); }, deps);
  return { data, loading, error, total, refetch: fetch, setData };
}

// ── Rules ──────────────────────────────────────────────────────────
export function useRules() {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const { data: rules, loading, error, total, refetch, setData } = useList(ruleApi.list);

  const createRule = useCallback(async d => {
    const res = await ruleApi.create(d);
    if (!mounted.current) return;
    setData(p => [res.data, ...p]);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateRule = useCallback(async (id, d) => {
    const res = await ruleApi.update(id, d);
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleteRule = useCallback(async id => {
    await ruleApi.delete(id);
    if (!mounted.current) return;
    setData(p => p.filter(x => x.id !== id));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleRule = useCallback(async id => {
    const res = await ruleApi.toggle(id);
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? { ...x, is_active: res.data?.is_active ?? !x.is_active } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { rules, loading, error, total, refetch, createRule, updateRule, deleteRule, toggleRule };
}

// ── Submissions ────────────────────────────────────────────────────
export function useSubmissions(filters={}) {
  const key = JSON.stringify(filters);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetcher = useCallback(p => submissionApi.list({ ...filters, ...p }), [key]);
  const { data: submissions, loading, error, total, refetch, setData } = useList(fetcher, [key]);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);

  const fetchStats = useCallback(async () => {
    const res = await submissionApi.stats();
    if (!mounted.current) return;
    setStats(res.data);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchQueue = useCallback(async () => {
    const res = await submissionApi.queue();
    if (!mounted.current) return;
    setQueue(safeArr(res.data));
    return safeArr(res.data);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchStats(); }, []);

  const reviewSubmission = useCallback(async (id, action, note='', flagReason='') => {
    if (!mounted.current) return;
    const res = await submissionApi.review(id, { action, note, flag_reason: flagReason });
    setData(p => p.map(x => x.id === id ? res.data : x));
    setQueue(p => p.filter(x => x.id !== id));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rescanSubmission = useCallback(async (id, scanType='combined') => {
    const res = await submissionApi.rescan(id, { scan_type: scanType });
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? { ...x, status: 'scanning' } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const bulkAction = useCallback(async (ids, action, note='') => {
    const res = await submissionApi.bulkAction({ submission_ids: ids, action, note });
    if (!mounted.current) return;
    await refetch();
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    submissions, loading, error, total, refetch,
    stats, queue, fetchQueue, fetchStats,
    reviewSubmission, rescanSubmission, bulkAction,
  };
}

// ── Bots ───────────────────────────────────────────────────────────
export function useBots() {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const { data: bots, loading, error, refetch, setData } = useList(botApi.list);

  const createBot = useCallback(async d => {
    const res = await botApi.create(d);
    if (!mounted.current) return;
    setData(p => [res.data, ...p]);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateBot = useCallback(async (id, d) => {
    const res = await botApi.update(id, d);
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleteBot = useCallback(async id => {
    await botApi.delete(id);
    if (!mounted.current) return;
    setData(p => p.filter(x => x.id !== id));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startBot = useCallback(async id => {
    const res = await botApi.start(id);
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? { ...x, status: 'running' } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopBot = useCallback(async id => {
    const res = await botApi.stop(id);
    if (!mounted.current) return;
    setData(p => p.map(x => x.id === id ? { ...x, status: 'idle' } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getBotHealth = useCallback(async id => {
    const res = await botApi.health(id);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { bots, loading, error, refetch, createBot, updateBot, deleteBot, startBot, stopBot, getBotHealth };
}

// ── Dashboard ──────────────────────────────────────────────────────
export function useDashboard() {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await dashboardApi.get();
      if (!mounted.current) return;
      setData(res.data);
      return res.data;
    } catch(e) { if (mounted.current) setError(errMsg(e)); }
    finally    { if (mounted.current) setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetch(); }, []);
  return { data, loading, error, refetch: fetch };
}