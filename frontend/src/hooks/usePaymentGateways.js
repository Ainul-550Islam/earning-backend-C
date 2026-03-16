import { useState, useEffect, useCallback } from "react";
import {
  paymentGatewayAPI,
  gatewayConfigAPI,
  paymentGatewayMethodAPI,
  gatewayTransactionAPI,
  payoutRequestAPI,
  currencyAPI,
  webhookLogAPI,
} from "../api/endpoints/paymentGateways";

// ─────────────────────────────────────────────────────────────────
//  usePaymentGateways → PaymentGateway model
// ─────────────────────────────────────────────────────────────────
export const usePaymentGateways = (initialFilters = {}) => {
  const [gateways, setGateways] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchGateways = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await paymentGatewayAPI.list(filters);
      setGateways(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load gateways");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createGateway = async (formData) => {
    try {
      const { data } = await paymentGatewayAPI.create(formData);
      setGateways((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateGateway = async (id, formData) => {
    try {
      const { data } = await paymentGatewayAPI.update(id, formData);
      setGateways((prev) => prev.map((g) => (g.id === id ? data : g)));
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteGateway = async (id) => {
    try {
      await paymentGatewayAPI.delete(id);
      setGateways((prev) => prev.filter((g) => g.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // status: 'active' | 'inactive' | 'maintenance'
  const toggleStatus = async (id, status) => {
    try {
      const { data } = await paymentGatewayAPI.toggleStatus(id, status);
      setGateways((prev) => prev.map((g) => (g.id === id ? data : g)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchGateways(); }, [fetchGateways]);

  return {
    gateways, loading, error, filters, setFilters,
    createGateway, updateGateway, deleteGateway, toggleStatus,
    refetch: fetchGateways,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useGatewayConfig → GatewayConfig model (per gateway)
// ─────────────────────────────────────────────────────────────────
export const useGatewayConfig = (gatewayId) => {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchConfigs = useCallback(async () => {
    if (!gatewayId) return;
    try {
      setLoading(true);
      const { data } = await gatewayConfigAPI.list(gatewayId);
      setConfigs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load configs");
    } finally {
      setLoading(false);
    }
  }, [gatewayId]);

  const createConfig = async (formData) => {
    try {
      const { data } = await gatewayConfigAPI.create({ ...formData, gateway: gatewayId });
      setConfigs((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateConfig = async (id, formData) => {
    try {
      const { data } = await gatewayConfigAPI.update(id, formData);
      setConfigs((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteConfig = async (id) => {
    try {
      await gatewayConfigAPI.delete(id);
      setConfigs((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  return {
    configs, loading, error,
    createConfig, updateConfig, deleteConfig,
    refetch: fetchConfigs,
  };
};

// ─────────────────────────────────────────────────────────────────
//  usePaymentMethods → PaymentGatewayMethod model
// ─────────────────────────────────────────────────────────────────
export const usePaymentMethods = (initialFilters = {}) => {
  const [methods, setMethods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);

  const fetchMethods = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await paymentGatewayMethodAPI.list(filters);
      setMethods(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load payment methods");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const verify = async (id) => {
    try {
      const { data } = await paymentGatewayMethodAPI.verify(id);
      setMethods((prev) => prev.map((m) => (m.id === id ? data : m)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteMethod = async (id) => {
    try {
      await paymentGatewayMethodAPI.delete(id);
      setMethods((prev) => prev.filter((m) => m.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchMethods(); }, [fetchMethods]);

  return {
    methods, loading, error, filters, setFilters,
    verify, deleteMethod,
    refetch: fetchMethods,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useGatewayTransactions → GatewayTransaction model
// ─────────────────────────────────────────────────────────────────
export const useGatewayTransactions = (initialFilters = {}) => {
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, transaction_type, gateway, user, page }

  const fetchTransactions = useCallback(async () => {
    try {
      setLoading(true);
      const [txRes, statsRes] = await Promise.all([
        gatewayTransactionAPI.list(filters),
        gatewayTransactionAPI.stats(),
      ]);
      setTransactions(txRes.data?.results ?? txRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const updateStatus = async (id, status) => {
    try {
      const { data } = await gatewayTransactionAPI.update(id, { status });
      setTransactions((prev) => prev.map((t) => (t.id === id ? data : t)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchTransactions(); }, [fetchTransactions]);

  return {
    transactions, stats, loading, error, filters, setFilters,
    updateStatus,
    refetch: fetchTransactions,
  };
};

// ─────────────────────────────────────────────────────────────────
//  usePayoutRequests → PayoutRequest model
// ─────────────────────────────────────────────────────────────────
export const usePayoutRequests = (initialFilters = {}) => {
  const [payouts, setPayouts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, payout_method, user, page }

  const fetchPayouts = useCallback(async () => {
    try {
      setLoading(true);
      const [payoutRes, statsRes] = await Promise.all([
        payoutRequestAPI.list(filters),
        payoutRequestAPI.stats(),
      ]);
      setPayouts(payoutRes.data?.results ?? payoutRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load payout requests");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const approve = async (id, admin_notes = "") => {
    try {
      const { data } = await payoutRequestAPI.approve(id, admin_notes);
      setPayouts((prev) => prev.map((p) => (p.id === id ? data : p)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const reject = async (id, admin_notes = "") => {
    try {
      const { data } = await payoutRequestAPI.reject(id, admin_notes);
      setPayouts((prev) => prev.map((p) => (p.id === id ? data : p)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const complete = async (id) => {
    try {
      const { data } = await payoutRequestAPI.complete(id);
      setPayouts((prev) => prev.map((p) => (p.id === id ? data : p)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchPayouts(); }, [fetchPayouts]);

  return {
    payouts, stats, loading, error, filters, setFilters,
    approve, reject, complete,
    refetch: fetchPayouts,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useCurrencies → Currency model
// ─────────────────────────────────────────────────────────────────
export const useCurrencies = () => {
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCurrencies = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await currencyAPI.list();
      setCurrencies(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load currencies");
    } finally {
      setLoading(false);
    }
  }, []);

  const createCurrency = async (formData) => {
    try {
      const { data } = await currencyAPI.create(formData);
      setCurrencies((prev) => [...prev, data]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateCurrency = async (id, formData) => {
    try {
      const { data } = await currencyAPI.update(id, formData);
      setCurrencies((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteCurrency = async (id) => {
    try {
      await currencyAPI.delete(id);
      setCurrencies((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers Currency.save() → sets only one default
  const setDefault = async (id) => {
    try {
      await currencyAPI.setDefault(id);
      setCurrencies((prev) =>
        prev.map((c) => ({ ...c, is_default: c.id === id }))
      );
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchCurrencies(); }, [fetchCurrencies]);

  return {
    currencies, loading, error,
    createCurrency, updateCurrency, deleteCurrency, setDefault,
    refetch: fetchCurrencies,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useWebhookLogs → PaymentGatewayWebhookLog model
// ─────────────────────────────────────────────────────────────────
export const useWebhookLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { gateway, processed, page }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await webhookLogAPI.list(filters);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load webhook logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const reprocess = async (id) => {
    try {
      const { data } = await webhookLogAPI.reprocess(id);
      setLogs((prev) => prev.map((l) => (l.id === id ? data : l)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs, loading, error, filters, setFilters,
    reprocess,
    refetch: fetchLogs,
  };
};