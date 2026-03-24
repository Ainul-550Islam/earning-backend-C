// src/pages/AuditLogs.jsx
// 100% API Coverage — 28 endpoints fully wired

import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../styles/auditlogs.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

const tkn = () => localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
const hdr = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${tkn()}` });
const BASE = '/api/audit_logs';

async function apiFetch(url, opts = {}) {
  try {
    const r = await fetch(url, { ...opts, headers: { ...hdr(), ...(opts.headers || {}) } });
    if (r.status === 204) return { ok: true };
    if (!r.ok) { const e = await r.json().catch(() => ({})); return { error: e?.detail || e?.message || `HTTP ${r.status}` }; }
    return await r.json();
  } catch (e) { return { error: e.message }; }
}
const POST  = (u, b) => apiFetch(u, { method: 'POST',   body: JSON.stringify(b) });
const PUT   = (u, b) => apiFetch(u, { method: 'PUT',    body: JSON.stringify(b) });
const PATCH = (u, b) => apiFetch(u, { method: 'PATCH',  body: JSON.stringify(b) });
const DEL   = u      => apiFetch(u, { method: 'DELETE' });
const toList = r => { if (!r || r.error) return []; if (Array.isArray(r)) return r; return r.results || r.data || r.logs || []; };

// ── NO DEMO DATA — real API only ─────────────────────────────────────────────
const DLOGS = [];
const DSTATS = { total_logs:0, logs_today:0, logs_this_week:0, logs_this_month:0, error_logs:0, warning_logs:0, security_logs:0, success_rate:0, avg_response_time:0, storage_usage_mb:0, archive_count:0, top_actions:[], top_users:[], top_ips:[] };
const DCFGS = [];
const DALERTS = [];
const DDASH = [];
const DARCH = [];

// ── ICONS SVG ─────────────────────────────────────────────────────────────────
const Shield   = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
const SearchIco= () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
const RefreshIco=() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>;
const DownIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;
const EyeIco   = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>;
const XIco     = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
const CheckIco = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>;
const FilterIco= () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>;
const BellIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>;
const ArchiveIco=() => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>;
const ChartIco = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
const TrashIco = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>;
const GearIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
const DashIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>;
const LiveIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 7.76a6 6 0 0 0 0 8.49M20.07 4.93a10 10 0 0 1 0 14.14M3.93 4.93a10 10 0 0 0 0 14.14"/></svg>;
const HealthIco= () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>;
const PlusIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const EditIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
const ZapIco   = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
const StarIco  = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>;
const ResetIco = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.96"/></svg>;

// ── HELPERS ───────────────────────────────────────────────────────────────────
const fmtDt = d => { if(!d) return '—'; try { return new Date(d).toLocaleString('en-US',{month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}); } catch{return d;} };
const fmtDate = d => { if(!d) return '—'; try{return new Date(d).toLocaleDateString('en-US',{month:'short',day:'2-digit',year:'numeric'});}catch{return d;} };
const avBg = n => { const c=['linear-gradient(135deg,#7c3aed,#2563eb)','linear-gradient(135deg,#059669,#0891b2)','linear-gradient(135deg,#d97706,#ea580c)','linear-gradient(135deg,#e11d48,#7c3aed)','linear-gradient(135deg,#2563eb,#0891b2)']; return c[(n||'A').charCodeAt(0)%c.length]; };
// Extract clean username — removes " - $0.00" or similar suffixes from __str__
const cleanUser = u => {
  if (!u) return null;
  const s = String(u);
  // Remove " - $X.XX" pattern
  const clean = s.replace(/\s*-\s*\$[\d.,]+$/, '').trim();
  return clean || s;
};
const atag = a => { if(!a) return 'tgr'; const v=a.toUpperCase(); if(['LOGIN','REGISTER'].includes(v)) return 'tg'; if(v==='LOGOUT') return 'tb'; if(['PASSWORD_CHANGE','PROFILE_UPDATE'].includes(v)) return 'tv'; if(v==='DEPOSIT') return 'tc'; if(v==='WITHDRAWAL') return 'to'; if(['USER_BAN','IP_BLOCK','BRUTE_FORCE_ATTEMPT'].includes(v)) return 'tr'; if(v.includes('KYC')||v.includes('OFFER')||v.includes('REFERRAL')) return 'tv'; if(['SYSTEM_ALERT','BACKUP','MAINTENANCE'].includes(v)) return 'ta'; return 'tgr'; };
const ltag = l => { if(!l) return 'tgr'; switch(l.toUpperCase()){case 'CRITICAL':case 'ERROR':case 'SECURITY':return 'tr';case 'WARNING':return 'ta';case 'INFO':return 'tg';case 'DEBUG':return 'tb';default:return 'tgr';} };
const mtag = m => { if(!m) return 'tgr'; switch(m.toUpperCase()){case 'GET':return 'tg';case 'POST':return 'tb';case 'PUT':case 'PATCH':return 'ta';case 'DELETE':return 'tr';default:return 'tgr';} };
const sevtag = s => { switch((s||'').toUpperCase()){case 'CRITICAL':case 'ERROR':case 'SECURITY':return 'tr';case 'WARNING':return 'ta';case 'INFO':return 'tg';default:return 'tgr';} };

const VIEWS     = ['Logs','Stats','Timeline','Live','Configs','Dashboards','Alert Rules','Archives','Health'];
const ACT_FLTRS = [
  {label:'All Events',    val:'',                                 dot:'#a855f7'},
  {label:'Auth',          val:'LOGIN,LOGOUT,REGISTER',            dot:'#34d399'},
  {label:'Profile/Pass',  val:'PROFILE_UPDATE,PASSWORD_CHANGE',   dot:'#a855f7'},
  {label:'Financial',     val:'DEPOSIT,WITHDRAWAL,WALLET_TRANSFER',dot:'#22d3ee'},
  {label:'Offers',        val:'OFFER_VIEW,OFFER_CLICK,OFFER_COMPLETE',dot:'#60a5fa'},
  {label:'KYC',           val:'KYC_SUBMIT,KYC_APPROVE,KYC_REJECT',dot:'#fbbf24'},
  {label:'Security',      val:'SUSPICIOUS_LOGIN,BRUTE_FORCE_ATTEMPT,IP_BLOCK',dot:'#fb7185'},
  {label:'Admin',         val:'USER_BAN,USER_UNBAN,MANUAL_CREDIT,MANUAL_DEBIT',dot:'#fb923c'},
  {label:'System',        val:'SYSTEM_ALERT,BACKUP,MAINTENANCE',  dot:'#475569'},
];
const LVL_FLTRS = [
  {label:'All Levels',val:'',         dot:'#475569'},
  {label:'Info',      val:'INFO',     dot:'#34d399'},
  {label:'Warning',   val:'WARNING',  dot:'#fbbf24'},
  {label:'Error',     val:'ERROR',    dot:'#fb7185'},
  {label:'Critical',  val:'CRITICAL', dot:'#fb7185'},
  {label:'Security',  val:'SECURITY', dot:'#fb7185'},
];
const EXPFMTS  = ['json','csv','excel','pdf'];
const EXPCOMPS = ['none','gzip','zip'];
const LOG_LVLS = ['DEBUG','INFO','WARNING','ERROR','CRITICAL','SECURITY'];
const ALT_ACTS = ['EMAIL','SMS','WEBHOOK','CREATE_TICKET','BLOCK_USER','FLAG_TRANSACTION'];
const PAGE     = 20;

// ── REUSABLE COMPONENTS ───────────────────────────────────────────────────────
function Modal({ title, icon: Ic, onClose, children, width=480 }) {
  return (
    <div className="al-overlay" onClick={onClose}>
      <div className="al-modal" style={{width,maxWidth:'95vw'}} onClick={e=>e.stopPropagation()}>
        <div className="al-modal-head">
          <div className="al-modal-title">{Ic && <Ic/>}{title}</div>
          <button className="al-dt-close" onClick={onClose}><XIco/></button>
        </div>
        {children}
      </div>
    </div>
  );
}
function FR({label,children}) {
  return (
    <div className="al-form-row">
      <label className="al-form-lbl">{label}</label>
      <div className="al-form-ctrl">{children}</div>
    </div>
  );
}
function Tgl({value,onChange}) {
  return <div className={`al-tgl ${value?'on':''}`} onClick={()=>onChange(!value)}><div className="al-tgl-knob"/></div>;
}
function Btn({children,onClick,cls='',disabled=false,style={}}) {
  return <button className={`al-hbtn ${cls}`} onClick={onClick} disabled={disabled} style={style}>{children}</button>;
}

// ═══════════════════════════════════════════════════════════════════════════════
export default function AuditLogs() {
  const [view,    setView]   = useState('Logs');
  const [logs,    setLogs]   = useState([]);
  const [stats,   setStats]  = useState({ total_logs:0, logs_today:0, logs_this_week:0, logs_this_month:0, error_logs:0, warning_logs:0, security_logs:0, success_rate:0, avg_response_time:0, storage_usage_mb:0, archive_count:0, top_actions:[], top_users:[], top_ips:[] });
  const [tl,      setTl]     = useState([]);
  const [live,    setLive]   = useState([]);
  const [liveOn,  setLiveOn] = useState(false);
  const [cfgs,    setCfgs]   = useState([]);
  const [dash,    setDash]   = useState([]);
  const [alerts,  setAlerts] = useState([]);
  const [arch,    setArch]   = useState([]);
  const [health,  setHealth] = useState(null);
  const [load,    setLoad]   = useState(false);
  const [apiOk,   setApiOk]  = useState(false);
  const [toast,   setToast]  = useState(null);
  const [sel,     setSel]    = useState(null);
  const [search,  setSearch] = useState('');
  const [actF,    setActF]   = useState('');
  const [lvlF,    setLvlF]   = useState('');
  const [sucF,    setSucF]   = useState('');
  const [page,    setPage]   = useState(1);
  const [total,   setTotal]  = useState(0);
  const [timer,   setTimer]  = useState(30);
  const [tlInt,   setTlInt]  = useState('hour');
  const [expFmt,  setExpFmt] = useState('json');
  const [expComp, setExpComp]= useState('none');
  const [expBusy, setExpBusy]= useState(false);
  const [adv,     setAdv]    = useState(false);
  const [advQ,    setAdvQ]   = useState({search:'',filters:{}});
  const [dbPreview,setDbPrev]= useState(null);
  // modals
  const [mPur,  setMPur]  = useState(false);  const [purDays,  setPurDays]  = useState(365);
  const [mRed,  setMRed]  = useState(false);  const [redF,     setRedF]     = useState({request_body:false,response_body:false,error_message:false,stack_trace:false});
  const [mCfg,  setMCfg]  = useState(false);  const [cfgEdit,  setCfgEdit]  = useState(null);
  const [mDb,   setMDb]   = useState(false);  const [dbEdit,   setDbEdit]   = useState(null);
  const [mAlt,  setMAlt]  = useState(false);  const [altEdit,  setAltEdit]  = useState(null);
  const [mArch, setMArch] = useState(false);  const [archForm, setArchForm] = useState({start_date:'',end_date:'',compression:'zip'});

  const timerRef = useRef();
  const liveRef  = useRef();

  // toast
  const toast$ = useCallback((msg,type='ok') => { setToast({msg,type}); setTimeout(()=>setToast(null),3200); },[]);

  // ── LOAD LOGS (GET /logs/) ─────────────────────────────────────────────────
  const loadLogs = useCallback(async (spinner=false) => {
    if(spinner) setLoad(true);
    const p = new URLSearchParams({page_size:PAGE,page,ordering:'-timestamp'});
    if(search) p.set('search',search);
    if(lvlF)   p.set('level',lvlF);
    if(sucF)   p.set('success',sucF);
    if(actF)   actF.split(',').filter(Boolean).forEach(a=>p.append('action',a));
    const [res,st] = await Promise.all([apiFetch(`${BASE}/logs/?${p}`), apiFetch(`${BASE}/stats/`)]);
    if(res&&!res.error){ const l=toList(res); setApiOk(true); if(l.length||res.count!=null){setLogs(l);setTotal(res.count||l.length);} }
    if(st&&!st.error){ const s=st.data||st; if(s.total_logs!=null) setStats(s); }
    setTimer(30);
    if(spinner) setLoad(false);
  },[page,search,actF,lvlF,sucF]);

  const loadTimeline  = useCallback(async()=>{ const r=await apiFetch(`${BASE}/logs/timeline/?interval=${tlInt}&limit=24`); if(r&&!r.error) setTl(toList(r)); },[tlInt]);
  const loadCfgs      = useCallback(async()=>{ const r=await apiFetch(`${BASE}/configs/`);       if(r&&!r.error){ const l=toList(r); if(l.length) setCfgs(l); } },[]);
  const loadDash      = useCallback(async()=>{ const r=await apiFetch(`${BASE}/dashboards/`);    if(r&&!r.error){ const l=toList(r); if(l.length) setDash(l); } },[]);
  const loadAlerts    = useCallback(async()=>{ const r=await apiFetch(`${BASE}/alert-rules/`);   if(r&&!r.error){ const l=toList(r); if(l.length) setAlerts(l); } },[]);
  const loadArch      = useCallback(async()=>{ const r=await apiFetch(`${BASE}/archives/`);      if(r&&!r.error){ const l=toList(r); if(l.length) setArch(l); } },[]);
  const loadHealth    = useCallback(async()=>{ const r=await apiFetch(`${BASE}/health/`);        if(r&&!r.error) setHealth(r.data||r); },[]);
  const pollLive      = useCallback(async()=>{ const r=await apiFetch(`${BASE}/live/`);          if(r&&!r.error) setLive((toList(r)||[]).slice(0,50)); },[]);

  useEffect(()=>{ loadLogs(true); },[loadLogs]);
  useEffect(()=>{
    if(view==='Timeline')    loadTimeline();
    if(view==='Configs')     loadCfgs();
    if(view==='Dashboards')  loadDash();
    if(view==='Alert Rules') loadAlerts();
    if(view==='Archives')    loadArch();
    if(view==='Health')      loadHealth();
  },[view]);
  useEffect(()=>{ clearInterval(timerRef.current); timerRef.current=setInterval(()=>setTimer(p=>{if(p<=1){loadLogs();return 30;}return p-1;}),1000); return()=>clearInterval(timerRef.current); },[loadLogs]);
  useEffect(()=>{ if(liveOn){pollLive();liveRef.current=setInterval(pollLive,5000);}else clearInterval(liveRef.current); return()=>clearInterval(liveRef.current); },[liveOn,pollLive]);

  // ── DETAIL ────────────────────────────────────────────────────────────────
  const openDetail = async log => { setSel(log); const r=await apiFetch(`${BASE}/logs/${log.id}/`); if(r&&!r.error) setSel(r.data||r); };

  // ── EXPORT — POST /export/ ────────────────────────────────────────────────
  const handleExport = async () => {
    setExpBusy(true);
    try {
      const filters = {};
      if (actF)   filters.action  = actF.split(',');
      if (lvlF)   filters.level   = lvlF;
      if (sucF)   filters.success = sucF === 'true';
      if (search) filters.search  = search;
      const body = { format: expFmt, compression: expComp, filters };
      const r = await fetch(`${BASE}/export/`, { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
      if (!r.ok) { toast$('Export failed: ' + r.status, 'err'); return; }
      const blob = await r.blob();
      const ext  = expFmt === 'excel' ? 'xlsx' : expComp === 'zip' ? 'zip' : expComp === 'gzip' ? 'gz' : expFmt;
      const a    = document.createElement('a');
      a.href     = URL.createObjectURL(blob);
      a.download = `audit_${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      toast$(`Exported as ${ext.toUpperCase()}`);
    } catch (e) { toast$(e.message, 'err'); } finally { setExpBusy(false); }
  };

  // ── ADVANCED SEARCH — POST /search/ ──────────────────────────────────────
  const handleAdvSearch = async () => {
    setLoad(true);
    const r = await POST(`${BASE}/search/`,{query:advQ,page:1,page_size:PAGE,sort_by:'-timestamp'});
    if(r&&!r.error){ setLogs(r.results||toList(r)); setTotal(r.total||0); setApiOk(true); toast$(`Found ${r.total||0} results`); }
    else toast$(r?.error||'Search failed','err');
    setLoad(false);
  };

  // ── PURGE — DELETE /purge/?days=N&confirm=true ────────────────────────────
  const handlePurge = async () => {
    const r = await DEL(`${BASE}/purge/?days=${purDays}&confirm=true`);
    if(r&&!r.error){toast$(`Purged ${r.deleted_count??'?'} logs`);setMPur(false);loadLogs(true);}
    else toast$(r?.error||'Purge failed','err');
  };

  // ── REDACT — POST /logs/{id}/redact/ ─────────────────────────────────────
  const handleRedact = async () => {
    if(!sel) return;
    const fields=Object.entries(redF).filter(([,v])=>v).map(([k])=>k);
    if(!fields.length){toast$('Select at least one field','err');return;}
    const r=await POST(`${BASE}/logs/${sel.id}/redact/`,{fields});
    if(r&&!r.error){toast$('Log redacted');setMRed(false);loadLogs();setSel(p=>({...p,...Object.fromEntries(fields.map(f=>[f,'[REDACTED]']))}))}
    else toast$(r?.error||'Redact failed','err');
  };

  // ── CONFIGS CRUD ──────────────────────────────────────────────────────────
  const saveCfg = async () => {
    if(!cfgEdit) return;
    const isNew=!cfgEdit.id; const url=isNew?`${BASE}/configs/`:`${BASE}/configs/${cfgEdit.id}/`;
    const r=await(isNew?POST:PUT)(url,cfgEdit);
    if(r&&!r.error){toast$(isNew?'Config created':'Config updated');setMCfg(false);loadCfgs();}
    else toast$(r?.error||'Save failed','err');
  };
  const delCfg = async id => { const r=await DEL(`${BASE}/configs/${id}/`); if(r&&!r.error){toast$('Config deleted');loadCfgs();}else toast$(r?.error||'Delete failed','err'); };
  const loadDefaultCfgs = async () => { const r=await apiFetch(`${BASE}/configs/defaults/`); if(r&&!r.error){setCfgs(toList(r));toast$('Default configs loaded');}else toast$(r?.error||'Failed','err'); };
  const resetCfgs = async () => { const r=await POST(`${BASE}/configs/reset/`,{}); if(r&&!r.error){toast$('Configs reset');loadCfgs();}else toast$(r?.error||'Reset failed','err'); };

  // ── DASHBOARDS CRUD ───────────────────────────────────────────────────────
  const saveDb = async () => {
    if(!dbEdit) return;
    const isNew=!dbEdit.id; const url=isNew?`${BASE}/dashboards/`:`${BASE}/dashboards/${dbEdit.id}/`;
    const r=await(isNew?POST:PUT)(url,dbEdit);
    if(r&&!r.error){toast$(isNew?'Dashboard created':'Dashboard updated');setMDb(false);loadDash();}
    else toast$(r?.error||'Save failed','err');
  };
  const delDb = async id => { const r=await DEL(`${BASE}/dashboards/${id}/`); if(r&&!r.error){toast$('Deleted');loadDash();}else toast$(r?.error||'Failed','err'); };
  const setDefaultDb = async id => { const r=await POST(`${BASE}/dashboards/${id}/set_default/`,{}); if(r&&!r.error){toast$('Set as default');setDash(p=>p.map(d=>({...d,is_default:d.id===id})));}else toast$(r?.error||'Failed','err'); };
  const previewDb = async db => { const r=await apiFetch(`${BASE}/dashboards/${db.id}/preview/`); if(r&&!r.error) setDbPrev(r.data||r); else toast$(r?.error||'Preview failed','err'); };

  // ── ALERTS CRUD ───────────────────────────────────────────────────────────
  const saveAlt = async () => {
    if(!altEdit) return;
    const isNew=!altEdit.id; const url=isNew?`${BASE}/alert-rules/`:`${BASE}/alert-rules/${altEdit.id}/`;
    const r=await(isNew?POST:PUT)(url,altEdit);
    if(r&&!r.error){toast$(isNew?'Alert rule created':'Alert rule updated');setMAlt(false);loadAlerts();}
    else toast$(r?.error||'Save failed','err');
  };
  const delAlt = async id => { const r=await DEL(`${BASE}/alert-rules/${id}/`); if(r&&!r.error){toast$('Alert rule deleted');loadAlerts();}else toast$(r?.error||'Failed','err'); };
  const toggleAlt = async rule => { const ep=rule.enabled?'disable':'enable'; const r=await POST(`${BASE}/alert-rules/${rule.id}/${ep}/`,{}); if(r&&!r.error){toast$(`Rule ${ep}d`);setAlerts(p=>p.map(a=>a.id===rule.id?{...a,enabled:!a.enabled}:a));}else toast$(r?.error||'Toggle failed','err'); };
  const testAlt = async rule => { const r=await POST(`${BASE}/alert-rules/${rule.id}/test/`,{}); if(r&&!r.error) toast$(`Test: ${r.matching_logs??0} matching logs`); else toast$(r?.error||'Test failed','err'); };
  const loadTriggered = async () => { const r=await apiFetch(`${BASE}/alert-rules/triggered/`); if(r&&!r.error){const l=toList(r);if(l.length)setAlerts(l);toast$(`${l.length} triggered rules`);}else toast$(r?.error||'Failed','err'); };

  // ── ARCHIVES ──────────────────────────────────────────────────────────────
  const createArch = async () => {
    if(!archForm.start_date||!archForm.end_date){toast$('Select date range','err');return;}
    const r=await POST(`${BASE}/archives/create/`,archForm);
    if(r&&!r.error){toast$('Archive created');setMArch(false);loadArch();}
    else toast$(r?.error||'Create failed','err');
  };
  const downloadArch = async a => {
    try { const r=await fetch(`${BASE}/archives/${a.id}/download/`,{headers:hdr()}); if(!r.ok){toast$('Download failed','err');return;} const blob=await r.blob(); const el=document.createElement('a'); el.href=URL.createObjectURL(blob); el.download=`archive_${a.id}.zip`; el.click(); toast$('Download started'); }
    catch(e){toast$(e.message,'err');}
  };

  // ── COMPUTED ──────────────────────────────────────────────────────────────
  const displayed = apiOk ? logs : logs.filter(l=>{
    if(search&&!JSON.stringify(l).toLowerCase().includes(search.toLowerCase())) return false;
    if(actF&&!actF.split(',').includes(l.action)) return false;
    if(lvlF&&l.level!==lvlF) return false;
    if(sucF&&String(l.success)!==sucF) return false;
    return true;
  });
  const ds = stats.total_logs > 0 ? stats : {
    total_logs:   logs.length,
    logs_today:   logs.filter(l => new Date(l.timestamp).toDateString() === new Date().toDateString()).length,
    success_rate: logs.length ? ((logs.filter(l => l.success).length / logs.length) * 100).toFixed(1) : 0,
    error_logs:   logs.filter(l => ['ERROR','CRITICAL'].includes(l.level)).length,
    warning_logs: logs.filter(l => l.level === 'WARNING').length,
    avg_response_time: 0, storage_usage_mb: 0, archive_count: 0,
    top_actions: [], top_users: [], top_ips: [],
  };
  const totalPages = Math.max(1,Math.ceil((total||displayed.length)/PAGE));

  // ── NEW CONFIG / ALERT / DASHBOARD helpers ────────────────────────────────
  const newCfg  = () => { setCfgEdit({action:'',enabled:true,log_level:'INFO',log_request_body:true,log_response_body:true,log_headers:false,retention_days:365,notify_admins:false,notify_users:false}); setMCfg(true); };
  const newDb   = () => { setDbEdit({name:'',description:'',filters:{},columns:[],refresh_interval:300,is_default:false}); setMDb(true); };
  const newAlt  = () => { setAltEdit({name:'',description:'',severity:'WARNING',action:'EMAIL',enabled:true,cooldown_minutes:5,condition:{field:'level',operator:'equals',value:'ERROR'},action_config:{email:'admin@example.com'}}); setMAlt(true); };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="al-root">
      <div className="al-bg-mesh"/><div className="al-noise"/>
        <PageEndpointPanel pageKey="AuditLogs" title="AuditLogs Endpoints" />

      {/* TOAST */}
      {toast && <div className={`al-toast ${toast.type==='err'?'err':''}`}>{toast.type==='err'?<XIco/>:<CheckIco/>} {toast.msg}</div>}

      {/* HEADER */}
      <header className="al-header">
        <div className="al-header-left">
          <div className="al-logo"><div className="al-logo-icon"><Shield/></div>Audit Intelligence</div>
          <div className="al-vdiv"/>
          <div className="al-crumb">Admin <span>/ Audit Logs</span></div>
        </div>
        <div className="al-header-right">
          <div className="al-live"><div className="al-live-dot"/>{apiOk?'API LIVE':'DEMO'}</div>
          <div className="al-refresh-timer">sync <span>{timer}s</span></div>
          <Btn onClick={()=>loadLogs(true)}><RefreshIco/> Refresh</Btn>
          <Btn cls="danger" onClick={()=>setMPur(true)}><TrashIco/> Purge</Btn>
        </div>
      </header>

      {/* KPI CARDS */}
      <div className="al-kpis">
        {[
          {cls:'kv',label:'Total Events', val:(ds.total_logs||0).toLocaleString(),             sub:'All time'},
          {cls:'kg',label:'Success Rate', val:`${parseFloat(ds.success_rate||0).toFixed(1)}%`, sub:'Healthy ops'},
          {cls:'kr',label:'Errors',       val:(ds.error_logs||0),                              sub:'Need attention'},
          {cls:'kb',label:'Today',        val:(ds.logs_today||0).toLocaleString(),              sub:'Last 24h'},
          {cls:'ka',label:'Warnings',     val:(ds.warning_logs||0),                            sub:'Review needed'},
          {cls:'kc',label:'Avg Response', val:`${Math.round(ds.avg_response_time||0)}ms`,       sub:'Response time'},
        ].map((k,i)=>(
          <div key={i} className={`al-kpi ${k.cls}`}>
            <div className="al-kpi-bar"/>
            <div className="al-kpi-label">{k.label}</div>
            <div className="al-kpi-val">{k.val}</div>
            <div className="al-kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* TABS */}
      <div className="al-tabs">
        {VIEWS.map(v=>(
          <button key={v} className={`al-tab ${view===v?'on':''}`} onClick={()=>setView(v)}>
            {v==='Stats'&&<ChartIco/>}{v==='Timeline'&&<LiveIco/>}{v==='Live'&&<LiveIco/>}
            {v==='Configs'&&<GearIco/>}{v==='Dashboards'&&<DashIco/>}{v==='Alert Rules'&&<BellIco/>}
            {v==='Archives'&&<ArchiveIco/>}{v==='Health'&&<HealthIco/>}
            {v}
          </button>
        ))}
      </div>

      {/* LAYOUT */}
      <div className="al-layout">

        {/* SIDEBAR */}
        {view==='Logs' && (
          <aside className="al-sidebar">
            <div className="al-sb-title">Action Type</div>
            {ACT_FLTRS.map((f,i)=>(
              <div key={i} className={`al-nav ${actF===f.val?'on':''}`} onClick={()=>{setActF(f.val);setPage(1);}}>
                <div className="al-nav-l"><div className="al-dot" style={{background:f.dot}}/>{f.label}</div>
              </div>
            ))}
            <div className="al-sep"/>
            <div className="al-sb-title">Severity</div>
            {LVL_FLTRS.map((f,i)=>(
              <div key={i} className={`al-nav ${lvlF===f.val?'on':''}`} onClick={()=>{setLvlF(f.val);setPage(1);}}>
                <div className="al-nav-l"><div className="al-dot" style={{background:f.dot}}/>{f.label}</div>
              </div>
            ))}
            <div className="al-sep"/>
            <div className="al-sb-title">Status</div>
            {[['','All'],['true','Success'],['false','Failed']].map(([v,l],i)=>(
              <div key={i} className={`al-nav ${sucF===v?'on':''}`} onClick={()=>{setSucF(v);setPage(1);}}>
                <div className="al-nav-l"><div className="al-dot" style={{background:v===''?'#475569':v==='true'?'#34d399':'#fb7185'}}/>{l}</div>
              </div>
            ))}
          </aside>
        )}

        {/* ══ LOGS VIEW ════════════════════════════════════════════════════ */}
        {view==='Logs' && (
          <div className="al-content">
            <div className="al-toolbar">
              <div className="al-search">
                <SearchIco/>
                <input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Search user, action, IP, message..."/>
                {search && <button className="al-clear-btn" onClick={()=>setSearch('')}><XIco/></button>}
              </div>
              <div className={`al-chip ${adv?'on':''}`} onClick={()=>setAdv(p=>!p)} style={{cursor:'pointer',display:'flex',alignItems:'center',gap:6}}><FilterIco/> Advanced</div>
              <div className="al-chips">
                {[['','All'],['true','✓ OK'],['false','✗ Fail']].map(([v,l],i)=>(
                  <div key={i} className={`al-chip ${sucF===v?'on':''}`} onClick={()=>{setSucF(v);setPage(1);}}>{l}</div>
                ))}
              </div>
            </div>

            {/* Advanced search */}
            {adv && (
              <div className="al-adv-panel">
                <div style={{fontSize:12,fontWeight:600,color:'var(--text-secondary)',marginBottom:10,display:'flex',alignItems:'center',gap:6}}><FilterIco/> Advanced Search — POST /search/</div>
                <div style={{display:'flex',gap:10,flexWrap:'wrap',marginBottom:10}}>
                  <input className="al-input" style={{flex:1,minWidth:200}} value={advQ.search} onChange={e=>setAdvQ(p=>({...p,search:e.target.value}))} placeholder="Full-text search..."/>
                  <input className="al-input" style={{flex:1,minWidth:200,fontFamily:'var(--font-mono)',fontSize:11}}
                    value={typeof advQ.filters==='string'?advQ.filters:JSON.stringify(advQ.filters||{})}
                    onChange={e=>{try{setAdvQ(p=>({...p,filters:JSON.parse(e.target.value)}))}catch{setAdvQ(p=>({...p,filters:e.target.value}))}}}
                    placeholder='{"and":[{"field":"level","operator":"equals","value":"ERROR"}]}'/>
                </div>
                <div style={{display:'flex',gap:8}}>
                  <Btn cls="pri" onClick={handleAdvSearch}><SearchIco/> Search</Btn>
                  <Btn onClick={()=>{setAdv(false);setAdvQ({search:'',filters:{}});loadLogs(true);}}>Reset</Btn>
                </div>
              </div>
            )}

            {load ? (
              <div className="al-loading"><div className="al-spin"/> Loading...</div>
            ) : (
              <div className="al-tw">
                <table className="al-table">
                  <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Level</th><th>Status</th><th>IP</th><th>Method</th><th>Path</th><th>Time</th><th></th></tr></thead>
                  <tbody>
                    {displayed.map(log=>(
                      <tr key={log.id} className={sel?.id===log.id?'sel':''} onClick={()=>openDetail(log)}>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--text-muted)'}}>{fmtDt(log.timestamp||log.created_at)}</td>
                        <td>
                          <div className="al-ucell">
                            <div className="al-av" style={{background:avBg(cleanUser(log.user)||'A')}}>{(cleanUser(log.user)||'?')[0].toUpperCase()}</div>
                            <span style={{fontSize:12,fontWeight:600,color:'var(--text-primary)'}}>{cleanUser(log.user)||'Anonymous'}</span>
                          </div>
                        </td>
                        <td><span className={`al-tag ${atag(log.action)}`}>{log.action_display||log.action||'—'}</span></td>
                        <td><span className={`al-tag ${ltag(log.level)}`}>{log.level||'—'}</span></td>
                        <td>{log.success?<span className="al-ok"><CheckIco/> OK</span>:<span className="al-fail"><XIco/> Fail</span>}</td>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:11}}>{log.user_ip||'—'}</td>
                        <td>{log.request_method?<span className={`al-tag ${mtag(log.request_method)}`}>{log.request_method}</span>:<span style={{color:'var(--text-muted)'}}>—</span>}</td>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--text-muted)',maxWidth:130,overflow:'hidden',textOverflow:'ellipsis'}}>{log.request_path||'—'}</td>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:11,color:(log.response_time_ms||0)>500?'var(--amber2)':'var(--text-muted)'}}>{log.response_time_ms!=null?`${log.response_time_ms}ms`:'—'}</td>
                        <td onClick={e=>{e.stopPropagation();openDetail(log);}}><Btn style={{padding:'4px 10px',fontSize:11}}><EyeIco/></Btn></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {displayed.length===0&&<div className="al-empty"><div style={{opacity:.3,marginBottom:12}}><FilterIco/></div>No logs found</div>}
              </div>
            )}

            <div className="al-pagination">
              <span>{displayed.length>0?`Showing ${((page-1)*PAGE)+1}–${Math.min(page*PAGE,total||displayed.length)} of ${(total||displayed.length).toLocaleString()}`:'No events'}</span>
              <div className="al-pg">
                <button className="al-pgb" onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1}>‹</button>
                {[...Array(Math.min(5,totalPages))].map((_,i)=><button key={i} className={`al-pgb ${page===i+1?'on':''}`} onClick={()=>setPage(i+1)}>{i+1}</button>)}
                {totalPages>5&&<button className="al-pgb" style={{width:'auto',padding:'0 10px'}}>…</button>}
                <button className="al-pgb" onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages}>›</button>
              </div>
            </div>

            {/* Export panel */}
            <div className="al-exp-panel">
              <div className="al-exp-title"><DownIco/> Export Logs — POST /export/</div>
              <div className="al-exp-row"><label>Format</label><div className="al-chips">{EXPFMTS.map(f=><div key={f} className={`al-chip ${expFmt===f?'on':''}`} onClick={()=>setExpFmt(f)}>{f.toUpperCase()}</div>)}</div></div>
              <div className="al-exp-row"><label>Compression</label><div className="al-chips">{EXPCOMPS.map(c=><div key={c} className={`al-chip ${expComp===c?'on':''}`} onClick={()=>setExpComp(c)}>{c.toUpperCase()}</div>)}</div></div>
              <Btn cls="pri" onClick={handleExport} disabled={expBusy} style={{marginTop:8}}>
                {expBusy?<div className="al-spin" style={{width:12,height:12,margin:0}}/>:<DownIco/>}
                {expBusy?'Exporting...':`Export ${expFmt.toUpperCase()}`}
              </Btn>
            </div>
          </div>
        )}

        {/* ══ STATS VIEW ═══════════════════════════════════════════════════ */}
        {view==='Stats' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div className="al-section-title"><ChartIco/> Audit Statistics</div>
            <div className="al-stats-grid">
              <div className="al-card">
                <div className="al-card-title">Top Actions</div>
                {(ds.top_actions||[]).map((a,i)=>{
                  const max=(ds.top_actions||[])[0]?.count||1;
                  return <div className="al-bar-row" key={i}><span className={`al-tag ${atag(a.action)}`} style={{minWidth:110}}>{a.action}</span><div className="al-bar-track"><div className="al-bar-fill" style={{width:`${Math.round((a.count/max)*100)}%`}}/></div><span className="al-bar-val">{(a.count||0).toLocaleString()}</span></div>;
                })}
              </div>
              <div className="al-card">
                <div className="al-card-title">Most Active Users</div>
                {(ds.top_users||[]).map((u,i)=>(
                  <div className="al-user-row" key={i}>
                    <div className="al-av" style={{background:avBg(u.user__username||'?'),width:28,height:28}}>{(u.user__username||'?')[0].toUpperCase()}</div>
                    <div style={{flex:1}}><div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)'}}>{cleanUser(u.user__username)||u.user__email||'—'}</div><div style={{fontSize:10,color:'var(--text-muted)'}}>{u.user__email||''}</div></div>
                    <span className="al-bar-val">{(u.count||0).toLocaleString()}</span>
                  </div>
                ))}
              </div>
              <div className="al-card">
                <div className="al-card-title">Top IP Addresses</div>
                {(ds.top_ips||[]).map((ip,i)=><div className="al-bar-row" key={i}><span style={{fontFamily:'var(--font-mono)',fontSize:12,color:'var(--violet2)',minWidth:130}}>{ip.user_ip||'—'}</span><span className="al-bar-val">{(ip.count||0).toLocaleString()}</span></div>)}
              </div>
              <div className="al-card">
                <div className="al-card-title">Storage & Archival</div>
                <div className="al-kv-row"><span>Table size</span><span className="hi">{ds.storage_usage_mb} MB</span></div>
                <div className="al-kv-row"><span>Archives</span><span className="hi">{ds.archive_count}</span></div>
                <div className="al-kv-row"><span>This month</span><span>{(ds.logs_this_month||0).toLocaleString()}</span></div>
                <div className="al-kv-row"><span>Security events</span><span className="er">{ds.security_logs||0}</span></div>
              </div>
            </div>
          </div>
        )}

        {/* ══ TIMELINE VIEW ════════════════════════════════════════════════ */}
        {view==='Timeline' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><LiveIco/> Activity Timeline — GET /logs/timeline/</div>
              <div className="al-chips">{['hour','day'].map(i=><div key={i} className={`al-chip ${tlInt===i?'on':''}`} onClick={()=>setTlInt(i)}>By {i}</div>)}</div>
            </div>
            {tl.length===0?<div className="al-empty">No timeline data</div>:(
              <div className="al-timeline">
                {tl.map((t,i)=>{ const max=Math.max(...tl.map(x=>x.count||0),1); const h=Math.max(8,Math.round(((t.count||0)/max)*120));
                  return <div className="al-tl-bar" key={i} title={`${t.time_group}: ${t.count}`}><div className="al-tl-fill" style={{height:h,background:'linear-gradient(180deg,#a855f7,#60a5fa)'}}/><div className="al-tl-val">{t.count||0}</div><div className="al-tl-lbl">{String(t.time_group||'').slice(-5)}</div></div>;
                })}
              </div>
            )}
          </div>
        )}

        {/* ══ LIVE VIEW ════════════════════════════════════════════════════ */}
        {view==='Live' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><LiveIco/> Live Feed — GET /live/ (polls 5s)</div>
              <div style={{display:'flex',gap:8,alignItems:'center'}}>
                {liveOn&&<div style={{display:'flex',alignItems:'center',gap:6,fontSize:11,color:'var(--green2)'}}><div className="al-live-dot"/>LIVE</div>}
                <Btn cls={liveOn?'pri':''} onClick={()=>setLiveOn(p=>!p)}>{liveOn?<><XIco/> Stop</>:<><LiveIco/> Start Live</>}</Btn>
                <Btn onClick={pollLive}><RefreshIco/> Poll Now</Btn>
              </div>
            </div>
            {live.length===0?<div className="al-empty"><div style={{opacity:.3,marginBottom:12}}><LiveIco/></div>{liveOn?'Waiting for events...':'Click "Start Live" to begin'}</div>:(
              <div className="al-tw">
                <table className="al-table">
                  <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Level</th><th>IP</th><th>Message</th></tr></thead>
                  <tbody>
                    {live.map((log,i)=>(
                      <tr key={log.id||i}>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--text-muted)'}}>{fmtDt(log.timestamp)}</td>
                        <td><div className="al-ucell"><div className="al-av" style={{background:avBg(cleanUser(log.user)||'A')}}>{(cleanUser(log.user)||'?')[0].toUpperCase()}</div><span style={{fontSize:12}}>{cleanUser(log.user)||'Anon'}</span></div></td>
                        <td><span className={`al-tag ${atag(log.action)}`}>{log.action||'—'}</span></td>
                        <td><span className={`al-tag ${ltag(log.level)}`}>{log.level||'—'}</span></td>
                        <td style={{fontFamily:'var(--font-mono)',fontSize:11}}>{log.user_ip||'—'}</td>
                        <td style={{fontSize:11,color:'var(--text-muted)',maxWidth:220,overflow:'hidden',textOverflow:'ellipsis'}}>{log.message||'—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ══ CONFIGS VIEW ═════════════════════════════════════════════════ */}
        {view==='Configs' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><GearIco/> Log Configurations — /configs/</div>
              <div style={{display:'flex',gap:8}}>
                <Btn onClick={loadDefaultCfgs}><DownIco/> Load Defaults</Btn>
                <Btn cls="danger" onClick={resetCfgs}><ResetIco/> Reset All</Btn>
                <Btn cls="pri" onClick={newCfg}><PlusIco/> New Config</Btn>
              </div>
            </div>
            <div className="al-tw">
              <table className="al-table">
                <thead><tr><th>Action</th><th>Enabled</th><th>Level</th><th>Req Body</th><th>Res Body</th><th>Headers</th><th>Retention</th><th>Notify Admin</th><th>Notify User</th><th></th></tr></thead>
                <tbody>
                  {cfgs.map(cfg=>(
                    <tr key={cfg.id}>
                      <td><span className={`al-tag ${atag(cfg.action)}`}>{cfg.action}</span></td>
                      <td><Tgl value={cfg.enabled} onChange={async v=>{const r=await PATCH(`${BASE}/configs/${cfg.id}/`,{enabled:v});if(r&&!r.error){setCfgs(p=>p.map(c=>c.id===cfg.id?{...c,enabled:v}:c));toast$(v?'Enabled':'Disabled');}else toast$(r?.error||'Failed','err');}}/></td>
                      <td><span className={`al-tag ${ltag(cfg.log_level)}`}>{cfg.log_level}</span></td>
                      {['log_request_body','log_response_body','log_headers','notify_admins','notify_users'].map(k=>(
                        <td key={k} style={{textAlign:'center'}}>{cfg[k]?<span className="al-ok" style={{justifyContent:'center'}}><CheckIco/></span>:<span style={{color:'var(--text-muted)'}}>—</span>}</td>
                      ))}
                      <td style={{fontFamily:'var(--font-mono)',fontSize:11}}>{cfg.retention_days}d</td>
                      <td><div style={{display:'flex',gap:4}}><Btn style={{padding:'4px 8px'}} onClick={()=>{setCfgEdit({...cfg});setMCfg(true);}}><EditIco/></Btn><Btn cls="danger" style={{padding:'4px 8px'}} onClick={()=>delCfg(cfg.id)}><TrashIco/></Btn></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ══ DASHBOARDS VIEW ══════════════════════════════════════════════ */}
        {view==='Dashboards' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><DashIco/> Custom Dashboards — /dashboards/</div>
              <Btn cls="pri" onClick={newDb}><PlusIco/> New Dashboard</Btn>
            </div>
            <div className="al-cards-list">
              {dash.map(db=>(
                <div key={db.id} className="al-alert-card">
                  <div className="al-alert-head">
                    <div>
                      <div style={{display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontWeight:600,fontSize:14,color:'var(--text-primary)'}}>{db.name}</span>
                        {db.is_default&&<span className="al-tag tg" style={{fontSize:9}}>DEFAULT</span>}
                      </div>
                      <div style={{fontSize:11,color:'var(--text-muted)',marginTop:3}}>{db.description||'No description'}</div>
                    </div>
                    <div style={{display:'flex',gap:6}}>
                      <Btn style={{padding:'5px 8px'}} onClick={()=>previewDb(db)}><EyeIco/></Btn>
                      <Btn style={{padding:'5px 8px'}} onClick={()=>{setDbEdit({...db});setMDb(true);}}><EditIco/></Btn>
                      <Btn cls="danger" style={{padding:'5px 8px'}} onClick={()=>delDb(db.id)}><TrashIco/></Btn>
                    </div>
                  </div>
                  <div className="al-alert-stats">
                    <div className="al-kv-row"><span>Refresh</span><span>{db.refresh_interval}s</span></div>
                    <div className="al-kv-row"><span>Columns</span><span>{(db.columns||[]).length} fields</span></div>
                  </div>
                  {!db.is_default&&<Btn style={{width:'100%',marginTop:10,justifyContent:'center'}} onClick={()=>setDefaultDb(db.id)}><StarIco/> Set as Default</Btn>}
                </div>
              ))}
            </div>
            {dbPreview&&(
              <div style={{marginTop:24}}>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
                  <div className="al-section-title"><EyeIco/> Dashboard Preview</div>
                  <Btn onClick={()=>setDbPrev(null)}><XIco/> Close</Btn>
                </div>
                <div className="al-tw">
                  <table className="al-table">
                    <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Level</th><th>Status</th></tr></thead>
                    <tbody>
                      {toList(dbPreview?.preview_data||dbPreview).slice(0,10).map((log,i)=>(
                        <tr key={i}>
                          <td style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--text-muted)'}}>{fmtDt(log.timestamp)}</td>
                          <td style={{fontSize:12}}>{cleanUser(log.user)||'—'}</td>
                          <td><span className={`al-tag ${atag(log.action)}`}>{log.action||'—'}</span></td>
                          <td><span className={`al-tag ${ltag(log.level)}`}>{log.level||'—'}</span></td>
                          <td>{log.success?<span className="al-ok"><CheckIco/> OK</span>:<span className="al-fail"><XIco/> Fail</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══ ALERT RULES VIEW ═════════════════════════════════════════════ */}
        {view==='Alert Rules' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><BellIco/> Alert Rules — /alert-rules/</div>
              <div style={{display:'flex',gap:8}}>
                <Btn onClick={loadTriggered}><ZapIco/> Triggered</Btn>
                <Btn cls="pri" onClick={newAlt}><PlusIco/> New Rule</Btn>
              </div>
            </div>
            <div className="al-cards-list">
              {alerts.map(rule=>(
                <div key={rule.id} className="al-alert-card">
                  <div className="al-alert-head">
                    <div>
                      <div style={{fontWeight:600,fontSize:14,color:'var(--text-primary)'}}>{rule.name}</div>
                      <div style={{fontSize:11,color:'var(--text-muted)',marginTop:2}}>{rule.description||'No description'}</div>
                    </div>
                    <div style={{display:'flex',gap:6,alignItems:'center'}}>
                      <span className={`al-tag ${sevtag(rule.severity)}`}>{rule.severity}</span>
                      <Tgl value={rule.enabled} onChange={()=>toggleAlt(rule)}/>
                    </div>
                  </div>
                  <div className="al-alert-stats">
                    <div className="al-kv-row"><span>Action</span><span className="al-tag ta" style={{fontSize:10}}>{rule.action}</span></div>
                    <div className="al-kv-row"><span>Triggered</span><span className="hi">{rule.trigger_count||0}x</span></div>
                    <div className="al-kv-row"><span>Last triggered</span><span>{fmtDt(rule.last_triggered)||'Never'}</span></div>
                    <div className="al-kv-row"><span>Condition</span><span style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--text-muted)'}}>{JSON.stringify(rule.condition||{}).substring(0,40)}…</span></div>
                  </div>
                  <div style={{display:'flex',gap:6,marginTop:12}}>
                    <Btn style={{flex:1}} onClick={()=>testAlt(rule)}><ZapIco/> Test</Btn>
                    <Btn style={{padding:'6px 10px'}} onClick={()=>{setAltEdit({...rule});setMAlt(true);}}><EditIco/></Btn>
                    <Btn cls="danger" style={{padding:'6px 10px'}} onClick={()=>delAlt(rule.id)}><TrashIco/></Btn>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ ARCHIVES VIEW ════════════════════════════════════════════════ */}
        {view==='Archives' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><ArchiveIco/> Log Archives — /archives/</div>
              <Btn cls="pri" onClick={()=>setMArch(true)}><PlusIco/> Create Archive</Btn>
            </div>
            <div className="al-cards-list">
              {arch.map(a=>(
                <div key={a.id} className="al-archive-card">
                  <div className="al-alert-head">
                    <div>
                      <div style={{fontWeight:600,fontSize:13,color:'var(--text-primary)'}}>{fmtDate(a.start_date)} → {fmtDate(a.end_date)}</div>
                      <div style={{fontSize:11,color:'var(--text-muted)',marginTop:2}}>{(a.total_logs||0).toLocaleString()} logs · {fmtDate(a.created_at)}</div>
                    </div>
                    <Btn cls="pri" onClick={()=>downloadArch(a)}><DownIco/> Download</Btn>
                  </div>
                  <div className="al-alert-stats">
                    <div className="al-kv-row"><span>Compressed</span><span className="hi">{a.compressed_size_mb} MB</span></div>
                    <div className="al-kv-row"><span>Original</span><span>{a.original_size_mb} MB</span></div>
                    <div className="al-kv-row"><span>Ratio</span><span>{a.compression_ratio}x</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ HEALTH VIEW ══════════════════════════════════════════════════ */}
        {view==='Health' && (
          <div className="al-content" style={{padding:'20px 24px'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
              <div className="al-section-title"><HealthIco/> System Health — GET /health/</div>
              <Btn onClick={loadHealth}><RefreshIco/> Check Now</Btn>
            </div>
            {health?(
              <div style={{maxWidth:560}}>
                <div className={`al-health-badge ${health.status==='healthy'?'ok':'err'}`} style={{marginBottom:20}}>
                  {health.status==='healthy'?<CheckIco/>:<XIco/>} {(health.status||'').toUpperCase()}
                </div>
                <div className="al-card">
                  <div className="al-card-title">Checks</div>
                  {Object.entries(health.checks||{}).map(([k,v])=>(
                    <div className="al-kv-row" key={k}>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11}}>{k}</span>
                      <span className={String(v).startsWith('ok')?'hi':'er'}>{v}</span>
                    </div>
                  ))}
                </div>
                <div className="al-kv-row" style={{marginTop:12}}>
                  <span style={{color:'var(--text-muted)'}}>Checked at</span>
                  <span style={{fontFamily:'var(--font-mono)',fontSize:11}}>{fmtDt(health.timestamp)}</span>
                </div>
              </div>
            ):<div className="al-empty"><div className="al-spin" style={{margin:'0 auto 12px'}}/>Loading...</div>}
          </div>
        )}

        {/* DETAIL PANEL */}
        {view==='Logs' && sel && (
          <aside className="al-detail">
            <div className="al-dt-head">
              <button className="al-dt-close" onClick={()=>setSel(null)} style={{float:'right'}}><XIco/></button>
              <div className="al-dt-action">{sel.action_display||sel.action||'Event Detail'}</div>
              <div className="al-dt-tags">
                <span className={`al-tag ${ltag(sel.level)}`}>{sel.level||'—'}</span>
                <span className={`al-tag ${sel.success?'tg':'tr'}`}>{sel.success?'Success':'Failed'}</span>
                {sel.request_method&&<span className={`al-tag ${mtag(sel.request_method)}`}>{sel.request_method}</span>}
              </div>
              <div className="al-dt-id">ID: {String(sel.id||'').substring(0,12).toUpperCase()}…</div>
            </div>
            <div className="al-dt-body">
              {[
                {l:'User',         v:cleanUser(sel.user)||'Anonymous',                                          c:''},
                {l:'Timestamp',    v:fmtDt(sel.timestamp||sel.created_at),                          c:''},
                {l:'IP Address',   v:sel.user_ip||sel.ip_address||'—',                              c:'hi'},
                {l:'Country/City', v:[sel.country,sel.city].filter(Boolean).join(' / ')||'—',        c:''},
                {l:'Request Path', v:sel.request_path||'—',                                          c:''},
                {l:'Resource',     v:[sel.resource_type,sel.resource_id].filter(Boolean).join(' #')||'—',c:''},
                {l:'Status Code',  v:sel.status_code||'—',                                           c:''},
                {l:'Resp Time',    v:sel.response_time_ms?`${sel.response_time_ms}ms`:'—',           c:(sel.response_time_ms||0)>500?'wa':''},
                {l:'Correlation',  v:sel.correlation_id?String(sel.correlation_id).substring(0,16)+'…':'—',c:'hi'},
                {l:'Message',      v:sel.message||'—',                                               c:''},
                {l:'Error',        v:sel.error_message||'None',                                      c:sel.error_message?'er':''},
              ].map((r,i)=>(
                <div className="al-dt-row" key={i}>
                  <div className="al-dt-lbl">{r.l}</div>
                  <div className={`al-dt-val ${r.c}`}>{r.v}</div>
                </div>
              ))}
              {sel.changes&&Object.keys(sel.changes).length>0&&(
                <div className="al-dt-row">
                  <div className="al-dt-lbl">Changes</div>
                  {Object.entries(sel.changes).map(([k,ch])=>(
                    <div key={k} style={{marginBottom:6}}>
                      <div style={{fontSize:10,color:'var(--text-muted)',fontWeight:600}}>{k}</div>
                      <div style={{display:'flex',gap:6,fontSize:10,fontFamily:'var(--font-mono)'}}>
                        <span className="al-tag tr" style={{padding:'2px 6px'}}>{String(ch.old).substring(0,28)}</span>
                        <span style={{color:'var(--text-muted)'}}>→</span>
                        <span className="al-tag tg" style={{padding:'2px 6px'}}>{String(ch.new).substring(0,28)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {sel.metadata&&Object.keys(sel.metadata).length>0&&(
                <div className="al-dt-row">
                  <div className="al-dt-lbl">Metadata</div>
                  <pre className="al-pre">{JSON.stringify(sel.metadata,null,2)}</pre>
                </div>
              )}
              {sel.device_info&&(
                <div className="al-dt-row">
                  <div className="al-dt-lbl">Device</div>
                  <div className="al-dt-val">{sel.device_info.browser} / {sel.device_info.os}{sel.device_info.is_mobile&&<span className="al-tag ta" style={{marginLeft:6,fontSize:9}}>Mobile</span>}{sel.device_info.is_bot&&<span className="al-tag tr" style={{marginLeft:6,fontSize:9}}>Bot</span>}</div>
                </div>
              )}
              <div style={{display:'flex',gap:8,marginTop:16}}>
                <Btn style={{flex:1}} onClick={()=>setMRed(true)}><Shield/> Redact Fields</Btn>
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* ══════════════ MODALS ══════════════════════════════════════════════ */}

      {/* PURGE */}
      {mPur&&(
        <Modal title="Purge Old Logs" icon={TrashIco} onClose={()=>setMPur(false)}>
          <p className="al-modal-desc">Permanently delete logs older than N days.<br/><strong style={{color:'var(--rose2)'}}>This action cannot be undone.</strong></p>
          <FR label="Delete logs older than">
            <div style={{display:'flex',gap:8,alignItems:'center'}}>
              <input type="number" value={purDays} min={1} onChange={e=>setPurDays(Number(e.target.value))} className="al-input" style={{width:80}}/>
              <span style={{fontSize:12,color:'var(--text-muted)'}}>days</span>
            </div>
          </FR>
          <div className="al-modal-actions">
            <Btn onClick={()=>setMPur(false)}>Cancel</Btn>
            <Btn cls="danger" onClick={handlePurge}><TrashIco/> Confirm Purge</Btn>
          </div>
        </Modal>
      )}

      {/* REDACT */}
      {mRed&&sel&&(
        <Modal title="Redact Sensitive Fields" icon={Shield} onClose={()=>setMRed(false)}>
          <p className="al-modal-desc">Select fields to redact from log <code style={{fontFamily:'var(--font-mono)',fontSize:11}}>{String(sel.id).substring(0,12)}…</code></p>
          <div className="al-check-group">
            {Object.entries(redF).map(([k,v])=>(
              <label className="al-check-row" key={k}>
                <input type="checkbox" checked={v} onChange={e=>setRedF(p=>({...p,[k]:e.target.checked}))}/>
                <span className="al-tag tgr">{k}</span>
              </label>
            ))}
          </div>
          <div className="al-modal-actions">
            <Btn onClick={()=>setMRed(false)}>Cancel</Btn>
            <Btn cls="pri" onClick={handleRedact}><Shield/> Redact</Btn>
          </div>
        </Modal>
      )}

      {/* CONFIG EDIT */}
      {mCfg&&cfgEdit&&(
        <Modal title={cfgEdit.id?'Edit Config':'New Config'} icon={GearIco} onClose={()=>setMCfg(false)} width={520}>
          <FR label="Action"><input className="al-input" style={{width:'100%'}} value={cfgEdit.action} onChange={e=>setCfgEdit(p=>({...p,action:e.target.value}))} placeholder="LOGIN, WITHDRAWAL..."/></FR>
          <FR label="Log Level">
            <select className="al-input" value={cfgEdit.log_level} onChange={e=>setCfgEdit(p=>({...p,log_level:e.target.value}))}>
              {LOG_LVLS.map(l=><option key={l} value={l}>{l}</option>)}
            </select>
          </FR>
          <FR label="Retention (days)"><input type="number" className="al-input" value={cfgEdit.retention_days} min={1} onChange={e=>setCfgEdit(p=>({...p,retention_days:Number(e.target.value)}))}/></FR>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:16}}>
            {[['enabled','Enabled'],['log_request_body','Log Request Body'],['log_response_body','Log Response Body'],['log_headers','Log Headers'],['notify_admins','Notify Admins'],['notify_users','Notify Users']].map(([k,l])=>(
              <label key={k} style={{display:'flex',alignItems:'center',gap:8,fontSize:12,color:'var(--text-secondary)',cursor:'pointer'}}>
                <Tgl value={!!cfgEdit[k]} onChange={v=>setCfgEdit(p=>({...p,[k]:v}))}/> {l}
              </label>
            ))}
          </div>
          <div className="al-modal-actions"><Btn onClick={()=>setMCfg(false)}>Cancel</Btn><Btn cls="pri" onClick={saveCfg}><CheckIco/> Save</Btn></div>
        </Modal>
      )}

      {/* DASHBOARD EDIT */}
      {mDb&&dbEdit&&(
        <Modal title={dbEdit.id?'Edit Dashboard':'New Dashboard'} icon={DashIco} onClose={()=>setMDb(false)} width={520}>
          <FR label="Name"><input className="al-input" style={{width:'100%'}} value={dbEdit.name} onChange={e=>setDbEdit(p=>({...p,name:e.target.value}))} placeholder="Dashboard name"/></FR>
          <FR label="Description"><input className="al-input" style={{width:'100%'}} value={dbEdit.description||''} onChange={e=>setDbEdit(p=>({...p,description:e.target.value}))} placeholder="Short description"/></FR>
          <FR label="Refresh (sec)"><input type="number" className="al-input" value={dbEdit.refresh_interval||300} min={60} onChange={e=>setDbEdit(p=>({...p,refresh_interval:Number(e.target.value)}))}/></FR>
          <FR label="Filters (JSON)">
            <input className="al-input" style={{width:'100%',fontFamily:'var(--font-mono)',fontSize:11}}
              value={typeof dbEdit.filters==='string'?dbEdit.filters:JSON.stringify(dbEdit.filters||{})}
              onChange={e=>{try{setDbEdit(p=>({...p,filters:JSON.parse(e.target.value)}))}catch{setDbEdit(p=>({...p,filters:e.target.value}))}}}
              placeholder='{"level":"ERROR"}'/>
          </FR>
          <div className="al-modal-actions"><Btn onClick={()=>setMDb(false)}>Cancel</Btn><Btn cls="pri" onClick={saveDb}><CheckIco/> Save</Btn></div>
        </Modal>
      )}

      {/* ALERT RULE EDIT */}
      {mAlt&&altEdit&&(
        <Modal title={altEdit.id?'Edit Alert Rule':'New Alert Rule'} icon={BellIco} onClose={()=>setMAlt(false)} width={520}>
          <FR label="Name"><input className="al-input" style={{width:'100%'}} value={altEdit.name} onChange={e=>setAltEdit(p=>({...p,name:e.target.value}))} placeholder="Rule name"/></FR>
          <FR label="Description"><input className="al-input" style={{width:'100%'}} value={altEdit.description||''} onChange={e=>setAltEdit(p=>({...p,description:e.target.value}))} placeholder="What does this detect?"/></FR>
          <FR label="Severity">
            <select className="al-input" value={altEdit.severity} onChange={e=>setAltEdit(p=>({...p,severity:e.target.value}))}>
              {LOG_LVLS.map(s=><option key={s} value={s}>{s}</option>)}
            </select>
          </FR>
          <FR label="Action">
            <select className="al-input" value={altEdit.action} onChange={e=>setAltEdit(p=>({...p,action:e.target.value}))}>
              {ALT_ACTS.map(a=><option key={a} value={a}>{a}</option>)}
            </select>
          </FR>
          <FR label="Cooldown (min)"><input type="number" className="al-input" value={altEdit.cooldown_minutes||5} min={1} onChange={e=>setAltEdit(p=>({...p,cooldown_minutes:Number(e.target.value)}))}/></FR>
          <FR label="Condition (JSON)">
            <input className="al-input" style={{width:'100%',fontFamily:'var(--font-mono)',fontSize:11}}
              value={typeof altEdit.condition==='string'?altEdit.condition:JSON.stringify(altEdit.condition||{})}
              onChange={e=>{try{setAltEdit(p=>({...p,condition:JSON.parse(e.target.value)}))}catch{setAltEdit(p=>({...p,condition:e.target.value}))}}}
              placeholder='{"field":"level","operator":"equals","value":"ERROR"}'/>
          </FR>
          <div className="al-modal-actions"><Btn onClick={()=>setMAlt(false)}>Cancel</Btn><Btn cls="pri" onClick={saveAlt}><CheckIco/> Save Rule</Btn></div>
        </Modal>
      )}

      {/* ARCHIVE CREATE */}
      {mArch&&(
        <Modal title="Create Archive" icon={ArchiveIco} onClose={()=>setMArch(false)}>
          <p className="al-modal-desc">Compress and archive logs within a date range.</p>
          <FR label="Start Date"><input type="datetime-local" className="al-input" style={{width:'100%'}} value={archForm.start_date} onChange={e=>setArchForm(p=>({...p,start_date:e.target.value}))}/></FR>
          <FR label="End Date"><input type="datetime-local" className="al-input" style={{width:'100%'}} value={archForm.end_date} onChange={e=>setArchForm(p=>({...p,end_date:e.target.value}))}/></FR>
          <FR label="Compression">
            <div className="al-chips">{['zip','gzip','none'].map(c=><div key={c} className={`al-chip ${archForm.compression===c?'on':''}`} onClick={()=>setArchForm(p=>({...p,compression:c}))}>{c.toUpperCase()}</div>)}</div>
          </FR>
          <div className="al-modal-actions"><Btn onClick={()=>setMArch(false)}>Cancel</Btn><Btn cls="pri" onClick={createArch}><ArchiveIco/> Create Archive</Btn></div>
        </Modal>
      )}
    </div>
  );
}


// // src/pages/AuditLogs.jsx — Ultra Modern Glassmorphism
// // ✅ REAL API — /api/audit_logs/ endpoints

// import React, { useState, useEffect, useCallback, useRef } from 'react';
// import '../styles/auditlogs.css';

// const tkn = () => localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
// const hdr = () => ({ 'Authorization': `Bearer ${tkn()}` });
// const BASE = '/api/audit_logs';

// async function apiFetch(url) {
//   try {
//     const r = await fetch(url, { headers: hdr() });
//     if (!r.ok) return null;
//     return await r.json();
//   } catch { return null; }
// }
// const toList = r => {
//   if (!r) return [];
//   if (Array.isArray(r)) return r;
//   if (Array.isArray(r.results)) return r.results;
//   if (Array.isArray(r.data)) return r.data;
//   return [];
// };

// // ─── FALLBACK ────────────────────────────────────────────────────
// const FB = [
//   { id:'1', user:'Ainul Islam', action:'LOGIN',          action_display:'User Login',      level:'INFO',     success:true,  user_ip:'192.168.1.1', message:'Logged in',        timestamp:'2026-03-05T08:00:00Z', request_method:'POST', request_path:'/api/auth/login/' },
//   { id:'2', user:'Ainul Islam', action:'PROFILE_UPDATE', action_display:'Profile Update',  level:'INFO',     success:true,  user_ip:'192.168.1.1', message:'Profile updated',  timestamp:'2026-03-05T07:45:00Z', request_method:'PUT',  request_path:'/api/auth/profile/' },
//   { id:'3', user:'Ainul Islam', action:'PASSWORD_CHANGE',action_display:'Password Change', level:'WARNING',  success:true,  user_ip:'192.168.1.1', message:'Password changed', timestamp:'2026-03-05T07:30:00Z', request_method:'POST', request_path:'/api/auth/password/' },
//   { id:'4', user:'Ainul Islam', action:'LOGOUT',         action_display:'User Logout',     level:'INFO',     success:true,  user_ip:'192.168.1.1', message:'Logged out',       timestamp:'2026-03-05T06:00:00Z', request_method:'POST', request_path:'/api/auth/logout/' },
//   { id:'5', user:'tanvir007',   action:'DEPOSIT',        action_display:'Deposit',         level:'INFO',     success:true,  user_ip:'10.0.0.2',    message:'Deposit $50',      timestamp:'2026-03-04T22:00:00Z', request_method:'POST', request_path:'/api/wallet/' },
//   { id:'6', user:'sumaiya_m',   action:'WITHDRAWAL',     action_display:'Withdrawal',      level:'WARNING',  success:false, user_ip:'10.0.0.5',    message:'Withdrawal failed',timestamp:'2026-03-04T20:00:00Z', request_method:'POST', request_path:'/api/wallet/' },
//   { id:'7', user:'karim_x',     action:'OFFER_CLICK',    action_display:'Offer Click',     level:'INFO',     success:true,  user_ip:'10.0.0.8',    message:'Offer clicked',    timestamp:'2026-03-04T18:00:00Z', request_method:'GET',  request_path:'/api/offers/' },
//   { id:'8', user:'unknown',     action:'LOGIN',          action_display:'User Login',      level:'CRITICAL', success:false, user_ip:'45.33.22.11', message:'Failed login',     timestamp:'2026-03-04T16:00:00Z', request_method:'POST', request_path:'/api/auth/login/' },
// ];

// // ─── ICONS ───────────────────────────────────────────────────────
// const I = {
//   Shield:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
//   Search:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
//   Refresh:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>,
//   Download: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
//   Eye:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
//   X:        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
//   Check:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
//   Filter:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>,
// };

// const fmtDt = (d) => {
//   if (!d) return '—';
//   try { return new Date(d).toLocaleString('en-US', { month:'short', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false }); }
//   catch { return d; }
// };

// // Tag color by action
// const actionTag = (a) => {
//   if (!a) return 'tgr';
//   const v = a.toUpperCase();
//   if (v === 'LOGIN' || v === 'REGISTER') return 'tg';
//   if (v === 'LOGOUT') return 'tb';
//   if (v === 'PASSWORD_CHANGE') return 'ta';
//   if (v === 'PROFILE_UPDATE') return 'tv';
//   if (v === 'DEPOSIT') return 'tc';
//   if (v === 'WITHDRAWAL') return 'to';
//   if (v.includes('DELETE') || v.includes('BLOCK')) return 'tr';
//   if (v.includes('OFFER')) return 'tv';
//   return 'tgr';
// };
// // Tag color by level
// const levelTag = (l) => {
//   if (!l) return 'tgr';
//   switch (l.toUpperCase()) {
//     case 'CRITICAL': case 'ERROR': return 'tr';
//     case 'WARNING': return 'ta';
//     case 'INFO': return 'tg';
//     case 'DEBUG': return 'tb';
//     default: return 'tgr';
//   }
// };
// // Method tag
// const methodTag = (m) => {
//   if (!m) return 'tgr';
//   switch (m.toUpperCase()) {
//     case 'GET': return 'tg'; case 'POST': return 'tb';
//     case 'PUT': case 'PATCH': return 'ta'; case 'DELETE': return 'tr';
//     default: return 'tgr';
//   }
// };

// // Avatar gradient by initial
// const avBg = (name) => {
//   const colors = [
//     'linear-gradient(135deg,#7c3aed,#2563eb)',
//     'linear-gradient(135deg,#059669,#0891b2)',
//     'linear-gradient(135deg,#d97706,#ea580c)',
//     'linear-gradient(135deg,#e11d48,#7c3aed)',
//     'linear-gradient(135deg,#2563eb,#0891b2)',
//   ];
//   const i = (name || 'A').charCodeAt(0) % colors.length;
//   return colors[i];
// };

// // ─── ACTION FILTERS ───────────────────────────────────────────────
// const ACT_FILTERS = [
//   { label:'All Events',       val:'',                          dot:'#a855f7' },
//   { label:'Login / Logout',   val:'LOGIN,LOGOUT',              dot:'#34d399' },
//   { label:'Profile Updates',  val:'PROFILE_UPDATE',            dot:'#a855f7' },
//   { label:'Password Change',  val:'PASSWORD_CHANGE',           dot:'#fbbf24' },
//   { label:'Deposits',         val:'DEPOSIT',                   dot:'#22d3ee' },
//   { label:'Withdrawals',      val:'WITHDRAWAL',                dot:'#fb923c' },
//   { label:'Offer Events',     val:'OFFER_VIEW,OFFER_CLICK,OFFER_COMPLETE', dot:'#60a5fa' },
// ];
// const LVL_FILTERS = [
//   { label:'All Levels',  val:'' },
//   { label:'Info',        val:'INFO' },
//   { label:'Warning',     val:'WARNING' },
//   { label:'Error',       val:'ERROR' },
//   { label:'Critical',    val:'CRITICAL' },
// ];

// // ═════════════════════════════════════════════════════════════════
// export default function AuditLogs() {
//   const [logs,    setLogs]   = useState(FB);
//   const [stats,   setStats]  = useState({ total_logs:0, logs_today:0, success_rate:0, error_logs:0, warning_logs:0 });
//   const [loading, setLoad]   = useState(false);
//   const [apiOk,   setApiOk]  = useState(false);
//   const [sel,     setSel]    = useState(null);
//   const [search,  setSearch] = useState('');
//   const [actF,    setActF]   = useState('');
//   const [lvlF,    setLvlF]   = useState('');
//   const [page,    setPage]   = useState(1);
//   const [total,   setTotal]  = useState(0);
//   const [timer,   setTimer]  = useState(30);
//   const PAGE = 20;
//   const ref = useRef();

//   const load = useCallback(async (showSpinner = false) => {
//     if (showSpinner) setLoad(true);
//     const p = new URLSearchParams({ page_size: PAGE, page, ordering: '-timestamp' });
//     if (search) p.set('search', search);
//     if (lvlF)   p.set('level', lvlF);
//     if (actF)   actF.split(',').forEach(a => p.append('action', a));

//     // GET /api/audit_logs/logs/ → AuditLogSerializer
//     const res = await apiFetch(`${BASE}/logs/?${p}`);
//     if (res) {
//       const list = toList(res);
//       if (list.length > 0 || res.count != null) {
//         setLogs(list); setTotal(res.count || list.length); setApiOk(true);
//       }
//     }
//     // GET /api/audit_logs/stats/ → AuditStatsSerializer
//     const st = await apiFetch(`${BASE}/stats/`);
//     if (st) { const s = st.data || st; if (s.total_logs != null) setStats(s); }
//     setTimer(30);
//     if (showSpinner) setLoad(false);
//   }, [page, search, actF, lvlF]);

//   useEffect(() => { load(true); }, [load]);

//   useEffect(() => {
//     ref.current = setInterval(() => setTimer(p => { if (p <= 1) { load(); return 30; } return p - 1; }), 1000);
//     return () => clearInterval(ref.current);
//   }, [load]);

//   const openDetail = async (log) => {
//     setSel(log);
//     const r = await apiFetch(`${BASE}/logs/${log.id}/`);
//     if (r) setSel(r.data || r);
//   };

//   const displayed = apiOk ? logs : logs.filter(l => {
//     if (search && !JSON.stringify(l).toLowerCase().includes(search.toLowerCase())) return false;
//     if (actF && !actF.split(',').includes(l.action)) return false;
//     if (lvlF && l.level !== lvlF) return false;
//     return true;
//   });

//   const ds = stats.total_logs > 0 ? stats : {
//     total_logs:  logs.length,
//     logs_today:  logs.filter(l => l.timestamp && new Date(l.timestamp).toDateString() === new Date().toDateString()).length,
//     success_rate:logs.length ? ((logs.filter(l=>l.success).length/logs.length)*100).toFixed(1) : 0,
//     error_logs:  logs.filter(l=>l.level==='ERROR'||l.level==='CRITICAL').length,
//     warning_logs:logs.filter(l=>l.level==='WARNING').length,
//   };

//   const totalPages = Math.max(1, Math.ceil((total || displayed.length) / PAGE));

//   // ── RENDER ─────────────────────────────────────────────────────
//   return (
//     <div className="al-root">
//       <div className="al-bg-mesh" /><div className="al-noise" />

//       {/* HEADER */}
//       <header className="al-header">
//         <div className="al-header-left">
//           <div className="al-logo">
//             <div className="al-logo-icon">{I.Shield}</div>
//             Audit Intelligence
//           </div>
//           <div className="al-vdiv" />
//           <div className="al-crumb">Admin Panel <span>/ Audit Logs</span></div>
//         </div>
//         <div className="al-header-right">
//           <div className="al-live"><div className="al-live-dot" />{apiOk ? 'API LIVE' : 'DEMO'}</div>
//           <div className="al-refresh-timer">sync <span>{timer}s</span></div>
//           <button className="al-hbtn" onClick={() => load(true)}>{I.Refresh} Refresh</button>
//           <button className="al-hbtn pri">{I.Download} Export</button>
//         </div>
//       </header>

//       {/* KPI CARDS */}
//       <div className="al-kpis">
//         {[
//           { cls:'kv', label:'Total Events',  val:(ds.total_logs||0).toLocaleString(), sub:'All time' },
//           { cls:'kg', label:'Success Rate',  val:`${parseFloat(ds.success_rate||0).toFixed(1)}%`, sub:'Healthy operations' },
//           { cls:'tr', label:'Errors',        val:(ds.error_logs||0), sub:'Need attention', cls2:'kr' },
//           { cls:'kb', label:'Today',         val:(ds.logs_today||0), sub:'Last 24 hours' },
//           { cls:'ka', label:'Warnings',      val:(ds.warning_logs||0), sub:'Review needed' },
//         ].map((k,i) => (
//           <div className={`al-kpi ${k.cls2||k.cls}`} key={i}>
//             <div className="al-kpi-bar" />
//             <div className="al-kpi-label">{k.label}</div>
//             <div className="al-kpi-val">{k.val}</div>
//             <div className="al-kpi-sub">{k.sub}</div>
//           </div>
//         ))}
//       </div>

//       {/* BODY */}
//       <div className="al-layout">
//         {/* SIDEBAR */}
//         <aside className="al-sidebar">
//           <div className="al-sb-title">Action Type</div>
//           {ACT_FILTERS.map((f,i) => (
//             <div key={i} className={`al-nav ${actF===f.val?'on':''}`} onClick={() => { setActF(f.val); setPage(1); }}>
//               <div className="al-nav-l">
//                 <div className="al-dot" style={{ background: f.dot }} />
//                 {f.label}
//               </div>
//             </div>
//           ))}
//           <div className="al-sep" />
//           <div className="al-sb-title">Severity</div>
//           {LVL_FILTERS.map((f,i) => (
//             <div key={i} className={`al-nav ${lvlF===f.val?'on':''}`} onClick={() => { setLvlF(f.val); setPage(1); }}>
//               <div className="al-nav-l">
//                 <div className="al-dot" style={{ background: f.val==='ERROR'||f.val==='CRITICAL'?'#fb7185':f.val==='WARNING'?'#fbbf24':f.val==='INFO'?'#34d399':'#475569' }} />
//                 {f.label}
//               </div>
//             </div>
//           ))}
//         </aside>

//         {/* MAIN */}
//         <div className="al-content">
//           {/* Toolbar */}
//           <div className="al-toolbar">
//             <div className="al-search">
//               {I.Search}
//               <input
//                 value={search}
//                 onChange={e => { setSearch(e.target.value); setPage(1); }}
//                 placeholder="Search by user, action, IP address, message..."
//               />
//             </div>
//             <div className="al-chips">
//               {['All','Success','Failed'].map((c,i) => (
//                 <div key={i} className={`al-chip ${i===0?'on':''}`}>{c}</div>
//               ))}
//             </div>
//           </div>

//           {/* Table */}
//           {loading ? (
//             <div className="al-loading"><div className="al-spin" /> Loading audit logs...</div>
//           ) : (
//             <div className="al-tw">
//               <table className="al-table">
//                 <thead>
//                   <tr>
//                     <th>Timestamp</th>
//                     <th>User</th>
//                     <th>Action</th>
//                     <th>Level</th>
//                     <th>Status</th>
//                     <th>IP Address</th>
//                     <th>Method</th>
//                     <th>Path</th>
//                     <th>Message</th>
//                     <th></th>
//                   </tr>
//                 </thead>
//                 <tbody>
//                   {displayed.map(log => (
//                     <tr key={log.id} className={sel?.id===log.id?'sel':''} onClick={() => openDetail(log)}>
//                       <td style={{ fontFamily:'var(--font-mono)', fontSize:'11px', color:'var(--text-muted)' }}>
//                         {fmtDt(log.timestamp || log.created_at)}
//                       </td>
//                       <td>
//                         <div className="al-ucell">
//                           <div className="al-av" style={{ background: avBg(log.user||'A') }}>
//                             {(log.user||'?')[0].toUpperCase()}
//                           </div>
//                           <span style={{ fontSize:'12px', fontWeight:600, color:'var(--text-primary)' }}>
//                             {log.user || 'Anonymous'}
//                           </span>
//                         </div>
//                       </td>
//                       <td><span className={`al-tag ${actionTag(log.action)}`}>{log.action_display || log.action || '—'}</span></td>
//                       <td><span className={`al-tag ${levelTag(log.level)}`}>{log.level_display || log.level || '—'}</span></td>
//                       <td>
//                         {log.success
//                           ? <span className="al-ok">{I.Check} OK</span>
//                           : <span className="al-fail">{I.X} Fail</span>
//                         }
//                       </td>
//                       <td style={{ fontFamily:'var(--font-mono)', fontSize:'11px' }}>
//                         {log.user_ip || log.ip_address || '—'}
//                       </td>
//                       <td>
//                         {log.request_method
//                           ? <span className={`al-tag ${methodTag(log.request_method)}`}>{log.request_method}</span>
//                           : <span style={{color:'var(--text-muted)'}}>—</span>
//                         }
//                       </td>
//                       <td style={{ fontFamily:'var(--font-mono)', fontSize:'10px', color:'var(--text-muted)', maxWidth:'140px', overflow:'hidden', textOverflow:'ellipsis' }}>
//                         {log.request_path || '—'}
//                       </td>
//                       <td style={{ maxWidth:'180px', overflow:'hidden', textOverflow:'ellipsis', color:'var(--text-muted)', fontSize:'11px' }}>
//                         {log.message || '—'}
//                       </td>
//                       <td onClick={e => { e.stopPropagation(); openDetail(log); }}>
//                         <button className="al-hbtn" style={{ padding:'4px 10px', fontSize:'11px' }}>{I.Eye}</button>
//                       </td>
//                     </tr>
//                   ))}
//                 </tbody>
//               </table>
//               {displayed.length === 0 && (
//                 <div className="al-empty">
//                   <div style={{fontSize:36, marginBottom:12, opacity:0.3}}>{I.Filter}</div>
//                   <div>No logs found — try adjusting your filters</div>
//                 </div>
//               )}
//             </div>
//           )}

//           {/* Pagination */}
//           <div className="al-pagination">
//             <span>
//               {displayed.length > 0
//                 ? `Showing ${((page-1)*PAGE)+1}–${Math.min(page*PAGE, total||displayed.length)} of ${(total||displayed.length).toLocaleString()} events`
//                 : 'No events'
//               }
//             </span>
//             <div className="al-pg">
//               <button className="al-pgb" onClick={() => setPage(p=>Math.max(1,p-1))} disabled={page===1}>‹</button>
//               {[...Array(Math.min(5, totalPages))].map((_,i) => (
//                 <button key={i} className={`al-pgb ${page===i+1?'on':''}`} onClick={() => setPage(i+1)}>{i+1}</button>
//               ))}
//               {totalPages > 5 && <button className="al-pgb" style={{width:'auto',padding:'0 10px'}}>…</button>}
//               <button className="al-pgb" onClick={() => setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages}>›</button>
//             </div>
//           </div>
//         </div>

//         {/* DETAIL PANEL */}
//         {sel && (
//           <aside className="al-detail">
//             <div className="al-dt-head">
//               <button className="al-dt-close" onClick={() => setSel(null)} style={{float:'right'}}>{I.X}</button>
//               <div className="al-dt-action">{sel.action_display || sel.action || 'Event Detail'}</div>
//               <div className="al-dt-tags">
//                 <span className={`al-tag ${levelTag(sel.level)}`}>{sel.level || '—'}</span>
//                 <span className={`al-tag ${sel.success?'tg':'tr'}`}>{sel.success ? 'Success' : 'Failed'}</span>
//                 {sel.request_method && <span className={`al-tag ${methodTag(sel.request_method)}`}>{sel.request_method}</span>}
//               </div>
//               <div className="al-dt-id">ID: {String(sel.id||'').substring(0,8).toUpperCase()}...</div>
//             </div>
//             <div className="al-dt-body">
//               {[
//                 { l:'User',          v: sel.user || 'Anonymous',               c:'' },
//                 { l:'Timestamp',     v: fmtDt(sel.timestamp||sel.created_at),  c:'' },
//                 { l:'IP Address',    v: sel.user_ip || sel.ip_address || '—',  c:'hi' },
//                 { l:'Country',       v: sel.country || '—',                    c:'' },
//                 { l:'City',          v: sel.city || '—',                       c:'' },
//                 { l:'Request Path',  v: sel.request_path || '—',               c:'' },
//                 { l:'Resource Type', v: sel.resource_type || '—',              c:'' },
//                 { l:'Resource ID',   v: sel.resource_id || '—',                c:'' },
//                 { l:'Status Code',   v: sel.status_code || '—',                c:'' },
//                 { l:'Response Time', v: sel.response_time_ms ? `${sel.response_time_ms}ms` : '—', c:'' },
//                 { l:'Message',       v: sel.message || '—',                    c:'' },
//                 { l:'Error',         v: sel.error_message || 'None',           c: sel.error_message ? 'err' : '' },
//               ].map((r,i) => (
//                 <div className="al-dt-row" key={i}>
//                   <div className="al-dt-lbl">{r.l}</div>
//                   <div className={`al-dt-val ${r.c}`}>{r.v}</div>
//                 </div>
//               ))}
//               {sel.metadata && Object.keys(sel.metadata).length > 0 && (
//                 <div className="al-dt-row">
//                   <div className="al-dt-lbl">Metadata</div>
//                   <pre style={{ fontFamily:'var(--font-mono)', fontSize:'10px', color:'var(--text-muted)', margin:0, whiteSpace:'pre-wrap', wordBreak:'break-all' }}>
//                     {JSON.stringify(sel.metadata, null, 2)}
//                   </pre>
//                 </div>
//               )}
//             </div>
//           </aside>
//         )}
//       </div>
//     </div>
//   );
// }