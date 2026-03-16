// src/api/endpoints/AutoMod.js
import client from '../client';
const BASE = '/auto-mod';

export const ruleApi = {
  list:   (p={})    => client.get(`${BASE}/rules/`, { params: p }),
  get:    (id)      => client.get(`${BASE}/rules/${id}/`),
  create: (d)       => client.post(`${BASE}/rules/`, d),
  update: (id, d)   => client.patch(`${BASE}/rules/${id}/`, d),
  delete: (id)      => client.delete(`${BASE}/rules/${id}/`),
  toggle: (id)      => client.post(`${BASE}/rules/${id}/toggle/`),
};

export const submissionApi = {
  list:       (p={}) => client.get(`${BASE}/submissions/`, { params: p }),
  get:        (id)   => client.get(`${BASE}/submissions/${id}/`),
  submit:     (d)    => client.post(`${BASE}/submissions/submit/`, d),
  review:     (id,d) => client.post(`${BASE}/submissions/${id}/review/`, d),
  rescan:     (id,d) => client.post(`${BASE}/submissions/${id}/rescan/`, d),
  queue:      (p={}) => client.get(`${BASE}/submissions/queue/`, { params: p }),
  stats:      ()     => client.get(`${BASE}/submissions/stats/`),
  bulkAction: (d)    => client.post(`${BASE}/submissions/bulk-action/`, d),
};

export const scanApi = {
  list: (p={}) => client.get(`${BASE}/scans/`, { params: p }),
  get:  (id)   => client.get(`${BASE}/scans/${id}/`),
};

export const botApi = {
  list:   (p={}) => client.get(`${BASE}/bots/`, { params: p }),
  get:    (id)   => client.get(`${BASE}/bots/${id}/`),
  create: (d)    => client.post(`${BASE}/bots/`, d),
  update: (id,d) => client.patch(`${BASE}/bots/${id}/`, d),
  delete: (id)   => client.delete(`${BASE}/bots/${id}/`),
  start:  (id)   => client.post(`${BASE}/bots/${id}/start/`),
  stop:   (id)   => client.post(`${BASE}/bots/${id}/stop/`),
  health: (id)   => client.get(`${BASE}/bots/${id}/health/`),
};

export const dashboardApi = {
  get: () => client.get(`${BASE}/dashboard/`),
};
