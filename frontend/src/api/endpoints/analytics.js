// src/api/endpoints/analytics.js
import client from '../client';

const analyticsAPI = {

  // ─── REVENUE ANALYTICS (Dashboard Chart) ──────────────

  // Revenue trend (Dashboard এর Revenue Trend Chart)
  getRevenueTrend: (params = {}) =>
    client.get('/analytics/revenue-analytics/', { params }),
  // params: { period: 'daily'|'weekly'|'monthly', days: 7|30|90 }

  // Revenue detail একটি period এর
  getRevenueDetail: (id) =>
    client.get(`/analytics/revenue-analytics/${id}/`),


  // ─── USER ANALYTICS ───────────────────────────────────

  // সব users এর analytics
  getUserAnalytics: (params = {}) =>
    client.get('/analytics/user-analytics/', { params }),
  // params: { period, user, period_start }

  // একজন user এর analytics
  getUserAnalyticsDetail: (userId, params = {}) =>
    client.get('/analytics/user-analytics/', { params: { user: userId, ...params } }),


  // ─── REAL-TIME METRICS ────────────────────────────────

  // Real-time stats (active users, revenue/min etc.)
  getRealTimeMetrics: (params = {}) =>
    client.get('/analytics/realtime/metrics/', { params }),
  // params: { metric_type: 'active_users'|'revenue_per_minute' etc. }


  // ─── RETENTION ────────────────────────────────────────

  getRetentionAnalytics: (params = {}) =>
    client.get('/analytics/retention/', { params }),
  // params: { cohort_type: 'daily'|'weekly'|'monthly' }


  // ─── FUNNEL ───────────────────────────────────────────

  getFunnelAnalytics: (params = {}) =>
    client.get('/analytics/funnel/', { params }),
  // params: { funnel_type: 'user_signup'|'offer_completion' etc. }


  // ─── OFFER PERFORMANCE ────────────────────────────────

  getOfferPerformance: (params = {}) =>
    client.get('/analytics/offer-performance/', { params }),

  getOfferPerformanceDetail: (id) =>
    client.get(`/analytics/offer-performance/${id}/`),


  // ─── EVENTS ───────────────────────────────────────────

  getEvents: (params = {}) =>
    client.get('/analytics/events/', { params }),
  // params: { event_type, user, country, device_type }


  // ─── ALERT RULES ──────────────────────────────────────

  getAlertRules: (params = {}) =>
    client.get('/analytics/alert-rules/', { params }),

  createAlertRule: (data) =>
    client.post('/analytics/alert-rules/', data),

  updateAlertRule: (id, data) =>
    client.patch(`/analytics/alert-rules/${id}/`, data),

  deleteAlertRule: (id) =>
    client.delete(`/analytics/alert-rules/${id}/`),


  // ─── ALERT HISTORY ────────────────────────────────────

  getAlertHistory: (params = {}) =>
    client.get('/analytics/alerts/', { params }),
  // params: { is_resolved: false }

  resolveAlert: (id, notes) =>
    client.post(`/analytics/alerts/${id}/resolve/`, { resolution_notes: notes }),


  // ─── REPORTS ──────────────────────────────────────────

  getReports: (params = {}) =>
    client.get('/analytics/reports/', { params }),

  generateReport: (data) =>
    client.post('/analytics/reports/', data),
  // data: { name, report_type, format, parameters }

  getReportDetail: (id) =>
    client.get(`/analytics/reports/${id}/`),

};

export default analyticsAPI;