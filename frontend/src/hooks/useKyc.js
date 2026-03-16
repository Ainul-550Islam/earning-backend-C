import { useState, useEffect, useCallback } from "react";
import { kycAPI, kycLogAPI } from "../api/endpoints/kyc";

// ─────────────────────────────────────────────────────────────────
//  useKycList → KYC model (admin list view)
// ─────────────────────────────────────────────────────────────────
export const useKycList = (initialFilters = {}) => {
  const [kycList, setKycList] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { status, document_type, is_duplicate, risk_score_min, page }

  const fetchKycList = useCallback(async () => {
    try {
      setLoading(true);
      const [listRes, statsRes] = await Promise.all([
        kycAPI.list(filters),
        kycAPI.stats(),
      ]);
      setKycList(listRes.data?.results ?? listRes.data);
      setStats(statsRes.data);
      // stats: { total, pending, verified, rejected, expired, duplicate }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load KYC records");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // triggers approve() backend method
  // → status=verified, verified_at, expires_at (1yr), user.is_verified=True
  const approve = async (id) => {
    try {
      const { data } = await kycAPI.approve(id);
      setKycList((prev) => prev.map((k) => (k.id === id ? data : k)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers reject() backend method
  const reject = async (id, reason = "") => {
    try {
      const { data } = await kycAPI.reject(id, reason);
      setKycList((prev) => prev.map((k) => (k.id === id ? data : k)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers calculate_risk_score() backend method
  // returns: { risk_score, risk_factors }
  const calculateRisk = async (id) => {
    try {
      const { data } = await kycAPI.calculateRisk(id);
      setKycList((prev) =>
        prev.map((k) =>
          k.id === id
            ? { ...k, risk_score: data.risk_score, risk_factors: data.risk_factors }
            : k
        )
      );
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  // triggers KYCService.check_duplicate_kyc() backend service
  const checkDuplicate = async (id) => {
    try {
      const { data } = await kycAPI.checkDuplicate(id);
      setKycList((prev) =>
        prev.map((k) =>
          k.id === id ? { ...k, is_duplicate: data.is_duplicate } : k
        )
      );
      return { success: true, data };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const updateKyc = async (id, formData) => {
    try {
      const { data } = await kycAPI.update(id, formData);
      setKycList((prev) => prev.map((k) => (k.id === id ? data : k)));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  useEffect(() => { fetchKycList(); }, [fetchKycList]);

  return {
    kycList, stats, loading, error, filters, setFilters,
    approve, reject, calculateRisk, checkDuplicate, updateKyc,
    refetch: fetchKycList,
  };
};

// ─────────────────────────────────────────────────────────────────
//  useKycDetail → single KYC record (admin detail view)
// ─────────────────────────────────────────────────────────────────
export const useKycDetail = (id) => {
  const [kyc, setKyc] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const [kycRes, logsRes] = await Promise.all([
        kycAPI.detail(id),
        kycLogAPI.byKyc(id),
      ]);
      setKyc(kycRes.data);
      setLogs(logsRes.data?.results ?? logsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load KYC detail");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  return { kyc, logs, loading, error, refetch: fetchDetail };
};

// ─────────────────────────────────────────────────────────────────
//  useKycByUser → single user's KYC (from user profile page)
// ─────────────────────────────────────────────────────────────────
export const useKycByUser = (userId) => {
  const [kyc, setKyc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchKyc = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const { data } = await kycAPI.byUser(userId);
      setKyc(data);
    } catch (err) {
      setError(err.response?.data?.detail || "No KYC found for this user");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { fetchKyc(); }, [fetchKyc]);

  return { kyc, loading, error, refetch: fetchKyc };
};

// ─────────────────────────────────────────────────────────────────
//  useKycLogs → KYCVerificationLog model
// ─────────────────────────────────────────────────────────────────
export const useKycLogs = (initialFilters = {}) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  // filters: { kyc, action, performed_by, page }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await kycLogAPI.list(filters);
      setLogs(data?.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load KYC logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return { logs, loading, error, filters, setFilters, refetch: fetchLogs };
};