// src/api/endpoints/wallet.js
import client from '../client';

const walletAPI = {

  // ─── DASHBOARD ────────────────────────────────────────────────────────────
  getDashboardStats: () =>
    client.get('/wallet/summary/'),

  // ─── WALLETS ──────────────────────────────────────────────────────────────
  getAllWallets: (params = {}) =>
    client.get('/wallet/wallets/', { params }),

  getWalletDetail: (walletId) =>
    client.get(`/wallet/wallets/${walletId}/`),

  lockWallet: (walletId, reason) =>
    client.post(`/wallet/wallets/${walletId}/lock/`, { reason }),

  unlockWallet: (walletId) =>
    client.post(`/wallet/wallets/${walletId}/unlock/`),

  freezeWallet: (walletId, amount, reason) =>
    client.post(`/wallet/wallets/${walletId}/freeze_balance/`, { amount, reason }),

  unfreezeWallet: (walletId, amount, reason) =>
    client.post(`/wallet/wallets/${walletId}/unfreeze_balance/`, { amount, reason }),

  // ─── TRANSACTIONS ─────────────────────────────────────────────────────────
  getTransactions: (params = {}) =>
    client.get('/wallet/transactions/', { params }),

  getTransactionDetail: (transactionId) =>
    client.get(`/wallet/transactions/${transactionId}/`),

  approveTransaction: (transactionId) =>
    client.post(`/wallet/transactions/${transactionId}/approve/`),

  rejectTransaction: (transactionId, reason) =>
    client.post(`/wallet/transactions/${transactionId}/reject/`, { reason }),

  reverseTransaction: (transactionId, reason) =>
    client.post(`/wallet/transactions/${transactionId}/reverse/`, { reason }),

  // ✅ Quick Transfer — wallet.jsx Transfer button
  quickTransfer: ({ recipient, amount, currency }) =>
    client.post('/wallet/transfer/', { recipient, amount, currency }),

  // ─── WITHDRAWAL ───────────────────────────────────────────────────────────
  getWithdrawalRequests: (params = {}) =>
    client.get('/wallet/withdrawals/', { params }),

  getWithdrawalRequestDetail: (id) =>
    client.get(`/wallet/withdrawals/${id}/`),

  approveWithdrawal: (id) =>
    client.post(`/wallet/withdrawals/${id}/process/`),

  rejectWithdrawal: (id, adminNote) =>
    client.post(`/wallet/withdrawals/${id}/reject/`, { reason: adminNote }),

  // ✅ User withdrawal request — Wallet.jsx "Request Withdrawal" button
  requestWithdrawal: ({ amount, payment_method_id, note }) =>
    client.post('/wallet/request-withdrawal/', { amount, payment_method_id, note }),

  // ─── PAYMENT METHODS ──────────────────────────────────────────────────────
  getPaymentMethods: (params = {}) =>
    client.get('/wallet/payment-methods/', { params }),

  verifyPaymentMethod: (methodId) =>
    client.post(`/wallet/payment-methods/${methodId}/verify/`),

  // ─── MINING ───────────────────────────────────────────────────────────────
  // ✅ Mining Start/Stop — Wallet.jsx mining button
  startMining: () =>
    client.post('/wallet/mining/start/'),

  stopMining: () =>
    client.post('/wallet/mining/stop/'),

  getMiningStatus: () =>
    client.get('/wallet/mining/status/'),

  // ─── WEBHOOK LOGS ─────────────────────────────────────────────────────────
  getWebhookLogs: (params = {}) =>
    client.get('/wallet/webhook-logs/', { params }),

};

export default walletAPI;