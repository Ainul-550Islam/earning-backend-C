// src/api/endpoints/promotions.js
// EarnNexus — Promotions API — 100% Backend Connected

import apiClient from "../client";

export const PROMO_KEYS = {
  all:       ()         => ["promotions"],
  list:      (params)   => ["promotions", "list", params],
  detail:    (id)       => ["promotions", "detail", id],
  stats:     ()         => ["promotions", "stats"],
  sparkline: (id, days) => ["promotions", "sparkline", id, days],
};

// ── List & Detail ──────────────────────────────────────────────────
export const fetchPromotions = (params = {}) =>
  apiClient.get("/promotions/", { params }).then(r => r.data);

export const fetchPromotion = (id) =>
  apiClient.get(`/promotions/${id}/`).then(r => r.data);

// ── Stats & Sparkline ──────────────────────────────────────────────
export const fetchPromoStats = () =>
  apiClient.get("/promotions/stats/").then(r => r.data);

export const fetchSparkline = (id, days = 7) =>
  apiClient.get(`/promotions/${id}/sparkline/`, { params: { days } }).then(r => r.data);

// ── CRUD ───────────────────────────────────────────────────────────
export const createPromotion = (data) =>
  apiClient.post("/promotions/", data).then(r => r.data);

export const updatePromotion = (id, data) =>
  apiClient.put(`/promotions/${id}/`, data).then(r => r.data);

export const patchPromotion = (id, data) =>
  apiClient.patch(`/promotions/${id}/`, data).then(r => r.data);

export const deletePromotion = (id) =>
  apiClient.delete(`/promotions/${id}/`).then(r => r.data);

// ── Status Actions ─────────────────────────────────────────────────
export const pausePromotion   = (id) => apiClient.post(`/promotions/${id}/pause/`).then(r => r.data);
export const resumePromotion  = (id) => apiClient.post(`/promotions/${id}/resume/`).then(r => r.data);
export const archivePromotion = (id) => apiClient.post(`/promotions/${id}/archive/`).then(r => r.data);

// ── Google Ads Style Actions ───────────────────────────────────────
/** Duplicate a campaign (Google Ads style copy) */
export const duplicatePromotion = (id) =>
  apiClient.post(`/promotions/campaigns/${id}/duplicate/`).then(r => r.data);

/** Add more budget to a campaign */
export const topUpBudget = (id, amount) =>
  apiClient.post(`/promotions/campaigns/${id}/budget_top_up/`, { amount }).then(r => r.data);

/** Approve campaign (admin) */
export const approvePromotion = (id) =>
  apiClient.post(`/promotions/campaigns/${id}/approve/`).then(r => r.data);

// ── Submissions ────────────────────────────────────────────────────
/** List submissions (admin reviews worker proofs) */
export const fetchSubmissions = (params = {}) =>
  apiClient.get("/promotions/submissions/", { params }).then(r => r.data);

export const approveSubmission = (id, note = "") =>
  apiClient.post(`/promotions/submissions/${id}/approve/`, { note }).then(r => r.data);

export const rejectSubmission = (id, note) =>
  apiClient.post(`/promotions/submissions/${id}/reject/`, { note }).then(r => r.data);

// ── Bidding (Ad Auction) ───────────────────────────────────────────
export const fetchBids = () =>
  apiClient.get("/promotions/bidding/").then(r => r.data);

export const placeBid = (data) =>
  apiClient.post("/promotions/bidding/", data).then(r => r.data);

export const resolveBid = (id, action) =>
  apiClient.post(`/promotions/bidding/${id}/resolve/`, { action }).then(r => r.data);

// ── Analytics ──────────────────────────────────────────────────────
export const fetchCampaignAnalytics = (campaignId, params = {}) =>
  apiClient.get("/promotions/analytics/", { params: { campaign: campaignId, ...params } }).then(r => r.data);

export const fetchOverallAnalytics = () =>
  apiClient.get("/promotions/analytics/overall/").then(r => r.data);

// ── Finance ────────────────────────────────────────────────────────
export const fetchTransactions = (params = {}) =>
  apiClient.get("/promotions/transactions/", { params }).then(r => r.data);

export const fetchTransactionSummary = () =>
  apiClient.get("/promotions/transactions/summary/").then(r => r.data);

// ── Fraud & Security ───────────────────────────────────────────────
export const fetchFraudReports = (params = {}) =>
  apiClient.get("/promotions/fraud-reports/", { params }).then(r => r.data);

export const takeFraudAction = (id, action, note = "") =>
  apiClient.post(`/promotions/fraud-reports/${id}/take_action/`, { action, note }).then(r => r.data);

export const checkBlacklist = (type, value) =>
  apiClient.post("/promotions/blacklist/check/", { type, value }).then(r => r.data);

// ── Disputes ───────────────────────────────────────────────────────
export const fetchDisputes = (params = {}) =>
  apiClient.get("/promotions/disputes/", { params }).then(r => r.data);

export const resolveDispute = (id, data) =>
  apiClient.post(`/promotions/disputes/${id}/resolve/`, data).then(r => r.data);

// ── Reward Policies (Country-based rates) ─────────────────────────
export const fetchRewardPolicies = (params = {}) =>
  apiClient.get("/promotions/reward-policies/", { params }).then(r => r.data);

export const fetchRewardByCountry = (countryCode) =>
  apiClient.get(`/promotions/reward-policies/by-country/${countryCode}/`).then(r => r.data);

// ── User Offers (Worker side) ──────────────────────────────────────
export const fetchUserOffers = () =>
  apiClient.get("/promotions/user-offers/").then(r => r.data);

export const submitUserOffer = (data) =>
  apiClient.post("/promotions/user-offers/", data).then(r => r.data);