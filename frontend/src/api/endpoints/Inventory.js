// src/api/endpoints/Inventory.js
// Bulletproof Inventory API — /api/inventory/

import client from '../client';
const BASE = '/inventory';

// ── Reward Items ──────────────────────────────────────────────────
export const itemApi = {
  list:         (p={})    => client.get(`${BASE}/items/`, { params: p }),
  get:          (slug)    => client.get(`${BASE}/items/${slug}/`),
  create:       (d)       => client.post(`${BASE}/items/`, d),
  update:       (slug, d) => client.patch(`${BASE}/items/${slug}/`, d),
  delete:       (slug)    => client.delete(`${BASE}/items/${slug}/`),
  // Stock actions
  restock:      (slug, d) => client.post(`${BASE}/items/${slug}/restock/`, d),
  adjustStock:  (slug, d) => client.post(`${BASE}/items/${slug}/adjust-stock/`, d),
  stockHistory: (slug)    => client.get(`${BASE}/items/${slug}/stock-history/`),
  // Code actions
  bulkImport:   (slug, d) => client.post(`${BASE}/items/${slug}/bulk-import-codes/`, d),
  generateCodes:(slug, d) => client.post(`${BASE}/items/${slug}/generate-codes/`, d),
  // Award
  award:        (slug, d) => client.post(`${BASE}/items/${slug}/award/`, d),
};

// ── User Inventory ────────────────────────────────────────────────
export const inventoryApi = {
  list:   (p={}) => client.get(`${BASE}/user-inventory/`, { params: p }),
  get:    (id)   => client.get(`${BASE}/user-inventory/${id}/`),
  claim:  (id)   => client.post(`${BASE}/user-inventory/${id}/claim/`),
  revoke: (id,d) => client.post(`${BASE}/user-inventory/${id}/revoke/`, d),
};

// ── Redemption Codes ──────────────────────────────────────────────
export const codeApi = {
  list:  (p={}) => client.get(`${BASE}/codes/`, { params: p }),
  get:   (id)   => client.get(`${BASE}/codes/${id}/`),
  void:  (id, d={}) => client.post(`${BASE}/codes/${id}/void/`, d),
};

// ── Public ────────────────────────────────────────────────────────
export const catalogApi = {
  list: (p={}) => client.get(`${BASE}/catalog/`, { params: p }),
  mine: (p={}) => client.get(`${BASE}/mine/`, { params: p }),
};