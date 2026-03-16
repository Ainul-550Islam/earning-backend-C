// src/hooks/useVersionControl.js
// Bulletproof hooks for Version Control page

import { useState, useCallback, useEffect, useRef } from 'react';
import { policyApi, maintenanceApi, redirectApi } from '../api/endpoints/VersionControl';

// ── Generic safe caller ───────────────────────────────────────────
function useSafeCall() {
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);
  return useCallback((fn) => (...args) => {
    const promise = fn(...args);
    if (promise?.then) {
      return promise.catch(err => {
        if (!mountedRef.current) return;
        throw err;
      });
    }
    return promise;
  }, []);
}

// ══════════════════════════════════════════════════════════════════
// usePolicies — App Update Policies
// ══════════════════════════════════════════════════════════════════
export function usePolicies() {
  const [policies, setPolicies] = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  const fetchPolicies = useCallback(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res = await policyApi.list(params);
      if (!mountedRef.current) return;
      const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setPolicies(data);
      return data;
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err?.response?.data?.detail || err.message || 'Failed to load policies';
      setError(msg); throw err;
    } finally { if (mountedRef.current) setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createPolicy = useCallback(async (data) => {
    const res = await policyApi.create(data);
    if (!mountedRef.current) return;
    setPolicies(p => [res.data, ...p]);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updatePolicy = useCallback(async (id, data) => {
    const res = await policyApi.update(id, data);
    if (!mountedRef.current) return;
    setPolicies(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fix 3: delete with error handling — rollback on failure
  const deletePolicy = useCallback(async (id) => {
    const prev = policies;
    setPolicies(p => p.filter(x => x.id !== id));
    try {
      await policyApi.delete(id);
    } catch (err) {
      if (mountedRef.current) setPolicies(prev);
      throw err;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policies]);

  const activatePolicy = useCallback(async (id) => {
    const res = await policyApi.activate(id);
    if (!mountedRef.current) return;
    setPolicies(p => p.map(x => x.id === id ? { ...x, ...res.data } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fix 2: use res.data for deactivate update
  const deactivatePolicy = useCallback(async (id) => {
    const res = await policyApi.deactivate(id);
    if (!mountedRef.current) return;
    setPolicies(p => p.map(x => x.id === id ? { ...x, ...(res.data || { status: 'inactive' }) } : x));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchPolicies(); }, []);

  return { policies, loading, error, fetchPolicies, createPolicy, updatePolicy, deletePolicy, activatePolicy, deactivatePolicy };
}

// ══════════════════════════════════════════════════════════════════
// useMaintenance — Maintenance Schedules
// ══════════════════════════════════════════════════════════════════
export function useMaintenance() {
  const [schedules, setSchedules] = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  const fetchSchedules = useCallback(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res = await maintenanceApi.list(params);
      if (!mountedRef.current) return;
      const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setSchedules(data);
      return data;
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err?.response?.data?.detail || err.message || 'Failed to load schedules';
      setError(msg); throw err;
    } finally { if (mountedRef.current) setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createSchedule = useCallback(async (data) => {
    const res = await maintenanceApi.create(data);
    if (!mountedRef.current) return;
    setSchedules(p => [res.data, ...p]);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateSchedule = useCallback(async (id, data) => {
    const res = await maintenanceApi.update(id, data);
    if (!mountedRef.current) return;
    setSchedules(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fix 3: delete with rollback on failure
  const deleteSchedule = useCallback(async (id) => {
    const prev = schedules;
    setSchedules(p => p.filter(x => x.id !== id));
    try {
      await maintenanceApi.delete(id);
    } catch (err) {
      if (mountedRef.current) setSchedules(prev);
      throw err;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schedules]);

  const startMaintenance = useCallback(async (id) => {
    const res = await maintenanceApi.start(id);
    if (!mountedRef.current) return;
    setSchedules(p => p.map(x => x.id === id ? { ...x, ...res.data } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const endMaintenance = useCallback(async (id) => {
    const res = await maintenanceApi.end(id);
    if (!mountedRef.current) return;
    setSchedules(p => p.map(x => x.id === id ? { ...x, ...res.data } : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fix 2: use res.data for cancelMaintenance update
  const cancelMaintenance = useCallback(async (id) => {
    const res = await maintenanceApi.cancel(id);
    if (!mountedRef.current) return;
    setSchedules(p => p.map(x => x.id === id ? { ...x, ...(res.data || { status: 'CANCELLED' }) } : x));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchSchedules(); }, []);

  return { schedules, loading, error, fetchSchedules, createSchedule, updateSchedule, deleteSchedule, startMaintenance, endMaintenance, cancelMaintenance };
}

// ══════════════════════════════════════════════════════════════════
// useRedirects — Platform Redirects
// ══════════════════════════════════════════════════════════════════
export function useRedirects() {
  const [redirects, setRedirects] = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  const fetchRedirects = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await redirectApi.list();
      if (!mountedRef.current) return;
      const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setRedirects(data);
      return data;
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err?.response?.data?.detail || err.message || 'Failed to load redirects';
      setError(msg); throw err;
    } finally { if (mountedRef.current) setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createRedirect = useCallback(async (data) => {
    const res = await redirectApi.create(data);
    if (!mountedRef.current) return;
    setRedirects(p => [res.data, ...p]);
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateRedirect = useCallback(async (id, data) => {
    const res = await redirectApi.update(id, data);
    if (!mountedRef.current) return;
    setRedirects(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fix 3: delete with rollback on failure
  const deleteRedirect = useCallback(async (id) => {
    const prev = redirects;
    setRedirects(p => p.filter(x => x.id !== id));
    try {
      await redirectApi.delete(id);
    } catch (err) {
      if (mountedRef.current) setRedirects(prev);
      throw err;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redirects]);

  const toggleRedirect = useCallback(async (id, isActive) => {
    const res = await redirectApi.update(id, { is_active: isActive });
    if (!mountedRef.current) return;
    setRedirects(p => p.map(x => x.id === id ? res.data : x));
    return res.data;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchRedirects(); }, []);

  return { redirects, loading, error, fetchRedirects, createRedirect, updateRedirect, deleteRedirect, toggleRedirect };
}