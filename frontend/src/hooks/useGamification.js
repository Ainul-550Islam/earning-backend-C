// src/hooks/useGamification.js
import { useState, useEffect, useCallback } from 'react';
import * as api from '../api/endpoints/gamification';

export function useGamification() {
  const [cycles,       setCycles]       = useState([]);
  const [activeCycle,  setActiveCycle]  = useState(null);
  const [leaderboard,  setLeaderboard]  = useState([]);
  const [rewards,      setRewards]      = useState([]);
  const [achievements, setAchievements] = useState([]);
  const [myPoints,     setMyPoints]     = useState({ total_points: 0, rank: null });
  const [stats,        setStats]        = useState({ activeContests: 0, participants: 0, prizePool: 0 });
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fix 3: Run independent fetches in parallel
      const [cyclesRes, rewardsRes, achRes] = await Promise.allSettled([
        api.getContestCycles({ ordering: '-created_at', page_size: 20 }),
        api.getRewards({ page_size: 20 }),
        api.getAchievements({ page_size: 20, ordering: '-awarded_at' }),
      ]);

      // Process cycles (now axios → use .data)
      const cyclesList = cyclesRes.status === 'fulfilled'
        ? (cyclesRes.value.data?.results ?? cyclesRes.value.data ?? [])
        : [];
      setCycles(cyclesList);

      const active = cyclesList.find(c => c.status === 'ACTIVE') || cyclesList[0] || null;
      setActiveCycle(active);
      const activeCount = cyclesList.filter(c => c.status === 'ACTIVE').length;

      // Process rewards
      const rewardsList = rewardsRes.status === 'fulfilled'
        ? (rewardsRes.value.data?.results ?? rewardsRes.value.data ?? [])
        : [];
      setRewards(rewardsList);
      const prizePool = rewardsList.reduce((sum, r) => sum + parseFloat(r.reward_value || 0), 0);

      // Process achievements
      const achList = achRes.status === 'fulfilled'
        ? (achRes.value.data?.results ?? achRes.value.data ?? [])
        : [];
      setAchievements(achList);

      // My points + leaderboard in parallel (both optional/user-specific)
      const [ptsRes, lbRes] = await Promise.allSettled([
        api.getMyPoints(active?.id || ''),
        active?.id ? api.getCycleLeaderboard(active.id, 'GLOBAL') : Promise.resolve(null),
      ]);

      if (ptsRes.status === 'fulfilled' && ptsRes.value?.data) {
        setMyPoints(ptsRes.value.data);
      }

      if (lbRes.status === 'fulfilled' && lbRes.value) {
        const entries = lbRes.value.data?.snapshot_data ?? [];
        setLeaderboard(entries);
        // Fix 5: prefer cycle.participant_count over entries.length
        setStats({
          activeContests: activeCount,
          participants:   active?.participant_count ?? entries.length ?? 0,
          prizePool,
        });
      } else {
        setStats({ activeContests: activeCount, participants: 0, prizePool });
      }

    } catch (err) {
      // Fix 6: safe error message extraction
      const msg = err?.response?.data?.detail
        || err?.response?.data?.message
        || err?.message
        || 'Failed to load gamification data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Countdown to cycle end
  const getTimeLeft = (endDate) => {
    if (!endDate) return { d: '00', h: '00', m: '00' };
    const diff = new Date(endDate) - new Date();
    if (diff <= 0) return { d: '00', h: '00', m: '00' };
    const d = Math.floor(diff / 86400000);
    const h = Math.floor((diff % 86400000) / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    return {
      d: String(d).padStart(2, '0'),
      h: String(h).padStart(2, '0'),
      m: String(m).padStart(2, '0'),
    };
  };

  return {
    cycles, activeCycle, leaderboard, rewards, achievements,
    myPoints, stats, loading, error, refresh: fetchAll, getTimeLeft,
    // Actions — now return axios res, access res.data in component
    activateCycle:     api.activateCycle,
    completeCycle:     api.completeCycle,
    distributeRewards: api.distributeRewards,
    createCycle:       api.createContestCycle,
    createReward:      api.createReward,
    generateSnapshot:  api.generateSnapshot,
  };
}