// src/hooks/usePromotions.js
// EarnNexus — Promotions React Query hooks
// All hooks for the Promotions Management page

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  PROMO_KEYS,
  fetchPromotions,
  fetchPromotion,
  fetchPromoStats,
  fetchSparkline,
  createPromotion,
  updatePromotion,
  patchPromotion,
  deletePromotion,
  pausePromotion,
  resumePromotion,
  archivePromotion,
} from "../api/endpoints/promotions";

// ================================================================
// MOCK FALLBACK DATA — shown when API is offline
// ================================================================
const MOCK_PROMOS = [
  { id:1, title:"Weekend Bonus Offer",     bonus_rate:20,   yield_optimization:5260, risk_score:8,  risk_level:"LOW",    status:"active", promo_type:"bonus", traffic_monitor:true,  verified:false },
  { id:2, title:"Yield Maximizer Package", bonus_rate:15,   yield_optimization:7835, risk_score:8,  risk_level:"SAFE",   status:"active", promo_type:"yield", traffic_monitor:true,  verified:true  },
  { id:3, title:"Special Bonus Boost",     bonus_rate:25,   yield_optimization:6415, risk_score:7,  risk_level:"HIGH",   status:"active", promo_type:"bonus", traffic_monitor:true,  verified:false },
  { id:4, title:"Fraud Safe Bonus",        bonus_rate:10,   yield_optimization:3975, risk_score:3,  risk_level:"LOW",    status:"active", promo_type:"fraud", traffic_monitor:true,  verified:true  },
  { id:5, title:"Super Bonus Event",       bonus_rate:22,   yield_optimization:8110, risk_score:11, risk_level:"LOW",    status:"active", promo_type:"bonus", traffic_monitor:true,  verified:true  },
  { id:6, title:"Yield Booster Deluxe",    bonus_rate:18.5, yield_optimization:5345, risk_score:5,  risk_level:"MEDIUM", status:"active", promo_type:"yield", traffic_monitor:true,  verified:false },
];

const MOCK_STATS = {
  total: 32105,
  users_engaged: 175508,
  promos_managed: 412,
  active_count: 5,
  paused_count: 1,
};

// ================================================================
// usePromotions — list with filters
// ================================================================
/**
 * Usage:
 *   const { promos, isLoading, isError, isFetching } = usePromotions({ promo_type: "bonus" });
 *
 * Returns real API data, falls back to MOCK_PROMOS when offline.
 */
export function usePromotions(params = {}) {
  const query = useQuery({
    queryKey: PROMO_KEYS.list(params),
    queryFn:  () => fetchPromotions(params),
    staleTime: 30_000,
    retry: 1,
  });

  // Resolve data: DRF paginated → .results, or plain array, or mock
  const promos =
    query.data?.results ??
    (Array.isArray(query.data) ? query.data : null) ??
    (query.isError ? MOCK_PROMOS : null);

  return {
    promos,
    isLoading:  query.isLoading,
    isError:    query.isError,
    isFetching: query.isFetching,
    refetch:    query.refetch,
    // pagination
    count:  query.data?.count   ?? promos?.length ?? 0,
    next:   query.data?.next    ?? null,
    prev:   query.data?.previous ?? null,
  };
}

// ================================================================
// usePromotion — single detail
// ================================================================
/**
 * Usage:
 *   const { promo, isLoading } = usePromotion(promoId);
 */
export function usePromotion(id) {
  const query = useQuery({
    queryKey: PROMO_KEYS.detail(id),
    queryFn:  () => fetchPromotion(id),
    enabled:  !!id,
    staleTime: 60_000,
  });

  return {
    promo:      query.data ?? null,
    isLoading:  query.isLoading,
    isError:    query.isError,
  };
}

// ================================================================
// usePromoStats — sidebar counters
// ================================================================
/**
 * Usage:
 *   const { stats } = usePromoStats();
 *
 * Auto-refreshes every 30 seconds.
 */
export function usePromoStats() {
  const query = useQuery({
    queryKey: PROMO_KEYS.stats(),
    queryFn:  fetchPromoStats,
    staleTime: 30_000,
    retry: 1,
    refetchInterval: 30_000,
  });

  const stats = query.data ?? (query.isError ? MOCK_STATS : null);

  return {
    stats,
    isLoading:  query.isLoading,
    isError:    query.isError,
    isFetching: query.isFetching,
  };
}

// ================================================================
// useSparkline — per-card chart data
// ================================================================
/**
 * Usage:
 *   const { sparkData } = useSparkline(promo.id);
 */
export function useSparkline(id, days = 7) {
  const query = useQuery({
    queryKey: PROMO_KEYS.sparkline(id, days),
    queryFn:  () => fetchSparkline(id, days),
    enabled:  !!id,
    staleTime: 120_000,
    retry: 1,
  });

  return {
    sparkData:  query.data?.data ?? null,
    labels:     query.data?.labels ?? null,
    isLoading:  query.isLoading,
  };
}

// ================================================================
// useCreatePromotion
// ================================================================
/**
 * Usage:
 *   const { mutate, isPending, error } = useCreatePromotion();
 *   mutate({ title, bonus_rate, ... }, { onSuccess: () => closeModal() });
 */
export function useCreatePromotion() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: createPromotion,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });
}

// ================================================================
// useUpdatePromotion  (full PUT)
// ================================================================
/**
 * Usage:
 *   const { mutate, isPending } = useUpdatePromotion();
 *   mutate({ id, data: { title, ... } });
 */
export function useUpdatePromotion() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => updatePromotion(id, data),
    onMutate: async ({ id, data }) => {
      // Optimistic update
      await qc.cancelQueries({ queryKey: PROMO_KEYS.detail(id) });
      const prev = qc.getQueryData(PROMO_KEYS.detail(id));
      qc.setQueryData(PROMO_KEYS.detail(id), (old) => ({ ...old, ...data }));
      return { prev };
    },
    onError: (_err, { id }, ctx) => {
      qc.setQueryData(PROMO_KEYS.detail(id), ctx?.prev);
    },
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.detail(id) });
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });
}

// ================================================================
// usePatchPromotion  (partial PATCH)
// ================================================================
/**
 * Usage:
 *   const { mutate } = usePatchPromotion();
 *   mutate({ id: 3, data: { status: "paused" } });
 */
export function usePatchPromotion() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => patchPromotion(id, data),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.detail(id) });
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });
}

// ================================================================
// useDeletePromotion
// ================================================================
/**
 * Usage:
 *   const { mutate, isPending } = useDeletePromotion();
 *   mutate(promoId);
 */
export function useDeletePromotion() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: deletePromotion,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });
}

// ================================================================
// usePauseResume — toggle pause/resume with optimistic UI
// ================================================================
/**
 * Usage:
 *   const { toggle, isPending } = usePauseResume(promo);
 *   <button onClick={toggle}>PAUSE / RESUME</button>
 */
export function usePauseResume(promo) {
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      promo.status === "paused"
        ? resumePromotion(promo.id)
        : pausePromotion(promo.id),

    // Optimistic: flip status immediately
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: PROMO_KEYS.all() });
      const newStatus = promo.status === "paused" ? "active" : "paused";

      qc.setQueriesData({ queryKey: PROMO_KEYS.all() }, (old) => {
        if (!old) return old;
        const results = old.results ?? old;
        const updated = results.map((p) =>
          p.id === promo.id ? { ...p, status: newStatus } : p
        );
        return old.results ? { ...old, results: updated } : updated;
      });

      return { prevStatus: promo.status };
    },

    onError: (_err, _vars, ctx) => {
      // Rollback
      qc.setQueriesData({ queryKey: PROMO_KEYS.all() }, (old) => {
        if (!old) return old;
        const results = old.results ?? old;
        const rolled = results.map((p) =>
          p.id === promo.id ? { ...p, status: ctx?.prevStatus } : p
        );
        return old.results ? { ...old, results: rolled } : rolled;
      });
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });

  return {
    toggle:    mutation.mutate,
    isPending: mutation.isPending,
    isError:   mutation.isError,
    isPaused:  promo?.status === "paused",
  };
}

// ================================================================
// useArchivePromotion
// ================================================================
/**
 * Usage:
 *   const { mutate } = useArchivePromotion();
 *   mutate(promoId);
 */
export function useArchivePromotion() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: archivePromotion,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROMO_KEYS.all() });
    },
  });
}