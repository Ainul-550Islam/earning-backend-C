// src/api/endpoint/postback.js
// ═══════════════════════════════════════════════════════════════════════════
//  ALL endpoints match exactly:
//    models.py  •  viewsets.py  •  views.py  •  urls.py  •  serializers.py
//
//  BASE: /postback/
// ═══════════════════════════════════════════════════════════════════════════

import axiosInstance from "../axiosInstance";

// ── Safe response extractor ───────────────────────────────────────────────────
const safeData = (res) => res?.data ?? null;

// ── Normalise axios error into a plain object ─────────────────────────────────
const normaliseError = (err) => ({
  message:
    err?.message ||
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    "Unknown error",
  status:  err?.response?.status  ?? null,
  data:    err?.response?.data    ?? null,
  isNetworkError: !err?.response,
  isAuthError:    err?.response?.status === 401,
  isNotFound:     err?.response?.status === 404,
  isServerError:  (err?.response?.status ?? 0) >= 500,
});

// ── Generic safe caller ───────────────────────────────────────────────────────
// Returns { data, error } — never throws.
const safeCall = async (fn) => {
  try {
    const res = await fn();
    return { data: safeData(res), error: null };
  } catch (err) {
    return { data: null, error: normaliseError(err) };
  }
};

// ── Query-string builder (filters out null / undefined) ───────────────────────
const buildParams = (obj = {}) =>
  Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== ""),
  );


// ═══════════════════════════════════════════════════════════════════════════
//  1.  NETWORK POSTBACK CONFIG
//      /postback/networks/
// ═══════════════════════════════════════════════════════════════════════════

export const networkAPI = {

  /**
   * GET /postback/networks/
   * Returns NetworkPostbackConfigListSerializer[]
   * Supports: search, ordering, status filter, network_type filter, page
   *
   * @param {object} params
   * @param {string}  [params.search]        – searches name, network_key
   * @param {string}  [params.status]        – ACTIVE | INACTIVE | TESTING
   * @param {string}  [params.network_type]  – CPA | CPL | CPS | CPI | REV_SHARE
   * @param {string}  [params.ordering]      – name | created_at | status (prefix - for desc)
   * @param {number}  [params.page]          – pagination page number
   * @param {number}  [params.page_size]     – items per page
   */
  list: (params = {}) =>
    safeCall(() =>
      axiosInstance.get("/postback/networks/", {
        params: buildParams(params),
      }),
    ),

  /**
   * GET /postback/networks/{id}/
   * Returns NetworkPostbackConfigDetailSerializer
   * NOTE: secret_key is write-only — never returned
   *
   * @param {string} id – UUID
   */
  retrieve: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.get(`/postback/networks/${id}/`));
  },

  /**
   * POST /postback/networks/
   * Body: NetworkPostbackConfigWriteSerializer
   *
   * Required fields:
   *   name, network_key, secret_key
   * Optional:
   *   network_type, status, signature_algorithm,
   *   ip_whitelist, trust_forwarded_for, require_nonce,
   *   field_mapping, required_fields, dedup_window,
   *   reward_rules, default_reward_points,
   *   rate_limit_per_minute, contact_email, notes, metadata
   *
   * @param {object} payload
   */
  create: (payload = {}) => {
    if (!payload.name || !payload.network_key || !payload.secret_key) {
      return Promise.resolve({
        data: null,
        error: { message: "name, network_key and secret_key are required" },
      });
    }
    return safeCall(() => axiosInstance.post("/postback/networks/", payload));
  },

  /**
   * PUT /postback/networks/{id}/
   * Full update — NetworkPostbackConfigWriteSerializer
   *
   * @param {string} id
   * @param {object} payload
   */
  update: (id, payload = {}) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.put(`/postback/networks/${id}/`, payload));
  },

  /**
   * PATCH /postback/networks/{id}/
   * Partial update
   *
   * @param {string} id
   * @param {object} payload – only the fields to change
   */
  partialUpdate: (id, payload = {}) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.patch(`/postback/networks/${id}/`, payload));
  },

  /**
   * DELETE /postback/networks/{id}/
   *
   * @param {string} id
   */
  destroy: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.delete(`/postback/networks/${id}/`));
  },

  // ── Custom actions ────────────────────────────────────────────────────────

  /**
   * POST /postback/networks/{id}/activate/
   * Switches status → ACTIVE
   * Returns NetworkPostbackConfigDetailSerializer
   *
   * @param {string} id
   */
  activate: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.post(`/postback/networks/${id}/activate/`));
  },

  /**
   * POST /postback/networks/{id}/deactivate/
   * Switches status → INACTIVE
   * Returns NetworkPostbackConfigDetailSerializer
   *
   * @param {string} id
   */
  deactivate: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.post(`/postback/networks/${id}/deactivate/`));
  },

  /**
   * GET /postback/networks/{id}/validators/
   * Returns LeadValidatorSerializer[]
   *
   * @param {string} id
   */
  listValidators: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.get(`/postback/networks/${id}/validators/`));
  },

  /**
   * POST /postback/networks/{id}/validators/
   * Creates a new LeadValidator for this network
   *
   * Required: name, validator_type
   * Optional: params, is_blocking, sort_order, is_active, failure_reason
   *
   * validator_type options:
   *   field_present | field_regex | payout_range |
   *   offer_whitelist | user_must_exist | ip_reputation | custom_expression
   *
   * @param {string} id
   * @param {object} payload
   */
  createValidator: (id, payload = {}) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    if (!payload.name || !payload.validator_type) {
      return Promise.resolve({
        data: null,
        error: { message: "name and validator_type are required" },
      });
    }
    return safeCall(() =>
      axiosInstance.post(`/postback/networks/${id}/validators/`, payload),
    );
  },

  /**
   * GET /postback/networks/{id}/stats/
   * Returns per-network postback counts (total, rewarded, rejected, duplicate, failed)
   *
   * @param {string} id
   */
  stats: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.get(`/postback/networks/${id}/stats/`));
  },
};


// ═══════════════════════════════════════════════════════════════════════════
//  2.  POSTBACK LOGS  (read-only + retry)
//      /postback/logs/
// ═══════════════════════════════════════════════════════════════════════════

export const logsAPI = {

  /**
   * GET /postback/logs/
   * Returns PostbackLogSerializer[] (paginated)
   *
   * Filter params (match PostbackLogFilter):
   * @param {object} params
   * @param {string}  [params.status]          – RECEIVED|PROCESSING|VALIDATED|REWARDED|REJECTED|DUPLICATE|FAILED
   * @param {string}  [params.network]         – network UUID
   * @param {string}  [params.network__network_key] – network_key slug
   * @param {string}  [params.lead_id]         – exact match
   * @param {string}  [params.offer_id]        – exact match
   * @param {string}  [params.source_ip]       – exact IP
   * @param {boolean} [params.signature_verified]
   * @param {boolean} [params.ip_whitelisted]
   * @param {string}  [params.received_at__gte] – ISO datetime
   * @param {string}  [params.received_at__lte] – ISO datetime
   * @param {string}  [params.ordering]         – received_at | processed_at | status | payout
   * @param {number}  [params.page]
   * @param {number}  [params.page_size]
   */
  list: (params = {}) =>
    safeCall(() =>
      axiosInstance.get("/postback/logs/", {
        params: buildParams(params),
      }),
    ),

  /**
   * GET /postback/logs/{id}/
   * Returns PostbackLogDetailSerializer (includes raw_payload + request_headers)
   *
   * @param {string} id – UUID
   */
  retrieve: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.get(`/postback/logs/${id}/`));
  },

  /**
   * POST /postback/logs/{id}/retry/
   * Re-queues a FAILED or REJECTED log via Celery
   * Returns { status: "queued" }
   *
   * @param {string} id – UUID
   */
  retry: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.post(`/postback/logs/${id}/retry/`));
  },
};


// ═══════════════════════════════════════════════════════════════════════════
//  3.  DUPLICATE LEAD CHECKS
//      /postback/duplicates/
// ═══════════════════════════════════════════════════════════════════════════

export const duplicatesAPI = {

  /**
   * GET /postback/duplicates/
   * Returns DuplicateLeadCheckSerializer[] (paginated)
   *
   * @param {object} params
   * @param {string}  [params.network]    – network UUID
   * @param {string}  [params.lead_id]   – exact match
   * @param {string}  [params.ordering]  – -first_seen_at (default)
   * @param {number}  [params.page]
   * @param {number}  [params.page_size]
   */
  list: (params = {}) =>
    safeCall(() =>
      axiosInstance.get("/postback/duplicates/", {
        params: buildParams(params),
      }),
    ),

  /**
   * GET /postback/duplicates/{id}/
   * Returns DuplicateLeadCheckSerializer
   *
   * @param {string} id – UUID
   */
  retrieve: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.get(`/postback/duplicates/${id}/`));
  },

  /**
   * DELETE /postback/duplicates/{id}/
   * Clears a dedup entry — allows the lead to be re-accepted
   *
   * @param {string} id – UUID
   */
  destroy: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() => axiosInstance.delete(`/postback/duplicates/${id}/`));
  },
};


// ═══════════════════════════════════════════════════════════════════════════
//  4.  ADMIN DASHBOARD
//      /postback/admin/dashboard/
// ═══════════════════════════════════════════════════════════════════════════

export const dashboardAPI = {

  /**
   * GET /postback/admin/dashboard/
   * Returns 24-hour summary stats
   *
   * Response shape:
   * {
   *   period_hours: 24,
   *   active_networks: number,
   *   summary: {
   *     total: number, rewarded: number, rejected: number,
   *     duplicate: number, failed: number, pending: number
   *   },
   *   per_network: [
   *     { network__name, network__network_key, total, rewarded, rejected }
   *   ]
   * }
   */
  get: () =>
    safeCall(() => axiosInstance.get("/postback/admin/dashboard/")),
};


// ═══════════════════════════════════════════════════════════════════════════
//  5.  ADMIN LOG RETRY
//      /postback/admin/logs/{id}/retry/
// ═══════════════════════════════════════════════════════════════════════════

export const adminAPI = {

  /**
   * POST /postback/admin/logs/{id}/retry/
   * Admin-level retry — separate from the viewset retry action
   * Returns { status: "queued", log_id: "<uuid>" }
   *
   * @param {string} id – UUID (pk is uuid type in Django)
   */
  retryLog: (id) => {
    if (!id) return Promise.resolve({ data: null, error: { message: "id is required" } });
    return safeCall(() =>
      axiosInstance.post(`/postback/admin/logs/${id}/retry/`),
    );
  },
};


// ═══════════════════════════════════════════════════════════════════════════
//  6.  WEBHOOK INGESTION  (public — no auth header needed)
//      /postback/receive/{network_key}/
// ═══════════════════════════════════════════════════════════════════════════

export const webhookAPI = {

  /**
   * POST /postback/receive/{network_key}/
   * Inbound postback from affiliate network.
   * Security is handled server-side (HMAC signature, IP whitelist, nonce).
   *
   * @param {string} networkKey  – the network's unique slug
   * @param {object} payload     – postback params from the network
   * @param {object} [headers]   – optional extra headers (X-Signature, X-Postback-Nonce, etc.)
   */
  receive: (networkKey, payload = {}, headers = {}) => {
    if (!networkKey) {
      return Promise.resolve({
        data: null,
        error: { message: "networkKey is required" },
      });
    }
    return safeCall(() =>
      axiosInstance.post(
        `/postback/receive/${networkKey}/`,
        payload,
        { headers: { ...headers } },
      ),
    );
  },
};


// ═══════════════════════════════════════════════════════════════════════════
//  DEFAULT EXPORT — all namespaces together
// ═══════════════════════════════════════════════════════════════════════════

const postbackAPI = {
  network:    networkAPI,
  logs:       logsAPI,
  duplicates: duplicatesAPI,
  dashboard:  dashboardAPI,
  admin:      adminAPI,
  webhook:    webhookAPI,
};

export default postbackAPI;
