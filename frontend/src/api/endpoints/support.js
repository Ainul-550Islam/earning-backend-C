// src/api/endpoints/support.js  —  FIXED
import client from "../client";

// ─── SUPPORT SETTINGS ───────────────────────────────
export const supportSettingsAPI = {
  // ✅ FIXED BUG 1: was /support/settings/ — backend was /support/support-settings/
  // Now both match: /support/settings/
  get:    ()       => client.get("/support/settings/"),
  // ✅ FIXED BUG 2: PUT now works — backend GET/PUT/PATCH on same endpoint
  update: (data)   => client.put("/support/settings/", data),
  patch:  (data)   => client.patch("/support/settings/", data),
};

// ─── SUPPORT TICKETS ────────────────────────────────
export const supportTicketAPI = {
  // params: { status, priority, category, search, page }
  list:   (params = {}) => client.get("/support/tickets/", { params }),
  detail: (id)           => client.get(`/support/tickets/${id}/`),

  // ✅ FIXED BUG 3: was /create-ticket/ — now POST /tickets/ (same list endpoint)
  create: (data)         => client.post("/support/tickets/", data),

  // ✅ FIXED BUG 4: PATCH endpoint now exists
  update: (id, data)     => client.patch(`/support/tickets/${id}/`, data),

  // ✅ FIXED BUG 5: DELETE endpoint now exists
  delete: (id)           => client.delete(`/support/tickets/${id}/`),

  // ✅ FIXED BUG 6: respond endpoint now exists
  respond: (id, admin_response) =>
    client.patch(`/support/tickets/${id}/respond/`, { admin_response }),

  // ✅ FIXED BUG 7: stats endpoint now exists
  stats: () => client.get("/support/tickets/stats/"),
};

// ─── FAQ ─────────────────────────────────────────────
export const faqAPI = {
  list:   (params = {}) => client.get("/support/faqs/", { params }),

  // ✅ FIXED BUG 8: detail endpoint now exists
  detail: (id)           => client.get(`/support/faqs/${id}/`),

  // ✅ FIXED BUG 9: POST now works on /faqs/ endpoint
  create: (data)         => client.post("/support/faqs/", data),

  // ✅ FIXED BUG 10: PUT endpoint now exists
  update: (id, data)     => client.put(`/support/faqs/${id}/`, data),

  // ✅ FIXED BUG 11: DELETE endpoint now exists
  delete: (id)           => client.delete(`/support/faqs/${id}/`),
};