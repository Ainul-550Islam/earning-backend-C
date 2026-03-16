// src/api/endpoints/cache.js  —  COMPLETE CRUD
import client from '../client';

// ── READ ──────────────────────────────────────────────────────────────────────
export const getCacheStats    = ()         => client.get('/cache/');
export const getSystemStats   = ()         => client.get('/cache/stats/');
export const getCacheHealth   = ()         => client.get('/cache/health/');           // ✅ NEW
export const getUserProfile   = (userId)   => client.get(`/cache/user/${userId}/profile/`);
export const getTaskDetail    = (taskId)   => client.get(`/cache/task/${taskId}/`);

// ── KEYS LIST (admin) ─────────────────────────────────────────────────────────
// GET /cache/keys/?pattern=user*&limit=50
export const getCacheKeys = (pattern = '*', limit = 50) =>
  client.get('/cache/keys/', { params: { pattern, limit } });                         // ✅ NEW

// ── CREATE (admin) ────────────────────────────────────────────────────────────
// POST /cache/set/  →  { key, value, timeout }
export const setCacheKey = (key, value, timeout = 300) =>
  client.post('/cache/set/', { key, value, timeout });                                // ✅ NEW

// ── DELETE specific key (admin) ───────────────────────────────────────────────
// DELETE /cache/key/  →  { key } or { pattern }
export const deleteCacheKey     = (key)     => client.delete('/cache/key/', { data: { key } });      // ✅ NEW
export const deleteCachePattern = (pattern) => client.delete('/cache/key/', { data: { pattern } });  // ✅ NEW

// ── CLEAR bulk (existing, FIXED: POST not DELETE) ─────────────────────────────
// POST /cache/clear/  →  { type: "all"|"users"|"stats"|"tasks" }
export const clearCache = (type = 'all') => client.post('/cache/clear/', { type });