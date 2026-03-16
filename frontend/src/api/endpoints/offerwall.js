import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  OfferProvider Model → /api/offerwall/providers/
// ─────────────────────────────────────────────────────────────────
export const offerProviderAPI = {
  // GET    /api/offerwall/providers/
  // params: { status, provider_type, page }
  list: (params = {}) =>
    client.get("/offers/providers/", { params }),

  // GET    /api/offerwall/providers/:id/
  detail: (id) =>
    client.get(`/offers/providers/${id}/`),

  // POST   /api/offerwall/providers/
  create: (data) =>
    client.post("/offers/providers/", data),

  // PATCH  /api/offerwall/providers/:id/
  update: (id, data) =>
    client.patch(`/offers/providers/${id}/`, data),

  // DELETE /api/offerwall/providers/:id/
  delete: (id) =>
    client.delete(`/offers/providers/${id}/`),

  // POST   /api/offerwall/providers/:id/sync/
  // triggers: last_sync update + offer sync from provider
  sync: (id) =>
    client.post(`/offers/providers/${id}/sync/`),

  // GET    /api/offerwall/providers/:id/stats/
  // returns: { total_offers, total_conversions, total_revenue }
  stats: (id) =>
    client.get(`/offers/providers/${id}/stats/`),
};

// ─────────────────────────────────────────────────────────────────
//  OfferCategory Model → /api/offerwall/categories/
// ─────────────────────────────────────────────────────────────────
export const offerCategoryAPI = {
  // GET    /api/offerwall/categories/
  // params: { is_active, is_featured, page }
  list: (params = {}) =>
    client.get("/offers/categories/", { params }),

  // GET    /api/offerwall/categories/:id/
  detail: (id) =>
    client.get(`/offers/categories/${id}/`),

  // POST   /api/offerwall/categories/
  create: (data) =>
    client.post("/offers/categories/", data),

  // PATCH  /api/offerwall/categories/:id/
  update: (id, data) =>
    client.patch(`/offers/categories/${id}/`, data),

  // DELETE /api/offerwall/categories/:id/
  delete: (id) =>
    client.delete(`/offers/categories/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  Offer Model → /api/offerwall/offers/
// ─────────────────────────────────────────────────────────────────
export const offerAPI = {
  // GET    /api/offerwall/offers/
  // params: { status, offer_type, platform, category, provider,
  //           is_featured, is_trending, is_recommended, is_high_risk,
  //           search, page }
  list: (params = {}) =>
    client.get("/offers/offers/", { params }),

  // GET    /api/offerwall/offers/:id/
  detail: (id) =>
    client.get(`/offers/offers/${id}/`),

  // POST   /api/offerwall/offers/
  create: (data) =>
    client.post("/offers/offers/", data),

  // PATCH  /api/offerwall/offers/:id/
  update: (id, data) =>
    client.patch(`/offers/offers/${id}/`, data),

  // DELETE /api/offerwall/offers/:id/
  delete: (id) =>
    client.delete(`/offers/offers/${id}/`),

  // GET    /api/offerwall/offers/stats/
  // returns: { total, active, paused, expired, total_revenue }
  stats: () =>
    client.get("/offers/offers/stats/"),

  // POST   /api/offerwall/offers/:id/calculate_quality/
  // triggers: calculate_quality_score() backend method
  calculateQuality: (id) =>
    client.post(`/offers/offers/${id}/calculate_quality/`),

  // PATCH  /api/offerwall/offers/:id/toggle_featured/
  toggleFeatured: (id) =>
    client.patch(`/offers/offers/${id}/toggle_featured/`),

  // PATCH  /api/offerwall/offers/:id/toggle_trending/
  toggleTrending: (id) =>
    client.patch(`/offers/offers/${id}/toggle_trending/`),
};

// ─────────────────────────────────────────────────────────────────
//  OfferClick Model → /api/offerwall/clicks/
// ─────────────────────────────────────────────────────────────────
export const offerClickAPI = {
  // GET    /api/offerwall/clicks/
  // params: { offer, user, is_converted, country, page }
  list: (params = {}) =>
    client.get("/offers/clicks/", { params }),

  // GET    /api/offerwall/clicks/:id/
  detail: (id) =>
    client.get(`/offers/clicks/${id}/`),

  // GET    /api/offerwall/clicks/stats/
  // returns: { total, converted, conversion_rate, top_offers, top_countries }
  stats: () =>
    client.get("/offers/clicks/stats/"),
};

// ─────────────────────────────────────────────────────────────────
//  OfferConversion Model → /api/offerwall/conversions/
// ─────────────────────────────────────────────────────────────────
export const offerConversionAPI = {
  // GET    /api/offerwall/conversions/
  // params: { status, offer, user, is_verified, page }
  list: (params = {}) =>
    client.get("/offers/conversions/", { params }),

  // GET    /api/offerwall/conversions/:id/
  detail: (id) =>
    client.get(`/offers/conversions/${id}/`),

  // GET    /api/offerwall/conversions/stats/
  // returns: { total, pending, approved, rejected, total_payout }
  stats: () =>
    client.get("/offers/conversions/stats/"),

  // POST   /api/offerwall/conversions/:id/approve/
  // triggers: approve() backend method → credits user wallet
  approve: (id) =>
    client.post(`/offers/conversions/${id}/approve/`),

  // POST   /api/offerwall/conversions/:id/reject/
  // body: { reason }
  reject: (id, reason = "") =>
    client.post(`/offers/conversions/${id}/reject/`, { reason }),

  // POST   /api/offerwall/conversions/bulk_approve/
  // body: { ids: [...] }
  bulkApprove: (ids) =>
    client.post("/offers/conversions/bulk_approve/", { ids }),
};

// ─────────────────────────────────────────────────────────────────
//  OfferWall Model → /api/offerwall/walls/
// ─────────────────────────────────────────────────────────────────
export const offerWallAPI = {
  // GET    /api/offerwall/walls/
  // params: { is_active, page }
  list: (params = {}) =>
    client.get("/offers/walls/", { params }),

  // GET    /api/offerwall/walls/:id/
  detail: (id) =>
    client.get(`/offers/walls/${id}/`),

  // GET    /api/offerwall/walls/:slug/offers/
  // triggers: get_offers() backend method
  // params: { user, page }
  getOffers: (slug, params = {}) =>
    client.get(`/offers/walls/${slug}/offers/`, { params }),

  // POST   /api/offerwall/walls/
  create: (data) =>
    client.post("/offers/walls/", data),

  // PATCH  /api/offerwall/walls/:id/
  update: (id, data) =>
    client.patch(`/offers/walls/${id}/`, data),

  // DELETE /api/offerwall/walls/:id/
  delete: (id) =>
    client.delete(`/offers/walls/${id}/`),
};