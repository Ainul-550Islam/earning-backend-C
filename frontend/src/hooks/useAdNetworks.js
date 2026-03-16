import { useState, useEffect, useCallback } from "react";
import {
  adNetworkAPI,
  offerCategoryAPI,
  adOfferAPI,
  userOfferEngagementAPI,
  offerConversionAPI,
  offerWallAPI,
  adWebhookLogAPI,
  networkStatisticAPI,
  offerSyncLogAPI,
  blacklistedIPAPI,
  fraudRuleAPI,
  knownBadIPAPI,
  offerRecommendationAPI,
} from "../api/endpoints/adNetworks";

// ─────────────────────────────────────────────────────────────────
//  useAdNetworks → AdNetwork model
// ─────────────────────────────────────────────────────────────────
export const useAdNetworks = (initialFilters = {}) => {
  const [networks, setNetworks] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchNetworks = useCallback(async () => {
    try {
      setLoading(true);
      const [networksRes, statsRes] = await Promise.all([
        adNetworkAPI.list(filters),
        adNetworkAPI.stats(),
      ]);
      setNetworks(networksRes.data?.results ?? networksRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load ad networks");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createNetwork = async (formData) => {
    try {
      const { data } = await adNetworkAPI.create(formData);
      setNetworks((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateNetwork = async (id, formData) => {
    try {
      const { data } = await adNetworkAPI.update(id, formData);
      setNetworks((prev) => prev.map((n) => (n.id === id ? data : n)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteNetwork = async (id) => {
    try {
      await adNetworkAPI.delete(id);
      setNetworks((prev) => prev.filter((n) => n.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers offer sync from network → updates last_sync, next_sync
  const sync = async (id) => {
    try {
      const { data } = await adNetworkAPI.sync(id);
      setNetworks((prev) => prev.map((n) => (n.id === id ? { ...n, last_sync: data.last_sync } : n)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchNetworks(); }, [fetchNetworks]);

  return {
    networks, stats, loading, error, filters, setFilters,
    createNetwork, updateNetwork, deleteNetwork, sync,
    refetch: fetchNetworks,
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
//  useAdOffers → Offer model
// ─────────────────────────────────────────────────────────────────
export const useAdOffers = (initialFilters = {}) => {
  const [offers, setOffers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchOffers = useCallback(async () => {
    try {
      setLoading(true);
      const [offersRes, statsRes] = await Promise.all([
        adOfferAPI.list(filters),
        adOfferAPI.stats(),
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
      const { data } = await adOfferAPI.create(formData);
      setOffers((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateOffer = async (id, formData) => {
    try {
      const { data } = await adOfferAPI.update(id, formData);
      setOffers((prev) => prev.map((o) => (o.id === id ? data : o)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteOffer = async (id) => {
    try {
      await adOfferAPI.delete(id);
      setOffers((prev) => prev.filter((o) => o.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchOffers(); }, [fetchOffers]);

  return {
    offers, stats, loading, error, filters, setFilters,
    createOffer, updateOffer, deleteOffer,
    refetch: fetchOffers,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useEngagements → UserOfferEngagement model
// ─────────────────────────────────────────────────────────────────
export const useEngagements = (initialFilters = {}) => {
  const [engagements, setEngagements] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, user, offer, page }

  const fetchEngagements = useCallback(async () => {
    try {
      setLoading(true);
      const [engRes, statsRes] = await Promise.all([
        userOfferEngagementAPI.list(filters),
        userOfferEngagementAPI.stats(),
      ]);
      setEngagements(engRes.data?.results ?? engRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load engagements");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const approve = async (id) => {
    try {
      const { data } = await userOfferEngagementAPI.approve(id);
      setEngagements((prev) => prev.map((e) => (e.id === id ? data : e)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const reject = async (id, reason, details = "") => {
    try {
      const { data } = await userOfferEngagementAPI.reject(id, reason, details);
      setEngagements((prev) => prev.map((e) => (e.id === id ? data : e)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchEngagements(); }, [fetchEngagements]);

  return {
    engagements, stats, loading, error, filters, setFilters,
    approve, reject,
    refetch: fetchEngagements,
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
  // filters: { conversion_status, risk_level, is_verified, chargeback_processed, page }

  const fetchConversions = useCallback(async () => {
    try {
      setLoading(true);
      const [convRes, statsRes] = await Promise.all([
        offerConversionAPI.list(filters),
        offerConversionAPI.stats(),
      ]);
      setConversions(convRes.data?.results ?? convRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load conversions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const approve = async (id) => {
    try {
      const { data } = await offerConversionAPI.approve(id);
      setConversions((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

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
        prev.map((c) => (ids.includes(c.id) ? { ...c, conversion_status: "approved" } : c))
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

  useEffect(() => { fetchWalls(); }, [fetchWalls]);

  return {
    walls, loading, error, filters, setFilters,
    createWall, updateWall, deleteWall,
    refetch: fetchWalls,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useBlacklistedIPs → BlacklistedIP model
// ─────────────────────────────────────────────────────────────────
export const useBlacklistedIPs = (initialFilters = {}) => {
  const [ips, setIps] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { reason, is_active, page }

  const fetchIPs = useCallback(async () => {
    try {
      setLoading(true);
      const [ipsRes, statsRes] = await Promise.all([
        blacklistedIPAPI.list(filters),
        blacklistedIPAPI.stats(),
      ]);
      setIps(ipsRes.data?.results ?? ipsRes.data);
      setStats(statsRes.data);
      // stats: triggers get_statistics() backend classmethod
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load blacklisted IPs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const blockIP = async (formData) => {
    // formData: { ip_address, reason, expiry_date }
    try {
      const { data } = await blacklistedIPAPI.create(formData);
      setIps((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateIP = async (id, formData) => {
    try {
      const { data } = await blacklistedIPAPI.update(id, formData);
      setIps((prev) => prev.map((ip) => (ip.id === id ? data : ip)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const unblockIP = async (id) => {
    try {
      await blacklistedIPAPI.delete(id);
      setIps((prev) => prev.filter((ip) => ip.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers is_ip_blacklisted() backend classmethod
  const checkIP = async (ip_address) => {
    try {
      const { data } = await blacklistedIPAPI.checkIP(ip_address);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers cleanup_expired_entries() backend classmethod
  const cleanup = async (batch_size = 1000) => {
    try {
      const { data } = await blacklistedIPAPI.cleanup(batch_size);
      await fetchIPs();
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchIPs(); }, [fetchIPs]);

  return {
    ips, stats, loading, error, filters, setFilters,
    blockIP, updateIP, unblockIP, checkIP, cleanup,
    refetch: fetchIPs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useFraudRules → FraudDetectionRule model
// ─────────────────────────────────────────────────────────────────
export const useFraudRules = (initialFilters = {}) => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { rule_type, action, severity, is_active, page }

  const fetchRules = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await fraudRuleAPI.list(filters);
      setRules(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load fraud rules");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createRule = async (formData) => {
    try {
      const { data } = await fraudRuleAPI.create(formData);
      setRules((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateRule = async (id, formData) => {
    try {
      const { data } = await fraudRuleAPI.update(id, formData);
      setRules((prev) => prev.map((r) => (r.id === id ? data : r)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteRule = async (id) => {
    try {
      await fraudRuleAPI.delete(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchRules(); }, [fetchRules]);

  return {
    rules, loading, error, filters, setFilters,
    createRule, updateRule, deleteRule,
    refetch: fetchRules,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useAdWebhookLogs → AdNetworkWebhookLog model
// ─────────────────────────────────────────────────────────────────
export const useAdWebhookLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await adWebhookLogAPI.list(filters);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load webhook logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const reprocess = async (id) => {
    try {
      const { data } = await adWebhookLogAPI.reprocess(id);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return { logs, loading, error, filters, setFilters, reprocess, refetch: fetchLogs };
};

// ─────────────────────────────────────────────────────────────────
//  useNetworkStatistics → NetworkStatistic model
// ─────────────────────────────────────────────────────────────────
export const useNetworkStatistics = (initialFilters = {}) => {
  const [statistics, setStatistics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { ad_network, date, date_from, date_to, page }

  const fetchStatistics = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await networkStatisticAPI.list(filters);
      setStatistics(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load statistics");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchStatistics(); }, [fetchStatistics]);

  return { statistics, loading, error, filters, setFilters, refetch: fetchStatistics };
};