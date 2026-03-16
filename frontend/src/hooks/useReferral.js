// src/hooks/useReferral.js
import { useState, useEffect, useCallback } from 'react';
import referralAPI from '../api/endpoints/referral';


// ─── 1. Dashboard Stats (Referral Card) ───────────────────────────────────
export const useReferralStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await referralAPI.getReferralStats();
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Referral stats load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, error, refetch: fetchStats };
};


// ─── 2. Referrals List ────────────────────────────────────────────────────
export const useReferrals = (initialParams = {}) => {
  const [referrals, setReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchReferrals = useCallback(async () => {
    try {
      setLoading(true);
      const res = await referralAPI.getReferrals(params);
      setReferrals(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Referrals load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchReferrals(); }, [fetchReferrals]);

  return { referrals, loading, error, setParams, refetch: fetchReferrals };
};


// ─── 3. Referral Earnings List ────────────────────────────────────────────
export const useReferralEarnings = (initialParams = {}) => {
  const [earnings, setEarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchEarnings = useCallback(async () => {
    try {
      setLoading(true);
      const res = await referralAPI.getEarnings(params);
      setEarnings(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Earnings load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchEarnings(); }, [fetchEarnings]);

  // Total commission calculate
  const totalCommission = earnings.reduce(
    (sum, e) => sum + parseFloat(e.amount || 0), 0
  );

  return { earnings, totalCommission, loading, error, setParams, refetch: fetchEarnings };
};


// ─── 4. Referral Settings ─────────────────────────────────────────────────
export const useReferralSettings = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const res = await referralAPI.getSettings();
      // settings সাধারণত একটাই থাকে
      const data = res.data.results?.[0] || res.data[0] || res.data;
      setSettings(data);
    } catch (err) {
      setError(err.response?.data?.message || 'Settings load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  const updateSettings = async (data) => {
    setSaving(true);
    try {
      const res = await referralAPI.updateSettings(data);
      setSettings(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Settings update failed');
    } finally {
      setSaving(false);
    }
  };

  return { settings, loading, saving, error, updateSettings, refetch: fetchSettings };
};


// ─── 5. Single User Referral Detail ──────────────────────────────────────
export const useUserReferral = (userId) => {
  const [referrals, setReferrals] = useState([]);
  const [earnings, setEarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) return;

    const fetchAll = async () => {
      try {
        setLoading(true);
        const [refRes, earnRes] = await Promise.all([
          referralAPI.getUserReferrals(userId),
          referralAPI.getReferrerEarnings(userId),
        ]);
        setReferrals(refRes.data.results || refRes.data);
        setEarnings(earnRes.data.results || earnRes.data);
      } catch (err) {
        setError(err.response?.data?.message || 'User referral load failed');
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [userId]);

  const totalEarned = earnings.reduce(
    (sum, e) => sum + parseFloat(e.amount || 0), 0
  );

  return {
    referrals,
    earnings,
    totalEarned,
    referralCount: referrals.length,
    loading,
    error,
  };
};