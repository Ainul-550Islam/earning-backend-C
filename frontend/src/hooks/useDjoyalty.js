import { useState, useEffect, useCallback } from "react";
import { customerAPI, txnAPI, eventAPI } from "../api/endpoints/customers";

// ─────────────────────────────────────────────────────────────────
//  useCustomers → Customer model
// ─────────────────────────────────────────────────────────────────
export const useCustomers = (initialFilters = {}) => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { search, city, newsletter, page }

  const fetchCustomers = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await customerAPI.list(filters);
      setCustomers(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load customers");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createCustomer = async (formData) => {
    try {
      const { data } = await customerAPI.create(formData);
      setCustomers((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateCustomer = async (id, formData) => {
    try {
      const { data } = await customerAPI.update(id, formData);
      setCustomers((prev) => prev.map((c) => (c.id === id ? data : c)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteCustomer = async (id) => {
    try {
      await customerAPI.delete(id);
      setCustomers((prev) => prev.filter((c) => c.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchCustomers(); }, [fetchCustomers]);

  return {
    customers, loading, error, filters, setFilters,
    createCustomer, updateCustomer, deleteCustomer,
    refetch: fetchCustomers,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useTxns → Txn model (supports all 3 custom managers)
// ─────────────────────────────────────────────────────────────────
export const useTxns = (initialFilters = {}) => {
  const [txns, setTxns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { customer, is_discount, value_lt, value_gt, page }

  const fetchTxns = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await txnAPI.list(filters);
      setTxns(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // FullPriceTxnManager → is_discount=false
  const fetchFullPrice = async () => {
    try {
      const { data } = await txnAPI.fullPrice();
      setTxns(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // DiscountedTxnManager → is_discount=true
  const fetchDiscounted = async () => {
    try {
      const { data } = await txnAPI.discounted();
      setTxns(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  // SpendingTxnManager → value < 0
  const fetchSpending = async () => {
    try {
      const { data } = await txnAPI.spending();
      setTxns(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  const createTxn = async (formData) => {
    // formData: { customer, value, is_discount }
    try {
      const { data } = await txnAPI.create(formData);
      setTxns((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteTxn = async (id) => {
    try {
      await txnAPI.delete(id);
      setTxns((prev) => prev.filter((t) => t.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchTxns(); }, [fetchTxns]);

  return {
    txns, loading, error, filters, setFilters,
    fetchFullPrice,   // FullPriceTxnManager
    fetchDiscounted,  // DiscountedTxnManager
    fetchSpending,    // SpendingTxnManager
    createTxn, deleteTxn,
    refetch: fetchTxns,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useEvents → Event model
// ─────────────────────────────────────────────────────────────────
export const useEvents = (initialFilters = {}) => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { customer, action, page }

  const fetchEvents = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await eventAPI.list(filters);
      setEvents(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // CustomerRelatedEvtManager → customer=null (no customer linked)
  const fetchUnlinked = async () => {
    try {
      const { data } = await eventAPI.unlinked();
      setEvents(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed");
    }
  };

  const createEvent = async (formData) => {
    // formData: { customer (optional), action, description }
    try {
      const { data } = await eventAPI.create(formData);
      setEvents((prev) => [data, ...prev]);
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteEvent = async (id) => {
    try {
      await eventAPI.delete(id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  return {
    events, loading, error, filters, setFilters,
    fetchUnlinked,  // CustomerRelatedEvtManager
    createEvent, deleteEvent,
    refetch: fetchEvents,
  };
};