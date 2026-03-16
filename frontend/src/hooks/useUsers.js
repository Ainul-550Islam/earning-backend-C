// src/hooks/useUsers.js
import { useState, useEffect, useCallback } from 'react';
import usersAPI from '../api/endpoints/users';


// ─── 1. Dashboard Stats ────────────────────────────────────────────────────
export const useUserDashboardStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await usersAPI.getUserDashboardStats();
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Stats load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, error, refetch: fetchStats };
};


// ─── 2. Users List ─────────────────────────────────────────────────────────
export const useUsers = (initialParams = {}) => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null });

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await usersAPI.getUsers(params);
      setUsers(res.data.results || res.data);
      setPagination({
        count: res.data.count || 0,
        next: res.data.next,
        previous: res.data.previous,
      });
    } catch (err) {
      setError(err.response?.data?.message || 'Users load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const updateStatus = async (userId, status) => {
    await usersAPI.updateUserStatus(userId, status);
    fetchUsers();
  };

  return {
    users, loading, error, pagination,
    setParams, refetch: fetchUsers,
    updateStatus,
  };
};


// ─── 3. Single User Detail ─────────────────────────────────────────────────
export const useUserDetail = (userId) => {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [stats, setStats] = useState(null);
  const [rank, setRank] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) return;

    const fetchAll = async () => {
      try {
        setLoading(true);
        const [userRes, profileRes, statsRes, rankRes] = await Promise.all([
          usersAPI.getUserDetail(userId),
          usersAPI.getUserProfile(userId),
          usersAPI.getUserStatistics(userId),
          usersAPI.getUserRank(userId),
        ]);
        setUser(userRes.data);
        setProfile(profileRes.data);
        setStats(statsRes.data);
        setRank(rankRes.data);
      } catch (err) {
        setError(err.response?.data?.message || 'User detail load failed');
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [userId]);

  return { user, profile, stats, rank, loading, error };
};


// ─── 4. KYC List ───────────────────────────────────────────────────────────
export const useKYCList = (initialParams = { verification_status: 'pending' }) => {
  const [kycList, setKycList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchKYC = useCallback(async () => {
    try {
      setLoading(true);
      const res = await usersAPI.getKYCList(params);
      setKycList(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'KYC load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchKYC(); }, [fetchKYC]);

  const approveKYC = async (userId) => {
    await usersAPI.approveKYC(userId);
    fetchKYC();
  };

  const rejectKYC = async (userId, reason) => {
    await usersAPI.rejectKYC(userId, reason);
    fetchKYC();
  };

  return {
    kycList, loading, error,
    setParams, refetch: fetchKYC,
    approveKYC, rejectKYC,
  };
};


// ─── 5. Fraud Logs ─────────────────────────────────────────────────────────
export const useFraudLogs = (initialParams = { is_resolved: false }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const res = await usersAPI.getFraudLogs(params);
      setLogs(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Fraud logs load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const resolveFraud = async (logId) => {
    await usersAPI.resolveFraud(logId);
    fetchLogs();
  };

  return {
    logs, loading, error,
    setParams, refetch: fetchLogs,
    resolveFraud,
  };
};


// ─── 6. Login History ──────────────────────────────────────────────────────
export const useLoginHistory = (userId) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) return;
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await usersAPI.getLoginHistory(userId);
        setHistory(res.data.results || res.data);
      } catch (err) {
        setError(err.response?.data?.message || 'Login history load failed');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [userId]);

  return { history, loading, error };
};


// ─── 7. IP Reputation ──────────────────────────────────────────────────────
export const useIPReputations = (initialParams = {}) => {
  const [ips, setIps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchIPs = useCallback(async () => {
    try {
      setLoading(true);
      const res = await usersAPI.getIPReputations(params);
      setIps(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'IP reputations load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchIPs(); }, [fetchIPs]);

  const blacklistIP = async (ipId, reason) => {
    await usersAPI.blacklistIP(ipId, reason);
    fetchIPs();
  };

  return { ips, loading, error, setParams, refetch: fetchIPs, blacklistIP };
};


// ─── 8. Leaderboard ────────────────────────────────────────────────────────
export const useLeaderboard = (params = {}) => {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await usersAPI.getLeaderboard(params);
        setLeaderboard(res.data.results || res.data);
      } catch (err) {
        setError(err.response?.data?.message || 'Leaderboard load failed');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  return { leaderboard, loading, error };
};