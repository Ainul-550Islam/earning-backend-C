// src/api/endpoints/PayoutQueue.js
// Bulletproof Payout Queue API
// Base: /api/payout-queue/

import client from '../client';

const BASE = '/payout-queue';

// ── Batches ───────────────────────────────────────────────────────
export const batchApi = {
  list:        (params = {}) => client.get(`${BASE}/batches/`, { params }),
  get:         (id)          => client.get(`${BASE}/batches/${id}/`),
  create:      (data)        => client.post(`${BASE}/batches/`, data),
  update:      (id, data)    => client.patch(`${BASE}/batches/${id}/`, data),
  addItems:    (id, data)    => client.post(`${BASE}/batches/${id}/add-items/`, data),
  process:     (id)          => client.post(`${BASE}/batches/${id}/process/`),
  processAsync:(id)          => client.post(`${BASE}/batches/${id}/process-async/`),
  cancel:      (id)          => client.post(`${BASE}/batches/${id}/cancel/`),
  statistics:  (id)          => client.get(`${BASE}/batches/${id}/statistics/`),
};

// ── Items ─────────────────────────────────────────────────────────
export const itemApi = {
  list:   (params = {}) => client.get(`${BASE}/items/`, { params }),
  get:    (id)          => client.get(`${BASE}/items/${id}/`),
  cancel: (id)          => client.post(`${BASE}/items/${id}/cancel/`),
};

// ── Logs ──────────────────────────────────────────────────────────
export const logApi = {
  list: (params = {}) => client.get(`${BASE}/logs/`, { params }),
  get:  (id)          => client.get(`${BASE}/logs/${id}/`),
};

// ── Priorities ────────────────────────────────────────────────────
export const priorityApi = {
  list:   (params = {}) => client.get(`${BASE}/priorities/`, { params }),
  create: (data)        => client.post(`${BASE}/priorities/`, data),
  update: (id, data)    => client.patch(`${BASE}/priorities/${id}/`, data),
  delete: (id)          => client.delete(`${BASE}/priorities/${id}/`),
};
