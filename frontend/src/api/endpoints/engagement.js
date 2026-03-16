// src/api/endpoints/engagement.js
import client from '../client';

const engagementAPI = {

  // ─── DAILY CHECK-IN ───────────────────────────────────

  // সব check-in list (admin)
  getCheckIns: (params = {}) =>
    client.get('/engagement/checkins/', { params }),
  // params: { user, date, page }

  // একজন user এর check-in history
  getUserCheckIns: (userId, params = {}) =>
    client.get('/engagement/checkins/', { params: { user: userId, ...params } }),

  // Dashboard stats (total checkins today, avg streak etc.)
  getCheckInStats: () =>
    client.get('/engagement/checkins/stats/'),


  // ─── SPIN WHEEL ───────────────────────────────────────

  // সব spin history (admin)
  getSpinHistory: (params = {}) =>
    client.get('/engagement/spins/', { params }),
  // params: { user, page }

  // একজন user এর spin history
  getUserSpins: (userId) =>
    client.get('/engagement/spins/', { params: { user: userId } }),

  // Spin stats (total spins today, total coins won etc.)
  getSpinStats: () =>
    client.get('/engagement/spins/stats/'),


  // ─── LEADERBOARD ──────────────────────────────────────

  // Leaderboard (date অনুযায়ী)
  getLeaderboard: (params = {}) =>
    client.get('/engagement/leaderboard/', { params }),
  // params: { date: '2026-02-26', page }

  // Today's leaderboard
  getTodayLeaderboard: () =>
    client.get('/engagement/leaderboard/', {
      params: { date: new Date().toISOString().slice(0, 10) }
    }),


  // ─── LEADERBOARD REWARDS ──────────────────────────────

  getLeaderboardRewards: () =>
    client.get('/engagement/leaderboard-rewards/'),

  updateLeaderboardReward: (rank, coins) =>
    client.patch(`/engagement/leaderboard-rewards/${rank}/`, { reward_coins: coins }),


  // ─── ENGAGEMENT DASHBOARD STATS ───────────────────────

  // Dashboard এর Engagement card (89%) এর জন্য
  getEngagementStats: () =>
    client.get('/engagement/stats/'),

};

export default engagementAPI;