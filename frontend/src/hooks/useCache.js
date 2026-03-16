// src/hooks/useCache.js  —  COMPLETE CRUD HOOKS
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getCacheStats, getSystemStats, getCacheHealth,
  getUserProfile, getTaskDetail,
  getCacheKeys, setCacheKey, deleteCacheKey, deleteCachePattern,
  clearCache,
} from '../api/endpoints/cache';

// ── useCacheDashboard ─────────────────────────────────────────────────────────
export function useCacheDashboard(autoRefreshMs = 0) {
  const [stats,    setStats]    = useState(null);
  const [sysStats, setSysStats] = useState(null);
  const [health,   setHealth]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const timerRef = useRef(null);

  const fetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [cacheRes, sysRes, healthRes] = await Promise.allSettled([
        getCacheStats(), getSystemStats(), getCacheHealth(),
      ]);
      if (cacheRes.status  === 'fulfilled') setStats(cacheRes.value.data);
      if (sysRes.status    === 'fulfilled') setSysStats(sysRes.value.data);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
    } catch (e) {
      setError(e.message || 'Failed');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetch();
    if (autoRefreshMs > 0) { timerRef.current = setInterval(fetch, autoRefreshMs); }
    return () => clearInterval(timerRef.current);
  }, [fetch, autoRefreshMs]);

  return { stats, sysStats, health, loading, error, refetch: fetch };
}

// ── useCacheHealth ────────────────────────────────────────────────────────────
export function useCacheHealth() {
  const [health,  setHealth]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true); setError(null);
    try { const r = await getCacheHealth(); setHealth(r.data); }
    catch (e) { setError(e?.response?.data?.message || e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);
  return { health, loading, error, refetch: fetch };
}

// ── useCacheKeys  (READ — list keys) ─────────────────────────────────────────
export function useCacheKeys(initialPattern = '*') {
  const [keys,    setKeys]    = useState([]);
  const [count,   setCount]   = useState(0);
  const [pattern, setPattern] = useState(initialPattern);
  const [limit,   setLimit]   = useState(50);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await getCacheKeys(pattern, limit);
      setKeys(r.data?.keys || []);
      setCount(r.data?.count || 0);
    } catch (e) {
      setError(e?.response?.data?.error || e.message);
    } finally { setLoading(false); }
  }, [pattern, limit]);

  useEffect(() => { fetch(); }, [fetch]);
  return { keys, count, pattern, setPattern, limit, setLimit, loading, error, refetch: fetch };
}

// ── useCacheKeySet  (CREATE) ──────────────────────────────────────────────────
export function useCacheKeySet() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [success, setSuccess] = useState(false);

  const set = useCallback(async (key, value, timeout = 300) => {
    setLoading(true); setError(null); setSuccess(false);
    try {
      const r = await setCacheKey(key, value, timeout);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
      return { success: true, data: r.data };
    } catch (e) {
      const msg = e?.response?.data?.error || e.message || 'Failed to set key';
      setError(msg);
      return { success: false, error: msg };
    } finally { setLoading(false); }
  }, []);

  return { set, loading, error, success };
}

// ── useCacheKeyDelete  (DELETE specific) ─────────────────────────────────────
export function useCacheKeyDelete() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const deleteKey = useCallback(async (key) => {
    setLoading(true); setError(null);
    try {
      const r = await deleteCacheKey(key);
      return { success: true, deleted: r.data?.deleted };
    } catch (e) {
      const msg = e?.response?.data?.error || e.message;
      setError(msg);
      return { success: false, error: msg };
    } finally { setLoading(false); }
  }, []);

  const deletePattern = useCallback(async (pattern) => {
    setLoading(true); setError(null);
    try {
      const r = await deleteCachePattern(pattern);
      return { success: true, deleted: r.data?.deleted };
    } catch (e) {
      const msg = e?.response?.data?.error || e.message;
      setError(msg);
      return { success: false, error: msg };
    } finally { setLoading(false); }
  }, []);

  return { deleteKey, deletePattern, loading, error };
}

// ── useClearCache  (bulk DELETE) ─────────────────────────────────────────────
export function useClearCache() {
  const [clearing, setClearing] = useState(false);
  const [message,  setMessage]  = useState('');
  const [error,    setError]    = useState(null);

  const clear = useCallback(async (type = 'all') => {
    setClearing(true); setMessage(''); setError(null);
    try {
      const r = await clearCache(type);
      setMessage(r.data?.message || `✓ ${type.toUpperCase()} cache cleared!`);
      setTimeout(() => setMessage(''), 3000);
      return { success: true };
    } catch (e) {
      const msg = e?.response?.data?.error || 'Clear failed';
      setError(msg);
      setTimeout(() => setError(null), 3000);
      return { success: false, error: msg };
    } finally { setClearing(false); }
  }, []);

  return { clear, clearing, message, error };
}

// ── useCachedUserProfile ──────────────────────────────────────────────────────
export function useCachedUserProfile(userId) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    if (!userId) return;
    setLoading(true); setError(null);
    try { const r = await getUserProfile(userId); setProfile(r.data); }
    catch (e) { setError(e?.response?.data?.error || 'User not found'); }
    finally { setLoading(false); }
  }, [userId]);

  useEffect(() => { fetch(); }, [fetch]);
  return { profile, loading, error, refetch: fetch };
}

// ── useCachedTask ─────────────────────────────────────────────────────────────
export function useCachedTask(taskId) {
  const [task,    setTask]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async () => {
    if (!taskId) return;
    setLoading(true); setError(null);
    try { const r = await getTaskDetail(taskId); setTask(r.data); }
    catch (e) { setError(e?.response?.data?.error || 'Task not found'); }
    finally { setLoading(false); }
  }, [taskId]);

  useEffect(() => { fetch(); }, [fetch]);
  return { task, loading, error, refetch: fetch };
}