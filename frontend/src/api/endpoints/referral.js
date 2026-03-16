// src/api/endpoints/referral.js
import client from '../client';

const referralAPI = {

  // ─── REFERRAL SETTINGS ────────────────────────────────

  // Settings get (admin)
  getSettings: () =>
    client.get('/referral/settings/'),

  // Settings update
  updateSettings: (data) =>
    client.patch('/referral/settings/1/', data),
  // data: { direct_signup_bonus, referrer_signup_bonus, lifetime_commission_rate, is_active }


  // ─── REFERRALS ────────────────────────────────────────

  // সব referral list
  getReferrals: (params = {}) =>
    client.get('/referral/referrals/', { params }),
  // params: { referrer, signup_bonus_given, page }

  // একটি referral detail
  getReferralDetail: (id) =>
    client.get(`/referral/referrals/${id}/`),

  // Dashboard stats (total referrals, total commission etc.)
  getReferralStats: () =>
    client.get('/referral/stats/'),

  // একজন user এর referrals
  getUserReferrals: (userId, params = {}) =>
    client.get('/referral/referrals/', { params: { referrer: userId, ...params } }),


  // ─── REFERRAL EARNINGS ────────────────────────────────

  // সব earnings list
  getEarnings: (params = {}) =>
    client.get('/referral/earnings/', { params }),
  // params: { referrer, referred_user, page }

  // একজন referrer এর earnings
  getReferrerEarnings: (userId, params = {}) =>
    client.get('/referral/earnings/', { params: { referrer: userId, ...params } }),

};

export default referralAPI;