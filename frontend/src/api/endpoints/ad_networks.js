import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  AdNetwork Model → /api/ad_networks/networks/
// ─────────────────────────────────────────────────────────────────
export const adNetworkAPI = {
  // GET    /api/ad_networks/networks/
  // params: { category, is_active, is_testing, is_verified,
  //           country_support, network_type, page }
  list: (params = {}) =>
    client.get("/ad_networks/networks/", { params }),

  // GET    /api/ad_networks/networks/:id/
  detail: (id) =>
    client.get(`/ad_networks/networks/${id}/`),

  // POST   /api/ad_networks/networks/
  create: (data) =>
    client.post("/ad_networks/networks/", data),

  // PATCH  /api/ad_networks/networks/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/networks/${id}/`, data),

  // DELETE /api/ad_networks/networks/:id/
  delete: (id) =>
    client.delete(`/ad_networks/networks/${id}/`),

  // GET    /api/ad_networks/networks/stats/
  // returns: { total, active, total_payout, total_conversions, top_networks }
  stats: () =>
    client.get("/ad_networks/networks/stats/"),

  // POST   /api/ad_networks/networks/:id/sync/
  // triggers: offer sync from network → updates last_sync, next_sync
  sync: (id) =>
    client.post(`/ad_networks/networks/${id}/sync/`),
};

// ─────────────────────────────────────────────────────────────────
//  OfferCategory Model → /api/ad_networks/categories/
// ─────────────────────────────────────────────────────────────────
export const offerCategoryAPI = {
  // GET    /api/ad_networks/categories/
  // params: { is_active, is_featured, category_type, page }
  list: (params = {}) =>
    client.get("/ad_networks/categories/", { params }),

  // GET    /api/ad_networks/categories/:id/
  detail: (id) =>
    client.get(`/ad_networks/categories/${id}/`),

  // POST   /api/ad_networks/categories/
  create: (data) =>
    client.post("/ad_networks/categories/", data),

  // PATCH  /api/ad_networks/categories/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/categories/${id}/`, data),

  // DELETE /api/ad_networks/categories/:id/
  delete: (id) =>
    client.delete(`/ad_networks/categories/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  Offer Model → /api/ad_networks/offers/
// ─────────────────────────────────────────────────────────────────
export const adOfferAPI = {
  // GET    /api/ad_networks/offers/
  // params: { status, ad_network, category, is_featured, is_hot,
  //           is_new, is_exclusive, device_type, page }
  list: (params = {}) =>
    client.get("/ad_networks/offers/", { params }),

  // GET    /api/ad_networks/offers/:id/
  detail: (id) =>
    client.get(`/ad_networks/offers/${id}/`),

  // POST   /api/ad_networks/offers/
  create: (data) =>
    client.post("/ad_networks/offers/", data),

  // PATCH  /api/ad_networks/offers/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/offers/${id}/`, data),

  // DELETE /api/ad_networks/offers/:id/
  delete: (id) =>
    client.delete(`/ad_networks/offers/${id}/`),

  // GET    /api/ad_networks/offers/stats/
  // returns: { total, active, paused, expired, total_conversions }
  stats: () =>
    client.get("/ad_networks/offers/stats/"),
};

// ─────────────────────────────────────────────────────────────────
//  UserOfferEngagement Model → /api/ad_networks/engagements/
// ─────────────────────────────────────────────────────────────────
export const userOfferEngagementAPI = {
  // GET    /api/ad_networks/engagements/
  // params: { status, user, offer, page }
  list: (params = {}) =>
    client.get("/ad_networks/engagements/", { params }),

  // GET    /api/ad_networks/engagements/:id/
  detail: (id) =>
    client.get(`/ad_networks/engagements/${id}/`),

  // PATCH  /api/ad_networks/engagements/:id/
  // body: { status, rejection_reason, rejection_details }
  update: (id, data) =>
    client.patch(`/ad_networks/engagements/${id}/`, data),

  // POST   /api/ad_networks/engagements/:id/approve/
  approve: (id) =>
    client.post(`/ad_networks/engagements/${id}/approve/`),

  // POST   /api/ad_networks/engagements/:id/reject/
  // body: { rejection_reason, rejection_details }
  reject: (id, reason, details = "") =>
    client.post(`/ad_networks/engagements/${id}/reject/`, {
      rejection_reason: reason,
      rejection_details: details,
    }),

  // GET    /api/ad_networks/engagements/stats/
  // returns: { total, completed, pending, approved, rejected }
  stats: () =>
    client.get("/ad_networks/engagements/stats/"),
};

// ─────────────────────────────────────────────────────────────────
//  OfferConversion Model → /api/ad_networks/conversions/
// ─────────────────────────────────────────────────────────────────
export const offerConversionAPI = {
  // GET    /api/ad_networks/conversions/
  // params: { conversion_status, risk_level, is_verified,
  //           chargeback_processed, page }
  list: (params = {}) =>
    client.get("/ad_networks/conversions/", { params }),

  // GET    /api/ad_networks/conversions/:id/
  detail: (id) =>
    client.get(`/ad_networks/conversions/${id}/`),

  // PATCH  /api/ad_networks/conversions/:id/
  // body: { conversion_status, rejection_reason }
  update: (id, data) =>
    client.patch(`/ad_networks/conversions/${id}/`, data),

  // GET    /api/ad_networks/conversions/stats/
  // returns: { total, pending, approved, rejected, chargeback, total_payout }
  stats: () =>
    client.get("/ad_networks/conversions/stats/"),

  // POST   /api/ad_networks/conversions/:id/approve/
  approve: (id) =>
    client.post(`/ad_networks/conversions/${id}/approve/`),

  // POST   /api/ad_networks/conversions/:id/reject/
  // body: { rejection_reason }
  reject: (id, reason = "") =>
    client.post(`/ad_networks/conversions/${id}/reject/`, { rejection_reason: reason }),

  // POST   /api/ad_networks/conversions/bulk_approve/
  // body: { ids: [...] }
  bulkApprove: (ids) =>
    client.post("/ad_networks/conversions/bulk_approve/", { ids }),
};

// ─────────────────────────────────────────────────────────────────
//  OfferWall Model → /api/ad_networks/walls/
// ─────────────────────────────────────────────────────────────────
export const offerWallAPI = {
  // GET    /api/ad_networks/walls/
  // params: { wall_type, is_active, is_default, page }
  list: (params = {}) =>
    client.get("/ad_networks/walls/", { params }),

  // GET    /api/ad_networks/walls/:id/
  detail: (id) =>
    client.get(`/ad_networks/walls/${id}/`),

  // POST   /api/ad_networks/walls/
  create: (data) =>
    client.post("/ad_networks/walls/", data),

  // PATCH  /api/ad_networks/walls/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/walls/${id}/`, data),

  // DELETE /api/ad_networks/walls/:id/
  delete: (id) =>
    client.delete(`/ad_networks/walls/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  AdNetworkWebhookLog Model → /api/ad_networks/webhooks/
// ─────────────────────────────────────────────────────────────────
export const adWebhookLogAPI = {
  // GET    /api/ad_networks/webhooks/
  // params: { ad_network, processed, is_valid_signature, event_type, page }
  list: (params = {}) =>
    client.get("/ad_networks/webhooks/", { params }),

  // GET    /api/ad_networks/webhooks/:id/
  detail: (id) =>
    client.get(`/ad_networks/webhooks/${id}/`),

  // POST   /api/ad_networks/webhooks/:id/reprocess/
  reprocess: (id) =>
    client.post(`/ad_networks/webhooks/${id}/reprocess/`),
};

// ─────────────────────────────────────────────────────────────────
//  NetworkStatistic Model → /api/ad_networks/statistics/
// ─────────────────────────────────────────────────────────────────
export const networkStatisticAPI = {
  // GET    /api/ad_networks/statistics/
  // params: { ad_network, date, date_from, date_to, page }
  list: (params = {}) =>
    client.get("/ad_networks/statistics/", { params }),
};

// ─────────────────────────────────────────────────────────────────
//  OfferSyncLog Model → /api/ad_networks/sync-logs/
// ─────────────────────────────────────────────────────────────────
export const offerSyncLogAPI = {
  // GET    /api/ad_networks/sync-logs/
  // params: { ad_network, status, page }
  list: (params = {}) =>
    client.get("/ad_networks/sync-logs/", { params }),

  // GET    /api/ad_networks/sync-logs/:id/
  detail: (id) =>
    client.get(`/ad_networks/sync-logs/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  BlacklistedIP Model → /api/ad_networks/blacklisted-ips/
// ─────────────────────────────────────────────────────────────────
export const blacklistedIPAPI = {
  // GET    /api/ad_networks/blacklisted-ips/
  // params: { reason, is_active, page }
  list: (params = {}) =>
    client.get("/ad_networks/blacklisted-ips/", { params }),

  // GET    /api/ad_networks/blacklisted-ips/:id/
  detail: (id) =>
    client.get(`/ad_networks/blacklisted-ips/${id}/`),

  // POST   /api/ad_networks/blacklisted-ips/
  // body: { ip_address, reason, expiry_date }
  create: (data) =>
    client.post("/ad_networks/blacklisted-ips/", data),

  // PATCH  /api/ad_networks/blacklisted-ips/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/blacklisted-ips/${id}/`, data),

  // DELETE /api/ad_networks/blacklisted-ips/:id/
  delete: (id) =>
    client.delete(`/ad_networks/blacklisted-ips/${id}/`),

  // GET    /api/ad_networks/blacklisted-ips/stats/
  // triggers: get_statistics() backend classmethod
  stats: () =>
    client.get("/ad_networks/blacklisted-ips/stats/"),

  // POST   /api/ad_networks/blacklisted-ips/check/
  // body: { ip_address }  → triggers: is_ip_blacklisted()
  checkIP: (ip_address) =>
    client.post("/ad_networks/blacklisted-ips/check/", { ip_address }),

  // POST   /api/ad_networks/blacklisted-ips/cleanup/
  // triggers: cleanup_expired_entries() backend classmethod
  cleanup: (batch_size = 1000) =>
    client.post("/ad_networks/blacklisted-ips/cleanup/", { batch_size }),
};

// ─────────────────────────────────────────────────────────────────
//  FraudDetectionRule Model → /api/ad_networks/fraud-rules/
// ─────────────────────────────────────────────────────────────────
export const fraudRuleAPI = {
  // GET    /api/ad_networks/fraud-rules/
  // params: { rule_type, action, severity, is_active, page }
  list: (params = {}) =>
    client.get("/ad_networks/fraud-rules/", { params }),

  // GET    /api/ad_networks/fraud-rules/:id/
  detail: (id) =>
    client.get(`/ad_networks/fraud-rules/${id}/`),

  // POST   /api/ad_networks/fraud-rules/
  create: (data) =>
    client.post("/ad_networks/fraud-rules/", data),

  // PATCH  /api/ad_networks/fraud-rules/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/fraud-rules/${id}/`, data),

  // DELETE /api/ad_networks/fraud-rules/:id/
  delete: (id) =>
    client.delete(`/ad_networks/fraud-rules/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  KnownBadIP Model → /api/ad_networks/known-bad-ips/
// ─────────────────────────────────────────────────────────────────
export const knownBadIPAPI = {
  // GET    /api/ad_networks/known-bad-ips/
  // params: { threat_type, source, is_active, page }
  list: (params = {}) =>
    client.get("/ad_networks/known-bad-ips/", { params }),

  // POST   /api/ad_networks/known-bad-ips/
  // body: { ip_address, threat_type, source, confidence_score, expires_at }
  create: (data) =>
    client.post("/ad_networks/known-bad-ips/", data),

  // PATCH  /api/ad_networks/known-bad-ips/:id/
  update: (id, data) =>
    client.patch(`/ad_networks/known-bad-ips/${id}/`, data),

  // DELETE /api/ad_networks/known-bad-ips/:id/
  delete: (id) =>
    client.delete(`/ad_networks/known-bad-ips/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  SmartOfferRecommendation → /api/ad_networks/recommendations/
// ─────────────────────────────────────────────────────────────────
export const offerRecommendationAPI = {
  // GET    /api/ad_networks/recommendations/
  // params: { user, offer, is_displayed, is_converted, page }
  list: (params = {}) =>
    client.get("/ad_networks/recommendations/", { params }),

  // GET    /api/ad_networks/recommendations/by_user/:userId/
  byUser: (userId) =>
    client.get("/ad_networks/recommendations/", { params: { user: userId } }),
};