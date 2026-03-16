// src/hooks/usePostback.js
// ═══════════════════════════════════════════════════════════════════════════
//  Bulletproof React hooks — every state handled, no silent failures
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useRef, useState } from "react";
import postbackAPI from "../api/endpoint/postback";

// ── Shared state shape ────────────────────────────────────────────────────────
const idle    = () => ({ data: null, loading: false, error: null });
const loading = (prev) => ({ ...prev, loading: true,  error: null });
const success = (data)  => ({ data,   loading: false, error: null });
const failure = (err)   => ({ data: null, loading: false, error: err?.message ?? "Unknown error" });


// ═══════════════════════════════════════════════════════════════════════════
//  useDashboard
//  GET /api/postback/admin/dashboard/
// ═══════════════════════════════════════════════════════════════════════════
export const useDashboard = (autoFetch = true) => {
  const [state, setState] = useState(idle());
  const intervalRef = useRef(null);

  const fetch = useCallback(async () => {
    setState((p) => loading(p));
    const { data, error } = await postbackAPI.dashboard.get();
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, []);

  // auto-poll every 30 seconds
  const startPolling = useCallback((ms = 30_000) => {
    stopPolling();
    intervalRef.current = setInterval(fetch, ms);
  }, [fetch]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (autoFetch) fetch();
    return () => stopPolling();
  }, [autoFetch, fetch, stopPolling]);

  return {
    ...state,
    refetch: fetch,
    startPolling,
    stopPolling,
    // safe accessors with fallbacks
    summary:        state.data?.summary        ?? {},
    perNetwork:     state.data?.per_network    ?? [],
    activeNetworks: state.data?.active_networks ?? 0,
    periodHours:    state.data?.period_hours   ?? 24,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useNetworkList
//  GET /api/postback/networks/
// ═══════════════════════════════════════════════════════════════════════════
export const useNetworkList = (initialParams = {}) => {
  const [state, setState]   = useState(idle());
  const [params, setParams] = useState(initialParams);

  const fetch = useCallback(async (overrideParams) => {
    setState((p) => loading(p));
    const p = overrideParams ?? params;
    const { data, error } = await postbackAPI.network.list(p);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const updateFilter = useCallback((newParams = {}) => {
    setParams((prev) => ({ ...prev, ...newParams }));
  }, []);

  return {
    ...state,
    refetch:      fetch,
    updateFilter,
    results:      state.data?.results ?? [],
    count:        state.data?.count   ?? 0,
    next:         state.data?.next    ?? null,
    previous:     state.data?.previous ?? null,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useNetworkDetail
//  GET /api/postback/networks/{id}/
// ═══════════════════════════════════════════════════════════════════════════
export const useNetworkDetail = (id) => {
  const [state, setState] = useState(idle());

  const fetch = useCallback(async () => {
    if (!id) return;
    setState((p) => loading(p));
    const { data, error } = await postbackAPI.network.retrieve(id);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [id]);

  useEffect(() => { fetch(); }, [fetch]);

  return { ...state, refetch: fetch };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useNetworkCRUD
//  create / update / partialUpdate / destroy + activate / deactivate
// ═══════════════════════════════════════════════════════════════════════════
export const useNetworkCRUD = () => {
  const [creating,    setCreating]    = useState(false);
  const [updating,    setUpdating]    = useState(false);
  const [destroying,  setDestroying]  = useState(false);
  const [toggling,    setToggling]    = useState(false);
  const [actionError, setActionError] = useState(null);

  const clearError = () => setActionError(null);

  // ── create ──────────────────────────────────────────────────────────────
  const createNetwork = useCallback(async (payload) => {
    setCreating(true); setActionError(null);
    const result = await postbackAPI.network.create(payload);
    if (result.error) setActionError(result.error.message);
    setCreating(false);
    return result;
  }, []);

  // ── full update ─────────────────────────────────────────────────────────
  const updateNetwork = useCallback(async (id, payload) => {
    setUpdating(true); setActionError(null);
    const result = await postbackAPI.network.update(id, payload);
    if (result.error) setActionError(result.error.message);
    setUpdating(false);
    return result;
  }, []);

  // ── partial update ──────────────────────────────────────────────────────
  const patchNetwork = useCallback(async (id, payload) => {
    setUpdating(true); setActionError(null);
    const result = await postbackAPI.network.partialUpdate(id, payload);
    if (result.error) setActionError(result.error.message);
    setUpdating(false);
    return result;
  }, []);

  // ── delete ──────────────────────────────────────────────────────────────
  const deleteNetwork = useCallback(async (id) => {
    setDestroying(true); setActionError(null);
    const result = await postbackAPI.network.destroy(id);
    if (result.error) setActionError(result.error.message);
    setDestroying(false);
    return result;
  }, []);

  // ── activate ────────────────────────────────────────────────────────────
  const activateNetwork = useCallback(async (id) => {
    setToggling(true); setActionError(null);
    const result = await postbackAPI.network.activate(id);
    if (result.error) setActionError(result.error.message);
    setToggling(false);
    return result;
  }, []);

  // ── deactivate ──────────────────────────────────────────────────────────
  const deactivateNetwork = useCallback(async (id) => {
    setToggling(true); setActionError(null);
    const result = await postbackAPI.network.deactivate(id);
    if (result.error) setActionError(result.error.message);
    setToggling(false);
    return result;
  }, []);

  return {
    creating, updating, destroying, toggling, actionError, clearError,
    createNetwork, updateNetwork, patchNetwork,
    deleteNetwork, activateNetwork, deactivateNetwork,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useNetworkStats
//  GET /api/postback/networks/{id}/stats/
// ═══════════════════════════════════════════════════════════════════════════
export const useNetworkStats = (id) => {
  const [state, setState] = useState(idle());

  const fetch = useCallback(async () => {
    if (!id) return;
    setState((p) => loading(p));
    const { data, error } = await postbackAPI.network.stats(id);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [id]);

  useEffect(() => { fetch(); }, [fetch]);

  return {
    ...state,
    refetch:   fetch,
    total:     state.data?.total     ?? 0,
    rewarded:  state.data?.rewarded  ?? 0,
    rejected:  state.data?.rejected  ?? 0,
    duplicate: state.data?.duplicate ?? 0,
    failed:    state.data?.failed    ?? 0,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useValidators
//  GET/POST /api/postback/networks/{id}/validators/
// ═══════════════════════════════════════════════════════════════════════════
export const useValidators = (networkId) => {
  const [state,    setState]   = useState(idle());
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  const fetchValidators = useCallback(async () => {
    if (!networkId) return;
    setState((p) => loading(p));
    const { data, error } = await postbackAPI.network.listValidators(networkId);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [networkId]);

  useEffect(() => { fetchValidators(); }, [fetchValidators]);

  const createValidator = useCallback(async (payload) => {
    setCreating(true); setCreateError(null);
    const result = await postbackAPI.network.createValidator(networkId, payload);
    if (result.error) setCreateError(result.error.message);
    else await fetchValidators(); // refresh list
    setCreating(false);
    return result;
  }, [networkId, fetchValidators]);

  return {
    ...state,
    validators:      state.data ?? [],
    refetch:         fetchValidators,
    createValidator,
    creating,
    createError,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  usePostbackLogs
//  GET /api/postback/logs/
// ═══════════════════════════════════════════════════════════════════════════
export const usePostbackLogs = (initialParams = {}) => {
  const [state,  setState]  = useState(idle());
  const [params, setParams] = useState(initialParams);

  const fetch = useCallback(async (overrideParams) => {
    setState((p) => loading(p));
    const p = overrideParams ?? params;
    const { data, error } = await postbackAPI.logs.list(p);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const updateFilter = useCallback((newParams = {}) => {
    setParams((prev) => ({ ...prev, ...newParams, page: 1 }));
  }, []);

  return {
    ...state,
    refetch:      fetch,
    updateFilter,
    logs:         state.data?.results  ?? [],
    count:        state.data?.count    ?? 0,
    next:         state.data?.next     ?? null,
    previous:     state.data?.previous ?? null,
  };
};


// ═══════════════════════════════════════════════════════════════════════════
//  usePostbackLogDetail
//  GET /api/postback/logs/{id}/
// ═══════════════════════════════════════════════════════════════════════════
export const usePostbackLogDetail = (id) => {
  const [state, setState] = useState(idle());

  const fetch = useCallback(async () => {
    if (!id) return;
    setState((p) => loading(p));
    const { data, error } = await postbackAPI.logs.retrieve(id);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [id]);

  useEffect(() => { fetch(); }, [fetch]);

  return { ...state, refetch: fetch };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useRetryLog
//  POST /api/postback/logs/{id}/retry/
//  POST /api/postback/admin/logs/{id}/retry/
// ═══════════════════════════════════════════════════════════════════════════
export const useRetryLog = () => {
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const [retrySuccess, setRetrySuccess] = useState(false);

  const reset = () => {
    setRetrying(false);
    setRetryError(null);
    setRetrySuccess(false);
  };

  // viewset retry: POST /api/postback/logs/{id}/retry/
  const retryLog = useCallback(async (id) => {
    setRetrying(true); setRetryError(null); setRetrySuccess(false);
    const { data, error } = await postbackAPI.logs.retry(id);
    if (error) setRetryError(error.message);
    else setRetrySuccess(true);
    setRetrying(false);
    return { data, error };
  }, []);

  // admin retry: POST /api/postback/admin/logs/{id}/retry/
  const adminRetryLog = useCallback(async (id) => {
    setRetrying(true); setRetryError(null); setRetrySuccess(false);
    const { data, error } = await postbackAPI.admin.retryLog(id);
    if (error) setRetryError(error.message);
    else setRetrySuccess(true);
    setRetrying(false);
    return { data, error };
  }, []);

  return { retrying, retryError, retrySuccess, retryLog, adminRetryLog, reset };
};


// ═══════════════════════════════════════════════════════════════════════════
//  useDuplicates
//  GET/DELETE /api/postback/duplicates/
// ═══════════════════════════════════════════════════════════════════════════
export const useDuplicates = (initialParams = {}) => {
  const [state,     setState]    = useState(idle());
  const [params,    setParams]   = useState(initialParams);
  const [clearing,  setClearing] = useState(false);
  const [clearError, setClearError] = useState(null);

  const fetch = useCallback(async (overrideParams) => {
    setState((p) => loading(p));
    const p = overrideParams ?? params;
    const { data, error } = await postbackAPI.duplicates.list(p);
    setState(error ? failure(error) : success(data));
    return { data, error };
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  const updateFilter = useCallback((newParams = {}) => {
    setParams((prev) => ({ ...prev, ...newParams }));
  }, []);

  // DELETE — clear a dedup entry so the lead can be re-accepted
  const clearEntry = useCallback(async (id) => {
    setClearing(true); setClearError(null);
    const { data, error } = await postbackAPI.duplicates.destroy(id);
    if (error) setClearError(error.message);
    else await fetch(); // refresh list
    setClearing(false);
    return { data, error };
  }, [fetch]);

  return {
    ...state,
    duplicates:   state.data?.results  ?? [],
    count:        state.data?.count    ?? 0,
    next:         state.data?.next     ?? null,
    previous:     state.data?.previous ?? null,
    refetch:      fetch,
    updateFilter,
    clearing,
    clearError,
    clearEntry,
  };
};