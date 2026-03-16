import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  Customer Model → /api/customers/
// ─────────────────────────────────────────────────────────────────
export const customerAPI = {
  // GET    /api/customers/
  // params: { search, city, newsletter, page }
  list: (params = {}) =>
    client.get("/customers/", { params }),

  // GET    /api/customers/:id/
  detail: (id) =>
    client.get(`/customers/${id}/`),

  // POST   /api/customers/
  create: (data) =>
    client.post("/customers/", data),

  // PATCH  /api/customers/:id/
  update: (id, data) =>
    client.patch(`/customers/${id}/`, data),

  // DELETE /api/customers/:id/
  delete: (id) =>
    client.delete(`/customers/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  Txn Model → /api/customers/transactions/
//  Custom Managers:
//    txn_full     → is_discount=false
//    txn_discount → is_discount=true
//    spending     → value < 0
// ─────────────────────────────────────────────────────────────────
export const txnAPI = {
  // GET    /api/customers/transactions/
  // params: { customer, is_discount, value_lt, value_gt, page }
  list: (params = {}) =>
    client.get("/customers/transactions/", { params }),

  // GET    /api/customers/transactions/?is_discount=false  (FullPriceTxnManager)
  fullPrice: (params = {}) =>
    client.get("/customers/transactions/", { params: { ...params, is_discount: false } }),

  // GET    /api/customers/transactions/?is_discount=true   (DiscountedTxnManager)
  discounted: (params = {}) =>
    client.get("/customers/transactions/", { params: { ...params, is_discount: true } }),

  // GET    /api/customers/transactions/?value_lt=0         (SpendingTxnManager)
  spending: (params = {}) =>
    client.get("/customers/transactions/", { params: { ...params, value_lt: 0 } }),

  // GET    /api/customers/transactions/:id/
  detail: (id) =>
    client.get(`/customers/transactions/${id}/`),

  // POST   /api/customers/transactions/
  // body: { customer, value, is_discount }
  create: (data) =>
    client.post("/customers/transactions/", data),

  // DELETE /api/customers/transactions/:id/
  delete: (id) =>
    client.delete(`/customers/transactions/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  Event Model → /api/customers/events/
//  Custom Manager:
//    customer_related → customer=null (no customer linked)
// ─────────────────────────────────────────────────────────────────
export const eventAPI = {
  // GET    /api/customers/events/
  // params: { customer, action, page }
  list: (params = {}) =>
    client.get("/customers/events/", { params }),

  // GET    /api/customers/events/?customer=null  (CustomerRelatedEvtManager)
  unlinked: (params = {}) =>
    client.get("/customers/events/", { params: { ...params, customer: "null" } }),

  // GET    /api/customers/events/:id/
  detail: (id) =>
    client.get(`/customers/events/${id}/`),

  // POST   /api/customers/events/
  // body: { customer (optional), action, description }
  create: (data) =>
    client.post("/customers/events/", data),

  // DELETE /api/customers/events/:id/
  delete: (id) =>
    client.delete(`/customers/events/${id}/`),
};