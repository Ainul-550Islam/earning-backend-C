// src/api/endpoints/notifications.js
import client from '../client';

const notificationsAPI = {

  // ─── NOTIFICATIONS ────────────────────────────────────────────────────────

  getAll: (params = {}) =>
    client.get('/notifications/', { params }),
  // params: { is_read, status, notification_type, priority, channel,
  //           is_archived, is_pinned, search, page }

  getUnreadCount: () =>
    client.get('/notifications/unread-count/'),

  getStats: (params = {}) =>
    client.get('/notifications/stats/', { params }),

  getDetail: (id) =>
    client.get(`/notifications/${id}/`),

  markAsRead: (id) =>
    client.post(`/notifications/${id}/mark-read/`),

  markAsUnread: (id) =>
    client.post(`/notifications/${id}/mark-unread/`),

  markAllAsRead: () =>
    client.post('/notifications/mark-all-read/'),

  archive: (id, reason = '') =>
    client.post(`/notifications/${id}/archive/`, { reason }),

  pin: (id) =>
    client.post(`/notifications/${id}/pin/`),

  unpin: (id) =>
    client.post(`/notifications/${id}/unpin/`),

  delete: (id) =>
    client.delete(`/notifications/${id}/`),

  bulkDelete: (ids) =>
    client.post('/notifications/bulk-delete/', { ids }),

  trackClick: (id) =>
    client.post(`/notifications/${id}/track-click/`),

  trackImpression: (id) =>
    client.post(`/notifications/${id}/track-impression/`),


  // ─── SEND (Admin) ─────────────────────────────────────────────────────────

  send: (data) =>
    client.post('/notifications/', data),
  // data: { user, title, message, notification_type, priority, channel,
  //         scheduled_for, expire_date, action_url, action_text, metadata }

  sendBulk: (data) =>
    client.post('/notifications/send-bulk/', data),


  // ─── TEMPLATES ────────────────────────────────────────────────────────────

  getTemplates: (params = {}) =>
    client.get('/notifications/templates/', { params }),

  getTemplate: (id) =>
    client.get(`/notifications/templates/${id}/`),

  createTemplate: (data) =>
    client.post('/notifications/templates/', data),

  updateTemplate: (id, data) =>
    client.patch(`/notifications/templates/${id}/`, data),

  deleteTemplate: (id) =>
    client.delete(`/notifications/templates/${id}/`),

  previewTemplate: (id, context = {}) =>
    client.post(`/notifications/templates/${id}/preview/`, { context }),


  // ─── PREFERENCES ──────────────────────────────────────────────────────────

  getPreferences: (userId = null) =>
    client.get('/notifications/preferences/', { params: userId ? { user: userId } : {} }),

  updatePreferences: (data) =>
    client.patch('/notifications/preferences/me/', data),
  // data: { enable_push, enable_email, enable_sms, quiet_hours_enabled,
  //         quiet_hours_start, quiet_hours_end, do_not_disturb, ... }


  // ─── DEVICE TOKENS ────────────────────────────────────────────────────────

  registerDevice: (data) =>
    client.post('/notifications/device-tokens/', data),

  updateDevice: (id, data) =>
    client.patch(`/notifications/device-tokens/${id}/`, data),

  removeDevice: (id) =>
    client.delete(`/notifications/device-tokens/${id}/`),

  getMyDevices: () =>
    client.get('/notifications/device-tokens/me/'),


  // ─── CAMPAIGNS ────────────────────────────────────────────────────────────

  getCampaigns: (params = {}) =>
    client.get('/notifications/campaigns/', { params }),

  getCampaign: (id) =>
    client.get(`/notifications/campaigns/${id}/`),

  createCampaign: (data) =>
    client.post('/notifications/campaigns/', data),

  updateCampaign: (id, data) =>
    client.patch(`/notifications/campaigns/${id}/`, data),

  startCampaign: (id) =>
    client.post(`/notifications/campaigns/${id}/start/`),

  pauseCampaign: (id) =>
    client.post(`/notifications/campaigns/${id}/pause/`),

  resumeCampaign: (id) =>
    client.post(`/notifications/campaigns/${id}/resume/`),

  cancelCampaign: (id) =>
    client.post(`/notifications/campaigns/${id}/cancel/`),

  getCampaignStats: (id) =>
    client.get(`/notifications/campaigns/${id}/stats/`),


  // ─── ANALYTICS ────────────────────────────────────────────────────────────

  getAnalytics: (params = {}) =>
    client.get('/notifications/analytics/', { params }),

  generateDailyReport: (date = null) =>
    client.post('/notifications/analytics/generate/', { date }),


  // ─── RULES ────────────────────────────────────────────────────────────────

  getRules: () =>
    client.get('/notifications/rules/'),

  createRule: (data) =>
    client.post('/notifications/rules/', data),

  updateRule: (id, data) =>
    client.patch(`/notifications/rules/${id}/`, data),

  toggleRule: (id, isActive) =>
    client.patch(`/notifications/rules/${id}/`, { is_active: isActive }),

  testRule: (id, context = {}) =>
    client.post(`/notifications/rules/${id}/test/`, { context }),


  // ─── NOTICES ──────────────────────────────────────────────────────────────

  getNotices: (params = {}) =>
    client.get('/notifications/notices/', { params }),

  getActiveNotices: () =>
    client.get('/notifications/notices/', { params: { status: 'published', is_published: true } }),

  getNotice: (id) =>
    client.get(`/notifications/notices/${id}/`),

  createNotice: (data) =>
    client.post('/notifications/notices/', data),

  updateNotice: (id, data) =>
    client.patch(`/notifications/notices/${id}/`, data),

  publishNotice: (id) =>
    client.post(`/notifications/notices/${id}/publish/`),

  unpublishNotice: (id) =>
    client.post(`/notifications/notices/${id}/unpublish/`),

  archiveNotice: (id) =>
    client.post(`/notifications/notices/${id}/archive/`),

  deleteNotice: (id) =>
    client.delete(`/notifications/notices/${id}/`),


  // ─── FEEDBACK ─────────────────────────────────────────────────────────────

  submitFeedback: (notificationId, data) =>
    client.post(`/notifications/${notificationId}/feedback/`, data),


  // ─── LOGS ─────────────────────────────────────────────────────────────────

  getLogs: (params = {}) =>
    client.get('/notifications/logs/', { params }),

};

export default notificationsAPI;