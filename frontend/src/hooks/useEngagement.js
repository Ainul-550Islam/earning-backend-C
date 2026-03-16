// src/hooks/useEngagement.js
import { useState, useEffect, useCallback } from 'react';
import engagementAPI from '../api/endpoints/engagement';


// ─── 1. Engagement Dashboard Stats (89% card) ─────────────────────────────
export const useEngagementStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await engagementAPI.getEngagementStats();
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Engagement stats load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, error, refetch: fetchStats };
};


// ─── 2. Daily Check-In Stats ──────────────────────────────────────────────
export const useCheckInStats = () => {
  const [stats, setStats] = useState(null);
  const [checkIns, setCheckIns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, listRes] = await Promise.all([
        engagementAPI.getCheckInStats(),
        engagementAPI.getCheckIns({ page: 1 }),
      ]);
      setStats(statsRes.data);
      setCheckIns(listRes.data.results || listRes.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Check-in data load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  return { stats, checkIns, loading, error, refetch: fetchAll };
};


// ─── 3. Spin Wheel Stats ──────────────────────────────────────────────────
export const useSpinStats = () => {
  const [stats, setStats] = useState(null);
  const [spins, setSpins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, spinsRes] = await Promise.all([
        engagementAPI.getSpinStats(),
        engagementAPI.getSpinHistory({ page: 1 }),
      ]);
      setStats(statsRes.data);
      setSpins(spinsRes.data.results || spinsRes.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Spin data load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  return { stats, spins, loading, error, refetch: fetchAll };
};


// ─── 4. Leaderboard ───────────────────────────────────────────────────────
export const useLeaderboard = (date = null) => {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLeaderboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = date
        ? await engagementAPI.getLeaderboard({ date })
        : await engagementAPI.getTodayLeaderboard();
      setLeaderboard(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Leaderboard load failed');
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { fetchLeaderboard(); }, [fetchLeaderboard]);

  // Top 3 আলাদা করা (podium display এর জন্য)
  const topThree = leaderboard.slice(0, 3);
  const rest = leaderboard.slice(3);

  return { leaderboard, topThree, rest, loading, error, refetch: fetchLeaderboard };
};


// ─── 5. User Engagement Detail ────────────────────────────────────────────
export const useUserEngagement = (userId) => {
  const [checkIns, setCheckIns] = useState([]);
  const [spins, setSpins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) return;

    const fetchAll = async () => {
      try {
        setLoading(true);
        const [checkInRes, spinRes] = await Promise.all([
          engagementAPI.getUserCheckIns(userId),
          engagementAPI.getUserSpins(userId),
        ]);
        setCheckIns(checkInRes.data.results || checkInRes.data);
        setSpins(spinRes.data.results || spinRes.data);
      } catch (err) {
        setError(err.response?.data?.message || 'User engagement load failed');
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [userId]);

  // Streak calculation
  const currentStreak = checkIns[0]?.consecutive_days || 0;
  const totalCoinsFromSpins = spins.reduce((sum, s) => sum + parseFloat(s.coins_won || 0), 0);

  return {
    checkIns, spins,
    currentStreak, totalCoinsFromSpins,
    loading, error,
  };
};