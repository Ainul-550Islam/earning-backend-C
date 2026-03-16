// src/api/endpoints/users.js
import client from '../client';

const usersAPI = {

  // ─── USERS ────────────────────────────────────────────

  // সব user list (filter সহ)
  getUsers: (params = {}) =>
    client.get('/users/', { params }),
  // params: { role, tier, is_verified, country, search, page }

  // একজন user এর detail
  getUserDetail: (userId) =>
    client.get(`/users/${userId}/`),

  // User update (admin)
  updateUser: (userId, data) =>
    client.patch(`/users/${userId}/`, data),

  // User ban/suspend
  updateUserStatus: (userId, status) =>
    client.post(`/users/${userId}/update-status/`, { account_status: status }),

  // Dashboard stats (total users, verified, banned etc.)
  getUserDashboardStats: () =>
    client.get('/users/dashboard-stats/'),


  // ─── USER PROFILE ─────────────────────────────────────

  getUserProfile: (userId) =>
    client.get(`/users/${userId}/profile/`),

  updateUserProfile: (userId, data) =>
    client.patch(`/users/${userId}/profile/`, data),


  // ─── USER STATISTICS ──────────────────────────────────

  getUserStatistics: (userId) =>
    client.get(`/users/${userId}/statistics/`),


  // ─── USER RANK ────────────────────────────────────────

  getUserRank: (userId) =>
    client.get(`/users/${userId}/rank/`),

  // Leaderboard
  getLeaderboard: (params = {}) =>
    client.get('/users/leaderboard/', { params }),


  // ─── LOGIN HISTORY ────────────────────────────────────

  getLoginHistory: (userId, params = {}) =>
    client.get(`/users/${userId}/login-history/`, { params }),


  // ─── USER ACTIVITY ────────────────────────────────────

  getUserActivity: (userId, params = {}) =>
    client.get(`/users/${userId}/activity/`, { params }),


  // ─── KYC ──────────────────────────────────────────────

  getKYCList: (params = {}) =>
    client.get('/users/kyc/', { params }),
  // params: { verification_status: 'pending' }

  getKYCDetail: (userId) =>
    client.get(`/users/${userId}/kyc/`),

  approveKYC: (userId) =>
    client.post(`/users/${userId}/kyc/approve/`),

  rejectKYC: (userId, reason) =>
    client.post(`/users/${userId}/kyc/reject/`, { rejection_reason: reason }),


  // ─── DEVICE & FINGERPRINT ────────────────────────────

  getUserDevices: (userId) =>
    client.get(`/users/${userId}/devices/`),

  getDeviceFingerprints: (params = {}) =>
    client.get('/users/device-fingerprints/', { params }),

  blockDevice: (fingerprintId) =>
    client.post(`/users/device-fingerprints/${fingerprintId}/block/`),


  // ─── IP REPUTATION ────────────────────────────────────

  getIPReputations: (params = {}) =>
    client.get('/users/ip-reputations/', { params }),

  blacklistIP: (ipId, reason) =>
    client.post(`/users/ip-reputations/${ipId}/blacklist/`, { reason }),


  // ─── FRAUD DETECTION ──────────────────────────────────

  getFraudLogs: (params = {}) =>
    client.get('/users/fraud-logs/', { params }),
  // params: { severity, event_type, is_resolved }

  resolveFraud: (logId) =>
    client.post(`/users/fraud-logs/${logId}/resolve/`),


  // ─── RISK SCORE ───────────────────────────────────────

  getUserRiskHistory: (userId) =>
    client.get(`/users/${userId}/risk-history/`),


  // ─── SECURITY SETTINGS ────────────────────────────────

  getUserSecuritySettings: (userId) =>
    client.get(`/users/${userId}/security-settings/`),


  // ─── OTP ──────────────────────────────────────────────

  getUserOTPs: (userId) =>
    client.get(`/users/${userId}/otps/`),


  // ─── RATE LIMIT ───────────────────────────────────────

  getRateLimitTrackers: (params = {}) =>
    client.get('/users/rate-limits/', { params }),

  unblockRateLimit: (trackerId) =>
    client.post(`/users/rate-limits/${trackerId}/unblock/`),

};

export default usersAPI;