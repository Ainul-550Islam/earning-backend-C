// src/pages/Engagement.jsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../styles/engagement.css';

// ── Auth helper ────────────────────────────────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ── API ────────────────────────────────────────────────────────────────────────
const BASE = '/api/engagement';
const API = {
  getDailyStats:     () => fetch(`${BASE}/daily-stats/`,           { headers: authHeaders() }),
  getLeaderboard:    () => fetch(`${BASE}/leaderboard/`,           { headers: authHeaders() }),
  dailyCheckin:      () => fetch(`${BASE}/daily-checkin/`,         { method:'POST', headers: authHeaders() }),
  spinWheel:         () => fetch(`${BASE}/spin-wheel/`,            { method:'POST', headers: authHeaders() }),
  // ✅ NEW: real data endpoints
  getCheckIns:       (p='') => fetch(`${BASE}/checkins/${p}`,      { headers: authHeaders() }),
  getSpins:          (p='') => fetch(`${BASE}/spins/${p}`,         { headers: authHeaders() }),
  getRewards:        () => fetch(`${BASE}/leaderboard-rewards/`,   { headers: authHeaders() }),
  updateReward:      (rank, coins) => fetch(`${BASE}/leaderboard-rewards/${rank}/`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reward_coins: coins }),
  }),
};

async function safeFetch(fn) {
  try {
    const res = await fn();
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

// ── Wheel segments ─────────────────────────────────────────────────────────────
const SEGMENTS = [
  { label:'5',   color:'#00f5ff', coins:5   },
  { label:'0',   color:'#1a1a2e', coins:0   },
  { label:'20',  color:'#7b2fff', coins:20  },
  { label:'10',  color:'#1a1a2e', coins:10  },
  { label:'50',  color:'#ffd700', coins:50  },
  { label:'0',   color:'#1a1a2e', coins:0   },
  { label:'15',  color:'#ff2d78', coins:15  },
  { label:'100', color:'#00ff88', coins:100 },
];

function SpinWheelSVG({ spinning, rotation }) {
  const cx = 80, cy = 80, r = 72;
  const n = SEGMENTS.length;
  const angle = (2 * Math.PI) / n;

  return (
    <svg viewBox="0 0 160 160" className={`spin-wheel-svg${spinning ? ' spinning' : ''}`}
      style={{ transform: `rotate(${rotation}deg)` }}>
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      {SEGMENTS.map((seg, i) => {
        const startAngle = i * angle - Math.PI / 2;
        const endAngle   = startAngle + angle;
        const x1 = cx + r * Math.cos(startAngle);
        const y1 = cy + r * Math.sin(startAngle);
        const x2 = cx + r * Math.cos(endAngle);
        const y2 = cy + r * Math.sin(endAngle);
        const midAngle = startAngle + angle / 2;
        const tx = cx + (r * .62) * Math.cos(midAngle);
        const ty = cy + (r * .62) * Math.sin(midAngle);
        return (
          <g key={i}>
            <path
              d={`M${cx},${cy} L${x1},${y1} A${r},${r} 0 0,1 ${x2},${y2} Z`}
              fill={seg.color}
              stroke="#020609" strokeWidth="1.5"
            />
            <text x={tx} y={ty} textAnchor="middle" dominantBaseline="middle"
              fontSize="9" fontFamily="'Orbitron',sans-serif" fontWeight="700"
              fill={seg.color === '#1a1a2e' ? '#555' : '#000'}
              transform={`rotate(${(i * 360/n + 360/n/2)}, ${tx}, ${ty})`}>
              {seg.label}
            </text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r="14" fill="#020609" stroke="rgba(0,245,255,0.3)" strokeWidth="1.5"/>
      <circle cx={cx} cy={cy} r="6"  fill="rgba(0,245,255,0.4)"/>
    </svg>
  );
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3200); return () => clearTimeout(t); }, [onClose]);
  return <div className={`eng-toast ${type}`}>{msg}</div>;
}

// ── Mock data fallbacks ────────────────────────────────────────────────────────
const MOCK_LB = [
  { rank:1, username:'CryptoKing',  coins_earned:1250, is_current_user:false },
  { rank:2, username:'NightOwl_X',  coins_earned:980,  is_current_user:false },
  { rank:3, username:'StarChaser',  coins_earned:760,  is_current_user:false },
  { rank:4, username:'You',         coins_earned:540,  is_current_user:true  },
  { rank:5, username:'ShadowFox',   coins_earned:420,  is_current_user:false },
];

const MOCK_ACTIVITY = [
  { type:'checkin', label:'Daily Check-in Completed',   meta:'2 mins ago',  color:'gold',  badge:'+5 coins'   },
  { type:'spin',    label:'Spin Wheel — Lucky Win!',    meta:'18 mins ago', color:'green', badge:'+50 coins'  },
  { type:'task',    label:'Task Completed',             meta:'1 hr ago',    color:'cyan',  badge:'+25 coins'  },
  { type:'streak',  label:'7-Day Streak Milestone',     meta:'Today',       color:'pink',  badge:'🔥 Bonus'   },
  { type:'referral',label:'Referral Reward Received',  meta:'Yesterday',   color:'gold',  badge:'+100 coins' },
];

const MOCK_REWARDS = [
  { rank:1, label:'1st Place',    coins:500 },
  { rank:2, label:'2nd Place',    coins:300 },
  { rank:3, label:'3rd Place',    coins:150 },
  { rank:4, label:'Top 10',       coins:50  },
  { rank:5, label:'Top 25',       coins:25  },
];

// ── Main Component ─────────────────────────────────────────────────────────────
export default function EngagementPage() {
  const [stats,      setStats]      = useState(null);
  const [leaderboard,setLeaderboard]= useState(MOCK_LB);
  const [balance,    setBalance]    = useState(0);
  const [spinning,   setSpinning]   = useState(false);
  const [spinDeg,    setSpinDeg]    = useState(0);
  const [spinResult, setSpinResult] = useState(null);
  const [toast,      setToast]      = useState(null);
  const [loading,    setLoading]    = useState(true);
  // ✅ NEW: real data state
  const [checkIns,   setCheckIns]   = useState([]);
  const [spins,      setSpins]      = useState([]);
  const [rewards,    setRewards]    = useState(MOCK_REWARDS);
  const [editReward, setEditReward] = useState(null); // { rank, coins }
  const [adminTab,   setAdminTab]   = useState('checkins'); // 'checkins'|'spins'|'rewards'
  const [showAdmin,  setShowAdmin]  = useState(false);
  const [savingReward, setSavingReward] = useState(false);
  const spinRef = useRef(0);

  const showToast = useCallback((msg, type='success') =>
    setToast({ msg, type, key: Date.now() }), []);

  // ── Fetch ──────────────────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [statsRes, lbRes, checkInRes, spinRes, rewardRes] = await Promise.all([
      safeFetch(API.getDailyStats),
      safeFetch(API.getLeaderboard),
      safeFetch(API.getCheckIns),   // ✅ real check-in history
      safeFetch(API.getSpins),      // ✅ real spin history
      safeFetch(API.getRewards),    // ✅ real rewards
    ]);
    if (statsRes) { setStats(statsRes); setBalance(statsRes.coin_balance || 0); }
    if (lbRes?.leaderboard?.length > 0) setLeaderboard(lbRes.leaderboard);
    // ✅ Replace mock activity with real data
    if (checkInRes) setCheckIns(checkInRes.results || checkInRes || []);
    if (spinRes)    setSpins(spinRes.results || spinRes || []);
    if (rewardRes && Array.isArray(rewardRes) && rewardRes.length > 0) setRewards(rewardRes);
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
  const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
  const h = { 'Authorization': `Bearer ${token}` };
  
  // Leaderboard
  fetch('/api/engagement/leaderboard/', { headers: h })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return;
      const list = data.leaderboard || data.results || data.data || [];
      if (list.length > 0) setLeaderboard(list.map((u, i) => ({
        rank: i + 1,
        user: u.username || u.user || u.name || 'User',
        points: u.total_points || u.points || u.score || 0,
        badge: u.rank_title || u.badge || 'Member',
      })));
    }).catch(() => {});
}, []);

  // ── Check-in ───────────────────────────────────────────────────────────────
  const handleCheckin = async () => {
    const res = await safeFetch(API.dailyCheckin);
    if (res?.success) {
      showToast(`✅ +${res.coins_earned} coins earned! ${res.consecutive_days} day streak 🔥`, 'success');
      setBalance(res.new_balance || balance);
      fetchAll();
    } else {
      showToast(res?.message || 'Already checked in today!', 'error');
    }
  };

  // ── Spin ───────────────────────────────────────────────────────────────────
  const handleSpin = async () => {
    if (spinning) return;
    if (stats?.spin_wheel?.spins_remaining <= 0) {
      showToast('No spins remaining today!', 'error');
      return;
    }
    setSpinning(true);
    setSpinResult(null);
    const extraSpins = 5 + Math.random() * 5;
    const newDeg = spinRef.current + (extraSpins * 360) + Math.random() * 360;
    spinRef.current = newDeg;
    setSpinDeg(newDeg);

    const res = await safeFetch(API.spinWheel);
    setTimeout(() => {
      setSpinning(false);
      if (res?.success) {
        setSpinResult(res.coins_won);
        setBalance(res.new_balance || balance);
        showToast(`🎰 You won ${res.coins_won} coins!`, 'success');
        fetchAll();
      } else {
        setSpinResult(0);
        showToast(res?.message || 'Spin failed', 'error');
      }
    }, 3100);
  };

  // ── Reward Edit ───────────────────────────────────────────────────────────
  const handleRewardSave = async () => {
    if (!editReward) return;
    setSavingReward(true);
    try {
      const res = await safeFetch(() => API.updateReward(editReward.rank, editReward.coins));
      if (res) {
        setRewards(prev => prev.map(r => r.rank === editReward.rank
          ? { ...r, reward_coins: editReward.coins, coins: editReward.coins }
          : r
        ));
        showToast(`✅ Rank ${editReward.rank} reward updated!`, 'success');
        setEditReward(null);
      } else {
        showToast('Update failed', 'error');
      }
    } finally { setSavingReward(false); }
  };

  // ── Helpers ────────────────────────────────────────────────────────────────
  const hasCheckedIn    = stats?.check_in?.has_checked_in || false;
  const consecutiveDays = stats?.check_in?.consecutive_days || 0;
  const spinsRemaining  = stats?.spin_wheel?.spins_remaining ?? 5;
  const spinsUsed       = stats?.spin_wheel?.spins_used ?? 0;
  const todayEarnings   = stats?.todays_earnings || 0;

  const weekDays = ['M','T','W','T','F','S','S'];
  const today    = new Date().getDay();

  const rankCls = (r) => r===1?'r1':r===2?'r2':r===3?'r3':'rn';

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="eng-page">
      <div className="eng-orb eng-orb-1"/>
      <div className="eng-orb eng-orb-2"/>
      <div className="eng-orb eng-orb-3"/>

      {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={() => setToast(null)}/>}

      <div className="eng-container">

        {/* ── Header ── */}
        <header className="eng-header">
          <div>
            <div className="eng-header__title">Engagement Hub</div>
            <div className="eng-header__sub">
              {new Date().toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'})}
            </div>
          </div>
          <div className="eng-header__right">
            <div className="balance-pill">
              <span className="balance-pill__icon">🪙</span>
              <div>
                <div className="balance-pill__label">COIN BALANCE</div>
                <div className="balance-pill__value">{Number(balance).toLocaleString()}</div>
              </div>
            </div>
            <div className="live-badge">
              <span className="live-dot"/>LIVE
            </div>
          </div>
        </header>

        {/* ── Stats ── */}
        <div className="eng-stats-grid">
          {[
            { icon:'🔥', label:'Streak Days',      value: consecutiveDays,              cls:'',      trend:'+1 today', up:true  },
            { icon:'🪙', label:"Today's Earnings",  value: Number(todayEarnings).toFixed(0), cls:'gold',  trend:'coins',    up:true  },
            { icon:'🎰', label:'Spins Remaining',   value: spinsRemaining,               cls:'green', trend:`${spinsUsed} used`, up:false },
            { icon:'🏆', label:'Leaderboard Rank',  value: leaderboard.find(e=>e.is_current_user)?.rank || '—', cls:'pink', trend:'today', up:true },
          ].map((s,i) => (
            <div className="eng-card eng-stat-card" key={i}>
              <div className="eng-stat-card__icon">{s.icon}</div>
              <div className="eng-stat-card__label">{s.label}</div>
              <div className={`eng-stat-card__value ${s.cls}`}>{s.value}</div>
              <span className={`eng-stat-card__trend ${s.up?'trend-up':'trend-down'}`}>
                {s.up?'▲':'▼'} {s.trend}
              </span>
            </div>
          ))}
        </div>

        {/* ── Main 3-col Grid ── */}
        <div className="eng-main-grid">

          {/* Check-in */}
          <div className="eng-card checkin-card">
            <div className="checkin-card__title">⚡ Daily Check-in</div>

            <div className="streak-days">
              {weekDays.map((d, i) => {
                const dayNum = (i + 1) % 7;
                const isActive = i < consecutiveDays;
                const isToday  = dayNum === today;
                return (
                  <div key={i} className={`streak-day${isActive?' active':''}${isToday&&!isActive?' today':''}`}>
                    {isActive ? '✓' : d}
                  </div>
                );
              })}
            </div>

            <div className="checkin-info">
              <div>
                <div className="checkin-streak">
                  {consecutiveDays}<span>day streak</span>
                </div>
              </div>
              <div className="checkin-coins">
                <div className="checkin-coins__val">+{5 + Math.min(consecutiveDays, 25)} coins</div>
                <div className="checkin-coins__lbl">today's reward</div>
              </div>
            </div>

            <button
              className={`checkin-btn${hasCheckedIn?' done':''}`}
              onClick={handleCheckin}
              disabled={hasCheckedIn || loading}
            >
              {hasCheckedIn ? '✓ Checked In Today' : loading ? 'Loading...' : '⚡ Check In Now'}
            </button>
          </div>

          {/* Spin Wheel */}
          <div className="eng-card spin-card">
            <div className="spin-card__title">🎰 Spin Wheel</div>

            <div className="spin-wheel-wrap">
              <div className="spin-pointer">▼</div>
              <SpinWheelSVG spinning={spinning} rotation={spinDeg}/>
            </div>

            <div className="spin-result">
              {spinResult !== null ? `🎉 +${spinResult} COINS!` : ''}
            </div>

            <div className="spin-slots">
              {Array.from({length:5}).map((_,i) => (
                <div key={i} className={`spin-slot ${i < spinsUsed ? 'used' : 'remaining'}`}>
                  {i < spinsUsed ? '✓' : '○'}
                </div>
              ))}
            </div>

            <button
              className="spin-btn"
              onClick={handleSpin}
              disabled={spinning || spinsRemaining <= 0 || loading}
            >
              {spinning ? 'Spinning...' : spinsRemaining > 0 ? `🎰 Spin (${spinsRemaining} left)` : 'No Spins Left'}
            </button>
          </div>

          {/* Leaderboard */}
          <div className="eng-card leaderboard-card">
            <div className="leaderboard-card__header">
              <div className="leaderboard-card__title">🏆 Leaderboard</div>
              <div className="leaderboard-date">
                {new Date().toLocaleDateString('en-US',{month:'short',day:'numeric'})}
              </div>
            </div>
            <div className="leaderboard-list">
              {leaderboard.slice(0,8).map((entry, i) => (
                <div key={i} className={`leaderboard-item${entry.is_current_user?' current-user':''}`}>
                  <div className={`lb-rank ${rankCls(entry.rank)}`}>
                    {entry.rank === 1 ? '🥇' : entry.rank === 2 ? '🥈' : entry.rank === 3 ? '🥉' : `#${entry.rank}`}
                  </div>
                  <div className="lb-avatar">
                    {entry.username?.charAt(0)?.toUpperCase()}
                  </div>
                  <div className="lb-info">
                    <div className="lb-username">
                      {entry.username}
                      {entry.is_current_user && <span className="lb-you">YOU</span>}
                    </div>
                  </div>
                  <div className="lb-coins">🪙 {Number(entry.coins_earned).toLocaleString()}</div>
                </div>
              ))}
              {leaderboard.length === 0 && (
                <div style={{padding:'20px',textAlign:'center',color:'var(--eng-muted)',fontFamily:'var(--font-mono)',fontSize:'.75rem'}}>
                  No entries yet today
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Bottom Grid ── */}
        <div className="eng-bottom-grid">

          {/* Activity Timeline — ✅ REAL DATA */}
          <div className="eng-card activity-card">
            <div className="activity-card__title">📋 Activity Timeline</div>
            <div className="activity-timeline">
              {/* Build combined real activity from checkIns + spins */}
              {[
                ...checkIns.slice(0,3).map(c => ({
                  type:'checkin', color:'gold',
                  label:`Daily Check-in — ${c.consecutive_days} day streak`,
                  meta: c.date || 'Today',
                  badge: `+${c.coins_earned} coins`,
                })),
                ...spins.slice(0,3).map(s => ({
                  type:'spin', color:'green',
                  label:`Spin Wheel — Won ${s.coins_won} coins`,
                  meta: s.spun_at ? new Date(s.spun_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : '',
                  badge: `+${s.coins_won} coins`,
                })),
                // fallback to mock if no real data
                ...(checkIns.length === 0 && spins.length === 0 ? MOCK_ACTIVITY : []),
              ]
              .sort(() => Math.random() - 0.5) // mix checkins + spins
              .slice(0,5)
              .map((item, i, arr) => (
                <div className="activity-tl-item" key={i}>
                  <div className="tl-line">
                    <div className={`tl-dot ${item.color}`}/>
                    {i < arr.length - 1 && <div className="tl-stem"/>}
                  </div>
                  <div className="tl-content">
                    <div className="tl-title">{item.label}</div>
                    <div className="tl-meta">{item.meta}</div>
                  </div>
                  <div className="tl-badge">{item.badge}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Rewards — ✅ REAL DATA + ADMIN EDIT */}
          <div className="eng-card rewards-card">
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
              <div className="rewards-card__title">🎁 Daily Rewards</div>
              <button onClick={()=>setShowAdmin(v=>!v)}
                style={{background:'rgba(0,245,255,0.1)',border:'1px solid rgba(0,245,255,0.2)',
                  borderRadius:6,padding:'4px 10px',color:'var(--eng-cyan)',fontSize:'.68rem',
                  cursor:'pointer',fontFamily:'var(--font-mono)'}}>
                {showAdmin ? '✕ Close' : '⚙ Admin'}
              </button>
            </div>
            {rewards.map((r, i) => (
              <div className="reward-item" key={i}>
                <div className={`reward-item__rank ${rankCls(r.rank)}`}>
                  {r.rank === 1 ? '🥇' : r.rank === 2 ? '🥈' : r.rank === 3 ? '🥉' : `#${r.rank}`}
                </div>
                <div className="reward-item__label">{r.label || `Rank ${r.rank}`}</div>
                {editReward?.rank === r.rank ? (
                  <div style={{display:'flex',gap:4,alignItems:'center'}}>
                    <input type="number" value={editReward.coins}
                      onChange={e=>setEditReward(p=>({...p,coins:Number(e.target.value)}))}
                      style={{width:60,background:'rgba(0,0,0,0.4)',border:'1px solid rgba(0,245,255,0.3)',
                        borderRadius:4,padding:'2px 6px',color:'var(--eng-cyan)',fontSize:'.75rem',
                        fontFamily:'var(--font-mono)'}}/>
                    <button onClick={handleRewardSave} disabled={savingReward}
                      style={{background:'rgba(0,255,136,0.15)',border:'1px solid rgba(0,255,136,0.3)',
                        borderRadius:4,padding:'2px 8px',color:'#00ff88',fontSize:'.7rem',cursor:'pointer'}}>
                      {savingReward?'…':'✓'}
                    </button>
                    <button onClick={()=>setEditReward(null)}
                      style={{background:'none',border:'none',color:'var(--eng-muted)',cursor:'pointer',fontSize:'.75rem'}}>✕</button>
                  </div>
                ) : (
                  <div style={{display:'flex',alignItems:'center',gap:8}}>
                    <div className="reward-item__coins">🪙 {r.reward_coins || r.coins}</div>
                    {showAdmin && (
                      <button onClick={()=>setEditReward({rank:r.rank,coins:r.reward_coins||r.coins})}
                        style={{background:'rgba(0,245,255,0.08)',border:'1px solid rgba(0,245,255,0.15)',
                          borderRadius:4,padding:'2px 6px',color:'var(--eng-cyan)',fontSize:'.65rem',cursor:'pointer'}}>
                        Edit
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div style={{marginTop:'16px',padding:'12px',borderRadius:'var(--radius-sm)',
              background:'rgba(0,245,255,0.04)',border:'1px solid var(--eng-border)',
              fontFamily:'var(--font-mono)',fontSize:'.68rem',color:'var(--eng-muted)',
              textAlign:'center',lineHeight:'1.6'}}>
              Rewards distributed daily at<br/>
              <span style={{color:'var(--eng-cyan)'}}>00:00 UTC</span>
            </div>
          </div>
        </div>

        {/* ── Admin CRUD Panel ── ✅ NEW */}
        {showAdmin && (
          <div style={{marginTop:24,background:'rgba(0,0,0,0.4)',border:'1px solid rgba(0,245,255,0.15)',
            borderRadius:12,padding:20,backdropFilter:'blur(10px)'}}>
            <div style={{display:'flex',gap:8,marginBottom:16}}>
              {[['checkins','📋 Check-ins'],['spins','🎰 Spin History'],['rewards','🎁 Reward Config']].map(([k,l])=>(
                <button key={k} onClick={()=>setAdminTab(k)} style={{
                  padding:'6px 14px',borderRadius:8,cursor:'pointer',
                  fontFamily:'var(--font-mono)',fontSize:'.72rem',fontWeight:700,
                  background: adminTab===k?'rgba(0,245,255,0.15)':'rgba(255,255,255,0.04)',
                  border:`1px solid ${adminTab===k?'rgba(0,245,255,0.4)':'rgba(255,255,255,0.08)'}`,
                  color: adminTab===k?'var(--eng-cyan)':'var(--eng-muted)',
                }}>{l}</button>
              ))}
            </div>

            {/* Check-ins Table */}
            {adminTab==='checkins' && (
              <div style={{overflowX:'auto'}}>
                <table style={{width:'100%',borderCollapse:'collapse',fontFamily:'var(--font-mono)',fontSize:'.72rem'}}>
                  <thead><tr style={{borderBottom:'1px solid rgba(0,245,255,0.1)'}}>
                    {['User','Date','Coins','Streak','Bonus'].map(h=>(
                      <th key={h} style={{padding:'8px 12px',color:'var(--eng-muted)',textAlign:'left',fontWeight:700,letterSpacing:'.06em'}}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {checkIns.length===0
                      ? <tr><td colSpan={5} style={{padding:20,textAlign:'center',color:'var(--eng-muted)'}}>No check-in data</td></tr>
                      : checkIns.slice(0,10).map((c,i)=>(
                          <tr key={i} style={{borderBottom:'1px solid rgba(255,255,255,0.03)'}}>
                            <td style={{padding:'8px 12px',color:'var(--eng-text)'}}>{c.user || '—'}</td>
                            <td style={{padding:'8px 12px',color:'var(--eng-muted)'}}>{c.date}</td>
                            <td style={{padding:'8px 12px',color:'#ffd700'}}>+{c.coins_earned}</td>
                            <td style={{padding:'8px 12px',color:'var(--eng-cyan)'}}>{c.consecutive_days}d</td>
                            <td style={{padding:'8px 12px',color:c.bonus_claimed?'#00ff88':'var(--eng-muted)'}}>{c.bonus_claimed?'✓':'—'}</td>
                          </tr>
                        ))
                    }
                  </tbody>
                </table>
              </div>
            )}

            {/* Spins Table */}
            {adminTab==='spins' && (
              <div style={{overflowX:'auto'}}>
                <table style={{width:'100%',borderCollapse:'collapse',fontFamily:'var(--font-mono)',fontSize:'.72rem'}}>
                  <thead><tr style={{borderBottom:'1px solid rgba(0,245,255,0.1)'}}>
                    {['User','Coins Won','Spun At','Total Spins','Total Won'].map(h=>(
                      <th key={h} style={{padding:'8px 12px',color:'var(--eng-muted)',textAlign:'left',fontWeight:700,letterSpacing:'.06em'}}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {spins.length===0
                      ? <tr><td colSpan={5} style={{padding:20,textAlign:'center',color:'var(--eng-muted)'}}>No spin data</td></tr>
                      : spins.slice(0,10).map((s,i)=>(
                          <tr key={i} style={{borderBottom:'1px solid rgba(255,255,255,0.03)'}}>
                            <td style={{padding:'8px 12px',color:'var(--eng-text)'}}>{s.user || '—'}</td>
                            <td style={{padding:'8px 12px',color:'#00ff88'}}>+{s.coins_won}</td>
                            <td style={{padding:'8px 12px',color:'var(--eng-muted)'}}>{s.spun_at?new Date(s.spun_at).toLocaleString():''}</td>
                            <td style={{padding:'8px 12px',color:'var(--eng-cyan)'}}>{s.total_spins}</td>
                            <td style={{padding:'8px 12px',color:'#ffd700'}}>{s.total_won}</td>
                          </tr>
                        ))
                    }
                  </tbody>
                </table>
              </div>
            )}

            {/* Reward Config */}
            {adminTab==='rewards' && (
              <div>
                <p style={{color:'var(--eng-muted)',fontSize:'.72rem',fontFamily:'var(--font-mono)',marginBottom:12}}>
                  Click Edit on any reward tier to update coins. Changes are saved immediately.
                </p>
                {rewards.map((r,i)=>(
                  <div key={i} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 0',
                    borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                    <div style={{width:40,color:'var(--eng-cyan)',fontFamily:'var(--font-mono)',fontWeight:700}}>
                      {r.rank===1?'🥇':r.rank===2?'🥈':r.rank===3?'🥉':`#${r.rank}`}
                    </div>
                    <div style={{flex:1,color:'var(--eng-text)',fontFamily:'var(--font-mono)',fontSize:'.75rem'}}>
                      {r.label||`Rank ${r.rank}`}
                    </div>
                    {editReward?.rank===r.rank?(
                      <div style={{display:'flex',gap:6,alignItems:'center'}}>
                        <input type="number" value={editReward.coins}
                          onChange={e=>setEditReward(p=>({...p,coins:Number(e.target.value)}))}
                          style={{width:80,background:'rgba(0,0,0,0.5)',border:'1px solid rgba(0,245,255,0.3)',
                            borderRadius:6,padding:'4px 10px',color:'var(--eng-cyan)',fontSize:'.8rem',
                            fontFamily:'var(--font-mono)'}}/>
                        <button onClick={handleRewardSave} disabled={savingReward}
                          style={{background:'rgba(0,255,136,0.15)',border:'1px solid rgba(0,255,136,0.3)',
                            borderRadius:6,padding:'5px 14px',color:'#00ff88',fontWeight:700,cursor:'pointer',
                            fontFamily:'var(--font-mono)',fontSize:'.75rem'}}>
                          {savingReward?'Saving…':'Save'}
                        </button>
                        <button onClick={()=>setEditReward(null)}
                          style={{background:'none',border:'1px solid rgba(255,255,255,0.1)',
                            borderRadius:6,padding:'5px 10px',color:'var(--eng-muted)',cursor:'pointer'}}>✕</button>
                      </div>
                    ):(
                      <div style={{display:'flex',alignItems:'center',gap:10}}>
                        <span style={{color:'#ffd700',fontFamily:'var(--font-mono)',fontWeight:700}}>🪙 {r.reward_coins||r.coins}</span>
                        <button onClick={()=>setEditReward({rank:r.rank,coins:r.reward_coins||r.coins})}
                          style={{background:'rgba(0,245,255,0.08)',border:'1px solid rgba(0,245,255,0.2)',
                            borderRadius:6,padding:'4px 12px',color:'var(--eng-cyan)',fontSize:'.72rem',
                            cursor:'pointer',fontFamily:'var(--font-mono)'}}>Edit</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}