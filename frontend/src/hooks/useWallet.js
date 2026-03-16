// src/hooks/useWallet.js
import { useState, useEffect, useCallback } from 'react';
import walletAPI from '../api/endpoints/wallet';
// import { useWallets, useWalletDashboardStats, useTransactions } from '../hooks/useWallet';
// ─── 1. Dashboard Stats Hook ───────────────────────────────────────────────
export const useWalletDashboardStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await walletAPI.getDashboardStats();
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Stats load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return { stats, loading, error, refetch: fetchStats };
};


// ─── 2. All Wallets Hook ───────────────────────────────────────────────────
export const useWallets = (initialParams = {}) => {
  const [wallets, setWallets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchWallets = useCallback(async () => {
    try {
      setLoading(true);
      const res = await walletAPI.getAllWallets(params);
      setWallets(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Wallets load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchWallets();
  }, [fetchWallets]);

  // Wallet lock/unlock actions
  const lockWallet = async (walletId, reason) => {
    await walletAPI.lockWallet(walletId, reason);
    fetchWallets(); // refresh
  };

  const unlockWallet = async (walletId) => {
    await walletAPI.unlockWallet(walletId);
    fetchWallets();
  };

  return {
    wallets, loading, error,
    setParams, refetch: fetchWallets,
    lockWallet, unlockWallet,
  };
};


// ─── 3. Transactions Hook ──────────────────────────────────────────────────
export const useTransactions = (initialParams = {}) => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchTransactions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await walletAPI.getTransactions(params);
      setTransactions(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Transactions load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const approveTransaction = async (id) => {
    await walletAPI.approveTransaction(id);
    fetchTransactions();
  };

  const rejectTransaction = async (id, reason) => {
    await walletAPI.rejectTransaction(id, reason);
    fetchTransactions();
  };

  const reverseTransaction = async (id, reason) => {
    await walletAPI.reverseTransaction(id, reason);
    fetchTransactions();
  };

  return {
    transactions, loading, error,
    setParams, refetch: fetchTransactions,
    approveTransaction, rejectTransaction, reverseTransaction,
  };
};


// ─── 4. Withdrawal Requests Hook ──────────────────────────────────────────
export const useWithdrawalRequests = (initialParams = { status: 'pending' }) => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchRequests = useCallback(async () => {
    try {
      setLoading(true);
      const res = await walletAPI.getWithdrawalRequests(params);
      setRequests(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Withdrawal requests load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const approveWithdrawal = async (id) => {
    await walletAPI.approveWithdrawal(id);
    fetchRequests();
  };

  const rejectWithdrawal = async (id, adminNote) => {
    await walletAPI.rejectWithdrawal(id, adminNote);
    fetchRequests();
  };

  return {
    requests, loading, error,
    setParams, refetch: fetchRequests,
    approveWithdrawal, rejectWithdrawal,
  };
};


// ─── 5. Single Wallet Detail Hook ─────────────────────────────────────────
export const useWalletDetail = (walletId) => {
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!walletId) return;

    const fetch = async () => {
      try {
        setLoading(true);
        const res = await walletAPI.getWalletDetail(walletId);
        setWallet(res.data);
      } catch (err) {
        setError(err.response?.data?.message || 'Wallet detail load failed');
      } finally {
        setLoading(false);
      }
    };

    fetch();
  }, [walletId]);

  return { wallet, loading, error };
};