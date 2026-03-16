import { useState, useEffect, useCallback } from "react";
import {
  supportSettingsAPI,
  supportTicketAPI,
  faqAPI,
} from "../api/endpoints/support";

// ─────────────────────────────────────────────────────
//  useSupportSettings — SupportSettings model
// ─────────────────────────────────────────────────────
export const useSupportSettings = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await supportSettingsAPI.get();
      setSettings(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = async (formData) => {
    try {
      const { data } = await supportSettingsAPI.update(formData);
      setSettings(data);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return { settings, loading, error, updateSettings, refetch: fetchSettings };
};

// ─────────────────────────────────────────────────────
//  useSupportTickets — SupportTicket model (list)
// ─────────────────────────────────────────────────────
export const useSupportTickets = (initialFilters = {}) => {
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // status, priority, category, search, page

  const fetchTickets = useCallback(async () => {
    try {
      setLoading(true);
      const [ticketRes, statsRes] = await Promise.all([
        supportTicketAPI.list(filters),
        supportTicketAPI.stats(),
      ]);
      setTickets(ticketRes.data?.results ?? ticketRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const respondToTicket = async (id, admin_response) => {
    try {
      const { data } = await supportTicketAPI.respond(id, admin_response);
      setTickets((prev) => prev.map((t) => (t.id === id ? data : t)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateTicket = async (id, payload) => {
    // payload: { status, priority }
    try {
      const { data } = await supportTicketAPI.update(id, payload);
      setTickets((prev) => prev.map((t) => (t.id === id ? data : t)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteTicket = async (id) => {
    try {
      await supportTicketAPI.delete(id);
      setTickets((prev) => prev.filter((t) => t.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  return {
    tickets,
    stats,
    loading,
    error,
    filters,
    setFilters,
    respondToTicket,
    updateTicket,
    deleteTicket,
    refetch: fetchTickets,
  };
};

// ─────────────────────────────────────────────────────
//  useFAQ — FAQ model
// ─────────────────────────────────────────────────────
export const useFAQ = () => {
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFaqs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await faqAPI.list();
      setFaqs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load FAQs");
    } finally {
      setLoading(false);
    }
  }, []);

  const createFaq = async (formData) => {
    try {
      const { data } = await faqAPI.create(formData);
      setFaqs((prev) => [data, ...prev]);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateFaq = async (id, formData) => {
    try {
      const { data } = await faqAPI.update(id, formData);
      setFaqs((prev) => prev.map((f) => (f.id === id ? data : f)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const deleteFaq = async (id) => {
    try {
      await faqAPI.delete(id);
      setFaqs((prev) => prev.filter((f) => f.id !== id));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => {
    fetchFaqs();
  }, [fetchFaqs]);

  return {
    faqs,
    loading,
    error,
    createFaq,
    updateFaq,
    deleteFaq,
    refetch: fetchFaqs,
  };
};