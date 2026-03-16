// src/hooks/useInventory.js
// Bulletproof Inventory Hooks — Defensive Coding, No Silent Failures

import { useState, useCallback, useEffect, useRef } from 'react';
import { itemApi, inventoryApi, codeApi, catalogApi } from '../api/endpoints/Inventory'; // ✅ FIXED: added catalogApi

// ── Safe utils ────────────────────────────────────────────────────
const safeArr = (d) => Array.isArray(d) ? d : (d?.results ?? []);
const errMsg  = (e) => {
  if (!e) return 'Unknown error';
  if (e?.response?.data) {
    const d = e.response.data;
    if (typeof d === 'string') return d;
    if (d.detail) return d.detail;
    if (d.error)  return d.error;
    // Flatten field errors
    const fields = Object.entries(d)
      .map(([k,v]) => `${k}: ${Array.isArray(v)?v.join(', '):v}`)
      .join(' | ');
    if (fields) return fields;
  }
  return e.message || 'Something went wrong';
};

function useSafeCall() {
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  return useCallback(fn => (...args) => {
    const p = fn(...args);
    return p?.then ? p.catch(e => { if (mounted.current) throw e; }) : p;
  }, []);
}

function useAsyncState(fetcher, deps = []) {
  const [data,    setData]    = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [total,   setTotal]   = useState(0);
  const safe = useSafeCall();

  const fetch = useCallback(safe(async (params = {}) => {
    setLoading(true); setError(null);
    try {
      const res  = await fetcher(params);
      const arr  = safeArr(res.data);
      setData(arr);
      setTotal(res.data?.count ?? arr.length);
      return arr;
    } catch (e) {
      setError(errMsg(e));
      throw e;
    } finally { setLoading(false); }
  }), deps);

  useEffect(() => { fetch(); }, deps);
  return { data, loading, error, total, refetch: fetch, setData };
}

// ══════════════════════════════════════════════════════════════════
// useItems — Reward Items (full CRUD + stock + codes + award)
// ══════════════════════════════════════════════════════════════════
export function useItems() {
  const { data: items, loading, error, total, refetch, setData } = useAsyncState(itemApi.list);
  const safe = useSafeCall();

  const createItem = useCallback(safe(async (d) => {
    const res = await itemApi.create(d);
    setData(p => [res.data, ...p]);
    return res.data;
  }), []);

  const updateItem = useCallback(safe(async (slug, d) => {
    const res = await itemApi.update(slug, d);
    setData(p => p.map(x => x.slug === slug ? res.data : x));
    return res.data;
  }), []);

  const deleteItem = useCallback(safe(async (slug) => {
    await itemApi.delete(slug);
    setData(p => p.filter(x => x.slug !== slug));
  }), []);

  const restockItem = useCallback(safe(async (slug, qty, note = '') => {
    const res = await itemApi.restock(slug, { quantity: qty, note });
    setData(p => p.map(x => x.slug === slug ? { ...x, current_stock: res.data.current_stock ?? x.current_stock } : x));
    return res.data;
  }), []);

  // Backend: AdjustStockSerializer uses `delta` (not quantity/reason → note)
  const adjustStock = useCallback(safe(async (slug, delta, note = '') => {
    const res = await itemApi.adjustStock(slug, { delta, note });
    setData(p => p.map(x => x.slug === slug ? { ...x, current_stock: res.data.current_stock ?? x.current_stock } : x));
    return res.data;
  }), []);

  const getStockHistory = useCallback(safe(async (slug) => {
    const res = await itemApi.stockHistory(slug);
    return safeArr(res.data);
  }), []);

  // Backend: BulkImportCodesSerializer — codes[], optional expires_at, batch_id
  const bulkImportCodes = useCallback(safe(async (slug, codes, opts = {}) => {
    const res = await itemApi.bulkImport(slug, { codes, ...opts });
    return res.data;
  }), []);

  // Backend: GenerateCodesSerializer — count, optional expires_at, batch_id (no prefix)
  const generateCodes = useCallback(safe(async (slug, count, opts = {}) => {
    const res = await itemApi.generateCodes(slug, { count, ...opts });
    return res.data;
  }), []);

  // Backend: AwardItemSerializer — user_id, delivery_method, expires_at
  // ✅ FIXED BUG 1: removed itemId — viewset injects item_id from URL slug automatically
  // viewsets.py: serializer = AwardItemSerializer(data={**request.data, "item_id": str(item.pk)})
  const awardItem = useCallback(safe(async (slug, userId, opts = {}) => {
    const res = await itemApi.award(slug, { user_id: userId, ...opts });
    return res.data;
  }), []);

  return {
    items, loading, error, total, refetch,
    createItem, updateItem, deleteItem,
    restockItem, adjustStock, getStockHistory,
    bulkImportCodes, generateCodes, awardItem,
  };
}

// ══════════════════════════════════════════════════════════════════
// useUserInventory — Per-user inventory entries
// ══════════════════════════════════════════════════════════════════
export function useUserInventory(filters = {}) {
  const filterKey = JSON.stringify(filters);
  const { data: entries, loading, error, total, refetch, setData } = useAsyncState(
    (p) => inventoryApi.list({ ...filters, ...p }), [filterKey]
  );
  const safe = useSafeCall();

  const claimEntry = useCallback(safe(async (id) => {
    const res = await inventoryApi.claim(id);
    setData(p => p.map(x => x.id === id ? { ...x, status: 'claimed' } : x));
    return res.data;
  }), []);

  const revokeEntry = useCallback(safe(async (id, reason = '') => {
    const res = await inventoryApi.revoke(id, { reason });
    setData(p => p.map(x => x.id === id ? { ...x, status: 'revoked' } : x));
    return res.data;
  }), []);

  return { entries, loading, error, total, refetch, claimEntry, revokeEntry };
}

// ══════════════════════════════════════════════════════════════════
// useCodes — Redemption Codes
// ══════════════════════════════════════════════════════════════════
export function useCodes(filters = {}) {
  const filterKey = JSON.stringify(filters);
  const { data: codes, loading, error, total, refetch, setData } = useAsyncState(
    (p) => codeApi.list({ ...filters, ...p }), [filterKey]
  );
  const safe = useSafeCall();

  const voidCode = useCallback(safe(async (id, reason = 'Voided by admin.') => {
    await codeApi.void(id, { reason });
    setData(p => p.map(x => x.id === id ? { ...x, status: 'voided' } : x));
  }), []);

  return { codes, loading, error, total, refetch, voidCode };
}


// ══════════════════════════════════════════════════════════════════
// useCatalog — Public item catalog
// ✅ NEW: was missing — catalogApi existed in Inventory.js but no hook
// ══════════════════════════════════════════════════════════════════
export function useCatalog(params = {}) {
  const { data: items, loading, error, total, refetch } = useAsyncState(
    (p) => catalogApi.list({ ...params, ...p }), [JSON.stringify(params)]
  );
  return { items, loading, error, total, refetch };
}

// ══════════════════════════════════════════════════════════════════
// useMyInventory — Authenticated user's own inventory
// ✅ NEW: was missing — GET /inventory/mine/
// ══════════════════════════════════════════════════════════════════
export function useMyInventory(params = {}) {
  const { data: items, loading, error, total, refetch } = useAsyncState(
    (p) => catalogApi.mine({ ...params, ...p }), [JSON.stringify(params)]
  );
  return { items, loading, error, total, refetch };
}