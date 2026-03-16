// src/hooks/usePayoutQueue.js
// Bulletproof Payout Queue Hooks

import { useState, useCallback, useEffect, useRef } from 'react';
import { batchApi, itemApi, logApi, priorityApi } from '../api/endpoints/PayoutQueue';

function useSafeCall() {
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);
  return useCallback((fn) => (...args) => {
    const p = fn(...args);
    return p?.then ? p.catch(e => { if (mountedRef.current) throw e; }) : p;
  }, []);
}

const safeArray = (d) => Array.isArray(d) ? d : (d?.results ?? []);
const errMsg    = (e) => e?.response?.data?.detail || e?.response?.data?.error || e?.message || 'Something went wrong';

// ══════════════════════════════════════════════════════════════════
// useBatches
// ══════════════════════════════════════════════════════════════════
export function useBatches() {
  const [batches,  setBatches]  = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [total,    setTotal]    = useState(0);
  const safe = useSafeCall();

  const fetchBatches = useCallback(safe(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res  = await batchApi.list(params);
      const data = safeArray(res.data);
      setBatches(data);
      setTotal(res.data?.count ?? data.length);
      return data;
    } catch (e) { setError(errMsg(e)); throw e; }
    finally { setLoading(false); }
  }), []);

  const createBatch = useCallback(safe(async (data) => {
    const res = await batchApi.create(data);
    setBatches(p => [res.data, ...p]);
    return res.data;
  }), []);

  const cancelBatch = useCallback(safe(async (id) => {
    await batchApi.cancel(id);
    setBatches(p => p.map(b => b.id === id ? { ...b, status: 'CANCELLED' } : b));
  }), []);

  const processBatch = useCallback(safe(async (id, async_ = false) => {
    const res = async_ ? await batchApi.processAsync(id) : await batchApi.process(id);
    setBatches(p => p.map(b => b.id === id ? { ...b, status: async_ ? b.status : 'PROCESSING' } : b));
    return res.data;
  }), []);

  const getBatchStats = useCallback(safe(async (id) => {
    const res = await batchApi.statistics(id);
    return res.data;
  }), []);

  useEffect(() => { fetchBatches(); }, []);

  return { batches, loading, error, total, fetchBatches, createBatch, cancelBatch, processBatch, getBatchStats };
}

// ══════════════════════════════════════════════════════════════════
// usePayoutItems
// ══════════════════════════════════════════════════════════════════
export function usePayoutItems(batchId = null) {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [total,   setTotal]   = useState(0);
  const safe = useSafeCall();

  const fetchItems = useCallback(safe(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const p   = batchId ? { ...params, batch: batchId } : params;
      const res  = await itemApi.list(p);
      const data = safeArray(res.data);
      setItems(data);
      setTotal(res.data?.count ?? data.length);
      return data;
    } catch (e) { setError(errMsg(e)); throw e; }
    finally { setLoading(false); }
  }), [batchId]);

  const cancelItem = useCallback(safe(async (id) => {
    await itemApi.cancel(id);
    setItems(p => p.map(i => i.id === id ? { ...i, status: 'CANCELLED' } : i));
  }), []);

  useEffect(() => { fetchItems(); }, [batchId]);

  return { items, loading, error, total, fetchItems, cancelItem };
}

// ══════════════════════════════════════════════════════════════════
// useLogs
// ══════════════════════════════════════════════════════════════════
export function useLogs() {
  const [logs,    setLogs]    = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const safe = useSafeCall();

  const fetchLogs = useCallback(safe(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res  = await logApi.list(params);
      const data = safeArray(res.data);
      setLogs(data);
      return data;
    } catch (e) { setError(errMsg(e)); throw e; }
    finally { setLoading(false); }
  }), []);

  useEffect(() => { fetchLogs(); }, []);

  return { logs, loading, error, fetchLogs };
}

// ══════════════════════════════════════════════════════════════════
// usePriorities
// ══════════════════════════════════════════════════════════════════
export function usePriorities() {
  const [priorities, setPriorities] = useState([]);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const safe = useSafeCall();

  const fetchPriorities = useCallback(safe(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res  = await priorityApi.list(params);
      const data = safeArray(res.data);
      setPriorities(data);
      return data;
    } catch (e) { setError(errMsg(e)); throw e; }
    finally { setLoading(false); }
  }), []);

  useEffect(() => { fetchPriorities(); }, []);

  return { priorities, loading, error, fetchPriorities };
}
