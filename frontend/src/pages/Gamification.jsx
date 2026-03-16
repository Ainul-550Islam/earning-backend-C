// src/pages/Gamification.jsx
import React, { useState, useEffect, useCallback } from 'react';
import '../styles/Gamification.css';
import {
  Search, Calendar, Bell, Settings, ChevronDown, ChevronRight,
  BarChart2, Trophy, Gift, Star, Target, Zap, Users, Clock,
  LayoutDashboard, RefreshCw, Plus, X, Minus, ArrowUp, ArrowDown,
  ShieldCheck, Activity
} from 'lucide-react';

/* ─── API helpers ─────────────────────────────────── */
const BASE = '/api/gamification';
const tok  = () => localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token') || '';
const req  = async (url, opts = {}) => {
  let r;
  try { r = await fetch(url, {
    headers: { 'Content-Type':'application/json', Authorization:`Bearer ${tok()}`, ...opts.headers },
    ...opts,
  }); } catch { throw new Error('Network error — check connection'); }
  if (r.status === 204) return null;
  if (!r.ok) {
    const text = await r.text();
    // Try to keep raw JSON so callers can parse detailed errors
    throw new Error(text || `HTTP ${r.status}`);
  }
  return r.json();
};
const api = {
  // ── Contest Cycles ──────────────────────────────
  cycles:        (p='') => req(`${BASE}/contest-cycles/?ordering=-created_at&page_size=50${p?`&${p}`:''}`),
  cycle:          id    => req(`${BASE}/contest-cycles/${id}/`),
  createCycle:    d     => req(`${BASE}/contest-cycles/`,                          { method:'POST',   body:JSON.stringify(d) }),
  updateCycle:   (id,d) => req(`${BASE}/contest-cycles/${id}/`,                    { method:'PATCH',  body:JSON.stringify(d) }),
  deleteCycle:    id    => req(`${BASE}/contest-cycles/${id}/`,                    { method:'DELETE' }),
  activate:       id    => req(`${BASE}/contest-cycles/${id}/activate/`,           { method:'POST' }),
  complete:       id    => req(`${BASE}/contest-cycles/${id}/complete/`,           { method:'POST' }),
  distribute:     id    => req(`${BASE}/contest-cycles/${id}/distribute-rewards/`, { method:'POST' }),
  leaderboard:  (id,s='GLOBAL') => req(`${BASE}/contest-cycles/${id}/leaderboard/?scope=${s}`),

  // ── Rewards ─────────────────────────────────────
  rewards:       (p='') => req(`${BASE}/rewards/?page_size=50${p?`&${p}`:''}`),
  createReward:   d     => req(`${BASE}/rewards/`,                                 { method:'POST',   body:JSON.stringify(d) }),
  updateReward:  (id,d) => req(`${BASE}/rewards/${id}/`,                           { method:'PATCH',  body:JSON.stringify(d) }),
  deleteReward:   id    => req(`${BASE}/rewards/${id}/`,                           { method:'DELETE' }),

  // ── Achievements ─────────────────────────────────
  achievements:  (p='') => req(`${BASE}/achievements/?page_size=20&ordering=-awarded_at${p?`&${p}`:''}`),
  myPoints:     (cid='')=> req(`${BASE}/achievements/my-points/${cid?`?cycle_id=${cid}`:''}`),

  // ── Leaderboard Snapshot ─────────────────────────
  genSnapshot:    d     => req(`${BASE}/leaderboard-snapshots/generate/`,          { method:'POST',   body:JSON.stringify(d) }),
  snapshots:     (cid)  => req(`${BASE}/leaderboard-snapshots/?contest_cycle=${cid}&ordering=-generated_at`),

  // ── Achievement Award ─────────────────────────────
  awardAch:       d     => req(`${BASE}/achievements/`,                            { method:'POST',   body:JSON.stringify(d) }),
  batchAward:     d     => req(`${BASE}/achievements/batch-award/`,                { method:'POST',   body:JSON.stringify(d) }),

  // ── Cycle Reset ───────────────────────────────────
  resetCycle:     id    => req(`${BASE}/contest-cycles/${id}/reset/`,              { method:'POST' }),

  // ── Current User ──────────────────────────────────
  me:            ()     => req(`/api/auth/profile/my_profile/`),
  profile:       ()     => req(`/api/auth/users/me/`),

  // ── Notifications ─────────────────────────────────
  notifications: ()     => req(`/api/notifications/?page_size=10&ordering=-created_at`),
};

/* ─── sparkline SVG ───────────────────────────────── */
const Sparkline = ({ color = '#a855f7', h = 30, points = [] }) => {
  const pts = points.length ? points : Array.from({length:12},(_,i)=>20+Math.sin(i*0.8)*12+Math.random()*8);
  const max = Math.max(...pts), min = Math.min(...pts);
  const W = 120, H = h;
  const xs = pts.map((_,i)=> i*(W/(pts.length-1)));
  const ys = pts.map(p=> H - ((p-min)/(max-min||1))*(H-4) - 2);
  const d  = xs.map((x,i)=>`${i===0?'M':'L'}${x},${ys[i]}`).join(' ');
  const fill = xs.map((x,i)=>`${i===0?'M':'L'}${x},${ys[i]}`).join(' ')
    + ` L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{width:'100%',height:H}}>
      <defs>
        <linearGradient id={`sg${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={fill} fill={`url(#sg${color.replace('#','')})`}/>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5"
        style={{filter:`drop-shadow(0 0 3px ${color})`}}/>
    </svg>
  );
};

/* ─── rank icon ───────────────────────────────────── */
const RankIcon = ({ rank }) => {
  if (rank===1) return <span style={{fontSize:16,filter:'drop-shadow(0 0 6px #ffd700)'}}>👑</span>;
  if (rank===2) return <span style={{fontSize:14,filter:'drop-shadow(0 0 4px #c0c0c0)'}}>🥈</span>;
  if (rank===3) return <span style={{fontSize:14,filter:'drop-shadow(0 0 4px #cd7f32)'}}>🥉</span>;
  return <span className="gm-lb-rank-num">#{rank}</span>;
};

/* ─── delta ───────────────────────────────────────── */
const Delta = ({ v }) => {
  if (!v) return <Minus style={{width:9,height:9,color:'#3a1a5a'}}/>;
  if (v>0)  return <span style={{color:'#00ff88',fontSize:10,display:'flex',alignItems:'center',gap:1}}><ArrowUp style={{width:9,height:9}}/>{v}</span>;
  return <span style={{color:'#ff2d78',fontSize:10,display:'flex',alignItems:'center',gap:1}}><ArrowDown style={{width:9,height:9}}/>{Math.abs(v)}</span>;
};

/* ─── Avatar colors ───────────────────────────────── */
const AV_COLORS = ['#7c3aed','#db2777','#0891b2','#059669','#d97706','#dc2626','#7c3aed','#9333ea'];
const avColor = (name='') => AV_COLORS[(name.charCodeAt(0)||0) % AV_COLORS.length];

/* ─── Mock data (used if API unavailable) ─────────── */
const MOCK = {
  cycles: [{id:'c1',name:'Ultimate Contest',status:'ACTIVE',start_date:'2024-04-01',end_date:'2024-04-29',points_multiplier:'2.00',is_featured:true}],
  leaderboard:[
    {rank:1,user_id:'u1',display_name:'Saints',points:78000,delta_rank:null},
    {rank:2,user_id:'u2',display_name:'TenzyX',points:56720,delta_rank:1},
    {rank:3,user_id:'u3',display_name:'FunLancer',points:53588,delta_rank:-1},
    {rank:4,user_id:'u4',display_name:'WebKing',points:50100,delta_rank:2},
    {rank:5,user_id:'u5',display_name:'Anromsta',points:45000,delta_rank:0},
    {rank:6,user_id:'u6',display_name:'Sonykesis',points:46700,delta_rank:-1},
    {rank:7,user_id:'u7',display_name:'KatsSoft',points:46930,delta_rank:1},
    {rank:19,user_id:'me',display_name:'Ainul Islam',points:48930,delta_rank:3,isMe:true},
  ],
  rewards:[
    {id:'r1',title:'Gold Trophy',reward_type:'POINTS',reward_value:'2000',rank_from:1,rank_to:1,is_exhausted:false,usd:'560'},
    {id:'r2',title:'Silver Trophy',reward_type:'POINTS',reward_value:'1500',rank_from:2,rank_to:2,is_exhausted:false,usd:'200'},
    {id:'r3',title:'Bronze Trophy',reward_type:'POINTS',reward_value:'1000',rank_from:3,rank_to:3,is_exhausted:false,usd:'100'},
  ],
  achievements:[
    {id:'a1',title:'Point Pro',achievement_type:'MILESTONE',description:'Collect 50,000 Points',points_awarded:1000,awarded_at:'2024-04-28T10:00:00Z',user:'TenzyX',progress:82},
    {id:'a2',title:'Daily Winner',achievement_type:'STREAK',description:'Win Daily challenge as',points_awarded:500,awarded_at:'2024-04-28T05:00:00Z',user:'BoostMaster',progress:60},
    {id:'a3',title:'Points Hunter',achievement_type:'BADGE',description:'Collect $1,500 Pts create',points_awarded:300,awarded_at:'2024-04-27T15:00:00Z',user:'Carbonite',progress:45},
    {id:'a4',title:'Daily Grinder',achievement_type:'RANK_REWARD',description:'Daily Grinder Challenge',points_awarded:900,awarded_at:'2024-04-27T06:00:00Z',user:'Ainul Islam',progress:70},
  ],
  achUsers:[
    {name:'TenzyX',pts:'+1,300 pts',fits:'610060',badge:'Latved',color:'#7c3aed'},
    {name:'BoostMaster',pts:'+380 PTS',fits:'218',badge:'Levied',color:'#0891b2'},
    {name:'Carbonite',pts:'+900 PTS',fits:'145',badge:'Levied',color:'#059669'},
    {name:'WebKing',pts:'+300 PTS',fits:'92',badge:'Levied',color:'#d97706'},
  ],
  latestFeed:[
    {user:'TenzyX',sub:'Torlk PTrs claras',pts:'+1000 PTS',time:'1 hr. ago',pos:true,color:'#7c3aed'},
    {user:'BoostMaster',sub:'PTrs achleronnors',pts:'+500 PTS',time:'5 hr. ago',pos:true,color:'#0891b2'},
    {user:'Carbonite',sub:'Darik PTs Vininine',pts:'+300 PTS',time:'9 hr. ago',pos:true,color:'#059669'},
    {user:'Ainul Islam',sub:'Rembasted',pts:'+500 PTS',time:'18 hr. ago',pos:true,color:'#a855f7'},
    {user:'Tifaysh',sub:'Only n Dalaser',pts:'+200 PTS',time:'21 hr. ago',pos:true,color:'#d97706'},
  ],
};

const BADGE_COLORS = {
  MILESTONE:'#ffd700', STREAK:'#ff8c00', BADGE:'#a855f7',
  RANK_REWARD:'#00f3ff', BONUS:'#00ff88', CUSTOM:'#ff2d78'
};
const BADGE_ICONS = {
  MILESTONE:'💰', STREAK:'🏆', BADGE:'⭐', RANK_REWARD:'🎯', BONUS:'⚡', CUSTOM:'✨'
};

/* ══════════════════════════════════════════
   MODAL
══════════════════════════════════════════ */

/* ══════════════════════════════════════════
   CYCLE MODAL — Create & Edit
══════════════════════════════════════════ */
const CycleModal = ({ onClose, onSave, editData = null }) => {
  const isEdit = !!editData;
  const fmt = (d) => d ? d.replace('Z','').slice(0,16) : '';
  const [f, setF] = useState({
    name:              editData?.name              || '',
    slug:              editData?.slug              || '',
    description:       editData?.description       || '',
    start_date:        fmt(editData?.start_date)   || '',
    end_date:          fmt(editData?.end_date)      || '',
    points_multiplier: editData?.points_multiplier || '1.00',
    max_participants:  editData?.max_participants  || '',
    is_featured:       editData?.is_featured       || false,
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setF(p=>({...p,[k]:v}));
  const submit = async () => {
    if (!f.name||!f.slug||!f.start_date||!f.end_date) { alert('Fill required fields'); return; }
    setSaving(true);
    try { await onSave({...f, max_participants: f.max_participants||null}); onClose(); }
    catch(e){ alert(e.message); } finally { setSaving(false); }
  };
  return (
    <div className="gm-modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="gm-modal">
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
          <div className="gm-modal-title">{isEdit?'✏️ EDIT CONTEST CYCLE':'➕ NEW CONTEST CYCLE'}</div>
          <X style={{width:18,height:18,color:'#6a4a8a',cursor:'pointer'}} onClick={onClose}/>
        </div>
        <div className="gm-form-grid">
          <div className="gm-form-full"><label className="gm-form-label">NAME *</label>
            <input className="gm-form-input" value={f.name} onChange={e=>set('name',e.target.value)} placeholder="Ultimate Contest"/></div>
          <div><label className="gm-form-label">SLUG *</label>
            <input className="gm-form-input" value={f.slug} onChange={e=>set('slug',e.target.value)} placeholder="ultimate-contest" disabled={isEdit} style={isEdit?{opacity:0.5}:{}}/></div>
          <div><label className="gm-form-label">MULTIPLIER</label>
            <input className="gm-form-input" type="number" step="0.01" value={f.points_multiplier} onChange={e=>set('points_multiplier',e.target.value)}/></div>
          <div><label className="gm-form-label">START DATE *</label>
            <input className="gm-form-input" type="datetime-local" value={f.start_date} onChange={e=>set('start_date',e.target.value)}/></div>
          <div><label className="gm-form-label">END DATE *</label>
            <input className="gm-form-input" type="datetime-local" value={f.end_date} onChange={e=>set('end_date',e.target.value)}/></div>
          <div><label className="gm-form-label">MAX PARTICIPANTS</label>
            <input className="gm-form-input" type="number" value={f.max_participants} onChange={e=>set('max_participants',e.target.value)} placeholder="unlimited"/></div>
          <div className="gm-form-full"><label className="gm-form-label">DESCRIPTION</label>
            <textarea className="gm-form-input gm-form-textarea" rows={2} value={f.description} onChange={e=>set('description',e.target.value)}/></div>
          <div className="gm-form-full" style={{display:'flex',alignItems:'center',gap:10}}>
            <input type="checkbox" style={{width:16,height:16,accentColor:'#a855f7'}} checked={f.is_featured} onChange={e=>set('is_featured',e.target.checked)}/>
            <span style={{fontSize:13,color:'#c8a8e8'}}>Featured Contest</span>
          </div>
        </div>
        <div className="gm-modal-actions">
          <button className="gm-btn-cancel" onClick={onClose}>Cancel</button>
          <button className="gm-btn-create" onClick={submit} disabled={saving}>
            {saving?(isEdit?'Saving...':'Creating...'):(isEdit?'💾 Save Changes':'➕ Create Cycle')}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════
   REWARD MODAL — Create & Edit
══════════════════════════════════════════ */
const RewardModal = ({ onClose, onSave, editData = null, cycles = [] }) => {
  const isEdit = !!editData;
  const [f, setF] = useState({
    contest_cycle: editData?.contest_cycle || cycles[0]?.id || '',
    title:         editData?.title         || '',
    description:   editData?.description   || '',
    reward_type:   editData?.reward_type   || 'POINTS',
    reward_value:  editData?.reward_value  || '0',
    rank_from:     editData?.rank_from     || 1,
    rank_to:       editData?.rank_to       || 1,
    total_budget:  editData?.total_budget  || '',
    is_active:     editData?.is_active !== false,
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setF(p=>({...p,[k]:v}));
  const submit = async () => {
    if (!f.title) { alert('Title is required'); return; }
    if (parseInt(f.rank_to) < parseInt(f.rank_from)) {
      alert('❌ Rank To must be >= Rank From!\nExample: Rank From=1, Rank To=3'); return;
    }
    setSaving(true);
    try {
      const payload = {
        title:        f.title,
        description:  f.description,
        reward_type:  f.reward_type,
        reward_value: parseFloat(f.reward_value)||0,
        rank_from:    parseInt(f.rank_from)||1,
        rank_to:      parseInt(f.rank_to)||1,
        is_active:    f.is_active,
        ...(f.total_budget ? {total_budget: parseFloat(f.total_budget)} : {}),
        ...(f.contest_cycle ? {contest_cycle: f.contest_cycle} : {}),
      };
      await onSave(payload);
      onClose();
    }
    catch(e){
      try {
        const errObj = JSON.parse(e.message);
        const msgs = Object.entries(errObj).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(', ');
        alert('❌ Validation Error:\n' + msgs);
      } catch {
        alert('❌ Error: ' + (e.message||'Unknown error'));
      }
      console.error('RewardModal save error:', e);
    }
    finally { setSaving(false); }
  };
  return (
    <div className="gm-modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="gm-modal">
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
          <div className="gm-modal-title">{isEdit?'✏️ EDIT REWARD':'🎁 NEW REWARD'}</div>
          <X style={{width:18,height:18,color:'#6a4a8a',cursor:'pointer'}} onClick={onClose}/>
        </div>
        <div className="gm-form-grid">
          <div className="gm-form-full"><label className="gm-form-label">CONTEST CYCLE *</label>
            <select className="gm-form-input" value={f.contest_cycle} onChange={e=>set('contest_cycle',e.target.value)} style={{cursor:'pointer'}}>
              {cycles.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
            </select></div>
          <div className="gm-form-full"><label className="gm-form-label">TITLE *</label>
            <input className="gm-form-input" value={f.title} onChange={e=>set('title',e.target.value)} placeholder="Gold Trophy"/></div>
          <div><label className="gm-form-label">REWARD TYPE</label>
            <select className="gm-form-input" value={f.reward_type} onChange={e=>set('reward_type',e.target.value)} style={{cursor:'pointer'}}>
              {['POINTS','BADGE','COUPON','PHYSICAL','CUSTOM'].map(t=><option key={t} value={t}>{t}</option>)}
            </select></div>
          <div><label className="gm-form-label">REWARD VALUE</label>
            <input className="gm-form-input" type="number" step="0.01" value={f.reward_value} onChange={e=>set('reward_value',e.target.value)}/></div>
          <div><label className="gm-form-label">RANK FROM</label>
            <input className="gm-form-input" type="number" min="1" value={f.rank_from} onChange={e=>set('rank_from',parseInt(e.target.value)||1)}/></div>
          <div><label className="gm-form-label">RANK TO
            {parseInt(f.rank_to) < parseInt(f.rank_from) && <span style={{color:'#ff2d78',marginLeft:6,fontSize:10}}>⚠️ must be ≥ Rank From</span>}
          </label>
            <input className="gm-form-input" type="number" min={f.rank_from} value={f.rank_to}
              onChange={e=>set('rank_to',parseInt(e.target.value)||1)}
              style={parseInt(f.rank_to)<parseInt(f.rank_from)?{borderColor:'#ff2d78'}:{}}/></div>
          <div><label className="gm-form-label">TOTAL BUDGET</label>
            <input className="gm-form-input" type="number" value={f.total_budget} onChange={e=>set('total_budget',e.target.value)} placeholder="unlimited"/></div>
          <div className="gm-form-full"><label className="gm-form-label">DESCRIPTION</label>
            <textarea className="gm-form-input gm-form-textarea" rows={2} value={f.description} onChange={e=>set('description',e.target.value)}/></div>
          <div className="gm-form-full" style={{display:'flex',alignItems:'center',gap:10}}>
            <input type="checkbox" style={{width:16,height:16,accentColor:'#00ff88'}} checked={f.is_active} onChange={e=>set('is_active',e.target.checked)}/>
            <span style={{fontSize:13,color:'#c8a8e8'}}>Active Reward</span>
          </div>
        </div>
        <div className="gm-modal-actions">
          <button className="gm-btn-cancel" onClick={onClose}>Cancel</button>
          <button className="gm-btn-create" onClick={submit} disabled={saving}>
            {saving?'Saving...':(isEdit?'💾 Save Changes':'🎁 Create Reward')}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════
   DELETE CONFIRM MODAL
══════════════════════════════════════════ */
const DeleteModal = ({ onClose, onConfirm, label='this item' }) => {
  const [deleting, setDeleting] = useState(false);
  const confirm = async () => {
    setDeleting(true);
    try { await onConfirm(); onClose(); }
    catch(e){ alert(e.message); } finally { setDeleting(false); }
  };
  return (
    <div className="gm-modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="gm-modal" style={{maxWidth:380,textAlign:'center'}}>
        <div style={{fontSize:40,marginBottom:14}}>🗑️</div>
        <div className="gm-modal-title" style={{color:'#ff2d78',textShadow:'0 0 12px #ff2d78',justifyContent:'center',display:'flex'}}>DELETE CONFIRM</div>
        <p style={{fontSize:13,color:'rgba(200,168,232,0.7)',margin:'12px 0 24px',lineHeight:1.6}}>
          Are you sure you want to delete <strong style={{color:'#fff'}}>{label}</strong>?<br/>
          <span style={{fontSize:11,color:'rgba(255,45,120,0.5)'}}>This action cannot be undone.</span>
        </p>
        <div className="gm-modal-actions" style={{justifyContent:'center'}}>
          <button className="gm-btn-cancel" onClick={onClose}>Cancel</button>
          <button onClick={confirm} disabled={deleting}
            style={{padding:'10px 24px',borderRadius:8,border:'none',cursor:'pointer',
              fontFamily:'Orbitron,sans-serif',fontSize:10,fontWeight:700,letterSpacing:1,
              background:'linear-gradient(135deg,#ff2d78,#ff6b35)',color:'#fff',
              boxShadow:'0 0 20px rgba(255,45,120,0.35)'}}>
            {deleting?'Deleting...':'🗑️ Delete'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════
   AWARD ACHIEVEMENT MODAL
══════════════════════════════════════════ */
const AwardModal = ({ onClose, onSave, cycles = [] }) => {
  const [f, setF] = useState({
    user_id: '', contest_cycle: cycles[0]?.id || '',
    achievement_type: 'BONUS', points_awarded: '100',
    title: '', description: '', metadata: '',
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setF(p=>({...p,[k]:v}));
  const submit = async () => {
    if (!f.user_id||!f.title) { alert('User ID and Title are required'); return; }
    setSaving(true);
    try {
      await onSave({
        user: f.user_id,
        contest_cycle: f.contest_cycle||null,
        achievement_type: f.achievement_type,
        points_awarded: parseInt(f.points_awarded)||0,
        title: f.title,
        description: f.description,
        is_awarded: true,
        awarded_at: new Date().toISOString(),
      });
      onClose();
    } catch(e) {
      try { const err=JSON.parse(e.message); alert('❌ '+Object.entries(err).map(([k,v])=>`${k}: ${v}`).join(', ')); }
      catch { alert('❌ '+e.message); }
    } finally { setSaving(false); }
  };
  const ACH_TYPES = ['RANK_REWARD','MILESTONE','STREAK','BADGE','BONUS','CUSTOM'];
  return (
    <div className="gm-modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="gm-modal">
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
          <div className="gm-modal-title">🏆 AWARD ACHIEVEMENT</div>
          <X style={{width:18,height:18,color:'#6a4a8a',cursor:'pointer'}} onClick={onClose}/>
        </div>
        <div className="gm-form-grid">
          <div className="gm-form-full"><label className="gm-form-label">USER ID / USERNAME *</label>
            <input className="gm-form-input" value={f.user_id} onChange={e=>set('user_id',e.target.value)} placeholder="UUID or username"/></div>
          <div className="gm-form-full"><label className="gm-form-label">TITLE *</label>
            <input className="gm-form-input" value={f.title} onChange={e=>set('title',e.target.value)} placeholder="Achievement title"/></div>
          <div><label className="gm-form-label">TYPE</label>
            <select className="gm-form-input" value={f.achievement_type} onChange={e=>set('achievement_type',e.target.value)} style={{cursor:'pointer'}}>
              {ACH_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
            </select></div>
          <div><label className="gm-form-label">POINTS</label>
            <input className="gm-form-input" type="number" value={f.points_awarded} onChange={e=>set('points_awarded',e.target.value)}/></div>
          <div className="gm-form-full"><label className="gm-form-label">CONTEST CYCLE</label>
            <select className="gm-form-input" value={f.contest_cycle} onChange={e=>set('contest_cycle',e.target.value)} style={{cursor:'pointer'}}>
              <option value="">— No cycle —</option>
              {cycles.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
            </select></div>
          <div className="gm-form-full"><label className="gm-form-label">DESCRIPTION</label>
            <textarea className="gm-form-input gm-form-textarea" rows={2} value={f.description} onChange={e=>set('description',e.target.value)}/></div>
        </div>
        <div className="gm-modal-actions">
          <button className="gm-btn-cancel" onClick={onClose}>Cancel</button>
          <button className="gm-btn-create" onClick={submit} disabled={saving}>
            {saving?'Awarding...':'🏆 Award Achievement'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default function Gamification() {
  const [cycles,       setCycles]     = useState([]);
  const [activeCycle,  setActive]     = useState(null);
  const [lb,           setLb]         = useState([]);
  const [rewards,      setRewards]    = useState([]);
  const [achievements, setAch]        = useState([]);
  const [achUsers,     setAchUsers]   = useState([]);
  const [latestFeed,   setFeed]       = useState([]);
  const [currentUser,  setCurrentUser] = useState(null);
  const [notifications,setNotifs]      = useState([]);
  const [notifOpen,    setNotifOpen]   = useState(false);
  const [searchQuery,  setSearch]      = useState('');
  const [searchResults,setSearchRes]   = useState([]);
  const [searchOpen,   setSearchOpen]  = useState(false);
  const [myPts,        setMyPts]       = useState({total_points:0,rank:null});
  const [stats,        setStats]      = useState({active:0,participants:0,prize:0});
  const [loading,      setLoading]    = useState(true);
  const [activeTab,    setTab]        = useState('CURRENT');
  const [activeNav,    setNav]        = useState('leaderboard');
  const [showModal,    setModal]      = useState(false);
  const [actLoad,      setActLoad]    = useState('');
  const [tick,         setTick]       = useState(0);

  // ── CRUD modal states ──────────────────────────
  const [editCycle,      setEditCycle]   = useState(null);
  const [showEditCycle,  setShowEdit]    = useState(false);
  const [showRewardModal,setShowReward]  = useState(false);
  const [editReward,     setEditReward]  = useState(null);
  const [deleteTarget,   setDelTarget]   = useState(null);

  // ── New feature states ────────────────────────
  const [lbScope,        setLbScope]    = useState('GLOBAL');
  const [showAwardModal, setShowAward]  = useState(false);
  const [snapshotList,   setSnapList]   = useState([]);
  const [showSnapList,   setShowSnap]   = useState(false);
  const [badgePage,      setBadgePage]  = useState(0);
  const BADGES_PER_PAGE = 4;

  // ── CRUD handlers ──────────────────────────────
  const handleCreateCycle  = async (d) => { if(!d) return; await api.createCycle(d); await loadData(); };
  const handleEditCycle    = async (d) => {
    const res = await api.updateCycle(editCycle.id, d);
    await loadData();
  };
  const handleDeleteCycle  = async (id) => { await api.deleteCycle(id);           await loadData(); };
  const handleCreateReward = async (d) => { await api.createReward(d);            await loadData(); };
  const handleEditReward   = async (d) => {
    // Check if this is mock data (fake IDs like 'r1', 'r2')
    if (editReward?.id && String(editReward.id).match(/^r\d+$/)) {
      alert('⚠️ This is demo data. Please create a real reward first using "+ ADD REWARD" button.');
      return;
    }
    const res = await api.updateReward(editReward.id, d);
    await loadData();
  };
  const handleDeleteReward = async (id) => {
    if (id && String(id).match(/^r\d+$/)) {
      alert('⚠️ This is demo data. Cannot delete mock rewards.');
      return;
    }
    await api.deleteReward(id);
    await loadData();
  };

  useEffect(()=>{ const t=setInterval(()=>setTick(p=>p+1),60000); return ()=>clearInterval(t); },[]);

  const timeLeft = useCallback((end) => {
    if (!end) return {d:'08',h:'14',m:'20'};
    const diff = new Date(end) - new Date();
    if (diff<=0) return {d:'00',h:'00',m:'00'};
    return {
      d: String(Math.floor(diff/86400000)).padStart(2,'0'),
      h: String(Math.floor((diff%86400000)/3600000)).padStart(2,'0'),
      m: String(Math.floor((diff%3600000)/60000)).padStart(2,'0'),
    };
  }, [tick]);

  // ── New feature handlers ─────────────────────────
  const handleGenerateSnapshot = async (scope='GLOBAL') => {
    if (!activeCycle?.id) { alert('❌ No active cycle found! Activate a cycle first.'); return; }
    try {
      setActLoad('Snapshot_'+scope);
      await api.genSnapshot({ cycle_id: activeCycle.id, scope, top_n: 100 });
      await loadData();
      alert('✅ Snapshot generated for '+scope);
    } catch(e) {
      try { const err=JSON.parse(e.message); alert('❌ '+Object.values(err).flat().join(', ')); }
      catch { alert('❌ '+e.message); }
    } finally { setActLoad(''); }
  };

  const handleResetCycle = async (id, name) => {
    if (!window.confirm(`⚠️ Reset cycle "${name}"?
This will clear leaderboard data!`)) return;
    try {
      setActLoad('Reset');
      await api.resetCycle(id);
      await loadData();
      alert('✅ Cycle reset successfully');
    } catch(e) { alert('❌ Reset failed: '+e.message); }
    finally { setActLoad(''); }
  };

  const handleAwardAchievement = async (d) => {
    if (!d) return;
    try {
      await api.awardAch(d);
      await loadData();
    } catch(e) {
      try {
        const err = JSON.parse(e.message);
        const msg = Object.entries(err).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
        throw new Error(msg);
      } catch(e2) { throw e2.message ? e2 : e; }
    }
  };

  const loadSnapshots = async () => {
    if (!activeCycle?.id) { alert('❌ No active cycle. Activate a cycle first.'); return; }
    try {
      const r = await api.snapshots(activeCycle.id);
      setSnapList(r.results||r||[]);
      setShowSnap(true);
    } catch(e) { alert('❌ Could not load snapshots: '+e.message); }
  };

  // ── Search handler ────────────────────────────────
  const handleSearch = useCallback((q) => {
    setSearch(q);
    if (!q.trim()) { setSearchRes([]); setSearchOpen(false); return; }
    const lower = q.toLowerCase();
    const results = [
      ...cycles.filter(c=>c.name?.toLowerCase().includes(lower)).map(c=>({type:'Cycle',label:c.name,status:c.status})),
      ...rewards.filter(r=>r.title?.toLowerCase().includes(lower)).map(r=>({type:'Reward',label:r.title,value:r.reward_value})),
      ...achievements.filter(a=>(a.title||'').toLowerCase().includes(lower)).map(a=>({type:'Achievement',label:a.title,pts:a.points_awarded})),
    ].slice(0,8);
    setSearchRes(results);
    setSearchOpen(results.length > 0);
  }, [cycles, rewards, achievements]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      /* real current user */
      try {
        const u = await api.me();
        setCurrentUser(u);
      } catch {
        try {
          const u2 = await api.profile();
          setCurrentUser(u2);
        } catch { /* stay null */ }
      }

      /* real notifications */
      try {
        const n = await api.notifications();
        setNotifs(n.results||n||[]);
      } catch { setNotifs([]); }

      /* cycles */
      let cList = [];
      try {
        const r = await api.cycles();
        cList = r.results||r||[];
      } catch { cList = []; }
      setCycles(cList);
      const active = cList.find(c=>c.status==='ACTIVE')||null;
      setActive(active);

      /* rewards */
      let rList = [];
      try { const r=await api.rewards(); rList=r.results||r||[]; } catch { rList=[]; }
      setRewards(rList);
      const prize = rList.reduce((s,r)=>s+parseFloat(r.reward_value||0),0);

      /* leaderboard */
      let lbData = [];
      if (active?.id) {
        try {
          const snap = await api.leaderboard(active.id,'GLOBAL');
          if (snap?.snapshot_data?.length) lbData = snap.snapshot_data;
        } catch {}
      }
      setLb(lbData);

      /* achievements */
      let aList = [];
      try { const r=await api.achievements(); aList=r.results||r||[]; } catch { aList=[]; }
      const finalAch = aList;
      setAch(finalAch);

      /* achUsers — real data থেকে: achievement list → showcase table */
      const AV_COLORS_MAP = ['#7c3aed','#0891b2','#059669','#d97706','#a855f7','#dc2626'];
      const realAchUsers = finalAch.slice(0, 4).map((a, i) => ({
        name:  a.user  || a.title || `User ${i+1}`,
        pts:   `+${(a.points_awarded || 0).toLocaleString()} PTS`,
        fits:  a.metadata?.fits || String((a.points_awarded || 0) * 2),
        type:  a.achievement_type || a.achievement_type_display || 'BONUS',
        badge: a.is_awarded !== false ? 'Awarded' : 'Pending',
        color: AV_COLORS_MAP[i % AV_COLORS_MAP.length],
      }));
      setAchUsers(realAchUsers.length ? realAchUsers : []);

      /* latestFeed — real data থেকে: awarded_at দিয়ে sort করে feed */
      const sorted = [...finalAch].sort(
        (a, b) => new Date(b.awarded_at || 0) - new Date(a.awarded_at || 0)
      );
      const realFeed = sorted.slice(0, 5).map((a, i) => {
        const agoMs  = new Date() - new Date(a.awarded_at || Date.now());
        const agoMin = Math.floor(agoMs / 60000);
        const agoHr  = Math.floor(agoMs / 3600000);
        const agoDy  = Math.floor(agoMs / 86400000);
        const timeStr = agoDy  > 0 ? `${agoDy} day ago`
                      : agoHr  > 0 ? `${agoHr} hr. ago`
                      : `${agoMin} min. ago`;
        return {
          user:  a.user || a.title || `User ${i+1}`,
          sub:   a.description || a.achievement_type_display || a.achievement_type || '',
          pts:   `+${(a.points_awarded || 0).toLocaleString()} PTS`,
          time:  timeStr,
          pos:   true,
          color: AV_COLORS_MAP[i % AV_COLORS_MAP.length],
        };
      });
      setFeed(realFeed.length ? realFeed : []);

      /* my points */
      try {
        // Don't pass cycle_id to avoid 500 when cycle has no data yet
        const mp = await api.myPoints('');
        setMyPts(mp);
      } catch {}

      setStats({ active:cList.filter(c=>c.status==='ACTIVE').length, participants:lbData.length, prize });
    } finally { setLoading(false); }
  }, []);

  useEffect(()=>{ loadData(); },[loadData]);

  const doAction = async (fn, id, label) => {
    if (!id) { alert(`❌ No ID provided for ${label}`); return; }
    try {
      setActLoad(label);
      await fn(id);
      await loadData();
      // success toast
    } catch(e){
      try {
        const err = JSON.parse(e.message);
        const msg = Object.entries(err).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
        alert(`❌ ${label} failed: ${msg}`);
      } catch { alert(`❌ ${label} failed: ${e.message||'Unknown error'}`); }
    }
    finally { setActLoad(''); }
  };

  if (loading) return (
    <div className="gm-loading">
      <div className="gm-spinner"/>
      <div className="gm-loading-text">LOADING GAMIFICATION...</div>
    </div>
  );

  const tl  = timeLeft(activeCycle?.end_date);
  const now = new Date().toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});

  /* which leaderboard entries to show */
  const topEntries = lb.filter(e=>!e.isMe).slice(0,7);
  const myName     = currentUser ? (currentUser.username || currentUser.email?.split('@')[0]) : null;
  const meEntry    = lb.find(e=>e.isMe || (myName && e.display_name===myName) || (currentUser?.pk && e.user_id===String(currentUser.pk)));

  return (
    <div className="gm-root">

      {/* ══ HEADER ══ */}
      <header className="gm-header">
        <div className="gm-logo">
          <div className="gm-logo-diamond"/>
          <span className="gm-logo-text">GAMIFICATION</span>
        </div>
        <div className="gm-search" style={{position:'relative'}}>
          <Search style={{width:15,height:15}}/>
          <input
            placeholder="Search cycles, rewards, achievements..."
            value={searchQuery}
            onChange={e=>handleSearch(e.target.value)}
            onFocus={()=>searchResults.length&&setSearchOpen(true)}
            onBlur={()=>setTimeout(()=>setSearchOpen(false),200)}
          />
          {searchOpen && (
            <div style={{position:'absolute',top:'calc(100% + 6px)',left:0,right:0,zIndex:9999,
              background:'rgba(8,4,24,0.98)',border:'1px solid rgba(168,85,247,0.3)',
              borderRadius:10,overflow:'hidden',boxShadow:'0 8px 32px rgba(0,0,0,0.5)'}}>
              {searchResults.map((r,i)=>(
                <div key={i} style={{padding:'10px 16px',borderBottom:'1px solid rgba(168,85,247,0.07)',
                  display:'flex',alignItems:'center',gap:10,cursor:'pointer',transition:'background .15s'}}
                  onMouseEnter={e=>e.currentTarget.style.background='rgba(168,85,247,0.08)'}
                  onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                  <span style={{padding:'2px 8px',borderRadius:4,fontSize:9,fontFamily:'Orbitron,sans-serif',
                    background:'rgba(168,85,247,0.15)',color:'#a855f7',border:'1px solid rgba(168,85,247,0.2)',
                    flexShrink:0}}>{r.type}</span>
                  <span style={{fontSize:13,color:'#e0d0f0',flex:1}}>{r.label}</span>
                  {r.status && <span style={{fontSize:10,color:'rgba(168,85,247,0.5)'}}>{r.status}</span>}
                  {r.pts    && <span style={{fontSize:10,color:'#a855f7',fontFamily:'Orbitron,sans-serif'}}>+{r.pts}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="gm-header-right">
          <div className="gm-header-date">
            <Calendar style={{width:13,height:13,color:'#a855f7'}}/>
            {now}
          </div>
          <div className="gm-icon-btn" style={{position:'relative'}}
            onClick={()=>setNotifOpen(p=>!p)}>
            <Bell style={{width:15,height:15}}/>
            {notifications.length > 0 && (
              <div className="gm-notif-dot" style={{
                position:'absolute',top:5,right:5,width:16,height:16,borderRadius:'50%',
                background:'#ff2d78',color:'#fff',fontSize:9,fontWeight:700,
                display:'flex',alignItems:'center',justifyContent:'center',
                fontFamily:'Orbitron,sans-serif',boxShadow:'0 0 8px #ff2d78',
              }}>{notifications.length > 9 ? '9+' : notifications.length}</div>
            )}
            {notifOpen && (
              <div style={{position:'absolute',top:'calc(100% + 8px)',right:0,width:300,zIndex:9999,
                background:'rgba(8,4,24,0.98)',border:'1px solid rgba(168,85,247,0.3)',
                borderRadius:12,overflow:'hidden',boxShadow:'0 8px 32px rgba(0,0,0,0.6)'}}>
                <div style={{padding:'10px 16px',borderBottom:'1px solid rgba(168,85,247,0.1)',
                  fontFamily:'Orbitron,sans-serif',fontSize:10,color:'#a855f7',letterSpacing:1}}>
                  NOTIFICATIONS {notifications.length > 0 && `(${notifications.length})`}
                </div>
                {notifications.length === 0
                  ? <div style={{padding:'20px',textAlign:'center',fontSize:12,color:'rgba(168,85,247,0.4)'}}>No notifications</div>
                  : notifications.slice(0,6).map((n,i)=>(
                    <div key={i} style={{padding:'10px 16px',borderBottom:'1px solid rgba(168,85,247,0.06)',
                      display:'flex',gap:10,alignItems:'flex-start'}}>
                      <div style={{width:8,height:8,borderRadius:'50%',background:'#a855f7',
                        flexShrink:0,marginTop:4,boxShadow:'0 0 6px #a855f7'}}/>
                      <div>
                        <div style={{fontSize:12,color:'#e0d0f0'}}>{n.title||n.message||n.notification_type||'Notification'}</div>
                        <div style={{fontSize:10,color:'rgba(168,85,247,0.4)',marginTop:2,fontFamily:'Share Tech Mono,monospace'}}>
                          {n.created_at ? new Date(n.created_at).toLocaleDateString() : ''}
                        </div>
                      </div>
                    </div>
                  ))
                }
              </div>
            )}
          </div>
          <div className="gm-icon-btn">
            <Settings style={{width:15,height:15}}/>
          </div>
          <div className="gm-user-avatar" title={currentUser?.username||currentUser?.email||'Admin'}
          style={{overflow:'hidden',padding:0}}>
          {currentUser?.avatar
            ? <img src={currentUser.avatar} alt="av" style={{width:'100%',height:'100%',objectFit:'cover',borderRadius:'50%'}}/>
            : (currentUser?.username||currentUser?.email||'A')[0].toUpperCase()}
        </div>
        </div>
      </header>

      {showModal      && <CycleModal  onClose={()=>setModal(false)}    onSave={handleCreateCycle} />}
      {showEditCycle  && <CycleModal  onClose={()=>setShowEdit(false)}   onSave={handleEditCycle}   editData={editCycle} />}
      {showRewardModal && <RewardModal onClose={()=>setShowReward(false)} onSave={editReward?handleEditReward:handleCreateReward} editData={editReward} cycles={cycles} />}
      {showAwardModal && <AwardModal  onClose={()=>setShowAward(false)}  onSave={handleAwardAchievement} cycles={cycles} />}
      {deleteTarget   && <DeleteModal onClose={()=>setDelTarget(null)} label={deleteTarget.label}
        onConfirm={()=> deleteTarget.type==='cycle' ? handleDeleteCycle(deleteTarget.id) : handleDeleteReward(deleteTarget.id)} />}

      {/* Snapshot History Panel */}
      {showSnapList && (
        <div className="gm-modal-overlay" onClick={e=>e.target===e.currentTarget&&setShowSnap(false)}>
          <div className="gm-modal" style={{maxWidth:600}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:16}}>
              <div className="gm-modal-title">📸 SNAPSHOT HISTORY</div>
              <X style={{width:18,height:18,color:'#6a4a8a',cursor:'pointer'}} onClick={()=>setShowSnap(false)}/>
            </div>
            {snapshotList.length===0
              ? <div style={{textAlign:'center',color:'rgba(168,85,247,0.4)',padding:20}}>No snapshots yet</div>
              : snapshotList.map(s=>(
                <div key={s.id} style={{padding:'10px 0',borderBottom:'1px solid rgba(168,85,247,0.1)',
                  display:'flex',gap:12,alignItems:'center'}}>
                  <span style={{padding:'2px 8px',borderRadius:4,fontSize:9,fontFamily:'Orbitron,sans-serif',
                    background:s.status==='FINALIZED'?'rgba(0,255,136,0.1)':'rgba(255,215,0,0.1)',
                    color:s.status==='FINALIZED'?'#00ff88':'#ffd700',
                    border:`1px solid ${s.status==='FINALIZED'?'rgba(0,255,136,0.2)':'rgba(255,215,0,0.2)'}`}}>
                    {s.status}
                  </span>
                  <span style={{fontSize:11,color:'rgba(200,168,232,0.6)',fontFamily:'Share Tech Mono,monospace'}}>
                    {s.scope}
                  </span>
                  <span style={{fontSize:11,color:'rgba(200,168,232,0.4)',fontFamily:'Share Tech Mono,monospace',flex:1}}>
                    {s.generated_at ? new Date(s.generated_at).toLocaleString() : s.created_at?.slice(0,16)}
                  </span>
                  <span style={{fontFamily:'Orbitron,sans-serif',fontSize:10,color:'#a855f7'}}>
                    {s.entry_count} entries
                  </span>
                </div>
              ))
            }
          </div>
        </div>
      )}
      <div className="gm-body">

        {/* ══ SIDEBAR ══ */}
        <aside className="gm-sidebar">

          {/* profile */}
          <div className="gm-sb-profile">
            <div className="gm-sb-avatar">
              {currentUser?.avatar
                ? <img src={currentUser.avatar} alt="avatar" style={{width:'100%',height:'100%',objectFit:'cover',borderRadius:8}}/>
                : <div className="gm-sb-avatar-placeholder">
                    {(currentUser?.username||currentUser?.email||'A')[0].toUpperCase()}
                  </div>
              }
            </div>
            <div>
              <div className="gm-sb-name">
                {currentUser ? (currentUser.username || currentUser.email || 'Admin') : 'Loading...'}
              </div>
              <div className="gm-sb-role">
                ({currentUser?.role || 'admin'})
              </div>
            </div>
            <ChevronDown className="gm-sb-chevron" style={{width:14,height:14}}/>
          </div>

          {/* points */}
          <div className="gm-sb-points">
            <span className="gm-pts-icon">💎</span>
            <div>
              <div style={{display:'flex',alignItems:'baseline',gap:5}}>
                <span className="gm-pts-value">{(myPts?.total_points||0).toLocaleString()}</span>
                <span className="gm-pts-label">PTS</span>
              </div>
            </div>
            {myPts?.today_points ? <div className="gm-pts-today">+{myPts.today_points} today</div> : null}
          </div>

          {/* active cycle button */}
          <div className="gm-active-cycle-btn">
            <div className="gm-cycle-x"/>
            <span>{activeCycle?.name?.toUpperCase()||'NO ACTIVE CYCLE'}</span>
          </div>

          {/* dropdown */}
          <div className="gm-sb-dropdown">
            <RefreshCw style={{width:10,height:10,color:'rgba(168,85,247,0.5)'}}/>
            <span>{activeCycle ? `${activeCycle.start_date?.slice(0,10)} → ${activeCycle.end_date?.slice(0,10)}` : "No active cycle"}</span>
            <ChevronDown style={{width:10,height:10,color:'rgba(168,85,247,0.5)'}}/>
          </div>

          {/* corp section */}
          <div className="gm-sb-corp">
            <Activity style={{width:11,height:11,color:'rgba(168,85,247,0.5)'}}/>
            <span>{activeCycle ? `×${activeCycle.points_multiplier} multiplier` : ""}</span>
            <Settings style={{width:11,height:11,color:'rgba(168,85,247,0.4)'}}/>
          </div>

          {/* nav */}
          <nav className="gm-sb-nav">
            {[
              {id:'leaderboard',  icon:<BarChart2 style={{width:15,height:15}}/>, label:'Leaderboard'},
              {id:'cycle',        icon:<RefreshCw style={{width:15,height:15}}/>, label:'Contest Cycle'},
              {id:'rewards',      icon:<Gift       style={{width:15,height:15}}/>, label:'Rewards'},
              {id:'achievements', icon:<Star       style={{width:15,height:15}}/>, label:'Achievements'},
              {id:'challenges',   icon:<Target     style={{width:15,height:15}}/>, label:'Challenges', soon:true},
            ].map(item=>(
              <div key={item.id}
                className={`gm-sb-nav-item${activeNav===item.id?' active':''}`}
                onClick={()=>{
                  if(item.soon){ alert('🚧 Challenges module coming soon!'); return; }
                  setNav(item.id);
                  const el = document.getElementById('gm-section-'+item.id);
                  if (!el) return; // section not found, nav highlight still updates
                  if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
                }}>
                <span className="gm-sb-nav-icon">{item.icon}</span>
                <span className="gm-sb-nav-label">
                  {item.label}{item.soon&&<span style={{fontSize:8,marginLeft:4,color:'rgba(168,85,247,0.3)'}}>SOON</span>}
                </span>
              </div>
            ))}
          </nav>

          {/* new contest */}
          <div className="gm-new-contest-btn" onClick={(e)=>{e.stopPropagation();setEditCycle(null);setModal(true);}}>
            <Plus style={{width:13,height:13}}/>
            NEW CONTEST
          </div>

          {/* icon shortcuts */}
          <div className="gm-sb-icons">
            {[LayoutDashboard, ShieldCheck, Gift, Star, Target, Activity, Settings].map((Icon,i)=>(
              <div key={i} className="gm-sb-icon-row"><Icon style={{width:13,height:13}}/></div>
            ))}
          </div>

          {/* terminal */}
          <div className="gm-terminal">{(currentUser?.username||"admin").toLowerCase()}@gamification $</div>
        </aside>

        {/* ══ MAIN ══ */}
        <main className="gm-main">

          {/* page title */}
          <div className="gm-page-title">
            <h1><span className="accent">GAMIFICATION</span> <span className="light">OVERVIEW</span></h1>
            <button style={{
              padding:'8px 16px',border:'1px solid rgba(168,85,247,0.3)',borderRadius:8,
              background:'rgba(168,85,247,0.1)',color:'#c8a8e8',cursor:'pointer',
              fontFamily:'Orbitron,sans-serif',fontSize:10,letterSpacing:1,
              display:'flex',alignItems:'center',gap:6,
            }} onClick={loadData}>
              <RefreshCw style={{width:11,height:11,animation:loading?"spin 1s linear infinite":"none"}}/>{loading?" LOADING...":" REFRESH"}
            </button>
          </div>

          {/* ── STAT CARDS ── */}
          <div className="gm-stats-grid">
            {/* Active Contests */}
            <div className="gm-stat-card" style={{'--accent-color':'#ff2d78','--border-color':'rgba(255,45,120,0.3)','--glow-color':'rgba(255,45,120,0.1)'}}>
              <div className="gm-stat-top">
                <div className="gm-stat-label">ACTIVE CONTESTS</div>
                <Zap style={{width:14,height:14,color:'#ff2d78'}}/>
              </div>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                <div className="gm-stat-value large">{stats.active||6}</div>
                <div className="gm-stat-badge">{stats.active||6}</div>
              </div>
              <Sparkline color="#ff2d78"/>
            </div>

            {/* Current Participants */}
            <div className="gm-stat-card" style={{'--accent-color':'#00f3ff','--border-color':'rgba(0,243,255,0.3)','--glow-color':'rgba(0,243,255,0.08)'}}>
              <div className="gm-stat-top">
                <div className="gm-stat-label">CURRENT PARTICIPANTS</div>
                <Users style={{width:14,height:14,color:'#00f3ff'}}/>
              </div>
              <div className="gm-stat-value large">{(stats.participants||12408).toLocaleString()}</div>
              <div className="gm-stat-footer">TOTAL USERS</div>
              <Sparkline color="#00f3ff"/>
            </div>

            {/* Next Reset */}
            <div className="gm-stat-card" style={{'--accent-color':'#ff8c00','--border-color':'rgba(255,140,0,0.35)','--glow-color':'rgba(255,140,0,0.1)'}}>
              <div className="gm-stat-top">
                <div className="gm-stat-label">NEXT RESET IN</div>
                <Clock style={{width:14,height:14,color:'#ff8c00'}}/>
              </div>
              <div className="gm-stat-value countdown">{tl.d}d {tl.h}h {tl.m}m</div>
              <div className="gm-stat-footer">{activeCycle?.name||'PROWM PNG DALIGE'}</div>
            </div>

            {/* Total Prize Pool */}
            <div className="gm-stat-card" style={{'--accent-color':'#ffd700','--border-color':'rgba(255,215,0,0.3)','--glow-color':'rgba(255,215,0,0.08)'}}>
              <div className="gm-stat-top">
                <div className="gm-stat-label">TOTAL PRIZE POOL</div>
                <Trophy style={{width:14,height:14,color:'#ffd700'}}/>
              </div>
              <div className="gm-stat-value large">${(stats.prize||0).toLocaleString(undefined,{maximumFractionDigits:0})}</div>
              <div className="gm-stat-footer">+ IPS CUELINGS</div>
              <Sparkline color="#ffd700"/>
            </div>
          </div>

          {/* ── MIDDLE ROW ── */}
          <div className="gm-middle-row">

            {/* Contest Cycle card */}
            <div id="gm-section-leaderboard" className="gm-contest-card">
              {/* header tabs */}
              <div className="gm-cc-header">
                <div className="gm-cc-title">CONTEST CYCLE</div>
                <div className="gm-cc-tabs">
                  {['CURRENT','WEEKLY','ALL TIME'].map((t,i)=>(
                    <React.Fragment key={t}>
                      {i>0&&<span className="gm-cc-tab-sep">·</span>}
                      <div className={`gm-cc-tab${activeTab===t?' active':''}`} onClick={()=>setTab(t)}>{t}</div>
                    </React.Fragment>
                  ))}
                  <span style={{marginLeft:8,color:'rgba(168,85,247,0.3)',fontSize:13}}>★ ✕ ◆</span>
                </div>
              </div>

              {/* hero */}
              {/* Tab filtered cycle display */}
              {activeTab==='WEEKLY' && (
                cycles.filter(c=>c.is_featured).length===0
                  ? <div style={{padding:'10px',textAlign:'center',color:'rgba(168,85,247,0.3)',fontSize:11,fontFamily:'Share Tech Mono,monospace'}}>No featured/weekly contests</div>
                  : <div style={{padding:'8px 16px',display:'flex',gap:8,flexWrap:'wrap',borderBottom:'1px solid rgba(100,60,220,0.1)'}}>
                      {cycles.filter(c=>c.is_featured).map(c=>(
                        <span key={c.id} style={{padding:'3px 10px',borderRadius:5,fontSize:10,cursor:'pointer',
                          fontFamily:'Share Tech Mono,monospace',
                          background:'rgba(255,215,0,0.08)',color:'#ffd700',
                          border:'1px solid rgba(255,215,0,0.2)'}}>
                          ★ {c.name} · {c.status}
                        </span>
                      ))}
                    </div>
              )}
              {activeTab==='ALL TIME' && cycles.length>0 && (
                <div style={{padding:'8px 16px',display:'flex',gap:8,flexWrap:'wrap',borderBottom:'1px solid rgba(100,60,220,0.1)'}}>
                  {cycles.map(c=>(
                    <span key={c.id}
                      style={{padding:'3px 10px',borderRadius:5,fontSize:10,cursor:'pointer',
                        fontFamily:'Share Tech Mono,monospace',
                        background:c.status==='ACTIVE'?'rgba(0,255,136,0.1)':'rgba(168,85,247,0.07)',
                        color:c.status==='ACTIVE'?'#00ff88':'rgba(168,85,247,0.5)',
                        border:`1px solid ${c.status==='ACTIVE'?'rgba(0,255,136,0.2)':'rgba(168,85,247,0.1)'}`}}>
                      {c.name} · {c.status}
                    </span>
                  ))}
                </div>
              )}
              <div className="gm-cc-hero">
                <div className="gm-cc-hero-top">
                  <div>
                    <div className="gm-cc-name">{activeCycle?.name?.toUpperCase()||'ULTIMATE CONTEST'}</div>
                  </div>
                  <div style={{display:'flex',gap:8,alignItems:'center'}}>
                    <div className="gm-cc-snapshot-badge" style={{cursor:'pointer'}}
                      onClick={()=>handleGenerateSnapshot('GLOBAL')}>
                      <RefreshCw style={{width:9,height:9}}/> 
                      {actLoad==='Snapshot_GLOBAL'?'GENERATING...':'GENERATE SNAPSHOT'}
                    </div>
                    <span style={{
                      padding:'4px 10px',borderRadius:6,cursor:'pointer',
                      background:'rgba(255,215,0,0.1)',border:'1px solid rgba(255,215,0,0.25)',
                      fontFamily:'Share Tech Mono,monospace',fontSize:9,color:'rgba(255,215,0,0.6)'
                    }} onClick={loadSnapshots}>📋 HISTORY</span>
                  </div>
                </div>
                <div className="gm-cc-rank-display">TOP RANK :</div>
                <div className="gm-cc-rank-value">
                  {lb?.[0]?.display_name?.toUpperCase() || 'NO DATA'}
                </div>
                {lb?.[0] && <div style={{fontFamily:"Share Tech Mono,monospace",fontSize:12,color:"rgba(255,215,0,0.5)",marginTop:2}}>
                  {(lb[0]?.points||0).toLocaleString()} PTS
                </div>}

                {/* admin actions */}
                <div style={{display:'flex',gap:6,marginTop:10,flexWrap:'wrap',alignItems:'center'}}>
                  {activeCycle?.status==='DRAFT' && (
                    <button type="button" onClick={()=>doAction(api.activate,activeCycle.id,'Activate')} disabled={!!actLoad}
                      style={{padding:'6px 14px',borderRadius:6,border:'1px solid #00ff88',background:'rgba(0,255,136,.08)',
                        color:'#00ff88',fontFamily:'Orbitron,sans-serif',fontSize:9,cursor:'pointer',letterSpacing:1}}>
                      {actLoad==='Activate'?'⏳ ...':'▶ ACTIVATE'}
                    </button>
                  )}
                  {activeCycle?.status==='ACTIVE' && (<>
                    <button type="button" onClick={()=>doAction(api.complete,activeCycle.id,'Complete')} disabled={!!actLoad}
                      style={{padding:'6px 14px',borderRadius:6,border:'1px solid #ffd700',background:'rgba(255,215,0,.08)',
                        color:'#ffd700',fontFamily:'Orbitron,sans-serif',fontSize:9,cursor:'pointer',letterSpacing:1}}>
                      {actLoad==='Complete'?'⏳ ...':'✓ COMPLETE'}
                    </button>
                  </>)}
                  {activeCycle?.status==='COMPLETED' && (
                    <button type="button" onClick={()=>doAction(api.distribute,activeCycle.id,'Distribute')} disabled={!!actLoad}
                      style={{padding:'6px 14px',borderRadius:6,border:'1px solid #a855f7',background:'rgba(168,85,247,.08)',
                        color:'#a855f7',fontFamily:'Orbitron,sans-serif',fontSize:9,cursor:'pointer',letterSpacing:1}}>
                      {actLoad==='Distribute'?'⏳ ...':'🎁 DISTRIBUTE'}
                    </button>
                  )}
                  {/* Generate Snapshot — all scopes */}
                  {activeCycle?.id && (<>
                    {['GLOBAL','REGIONAL','CATEGORY'].map(sc=>(
                      <button key={sc} type="button" disabled={!!actLoad}
                        onClick={()=>handleGenerateSnapshot(sc)}
                        style={{padding:'6px 12px',borderRadius:6,
                          border:`1px solid ${lbScope===sc?'rgba(0,243,255,0.6)':'rgba(0,243,255,0.2)'}`,
                          background:lbScope===sc?'rgba(0,243,255,0.12)':'rgba(0,243,255,0.04)',
                          color:'#00f3ff',fontFamily:'Orbitron,sans-serif',fontSize:8,cursor:'pointer',letterSpacing:0.5}}>
                        {actLoad==='Snapshot_'+sc?'⏳':'📸'} {sc}
                      </button>
                    ))}
                  </>)}
                  {/* Award Achievement */}
                  <button type="button" onClick={()=>setShowAward(true)}
                    style={{padding:'6px 12px',borderRadius:6,border:'1px solid rgba(255,215,0,0.3)',
                      background:'rgba(255,215,0,0.06)',color:'#ffd700',fontFamily:'Orbitron,sans-serif',
                      fontSize:8,cursor:'pointer',letterSpacing:0.5}}>
                    🏆 AWARD
                  </button>
                  {/* Reset Cycle — only DRAFT */}
                  {activeCycle?.status==='DRAFT' && (
                    <button type="button" disabled={!!actLoad}
                      onClick={()=>handleResetCycle(activeCycle.id,activeCycle.name)}
                      style={{padding:'6px 12px',borderRadius:6,border:'1px solid rgba(255,45,120,0.3)',
                        background:'rgba(255,45,120,0.06)',color:'#ff2d78',fontFamily:'Orbitron,sans-serif',
                        fontSize:8,cursor:'pointer',letterSpacing:0.5}}>
                      {actLoad==='Reset'?'⏳ ...':'🔄 RESET'}
                    </button>
                  )}
                  {/* Snapshot history */}
                  <button type="button" onClick={loadSnapshots}
                    style={{padding:'6px 12px',borderRadius:6,border:'1px solid rgba(168,85,247,0.2)',
                      background:'rgba(168,85,247,0.05)',color:'rgba(168,85,247,0.6)',fontFamily:'Orbitron,sans-serif',
                      fontSize:8,cursor:'pointer',letterSpacing:0.5}}>
                    📋 HISTORY
                  </button>
                </div>
              </div>

              {/* split: left rewards | right leaderboard */}
              <div className="gm-cc-split">

                {/* LEFT */}
                <div className="gm-cc-left">
                  <div className="gm-cc-prize-big">${(stats.prize||0).toLocaleString()}</div>
                  <div className="gm-cc-prize-sub">TOTAL PRIZE POOL · {lb.length} RANKED</div>

                  {/* tags */}
                  <div className="gm-cc-tags">
                    {[
                      activeCycle?.name||'Contest',
                      `×${activeCycle?.points_multiplier||'1.00'} MULT`,
                      `${lb.length} RANKED`,
                      activeCycle?.status||'ACTIVE',
                      activeCycle?.is_featured?'★ FEATURED':'STANDARD'
                    ].map(t=>(
                      <span key={t} className="gm-cc-tag">{t}</span>
                    ))}
                  </div>

                  {/* rewards table */}
                  <div className="gm-rewards-table">
                    <div className="gm-rewards-table-head">
                      <span>REWARDS</span><span>PRIZE</span><span>POINTS</span>
                    </div>
                    {rewards.length === 0 && (
                    <div style={{padding:'12px 16px',fontSize:11,color:'rgba(168,85,247,0.3)',
                      fontFamily:"Share Tech Mono,monospace",textAlign:'center',lineHeight:1.8}}>
                      No rewards yet<br/>
                      <span style={{fontSize:9}}>Use ➕ ADD REWARD to create one</span>
                    </div>
                  )}
                  {rewards.slice(0,3).map((r,i)=>(
                      <div key={r.id} className="gm-reward-row">
                        <div className="gm-reward-rank">
                          <div className="gm-reward-icon">{['🥇','🥈','🥉'][i]}</div>
                          Rank {i+1}.
                        </div>
                        <div className="gm-reward-pts">
                          +{parseFloat(r.reward_value||0).toLocaleString()}
                          <span> PTS</span>
                        </div>
                        <div className="gm-reward-usd">
                          {r.reward_type==='POINTS'?`${r.reward_type}`:`$${parseFloat(r.total_budget||0).toLocaleString()}`} <span style={{fontSize:9,color:'rgba(255,215,0,0.5)'}}>{r.reward_type}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="gm-rank-footer">
                    <div className="gm-rank-badge">
                      <span className="gm-rank-badge-icon">🏅</span>
                      <span className="gm-rank-badge-text">
                        {meEntry ? `Rank #${meEntry.rank} · ${meEntry.points?.toLocaleString()} PTS` : "Not ranked yet"}
                      </span>
                    </div>
                    <button className="gm-view-board-btn" onClick={()=>{
                        setNav("leaderboard");
                        setTimeout(()=>{
                          const el=document.getElementById('gm-section-leaderboard');
                          if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
                        },100);
                      }}>VIEW FULL BOARD ↓</button>
                  </div>
                </div>

                {/* RIGHT — leaderboard */}
                <div className="gm-cc-right" style={{display:'flex',flexDirection:'column'}}>
                  <div className="gm-lb-header">
                    <div>
                      <div className="gm-lb-prize">${(stats.prize||0).toLocaleString()}</div>
                      <div className="gm-lb-prize-sub">Total Prize Pool</div>
                    </div>
                    {/* Scope filter */}
                    <div style={{display:'flex',gap:4}}>
                      {['GLOBAL','REGIONAL','CATEGORY'].map(sc=>(
                        <button key={sc} type="button"
                          onClick={async()=>{
                            setLbScope(sc);
                            if (!activeCycle?.id) { alert('❌ No active cycle'); return; }
                            try {
                              const snap = await api.leaderboard(activeCycle.id, sc);
                              if (snap?.snapshot_data?.length) setLb(snap.snapshot_data);
                              else alert(`ℹ️ No ${sc} snapshot data yet. Generate one first.`);
                            } catch(e) { alert('❌ '+e.message); }
                          }}
                          style={{padding:'3px 8px',borderRadius:4,cursor:'pointer',
                            fontFamily:'Orbitron,sans-serif',fontSize:7,letterSpacing:0.5,
                            border:`1px solid ${lbScope===sc?'rgba(0,243,255,0.5)':'rgba(100,60,180,0.2)'}`,
                            background:lbScope===sc?'rgba(0,243,255,0.1)':'transparent',
                            color:lbScope===sc?'#00f3ff':'rgba(168,85,247,0.4)'}}>
                          {sc}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="gm-lb-entries" style={{flex:1,overflowY:'auto',maxHeight:280}}>
                    {topEntries.length===0 && (
                      <div style={{padding:'30px',textAlign:'center',color:'rgba(168,85,247,0.3)',
                        fontFamily:'Share Tech Mono,monospace',fontSize:11,lineHeight:1.8}}>
                        No leaderboard data<br/>
                        <span style={{fontSize:9,color:'rgba(168,85,247,0.2)'}}>
                          Click 📸 GLOBAL to generate snapshot
                        </span>
                      </div>
                    )}
                    {topEntries.map((e,i)=>(
                      <div key={e.user_id||i} className="gm-lb-row">
                        <div className="gm-lb-rank"><RankIcon rank={e.rank}/></div>
                        <div className="gm-lb-avatar" style={{background:avColor(e.display_name)}}>
                          {(e.display_name||'?')[0].toUpperCase()}
                        </div>
                        <div className={`gm-lb-name${e.rank<=1?' gold':''}`}>{e.display_name}</div>
                        <Delta v={e.delta_rank}/>
                        <div className="gm-lb-pts">{(e.points||0).toLocaleString()}<span> pts</span></div>
                      </div>
                    ))}
                    {/* separator */}
                    {meEntry && <>
                      <div style={{padding:'3px 16px',background:'rgba(168,85,247,0.03)',
                        borderBottom:'1px dashed rgba(168,85,247,0.1)',
                        fontFamily:'Share Tech Mono,monospace',fontSize:9,color:'rgba(168,85,247,0.3)'}}>
                        · · · rank {meEntry.rank} · · ·
                      </div>
                      <div className="gm-lb-row me">
                        <div className="gm-lb-rank"><span style={{fontSize:11,fontFamily:'Orbitron,sans-serif',color:'#ff2d78',fontWeight:700}}>#{meEntry.rank}</span></div>
                        <div className="gm-lb-avatar" style={{background:'#a855f7'}}>A</div>
                        <div className="gm-lb-name" style={{color:'#ff2d78',fontWeight:700}}>{meEntry.display_name}</div>
                        <Delta v={meEntry.delta_rank}/>
                        <div className="gm-lb-pts" style={{color:'#ff2d78'}}>{(meEntry.points||48930).toLocaleString()}<span> pts</span></div>
                      </div>
                      <div style={{padding:'4px 16px',
                        fontFamily:'Share Tech Mono,monospace',fontSize:9,color:'rgba(168,85,247,0.25)',
                        display:'flex',justifyContent:'space-between'}}>
                        <span>sank 148. cullacted</span><span>$ 188 teney</span>
                      </div>
                    </>}
                  </div>
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN */}
            <div className="gm-right-col">

              {/* TOP CONTEST REWARDS */}
              <div id="gm-section-rewards" className="gm-top-rewards">
                <div className="gm-tr-header">
                  <div className="gm-tr-title">TOP CONTEST REWARDS</div>
                  <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:9,color:'rgba(255,215,0,0.35)'}}>
                    {rewards.length ? `${rewards.length} REWARDS` : 'NO REWARDS'}
                  </span>
                </div>
                <div className="gm-tr-body">
                  <span className="gm-tr-trophy">🏆</span>
                  <div>
                    <span className="gm-tr-pts">{parseFloat(rewards[0]?.reward_value||2000).toLocaleString()}</span>
                    <span className="gm-tr-pts-label">{rewards[0]?.reward_type||"PTS"}</span>
                  </div>
                  <div className="gm-tr-usd">{rewards[0]?.reward_type||'REWARD'}</div>
                  <div className="gm-tr-name">{rewards[0]?.title||'No reward yet'}</div>
                </div>
                <div className="gm-tr-tiers">
                  {rewards.length===0 && <div style={{padding:"12px",textAlign:"center",color:"rgba(168,85,247,0.3)",fontSize:11,fontFamily:"Share Tech Mono,monospace"}}>No rewards yet</div>}
                  {rewards.slice(0,3).map((r,i)=>(
                    <div key={r.id} className="gm-tr-tier">
                      <span className="gm-tr-tier-icon">{['🥇','🥈','🥉'][i]}</span>
                      <span className="gm-tr-tier-label">Rank {r.rank_from}–{r.rank_to} {r.title}</span>
                      <span className="gm-tr-tier-value">+{parseFloat(r.reward_value||0).toLocaleString()}</span>
                      <div style={{display:'flex',gap:4,marginLeft:'auto',flexShrink:0}}>
                        <button
                          type="button"
                          onClick={(e)=>{e.stopPropagation();setEditReward(r);setShowReward(true);}}
                          style={{cursor:'pointer',fontSize:13,padding:'3px 8px',borderRadius:4,
                            background:'rgba(0,243,255,0.12)',color:'#00f3ff',
                            border:'1px solid rgba(0,243,255,0.3)',lineHeight:1}}>✏️</button>
                        <button
                          type="button"
                          onClick={(e)=>{e.stopPropagation();setDelTarget({type:'reward',id:r.id,label:r.title});}}
                          style={{cursor:'pointer',fontSize:13,padding:'3px 8px',borderRadius:4,
                            background:'rgba(255,45,120,0.12)',color:'#ff2d78',
                            border:'1px solid rgba(255,45,120,0.3)',lineHeight:1}}>🗑️</button>
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{padding:'8px 16px 14px',display:'flex',justifyContent:'center'}}>
                  <button type="button" onClick={(e)=>{e.stopPropagation();setEditReward(null);setShowReward(true);}}
                    style={{padding:'7px 18px',borderRadius:7,border:'1px solid rgba(255,215,0,0.3)',
                      background:'rgba(255,215,0,0.07)',color:'#ffd700',cursor:'pointer',
                      fontFamily:'Orbitron,sans-serif',fontSize:9,letterSpacing:1,fontWeight:700}}>
                    ➕ ADD REWARD
                  </button>
                </div>
              </div>

              {/* ACHIEVEMENT SHOWCASE (table) */}
              <div className="gm-ach-showcase">
                <div className="gm-ach-sh-header">
                  <div className="gm-ach-sh-title">ACHIEVEMENT SHOWCASE</div>
                  <button type="button" onClick={()=>setShowAward(true)}
                    style={{padding:'4px 12px',borderRadius:6,border:'1px solid rgba(255,215,0,0.3)',
                      background:'rgba(255,215,0,0.07)',color:'#ffd700',cursor:'pointer',
                      fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:1}}>
                    🏆 AWARD
                  </button>
                </div>
                <div className="gm-ach-sh-cols">
                  <span className="gm-ach-sh-col">USER</span>
                  <span className="gm-ach-sh-col">POINTS</span>
                  <span className="gm-ach-sh-col">TYPE</span>
                  <span className="gm-ach-sh-col">STATUS</span>
                </div>
                {achUsers.map((u,i)=>(
                  <div key={i} className="gm-ach-user-row">
                    <div className="gm-ach-user-info">
                      <div className="gm-ach-user-av" style={{background:u.color}}>{u.name[0]}</div>
                      <span className="gm-ach-user-name">{u.name}</span>
                    </div>
                    <span className="gm-ach-pts">{u.pts}</span>
                    <span className="gm-ach-fits">{u.type||u.fits}</span>
                    <span className={`gm-ach-badge ${u.badge==='Levied'?'levied':'latved'}`}>{u.badge}</span>
                  </div>
                ))}
              </div>

            </div>
          </div>

          {/* ── BOTTOM ROW ── */}
          <div className="gm-bottom-row">

            {/* ACHIEVEMENT SHOWCASE (badges) */}
<div id="gm-section-achievements" style={{display:"contents"}}></div>
            <div className="gm-badges-card">
              <div className="gm-badges-header">
                <div className="gm-badges-title">ACHIEVEMENT SHOWCASE</div>
                <div className="gm-badges-meta">
                  <span style={{fontSize:9,color:"rgba(168,85,247,0.3)"}}>RECENT ACHIEVEMENTS</span>
                  <X style={{width:11,height:11,color:'rgba(168,85,247,0.4)',cursor:'pointer'}}/>
                </div>
              </div>
              <div className="gm-badges-grid">
                {achievements.length===0 && <div style={{padding:"20px",textAlign:"center",color:"rgba(168,85,247,0.3)",fontSize:11,fontFamily:"Share Tech Mono,monospace",gridColumn:"1/-1"}}>No achievements yet</div>}
                {achievements.slice(badgePage*BADGES_PER_PAGE, badgePage*BADGES_PER_PAGE+BADGES_PER_PAGE).map((a,i)=>{
                  const color = BADGE_COLORS[a.achievement_type]||'#a855f7';
                  const icon  = BADGE_ICONS[a.achievement_type]||'⭐';
                  const prog  = a.progress || Math.min(100, Math.round((a.points_awarded||0)/10)) || 50;
                  return (
                    <div key={a.id} className="gm-badge-card" style={{'--badge-color':color}}>
                      <span className="gm-badge-icon">{icon}</span>
                      <div className="gm-badge-name">{(a.title||a.achievement_type||'ACHIEVEMENT').toUpperCase()}</div>
                      <div className="gm-badge-desc">{a.description||'No description'}</div>
                      <div className="gm-badge-progress-wrap">
                        <div className="gm-badge-progress-bar" style={{width:`${prog}%`}}/>
                      </div>
                      <div className="gm-badge-bottom">
                        <span className="gm-badge-progress-txt">{prog}%</span>
                        <div className="gm-badge-action">→</div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="gm-badges-footer">
                <button className="gm-page-btn"
                  disabled={badgePage===0}
                  onClick={()=>setBadgePage(p=>Math.max(0,p-1))}
                  style={{opacity:badgePage===0?0.3:1}}>← Prev</button>
                <span className="gm-page-num">
                  {badgePage+1}/{Math.ceil(achievements.length/BADGES_PER_PAGE)||1}
                </span>
                <button className="gm-page-btn"
                  disabled={(badgePage+1)*BADGES_PER_PAGE>=achievements.length}
                  onClick={()=>setBadgePage(p=>p+1)}
                  style={{opacity:(badgePage+1)*BADGES_PER_PAGE>=achievements.length?0.3:1}}>Next →</button>
              </div>
            </div>

            {/* LATEST ACHIEVEMENTS */}
            <div className="gm-latest-card">
              <div className="gm-latest-header">
                <span className="gm-latest-title">LATEST ACHIEVEMENTS</span>
                <span className="gm-view-all" onClick={()=>setNav("achievements")} style={{cursor:"pointer"}}>VIEW ALL ›</span>
              </div>
              <div className="gm-latest-list">
                {latestFeed.map((item,i)=>(
                  <div key={i} className="gm-latest-row">
                    <div className="gm-latest-av" style={{background:item.color}}>{item.user[0]}</div>
                    <div className="gm-latest-info">
                      <div className="gm-latest-name">{item.user}</div>
                      <div className="gm-latest-sub">{item.sub}</div>
                    </div>
                    <div className="gm-latest-right">
                      <div className={`gm-latest-pts ${item.pos?'pos':'neg'}`}>{item.pts}</div>
                      <div className="gm-latest-time">{item.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* ── ALL CYCLES TABLE ── */}
          {cycles.length > 0 && (
            <div id="gm-section-cycle" className="gm-contest-card" style={{marginTop:16}}>
              <div className="gm-cc-header">
                <div className="gm-cc-title">ALL CONTEST CYCLES</div>
                <div style={{display:'flex',gap:8,alignItems:'center'}}>
                  <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:10,color:'rgba(168,85,247,0.4)'}}>{cycles.length} total</span>
                  <button onClick={()=>{setEditCycle(null);setModal(true);}}
                    style={{padding:'5px 14px',borderRadius:6,border:'1px solid rgba(168,85,247,0.3)',
                      background:'rgba(168,85,247,0.1)',color:'#a855f7',cursor:'pointer',
                      fontFamily:'Orbitron,sans-serif',fontSize:9,letterSpacing:1,fontWeight:700,display:'flex',alignItems:'center',gap:5}}>
                    <span>➕</span> NEW CYCLE
                  </button>
                </div>
              </div>
              {cycles.length===0 && (
                <div style={{padding:'30px',textAlign:'center',color:'rgba(168,85,247,0.3)',
                  fontFamily:'Share Tech Mono,monospace',fontSize:11}}>
                  No contest cycles yet — click ➕ NEW CYCLE to create one
                </div>
              )}
              <table style={{width:'100%',borderCollapse:'collapse',display:cycles.length?'table':'none'}}>
                <thead>
                  <tr>
                    {['NAME','STATUS','START','END','×MULT','FEATURED','ACTIONS'].map(h=>(
                      <th key={h} style={{padding:'8px 16px',fontFamily:'Share Tech Mono,monospace',
                        fontSize:9,color:'rgba(168,85,247,0.4)',letterSpacing:1,textAlign:'left',
                        borderBottom:'1px solid rgba(100,60,220,0.12)'}}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cycles.map(c=>{
                    const SC = {ACTIVE:'#00ff88',DRAFT:'#ffd700',COMPLETED:'#00f3ff',ARCHIVED:'#4a2a6a'};
                    const col = SC[c.status]||'#4a2a6a';
                    return (
                      <tr key={c.id}
                        onMouseEnter={e=>e.currentTarget.style.background='rgba(168,85,247,0.04)'}
                        onMouseLeave={e=>e.currentTarget.style.background='transparent'}
                        style={{borderBottom:'1px solid rgba(100,60,220,0.05)',transition:'background .15s'}}>
                        <td style={{padding:'11px 16px',fontSize:13,fontWeight:700,color:'#e0d0f0'}}>{c.name}</td>
                        <td style={{padding:'11px 16px'}}>
                          <span style={{padding:'3px 10px',borderRadius:6,fontSize:9,
                            fontFamily:'Orbitron,sans-serif',fontWeight:700,
                            background:`${col}18`,color:col,border:`1px solid ${col}33`}}>
                            {c.status}
                          </span>
                        </td>
                        <td style={{padding:'11px 16px',fontSize:11,color:'rgba(180,160,255,0.5)',fontFamily:'Share Tech Mono,monospace'}}>{c.start_date?.slice(0,10)}</td>
                        <td style={{padding:'11px 16px',fontSize:11,color:'rgba(180,160,255,0.5)',fontFamily:'Share Tech Mono,monospace'}}>{c.end_date?.slice(0,10)}</td>
                        <td style={{padding:'11px 16px',fontFamily:'Orbitron,sans-serif',fontSize:12,color:'#a855f7'}}>×{c.points_multiplier}</td>
                        <td style={{padding:'11px 16px',fontSize:12,color:c.is_featured?'#ffd700':'#4a2a6a'}}>{c.is_featured?'★ Yes':'—'}</td>
                        <td style={{padding:'11px 16px'}}>
                          <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
                            {c.status==='DRAFT' && (
                              <button disabled={!!actLoad}
                                onClick={()=>doAction(api.activate,c.id,'Activate')}
                                style={{padding:'4px 10px',borderRadius:5,border:'1px solid #00ff88',
                                  background:'rgba(0,255,136,0.08)',color:'#00ff88',cursor:'pointer',
                                  fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:0.5}}>
                                ▶ Activate
                              </button>
                            )}
                            {c.status==='ACTIVE' && (
                              <button disabled={!!actLoad}
                                onClick={()=>doAction(api.complete,c.id,'Complete')}
                                style={{padding:'4px 10px',borderRadius:5,border:'1px solid #ffd700',
                                  background:'rgba(255,215,0,0.08)',color:'#ffd700',cursor:'pointer',
                                  fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:0.5}}>
                                ✓ Complete
                              </button>
                            )}
                            {c.status==='COMPLETED' && (
                              <button disabled={!!actLoad}
                                onClick={()=>doAction(api.distribute,c.id,'Distribute')}
                                style={{padding:'4px 10px',borderRadius:5,border:'1px solid #a855f7',
                                  background:'rgba(168,85,247,0.08)',color:'#a855f7',cursor:'pointer',
                                  fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:0.5}}>
                                🎁 Distribute
                              </button>
                            )}
                            {/* Edit button */}
                            <button
                              type="button"
                              onClick={(e)=>{e.stopPropagation();setEditCycle(c);setShowEdit(true);}}
                              style={{padding:'4px 10px',borderRadius:5,border:'1px solid rgba(0,243,255,0.3)',
                                background:'rgba(0,243,255,0.07)',color:'#00f3ff',cursor:'pointer',
                                fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:0.5}}>
                              ✏️ Edit
                            </button>
                            {/* Delete button — only DRAFT or ARCHIVED */}
                            {(c.status==='DRAFT'||c.status==='ARCHIVED') && (
                              <button
                                onClick={(e)=>{e.stopPropagation();setDelTarget({type:'cycle',id:c.id,label:c.name});}}
                                style={{padding:'4px 10px',borderRadius:5,border:'1px solid rgba(255,45,120,0.3)',
                                  background:'rgba(255,45,120,0.07)',color:'#ff2d78',cursor:'pointer',
                                  fontFamily:'Orbitron,sans-serif',fontSize:8,letterSpacing:0.5}}>
                                🗑️ Delete
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
