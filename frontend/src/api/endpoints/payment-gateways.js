import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  PaymentGateway Model → /api/payment_gateways/gateways/
// ─────────────────────────────────────────────────────────────────
export const paymentGatewayAPI = {
  // GET    /api/payment_gateways/gateways/
  // params: { status, name, supports_deposit, supports_withdrawal, page }
  list: (params = {}) =>
    client.get("/payment_gateways/gateways/", { params }),

  // GET    /api/payment_gateways/gateways/:id/
  detail: (id) =>
    client.get(`/payment_gateways/gateways/${id}/`),

  // POST   /api/payment_gateways/gateways/
  create: (data) =>
    client.post("/payment_gateways/gateways/", data),

  // PATCH  /api/payment_gateways/gateways/:id/
  update: (id, data) =>
    client.patch(`/payment_gateways/gateways/${id}/`, data),

  // DELETE /api/payment_gateways/gateways/:id/
  delete: (id) =>
    client.delete(`/payment_gateways/gateways/${id}/`),

  // PATCH  /api/payment_gateways/gateways/:id/toggle_status/
  // body: { status: 'active' | 'inactive' | 'maintenance' }
  toggleStatus: (id, status) =>
    client.patch(`/payment_gateways/gateways/${id}/toggle_status/`, { status }),
};

// ─────────────────────────────────────────────────────────────────
//  GatewayConfig Model → /api/payment_gateways/configs/
// ─────────────────────────────────────────────────────────────────
export const gatewayConfigAPI = {
  // GET    /api/payment_gateways/configs/?gateway=:id
  list: (gatewayId) =>
    client.get("/payment_gateways/configs/", { params: { gateway: gatewayId } }),

  // POST   /api/payment_gateways/configs/
  // body: { gateway, key, value, is_secret, description }
  create: (data) =>
    client.post("/payment_gateways/configs/", data),

  // PATCH  /api/payment_gateways/configs/:id/
  update: (id, data) =>
    client.patch(`/payment_gateways/configs/${id}/`, data),

  // DELETE /api/payment_gateways/configs/:id/
  delete: (id) =>
    client.delete(`/payment_gateways/configs/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  PaymentGatewayMethod Model → /api/payment_gateways/methods/
// ─────────────────────────────────────────────────────────────────
export const paymentGatewayMethodAPI = {
  // GET    /api/payment_gateways/methods/
  // params: { user, gateway, is_verified, is_default, page }
  list: (params = {}) =>
    client.get("/payment_gateways/methods/", { params }),

  // GET    /api/payment_gateways/methods/:id/
  detail: (id) =>
    client.get(`/payment_gateways/methods/${id}/`),

  // POST   /api/payment_gateways/methods/
  create: (data) =>
    client.post("/payment_gateways/methods/", data),

  // PATCH  /api/payment_gateways/methods/:id/
  update: (id, data) =>
    client.patch(`/payment_gateways/methods/${id}/`, data),

  // DELETE /api/payment_gateways/methods/:id/
  delete: (id) =>
    client.delete(`/payment_gateways/methods/${id}/`),

  // PATCH  /api/payment_gateways/methods/:id/verify/
  verify: (id) =>
    client.patch(`/payment_gateways/methods/${id}/verify/`),

  // PATCH  /api/payment_gateways/methods/:id/set_default/
  setDefault: (id) =>
    client.patch(`/payment_gateways/methods/${id}/set_default/`),
};

// ─────────────────────────────────────────────────────────────────
//  GatewayTransaction Model → /api/payment_gateways/transactions/
// ─────────────────────────────────────────────────────────────────
export const gatewayTransactionAPI = {
  // GET    /api/payment_gateways/transactions/
  // params: { status, transaction_type, gateway, user, page }
  list: (params = {}) =>
    client.get("/payment_gateways/transactions/", { params }),

  // GET    /api/payment_gateways/transactions/:id/
  detail: (id) =>
    client.get(`/payment_gateways/transactions/${id}/`),

  // GET    /api/payment_gateways/transactions/stats/
  // returns: { total, completed, pending, failed, total_amount }
  stats: () =>
    client.get("/payment_gateways/transactions/stats/"),

  // PATCH  /api/payment_gateways/transactions/:id/
  // body: { status }
  update: (id, data) =>
    client.patch(`/payment_gateways/transactions/${id}/`, data),
};

// ─────────────────────────────────────────────────────────────────
//  PayoutRequest Model → /api/payment_gateways/payouts/
// ─────────────────────────────────────────────────────────────────
export const payoutRequestAPI = {
  // GET    /api/payment_gateways/payouts/
  // params: { status, payout_method, user, page }
  list: (params = {}) =>
    client.get("/payment_gateways/payouts/", { params }),

  // GET    /api/payment_gateways/payouts/:id/
  detail: (id) =>
    client.get(`/payment_gateways/payouts/${id}/`),

  // GET    /api/payment_gateways/payouts/stats/
  stats: () =>
    client.get("/payment_gateways/payouts/stats/"),

  // PATCH  /api/payment_gateways/payouts/:id/approve/
  approve: (id, admin_notes = "") =>
    client.patch(`/payment_gateways/payouts/${id}/approve/`, { admin_notes }),

  // PATCH  /api/payment_gateways/payouts/:id/reject/
  reject: (id, admin_notes = "") =>
    client.patch(`/payment_gateways/payouts/${id}/reject/`, { admin_notes }),

  // PATCH  /api/payment_gateways/payouts/:id/complete/
  complete: (id) =>
    client.patch(`/payment_gateways/payouts/${id}/complete/`),
};

// ─────────────────────────────────────────────────────────────────
//  Currency Model → /api/payment_gateways/currencies/
// ─────────────────────────────────────────────────────────────────
export const currencyAPI = {
  // GET    /api/payment_gateways/currencies/
  list: (params = {}) =>
    client.get("/payment_gateways/currencies/", { params }),

  // POST   /api/payment_gateways/currencies/
  create: (data) =>
    client.post("/payment_gateways/currencies/", data),

  // PATCH  /api/payment_gateways/currencies/:id/
  update: (id, data) =>
    client.patch(`/payment_gateways/currencies/${id}/`, data),

  // DELETE /api/payment_gateways/currencies/:id/
  delete: (id) =>
    client.delete(`/payment_gateways/currencies/${id}/`),

  // PATCH  /api/payment_gateways/currencies/:id/set_default/
  setDefault: (id) =>
    client.patch(`/payment_gateways/currencies/${id}/set_default/`),
};

// ─────────────────────────────────────────────────────────────────
//  PaymentGatewayWebhookLog Model → /api/payment_gateways/webhooks/
// ─────────────────────────────────────────────────────────────────
export const webhookLogAPI = {
  // GET    /api/payment_gateways/webhooks/
  // params: { gateway, processed, page }
  list: (params = {}) =>
    client.get("/payment_gateways/webhooks/", { params }),

  // GET    /api/payment_gateways/webhooks/:id/
  detail: (id) =>
    client.get(`/payment_gateways/webhooks/${id}/`),

  // PATCH  /api/payment_gateways/webhooks/:id/reprocess/
  reprocess: (id) =>
    client.patch(`/payment_gateways/webhooks/${id}/reprocess/`),
};