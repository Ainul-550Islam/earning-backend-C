// src/api/endpoints/rateLimit.js
import client from '../client';

const rateLimitAPI = {

  // ── CONFIGS (Full CRUD) ───────────────────────────────
  getConfigs:     (params={}) => client.get('rate-limit/configs/', { params }),
  getConfig:      (id)        => client.get(`rate-limit/configs/${id}/`),
  createConfig:   (data)      => client.post('rate-limit/configs/', data),
  updateConfig:   (id, data)  => client.patch(`rate-limit/configs/${id}/`, data),
  deleteConfig:   (id)        => client.delete(`rate-limit/configs/${id}/`),
  duplicateConfig:(id)        => client.post(`rate-limit/configs/${id}/duplicate/`),
  testConfig:     (id, data)  => client.post(`rate-limit/configs/${id}/test/`, data),
  bulkUpdate:     (data)      => client.post('rate-limit/configs/bulk_update/', data),
  getTypes:       ()          => client.get('rate-limit/configs/types/'),

  // ── LOGS ─────────────────────────────────────────────
  getLogs:     (params={}) => client.get('rate-limit/logs/', { params }),
  getLogStats: (params={}) => client.get('rate-limit/logs/stats/', { params }),
  clearOldLogs:(days=30)   => client.delete(`rate-limit/logs/clear_old/?days=${days}`),

  // ── USER PROFILES (Full CRUD) ─────────────────────────
  getProfiles:     (params={}) => client.get('rate-limit/user-profiles/', { params }),
  getProfile:      (id)        => client.get(`rate-limit/user-profiles/${id}/`),
  updateProfile:   (id, data)  => client.patch(`rate-limit/user-profiles/${id}/`, data),
  deleteProfile:   (id)        => client.delete(`rate-limit/user-profiles/${id}/`),
  resetLimits:     (id)        => client.post(`rate-limit/user-profiles/${id}/reset_limits/`),
  upgradePremium:  (id, data)  => client.post(`rate-limit/user-profiles/${id}/upgrade_premium/`, data),
  setCustomLimits: (id, data)  => client.post(`rate-limit/user-profiles/${id}/set_custom_limits/`, data),

  // ── DASHBOARD & HEALTH ────────────────────────────────
  getDashboard: (params={}) => client.get('rate-limit/dashboard/', { params }),
  getHealth:    ()          => client.get('rate-limit/health/'),
  testEndpoint: (data)      => client.post('rate-limit/test/', data),
};

export default rateLimitAPI;