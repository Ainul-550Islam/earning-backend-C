// Subscription.jsx — 100% Control, Full CRUD
// API Base: /api/subscriptions/
// Models: SubscriptionPlan, MembershipBenefit, UserSubscription, SubscriptionPayment

import { useState, useEffect, useCallback, useRef } from "react";

// ─── API ──────────────────────────────────────────────────────────────────────
const getToken = () =>
  localStorage.getItem("adminAccessToken") ||
  localStorage.getItem("access_token") ||
  localStorage.getItem("token") || "";

const _BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace('/api','');
const api = async (path, opts = {}) => {
  const token = getToken();
  const isFormData = opts.body instanceof FormData;
  const res = await fetch(`${_BASE}/api/subscriptions${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
      ...opts.headers,
    },
    ...opts,
  });
  if (res.status === 204) return {};
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
};

// ─── DESIGN TOKENS ────────────────────────────────────────────────────────────
const C = {
  bg:       "#07070b",
  s0:       "#0c0c13",
  s1:       "#101018",
  s2:       "#161620",
  s3:       "#1c1c2a",
  border:   "rgba(255,255,255,0.055)",
  border2:  "rgba(255,255,255,0.10)",
  text:     "#eeeef5",
  sub:      "#9090b0",
  muted:    "#55556a",
  accent:   "#7c6dfa",
  accentLo: "rgba(124,109,250,0.18)",
  accentGl: "rgba(124,109,250,0.35)",
  green:    "#00dba0",
  greenLo:  "rgba(0,219,160,0.15)",
  red:      "#ff4466",
  redLo:    "rgba(255,68,102,0.15)",
  yellow:   "#f5c518",
  yellowLo: "rgba(245,197,24,0.15)",
  blue:     "#3ab8ff",
  blueLo:   "rgba(58,184,255,0.15)",
  purple:   "#c084fc",
  purpleLo: "rgba(192,132,252,0.15)",
  orange:   "#ff8c42",
  orangeLo: "rgba(255,140,66,0.15)",
};

// ─── GLOBAL STYLES ────────────────────────────────────────────────────────────
const GS = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&family=Fraunces:ital,wght@0,300;0,600;1,300;1,600&display=swap');
    *{box-sizing:border-box;margin:0;padding:0;}
    body{background:${C.bg};}
    ::-webkit-scrollbar{width:3px;height:3px;}
    ::-webkit-scrollbar-thumb{background:rgba(124,109,250,0.3);border-radius:2px;}
    input::placeholder,textarea::placeholder{color:${C.muted};}
    select option{background:${C.s1};color:${C.text};}
    @keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
    @keyframes inScale{from{opacity:0;transform:scale(0.97)}to{opacity:1;transform:scale(1)}}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.45}}
    @keyframes spin{to{transform:rotate(360deg)}}
    @keyframes shimmer{0%{background-position:-400px 0}100%{background-position:400px 0}}
    .row:hover{background:rgba(124,109,250,0.03)!important;transition:background 0.15s;}
    .hov:hover{opacity:0.78!important;}
    .inp:focus{border-color:${C.accent}!important;box-shadow:0 0 0 3px ${C.accentLo}!important;outline:none;}
    .pill:hover{border-color:rgba(124,109,250,0.45)!important;}
    .card-hov:hover{border-color:rgba(124,109,250,0.3)!important;transform:translateY(-1px);}
    .act:hover{background:rgba(255,255,255,0.07)!important;color:${C.text}!important;}
  `}</style>
);

// ─── SHARED INPUT STYLES ──────────────────────────────────────────────────────
const IS = {
  width:"100%", background:C.s2, border:`1px solid ${C.border2}`,
  borderRadius:8, padding:"9px 13px", color:C.text, fontSize:13,
  fontFamily:"'Outfit',sans-serif", transition:"all 0.2s",
};

// ─── ICONS (SVG path strings) ─────────────────────────────────────────────────
const PATHS = {
  plans:    "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  subs:     "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75 M9 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  payments: "M2 5h20v14H2z M2 10h20",
  analytics:"M18 20V10 M12 20V4 M6 20v-6",
  plus:     "M12 5v14 M5 12h14",
  edit:     "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  trash:    "M3 6h18 M19 6l-1 14H6L5 6 M8 6V4h8v2",
  eye:      "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  x:        "M18 6L6 18 M6 6l12 12",
  check:    "M20 6L9 17l-5-5",
  pause:    "M6 4h4v16H6z M14 4h4v16h-4z",
  play:     "M5 3l14 9-14 9V3z",
  stop:     "M18 6H6v12h12z",
  refresh:  "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  arrow:    "M7 16V4m0 0L3 8m4-4l4 4 M17 8v12m0 0l4-4m-4 4l-4-4",
  gift:     "M20 12v10H4V12 M2 7h20v5H2z M12 22V7 M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z",
  money:    "M12 1v22 M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  calendar: "M3 4h18v18H3z M16 2v4 M8 2v4 M3 10h18",
  tag:      "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z M7 7h.01",
  info:     "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 8h.01 M12 12v4",
  chevron:  "M6 9l6 6 6-6",
  benefit:  "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3",
  search:   "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  cancel:   "M18 6L6 18 M6 6l12 12",
  refund:   "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
};
const Ico = ({ n, s = 15, c = "currentColor" }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c}
    strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{flexShrink:0}}>
    {(PATHS[n]||"").split(" M").map((d,i)=><path key={i} d={i===0?d:"M"+d}/>)}
  </svg>
);

// ─── TOAST ────────────────────────────────────────────────────────────────────
function useToast() {
  const [t, setT] = useState(null);
  const show = (msg, type="ok") => {
    setT({ msg, type });
    setTimeout(() => setT(null), 3200);
  };
  return { toast: t, ok: (m) => show(m,"ok"), err: (m) => show(m,"err"), info: (m) => show(m,"info") };
}
const Toast = ({ t }) => {
  if (!t) return null;
  const cfg = {
    ok:   { bg:C.greenLo, border:C.green,  color:C.green,  icon:"✓" },
    err:  { bg:C.redLo,   border:C.red,    color:C.red,    icon:"✗" },
    info: { bg:C.blueLo,  border:C.blue,   color:C.blue,   icon:"ℹ" },
  }[t.type] || {};
  return (
    <div style={{position:"fixed",bottom:28,right:28,zIndex:9999,background:cfg.bg,border:`1px solid ${cfg.border}40`,
      borderRadius:12,padding:"12px 20px",color:cfg.color,fontSize:13,fontFamily:"'Outfit',sans-serif",
      animation:"in 0.3s ease",boxShadow:"0 8px 32px rgba(0,0,0,0.5)",display:"flex",alignItems:"center",gap:10,maxWidth:360}}>
      <span style={{fontWeight:700,fontSize:16}}>{cfg.icon}</span>
      <span>{t.msg}</span>
    </div>
  );
};

// ─── CONFIRM DIALOG ───────────────────────────────────────────────────────────
const Confirm = ({ msg, sub, onConfirm, onCancel, danger=true }) => (
  <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.85)",zIndex:5000,display:"flex",alignItems:"center",justifyContent:"center",padding:24}}>
    <div style={{background:C.s1,border:`1px solid ${danger?C.red+"40":C.border2}`,borderRadius:16,padding:28,maxWidth:380,width:"100%",animation:"inScale 0.2s ease",textAlign:"center"}}>
      <div style={{fontSize:38,marginBottom:14}}>{danger?"⚠️":"❓"}</div>
      <p style={{color:C.text,fontSize:15,fontWeight:600,marginBottom:8,fontFamily:"'Fraunces',serif"}}>{msg}</p>
      {sub&&<p style={{color:C.sub,fontSize:12,marginBottom:22,lineHeight:1.7}}>{sub}</p>}
      {!sub&&<div style={{marginBottom:22}}/>}
      <div style={{display:"flex",gap:10,justifyContent:"center"}}>
        <button onClick={onConfirm} style={{background:danger?C.red:C.accent,color:"#fff",border:"none",borderRadius:9,
          padding:"10px 26px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Outfit',sans-serif"}}>
          {danger?"Yes, Delete":"Confirm"}
        </button>
        <button onClick={onCancel} style={{background:C.s2,color:C.sub,border:`1px solid ${C.border}`,
          borderRadius:9,padding:"10px 20px",fontSize:13,cursor:"pointer"}}>Cancel</button>
      </div>
    </div>
  </div>
);

// ─── MODAL ────────────────────────────────────────────────────────────────────
const Modal = ({ title, subtitle, onClose, children, width=560 }) => (
  <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.82)",zIndex:4000,display:"flex",alignItems:"center",justifyContent:"center",padding:20}} onClick={onClose}>
    <div style={{background:C.s0,border:`1px solid ${C.border2}`,borderRadius:18,width:"100%",maxWidth:width,
      maxHeight:"92vh",overflow:"auto",animation:"inScale 0.22s ease"}} onClick={e=>e.stopPropagation()}>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",
        padding:"20px 24px 16px",borderBottom:`1px solid ${C.border}`,position:"sticky",top:0,background:C.s0,zIndex:1}}>
        <div>
          <h3 style={{color:C.text,fontWeight:700,fontSize:17,fontFamily:"'Fraunces',serif",letterSpacing:"-0.02em"}}>{title}</h3>
          {subtitle&&<p style={{color:C.muted,fontSize:12,marginTop:4}}>{subtitle}</p>}
        </div>
        <button onClick={onClose} className="act" style={{background:"none",border:"none",color:C.muted,
          cursor:"pointer",padding:"4px 6px",borderRadius:6,transition:"all 0.15s"}}><Ico n="x" s={17}/></button>
      </div>
      <div style={{padding:"22px 24px"}}>{children}</div>
    </div>
  </div>
);

// ─── FORM FIELD ───────────────────────────────────────────────────────────────
const FF = ({ label, required, error, hint, children }) => (
  <div>
    {label && (
      <label style={{display:"block",color:C.muted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",
        textTransform:"uppercase",marginBottom:7,fontFamily:"'JetBrains Mono',monospace"}}>
        {label}{required&&<span style={{color:C.red,marginLeft:3}}>*</span>}
      </label>
    )}
    {children}
    {error && <p style={{color:C.red,fontSize:11,marginTop:5}}>{error}</p>}
    {hint && !error && <p style={{color:C.muted,fontSize:11,marginTop:5}}>{hint}</p>}
  </div>
);

const Input = ({ value, onChange, placeholder="", type="text", ...rest }) => (
  <input className="inp" type={type} value={value??""} onChange={e=>onChange(e.target.value)}
    placeholder={placeholder} style={IS} {...rest}/>
);
const Textarea = ({ value, onChange, rows=3 }) => (
  <textarea className="inp" value={value??""} onChange={e=>onChange(e.target.value)}
    rows={rows} style={{...IS,resize:"vertical",lineHeight:1.6}}/>
);
const Select = ({ value, onChange, options, placeholder }) => (
  <select className="inp" value={value??""} onChange={e=>onChange(e.target.value)} style={IS}>
    {placeholder && <option value="">{placeholder}</option>}
    {options.map(o => (
      <option key={Array.isArray(o)?o[0]:o} value={Array.isArray(o)?o[0]:o}>
        {Array.isArray(o)?o[1]:o.replace(/_/g," ")}
      </option>
    ))}
  </select>
);
const Toggle = ({ value, onChange, label }) => (
  <label style={{display:"flex",alignItems:"center",gap:10,cursor:"pointer",userSelect:"none"}}>
    <div onClick={()=>onChange(!value)} style={{width:40,height:22,borderRadius:11,
      background:value?C.accent:C.s3,cursor:"pointer",transition:"background 0.2s",position:"relative",
      boxShadow:value?`0 0 10px ${C.accentLo}`:"",flexShrink:0}}>
      <div style={{position:"absolute",top:3,left:value?19:3,width:16,height:16,borderRadius:"50%",
        background:"#fff",transition:"left 0.2s",boxShadow:"0 1px 3px rgba(0,0,0,0.4)"}}/>
    </div>
    {label&&<span style={{color:C.sub,fontSize:13}}>{label}</span>}
  </label>
);

// ─── STATUS BADGES ────────────────────────────────────────────────────────────
const STATUS_CFG = {
  // Plan status
  active:    { color:C.green,  bg:C.greenLo,  label:"ACTIVE" },
  inactive:  { color:C.muted,  bg:"rgba(85,85,106,0.2)", label:"INACTIVE" },
  archived:  { color:C.muted,  bg:"rgba(85,85,106,0.15)",label:"ARCHIVED" },
  // Subscription status
  trialing:  { color:C.blue,   bg:C.blueLo,   label:"TRIALING" },
  past_due:  { color:C.orange, bg:C.orangeLo, label:"PAST DUE" },
  cancelled: { color:C.red,    bg:C.redLo,    label:"CANCELLED" },
  expired:   { color:C.muted,  bg:"rgba(85,85,106,0.2)", label:"EXPIRED" },
  paused:    { color:C.yellow, bg:C.yellowLo, label:"PAUSED" },
  pending:   { color:C.yellow, bg:C.yellowLo, label:"PENDING" },
  // Payment status
  succeeded: { color:C.green,  bg:C.greenLo,  label:"SUCCEEDED" },
  failed:    { color:C.red,    bg:C.redLo,    label:"FAILED" },
  refunded:  { color:C.purple, bg:C.purpleLo, label:"REFUNDED" },
  partially_refunded:{ color:C.purple, bg:C.purpleLo, label:"PARTIAL REFUND" },
  disputed:  { color:C.orange, bg:C.orangeLo, label:"DISPUTED" },
};
const Chip = ({ s, small=false }) => {
  const cfg = STATUS_CFG[s] || { color:C.sub, bg:"rgba(144,144,176,0.1)", label:s||"—" };
  return (
    <span style={{color:cfg.color,background:cfg.bg,padding:small?"1px 7px":"2px 9px",borderRadius:20,
      fontSize:small?9:10,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",
      letterSpacing:"0.08em",border:`1px solid ${cfg.color}25`,whiteSpace:"nowrap"}}>
      {cfg.label}
    </span>
  );
};

// ─── ACTION BUTTON ────────────────────────────────────────────────────────────
const AB = ({ icon, onClick, title, color=C.sub, disabled=false }) => (
  <button className="act" onClick={onClick} title={title} disabled={disabled}
    style={{background:"none",border:"none",color:disabled?C.muted:color,cursor:disabled?"not-allowed":"pointer",
      padding:"5px 7px",borderRadius:7,transition:"all 0.15s",display:"flex",alignItems:"center",opacity:disabled?0.4:1}}>
    <Ico n={icon} s={13}/>
  </button>
);

// ─── PRIMARY BUTTON ───────────────────────────────────────────────────────────
const PBtn = ({ children, onClick, disabled, loading, variant="accent", small=false }) => {
  const bg = variant==="red"?C.red:variant==="green"?C.green:variant==="outline"?"transparent":C.accent;
  const shadow = variant==="red"?C.redLo:variant==="green"?C.greenLo:C.accentLo;
  return (
    <button className="hov" onClick={onClick} disabled={disabled||loading}
      style={{background:variant==="outline"?"transparent":bg,color:variant==="outline"?C.sub:"#fff",
        border:variant==="outline"?`1px solid ${C.border2}`:"none",borderRadius:9,
        padding:small?"7px 16px":"10px 22px",fontWeight:700,fontSize:small?12:13,cursor:"pointer",
        display:"flex",alignItems:"center",gap:7,fontFamily:"'Outfit',sans-serif",
        boxShadow:variant==="outline"?"none":`0 4px 18px ${shadow}`,
        opacity:(disabled||loading)?0.55:1,transition:"opacity 0.15s",whiteSpace:"nowrap"}}>
      {loading&&<div style={{width:12,height:12,borderRadius:"50%",border:`2px solid rgba(255,255,255,0.3)`,
        borderTopColor:"#fff",animation:"spin 0.7s linear infinite"}}/>}
      {children}
    </button>
  );
};

// ─── STAT CARD ────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, sub, icon, color=C.accent, delay=0 }) => (
  <div style={{background:C.s1,border:`1px solid ${C.border}`,borderRadius:16,padding:"20px 22px",
    position:"relative",overflow:"hidden",animation:`in 0.5s ease ${delay}ms both`,
    borderTop:`2px solid ${color}`}}>
    <div style={{position:"absolute",top:-24,right:-24,width:80,height:80,borderRadius:"50%",
      background:color,opacity:0.06,pointerEvents:"none"}}/>
    <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:14}}>
      <div style={{width:30,height:30,borderRadius:9,background:`${color}18`,display:"flex",
        alignItems:"center",justifyContent:"center",color}}><Ico n={icon} s={14}/></div>
      <span style={{color:C.muted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",
        textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>{label}</span>
    </div>
    <div style={{fontSize:32,fontWeight:800,color:C.text,fontFamily:"'Fraunces',serif",
      letterSpacing:"-0.04em",lineHeight:1}}>{value}</div>
    {sub&&<div style={{color:C.muted,fontSize:11,marginTop:6}}>{sub}</div>}
  </div>
);

// ─── EMPTY STATE ──────────────────────────────────────────────────────────────
const Empty = ({ icon, title, sub }) => (
  <div style={{padding:"64px 24px",textAlign:"center",animation:"in 0.4s ease both"}}>
    <div style={{fontSize:40,marginBottom:14}}>{icon||"📭"}</div>
    <div style={{color:C.sub,fontSize:15,fontWeight:600,fontFamily:"'Fraunces',serif",marginBottom:6}}>{title}</div>
    {sub&&<div style={{color:C.muted,fontSize:12}}>{sub}</div>}
  </div>
);

// ─── LOADING SKELETON ─────────────────────────────────────────────────────────
const Skeleton = ({ rows=5 }) => (
  <div style={{padding:"8px 0"}}>
    {Array.from({length:rows}).map((_,i)=>(
      <div key={i} style={{height:52,margin:"0 0 2px",borderRadius:8,
        background:`linear-gradient(90deg,${C.s2} 25%,${C.s3} 50%,${C.s2} 75%)`,
        backgroundSize:"800px 100%",animation:`shimmer 1.4s ease infinite`,
        animationDelay:`${i*80}ms`}}/>
    ))}
  </div>
);

// ─── TABLE WRAPPER ────────────────────────────────────────────────────────────
const Table = ({ headers, children, loading, empty }) => (
  <div style={{background:C.s1,border:`1px solid ${C.border}`,borderRadius:14,overflow:"hidden"}}>
    <div style={{display:"grid",gridTemplateColumns:headers.map(h=>h.w||"1fr").join(" "),
      gap:0,padding:"10px 20px",background:C.s2,borderBottom:`1px solid ${C.border}`}}>
      {headers.map(h=>(
        <span key={h.label} style={{color:C.muted,fontSize:9,fontWeight:700,letterSpacing:"0.12em",
          textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>{h.label}</span>
      ))}
    </div>
    {loading ? <Skeleton/> : (empty ? empty : children)}
  </div>
);
const TR = ({ cols, style={} }) => (
  <div className="row" style={{display:"grid",gridTemplateColumns:cols.map(c=>c.w||"1fr").join(" "),
    gap:0,padding:"13px 20px",borderBottom:`1px solid ${C.border}`,
    alignItems:"center",animation:"in 0.3s ease both",...style}}>
    {cols.map((c,i)=><div key={i} style={{minWidth:0,...(c.style||{})}}>{c.v}</div>)}
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// PLANS TAB
// ═══════════════════════════════════════════════════════════════════════════════
const PLAN_INTERVALS = [["daily","Daily"],["weekly","Weekly"],["monthly","Monthly"],
  ["quarterly","Quarterly"],["yearly","Yearly"],["lifetime","Lifetime"]];
const PLAN_STATUS    = [["active","Active"],["inactive","Inactive"],["archived","Archived"]];
const CURRENCIES     = [["USD","USD"],["EUR","EUR"],["GBP","GBP"],["BDT","BDT"],["INR","INR"],["AUD","AUD"],["CAD","CAD"]];
const BENEFIT_TYPES  = [["feature","Feature"],["limit","Limit"],["discount","Discount"],
  ["priority","Priority"],["storage","Storage"],["api_calls","API Calls"],["support","Support"],["custom","Custom"]];

const BLANK_PLAN = {
  name:"", slug:"", description:"", status:"active",
  price:"0.00", currency:"USD", interval:"monthly", interval_count:1,
  trial_period_days:0, discount_percent:"0.00", setup_fee:"0.00",
  is_featured:false, sort_order:0, max_users:"", metadata:{},
};

function usePlans() {
  const [plans, setPlans]     = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, ok, err }    = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api("/plans/?page_size=100");
      setPlans(d.results || d || []);
    } catch(_) { setPlans([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create  = async (data)    => { try { await api("/plans/",{method:"POST",body:JSON.stringify(data)}); ok("Plan created!"); load(); } catch(e){ err(e?.name?.[0]||e?.detail||"Failed"); throw e; } };
  const update  = async (slug,d)  => { try { await api(`/plans/${slug}/`,{method:"PATCH",body:JSON.stringify(d)}); ok("Plan updated!"); load(); } catch(e){ err(e?.name?.[0]||e?.detail||"Failed"); throw e; } };
  const destroy = async (slug)    => { try { await api(`/plans/${slug}/`,{method:"DELETE"}); ok("Plan deleted"); load(); } catch(e){ err(e?.detail||"Cannot delete — has active subscribers"); throw e; } };

  return { plans, loading, toast, create, update, destroy, reload:load };
}

function useBenefits(planSlug) {
  const [benefits, setBenefits] = useState([]);
  const [loading, setLoading]   = useState(false);
  const { toast, ok, err }      = useToast();

  const load = useCallback(async () => {
    if (!planSlug) return;
    setLoading(true);
    try {
      const d = await api(`/plans/${planSlug}/`);
      setBenefits(d.benefits || []);
    } catch(_) { setBenefits([]); }
    finally { setLoading(false); }
  }, [planSlug]);

  useEffect(() => { load(); }, [load]);

  const create  = async (data)   => { try { await api("/benefits/",{method:"POST",body:JSON.stringify(data)}); ok("Benefit added"); load(); } catch(e){ err(e?.label?.[0]||e?.detail||"Failed"); throw e; } };
  const update  = async (id,d)   => { try { await api(`/benefits/${id}/`,{method:"PATCH",body:JSON.stringify(d)}); ok("Benefit updated"); load(); } catch(e){ err(e?.detail||"Failed"); throw e; } };
  const destroy = async (id)     => { try { await api(`/benefits/${id}/`,{method:"DELETE"}); ok("Removed"); load(); } catch(e){ err(e?.detail||"Failed"); } };

  return { benefits, loading, toast, create, update, destroy };
}

const PlanFormModal = ({ plan, onClose, onCreate, onUpdate }) => {
  const [form, setForm]   = useState(plan ? { ...plan } : { ...BLANK_PLAN });
  const [saving, setSave] = useState(false);
  const [errors, setErrs] = useState({});
  const s = k => v => setForm(p=>({...p,[k]:v}));

  const handleSubmit = async () => {
    const e = {};
    if (!form.name.trim()) e.name = "Name is required";
    if (!form.slug.trim()) e.slug = "Slug is required";
    if (parseFloat(form.price) < 0) e.price = "Price cannot be negative";
    if (Object.keys(e).length) { setErrs(e); return; }
    setSave(true);
    try {
      const payload = { ...form,
        price: parseFloat(form.price)||0,
        discount_percent: parseFloat(form.discount_percent)||0,
        setup_fee: parseFloat(form.setup_fee)||0,
        max_users: form.max_users ? parseInt(form.max_users) : null,
        interval_count: parseInt(form.interval_count)||1,
        trial_period_days: parseInt(form.trial_period_days)||0,
        sort_order: parseInt(form.sort_order)||0,
      };
      if (plan) await onUpdate(plan.slug, payload);
      else await onCreate(payload);
      onClose();
    } catch(_) {} finally { setSave(false); }
  };

  // Auto-generate slug from name
  const handleName = v => {
    s("name")(v);
    if (!plan) s("slug")(v.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,""));
  };

  return (
    <Modal title={plan?"Edit Plan":"Create Plan"}
      subtitle={plan?`Editing: ${plan.name}`:"Define a new subscription tier"}
      onClose={onClose} width={620}>
      <div style={{display:"grid",gap:16}}>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
          <FF label="Plan Name" required error={errors.name}>
            <Input value={form.name} onChange={handleName} placeholder="e.g. Pro"/>
          </FF>
          <FF label="Slug" required error={errors.slug} hint="URL-friendly identifier">
            <Input value={form.slug} onChange={s("slug")} placeholder="e.g. pro-monthly"/>
          </FF>
        </div>
        <FF label="Description">
          <Textarea value={form.description} onChange={s("description")} rows={2}/>
        </FF>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14}}>
          <FF label="Price" required error={errors.price}>
            <Input value={form.price} onChange={s("price")} type="number" placeholder="0.00"/>
          </FF>
          <FF label="Currency">
            <Select value={form.currency} onChange={s("currency")} options={CURRENCIES}/>
          </FF>
          <FF label="Status">
            <Select value={form.status} onChange={s("status")} options={PLAN_STATUS}/>
          </FF>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
          <FF label="Billing Interval">
            <Select value={form.interval} onChange={s("interval")} options={PLAN_INTERVALS}/>
          </FF>
          <FF label="Interval Count" hint="e.g. 3 = every 3 months">
            <Input value={form.interval_count} onChange={s("interval_count")} type="number" placeholder="1"/>
          </FF>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14}}>
          <FF label="Trial Days">
            <Input value={form.trial_period_days} onChange={s("trial_period_days")} type="number" placeholder="0"/>
          </FF>
          <FF label="Discount %" hint="0 = no discount">
            <Input value={form.discount_percent} onChange={s("discount_percent")} type="number" placeholder="0.00"/>
          </FF>
          <FF label="Setup Fee">
            <Input value={form.setup_fee} onChange={s("setup_fee")} type="number" placeholder="0.00"/>
          </FF>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
          <FF label="Max Users" hint="Leave blank = unlimited">
            <Input value={form.max_users||""} onChange={s("max_users")} type="number" placeholder="Unlimited"/>
          </FF>
          <FF label="Sort Order">
            <Input value={form.sort_order} onChange={s("sort_order")} type="number" placeholder="0"/>
          </FF>
        </div>
        <div style={{display:"flex",gap:24,padding:"4px 0"}}>
          <Toggle value={form.is_featured} onChange={s("is_featured")} label="Featured plan"/>
        </div>
        <div style={{display:"flex",gap:10,paddingTop:4,borderTop:`1px solid ${C.border}`}}>
          <PBtn onClick={handleSubmit} loading={saving}>
            {plan?"Save Changes":"Create Plan"}
          </PBtn>
          <PBtn onClick={onClose} variant="outline">Cancel</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const BenefitsModal = ({ plan, onClose }) => {
  const { benefits, loading, toast, create, update, destroy } = useBenefits(plan.slug);
  const [modal, setModal]   = useState(null); // {mode,data?}
  const [confirm, setConf]  = useState(null);
  const [form, setForm]     = useState({ benefit_type:"feature", label:"", value:"", is_highlighted:false, sort_order:0 });
  const [saving, setSave]   = useState(false);
  const s = k => v => setForm(p=>({...p,[k]:v}));

  const openCreate = () => { setForm({ benefit_type:"feature", label:"", value:"", is_highlighted:false, sort_order:0 }); setModal({mode:"create"}); };
  const openEdit   = b  => { setForm({ benefit_type:b.benefit_type, label:b.label, value:b.value||"", is_highlighted:b.is_highlighted, sort_order:b.sort_order }); setModal({mode:"edit",id:b.id}); };
  const handleSave = async () => {
    if (!form.label.trim()) return;
    setSave(true);
    try {
      if (modal.mode==="create") await create({ ...form, plan:plan.id });
      else await update(modal.id, form);
      setModal(null);
    } catch(_) {} finally { setSave(false); }
  };

  return (
    <Modal title={`Benefits — ${plan.name}`} subtitle={`${benefits.length} benefits`} onClose={onClose} width={620}>
      <Toast t={toast}/>
      {confirm && <Confirm msg="Remove this benefit?" onConfirm={confirm.fn} onCancel={()=>setConf(null)}/>}
      {modal && (
        <div style={{background:C.s2,borderRadius:12,padding:18,marginBottom:20,border:`1px solid ${C.border2}`}}>
          <p style={{color:C.sub,fontSize:12,marginBottom:14,fontWeight:600}}>
            {modal.mode==="create"?"Add Benefit":"Edit Benefit"}
          </p>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
            <FF label="Type"><Select value={form.benefit_type} onChange={s("benefit_type")} options={BENEFIT_TYPES}/></FF>
            <FF label="Sort"><Input value={form.sort_order} onChange={s("sort_order")} type="number"/></FF>
            <div style={{gridColumn:"span 2"}}>
              <FF label="Label *"><Input value={form.label} onChange={s("label")} placeholder="e.g. 10,000 API calls/month"/></FF>
            </div>
            <div style={{gridColumn:"span 2"}}>
              <FF label="Value" hint="Optional numeric or key value"><Input value={form.value} onChange={s("value")} placeholder="e.g. 10000"/></FF>
            </div>
            <Toggle value={form.is_highlighted} onChange={s("is_highlighted")} label="Highlight on pricing page"/>
          </div>
          <div style={{display:"flex",gap:8,marginTop:14}}>
            <PBtn onClick={handleSave} loading={saving} small>{modal.mode==="create"?"Add":"Update"}</PBtn>
            <PBtn onClick={()=>setModal(null)} variant="outline" small>Cancel</PBtn>
          </div>
        </div>
      )}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}>
        <span style={{color:C.muted,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>
          {benefits.length} benefit{benefits.length!==1?"s":""}
        </span>
        <PBtn onClick={openCreate} small><Ico n="plus" s={12}/>Add Benefit</PBtn>
      </div>
      {loading ? <Skeleton rows={3}/> :
       benefits.length===0 ? <Empty icon="🎁" title="No benefits" sub="Add features, limits, or perks to this plan"/> :
       benefits.map(b=>(
        <div key={b.id} className="row" style={{display:"flex",alignItems:"center",gap:12,padding:"11px 14px",
          borderRadius:9,border:`1px solid ${C.border}`,marginBottom:6,background:C.s0}}>
          <div style={{width:7,height:7,borderRadius:"50%",background:b.is_highlighted?C.yellow:C.muted,flexShrink:0}}/>
          <div style={{flex:1,minWidth:0}}>
            <div style={{color:C.text,fontSize:13,fontWeight:500}}>{b.label}</div>
            <div style={{display:"flex",gap:8,marginTop:2}}>
              <span style={{color:C.muted,fontSize:10,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase"}}>{b.benefit_type_display||b.benefit_type}</span>
              {b.value&&<span style={{color:C.accent,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{b.value}</span>}
            </div>
          </div>
          <div style={{display:"flex",gap:2}}>
            <AB icon="edit"  onClick={()=>openEdit(b)}  title="Edit"/>
            <AB icon="trash" onClick={()=>setConf({fn:()=>{destroy(b.id);setConf(null);}})} color={C.red} title="Remove"/>
          </div>
        </div>
      ))}
    </Modal>
  );
};

const PlansTab = () => {
  const { plans, loading, toast, create, update, destroy } = usePlans();
  const [modal,   setModal]   = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [bModal,  setBModal]  = useState(null);
  const [search,  setSearch]  = useState("");
  const [statusF, setStatusF] = useState("");

  const filtered = plans.filter(p=>
    (!search || p.name.toLowerCase().includes(search.toLowerCase()) || p.slug.includes(search)) &&
    (!statusF || p.status===statusF)
  );

  const H = [
    {label:"Plan",   w:"1fr"},
    {label:"Price",  w:"130px"},
    {label:"Interval",w:"110px"},
    {label:"Status", w:"110px"},
    {label:"Trial",  w:"80px"},
    {label:"Subs",   w:"70px"},
    {label:"",       w:"120px"},
  ];

  return (
    <div style={{animation:"in 0.4s ease both"}}>
      <Toast t={toast}/>
      {confirm  && <Confirm msg="Delete this plan?" sub="This cannot be undone. Plans with active subscribers cannot be deleted." onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
      {modal?.mode==="form" && <PlanFormModal plan={modal.plan} onClose={()=>setModal(null)} onCreate={create} onUpdate={update}/>}
      {bModal && <BenefitsModal plan={bModal} onClose={()=>setBModal(null)}/>}

      {/* Header */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:24}}>
        <div>
          <h2 style={{color:C.text,fontWeight:700,fontSize:22,fontFamily:"'Fraunces',serif",letterSpacing:"-0.03em"}}>Subscription Plans</h2>
          <p style={{color:C.muted,fontSize:12,marginTop:4}}>{plans.length} plans · {plans.filter(p=>p.status==="active").length} active</p>
        </div>
        <PBtn onClick={()=>setModal({mode:"form"})}><Ico n="plus" s={13}/>New Plan</PBtn>
      </div>

      {/* Filters */}
      <div style={{display:"flex",gap:10,marginBottom:18,flexWrap:"wrap",alignItems:"center"}}>
        <div style={{position:"relative",flex:"0 0 220px"}}>
          <Ico n="search" s={13} c={C.muted} style={{position:"absolute",left:10,top:"50%",transform:"translateY(-50%)"}}/>
          <input className="inp" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search plans…"
            style={{...IS,paddingLeft:32,width:"100%"}}/>
        </div>
        {["","active","inactive","archived"].map(s=>(
          <button key={s} onClick={()=>setStatusF(s)} className="pill"
            style={{background:statusF===s?`${C.accent}18`:C.s1,color:statusF===s?C.accent:C.sub,
              border:`1px solid ${statusF===s?C.accent+"50":C.border}`,borderRadius:20,
              padding:"6px 16px",fontSize:11,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace",
              fontWeight:600,letterSpacing:"0.04em",transition:"all 0.2s"}}>
            {s||"All"}
          </button>
        ))}
      </div>

      {/* Table */}
      <Table headers={H} loading={loading}
        empty={filtered.length===0?<Empty icon="⭐" title="No plans found" sub="Create your first subscription plan"/>:null}>
        {filtered.map((p,i)=>(
          <TR key={p.id} style={{animationDelay:`${i*30}ms`}} cols={[
            { v: (
              <div>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <span style={{color:C.text,fontWeight:600,fontSize:13}}>{p.name}</span>
                  {p.is_featured&&<span style={{color:C.yellow,fontSize:11,lineHeight:1}}>★</span>}
                </div>
                <div style={{color:C.muted,fontSize:11,fontFamily:"'JetBrains Mono',monospace",marginTop:2}}>{p.slug}</div>
              </div>
            )},
            { v: (
              <div>
                <span style={{color:C.text,fontWeight:700,fontSize:14,fontFamily:"'JetBrains Mono',monospace"}}>
                  {p.currency} {parseFloat(p.discounted_price||p.price).toFixed(2)}
                </span>
                {parseFloat(p.discount_percent)>0&&(
                  <div style={{color:C.muted,fontSize:10,textDecoration:"line-through"}}>
                    {p.currency} {parseFloat(p.price).toFixed(2)}
                  </div>
                )}
              </div>
            ), w:"130px"},
            { v: <span style={{color:C.sub,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{p.interval_display||p.interval}</span>, w:"110px"},
            { v: <Chip s={p.status}/>, w:"110px"},
            { v: (
              <span style={{color:p.trial_period_days>0?C.blue:C.muted,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>
                {p.trial_period_days>0?`${p.trial_period_days}d`:"—"}
              </span>
            ), w:"80px"},
            { v: <span style={{color:C.sub,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{(p.subscriptions||[]).length||"—"}</span>, w:"70px"},
            { v: (
              <div style={{display:"flex",gap:2}}>
                <AB icon="gift"  onClick={()=>setBModal(p)} title="Manage Benefits" color={C.purple}/>
                <AB icon="edit"  onClick={()=>setModal({mode:"form",plan:p})} title="Edit Plan"/>
                <AB icon="trash" onClick={()=>setConfirm({fn:()=>{destroy(p.slug);setConfirm(null);}})} title="Delete Plan" color={C.red}/>
              </div>
            ), w:"120px", style:{justifyContent:"flex-end"}},
          ]}/>
        ))}
      </Table>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// SUBSCRIPTIONS TAB
// ═══════════════════════════════════════════════════════════════════════════════
const CANCEL_REASONS = [
  ["too_expensive","Too Expensive"],["not_using","Not Using Enough"],
  ["missing_features","Missing Features"],["found_alternative","Found Alternative"],
  ["technical_issues","Technical Issues"],["customer_service","Poor Customer Service"],
  ["other","Other"],
];

function useSubscriptions() {
  const [subs, setSubs]       = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, ok, err }    = useToast();

  const load = useCallback(async (params={}) => {
    setLoading(true);
    const q = new URLSearchParams({page_size:100,...params}).toString();
    try {
      const d = await api(`/subscriptions/?${q}`);
      setSubs(d.results || d || []);
    } catch(_) { setSubs([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const subscribe   = async (data)     => { try { const r=await api("/subscriptions/subscribe/",{method:"POST",body:JSON.stringify(data)}); ok("Subscribed!"); load(); return r; } catch(e){ err(e?.plan_id?.[0]||e?.detail||"Failed"); throw e; } };
  const cancel      = async (id,data)  => { try { await api(`/subscriptions/${id}/cancel/`,{method:"POST",body:JSON.stringify(data)}); ok("Subscription cancelled"); load(); } catch(e){ err(e?.detail||"Cannot cancel"); throw e; } };
  const changePlan  = async (id,data)  => { try { await api(`/subscriptions/${id}/change-plan/`,{method:"POST",body:JSON.stringify(data)}); ok("Plan changed!"); load(); } catch(e){ err(e?.new_plan_id?.[0]||e?.detail||"Failed"); throw e; } };
  const pause       = async (id,data)  => { try { await api(`/subscriptions/${id}/pause/`,{method:"POST",body:JSON.stringify(data)}); ok("Subscription paused"); load(); } catch(e){ err(e?.detail||"Cannot pause"); throw e; } };
  const resume      = async (id)       => { try { await api(`/subscriptions/${id}/resume/`,{method:"POST"}); ok("Subscription resumed!"); load(); } catch(e){ err(e?.detail||"Cannot resume"); throw e; } };
  const destroy     = async (id)       => { try { await api(`/subscriptions/${id}/`,{method:"DELETE"}); ok("Deleted"); load(); } catch(e){ err(e?.detail||"Cannot delete"); throw e; } };

  return { subs, loading, toast, subscribe, cancel, changePlan, pause, resume, destroy, reload:load };
}

const CancelModal = ({ sub, onClose, onCancel }) => {
  const [form, setForm] = useState({ reason:"other", comment:"", at_period_end:true });
  const [saving, setSave] = useState(false);
  const s = k => v => setForm(p=>({...p,[k]:v}));
  const handleSubmit = async () => { setSave(true); try { await onCancel(sub.id, form); onClose(); } catch(_){} finally{setSave(false);} };
  return (
    <Modal title="Cancel Subscription" subtitle={`Plan: ${sub.plan?.name}`} onClose={onClose} width={480}>
      <div style={{display:"grid",gap:14}}>
        <FF label="Cancellation Reason">
          <Select value={form.reason} onChange={s("reason")} options={CANCEL_REASONS}/>
        </FF>
        <FF label="Comment (optional)">
          <Textarea value={form.comment} onChange={s("comment")} rows={3}/>
        </FF>
        <Toggle value={form.at_period_end} onChange={s("at_period_end")} label="Cancel at end of billing period (recommended)"/>
        <div style={{display:"flex",gap:10,paddingTop:4}}>
          <PBtn onClick={handleSubmit} loading={saving} variant="red">Cancel Subscription</PBtn>
          <PBtn onClick={onClose} variant="outline">Keep</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const ChangePlanModal = ({ sub, plans, onClose, onChangePlan }) => {
  const [planId, setPlanId] = useState("");
  const [saving, setSave]   = useState(false);
  const activePlans = plans.filter(p => p.status==="active" && p.id !== sub.plan?.id);
  const handleSubmit = async () => {
    if (!planId) return;
    setSave(true);
    try { await onChangePlan(sub.id, { new_plan_id:planId }); onClose(); } catch(_){} finally{setSave(false);}
  };
  return (
    <Modal title="Change Plan" subtitle={`Current: ${sub.plan?.name}`} onClose={onClose} width={420}>
      <div style={{display:"grid",gap:14}}>
        <FF label="New Plan" required>
          <Select value={planId} onChange={setPlanId} placeholder="Select a plan…"
            options={activePlans.map(p=>[p.id,`${p.name} — ${p.currency} ${p.price}/${p.interval}`])}/>
        </FF>
        <div style={{display:"flex",gap:10,paddingTop:4}}>
          <PBtn onClick={handleSubmit} loading={saving} disabled={!planId}>Confirm Change</PBtn>
          <PBtn onClick={onClose} variant="outline">Cancel</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const PauseModal = ({ sub, onClose, onPause }) => {
  const [resumeAt, setResumeAt] = useState("");
  const [saving, setSave]       = useState(false);
  const handleSubmit = async () => {
    setSave(true);
    try { await onPause(sub.id, resumeAt ? { resume_at:resumeAt } : {}); onClose(); } catch(_){} finally{setSave(false);}
  };
  return (
    <Modal title="Pause Subscription" subtitle={`Plan: ${sub.plan?.name}`} onClose={onClose} width={420}>
      <div style={{display:"grid",gap:14}}>
        <FF label="Resume At (optional)" hint="Leave blank = manual resume">
          <Input value={resumeAt} onChange={setResumeAt} type="datetime-local"/>
        </FF>
        <div style={{display:"flex",gap:10,paddingTop:4}}>
          <PBtn onClick={handleSubmit} loading={saving} variant="accent"><Ico n="pause" s={13}/>Pause</PBtn>
          <PBtn onClick={onClose} variant="outline">Cancel</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const SubscribeModal = ({ plans, onClose, onSubscribe }) => {
  const [form, setForm] = useState({ user_id:"", plan_id:"", payment_method:"credit_card", coupon_code:"" });
  const [saving, setSave] = useState(false);
  const s = k => v => setForm(p=>({...p,[k]:v}));
  const METHODS = [["credit_card","Credit Card"],["debit_card","Debit Card"],["paypal","PayPal"],
    ["stripe","Stripe"],["bank_transfer","Bank Transfer"],["bkash","bKash"],["nagad","Nagad"],
    ["rocket","Rocket"],["crypto","Crypto"],["other","Other"]];
  const activePlans = plans.filter(p=>p.status==="active");
  const handleSubmit = async () => {
    if (!form.plan_id) return;
    setSave(true);
    try { await onSubscribe({ plan_id:form.plan_id, payment_method:form.payment_method, coupon_code:form.coupon_code||undefined }); onClose(); } catch(_){} finally{setSave(false);}
  };
  return (
    <Modal title="Create Subscription" subtitle="Subscribe a user to a plan" onClose={onClose} width={460}>
      <div style={{display:"grid",gap:14}}>
        <FF label="Plan" required>
          <Select value={form.plan_id} onChange={s("plan_id")} placeholder="Select plan…"
            options={activePlans.map(p=>[p.id,`${p.name} — ${p.currency} ${parseFloat(p.price).toFixed(2)}/${p.interval}`])}/>
        </FF>
        <FF label="Payment Method">
          <Select value={form.payment_method} onChange={s("payment_method")} options={METHODS}/>
        </FF>
        <FF label="Coupon Code (optional)">
          <Input value={form.coupon_code} onChange={s("coupon_code")} placeholder="e.g. SAVE20"/>
        </FF>
        <div style={{display:"flex",gap:10,paddingTop:4}}>
          <PBtn onClick={handleSubmit} loading={saving} disabled={!form.plan_id}>Subscribe</PBtn>
          <PBtn onClick={onClose} variant="outline">Cancel</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const SubDetailModal = ({ sub, onClose }) => {
  const fields = [
    ["ID", sub.id?.slice(0,8)+"…"],
    ["Plan", sub.plan?.name],
    ["Status", <Chip s={sub.status}/>],
    ["Period Start", sub.current_period_start ? new Date(sub.current_period_start).toLocaleString() : "—"],
    ["Period End",   sub.current_period_end   ? new Date(sub.current_period_end).toLocaleString()   : "—"],
    ["Trial Start",  sub.trial_start ? new Date(sub.trial_start).toLocaleString() : "—"],
    ["Trial End",    sub.trial_end   ? new Date(sub.trial_end).toLocaleString()   : "—"],
    ["Paused At",    sub.paused_at   ? new Date(sub.paused_at).toLocaleString()   : "—"],
    ["Resumes At",   sub.pause_resumes_at ? new Date(sub.pause_resumes_at).toLocaleString() : "—"],
    ["Days Until Renewal", sub.days_until_renewal ?? "—"],
    ["Renewal Count", sub.renewal_count ?? 0],
    ["Cancel at Period End", sub.cancel_at_period_end ? "Yes" : "No"],
    ["Cancelled At", sub.cancelled_at ? new Date(sub.cancelled_at).toLocaleString() : "—"],
    ["Created", new Date(sub.created_at).toLocaleString()],
  ];
  return (
    <Modal title="Subscription Detail" onClose={onClose} width={520}>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
        {fields.map(([k,v])=>(
          <div key={k} style={{background:C.s2,borderRadius:9,padding:"11px 14px"}}>
            <div style={{color:C.muted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",marginBottom:5}}>{k}</div>
            <div style={{color:C.text,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{v||"—"}</div>
          </div>
        ))}
      </div>
    </Modal>
  );
};

const SubscriptionsTab = ({ plans }) => {
  const { subs, loading, toast, subscribe, cancel, changePlan, pause, resume, destroy } = useSubscriptions();
  const [modal,   setModal]   = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [search,  setSearch]  = useState("");
  const [statusF, setStatusF] = useState("");

  const filtered = subs.filter(s=>
    (!statusF || s.status===statusF) &&
    (!search  || s.plan?.name?.toLowerCase().includes(search.toLowerCase()) ||
                 s.id?.includes(search))
  );

  const canCancel = s => ["active","trialing","past_due","paused"].includes(s.status);
  const canPause  = s => ["active","trialing"].includes(s.status);
  const canResume = s => s.status==="paused";
  const canChange = s => ["active","trialing"].includes(s.status);

  const H = [
    {label:"User / ID",    w:"1fr"},
    {label:"Plan",         w:"150px"},
    {label:"Status",       w:"120px"},
    {label:"Period End",   w:"130px"},
    {label:"Renewals",     w:"90px"},
    {label:"Actions",      w:"150px"},
  ];

  const SUB_STATUSES = ["","active","trialing","paused","past_due","cancelled","expired","pending"];

  return (
    <div style={{animation:"in 0.4s ease both"}}>
      <Toast t={toast}/>
      {confirm && <Confirm msg={confirm.msg} sub={confirm.sub} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)} danger={confirm.danger}/>}
      {modal?.type==="subscribe" && <SubscribeModal plans={plans} onClose={()=>setModal(null)} onSubscribe={subscribe}/>}
      {modal?.type==="cancel"    && <CancelModal    sub={modal.sub}  onClose={()=>setModal(null)} onCancel={cancel}/>}
      {modal?.type==="changePlan"&& <ChangePlanModal sub={modal.sub} plans={plans} onClose={()=>setModal(null)} onChangePlan={changePlan}/>}
      {modal?.type==="pause"     && <PauseModal      sub={modal.sub} onClose={()=>setModal(null)} onPause={pause}/>}
      {modal?.type==="detail"    && <SubDetailModal  sub={modal.sub} onClose={()=>setModal(null)}/>}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:24}}>
        <div>
          <h2 style={{color:C.text,fontWeight:700,fontSize:22,fontFamily:"'Fraunces',serif",letterSpacing:"-0.03em"}}>Subscriptions</h2>
          <p style={{color:C.muted,fontSize:12,marginTop:4}}>{subs.length} total · {subs.filter(s=>s.status==="active").length} active</p>
        </div>
        <PBtn onClick={()=>setModal({type:"subscribe"})}><Ico n="plus" s={13}/>New Subscription</PBtn>
      </div>

      {/* Filters */}
      <div style={{display:"flex",gap:10,marginBottom:18,flexWrap:"wrap",alignItems:"center"}}>
        <div style={{position:"relative",flex:"0 0 220px"}}>
          <input className="inp" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by plan, ID…"
            style={{...IS,paddingLeft:12,width:"100%"}}/>
        </div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
          {SUB_STATUSES.map(s=>(
            <button key={s} onClick={()=>setStatusF(s)} className="pill"
              style={{background:statusF===s?`${C.accent}18`:C.s1,color:statusF===s?C.accent:C.sub,
                border:`1px solid ${statusF===s?C.accent+"50":C.border}`,borderRadius:20,
                padding:"5px 14px",fontSize:10,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace",
                fontWeight:600,letterSpacing:"0.04em",transition:"all 0.2s"}}>
              {s||"All"}
            </button>
          ))}
        </div>
      </div>

      <Table headers={H} loading={loading}
        empty={filtered.length===0?<Empty icon="👥" title="No subscriptions found" sub="Subscribe users to plans to see them here"/>:null}>
        {filtered.map((s,i)=>(
          <TR key={s.id} style={{animationDelay:`${i*25}ms`}} cols={[
            { v: (
              <div>
                <div style={{color:C.text,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{s.id?.slice(0,12)}…</div>
                {s.is_in_trial&&<span style={{color:C.blue,fontSize:10,fontWeight:600}}>IN TRIAL</span>}
              </div>
            )},
            { v: <span style={{color:C.sub,fontSize:13,fontWeight:500}}>{s.plan?.name||"—"}</span>, w:"150px"},
            { v: <Chip s={s.status}/>, w:"120px"},
            { v: (
              <span style={{color:s.days_until_renewal<=7&&s.days_until_renewal!=null?C.orange:C.sub,
                fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>
                {s.current_period_end ? new Date(s.current_period_end).toLocaleDateString() : "—"}
                {s.days_until_renewal!=null&&` (${s.days_until_renewal}d)`}
              </span>
            ), w:"130px"},
            { v: <span style={{color:C.muted,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{s.renewal_count||0}</span>, w:"90px"},
            { v: (
              <div style={{display:"flex",gap:2}}>
                <AB icon="eye"     onClick={()=>setModal({type:"detail",sub:s})} title="View Detail" color={C.blue}/>
                {canChange(s)&&<AB icon="arrow"   onClick={()=>setModal({type:"changePlan",sub:s})} title="Change Plan" color={C.accent}/>}
                {canPause(s) &&<AB icon="pause"   onClick={()=>setModal({type:"pause",sub:s})} title="Pause" color={C.yellow}/>}
                {canResume(s)&&<AB icon="play"    onClick={()=>setConfirm({msg:"Resume this subscription?",danger:false,fn:()=>{resume(s.id);setConfirm(null);}})} title="Resume" color={C.green}/>}
                {canCancel(s)&&<AB icon="cancel"  onClick={()=>setModal({type:"cancel",sub:s})} title="Cancel" color={C.red}/>}
                <AB icon="trash" onClick={()=>setConfirm({msg:"Delete subscription record?",sub:"This permanently removes the subscription.",fn:()=>{destroy(s.id);setConfirm(null);}})} title="Delete" color={C.red}/>
              </div>
            ), w:"150px"},
          ]}/>
        ))}
      </Table>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// PAYMENTS TAB
// ═══════════════════════════════════════════════════════════════════════════════
function usePayments() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading]   = useState(true);
  const { toast, ok, err }      = useToast();

  const load = useCallback(async (params={}) => {
    setLoading(true);
    const q = new URLSearchParams({page_size:100,...params}).toString();
    try {
      const d = await api(`/payments/?${q}`);
      setPayments(d.results || d || []);
    } catch(_) { setPayments([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const refund = async (id, amount) => {
    try {
      await api(`/payments/${id}/refund/`, { method:"POST", body:JSON.stringify(amount!=null?{amount}:{}) });
      ok(amount ? `Partial refund of ${amount} issued` : "Full refund issued");
      load();
    } catch(e) { err(e?.detail||e?.amount?.[0]||"Refund failed"); throw e; }
  };

  return { payments, loading, toast, refund, reload:load };
}

const RefundModal = ({ payment, onClose, onRefund }) => {
  const [type,   setType]   = useState("full");
  const [amount, setAmount] = useState("");
  const [saving, setSave]   = useState(false);
  const handleSubmit = async () => {
    setSave(true);
    try {
      await onRefund(payment.id, type==="partial" ? parseFloat(amount) : null);
      onClose();
    } catch(_){} finally{setSave(false);}
  };
  const maxRefund = parseFloat(payment.amount) - parseFloat(payment.amount_refunded||0);
  return (
    <Modal title="Issue Refund" subtitle={`Payment: ${payment.currency} ${payment.amount}`} onClose={onClose} width={420}>
      <div style={{display:"grid",gap:14}}>
        <div style={{display:"flex",gap:10}}>
          {["full","partial"].map(t=>(
            <button key={t} onClick={()=>setType(t)}
              style={{flex:1,padding:"10px",borderRadius:9,border:`1px solid ${type===t?C.accent+"60":C.border}`,
                background:type===t?C.accentLo:"transparent",color:type===t?C.accent:C.sub,
                cursor:"pointer",fontWeight:600,fontSize:13,fontFamily:"'Outfit',sans-serif"}}>
              {t==="full"?"Full Refund":"Partial Refund"}
            </button>
          ))}
        </div>
        {type==="full"&&(
          <div style={{background:C.s2,borderRadius:10,padding:14,textAlign:"center"}}>
            <span style={{color:C.green,fontSize:20,fontWeight:700,fontFamily:"'Fraunces',serif"}}>
              {payment.currency} {maxRefund.toFixed(2)}
            </span>
            <p style={{color:C.muted,fontSize:11,marginTop:4}}>Full available amount will be refunded</p>
          </div>
        )}
        {type==="partial"&&(
          <FF label="Refund Amount" hint={`Max: ${payment.currency} ${maxRefund.toFixed(2)}`}>
            <Input value={amount} onChange={setAmount} type="number" placeholder={maxRefund.toFixed(2)}/>
          </FF>
        )}
        <div style={{display:"flex",gap:10,paddingTop:4}}>
          <PBtn onClick={handleSubmit} loading={saving} disabled={type==="partial"&&!amount}>
            <Ico n="refund" s={13}/>Issue Refund
          </PBtn>
          <PBtn onClick={onClose} variant="outline">Cancel</PBtn>
        </div>
      </div>
    </Modal>
  );
};

const PaymentDetailModal = ({ payment, onClose }) => {
  const fields = [
    ["ID", payment.id?.slice(0,12)+"…"],
    ["Status",   <Chip s={payment.status}/>],
    ["Method",   payment.payment_method_display||payment.payment_method],
    ["Amount",   `${payment.currency} ${payment.amount}`],
    ["Net",      `${payment.currency} ${payment.net_amount}`],
    ["Refunded", `${payment.currency} ${payment.amount_refunded||"0.00"}`],
    ["Tax",      `${payment.currency} ${payment.tax_amount||"0.00"}`],
    ["Discount", `${payment.currency} ${payment.discount_amount||"0.00"}`],
    ["Transaction ID", payment.transaction_id||"—"],
    ["Paid At",  payment.paid_at ? new Date(payment.paid_at).toLocaleString() : "—"],
    ["Period",   payment.period_start ? `${new Date(payment.period_start).toLocaleDateString()} → ${new Date(payment.period_end).toLocaleDateString()}` : "—"],
    ["Failure",  payment.failure_message||"—"],
  ];
  return (
    <Modal title="Payment Detail" onClose={onClose} width={540}>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
        {fields.map(([k,v])=>(
          <div key={k} style={{background:C.s2,borderRadius:9,padding:"11px 14px"}}>
            <div style={{color:C.muted,fontSize:9,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",marginBottom:5}}>{k}</div>
            <div style={{color:C.text,fontSize:12,wordBreak:"break-all"}}>{v||"—"}</div>
          </div>
        ))}
      </div>
      {payment.invoice_url&&(
        <a href={payment.invoice_url} target="_blank" rel="noopener noreferrer"
          style={{display:"block",marginTop:14,color:C.accent,fontSize:12,textDecoration:"underline"}}>
          View Invoice ↗
        </a>
      )}
    </Modal>
  );
};

const PaymentsTab = () => {
  const { payments, loading, toast, refund } = usePayments();
  const [modal,    setModal]   = useState(null);
  const [confirm,  setConfirm] = useState(null);
  const [search,   setSearch]  = useState("");
  const [statusF,  setStatusF] = useState("");

  const filtered = payments.filter(p=>
    (!statusF || p.status===statusF) &&
    (!search  || p.transaction_id?.includes(search) ||
                 p.id?.includes(search) ||
                 p.payment_method?.includes(search))
  );

  const canRefund = p => ["succeeded"].includes(p.status) && !p.is_fully_refunded;

  const H = [
    {label:"ID / Transaction",  w:"1fr"},
    {label:"Method",            w:"130px"},
    {label:"Amount",            w:"130px"},
    {label:"Status",            w:"140px"},
    {label:"Paid At",           w:"130px"},
    {label:"Actions",           w:"100px"},
  ];

  const PAY_STATUSES = ["","pending","succeeded","failed","refunded","partially_refunded","disputed","cancelled"];
  const TOTAL_REV = payments.filter(p=>p.status==="succeeded").reduce((s,p)=>s+parseFloat(p.amount||0),0);
  const TOTAL_REFUNDED = payments.reduce((s,p)=>s+parseFloat(p.amount_refunded||0),0);

  return (
    <div style={{animation:"in 0.4s ease both"}}>
      <Toast t={toast}/>
      {confirm && <Confirm msg={confirm.msg} sub={confirm.sub} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)} danger={confirm.danger}/>}
      {modal?.type==="refund" && <RefundModal payment={modal.payment} onClose={()=>setModal(null)} onRefund={refund}/>}
      {modal?.type==="detail" && <PaymentDetailModal payment={modal.payment} onClose={()=>setModal(null)}/>}

      <div style={{marginBottom:24}}>
        <h2 style={{color:C.text,fontWeight:700,fontSize:22,fontFamily:"'Fraunces',serif",letterSpacing:"-0.03em"}}>Payments</h2>
        <p style={{color:C.muted,fontSize:12,marginTop:4}}>{payments.length} records</p>
      </div>

      {/* Revenue cards */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14,marginBottom:26}}>
        <StatCard label="Total Revenue"  value={`$${TOTAL_REV.toFixed(2)}`}       icon="money"    color={C.green}  delay={0}/>
        <StatCard label="Total Refunded" value={`$${TOTAL_REFUNDED.toFixed(2)}`}  icon="refund"   color={C.red}    delay={60}/>
        <StatCard label="Succeeded"      value={payments.filter(p=>p.status==="succeeded").length} icon="check" color={C.accent} delay={120}/>
        <StatCard label="Failed"         value={payments.filter(p=>p.status==="failed").length}    icon="cancel" color={C.orange} delay={180}/>
      </div>

      {/* Filters */}
      <div style={{display:"flex",gap:10,marginBottom:18,flexWrap:"wrap",alignItems:"center"}}>
        <input className="inp" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search ID, transaction…"
          style={{...IS,width:220}}/>
        <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
          {PAY_STATUSES.map(s=>(
            <button key={s} onClick={()=>setStatusF(s)} className="pill"
              style={{background:statusF===s?`${C.accent}18`:C.s1,color:statusF===s?C.accent:C.sub,
                border:`1px solid ${statusF===s?C.accent+"50":C.border}`,borderRadius:20,
                padding:"5px 14px",fontSize:10,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace",
                fontWeight:600,letterSpacing:"0.04em",transition:"all 0.2s"}}>
              {s||"All"}
            </button>
          ))}
        </div>
      </div>

      <Table headers={H} loading={loading}
        empty={filtered.length===0?<Empty icon="💳" title="No payments found" sub="Payment records will appear here"/>:null}>
        {filtered.map((p,i)=>(
          <TR key={p.id} style={{animationDelay:`${i*25}ms`}} cols={[
            { v: (
              <div>
                <div style={{color:C.text,fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>{p.id?.slice(0,12)}…</div>
                {p.transaction_id&&<div style={{color:C.muted,fontSize:10,fontFamily:"'JetBrains Mono',monospace",marginTop:2}}>{p.transaction_id.slice(0,20)}…</div>}
              </div>
            )},
            { v: <span style={{color:C.sub,fontSize:12}}>{p.payment_method_display||p.payment_method}</span>, w:"130px"},
            { v: (
              <div>
                <div style={{color:C.text,fontWeight:700,fontSize:13,fontFamily:"'JetBrains Mono',monospace"}}>{p.currency} {parseFloat(p.amount).toFixed(2)}</div>
                {parseFloat(p.amount_refunded||0)>0&&(
                  <div style={{color:C.red,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>-{p.currency} {parseFloat(p.amount_refunded).toFixed(2)}</div>
                )}
              </div>
            ), w:"130px"},
            { v: <Chip s={p.status}/>, w:"140px"},
            { v: <span style={{color:C.muted,fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>
                   {p.paid_at ? new Date(p.paid_at).toLocaleDateString() : "—"}
                 </span>, w:"130px"},
            { v: (
              <div style={{display:"flex",gap:2}}>
                <AB icon="eye"    onClick={()=>setModal({type:"detail",payment:p})} title="View Detail" color={C.blue}/>
                {canRefund(p)&&<AB icon="refund" onClick={()=>setModal({type:"refund",payment:p})} title="Issue Refund" color={C.purple}/>}
              </div>
            ), w:"100px"},
          ]}/>
        ))}
      </Table>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS TAB
// ═══════════════════════════════════════════════════════════════════════════════
function useAdminSummary() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api("/admin/summary/").then(setSummary).catch(()=>setSummary(null)).finally(()=>setLoading(false));
  }, []);
  return { summary, loading };
}

const AnalyticsTab = () => {
  const { summary, loading } = useAdminSummary();

  if (loading) return (
    <div style={{padding:64,textAlign:"center",color:C.muted,animation:"pulse 1.5s ease infinite"}}>Loading analytics…</div>
  );
  if (!summary) return (
    <Empty icon="📊" title="Analytics unavailable" sub="Admin access required to view dashboard summary"/>
  );

  const REV = parseFloat(summary.total_revenue||0);
  const PLAN_COLS = [
    {label:"Plan",          w:"1fr"},
    {label:"Price",         w:"120px"},
    {label:"Subscribers",   w:"120px"},
    {label:"MRR",           w:"120px"},
  ];

  return (
    <div style={{animation:"in 0.4s ease both"}}>
      <div style={{marginBottom:24}}>
        <h2 style={{color:C.text,fontWeight:700,fontSize:22,fontFamily:"'Fraunces',serif",letterSpacing:"-0.03em"}}>Analytics</h2>
        <p style={{color:C.muted,fontSize:12,marginTop:4}}>Revenue & subscriber overview</p>
      </div>

      {/* Summary Cards */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14,marginBottom:28}}>
        <StatCard label="Total Revenue"  value={`$${REV.toLocaleString("en",{minimumFractionDigits:2})}`} icon="money"    color={C.green}  delay={0}/>
        <StatCard label="Active Subs"    value={summary.active_subscriptions||0}                          icon="check"    color={C.accent} delay={60}/>
        <StatCard label="Trialing"       value={summary.trialing_subscriptions||0}                        icon="calendar" color={C.blue}   delay={120}/>
        <StatCard label="Past Due"       value={summary.past_due_subscriptions||0}                        icon="info"     color={C.orange} delay={180}/>
      </div>

      {/* Per-Plan breakdown */}
      {summary.plans?.length>0&&(
        <>
          <h3 style={{color:C.sub,fontSize:12,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",
            fontFamily:"'JetBrains Mono',monospace",marginBottom:14}}>Per-Plan Breakdown</h3>
          <Table headers={PLAN_COLS} loading={false}>
            {summary.plans.map((p,i)=>(
              <TR key={p.name} style={{animationDelay:`${i*40}ms`}} cols={[
                { v: <span style={{color:C.text,fontWeight:600,fontSize:14}}>{p.name}</span> },
                { v: <span style={{color:C.sub,fontFamily:"'JetBrains Mono',monospace",fontSize:13}}>{p.currency} {parseFloat(p.price).toFixed(2)}</span>, w:"120px"},
                { v: <span style={{color:C.accent,fontFamily:"'JetBrains Mono',monospace",fontSize:14,fontWeight:700}}>{p.subscriber_count}</span>, w:"120px"},
                { v: <span style={{color:C.green,fontFamily:"'JetBrains Mono',monospace",fontSize:13,fontWeight:600}}>
                       ${(parseFloat(p.price)*p.subscriber_count).toFixed(2)}/mo
                     </span>, w:"120px"},
              ]}/>
            ))}
          </Table>
          {/* MRR Bar chart */}
          <div style={{marginTop:20,background:C.s1,border:`1px solid ${C.border}`,borderRadius:14,padding:22}}>
            <h4 style={{color:C.muted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",marginBottom:18}}>Subscriber Distribution</h4>
            <div style={{display:"flex",flexDirection:"column",gap:12}}>
              {summary.plans.map(p=>{
                const total = summary.plans.reduce((s,x)=>s+x.subscriber_count,0)||1;
                const pct   = (p.subscriber_count/total)*100;
                return (
                  <div key={p.name}>
                    <div style={{display:"flex",justifyContent:"space-between",marginBottom:5}}>
                      <span style={{color:C.sub,fontSize:12}}>{p.name}</span>
                      <span style={{color:C.text,fontSize:12,fontFamily:"'JetBrains Mono',monospace",fontWeight:600}}>{p.subscriber_count} ({pct.toFixed(1)}%)</span>
                    </div>
                    <div style={{background:C.s3,borderRadius:3,height:6,overflow:"hidden"}}>
                      <div style={{height:"100%",width:`${pct}%`,background:`linear-gradient(90deg,${C.accent},${C.purple})`,
                        borderRadius:3,transition:"width 1s ease",animation:"in 0.8s ease both"}}/>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════
const TABS = [
  { id:"plans",       label:"Plans",         icon:"plans" },
  { id:"subs",        label:"Subscriptions", icon:"subs"  },
  { id:"payments",    label:"Payments",      icon:"payments" },
  { id:"analytics",   label:"Analytics",     icon:"analytics" },
];

export default function SubscriptionPage() {
  const [tab, setTab] = useState("plans");
  const { plans }     = usePlans();

  // Summary counts for header badges
  const activeSubs = 0; // loaded per tab

  return (
    <>
      <GS/>
      <div style={{minHeight:"100vh",background:C.bg,color:C.text,fontFamily:"'Outfit',sans-serif"}}>

        {/* ── TOP HEADER ────────────────────────────────────────────────── */}
        <div style={{background:C.s0,borderBottom:`1px solid ${C.border}`,padding:"0 36px",
          position:"sticky",top:0,zIndex:100,backdropFilter:"blur(12px)"}}>
          <div style={{display:"flex",alignItems:"center",gap:0,height:58}}>

            {/* Logo */}
            <div style={{display:"flex",alignItems:"center",gap:10,marginRight:40,flexShrink:0}}>
              <div style={{width:32,height:32,borderRadius:10,background:`linear-gradient(135deg,${C.accent},${C.purple})`,
                display:"flex",alignItems:"center",justifyContent:"center",boxShadow:`0 4px 14px ${C.accentLo}`}}>
                <Ico n="plans" s={15}/>
              </div>
              <span style={{fontSize:15,fontWeight:700,color:C.text,fontFamily:"'Fraunces',serif",letterSpacing:"-0.02em"}}>
                Subscriptions
              </span>
            </div>

            {/* Tabs */}
            <div style={{display:"flex",gap:2,height:"100%",alignItems:"center"}}>
              {TABS.map(t=>(
                <button key={t.id} onClick={()=>setTab(t.id)}
                  style={{display:"flex",alignItems:"center",gap:7,padding:"8px 16px",borderRadius:9,border:"none",
                    cursor:"pointer",fontSize:12,fontWeight:600,transition:"all 0.2s",fontFamily:"'Outfit',sans-serif",
                    background:tab===t.id?C.accentLo:"transparent",
                    color:tab===t.id?C.accent:C.muted,height:38}}>
                  <Ico n={t.icon} s={13}/>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── CONTENT ───────────────────────────────────────────────────── */}
        <div style={{maxWidth:1200,margin:"0 auto",padding:"36px 36px"}}>
          {tab==="plans"     && <PlansTab/>}
          {tab==="subs"      && <SubscriptionsTab plans={plans}/>}
          {tab==="payments"  && <PaymentsTab/>}
          {tab==="analytics" && <AnalyticsTab/>}
        </div>
      </div>
    </>
  );
}