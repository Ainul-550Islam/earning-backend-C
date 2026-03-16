import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  KYC Model → /api/kyc/records/
// ─────────────────────────────────────────────────────────────────
export const kycAPI = {
  // GET    /api/kyc/records/
  // params: { status, document_type, is_duplicate, risk_score_min, page }
  list: (params = {}) =>
    client.get("/kyc/records/", { params }),

  // GET    /api/kyc/records/:id/
  detail: (id) =>
    client.get(`/kyc/records/${id}/`),

  // GET    /api/kyc/records/by_user/:userId/
  byUser: (userId) =>
    client.get(`/kyc/records/by_user/${userId}/`),

  // GET    /api/kyc/records/stats/
  // returns: { total, pending, verified, rejected, expired, duplicate }
  stats: () =>
    client.get("/kyc/records/stats/"),

  // PATCH  /api/kyc/records/:id/
  update: (id, data) =>
    client.patch(`/kyc/records/${id}/`, data),

  // POST   /api/kyc/records/:id/approve/
  // triggers: approve() backend method → sets verified, expiry, user.is_verified=True
  approve: (id) =>
    client.post(`/kyc/records/${id}/approve/`),

  // POST   /api/kyc/records/:id/reject/
  // body: { reason }  →  triggers reject() backend method
  reject: (id, reason = "") =>
    client.post(`/kyc/records/${id}/reject/`, { reason }),

  // POST   /api/kyc/records/:id/calculate_risk/
  // triggers: calculate_risk_score() backend method
  // returns: { risk_score, risk_factors }
  calculateRisk: (id) =>
    client.post(`/kyc/records/${id}/calculate_risk/`),

  // POST   /api/kyc/records/:id/check_duplicate/
  // triggers: KYCService.check_duplicate_kyc() backend service
  checkDuplicate: (id) =>
    client.post(`/kyc/records/${id}/check_duplicate/`),
};

// ─────────────────────────────────────────────────────────────────
//  KYCVerificationLog Model → /api/kyc/logs/
// ─────────────────────────────────────────────────────────────────
export const kycLogAPI = {
  // GET    /api/kyc/logs/
  // params: { kyc, action, performed_by, page }
  list: (params = {}) =>
    client.get("/kyc/logs/", { params }),

  // GET    /api/kyc/logs/?kyc=:kycId   (logs for specific KYC)
  byKyc: (kycId) =>
    client.get("/kyc/logs/", { params: { kyc: kycId } }),
};