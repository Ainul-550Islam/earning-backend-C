// src/pages/Dashboard.jsx — Ultra Neon v5 — Real API + 3D Cards
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import RevenueChart from '../components/dashboard/RevenueChart';


/* ── auth ── */
const getToken = () =>
  localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token') ||
  localStorage.getItem('access_token') || localStorage.getItem('access');

const apiFetch = async (url) => {
  try {
    const r = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
};

/* ── SVG glow defs ── */
const GlowDefs = () => (
  <svg width="0" height="0" style={{ position:'absolute', overflow:'hidden' }}>
    <defs>
      <filter id="gf-p"><feGaussianBlur stdDeviation="3"   result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="gf-c"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="gf-g"><feGaussianBlur stdDeviation="2"   result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>
  </svg>
);

/* ── Custom Tooltip ── */
const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background:'rgba(5,2,20,.97)',border:'1px solid rgba(120,60,255,.35)',
      borderRadius:10,padding:'10px 14px',backdropFilter:'blur(22px)',
      boxShadow:'0 8px 32px rgba(0,0,0,.65)',
    }}>
      <div style={{ fontFamily:'Share Tech Mono',fontSize:'.64rem',color:'rgba(180,160,255,.5)',marginBottom:6 }}>{label}</div>
      {payload.map((p,i)=>(
        <div key={i} style={{ fontFamily:'Orbitron',fontSize:'.68rem',color:p.color,marginBottom:3,textShadow:`0 0 8px ${p.color}` }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
};

/* ── All system pages — 3D clickable cards ── */
const ALL_PAGES = [
  // Row 1 — Core
  { path:'/users',            icon:'👥', name:'Users',            sub:'User management',     color:'#00f3ff' },
  { path:'/wallet',           icon:'💰', name:'Wallet',           sub:'Balance & txns',      color:'#ffd700' },
  { path:'/tasks',            icon:'📋', name:'Tasks',            sub:'Task management',     color:'#ff8c00' },
  { path:'/offerwall',        icon:'⚡', name:'Offerwall',        sub:'Offers & rewards',    color:'#ff2d78' },
  // Row 2 — Finance
  { path:'/admin-finance',    icon:'💵', name:'Finance',          sub:'Revenue & payouts',   color:'#00ff88' },
  { path:'/payout-queue',     icon:'🏦', name:'Payout Queue',     sub:'Pending payouts',     color:'#ffd700' },
  { path:'/payment-gateways', icon:'💳', name:'Payments',         sub:'Gateway config',      color:'#c44fff' },
  { path:'/subscriptions',    icon:'🔄', name:'Subscriptions',    sub:'Plans & billing',     color:'#00f3ff' },
  // Row 3 — Security
  { path:'/security',         icon:'🛡️', name:'Security',         sub:'Sessions & IP',       color:'#00ff88' },
  { path:'/fraud-detection',  icon:'🔍', name:'Fraud Detection',  sub:'AI fraud engine',     color:'#ff003c' },
  { path:'/kyc',              icon:'🪪', name:'KYC',              sub:'Identity verify',     color:'#ff8c00' },
  { path:'/auto-mod',         icon:'🤖', name:'Auto Mod',         sub:'Auto moderation',     color:'#c44fff' },
  // Row 4 — Analytics
  { path:'/analytics',        icon:'📊', name:'Analytics',        sub:'Platform metrics',    color:'#ff2d78' },
  { path:'/behavior-analytics',icon:'🧠',name:'Behavior',         sub:'User behavior AI',    color:'#c44fff' },
  { path:'/engagement',       icon:'💬', name:'Engagement',       sub:'User engagement',     color:'#ffd700' },
  { path:'/audit-logs',       icon:'📝', name:'Audit Logs',       sub:'System logs',         color:'#00f3ff' },
  // Row 5 — Content
  { path:'/cms',              icon:'📄', name:'CMS',              sub:'Content management',  color:'#00ff88' },
  { path:'/promotions',       icon:'🎯', name:'Promotions',       sub:'Campaigns & bids',    color:'#ff8c00' },
  { path:'/ad-networks',      icon:'📡', name:'Ad Networks',      sub:'Ad management',       color:'#ff2d78' },
  { path:'/loyalty',          icon:'🎁', name:'Loyalty',          sub:'CRM & rewards',       color:'#c44fff' },
  // Row 6 — Operations
  { path:'/referral',         icon:'🔗', name:'Referral',         sub:'Referral program',    color:'#ffd700' },
  { path:'/support',          icon:'🎧', name:'Support',          sub:'Tickets & help',      color:'#00f3ff' },
  { path:'/notifications',    icon:'🔔', name:'Notifications',    sub:'Push & alerts',       color:'#ff8c00' },
  { path:'/messaging',        icon:'✉️', name:'Messaging',        sub:'User messages',       color:'#00ff88' },
  // Row 7 — System
  { path:'/postback',         icon:'📶', name:'Postback',         sub:'Network postbacks',   color:'#ff003c' },
  { path:'/inventory',        icon:'📦', name:'Inventory',        sub:'Asset inventory',     color:'#c44fff' },
  { path:'/gamification',     icon:'🏆', name:'Gamification',     sub:'Points & badges',     color:'#ffd700' },
  { path:'/cache',            icon:'⚡', name:'Cache',            sub:'Redis cache',         color:'#00f3ff' },
  // Row 8 — Admin
  { path:'/backup',           icon:'💾', name:'Backup',           sub:'Data backup',         color:'#00ff88' },
  { path:'/localization',     icon:'🌐', name:'Localization',     sub:'i18n & languages',    color:'#ff8c00' },
  { path:'/version-control',  icon:'🔧', name:'Version Control',  sub:'Deployments',         color:'#c44fff' },
  { path:'/settings',         icon:'⚙️', name:'Settings',         sub:'System config',       color:'#ff2d78' },
];

const LINKS = [
  {path:'/users',   icon:'👥',label:'Users',       sub:'Total registered', color:'#00f3ff',valKey:'users'  },
  {path:'/wallet',  icon:'💰',label:'Wallet',      sub:'Total balance',    color:'#ffd700',valKey:'wallet' },
  {path:'/tasks',   icon:'📋',label:'Tasks',       sub:'Active tasks',     color:'#ff8c00',valKey:'txns'   },
  {path:'/security',icon:'🛡️',label:'Security',    sub:'System status',   color:'#00ff88',valKey:'healthy'},
];

/* ═══════════════════════════════════════════════════════ */
export default function Dashboard() {
  const nav = useNavigate();

  const [stats,   setStats]  = useState({users:'—',revenue:'—',tasks:'—',engagement:'—'});
  const [chart,   setChart]  = useState([]);
  const [acts,    setActs]   = useState([]);
  const [offers,  setOffers] = useState([]);
  const [qv,      setQv]     = useState({users:'—',wallet:'$0.00',txns:'—',healthy:'✓'});
  const [refs,    setRefs]   = useState({count:0,label:'0 refs'});
  const [loading, setLoad]   = useState(true);

  const fetchAll = useCallback(async () => {
    setLoad(true);
    const [dashStats, tasks, ref, analytics] = await Promise.all([
      apiFetch('/api/users/dashboard-stats/'),
      apiFetch('/api/tasks/tasks/?page_size=1'),
      apiFetch('/api/referral/stats/'),
      apiFetch('/api/analytics/summary/'),
    ]);

    // Users — from dashboard-stats
    const uc  = dashStats?.total_users ?? dashStats?.active_users ?? 0;
    const rev = dashStats?.total_balance ?? 0;
    const tc  = tasks?.count ?? tasks?.pagination?.total ?? tasks?.total ?? (Array.isArray(tasks)?tasks.length:0);
    const rc  = ref?.data?.total_referrals ?? ref?.total_referrals ?? ref?.count ?? 0;
    const eng = dashStats?.active_users ?? analytics?.active_users ?? rc ?? 0;

    setRefs({count:rc, label:`${rc} refs`});
    setStats({
      users:      Number(uc) > 0 ? Number(uc).toLocaleString() : '—',
      revenue:    `$${Number(rev).toLocaleString(undefined,{maximumFractionDigits:2})}`,
      tasks:      Number(tc) > 0 ? tc.toString() : '—',
      engagement: Number(eng) > 0 ? Number(eng).toLocaleString() : '—',
    });
    setQv({
      users:   Number(uc) > 0 ? Number(uc).toLocaleString() : '0',
      wallet:  `$${Number(rev).toFixed(2)}`,
      txns:    Number(tc) > 0 ? tc.toString() : '0',
      healthy: dashStats?.fraud_events_today === 0 ? '✓ OK' : `⚠ ${dashStats?.fraud_events_today}`,
    });

    // Chart
    const revChart = await apiFetch('/api/analytics/revenue-analytics/?page_size=12&ordering=period_start');
    if (revChart) {
      const list = Array.isArray(revChart) ? revChart : (revChart.results || revChart.data || []);
      if (list.length > 0) setChart(list.map(r => ({
        date:    r.period_display || r.period_start_date || '',
        Revenue: parseFloat(r.revenue_total || 0),
        Tasks:   parseFloat(r.cost_total || 0),
        Users:   parseFloat(r.active_users || 0),
      })));
    }

    // Audit logs
    const auditRes = await apiFetch('/api/audit_logs/logs/?page_size=5&ordering=-timestamp');
    if (auditRes) {
      const list = Array.isArray(auditRes) ? auditRes : (auditRes.results || auditRes.data || []);
      if (list.length > 0) setActs(list.map((a,i) => ({
        id: a.id || i,
        user: (a.user || 'System').toString().split(' - ')[0].split('@')[0] || 'System',
        action: a.message || a.action_display || a.action || 'Action',
        module: (a.resource_type || a.request_path || 'system').toLowerCase().replace('/api/','').split('/')[0] || 'system',
        status: a.success ? 'done' : 'pending',
        time: a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : '',
      })));
    }

    // Top offers
    const offersRes = await apiFetch('/api/offers/offers/?page_size=100&ordering=-reward_amount');
    if (offersRes) {
      const list = Array.isArray(offersRes) ? offersRes : (offersRes.results || offersRes.data || []);
      if (list.length > 0) setOffers(list.map(o => ({
        id: o.id,
        name: o.title || o.name || 'Offer',
        reward: `$${parseFloat(o.reward_amount || o.payout || 0).toFixed(2)}`,
        icon: o.offer_type==='survey'?'📊':o.offer_type==='app'?'📱':o.offer_type==='video'?'🎬':o.offer_type==='game'?'🎮':'⚡',
      })));
    }

    setLoad(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const STATS = [
    {label:'TOTAL USERS', value:stats.users,      icon:'👤',color:'#ff2d78'},
    {label:'REVENUE',     value:stats.revenue,    icon:'💵',color:'#ffd700'},
    {label:'ACTIVE TASKS',value:stats.tasks,      icon:'📋',color:'#00ff88'},
    {label:'ENGAGEMENT',  value:stats.engagement, icon:'⚡',color:'#00f3ff'},
  ];

  const LEGEND = [
    {key:'Revenue',color:'#ff2d78'},
    {key:'Tasks',  color:'#00f3ff'},
    {key:'Users',  color:'#ffd700'},
  ];

  return (
    <div className="db-page">
      <GlowDefs/>
      <div className="db-content">

        {/* ══ 4 STAT CARDS ══ */}
        <div className="db-stats-row">
          {STATS.map((s,i)=>(
            <div key={i} className="db-stat" style={{'--sc':s.color}}>
              <div className="db-stat__top">
                <div className="db-stat__label">{s.label}</div>
                <div className="db-stat__icon">{s.icon}</div>
              </div>
              <div className="db-stat__value">
                {loading
                  ? <span className="db-shimmer" style={{width:90,height:44,display:'block'}}/>
                  : s.value}
              </div>
              <div className="db-stat__sub">Live data</div>
              <div className="db-stat__line"/>
            </div>
          ))}
        </div>

        {/* ══ MIDDLE ROW ══ */}
        <div className="db-middle-row">
          <div style={{width:"100%",marginBottom:20}}><RevenueChart /></div>

          {/* Right Panel */}
          <div className="db-right-col">
            {/* Referral */}
            <div className="db-referral">
              <div>
                <div className="db-referral-title"><span>⬡⬡</span> Referral</div>
                <div className="db-referral-sub">Total Earners · {refs.label}</div>
              </div>
              <div className="db-referral-val">{refs.count}</div>
            </div>

            {LINKS.map((q,i)=>(
              <div key={i} className="db-quick" style={{'--qc':q.color}} onClick={()=>nav(q.path)}>
                <div className="db-quick__icon">{q.icon}</div>
                <div className="db-quick__info">
                  <div className="db-quick__label">{q.label}</div>
                  <div className="db-quick__sub">{q.sub}</div>
                </div>
                <div className="db-quick__val" style={{color:q.color,textShadow:`0 0 8px ${q.color},0 0 18px ${q.color}`}}>
                  {loading ? '...' : qv[q.valKey]}
                </div>
                <div className="db-quick__arrow">›</div>
              </div>
            ))}

            {/* Top Offers */}
            <div className="db-card" style={{flex:'1 0 auto'}}>
              <div className="db-offers-title">
                <span><span className="t1">⚡ Top </span><span className="t2">Offers</span></span>
                <span className="db-offers-badge" onClick={()=>nav('/offerwall')} style={{cursor:'pointer'}}>
                  {offers.length > 0 ? `${offers.length} ›` : '100 ›'}
                </span>
              </div>
              <div style={{maxHeight:"300px",overflowY:"auto",overflowX:"hidden"}}>
              {offers.map((o,i)=>(
                <div key={o.id} className="db-offer-item">
                  <div className="db-offer-rank">#{i+1}</div>
                  <div className="db-offer-icon">{o.icon}</div>
                  <div className="db-offer-name">{o.name}</div>
                  <div className="db-offer-val">{o.reward}</div>
                </div>
              ))}
            </div>
              </div>
          </div>
        </div>

        {/* ══ ALL SYSTEM PAGES — 3D CARDS ══ */}
        <div style={{marginTop:24}}>
          <div style={{
            fontFamily:'Orbitron,monospace',fontSize:11,letterSpacing:3,
            color:'rgba(0,243,255,.7)',marginBottom:16,textTransform:'uppercase',
            display:'flex',alignItems:'center',gap:10,
          }}>
            <span style={{color:'#ff2d78'}}>◈</span> ALL SYSTEMS
            <span style={{fontSize:9,color:'rgba(180,160,255,.4)',letterSpacing:2}}>— CLICK TO NAVIGATE</span>
          </div>
          <div style={{
            display:'grid',
            gridTemplateColumns:'repeat(auto-fill, minmax(180px, 1fr))',
            gap:12,
          }}>
            {ALL_PAGES.map((p,i)=>(
              <div key={i} onClick={()=>nav(p.path)}
                style={{
                  background:`linear-gradient(145deg, rgba(5,10,25,.95), rgba(${
                    p.color==='#00f3ff'?'0,30,40':
                    p.color==='#ffd700'?'40,36,0':
                    p.color==='#ff8c00'?'40,20,0':
                    p.color==='#ff2d78'?'40,5,20':
                    p.color==='#00ff88'?'0,40,20':
                    p.color==='#c44fff'?'30,0,50':
                    p.color==='#ff003c'?'40,0,15':
                    '10,10,25'
                  },0.95))`,
                  border:`1px solid ${p.color}30`,
                  borderRadius:12,
                  padding:'16px 16px 14px',
                  cursor:'pointer',
                  transition:'all .35s cubic-bezier(.175,.885,.32,1.275)',
                  position:'relative',
                  overflow:'hidden',
                  boxShadow:`0 0 0 1px ${p.color}10, 0 4px 20px rgba(0,0,0,.5)`,
                }}
                onMouseEnter={e=>{
                  e.currentTarget.style.transform='perspective(500px) rotateX(-5deg) rotateY(5deg) translateY(-6px) scale(1.03)';
                  e.currentTarget.style.boxShadow=`0 0 0 1px ${p.color}40, 0 0 25px ${p.color}25, 0 12px 40px rgba(0,0,0,.7)`;
                  e.currentTarget.style.border=`1px solid ${p.color}60`;
                }}
                onMouseLeave={e=>{
                  e.currentTarget.style.transform='none';
                  e.currentTarget.style.boxShadow=`0 0 0 1px ${p.color}10, 0 4px 20px rgba(0,0,0,.5)`;
                  e.currentTarget.style.border=`1px solid ${p.color}30`;
                }}>
                {/* Top glow line */}
                <div style={{position:'absolute',top:0,left:'10%',right:'10%',height:1,background:`linear-gradient(90deg,transparent,${p.color}70,transparent)`}}/>
                {/* Corner accent */}
                <div style={{position:'absolute',top:0,right:0,width:35,height:35,background:`linear-gradient(225deg,${p.color}20,transparent)`,borderRadius:'0 12px 0 35px'}}/>
                {/* Icon */}
                <div style={{
                  fontSize:26,marginBottom:10,
                  filter:`drop-shadow(0 0 8px ${p.color}80)`,
                  display:'inline-block',
                }}>{p.icon}</div>
                {/* Name */}
                <div style={{
                  fontFamily:'Orbitron,monospace',fontSize:11,fontWeight:700,
                  color:p.color,letterSpacing:1,marginBottom:4,
                  textShadow:`0 0 10px ${p.color}60`,
                }}>{p.name}</div>
                {/* Sub */}
                <div style={{
                  fontSize:10,color:'rgba(180,180,200,.5)',
                  fontFamily:'Share Tech Mono,monospace',letterSpacing:.5,
                }}>{p.sub}</div>
                {/* Arrow */}
                <div style={{
                  position:'absolute',bottom:12,right:14,
                  fontSize:16,color:`${p.color}60`,
                  fontFamily:'monospace',
                }}>›</div>
              </div>
            ))}
          </div>
        </div>

        {/* ══ RECENT ACTIVITIES ══ */}
        {acts.length > 0 && (
          <div className="db-card db-bottom-row" style={{marginTop:24}}>
            <div className="db-act-header">
              <div className="db-act-title">
                <span className="w1">RECENT </span>
                <span className="w2">ACTIVITIES</span>
              </div>
              <div className="db-act-badge">
                <div className="db-act-dot"/>
                <span style={{color:'rgba(0,243,255,.6)'}}>{acts.length*20} total ›</span>
              </div>
            </div>
            <table className="db-act-table">
              <thead>
                <tr>{['USER','ACTION','MODULE','STATUS','TIME'].map(h=><th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {acts.map((a,i)=>(
                  <tr key={a.id||i}>
                    <td><span className="act-user">{a.user}</span></td>
                    <td><span className="act-action">{a.action}</span></td>
                    <td><span className={`act-mod ${a.module}`}>{a.module.charAt(0).toUpperCase()+a.module.slice(1)}</span></td>
                    <td><span className={`act-status ${a.status}`}>{a.status.toUpperCase()}</span></td>
                    <td><span className="act-time">{a.time}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      </div>
    </div>
  );
}



