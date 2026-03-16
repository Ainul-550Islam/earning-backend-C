// src/api/endpoints/gamification.js
import client from '../client';

// Contest Cycles
export const getContestCycles    = (params = {})      => client.get('/gamification/contest-cycles/', { params });
export const getContestCycle     = (id)               => client.get(`/gamification/contest-cycles/${id}/`);
export const createContestCycle  = (data)             => client.post('/gamification/contest-cycles/', data);
export const updateContestCycle  = (id, data)         => client.patch(`/gamification/contest-cycles/${id}/`, data);
export const deleteContestCycle  = (id)               => client.delete(`/gamification/contest-cycles/${id}/`);
export const activateCycle       = (id)               => client.post(`/gamification/contest-cycles/${id}/activate/`);
export const completeCycle       = (id)               => client.post(`/gamification/contest-cycles/${id}/complete/`);
export const distributeRewards   = (id)               => client.post(`/gamification/contest-cycles/${id}/distribute-rewards/`);
export const getCycleLeaderboard = (id, scope='GLOBAL') => client.get(`/gamification/contest-cycles/${id}/leaderboard/`, { params: { scope } });

// Leaderboard Snapshots
export const getSnapshots        = (params = {})      => client.get('/gamification/leaderboard-snapshots/', { params });
export const generateSnapshot    = (data)             => client.post('/gamification/leaderboard-snapshots/generate/', data);

// Rewards
export const getRewards          = (params = {})      => client.get('/gamification/rewards/', { params });
export const createReward        = (data)             => client.post('/gamification/rewards/', data);
export const updateReward        = (id, data)         => client.patch(`/gamification/rewards/${id}/`, data);
export const deleteReward        = (id)               => client.delete(`/gamification/rewards/${id}/`);

// Achievements
export const getAchievements     = (params = {})      => client.get('/gamification/achievements/', { params });
export const getMyPoints         = (cycleId = '')     => client.get('/gamification/achievements/my-points/', { params: cycleId ? { cycle_id: cycleId } : {} });