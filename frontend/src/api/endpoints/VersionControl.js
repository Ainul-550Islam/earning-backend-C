// src/api/endpoints/VersionControl.js
// Bulletproof Version Control API
// Base: /api/version-control/

import client from '../client';

const BASE = '/version-control';

// ── Update Policies ───────────────────────────────────────────────
export const policyApi = {
  list:       (params = {}) => client.get(`${BASE}/policies/`, { params }),
  create:     (data)        => client.post(`${BASE}/policies/`, data),
  update:     (id, data)    => client.patch(`${BASE}/policies/${id}/`, data),
  delete:     (id)          => client.delete(`${BASE}/policies/${id}/`),
  activate:   (id)          => client.post(`${BASE}/policies/${id}/activate/`),
  deactivate: (id)          => client.post(`${BASE}/policies/${id}/deactivate/`),
};

// ── Maintenance Schedules ─────────────────────────────────────────
export const maintenanceApi = {
  list:   (params = {}) => client.get(`${BASE}/maintenance/`, { params }),
  create: (data)        => client.post(`${BASE}/maintenance/`, data),
  update: (id, data)    => client.patch(`${BASE}/maintenance/${id}/`, data),
  delete: (id)          => client.delete(`${BASE}/maintenance/${id}/`),
  start:  (id)          => client.post(`${BASE}/maintenance/${id}/start/`),
  end:    (id)          => client.post(`${BASE}/maintenance/${id}/end/`),
  cancel: (id)          => client.post(`${BASE}/maintenance/${id}/cancel/`),
  status: ()            => client.get(`${BASE}/maintenance/status/`),
};

// ── Platform Redirects ────────────────────────────────────────────
export const redirectApi = {
  list:   (params = {}) => client.get(`${BASE}/redirects/`, { params }),
  create: (data)        => client.post(`${BASE}/redirects/`, data),
  update: (id, data)    => client.patch(`${BASE}/redirects/${id}/`, data),
  delete: (id)          => client.delete(`${BASE}/redirects/${id}/`),
  resolve:(params = {}) => client.get(`${BASE}/redirects/resolve/`, { params }),
};

// ── Public endpoints ──────────────────────────────────────────────
export const publicApi = {
  versionCheck:      (params = {}) => client.get(`${BASE}/version-check/`, { params }),
  maintenanceStatus: ()            => client.get(`${BASE}/maintenance-status/`),
};
