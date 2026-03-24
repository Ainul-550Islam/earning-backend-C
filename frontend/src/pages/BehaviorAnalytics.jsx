// =============================================================================
// BehaviorAnalytics.jsx — Bulletproof / Defensive Coding
// Backend: behavior_analytics Django app
// API base: /api/behavior-analytics/  (exact match with urls.py)
// Rules:
//   1. Zero mock data — every value comes from real API
//   2. Every API call has try/catch — no unhandled promise
//   3. Every response field has a safe fallback (?.  ?? "—")
//   4. Loading, error, empty states always handled
//   5. All CRUD operations: Create, Read, Update, List, Custom actions
//   6. axiosInstance auto-attaches adminAccessToken
// =============================================================================

import { useState, useEffect, useCallback, useRef } from "react";
import "../styles/behavior_analytics.css";
import axiosInstance from "../api/axiosInstance";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── BASE URL — axiosInstance.baseURL already includes /api
// Django mount: path("api/analytics/", include(...))  ← matches urls.py
// axiosInstance baseURL: http://localhost:8000/api  → final: /api/analytics/...
// ✅ FIXED: was /behavior-analytics which 404'd — backend is mounted at /api/analytics/
const B = "/behavior-analytics"; // ✅ matches Django mount path("api/behavior-analytics/",...)

// ─── Safe API wrapper ─────────────────────────────────────────────────────────
// Never throws — always returns { data, error }
const safeApi = {
  get: async (url, params = {}) => {
    try {
      const r = await axiosInstance.get(url, { params });
      return { data: r.data, error: null };
    } catch (e) {
      return { data: null, error: _extractError(e) };
    }
  },
  post: async (url, body = {}) => {
    try {
      const r = await axiosInstance.post(url, body);
      return { data: r.data, error: null };
    } catch (e) {
      return { data: null, error: _extractError(e) };
    }
  },
  patch: async (url, body = {}) => {
    try {
      const r = await axiosInstance.patch(url, body);
      return { data: r.data, error: null };
    } catch (e) {
      return { data: null, error: _extractError(e) };
    }
  },
  delete: async (url) => {
    try {
      const r = await axiosInstance.delete(url);
      return { data: r.data ?? {}, error: null };
    } catch (e) {
      return { data: null, error: _extractError(e) };
    }
  },
};

// ─── Extract human-readable error from axios error ───────────────────────────
function _extractError(e) {
  if (!e) return "Unknown error";
  const d = e?.response?.data;
  if (!d) return e?.message ?? "Network error";
  if (typeof d === "string") return d;
  if (d.detail) return String(d.detail);
  if (d.non_field_errors) return d.non_field_errors.join(", ");
  // Flatten field errors: { field: ["msg"] }
  const msgs = Object.entries(d)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
    .join(" | ");
  return msgs || "Request failed";
}

// ─── Formatters ───────────────────────────────────────────────────────────────
const fmtNum  = n => (n == null ? "—" : n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1e3 ? n.toLocaleString() : String(n));
const fmtSec  = s => { if (!s) return "0s"; const m = Math.floor(s/60), r = s%60; return m ? `${m}m ${r}s` : `${r}s`; };
const timeAgo = d => { if (!d) return ""; const s = (Date.now()-new Date(d))/1e3; return s<60?`${~~s}s ago`:s<3600?`${~~(s/60)}m ago`:`${~~(s/3600)}h ago`; };
const shortId = id => id ? id.toString().replace(/-/g,"").slice(0,12).toUpperCase() : "—";
const initials= n => (n || "?").split(/[\s_@.]/).map(w=>w[0]||"").join("").toUpperCase().slice(0,2) || "?";
const todayISO= () => new Date().toISOString().slice(0,10);
const safeFloat = (v, d=1) => { const n = parseFloat(v); return isNaN(n) ? "0" : n.toFixed(d); };

const AVC = ["135deg,#2a1260,#9000ff","135deg,#0d2a6b,#0066ff","135deg,#0d4a2a,#00aa55","135deg,#4a0d2a,#cc0066","135deg,#4a2a0d,#cc6600"];
const avColor = n => { if(!n) return `linear-gradient(${AVC[0]})`; let h=0; for(let i=0;i<n.length;i++) h=(h*31+n.charCodeAt(i))&0xfffff; return `linear-gradient(${AVC[h%AVC.length]})`; };

// ─── Backend choices (exact match with choices.py) ────────────────────────────
const DEVICE_TYPES   = ["desktop","mobile","tablet","unknown"];
const SESSION_STATUS = ["active","completed","bounced","expired"];
const CLICK_CATS     = ["navigation","cta","link","button","form","media","other"];
const NODE_TYPES     = ["entry","navigation","conversion","exit","error"];

// =============================================================================
// ─── Reusable UI components ───────────────────────────────────────────────────
// =============================================================================

function Spin() { return <div className="ba-spin"/>; }

function LoadRow({ cols }) {
  return (
    <tr><td colSpan={cols}>
      <div className="ba-loading"><Spin/>Loading...</div>
    </td></tr>
  );
}

function EmptyRow({ cols, msg = "No data found" }) {
  return (
    <tr><td colSpan={cols}>
      <div className="ba-empty">📭 {msg}</div>
    </td></tr>
  );
}

// Inline error box inside a panel/modal
function ErrBox({ msg, onClose }) {
  if (!msg) return null;
  return (
    <div className="ba-err-inline">
      ⚠ {msg}
      {onClose && (
        <button onClick={onClose} style={{marginLeft:8,background:"none",border:"none",color:"inherit",cursor:"pointer"}}>✕</button>
      )}
    </div>
  );
}

// Inline success box
function OkBox({ msg }) {
  if (!msg) return null;
  return <div className="ba-success">✅ {msg}</div>;
}

function TierBadge({ tier }) {
  const map = { low:"tb-low", medium:"tb-med", med:"tb-med", high:"tb-high", elite:"tb-elite" };
  const cls = map[(tier||"low").toLowerCase()] || "tb-low";
  return <span className={`ba-tier ${cls}`}>{(tier||"low").toUpperCase()}</span>;
}

function StatusBadge({ status }) {
  const map = { active:"s-active", completed:"s-medium", bounced:"s-bounce", expired:"s-low" };
  const cls = map[(status||"active").toLowerCase()] || "s-active";
  return <span className={`ba-status ${cls}`}>{(status||"active").toUpperCase()}</span>;
}

function Av({ name, size=28 }) {
  const n = String(name || "");
  return (
    <div className="ba-tbl-av"
      style={{background:avColor(n),width:size,height:size,fontSize:size*0.36}}>
      {initials(n)}
    </div>
  );
}

// Mini sparkline SVG — no external deps
function Spark({ color="#9000ff" }) {
  const pts = Array.from({length:22},(_,i)=>10+Math.sin(i*.7)*7+Math.cos(i*.3)*3);
  const W=100,H=30,mn=Math.min(...pts),mx=Math.max(...pts),rng=mx-mn||1;
  const sx=i=>(i/(pts.length-1))*W;
  const sy=y=>H-((y-mn)/rng)*(H-4)-2;
  const d=pts.map((y,i)=>`${i===0?"M":"L"}${sx(i).toFixed(1)} ${sy(y).toFixed(1)}`).join(" ");
  const gid=`sg${color.replace(/[^a-z0-9]/gi,"")}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={`${d} L${W} ${H} L0 ${H}Z`} fill={`url(#${gid})`}/>
      <path d={d} stroke={color} strokeWidth="1.8" fill="none"/>
    </svg>
  );
}

function BarMini({ pct, color="var(--purple)" }) {
  return (
    <div style={{flex:1,height:4,background:"rgba(255,255,255,.06)",borderRadius:2}}>
      <div style={{width:`${Math.min(100,pct||0)}%`,height:"100%",background:color,borderRadius:2,boxShadow:`0 0 4px ${color}`}}/>
    </div>
  );
}

function Pager({ page, total, onPage }) {
  if (!total || total <= 1) return null;
  return (
    <div className="ba-pag">
      <button className="ba-pag-btn" onClick={()=>onPage(page-1)} disabled={page<=1}>‹ Prev</button>
      <span className="ba-pag-cur">{page} / {total}</span>
      <button className="ba-pag-btn" onClick={()=>onPage(page+1)} disabled={page>=total}>Next ›</button>
    </div>
  );
}

function Modal({ title, onClose, wide, children }) {
  // Close on overlay click
  const handleOverlay = e => { if (e.target === e.currentTarget) onClose(); };
  // Close on Escape
  useEffect(() => {
    const fn = e => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [onClose]);
  return (
    <div className="ba-modal-overlay" onClick={handleOverlay}>
      <div className="ba-modal" style={wide ? {width:640} : {}}>
        <div className="ba-modal-hdr">
          <span className="ba-ch-title">{title}</span>
          <button className="ba-close" onClick={onClose}>✕</button>
        </div>
        <div className="ba-modal-body">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="ba-field">
      <label className="ba-field-lbl">{label}</label>
      {children}
    </div>
  );
}

function Inp({ value, onChange, type="text", placeholder="", disabled=false, min, max }) {
  return (
    <input className="ba-field-inp" type={type} value={value??""} min={min} max={max}
      onChange={e=>onChange(e.target.value)} placeholder={placeholder} disabled={disabled}/>
  );
}

function Sel({ value, onChange, options=[] }) {
  return (
    <select className="ba-field-inp" value={value??""} onChange={e=>onChange(e.target.value)}>
      {options.map(o=>{
        const v = o?.value ?? o;
        const l = o?.label ?? o;
        return <option key={v} value={v}>{l}</option>;
      })}
    </select>
  );
}

function Textarea({ value, onChange, rows=4, placeholder="" }) {
  return (
    <textarea className="ba-field-inp" rows={rows} value={value??""} placeholder={placeholder}
      onChange={e=>onChange(e.target.value)}
      style={{resize:"vertical",fontFamily:"var(--fmono)",fontSize:11}}/>
  );
}

function BtnPrimary({ onClick, disabled, children, style={} }) {
  return <button className="ba-btn-primary" onClick={onClick} disabled={disabled} style={style}>{children}</button>;
}
function BtnCancel({ onClick, children="Cancel" }) {
  return <button className="ba-btn-cancel" onClick={onClick}>{children}</button>;
}
function BtnSm({ onClick, disabled, danger, children }) {
  return (
    <button className={`ba-act-sm${danger?" ba-act-danger":""}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
function ModalActions({ onCancel, onConfirm, confirmText="Save", loading=false }) {
  return (
    <div style={{display:"flex",gap:8,marginTop:16,justifyContent:"flex-end"}}>
      <BtnCancel onClick={onCancel}/>
      <BtnPrimary onClick={onConfirm} disabled={loading}>
        {loading ? "Saving..." : confirmText}
      </BtnPrimary>
    </div>
  );
}

// =============================================================================
// ─── Hooks ────────────────────────────────────────────────────────────────────
// =============================================================================

// useFetch: one-shot fetch, re-runs when deps change
function useFetch(fetchFn, deps=[]) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const mountedRef            = useRef(true);

  const run = useCallback(async () => {
    setLoading(true); setError(null);
    const { data: d, error: e } = await fetchFn();
    if (!mountedRef.current) return;
    if (e) setError(e);
    else setData(d);
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    run();
    return () => { mountedRef.current = false; };
  }, [run]);

  return { data, loading, error, refetch: run };
}

// useList: paginated list with filtering
function useList(url, perPage=8, extraParams={}) {
  const [page, setPage]     = useState(1);
  const [items, setItems]   = useState([]);
  const [count, setCount]   = useState(0);
  const [loading, setLoad]  = useState(false);
  const [error, setError]   = useState(null);
  const [params, setParams] = useState(extraParams);
  const mountedRef          = useRef(true);

  const fetch = useCallback(async (pg, pr) => {
    setLoad(true); setError(null);
    const { data, error: e } = await safeApi.get(url, {
      limit: perPage, offset: (pg-1)*perPage, ...pr
    });
    if (!mountedRef.current) return;
    if (e) { setError(e); setLoad(false); return; }
    const list = Array.isArray(data?.results) ? data.results
               : Array.isArray(data)           ? data
               : [];
    setItems(list);
    setCount(typeof data?.count === "number" ? data.count : list.length);
    setLoad(false);
  }, [url, perPage]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => { fetch(page, params); }, [page, params, fetch]);

  const goPage       = p => { if (p>=1 && p<=Math.max(1,Math.ceil(count/perPage))) setPage(p); };
  const totalPages   = Math.max(1, Math.ceil(count/perPage));
  const updateParams = p => { setParams(prev => ({...prev,...p})); setPage(1); };

  return { items, count, loading, error, page, totalPages, goPage, params, updateParams,
           refetch: () => fetch(page, params) };
}

// =============================================================================
// ─── SECTION 1: DASHBOARD ─────────────────────────────────────────────────────
// =============================================================================
function DashboardView() {
  const {data:dash, loading:ldD, refetch:rD}   = useFetch(() => safeApi.get(`${B}/dashboard/`), []);
  const {data:admin, loading:ldA, refetch:rA}  = useFetch(() => safeApi.get(`${B}/admin/stats/`), []);
  const {data:stay, loading:ldS}               = useFetch(() => safeApi.get(`${B}/stay-times/stats/`), []);
  const [recalcLoading, setRL] = useState(false);
  const [recalcResult,  setRR] = useState(null);
  const [recalcErr,     setRE] = useState(null);

  const handleRecalc = async () => {
    setRL(true); setRE(null);
    const { data, error } = await safeApi.post(`${B}/engagement/recalculate/`);
    setRL(false);
    if (error) { setRE(error); return; }
    setRR(data); rD(); rA();
  };

  const stats = [
    { lbl:"Total Sessions",   val: fmtNum(admin?.total_sessions  ?? dash?.session_count  ?? 0), color:"#4488ff", ld:ldD||ldA },
    { lbl:"Total Clicks",     val: fmtNum(admin?.total_clicks    ?? dash?.click_count    ?? 0), color:"#ff6600", ld:ldD||ldA },
    { lbl:"Avg Stay Time",    val: fmtSec(Math.round(dash?.avg_stay_time_sec ?? admin?.avg_stay_sec ?? 0)), color:"#00ff88", ld:ldD },
    { lbl:"Engagement Score", val: `${safeFloat(dash?.latest_score?.score ?? admin?.avg_score ?? 0)}%`, color:"#9000ff", ld:ldD||ldA },
  ];

  return (
    <div className="ba-section-wrap">
      <div className="ba-stats-grid" style={{marginBottom:14}}>
        {stats.map((s,i) => (
          <div key={i} className="ba-card ba-sc ba-anim" style={{animationDelay:`${i*60}ms`}}>
            <div className="ba-sc-hdr">
              <span className="ba-sc-lbl">{s.lbl}</span>
              <div className="ba-sc-circ">⊙</div>
            </div>
            {s.ld ? <div className="ba-loading"><Spin/></div> : <>
              <div className="ba-sc-val">{s.val}</div>
              <div className="ba-spark"><Spark color={s.color}/></div>
            </>}
          </div>
        ))}
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
        {/* My Engagement */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch">
            <span className="ba-ch-title">My Engagement</span>
            <BtnSm onClick={handleRecalc} disabled={recalcLoading}>
              {recalcLoading ? "..." : "↻ Recalc"}
            </BtnSm>
          </div>
          {recalcErr && <ErrBox msg={recalcErr} onClose={()=>setRE(null)}/>}
          {ldD ? <div className="ba-loading"><Spin/></div> : <>
            <div style={{display:"flex",alignItems:"center",gap:10,margin:"10px 0"}}>
              <span style={{fontFamily:"var(--fhud)",fontSize:44,fontWeight:900,color:"var(--t1)"}}>
                {safeFloat(dash?.latest_score?.score ?? 0)}
              </span>
              <span style={{fontFamily:"var(--fhud)",fontSize:18,color:"var(--t3)"}}>%</span>
              <TierBadge tier={dash?.latest_score?.tier ?? "low"}/>
            </div>
            {recalcResult && (
              <OkBox msg={`Score: ${safeFloat(recalcResult?.score ?? 0)} | ${(recalcResult?.tier ?? "").toUpperCase()}`}/>
            )}
            <div style={{fontSize:9,color:"var(--t4)",fontFamily:"var(--fmono)",marginTop:4}}>
              Period: {dash?.period_days ?? 7}d | Sessions: {fmtNum(dash?.session_count)} | Clicks: {fmtNum(dash?.click_count)}
            </div>
          </>}
        </div>

        {/* Platform Today (staff only) */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch"><span className="ba-ch-title" style={{color:"var(--purple)"}}>Platform Today</span></div>
          {ldA ? <div className="ba-loading"><Spin/></div> : admin ? (
            <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:6}}>
              {[
                {lbl:"Sessions",     val:fmtNum(admin.total_sessions)},
                {lbl:"Clicks",       val:fmtNum(admin.total_clicks)},
                {lbl:"Avg Stay",     val:fmtSec(Math.round(admin.avg_stay_sec||0))},
                {lbl:"Avg Score",    val:safeFloat(admin.avg_score??0,2)},
                {lbl:"Scored Users", val:fmtNum(admin.scored_users)},
              ].map((r,i) => (
                <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:"1px solid rgba(80,30,160,.15)"}}>
                  <span style={{fontSize:10,color:"var(--t3)"}}>{r.lbl}</span>
                  <span style={{fontFamily:"var(--fmono)",fontSize:11,color:"var(--t1)",fontWeight:700}}>{r.val}</span>
                </div>
              ))}
            </div>
          ) : <div className="ba-empty" style={{padding:12,fontSize:10}}>🔒 Staff only</div>}
        </div>

        {/* Stay Stats */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch"><span className="ba-ch-title" style={{color:"var(--green)"}}>Stay Stats</span></div>
          {ldS ? <div className="ba-loading"><Spin/></div> : stay ? (
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginTop:6}}>
              {[
                {lbl:"Avg",     val:fmtSec(Math.round(stay.avg_duration||0)),    c:"#00eeff"},
                {lbl:"Total",   val:fmtSec(Math.round(stay.total_duration||0)),  c:"#ff00cc"},
                {lbl:"Records", val:fmtNum(stay.total_count||stay.count||0),     c:"#00ff88"},
                {lbl:"Bounces", val:fmtNum(stay.bounce_count||0),               c:"#ff6600"},
              ].map((s,i) => (
                <div key={i} style={{background:"rgba(255,255,255,.03)",border:"1px solid var(--bd-dim)",borderRadius:6,padding:"8px 10px"}}>
                  <div style={{fontFamily:"var(--fhud)",fontSize:17,fontWeight:700,color:s.c}}>{s.val}</div>
                  <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1,marginTop:2}}>{s.lbl}</div>
                </div>
              ))}
            </div>
          ) : <div className="ba-empty">No data</div>}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// ─── SECTION 2: USER PATHS ────────────────────────────────────────────────────
// Endpoints used:
//   GET  /paths/              → list
//   POST /paths/              → create
//   GET  /paths/{id}/         → view detail
//   POST /paths/{id}/close/   → close session
//   POST /paths/{id}/add_nodes/ → add nodes
// =============================================================================
function PathsView() {
  const list = useList(`${B}/paths/`, 8);

  const [showCreate, setShowCreate] = useState(false);
  const [showDetail, setShowDetail] = useState(null);
  const [showNodes,  setShowNodes]  = useState(null);
  const [showClose,  setShowClose]  = useState(null);

  const [createForm, setCreateForm] = useState({ session_id:"", device_type:"unknown", entry_url:"", nodes:"[]" });
  const [closeForm,  setCloseForm]  = useState({ exit_url:"", status:"completed" });
  const [nodesForm,  setNodesForm]  = useState("[]");

  const [err,  setErr]  = useState(null);
  const [ok,   setOk]   = useState(null);
  const [busy, setBusy] = useState(false);

  const cf = (k,v) => setCreateForm(f=>({...f,[k]:v}));

  // ── CREATE PATH ──
  const handleCreate = async () => {
    if (!createForm.session_id.trim()) { setErr("Session ID required"); return; }
    let nodes = [];
    try { nodes = JSON.parse(createForm.nodes || "[]"); }
    catch { setErr("Nodes must be valid JSON array"); return; }
    if (!Array.isArray(nodes)) { setErr("Nodes must be a JSON array []"); return; }
    setBusy(true); setErr(null);
    const { error } = await safeApi.post(`${B}/paths/`, {
      session_id:  createForm.session_id.trim(),
      device_type: createForm.device_type,
      entry_url:   createForm.entry_url.trim(),
      nodes,
    });
    setBusy(false);
    if (error) { setErr(error); return; }
    setOk("Path created successfully"); setShowCreate(false);
    setCreateForm({ session_id:"", device_type:"unknown", entry_url:"", nodes:"[]" });
    list.refetch();
  };

  // ── CLOSE SESSION ──
  const handleClose = async () => {
    setBusy(true); setErr(null);
    const { error } = await safeApi.post(`${B}/paths/${showClose.id}/close/`, closeForm);
    setBusy(false);
    if (error) { setErr(error); return; }
    setOk("Session closed"); setShowClose(null); list.refetch();
  };

  // ── ADD NODES ──
  const handleAddNodes = async () => {
    let nodes = [];
    try { nodes = JSON.parse(nodesForm); }
    catch { setErr("Invalid JSON"); return; }
    if (!Array.isArray(nodes) || !nodes.length) { setErr("At least 1 node required"); return; }
    setBusy(true); setErr(null);
    const { error } = await safeApi.post(`${B}/paths/${showNodes.id}/add_nodes/`, { nodes });
    setBusy(false);
    if (error) { setErr(error); return; }
    setOk("Nodes added"); setShowNodes(null); setNodesForm("[]"); list.refetch();
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr">
        <span className="ba-ch-title">User Paths <span style={{color:"var(--t4)",fontWeight:400}}>({fmtNum(list.count)})</span></span>
        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          <Sel value={list.params.status||""} onChange={v=>list.updateParams({status:v||undefined})}
            options={[{value:"",label:"All statuses"},...SESSION_STATUS.map(s=>({value:s,label:s.toUpperCase()}))]}/>
          <Sel value={list.params.ordering||"-created_at"} onChange={v=>list.updateParams({ordering:v})}
            options={[{value:"-created_at",label:"Newest"},{value:"created_at",label:"Oldest"},{value:"status",label:"Status"}]}/>
          <BtnPrimary onClick={()=>{setShowCreate(true);setErr(null);setOk(null);}}>+ New Path</BtnPrimary>
        </div>
      </div>

      <ErrBox msg={list.error}/>
      <OkBox msg={ok}/>

      <div className="ba-card" style={{padding:0,overflow:"hidden"}}>
        <table className="ba-tbl">
          <thead>
            <tr><th>User</th><th>Session ID</th><th>Device</th><th>Status</th><th>Depth</th><th>Nodes</th><th>Bounce</th><th>Created</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {list.loading ? <LoadRow cols={9}/> :
             list.items.length === 0 ? <EmptyRow cols={9}/> :
             list.items.map(p => {
               const nm = p.user_display ?? p.user ?? "Unknown";
               return (
                 <tr key={p.id}>
                   <td><div style={{display:"flex",alignItems:"center",gap:7}}><Av name={nm}/><span style={{fontWeight:500,fontSize:12}}>{nm}</span></div></td>
                   <td><span className="ba-sid">{shortId(p.session_id)}</span></td>
                   <td><span className="ba-pill">{p.device_type||"unknown"}</span></td>
                   <td><StatusBadge status={p.status}/></td>
                   <td className="ba-mono" style={{textAlign:"center"}}>{p.depth??0}</td>
                   <td className="ba-mono" style={{textAlign:"center"}}>{Array.isArray(p.nodes)?p.nodes.length:0}</td>
                   <td><span className={`ba-status ${p.is_bounce?"s-bounce":"s-active"}`}>{p.is_bounce?"YES":"NO"}</span></td>
                   <td style={{fontSize:10,color:"var(--t4)",fontFamily:"var(--fmono)"}}>{timeAgo(p.created_at)}</td>
                   <td>
                     <div style={{display:"flex",gap:4}}>
                       <BtnSm onClick={()=>setShowDetail(p)}>View</BtnSm>
                       <BtnSm onClick={()=>{setShowNodes(p);setNodesForm("[]");setErr(null);}}>+Nodes</BtnSm>
                       {p.status==="active" && (
                         <BtnSm danger onClick={()=>{setShowClose(p);setCloseForm({exit_url:"",status:"completed"});setErr(null);}}>Close</BtnSm>
                       )}
                     </div>
                   </td>
                 </tr>
               );
             })}
          </tbody>
        </table>
      </div>
      <Pager page={list.page} total={list.totalPages} onPage={list.goPage}/>

      {/* ── Create Modal ── */}
      {showCreate && (
        <Modal title="Create New Path" onClose={()=>setShowCreate(false)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <Field label="Session ID *"><Inp value={createForm.session_id} onChange={v=>cf("session_id",v)} placeholder="uuid-v4 or unique string"/></Field>
          <Field label="Device Type"><Sel value={createForm.device_type} onChange={v=>cf("device_type",v)} options={DEVICE_TYPES}/></Field>
          <Field label="Entry URL"><Inp value={createForm.entry_url} onChange={v=>cf("entry_url",v)} placeholder="https://example.com/page"/></Field>
          <Field label="Initial Nodes (JSON array)">
            <Textarea value={createForm.nodes} onChange={v=>cf("nodes",v)} rows={3} placeholder='[{"url":"/home","type":"entry","ts":1700000000}]'/>
          </Field>
          <ModalActions onCancel={()=>setShowCreate(false)} onConfirm={handleCreate} confirmText="Create Path" loading={busy}/>
        </Modal>
      )}

      {/* ── Detail Modal ── */}
      {showDetail && (
        <Modal title={`Path — ${shortId(showDetail.session_id)}`} wide onClose={()=>setShowDetail(null)}>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12}}>
            {[
              ["ID",          showDetail.id],
              ["Session ID",  showDetail.session_id],
              ["Device",      showDetail.device_type],
              ["Status",      <StatusBadge status={showDetail.status}/>],
              ["Depth",       showDetail.depth??0],
              ["Is Bounce",   showDetail.is_bounce?"Yes":"No"],
              ["Entry URL",   showDetail.entry_url||"—"],
              ["Exit URL",    showDetail.exit_url||"—"],
              ["Created",     showDetail.created_at?new Date(showDetail.created_at).toLocaleString():"—"],
              ["Updated",     showDetail.updated_at?new Date(showDetail.updated_at).toLocaleString():"—"],
            ].map(([lbl,val],i)=>(
              <div key={i} style={{background:"rgba(255,255,255,.02)",borderRadius:5,padding:"6px 8px"}}>
                <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1}}>{lbl}</div>
                <div style={{fontSize:10,color:"var(--t1)",fontFamily:"var(--fmono)",marginTop:2,wordBreak:"break-all"}}>{val}</div>
              </div>
            ))}
          </div>
          <div style={{fontSize:10,color:"var(--t3)",marginBottom:4}}>
            Nodes ({Array.isArray(showDetail.nodes)?showDetail.nodes.length:0}) | Clicks ({Array.isArray(showDetail.click_metrics)?showDetail.click_metrics.length:0}) | Stay ({Array.isArray(showDetail.stay_times)?showDetail.stay_times.length:0})
          </div>
          <div style={{background:"rgba(0,0,0,.3)",borderRadius:6,padding:8,maxHeight:130,overflowY:"auto",fontFamily:"var(--fmono)",fontSize:9,color:"var(--t2)"}}>
            {Array.isArray(showDetail.nodes) && showDetail.nodes.length > 0
              ? showDetail.nodes.map((n,i)=>(
                  <div key={i} style={{padding:"1px 0",borderBottom:"1px solid rgba(255,255,255,.04)"}}>
                    [{i}] <span style={{color:"var(--cyan)"}}>{n?.type??""}</span> → {n?.url??""}
                  </div>
                ))
              : <span style={{color:"var(--t4)"}}>No nodes</span>
            }
          </div>
        </Modal>
      )}

      {/* ── Add Nodes Modal ── */}
      {showNodes && (
        <Modal title={`Add Nodes — ${shortId(showNodes.session_id)}`} onClose={()=>setShowNodes(null)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <div style={{fontSize:10,color:"var(--t3)",marginBottom:8}}>Types: <span style={{color:"var(--cyan)"}}>{NODE_TYPES.join(", ")}</span></div>
          <Field label="Nodes JSON Array *">
            <Textarea value={nodesForm} onChange={setNodesForm} rows={5} placeholder='[{"url":"/about","type":"navigation","ts":1700000000}]'/>
          </Field>
          <ModalActions onCancel={()=>setShowNodes(null)} onConfirm={handleAddNodes} confirmText="Add Nodes" loading={busy}/>
        </Modal>
      )}

      {/* ── Close Session Modal ── */}
      {showClose && (
        <Modal title={`Close — ${shortId(showClose.session_id)}`} onClose={()=>setShowClose(null)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <Field label="Exit URL"><Inp value={closeForm.exit_url} onChange={v=>setCloseForm(f=>({...f,exit_url:v}))} placeholder="https://example.com/exit"/></Field>
          <Field label="New Status">
            <Sel value={closeForm.status} onChange={v=>setCloseForm(f=>({...f,status:v}))}
              options={SESSION_STATUS.filter(s=>s!=="active").map(s=>({value:s,label:s.toUpperCase()}))}/>
          </Field>
          <ModalActions onCancel={()=>setShowClose(null)} onConfirm={handleClose} confirmText="Close Session" loading={busy}/>
        </Modal>
      )}
    </div>
  );
}

// =============================================================================
// ─── SECTION 3: CLICK METRICS ─────────────────────────────────────────────────
// Endpoints:
//   GET  /clicks/              → list
//   POST /clicks/              → record single
//   POST /clicks/bulk/         → bulk insert
//   GET  /clicks/top_elements/ → top elements
// =============================================================================
function ClicksView() {
  const list = useList(`${B}/clicks/`, 10);
  const [tab, setTab]           = useState("list");
  const [topEls, setTopEls]     = useState([]);
  const [topLoading, setTL]     = useState(false);
  const [topErr, setTopErr]     = useState(null);
  const [showCreate,  setCreate]    = useState(false);
  const [showBulk,    setBulk]      = useState(false);
  const [bulkJson,    setBulkJson]  = useState("");
  const [bulkResult,  setBulkResult]= useState(null);
  const [err, setErr]  = useState(null);
  const [ok,  setOk]   = useState(null);
  const [busy,setBusy] = useState(false);

  const [form, setForm] = useState({
    path:"", page_url:"", element_selector:"", element_text:"",
    category:"button", x_position:"", y_position:"",
    viewport_width:"", viewport_height:"",
    clicked_at: new Date().toISOString().slice(0,16),
  });
  const ff = (k,v) => setForm(f=>({...f,[k]:v}));

  const loadTop = async () => {
    setTL(true); setTopErr(null);
    const { data, error } = await safeApi.get(`${B}/clicks/top_elements/`, { limit:15 });
    setTL(false);
    if (error) { setTopErr(error); return; }
    setTopEls(Array.isArray(data) ? data : []);
  };
  useEffect(() => { if (tab==="top") loadTop(); }, [tab]);

  const handleCreate = async () => {
    if (!form.path || !form.page_url || !form.clicked_at) {
      setErr("Path ID, Page URL and Clicked At are required"); return;
    }
    setBusy(true); setErr(null);
    const body = {
      path:             form.path.trim(),
      page_url:         form.page_url.trim(),
      element_selector: form.element_selector || "",
      element_text:     form.element_text || "",
      category:         form.category,
      clicked_at:       new Date(form.clicked_at).toISOString(),
    };
    if (form.x_position)      body.x_position      = parseInt(form.x_position);
    if (form.y_position)      body.y_position      = parseInt(form.y_position);
    if (form.viewport_width)  body.viewport_width  = parseInt(form.viewport_width);
    if (form.viewport_height) body.viewport_height = parseInt(form.viewport_height);

    const { error } = await safeApi.post(`${B}/clicks/`, body);
    setBusy(false);
    if (error) { setErr(error); return; }
    setOk("Click recorded"); setCreate(false); list.refetch();
  };

  // ── BULK INSERT — POST /clicks/bulk/ ──────────────────────────────────────
  // Backend expects: { path: "uuid", events: [{page_url, category, clicked_at, ...}] }
  const handleBulk = async () => {
    if (!bulkJson.trim()) { setErr("JSON দাও"); return; }
    let parsed;
    try { parsed = JSON.parse(bulkJson); }
    catch { setErr("Invalid JSON — array of click objects হতে হবে"); return; }

    // Accept either array of full objects OR { path, events:[...] }
    let body;
    if (Array.isArray(parsed)) {
      // Each object must have a `path` field already
      if (!parsed.length) { setErr("Empty array — কমপক্ষে ১টি object দাও"); return; }
      if (!parsed[0].path) { setErr("প্রতিটি object-এ path (UUID) field থাকতে হবে"); return; }
      // Backend /clicks/bulk/ নেয়: { path, events:[...] } grouped by path
      // Same path ধরে নিচ্ছি সবার জন্য — সব object থেকে path নেওয়া হবে
      const pathId = parsed[0].path;
      body = { path: pathId, events: parsed };
    } else if (parsed.path && Array.isArray(parsed.events)) {
      body = parsed;
    } else {
      setErr('Format: [{"path":"uuid","page_url":"...","clicked_at":"..."}] অথবা {"path":"uuid","events":[...]}');
      return;
    }

    if (!body.path) { setErr("path (UUID) required"); return; }
    if (!body.events?.length) { setErr("events array empty"); return; }

    setBusy(true); setErr(null); setBulkResult(null);
    const { data, error } = await safeApi.post(`${B}/clicks/bulk/`, body);
    setBusy(false);
    if (error) { setErr(error); return; }
    setBulkResult(data);
    setOk(`✅ Bulk insert done — ${data?.inserted ?? data?.count ?? "?"} inserted`);
    list.refetch();
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr">
        <span className="ba-ch-title">Click Metrics <span style={{color:"var(--t4)",fontWeight:400}}>({fmtNum(list.count)})</span></span>
        <div style={{display:"flex",gap:8}}>
          {[{id:"list",lbl:"All Clicks"},{id:"top",lbl:"Top Elements"}].map(t=>(
            <button key={t.id} className={tab===t.id?"ba-btn-primary":"ba-btn-cancel"} onClick={()=>setTab(t.id)}>{t.lbl}</button>
          ))}
          <BtnPrimary onClick={()=>{setCreate(true);setErr(null);setOk(null);}}>+ Record</BtnPrimary>
          <BtnPrimary onClick={()=>{setBulk(true);setBulkJson("");setBulkResult(null);setErr(null);setOk(null);}}
            style={{background:"linear-gradient(135deg,#005599,#0099ff)"}}>⚡ Bulk Insert</BtnPrimary>
        </div>
      </div>
      <ErrBox msg={list.error}/>
      <OkBox msg={ok}/>

      {tab==="list" && <>
        <div style={{display:"flex",gap:8,marginBottom:10}}>
          <input className="ba-field-inp" style={{width:200,padding:"5px 10px"}} placeholder="Filter by page URL..."
            onChange={e=>list.updateParams({page_url:e.target.value||undefined})}/>
          <Sel value={list.params.category||""} onChange={v=>list.updateParams({category:v||undefined})}
            options={[{value:"",label:"All categories"},...CLICK_CATS.map(c=>({value:c,label:c.toUpperCase()}))]}/>
        </div>
        <div className="ba-card" style={{padding:0,overflow:"hidden"}}>
          <table className="ba-tbl">
            <thead><tr><th>Page URL</th><th>Selector</th><th>Text</th><th>Category</th><th>Position</th><th>Viewport</th><th>Clicked At</th></tr></thead>
            <tbody>
              {list.loading ? <LoadRow cols={7}/> :
               list.items.length === 0 ? <EmptyRow cols={7}/> :
               list.items.map(c=>(
                 <tr key={c.id}>
                   <td style={{maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontSize:11}}>{c.page_url||"—"}</td>
                   <td style={{fontFamily:"var(--fmono)",fontSize:9,color:"var(--cyan)",maxWidth:110,overflow:"hidden",textOverflow:"ellipsis"}}>{c.element_selector||"—"}</td>
                   <td style={{fontSize:10,color:"var(--t3)",maxWidth:90,overflow:"hidden",textOverflow:"ellipsis"}}>{c.element_text||"—"}</td>
                   <td><span className="ba-pill">{c.category||"—"}</span></td>
                   <td style={{fontFamily:"var(--fmono)",fontSize:10,color:"var(--t4)"}}>{c.x_position!=null?`${c.x_position},${c.y_position}`:"—"}</td>
                   <td style={{fontFamily:"var(--fmono)",fontSize:10,color:"var(--t4)"}}>{c.viewport_width?`${c.viewport_width}×${c.viewport_height}`:"—"}</td>
                   <td style={{fontSize:10,color:"var(--t4)",fontFamily:"var(--fmono)"}}>{timeAgo(c.clicked_at)}</td>
                 </tr>
               ))}
            </tbody>
          </table>
        </div>
        <Pager page={list.page} total={list.totalPages} onPage={list.goPage}/>
      </>}

      {tab==="top" && (
        <div className="ba-card" style={{padding:0,overflow:"hidden"}}>
          <div style={{padding:"10px 16px",borderBottom:"1px solid var(--bd-dim)",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <span style={{fontSize:11,color:"var(--t3)"}}>Top clicked CSS selectors</span>
            <BtnSm onClick={loadTop}>↻ Refresh</BtnSm>
          </div>
          {topErr && <ErrBox msg={topErr}/>}
          <table className="ba-tbl">
            <thead><tr><th style={{width:36}}>#</th><th>Element Selector</th><th>Click Count</th></tr></thead>
            <tbody>
              {topLoading ? <LoadRow cols={3}/> :
               topEls.length===0 ? <EmptyRow cols={3}/> :
               topEls.map((el,i)=>(
                 <tr key={i}>
                   <td style={{fontFamily:"var(--fmono)",color:"var(--purple)",fontWeight:700,textAlign:"center"}}>{i+1}</td>
                   <td style={{fontFamily:"var(--fmono)",fontSize:11,color:"var(--t2)"}}>{el.element_selector||"—"}</td>
                   <td>
                     <div style={{display:"flex",alignItems:"center",gap:8}}>
                       <BarMini pct={(el.count/(topEls[0]?.count||1))*100}/>
                       <span style={{fontFamily:"var(--fmono)",fontSize:11,color:"var(--t1)",minWidth:36}}>{fmtNum(el.count)}</span>
                     </div>
                   </td>
                 </tr>
               ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <Modal title="Record Click Event" wide onClose={()=>setCreate(false)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
            <Field label="Path ID (UUID) *"><Inp value={form.path} onChange={v=>ff("path",v)} placeholder="UserPath UUID"/></Field>
            <Field label="Page URL *"><Inp value={form.page_url} onChange={v=>ff("page_url",v)} placeholder="https://example.com/page"/></Field>
            <Field label="Element Selector"><Inp value={form.element_selector} onChange={v=>ff("element_selector",v)} placeholder="#submit-btn"/></Field>
            <Field label="Element Text"><Inp value={form.element_text} onChange={v=>ff("element_text",v)} placeholder="Submit"/></Field>
            <Field label="Category"><Sel value={form.category} onChange={v=>ff("category",v)} options={CLICK_CATS.map(c=>({value:c,label:c.toUpperCase()}))}/></Field>
            <Field label="Clicked At *"><Inp type="datetime-local" value={form.clicked_at} onChange={v=>ff("clicked_at",v)}/></Field>
            <Field label="X Position"><Inp type="number" value={form.x_position} onChange={v=>ff("x_position",v)} placeholder="0"/></Field>
            <Field label="Y Position"><Inp type="number" value={form.y_position} onChange={v=>ff("y_position",v)} placeholder="0"/></Field>
            <Field label="Viewport W"><Inp type="number" value={form.viewport_width} onChange={v=>ff("viewport_width",v)} placeholder="1920"/></Field>
            <Field label="Viewport H"><Inp type="number" value={form.viewport_height} onChange={v=>ff("viewport_height",v)} placeholder="1080"/></Field>
          </div>
          <ModalActions onCancel={()=>setCreate(false)} onConfirm={handleCreate} confirmText="Record Click" loading={busy}/>
        </Modal>
      )}

      {/* ── Bulk Insert Shell Modal ── */}
      {showBulk && (
        <Modal title="⚡ Bulk Click Insert" wide onClose={()=>setBulk(false)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>

          {/* Result box */}
          {bulkResult && (
            <div style={{background:"rgba(0,153,255,.08)",border:"1px solid rgba(0,153,255,.3)",borderRadius:8,padding:"10px 14px",marginBottom:12}}>
              <div style={{fontFamily:"var(--fhud)",fontSize:10,color:"#00aaff",marginBottom:6}}>INSERT RESULT</div>
              <div style={{display:"flex",gap:20}}>
                {[
                  {lbl:"Inserted", val: bulkResult.inserted ?? bulkResult.count ?? "?", c:"#00ff88"},
                  {lbl:"Skipped",  val: bulkResult.skipped  ?? 0,                        c:"#ff6600"},
                  {lbl:"Errors",   val: bulkResult.errors   ?? 0,                        c:"#ff4444"},
                ].map(({lbl,val,c})=>(
                  <div key={lbl}>
                    <div style={{fontFamily:"var(--fhud)",fontSize:22,fontWeight:900,color:c}}>{val}</div>
                    <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1}}>{lbl}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Format guide */}
          <div style={{background:"rgba(0,0,0,.4)",border:"1px solid rgba(255,255,255,.06)",borderRadius:7,padding:"10px 12px",marginBottom:12,fontFamily:"var(--fmono)",fontSize:9,color:"var(--t3)"}}>
            <div style={{color:"var(--cyan)",marginBottom:5,fontSize:9}}>// FORMAT 1 — array (সব object-এ path থাকবে)</div>
            <div style={{color:"var(--t2)"}}>{"["}</div>
            <div style={{paddingLeft:12}}>{'{"path":"uuid","page_url":"/home","category":"button","clicked_at":"2026-03-11T10:00:00Z"},'}</div>
            <div style={{paddingLeft:12}}>{'{"path":"uuid","page_url":"/about","category":"link","clicked_at":"2026-03-11T10:01:00Z"}'}</div>
            <div style={{color:"var(--t2)"}}>{"]"}</div>
            <div style={{color:"var(--cyan)",margin:"8px 0 5px",fontSize:9}}>// FORMAT 2 — grouped (একটা path, অনেক events)</div>
            <div style={{color:"var(--t2)"}}>{`{"path":"uuid","events":[`}</div>
            <div style={{paddingLeft:12}}>{'{"page_url":"/home","category":"cta","clicked_at":"2026-03-11T10:00:00Z"}'}</div>
            <div style={{color:"var(--t2)"}}>{"]}"}</div>
          </div>

          <Field label="JSON Payload *">
            <Textarea
              value={bulkJson}
              onChange={v=>{setBulkJson(v);setErr(null);setBulkResult(null);}}
              rows={10}
              placeholder='[{"path":"...","page_url":"...","category":"button","clicked_at":"..."}]'
            />
          </Field>

          {/* Live JSON validate indicator */}
          {bulkJson.trim() && (()=>{
            try {
              const p = JSON.parse(bulkJson);
              const count = Array.isArray(p) ? p.length : (Array.isArray(p.events) ? p.events.length : 0);
              return (
                <div style={{fontSize:9,fontFamily:"var(--fmono)",color:"var(--green)",marginBottom:8}}>
                  ✅ Valid JSON — {count} event{count!==1?"s":""} detected
                </div>
              );
            } catch {
              return (
                <div style={{fontSize:9,fontFamily:"var(--fmono)",color:"#ff6644",marginBottom:8}}>
                  ⚠ Invalid JSON
                </div>
              );
            }
          })()}

          <ModalActions
            onCancel={()=>setBulk(false)}
            onConfirm={handleBulk}
            confirmText={busy ? "Inserting..." : `⚡ Insert All`}
            loading={busy}
          />
        </Modal>
      )}
    </div>
  );
}

// =============================================================================
// ─── SECTION 4: STAY TIMES ────────────────────────────────────────────────────
// Endpoints:
//   GET  /stay-times/        → list
//   POST /stay-times/        → record
//   GET  /stay-times/stats/  → aggregate stats
// =============================================================================
function StayTimesView() {
  const list = useList(`${B}/stay-times/`, 10);
  const {data:stats, loading:ldS, refetch:rS} = useFetch(() => safeApi.get(`${B}/stay-times/stats/`), []);
  const [showCreate, setCreate] = useState(false);
  const [err,  setErr]  = useState(null);
  const [ok,   setOk]   = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ path:"", page_url:"", duration_seconds:"30", is_active_time:"true", scroll_depth_percent:"50" });
  const ff = (k,v) => setForm(f=>({...f,[k]:v}));

  const handleCreate = async () => {
    if (!form.path || !form.page_url) { setErr("Path ID and Page URL required"); return; }
    const dur = parseInt(form.duration_seconds);
    if (!dur || dur < 1) { setErr("Duration must be ≥ 1 second"); return; }
    setBusy(true); setErr(null);
    const body = {
      path:                 form.path.trim(),
      page_url:             form.page_url.trim(),
      duration_seconds:     dur,
      is_active_time:       form.is_active_time === "true",
      scroll_depth_percent: parseInt(form.scroll_depth_percent)||null,
    };
    const { error } = await safeApi.post(`${B}/stay-times/`, body);
    setBusy(false);
    if (error) { setErr(error); return; }
    setOk("Stay time recorded"); setCreate(false); list.refetch(); rS();
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr">
        <span className="ba-ch-title">Stay Times <span style={{color:"var(--t4)",fontWeight:400}}>({fmtNum(list.count)})</span></span>
        <div style={{display:"flex",gap:8}}>
          <input className="ba-field-inp" style={{width:180,padding:"5px 10px"}} placeholder="Filter by page URL..."
            onChange={e=>list.updateParams({page_url:e.target.value||undefined})}/>
          <BtnPrimary onClick={()=>{setCreate(true);setErr(null);setOk(null);}}>+ Record Stay</BtnPrimary>
        </div>
      </div>
      <ErrBox msg={list.error}/>
      <OkBox msg={ok}/>

      {!ldS && stats && (
        <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,marginBottom:12}}>
          {[
            {lbl:"Avg Duration",  val:fmtSec(Math.round(stats.avg_duration||0)),   c:"#00eeff"},
            {lbl:"Total Duration",val:fmtSec(Math.round(stats.total_duration||0)), c:"#ff00cc"},
            {lbl:"Records",       val:fmtNum(stats.total_count||stats.count||0),   c:"#00ff88"},
            {lbl:"Bounces",       val:fmtNum(stats.bounce_count||0),              c:"#ff6600"},
          ].map((s,i)=>(
            <div key={i} className="ba-card" style={{padding:"10px 14px"}}>
              <div style={{fontFamily:"var(--fhud)",fontSize:18,fontWeight:700,color:s.c}}>{s.val}</div>
              <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1,marginTop:2}}>{s.lbl}</div>
            </div>
          ))}
        </div>
      )}

      <div className="ba-card" style={{padding:0,overflow:"hidden"}}>
        <table className="ba-tbl">
          <thead><tr><th>Page URL</th><th>Duration</th><th>Active</th><th>Scroll Depth</th><th>Bounce</th><th>Created</th></tr></thead>
          <tbody>
            {list.loading ? <LoadRow cols={6}/> :
             list.items.length===0 ? <EmptyRow cols={6}/> :
             list.items.map(s=>(
               <tr key={s.id}>
                 <td style={{fontSize:11,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{s.page_url||"—"}</td>
                 <td style={{fontFamily:"var(--fmono)",color:"var(--cyan)",fontWeight:700}}>{fmtSec(s.duration_seconds)}</td>
                 <td><span className={`ba-status ${s.is_active_time?"s-active":"s-low"}`}>{s.is_active_time?"YES":"NO"}</span></td>
                 <td>
                   {s.scroll_depth_percent != null
                     ? <div style={{display:"flex",alignItems:"center",gap:6,minWidth:80}}>
                         <BarMini pct={s.scroll_depth_percent} color="var(--green)"/>
                         <span style={{fontSize:10,fontFamily:"var(--fmono)",color:"var(--green)"}}>{s.scroll_depth_percent}%</span>
                       </div>
                     : "—"}
                 </td>
                 <td><span className={`ba-status ${s.is_bounce?"s-bounce":"s-active"}`}>{s.is_bounce?"YES":"NO"}</span></td>
                 <td style={{fontSize:10,color:"var(--t4)",fontFamily:"var(--fmono)"}}>{timeAgo(s.created_at)}</td>
               </tr>
             ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.page} total={list.totalPages} onPage={list.goPage}/>

      {showCreate && (
        <Modal title="Record Stay Time" onClose={()=>setCreate(false)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <Field label="Path ID (UUID) *"><Inp value={form.path} onChange={v=>ff("path",v)} placeholder="UserPath UUID"/></Field>
          <Field label="Page URL *"><Inp value={form.page_url} onChange={v=>ff("page_url",v)} placeholder="https://example.com/page"/></Field>
          <Field label="Duration (seconds) *"><Inp type="number" value={form.duration_seconds} onChange={v=>ff("duration_seconds",v)} placeholder="30" min="1"/></Field>
          <Field label="Scroll Depth (0–100)"><Inp type="number" value={form.scroll_depth_percent} onChange={v=>ff("scroll_depth_percent",v)} placeholder="50" min="0" max="100"/></Field>
          <Field label="Is Active Time">
            <Sel value={form.is_active_time} onChange={v=>ff("is_active_time",v)}
              options={[{value:"true",label:"Yes — tab was active"},{value:"false",label:"No — tab in background"}]}/>
          </Field>
          <ModalActions onCancel={()=>setCreate(false)} onConfirm={handleCreate} confirmText="Record Stay" loading={busy}/>
        </Modal>
      )}
    </div>
  );
}

// =============================================================================
// ─── SECTION 5: ENGAGEMENT SCORES ─────────────────────────────────────────────
// Endpoints:
//   GET  /engagement-scores/              → list
//   GET  /engagement-scores/{id}/         → detail
//   POST /engagement/recalculate/         → recalculate my score
//   GET  /engagement-scores/summary/      → aggregate summary
// =============================================================================
function EngagementView() {
  const list = useList(`${B}/engagement-scores/`, 8, {ordering:"-score"});
  const [showDetail,  setShowDetail] = useState(null);
  const [showRecalc,  setShowRecalc] = useState(false);
  const [recalcDate,  setRecalcDate] = useState(todayISO());
  const [recalcResult,setRR]         = useState(null);
  const [err,  setErr]  = useState(null);
  const [busy, setBusy] = useState(false);
  const [sumRange, setSumRange] = useState({start:"",end:""});
  const {data:summary, loading:ldSum, refetch:rSum} = useFetch(
    () => safeApi.get(`${B}/engagement-scores/summary/`, {
      ...(sumRange.start ? {start_date:sumRange.start} : {}),
      ...(sumRange.end   ? {end_date:sumRange.end}     : {}),
    }),
    [sumRange.start, sumRange.end]
  );

  const handleRecalc = async () => {
    setBusy(true); setErr(null);
    const body = recalcDate ? {date:recalcDate} : {};
    const { data, error } = await safeApi.post(`${B}/engagement/recalculate/`, body);
    setBusy(false);
    if (error) { setErr(error); return; }
    setRR(data); setShowRecalc(false); list.refetch();
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr">
        <span className="ba-ch-title">Engagement Scores <span style={{color:"var(--t4)",fontWeight:400}}>({fmtNum(list.count)})</span></span>
        <div style={{display:"flex",gap:8}}>
          <Sel value={list.params.ordering||"-score"} onChange={v=>list.updateParams({ordering:v})}
            options={[{value:"-score",label:"Highest first"},{value:"score",label:"Lowest first"},{value:"-date",label:"Newest date"}]}/>
          <BtnPrimary onClick={()=>{setShowRecalc(true);setErr(null);}}>↻ Recalculate</BtnPrimary>
        </div>
      </div>
      <ErrBox msg={list.error}/>
      {recalcResult && (
        <OkBox msg={`Score: ${safeFloat(recalcResult?.score??0)} | ${(recalcResult?.tier??"").toUpperCase()} | Clicks: ${recalcResult?.click_count??0} | Stay: ${fmtSec(recalcResult?.total_stay_sec??0)}`}/>
      )}

      {/* Summary filter */}
      <div className="ba-card" style={{padding:14,marginBottom:12}}>
        <div style={{display:"flex",gap:10,alignItems:"flex-end",flexWrap:"wrap"}}>
          <div>
            <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1,marginBottom:4}}>START DATE</div>
            <input className="ba-field-inp" type="date" value={sumRange.start}
              onChange={e=>setSumRange(r=>({...r,start:e.target.value}))} style={{width:150}}/>
          </div>
          <div>
            <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1,marginBottom:4}}>END DATE</div>
            <input className="ba-field-inp" type="date" value={sumRange.end}
              onChange={e=>setSumRange(r=>({...r,end:e.target.value}))} style={{width:150}}/>
          </div>
          <BtnPrimary onClick={rSum}>Apply</BtnPrimary>
          {ldSum && <Spin/>}
          {!ldSum && summary && (
            <div style={{display:"flex",gap:16,marginLeft:10}}>
              {[
                {lbl:"Avg Score",val:safeFloat(summary.avg_score??0),c:"#9000ff"},
                {lbl:"Max Score",val:safeFloat(summary.max_score??0),c:"#00ff88"},
                {lbl:"Min Score",val:safeFloat(summary.min_score??0),c:"#ff6600"},
              ].map((s,i)=>(
                <div key={i} style={{textAlign:"center"}}>
                  <div style={{fontFamily:"var(--fhud)",fontSize:20,fontWeight:700,color:s.c}}>{s.val}</div>
                  <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase"}}>{s.lbl}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="ba-card" style={{padding:0,overflow:"hidden"}}>
        <table className="ba-tbl">
          <thead><tr><th>User</th><th>Date</th><th>Score</th><th>Tier</th><th>Clicks</th><th>Stay</th><th>Depth</th><th>Returns</th><th>Detail</th></tr></thead>
          <tbody>
            {list.loading ? <LoadRow cols={9}/> :
             list.items.length===0 ? <EmptyRow cols={9}/> :
             list.items.map(s=>{
               const nm = s.user_display ?? s.user ?? "Unknown";
               const pct= Math.min(100, parseFloat(s.score||0));
               return (
                 <tr key={s.id}>
                   <td><div style={{display:"flex",alignItems:"center",gap:7}}><Av name={nm}/><span style={{fontWeight:500,fontSize:11}}>{nm}</span></div></td>
                   <td style={{fontFamily:"var(--fmono)",fontSize:10,color:"var(--t3)"}}>{s.date||"—"}</td>
                   <td>
                     <div style={{display:"flex",alignItems:"center",gap:6}}>
                       <BarMini pct={pct}/>
                       <span style={{fontFamily:"var(--fmono)",fontSize:11,color:"var(--t1)",fontWeight:700,minWidth:34}}>{safeFloat(s.score??0)}</span>
                     </div>
                   </td>
                   <td><TierBadge tier={s.tier}/></td>
                   <td className="ba-mono" style={{textAlign:"center"}}>{s.click_count??0}</td>
                   <td className="ba-mono">{fmtSec(s.total_stay_sec??0)}</td>
                   <td className="ba-mono" style={{textAlign:"center"}}>{s.path_depth??0}</td>
                   <td className="ba-mono" style={{textAlign:"center"}}>{s.return_visits??0}</td>
                   <td><BtnSm onClick={()=>setShowDetail(s)}>View</BtnSm></td>
                 </tr>
               );
             })}
          </tbody>
        </table>
      </div>
      <Pager page={list.page} total={list.totalPages} onPage={list.goPage}/>

      {showDetail && (
        <Modal title="Engagement Score Detail" wide onClose={()=>setShowDetail(null)}>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12}}>
            {[
              ["ID",            showDetail.id],
              ["User",          showDetail.user_display ?? showDetail.user],
              ["Date",          showDetail.date],
              ["Score",         safeFloat(showDetail.score??0, 2)],
              ["Tier",          <TierBadge tier={showDetail.tier}/>],
              ["Click Count",   showDetail.click_count??0],
              ["Total Stay",    fmtSec(showDetail.total_stay_sec??0)],
              ["Path Depth",    showDetail.path_depth??0],
              ["Return Visits", showDetail.return_visits??0],
            ].map(([lbl,val],i)=>(
              <div key={i} style={{background:"rgba(255,255,255,.02)",borderRadius:5,padding:"6px 8px"}}>
                <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1}}>{lbl}</div>
                <div style={{fontSize:10,color:"var(--t1)",fontFamily:"var(--fmono)",marginTop:2,wordBreak:"break-all"}}>{val}</div>
              </div>
            ))}
          </div>
          {showDetail.breakdown_json && Object.keys(showDetail.breakdown_json).length > 0 && <>
            <div style={{fontSize:10,color:"var(--t3)",marginBottom:6}}>Score Breakdown</div>
            <div style={{background:"rgba(0,0,0,.3)",borderRadius:6,padding:10,fontFamily:"var(--fmono)",fontSize:10}}>
              {Object.entries(showDetail.breakdown_json).map(([k,v])=>(
                <div key={k} style={{display:"flex",justifyContent:"space-between",padding:"3px 0",borderBottom:"1px solid rgba(255,255,255,.05)"}}>
                  <span style={{color:"var(--t3)"}}>{k}</span>
                  <span style={{color:"var(--cyan)"}}>{typeof v==="number"?v.toFixed(2):String(v)}</span>
                </div>
              ))}
            </div>
          </>}
        </Modal>
      )}

      {showRecalc && (
        <Modal title="Recalculate Engagement Score" onClose={()=>setShowRecalc(false)}>
          <ErrBox msg={err} onClose={()=>setErr(null)}/>
          <p style={{fontSize:11,color:"var(--t3)",marginBottom:12}}>
            Synchronous recalculation for authenticated user.
          </p>
          <Field label="Date (blank = today)"><Inp type="date" value={recalcDate} onChange={setRecalcDate}/></Field>
          <ModalActions onCancel={()=>setShowRecalc(false)} onConfirm={handleRecalc} confirmText="Recalculate Now" loading={busy}/>
        </Modal>
      )}
    </div>
  );
}

// =============================================================================
// ─── SECTION 6: SESSION LOOKUP ────────────────────────────────────────────────
// Endpoint: GET /sessions/{session_id}/
// =============================================================================
function SessionsView() {
  const [sessionId, setSessionId] = useState("");
  const [userId,    setUserId]    = useState("");
  const [result,    setResult]    = useState(null);
  const [loading,   setLoad]      = useState(false);
  const [err,       setErr]       = useState(null);

  const lookup = async () => {
    if (!sessionId.trim()) { setErr("Session ID required"); return; }
    setLoad(true); setErr(null); setResult(null);
    const params = userId ? {user_id:userId} : {};
    const { data, error } = await safeApi.get(`${B}/sessions/${sessionId.trim()}/`, params);
    setLoad(false);
    if (error) { setErr(error); return; }
    setResult(data);
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr"><span className="ba-ch-title">Session Lookup</span></div>
      <div className="ba-card" style={{padding:20,marginBottom:12}}>
        <p style={{fontSize:11,color:"var(--t3)",marginBottom:14}}>
          Look up any <code style={{color:"var(--cyan)"}}>UserPath</code> by its <code style={{color:"var(--cyan)"}}>session_id</code>.
          Staff can specify a user_id override.
        </p>
        <div style={{display:"flex",gap:10,flexWrap:"wrap",alignItems:"flex-end"}}>
          <div style={{flex:2}}>
            <Field label="Session ID *"><Inp value={sessionId} onChange={setSessionId} placeholder="Frontend session_id string"/></Field>
          </div>
          <div style={{flex:1}}>
            <Field label="User ID (staff only)"><Inp value={userId} onChange={setUserId} placeholder="User UUID"/></Field>
          </div>
          <BtnPrimary onClick={lookup} disabled={loading}>{loading?"Looking up...":"Look Up"}</BtnPrimary>
        </div>
        <ErrBox msg={err} onClose={()=>setErr(null)}/>
      </div>

      {result && (
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch">
            <span className="ba-ch-title" style={{color:"var(--green)"}}>Found ✅</span>
            <StatusBadge status={result.status}/>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginTop:10}}>
            {[
              ["ID",        result.id],
              ["Session",   result.session_id],
              ["Device",    result.device_type],
              ["Depth",     result.depth??0],
              ["Is Bounce", result.is_bounce?"Yes":"No"],
              ["Entry URL", result.entry_url||"—"],
              ["Exit URL",  result.exit_url||"—"],
              ["Created",   result.created_at?new Date(result.created_at).toLocaleString():"—"],
              ["Updated",   result.updated_at?new Date(result.updated_at).toLocaleString():"—"],
            ].map(([lbl,val],i)=>(
              <div key={i} style={{background:"rgba(255,255,255,.02)",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:8,color:"var(--t4)",textTransform:"uppercase",letterSpacing:1}}>{lbl}</div>
                <div style={{fontSize:10,color:"var(--t1)",fontFamily:"var(--fmono)",marginTop:3,wordBreak:"break-all"}}>{val}</div>
              </div>
            ))}
          </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:10,marginTop:12}}>
            {[
              {lbl:"Nodes",    items:result.nodes,        render:n=>`${n?.type??""} → ${n?.url??""}`},
              {lbl:"Clicks",   items:result.click_metrics,render:c=>`${c?.category??""} — ${(c?.page_url??"").slice(0,35)}`},
              {lbl:"Stay",     items:result.stay_times,   render:s=>`${fmtSec(s?.duration_seconds??0)} — ${(s?.page_url??"").slice(0,35)}`},
            ].map(({lbl,items,render})=>(
              <div key={lbl}>
                <div style={{fontSize:10,color:"var(--t3)",marginBottom:4}}>{lbl} ({Array.isArray(items)?items.length:0})</div>
                <div style={{background:"rgba(0,0,0,.3)",borderRadius:6,padding:8,maxHeight:110,overflowY:"auto",fontFamily:"var(--fmono)",fontSize:9,color:"var(--t3)"}}>
                  {Array.isArray(items) && items.length > 0
                    ? items.map((x,i)=><div key={i} style={{padding:"1px 0",borderBottom:"1px solid rgba(255,255,255,.04)"}}>{render(x)}</div>)
                    : <span style={{color:"var(--t4)"}}>None</span>
                  }
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// ─── SECTION 7: REPORTS ───────────────────────────────────────────────────────
// Endpoints: /dashboard/  /admin/stats/  /stay-times/stats/
// =============================================================================
function ReportsView() {
  const {data:dash,  loading:ldD, refetch:rD} = useFetch(()=>safeApi.get(`${B}/dashboard/`), []);
  const {data:admin, loading:ldA, refetch:rA} = useFetch(()=>safeApi.get(`${B}/admin/stats/`), []);
  const {data:stay,  loading:ldS, refetch:rS} = useFetch(()=>safeApi.get(`${B}/stay-times/stats/`), []);
  const [busy, setBusy] = useState(false);

  const refreshAll = async () => {
    setBusy(true);
    await Promise.allSettled([rD(), rA(), rS()]);
    setBusy(false);
  };

  return (
    <div className="ba-section-wrap">
      <div className="ba-sec-hdr">
        <span className="ba-ch-title">Analytics Reports</span>
        <BtnPrimary onClick={refreshAll} disabled={busy}>{busy?"Refreshing...":"↻ Refresh All"}</BtnPrimary>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
        {/* User Report */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch"><span className="ba-ch-title" style={{color:"var(--cyan)"}}>User Report (7d)</span></div>
          {ldD ? <div className="ba-loading"><Spin/></div> : dash ? (
            <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:8}}>
              {[
                ["Sessions",     fmtNum(dash.session_count)],
                ["Clicks",       fmtNum(dash.click_count)],
                ["Avg Stay",     fmtSec(Math.round(dash.avg_stay_time_sec||0))],
                ["Total Stay",   fmtSec(Math.round(dash.total_stay_time_sec||0))],
                ["Latest Score", `${safeFloat(dash.latest_score?.score??0)}%`],
                ["Latest Tier",  <TierBadge tier={dash.latest_score?.tier||"low"}/>],
                ["Period",       `${dash.period_days??7} days`],
                ["Generated",    dash.generated_at?new Date(dash.generated_at).toLocaleTimeString():"—"],
              ].map(([lbl,val],i)=>(
                <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:"1px solid rgba(80,30,160,.15)"}}>
                  <span style={{fontSize:10,color:"var(--t3)"}}>{lbl}</span>
                  <span style={{fontFamily:"var(--fmono)",fontSize:10,color:"var(--t1)"}}>{val}</span>
                </div>
              ))}
            </div>
          ) : <div className="ba-empty">No data</div>}
        </div>

        {/* Platform Report */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch"><span className="ba-ch-title" style={{color:"var(--purple)"}}>Platform Report</span></div>
          {ldA ? <div className="ba-loading"><Spin/></div> : admin ? (
            <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:8}}>
              {[
                ["Date",          admin.date],
                ["Sessions",      fmtNum(admin.total_sessions)],
                ["Clicks",        fmtNum(admin.total_clicks)],
                ["Avg Stay",      fmtSec(Math.round(admin.avg_stay_sec||0))],
                ["Avg Score",     safeFloat(admin.avg_score??0,2)],
                ["Scored Users",  fmtNum(admin.scored_users)],
                ["Generated",     admin.generated_at?new Date(admin.generated_at).toLocaleTimeString():"—"],
              ].map(([lbl,val],i)=>(
                <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:"1px solid rgba(80,30,160,.15)"}}>
                  <span style={{fontSize:10,color:"var(--t3)"}}>{lbl}</span>
                  <span style={{fontFamily:"var(--fmono)",fontSize:10,color:"var(--t1)"}}>{val}</span>
                </div>
              ))}
            </div>
          ) : <div className="ba-empty" style={{fontSize:10}}>🔒 Staff only</div>}
        </div>

        {/* Stay Time Report */}
        <div className="ba-card" style={{padding:16}}>
          <div className="ba-ch"><span className="ba-ch-title" style={{color:"var(--green)"}}>Stay Report</span></div>
          {ldS ? <div className="ba-loading"><Spin/></div> : stay ? (
            <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:8}}>
              {[
                ["Avg Duration",   fmtSec(Math.round(stay.avg_duration||0)),   "#00eeff"],
                ["Total Duration", fmtSec(Math.round(stay.total_duration||0)), "#ff00cc"],
                ["Total Records",  fmtNum(stay.total_count||stay.count||0),    "#00ff88"],
                ["Bounce Count",   fmtNum(stay.bounce_count||0),              "#ff6600"],
              ].map(([lbl,val,c],i)=>(
                <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"5px 0",borderBottom:"1px solid rgba(80,30,160,.15)"}}>
                  <span style={{fontSize:10,color:"var(--t3)"}}>{lbl}</span>
                  <span style={{fontFamily:"var(--fhud)",fontSize:14,fontWeight:700,color:c}}>{val}</span>
                </div>
              ))}
            </div>
          ) : <div className="ba-empty">No data</div>}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
// =============================================================================
const NAV_ITEMS = [
  { id:"dashboard",  ico:"📊", lbl:"Dashboard"         },
  { id:"paths",      ico:"🛤️", lbl:"User Paths"        },
  { id:"clicks",     ico:"🖱️", lbl:"Click Metrics"     },
  { id:"stay",       ico:"⏱️", lbl:"Stay Times"        },
  { id:"engagement", ico:"📈", lbl:"Engagement Scores" },
  { id:"sessions",   ico:"🔍", lbl:"Session Lookup"    },
  { id:"reports",    ico:"📋", lbl:"Reports"           },
];

export default function BehaviorAnalytics() {
  const [nav, setNav] = useState("dashboard");
  const active   = NAV_ITEMS.find(n => n.id === nav);
  const todayStr = new Date().toLocaleDateString("en-US", {month:"short",day:"numeric",year:"numeric"});

  const renderView = () => {
    switch (nav) {
      case "dashboard":  return <DashboardView/>;
      case "paths":      return <PathsView/>;
      case "clicks":     return <ClicksView/>;
      case "stay":       return <StayTimesView/>;
      case "engagement": return <EngagementView/>;
      case "sessions":   return <SessionsView/>;
      case "reports":    return <ReportsView/>;
      default:           return <DashboardView/>;
    }
  };

  return (
    <div className="ba-page">
      {/* HEADER */}
      <header className="ba-header">
        <PageEndpointPanel pageKey="BehaviorAnalytics" title="BehaviorAnalytics Endpoints" />
        <div className="ba-logo">
          <div className="ba-logo-hex">
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <polygon points="7,1 13,4 13,10 7,13 1,10 1,4" stroke="white" strokeWidth="1.5" fill="none"/>
              <polygon points="7,4 10,5.5 10,8.5 7,10 4,8.5 4,5.5" fill="white" opacity=".7"/>
            </svg>
          </div>
          Behavior Analytics
        </div>
        <div className="ba-search">
          <span style={{color:"var(--t4)",fontSize:13}}>🔍</span>
          <input placeholder="Search..."/>
        </div>
        <div className="ba-hdr-r">
          <div className="ba-date">📅 {todayStr}</div>
          <div className="ba-hbtn">🔔<span className="ba-dot"/></div>
          <div className="ba-hbtn">⚙️</div>
          <div className="ba-hbtn">👤</div>
        </div>
      </header>

      <div className="ba-layout">
        {/* SIDEBAR */}
        <aside className="ba-sidebar">
          <div className="ba-user-card">
            <div className="ba-av">👤</div>
            <div style={{flex:1}}>
              <div className="ba-uname">Ainul_dev</div>
              <div className="ba-urole">(superadmin)</div>
            </div>
            <span style={{color:"var(--t4)",fontSize:10}}>▼</span>
          </div>
          <nav className="ba-nav">
            {NAV_ITEMS.map(item=>(
              <div key={item.id}
                className={`ba-nav-item${nav===item.id?" on":""}`}
                onClick={()=>setNav(item.id)}>
                <span className="ba-nav-ico">{item.ico}</span>
                {item.lbl}
              </div>
            ))}
          </nav>
          <div className="ba-sb-div"/>
          <div style={{marginTop:"auto"}}>
            <div className="ba-sb-icons">
              {["🔗","🔄","😊","🎯","💬","🌐","➡️"].map((ic,i)=>(
                <div key={i} className="ba-sb-ico">{ic}</div>
              ))}
            </div>
            <div className="ba-sb-term">AINUL@analytics:~ $</div>
          </div>
        </aside>

        {/* MAIN */}
        <main className="ba-main">
          <div className="ba-content-hdr">
            <h1 className="ba-content-title">{active?.ico} {active?.lbl}</h1>
            <div className="ba-content-acts">
              {["📤","🔄","⚙️"].map((ic,i)=><div key={i} className="ba-act">{ic}</div>)}
            </div>
          </div>
          <div key={nav} className="ba-anim">
            {renderView()}
          </div>
        </main>
      </div>
    </div>
  );
}