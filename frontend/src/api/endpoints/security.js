// src/api/endpoints/security.js
import client from '../client';

const securityAPI = {

  // ─── SECURITY LOGS ────────────────────────────────────
  getLogs:     (params = {}) => client.get('security/logs/', { params }),
  getLog:      (id)          => client.get(`security/security-logs/${id}/`),
  getLogStats: ()            => client.get('security/security-logs/statistics/'),
  resolveLog:  (id, data)    => client.post(`security/security-logs/${id}/resolve/`, data),

  // ─── DEVICES ──────────────────────────────────────────
  getDevices:      (params = {}) => client.get('security/devices/', { params }),
  getDevice:       (id)          => client.get(`security/devices/${id}/`),
  updateDevice:    (id, data)    => client.patch(`security/devices/${id}/`, data),
  deleteDevice:    (id)          => client.delete(`security/devices/${id}/`),
  blacklistDevice: (id, data)    => client.post(`security/devices/${id}/blacklist/`, data),
  whitelistDevice: (id, data)    => client.post(`security/devices/${id}/whitelist/`, data),
  toggleTrust:     (id, data)    => client.post(`security/devices/${id}/trust/`, data),

  // ─── RISK SCORES ──────────────────────────────────────
  getRiskScores:       (params = {}) => client.get('security/risk-scores/', { params }),
  recalculateRisk:     (id)          => client.post(`security/risk-scores/${id}/recalculate/`),
  getRiskDistribution: ()            => client.get('security/risk-scores/distribution/'),

  // ─── USER BANS ────────────────────────────────────────
  getBans:   (params = {}) => client.get('security/bans/', { params }),
  getBan:    (id)          => client.get(`security/bans/${id}/`),
  banUser:   (data)        => client.post('security/bans/', data),
  updateBan: (id, data)    => client.patch(`security/bans/${id}/`, data),
  unbanUser: (id, reason)  => client.post(`security/bans/${id}/deactivate/`, { reason }),
  deleteBan: (id)          => client.delete(`security/bans/${id}/`),

  // ─── IP BLACKLIST ─────────────────────────────────────
  getBlacklist:      (params = {}) => client.get('security/ip-blacklist/', { params }),
  getBlacklistEntry: (id)          => client.get(`security/ip-blacklist/${id}/`),
  blockIP:           (data)        => client.post('security/ip-blacklist/', data),
  updateBlock:       (id, data)    => client.patch(`security/ip-blacklist/${id}/`, data),
  unblockIP:         (id, reason)  => client.post(`security/ip-blacklist/${id}/deactivate/`, { reason }),
  deleteBlock:       (id)          => client.delete(`security/ip-blacklist/${id}/`),
  getBlacklistStats: ()            => client.get('security/ip-blacklist/stats/'),
  bulkBlockIPs:      (data)        => client.post('security/ip-blacklist/bulk-add/', data),

  // ─── SESSIONS ─────────────────────────────────────────
  getSessions:      (params = {}) => client.get('security/sessions/', { params }),
  terminateSession: (id, reason)  => client.post(`security/sessions/${id}/terminate/`, { reason }),

  // ─── AUDIT TRAIL ──────────────────────────────────────
  getAuditTrail: (params = {}) => client.get('security/audit/', { params }),

  // ─── DASHBOARD ────────────────────────────────────────
  getDashboard:     (params = {}) => client.get('security/dashboards/overview/', { params }),
  getTodayDashboard: ()           => client.get('security/dashboards/overview/'),

  // ─── AUTO-BLOCK RULES ─────────────────────────────────
  getAutoBlockRules:   ()                => client.get('security/auto-block-rules/'),
  createAutoBlockRule: (data)            => client.post('security/auto-block-rules/', data),
  updateAutoBlockRule: (id, data)        => client.patch(`security/auto-block-rules/${id}/`, data),
  deleteAutoBlockRule: (id)              => client.delete(`security/auto-block-rules/${id}/`),
  toggleAutoBlockRule: (id, is_active)   => client.patch(`security/auto-block-rules/${id}/`, { is_active }),

  // ─── HEALTH ───────────────────────────────────────────
  getHealth: () => client.get('security/health/'),
};

export default securityAPI;