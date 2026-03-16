import { useState, useEffect, useCallback } from "react";
import {
  offerProviderAPI,
  offerCategoryAPI,
  offerAPI,
  offerClickAPI,
  offerConversionAPI,
  offerWallAPI,
} from "../api/endpoints/offerwall";

// ─────────────────────────────────────────────────────────────────
//  useOfferProviders → OfferProvider model
// ─────────────────────────────────────────────────────────────────
export const useOfferProviders = (initialFilters = {}) => {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, provider_type, page }

  const fetchProviders = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await offerProviderAPI.list(filters);
      setProviders(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load providers");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createProvider = async (formData) => {
    try {
      const { data } = await offerProviderAPI.create(formData);
      setProviders((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateProvider = async (id, formData) => {
    try {
      const { data } = await offerProviderAPI.update(id, formData);
      setProviders((prev) => prev.map((p) => (p.id === id ? data : p)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteProvider = async (id) => {
    try {
      await offerProviderAPI.delete(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers last_sync + offer sync from provider
  const syncProvider = async (id) => {
    try {
      const { data } = await offerProviderAPI.sync(id);
      setProviders((prev) => prev.map((p) => (p.id === id ? { ...p, last_sync: data.last_sync } : p)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const getProviderStats = async (id) => {
    try {
      const { data } = await offerProviderAPI.stats(id);
      return { success: true, data };
      // data: { total_offers, total_conversions, total_revenue }
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchProviders(); }, [fetchProviders]);

  return {
    providers, loading, error, filters, setFilters,
    createProvider, updateProvider, deleteProvider,
    syncProvider, getProviderStats,
    refetch: fetchProviders,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useOfferCategories → OfferCategory model
// ─────────────────────────────────────────────────────────────────
export const useOfferCategories = (initialFilters = {}) => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchCategories = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await offerCategoryAPI.list(filters);
      setCategories(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load categories");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createCategory = async (formData) => {
    try {
      const { data } = await offerCategoryAPI.create(formData);
      setCategories((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateCategory = async (id, formData) => {
    try {
      const { data } = await offerCategoryAPI.update(id, formData);
      setCategories((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteCategory = async (id) => {
    try {
      await offerCategoryAPI.delete(id);
      setCategories((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchCategories(); }, [fetchCategories]);

  return {
    categories, loading, error, filters, setFilters,
    createCategory, updateCategory, deleteCategory,
    refetch: fetchCategories,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useOffers → Offer model
// ─────────────────────────────────────────────────────────────────
export const useOffers = (initialFilters = {}) => {
  const [offers, setOffers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, offer_type, platform, category, provider,
  //            is_featured, is_trending, is_high_risk, search, page }

  const fetchOffers = useCallback(async () => {
    try {
      setLoading(true);
      const [offersRes, statsRes] = await Promise.all([
        offerAPI.list(filters),
        offerAPI.stats(),
      ]);
      setOffers(offersRes.data?.results ?? offersRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load offers");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createOffer = async (formData) => {
    try {
      const { data } = await offerAPI.create(formData);
      setOffers((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateOffer = async (id, formData) => {
    try {
      const { data } = await offerAPI.update(id, formData);
      setOffers((prev) => prev.map((o) => (o.id === id ? data : o)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteOffer = async (id) => {
    try {
      await offerAPI.delete(id);
      setOffers((prev) => prev.filter((o) => o.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers calculate_quality_score() backend method
  const calculateQuality = async (id) => {
    try {
      const { data } = await offerAPI.calculateQuality(id);
      setOffers((prev) => prev.map((o) => (o.id === id ? { ...o, quality_score: data.quality_score } : o)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const toggleFeatured = async (id) => {
    try {
      const { data } = await offerAPI.toggleFeatured(id);
      setOffers((prev) => prev.map((o) => (o.id === id ? data : o)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const toggleTrending = async (id) => {
    try {
      const { data } = await offerAPI.toggleTrending(id);
      setOffers((prev) => prev.map((o) => (o.id === id ? data : o)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchOffers(); }, [fetchOffers]);

  return {
    offers, stats, loading, error, filters, setFilters,
    createOffer, updateOffer, deleteOffer,
    calculateQuality, toggleFeatured, toggleTrending,
    refetch: fetchOffers,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useOfferClicks → OfferClick model
// ─────────────────────────────────────────────────────────────────
export const useOfferClicks = (initialFilters = {}) => {
  const [clicks, setClicks] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { offer, user, is_converted, country, page }

  const fetchClicks = useCallback(async () => {
    try {
      setLoading(true);
      const [clicksRes, statsRes] = await Promise.all([
        offerClickAPI.list(filters),
        offerClickAPI.stats(),
      ]);
      setClicks(clicksRes.data?.results ?? clicksRes.data);
      setStats(statsRes.data);
      // stats: { total, converted, conversion_rate, top_offers, top_countries }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load clicks");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchClicks(); }, [fetchClicks]);

  return {
    clicks, stats, loading, error, filters, setFilters,
    refetch: fetchClicks,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useOfferConversions → OfferConversion model
// ─────────────────────────────────────────────────────────────────
export const useOfferConversions = (initialFilters = {}) => {
  const [conversions, setConversions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, offer, user, is_verified, page }

  const fetchConversions = useCallback(async () => {
    try {
      setLoading(true);
      const [convRes, statsRes] = await Promise.all([
        offerConversionAPI.list(filters),
        offerConversionAPI.stats(),
      ]);
      setConversions(convRes.data?.results ?? convRes.data);
      setStats(statsRes.data);
      // stats: { total, pending, approved, rejected, total_payout }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load conversions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // triggers approve() backend method → credits user wallet
  const approve = async (id) => {
    try {
      const { data } = await offerConversionAPI.approve(id);
      setConversions((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers reject() backend method
  const reject = async (id, reason = "") => {
    try {
      const { data } = await offerConversionAPI.reject(id, reason);
      setConversions((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const bulkApprove = async (ids) => {
    try {
      await offerConversionAPI.bulkApprove(ids);
      setConversions((prev) =>
        prev.map((c) => (ids.includes(c.id) ? { ...c, status: "approved" } : c))
      );
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchConversions(); }, [fetchConversions]);

  return {
    conversions, stats, loading, error, filters, setFilters,
    approve, reject, bulkApprove,
    refetch: fetchConversions,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useOfferWalls → OfferWall model
// ─────────────────────────────────────────────────────────────────
export const useOfferWalls = (initialFilters = {}) => {
  const [walls, setWalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchWalls = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await offerWallAPI.list(filters);
      setWalls(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load offer walls");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createWall = async (formData) => {
    try {
      const { data } = await offerWallAPI.create(formData);
      setWalls((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateWall = async (id, formData) => {
    try {
      const { data } = await offerWallAPI.update(id, formData);
      setWalls((prev) => prev.map((w) => (w.id === id ? data : w)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteWall = async (id) => {
    try {
      await offerWallAPI.delete(id);
      setWalls((prev) => prev.filter((w) => w.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers get_offers() backend method
  const getWallOffers = async (slug, params = {}) => {
    try {
      const { data } = await offerWallAPI.getOffers(slug, params);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchWalls(); }, [fetchWalls]);

  return {
    walls, loading, error, filters, setFilters,
    createWall, updateWall, deleteWall, getWallOffers,
    refetch: fetchWalls,
  };
};