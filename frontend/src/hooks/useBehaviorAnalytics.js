// =============================================================================
// src/hooks/useBehaviorAnalytics.js
// Custom React hooks — real API, axiosInstance, adminAccessToken
// =============================================================================

import { useState, useEffect, useCallback } from "react";
import {
  fetchDashboard,
  fetchAdminStats,
  fetchPaths,
  fetchPathById,
  createPath,
  closePath,
  addPathNodes,
  fetchSessionBySessionId,
  fetchClicks,
  recordClick,
  recordClicksBulk,
  fetchTopElements,
  fetchStayTimes,
  recordStayTime,
  fetchStayStats,
  fetchEngagementScores,
  fetchEngagementScoreById,
  recalculateEngagementScore,
  fetchEngagementSummary,
  recalculateMyEngagement,
  sendAnalyticsEvents,
} from "../api/behaviorAnalyticsApi";

// ── Generic async hook ────────────────────────────────────────────────────────
function useAsync(asyncFn, deps = [], runImmediately = true) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await asyncFn(...args);
      setData(result);
      return result;
    } catch (e) {
      setError(e.message ?? "Unknown error");
      return null;
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (runImmediately) execute();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runImmediately, ...deps]);

  return { data, loading, error, execute, setData };
}

// ── Generic paginated hook ────────────────────────────────────────────────────
function usePaginated(fetchFn, initialParams = {}) {
  const [params,  setParams]  = useState({ limit:10, offset:0, ordering:"-created_at", ...initialParams });
  const [items,   setItems]   = useState([]);
  const [count,   setCount]   = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async (overrideParams = null) => {
    setLoading(true);
    setError(null);
    try {
      const p    = overrideParams ?? params;
      const data = await fetchFn(p);
      const list = data?.results ?? (Array.isArray(data) ? data : []);
      setItems(list);
      setCount(data?.count ?? list.length);
    } catch (e) {
      setError(e.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [params, fetchFn]);

  useEffect(() => { fetch(); }, [params]);

  const goToPage = useCallback((page) => {
    setParams(prev => ({ ...prev, offset: (page - 1) * (prev.limit ?? 10) }));
  }, []);

  const currentPage = Math.floor((params.offset ?? 0) / (params.limit ?? 10)) + 1;
  const totalPages  = Math.max(1, Math.ceil(count / (params.limit ?? 10)));

  return { items, count, loading, error, params, setParams, currentPage, totalPages, goToPage, refetch: fetch };
}

// =============================================================================
// 1. useDashboard  — GET /api/analytics/dashboard/
// =============================================================================
export function useDashboard() {
  const { data, loading, error, execute } = useAsync(fetchDashboard, [], true);
  return { data, loading, error, refetch: execute };
}

// =============================================================================
// 2. useAdminStats  — GET /api/analytics/admin/stats/  (staff only)
// =============================================================================
export function useAdminStats() {
  const { data, loading, error, execute } = useAsync(fetchAdminStats, [], true);
  return { data, loading, error, refetch: execute };
}

// =============================================================================
// 3. usePaths  — GET /api/analytics/paths/  (paginated)
// =============================================================================
export function usePaths(initialParams = {}) {
  const { items: paths, count, loading, error, params, setParams,
          currentPage, totalPages, goToPage, refetch } =
    usePaginated(fetchPaths, { limit:10, offset:0, ordering:"-created_at", ...initialParams });

  return { paths, count, loading, error, params, setParams, currentPage, totalPages, goToPage, refetch };
}

// =============================================================================
// 4. usePathById  — GET /api/analytics/paths/:id/
// =============================================================================
export function usePathById(id) {
  const fn = useCallback(() => fetchPathById(id), [id]);
  const { data, loading, error, execute } = useAsync(fn, [id], !!id);
  return { path: data, loading, error, refetch: execute };
}

// =============================================================================
// 5. useCreatePath  — POST /api/analytics/paths/
// =============================================================================
export function useCreatePath() {
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [createdPath, setCreatedPath] = useState(null);

  const create = useCallback(async (data) => {
    setLoading(true); setError(null);
    try { const r = await createPath(data); setCreatedPath(r); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { create, loading, error, createdPath };
}

// =============================================================================
// 6. useClosePath  — POST /api/analytics/paths/:id/close/
// =============================================================================
export function useClosePath() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const close = useCallback(async (id, data = {}) => {
    setLoading(true); setError(null);
    try { return await closePath(id, data); }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { close, loading, error };
}

// =============================================================================
// 7. useAddPathNodes  — POST /api/analytics/paths/:id/add_nodes/
// =============================================================================
export function useAddPathNodes() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const addNodes = useCallback(async (id, nodes) => {
    setLoading(true); setError(null);
    try { return await addPathNodes(id, nodes); }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { addNodes, loading, error };
}

// =============================================================================
// 8. useSessionById  — GET /api/analytics/sessions/:session_id/
// =============================================================================
export function useSessionById(sessionId) {
  const fn = useCallback(() => fetchSessionBySessionId(sessionId), [sessionId]);
  const { data, loading, error, execute } = useAsync(fn, [sessionId], !!sessionId);
  return { session: data, loading, error, refetch: execute };
}

// =============================================================================
// 9. useClicks  — GET /api/analytics/clicks/  (paginated)
// =============================================================================
export function useClicks(initialParams = {}) {
  const { items: clicks, count, loading, error, params, setParams,
          currentPage, totalPages, goToPage, refetch } =
    usePaginated(fetchClicks, { limit:20, offset:0, ordering:"-clicked_at", ...initialParams });

  return { clicks, count, loading, error, params, setParams, currentPage, totalPages, goToPage, refetch };
}

// =============================================================================
// 10. useRecordClick  — POST /api/analytics/clicks/
// =============================================================================
export function useRecordClick() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const record = useCallback(async (data) => {
    setLoading(true); setError(null);
    try { return await recordClick(data); }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { record, loading, error };
}

// =============================================================================
// 11. useRecordClicksBulk  — POST /api/analytics/clicks/bulk/
// =============================================================================
export function useRecordClicksBulk() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [result,  setResult]  = useState(null);

  const recordBulk = useCallback(async (pathId, events) => {
    setLoading(true); setError(null);
    try { const r = await recordClicksBulk(pathId, events); setResult(r); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { recordBulk, loading, error, result };
}

// =============================================================================
// 12. useTopElements  — GET /api/analytics/clicks/top_elements/
// =============================================================================
export function useTopElements(limit = 10) {
  const fn = useCallback(() => fetchTopElements(limit), [limit]);
  const { data, loading, error, execute } = useAsync(fn, [limit], true);
  return { elements: Array.isArray(data) ? data : [], loading, error, refetch: execute };
}

// =============================================================================
// 13. useStayTimes  — GET /api/analytics/stay-times/  (paginated)
// =============================================================================
export function useStayTimes(initialParams = {}) {
  const { items: stayTimes, count, loading, error, params, setParams, refetch } =
    usePaginated(fetchStayTimes, { limit:20, offset:0, ordering:"-created_at", ...initialParams });

  return { stayTimes, count, loading, error, params, setParams, refetch };
}

// =============================================================================
// 14. useStayStats  — GET /api/analytics/stay-times/stats/
// =============================================================================
export function useStayStats() {
  const { data, loading, error, execute } = useAsync(fetchStayStats, [], true);
  return { stats: data, loading, error, refetch: execute };
}

// =============================================================================
// 15. useRecordStayTime  — POST /api/analytics/stay-times/
// =============================================================================
export function useRecordStayTime() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const record = useCallback(async (data) => {
    setLoading(true); setError(null);
    try { return await recordStayTime(data); }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { record, loading, error };
}

// =============================================================================
// 16. useEngagementScores  — GET /api/analytics/engagement-scores/  (paginated)
// =============================================================================
export function useEngagementScores(initialParams = {}) {
  const { items: scores, count, loading, error, params, setParams,
          currentPage, totalPages, goToPage, refetch } =
    usePaginated(fetchEngagementScores, { limit:10, offset:0, ordering:"-score", ...initialParams });

  return { scores, count, loading, error, params, setParams, currentPage, totalPages, goToPage, refetch };
}

// =============================================================================
// 17. useEngagementSummary  — GET /api/analytics/engagement-scores/summary/
// =============================================================================
export function useEngagementSummary(startDate = null, endDate = null) {
  const fn = useCallback(
    () => fetchEngagementSummary(startDate, endDate),
    [startDate, endDate]
  );
  const { data, loading, error, execute } = useAsync(fn, [startDate, endDate], true);
  return { summary: data, loading, error, refetch: execute };
}

// =============================================================================
// 18. useRecalculateEngagement
//     POST /api/analytics/engagement/recalculate/       (current user)
//     POST /api/analytics/engagement-scores/recalculate/ (staff/admin)
// =============================================================================
export function useRecalculateEngagement() {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [result,  setResult]  = useState(null);

  // current user
  const recalculate = useCallback(async (date = null) => {
    setLoading(true); setError(null);
    try { const r = await recalculateMyEngagement(date); setResult(r); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  // admin / staff
  const recalculateAdmin = useCallback(async (date = null) => {
    setLoading(true); setError(null);
    try { const r = await recalculateEngagementScore(date); setResult(r); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { recalculate, recalculateAdmin, loading, error, result };
}

// =============================================================================
// 19. useSendAnalyticsEvents  — POST /api/analytics/events/
// =============================================================================
export function useSendAnalyticsEvents() {
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [accepted, setAccepted] = useState(null);

  const send = useCallback(async (sessionId, events, platform = "web") => {
    setLoading(true); setError(null);
    try {
      const r = await sendAnalyticsEvents(sessionId, events, platform);
      setAccepted(r?.accepted ?? events.length);
      return r;
    } catch (e) { setError(e.message); return null; }
    finally { setLoading(false); }
  }, []);

  return { send, loading, error, accepted };
}

// =============================================================================
// 20. useBehaviorDashboard  ← MAIN HOOK for BehaviorAnalytics.jsx
//     সব data একসাথে fetch করে
// =============================================================================
export function useBehaviorDashboard({ pageSize = 5 } = {}) {
  const dashboard   = useDashboard();
  const adminStats  = useAdminStats();
  const stayStats   = useStayStats();
  const topElements = useTopElements(5);
  const engScores   = useEngagementScores({ limit: 5, ordering: "-score" });
  const recalc      = useRecalculateEngagement();
  const paths       = usePaths({ limit: pageSize, ordering: "-created_at" });

  // derived convenience values
  const totalSessions = adminStats.data?.total_sessions  ?? dashboard.data?.session_count    ?? 0;
  const totalClicks   = adminStats.data?.total_clicks    ?? dashboard.data?.click_count      ?? 0;
  const avgStaySec    = dashboard.data?.avg_stay_time_sec ?? adminStats.data?.avg_stay_sec   ?? 0;
  const totalStaySec  = dashboard.data?.total_stay_time_sec ?? 0;
  const avgScore      = dashboard.data?.latest_score?.score ?? adminStats.data?.avg_score    ?? 0;
  const scoreTier     = dashboard.data?.latest_score?.tier  ?? "LOW";
  const scoredUsers   = adminStats.data?.scored_users       ?? engScores.scores.length;

  const anyLoading  = dashboard.loading || adminStats.loading || paths.loading || engScores.loading;
  const firstError  = dashboard.error   || adminStats.error   || paths.error   || engScores.error || null;

  const refetchAll = useCallback(() => {
    dashboard.refetch();
    adminStats.refetch();
    paths.refetch();
    engScores.refetch();
    stayStats.refetch();
    topElements.refetch();
  }, []);

  return {
    // raw hooks
    dashboard, adminStats, stayStats, topElements, engScores, recalc, paths,

    // derived values
    totalSessions, totalClicks, avgStaySec,
    totalStaySec, avgScore, scoreTier, scoredUsers,

    // global
    anyLoading, firstError,

    // actions
    refetchAll,
    handleRecalculate: recalc.recalculate,
    goToPage:    paths.goToPage,
    currentPage: paths.currentPage,
    totalPages:  paths.totalPages,
  };
}