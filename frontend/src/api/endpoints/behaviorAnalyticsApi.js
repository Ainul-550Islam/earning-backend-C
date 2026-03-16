// =============================================================================
// src/api/behaviorAnalyticsApi.js
// axiosInstance use করে — token: adminAccessToken, baseURL: localhost:8000
// =============================================================================

import axiosInstance from "./axiosInstance";

// ✅ FIXED: axiosInstance.baseURL = http://localhost:8000/api (already includes /api)
// So BASE must be "/analytics" — not "/api/analytics" (would become /api/api/analytics/)
const BASE = "/behavior-analytics"; // ✅ matches Django mount path("api/behavior-analytics/",...)

const get  = (path, params = {}) =>
  axiosInstance.get(`${BASE}${path}`, { params }).then(r => r.data);

const post = (path, data = {}) =>
  axiosInstance.post(`${BASE}${path}`, data).then(r => r.data);

// =============================================================================
// DASHBOARD
// GET /api/analytics/dashboard/
// GET /api/analytics/admin/stats/
// =============================================================================
export const fetchDashboard  = () => get("/dashboard/");
export const fetchAdminStats = () => get("/admin/stats/");

// =============================================================================
// USER PATHS  →  /api/analytics/paths/
// =============================================================================
export const fetchPaths = (params = {}) =>
  get("/paths/", {
    limit:    params.limit    ?? 10,
    offset:   params.offset   ?? 0,
    ordering: params.ordering ?? "-created_at",
    ...(params.status      ? { status:      params.status      } : {}),
    ...(params.device_type ? { device_type: params.device_type } : {}),
  });

export const fetchPathById = (id)            => get(`/paths/${id}/`);
export const createPath    = (data)          => post("/paths/", data);
export const closePath     = (id, data = {}) => post(`/paths/${id}/close/`, data);
export const addPathNodes  = (id, nodes)     => post(`/paths/${id}/add_nodes/`, { nodes });

export const fetchSessionBySessionId = (sessionId, userId = null) =>
  get(`/sessions/${sessionId}/`, userId ? { user_id: userId } : {});

// =============================================================================
// CLICK METRICS  →  /api/analytics/clicks/
// =============================================================================
export const fetchClicks = (params = {}) =>
  get("/clicks/", {
    limit:    params.limit    ?? 20,
    offset:   params.offset   ?? 0,
    ordering: params.ordering ?? "-clicked_at",
    ...(params.page_url ? { page_url: params.page_url } : {}),
    ...(params.category ? { category: params.category } : {}),
  });

export const recordClick      = (data)           => post("/clicks/", data);
export const recordClicksBulk = (pathId, events) => post("/clicks/bulk/", { path_id: pathId, events });
export const fetchTopElements = (limit = 10)     => get("/clicks/top_elements/", { limit });

// =============================================================================
// STAY TIMES  →  /api/analytics/stay-times/
// =============================================================================
export const fetchStayTimes = (params = {}) =>
  get("/stay-times/", {
    limit:    params.limit    ?? 20,
    offset:   params.offset   ?? 0,
    ordering: params.ordering ?? "-created_at",
    ...(params.page_url ? { page_url: params.page_url } : {}),
  });

export const recordStayTime = (data) => post("/stay-times/", data);
export const fetchStayStats = ()     => get("/stay-times/stats/");

// =============================================================================
// ENGAGEMENT SCORES  →  /api/analytics/engagement-scores/
// =============================================================================
export const fetchEngagementScores = (params = {}) =>
  get("/engagement-scores/", {
    limit:    params.limit    ?? 10,
    offset:   params.offset   ?? 0,
    ordering: params.ordering ?? "-score",
    ...(params.start_date ? { start_date: params.start_date } : {}),
    ...(params.end_date   ? { end_date:   params.end_date   } : {}),
  });

export const fetchEngagementScoreById   = (id)          => get(`/engagement-scores/${id}/`);
export const recalculateEngagementScore = (date = null) => post("/engagement-scores/recalculate/", date ? { date } : {});
export const fetchEngagementSummary     = (s=null,e=null) =>
  get("/engagement-scores/summary/", {
    ...(s ? { start_date: s } : {}),
    ...(e ? { end_date:   e } : {}),
  });

// standalone view (current user)
export const recalculateMyEngagement = (date = null) =>
  post("/engagement/recalculate/", date ? { date } : {});

// =============================================================================
// EVENTS WEBHOOK  →  POST /api/analytics/events/
// =============================================================================
export const sendAnalyticsEvents = (sessionId, events, platform = "web") =>
  post("/events/", { session_id: sessionId, platform, events });