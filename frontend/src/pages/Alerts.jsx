// src/pages/Alerts.jsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import client from '../api/client';

// ─── ICONS ────────────────────────────────────────────────────────────────────
const Icon = ({ d, size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const IC = {
  bell:    "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  check:   "M20 6L9 17l-5-5",
  x:       "M18 6L6 18 M6 6l12 12",
  alert:   "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
  shield:  "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  refresh: "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  search:  "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  plus:    "M12 5v14 M5 12h14",
  edit:    "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  trash:   "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
  toggle:  "M9 12l2 2 4-4 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  play:    "M5 3l14 9-14 9V3z",
  chevR:   "M9 18l6-6-6-6",
  chevL:   "M15 18l-6-6 6-6",
  heart:   "M22 12h-4l-3 9L9 3l-3 9H2",
  sq:      "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  sqOk:    "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
};

// ─── SEVERITY CONFIG ──────────────────────────────────────────────────────────
const SEV = {
  critical: { color: '#ff2244', bg: '#ff224418', label: 'CRITICAL' },
  high:     { color: '#ff6600', bg: '#ff660018', label: 'HIGH' },
  medium:   { color: '#ffcc00', bg: '#ffcc0018', label: 'MEDIUM' },
  low:      { color: '#00ff88', bg: '#00ff8818', label: 'LOW' },
  info:     { color: '#00d4ff', bg: '#00d4ff18', label: 'INFO' },
};

const ALERT_TYPES = [
  'high_earning', 'mass_signup', 'payment_spike',
  'fraud_spike', 'server_error', 'low_balance',
];

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const T = {
  bg: '#010810', bgC: '#020c18', bgP: '#030f1e',
  primary: '#00d4ff', border: '#00d4ff18', borderMd: '#00d4ff33', borderSt: '#00d4ff55',
  text: '#cce8ff', textMuted: '#4a7a99',
  glow: '#00d4ff30', grad: 'linear-gradient(135deg,#00d4ff15,#0099cc08)',
};

const Spin = () => <span style={{ display:'inline-block', width:12, height:12, border:'2px solid currentColor', borderTopColor:'transparent', borderRadius:'50%', animation:'aspin 1s linear infinite' }} />;
const SK = ({ w='100%', h=12 }) => <div style={{ width:w, height:h, borderRadius:4, background:'linear-gradient(90deg,#0d2137 25%,#1a3a5c44 50%,#0d2137 75%)', backgroundSize:'200% 100%', animation:'ashimmer 1.5s infinite' }} />;

function useToast() {
  const [list, setList] = useState([]);
  const add = useCallback((msg, type='ok') => {
    const id = Date.now();
    setList(p => [...p, {id,msg,type}]);
    setTimeout(() => setList(p => p.filter(t => t.id!==id)), 3200);
  }, []);
  return { list, add };
}

const Toasts = ({ list }) => (
  <div style={{ position:'fixed', bottom:20, right:20, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
    {list.map(t => {
      const c = t.type==='err'?'#ff2244':t.type==='warn'?'#ffcc00':'#00ff88';
      return <div key={t.id} style={{ padding:'10px 16px', borderRadius:8, background:`${c}18`, border:`1px solid ${c}44`, color:c, fontSize:12, fontFamily:"'Courier New',monospace", animation:'afadeUp .3s ease', display:'flex', alignItems:'center', gap:8 }}>{t.type==='err'?'✗':t.type==='warn'?'⚠':'✓'} {t.msg}</div>;
    })}
  </div>
);

const SevBadge = ({ severity }) => {
  const s = SEV[severity] || SEV.info;
  return <span style={{ display:'inline-flex', alignItems:'center', gap:4, color:s.color, background:s.bg, border:`1px solid ${s.color}44`, borderRadius:20, padding:'2px 8px', fontSize:10, fontWeight:700, fontFamily:"'Courier New',monospace" }}><span style={{ width:5, height:5, borderRadius:'50%', background:s.color, display:'inline-block' }}/>{s.label}</span>;
};

const Stat = ({ label, value, icon, color, loading }) => (
  <div style={{ background:T.bgC, border:`1px solid ${color}33`, borderTop:`2px solid ${color}`, borderRadius:10, padding:'14px 16px', position:'relative', overflow:'hidden' }}>
    <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:8 }}>
      <span style={{ color }}><Icon d={icon} size={12}/></span>
      <span style={{ color:T.textMuted, fontSize:9, fontWeight:700, letterSpacing:'.1em', fontFamily:"'Courier New',monospace" }}>{label}</span>
    </div>
    {loading ? <SK h={22} w={50}/> : <div style={{ fontSize:24, fontWeight:900, color, fontFamily:"'Courier New',monospace", textShadow:`0 0 16px ${color}60` }}>{value}</div>}
  </div>
);

const Btn = ({ icon, label, color, onClick, loading, small=false, disabled=false }) => (
  <button onClick={onClick} disabled={loading||disabled}
    style={{ background:`${color}16`, border:`1px solid ${color}33`, borderRadius:6, padding:small?'5px 9px':'8px 14px', color, fontSize:10, fontWeight:700, cursor:(loading||disabled)?'not-allowed':'pointer', fontFamily:"'Courier New',monospace", display:'flex', alignItems:'center', gap:5, opacity:(loading||disabled)?.6:1, transition:'all .2s' }}
    onMouseEnter={e=>{ if(!loading&&!disabled) e.currentTarget.style.background=`${color}28`; }}
    onMouseLeave={e=>e.currentTarget.style.background=`${color}16`}>
    {loading?<Spin />:<Icon d={icon} size={11}/>} {label}
  </button>
);

const LabelIn = ({ label, children }) => (
  <div><div style={{ fontSize:10, color:T.textMuted, letterSpacing:'.1em', fontFamily:"'Courier New',monospace", marginBottom:5 }}>{label}</div>{children}</div>
);

const INP_STYLE = { width:'100%', background:T.bgP, border:`1px solid ${T.borderMd}`, borderRadius:8, padding:'9px 12px', color:T.text, fontSize:12, outline:'none', boxSizing:'border-box', fontFamily:"'Courier New',monospace" };

// ─── RULE MODAL ───────────────────────────────────────────────────────────────
const RuleModal = ({ rule, onClose, onSaved, toast }) => {
  const isEdit = !!rule?.id;
  const [form, setForm] = useState({
    name:                 rule?.name || '',
    alert_type:           rule?.alert_type || 'custom',
    severity:             rule?.severity || 'medium',
    description:          rule?.description || '',
    threshold_value:      rule?.threshold_value ?? 0,
    time_window_minutes:  rule?.time_window_minutes ?? 60,
    cooldown_minutes:     rule?.cooldown_minutes ?? 30,
    email_recipients:     rule?.email_recipients || '',
    send_email:           rule?.send_email ?? true,
    send_telegram:        rule?.send_telegram ?? false,
    send_sms:             rule?.send_sms ?? false,
    send_webhook:         rule?.send_webhook ?? false,
    webhook_url:          rule?.webhook_url || '',
    is_active:            rule?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const submit = async () => {
    if (!form.name.trim()) { toast('Name required','err'); return; }
    setSaving(true);
    try {
      if (isEdit) {
        await client.patch(`/alerts/rules/${rule.id}/`, form);
        toast('Rule updated ✓');
      } else {
        await client.post('/alerts/rules/create/', form);
        toast('Rule created ✓');
      }
      onSaved(); onClose();
    } catch(e) { toast(e?.response?.data?.error||'Failed','err'); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ position:'fixed', inset:0, zIndex:1000, background:'#000c', backdropFilter:'blur(6px)', display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ background:T.bgC, border:`1px solid ${T.borderSt}`, borderRadius:14, padding:26, width:620, maxWidth:'96vw', maxHeight:'90vh', overflowY:'auto', boxShadow:`0 24px 80px ${T.glow}`, animation:'afadeUp .3s ease' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:7, height:7, borderRadius:'50%', background:T.primary, animation:'apulse 1.5s infinite' }} />
            <span style={{ fontSize:14, fontWeight:800, color:T.text, fontFamily:"'Courier New',monospace" }}>{isEdit?`EDIT — ${rule.name}`:'NEW ALERT RULE'}</span>
          </div>
          <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', color:T.textMuted }}><Icon d={IC.x} size={16}/></button>
        </div>

        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
          <div style={{ gridColumn:'1/-1' }}>
            <LabelIn label="RULE NAME *">
              <input value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. High Withdrawal Alert"
                style={INP_STYLE} onFocus={e=>e.target.style.borderColor=T.borderSt} onBlur={e=>e.target.style.borderColor=T.borderMd}/>
            </LabelIn>
          </div>
          <LabelIn label="ALERT TYPE">
            <select value={form.alert_type} onChange={e=>set('alert_type',e.target.value)} style={INP_STYLE}>
              {ALERT_TYPES.map(t=><option key={t} value={t}>{t.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</option>)}
            </select>
          </LabelIn>
          <LabelIn label="SEVERITY">
            <select value={form.severity} onChange={e=>set('severity',e.target.value)} style={INP_STYLE}>
              {Object.entries(SEV).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
            </select>
          </LabelIn>
          <LabelIn label="THRESHOLD VALUE">
            <input type="number" value={form.threshold_value} onChange={e=>set('threshold_value',+e.target.value)} style={INP_STYLE}/>
          </LabelIn>
          <LabelIn label="TIME WINDOW (min)">
            <input type="number" value={form.time_window_minutes} onChange={e=>set('time_window_minutes',+e.target.value)} style={INP_STYLE}/>
          </LabelIn>
          <LabelIn label="COOLDOWN (min)">
            <input type="number" value={form.cooldown_minutes} onChange={e=>set('cooldown_minutes',+e.target.value)} style={INP_STYLE}/>
          </LabelIn>
          <LabelIn label="EMAIL RECIPIENTS">
            <input value={form.email_recipients} onChange={e=>set('email_recipients',e.target.value)} placeholder="email1@x.com, email2@x.com" style={INP_STYLE}/>
          </LabelIn>
          <div style={{ gridColumn:'1/-1' }}>
            <LabelIn label="DESCRIPTION">
              <textarea value={form.description} onChange={e=>set('description',e.target.value)} rows={2}
                style={{ ...INP_STYLE, resize:'vertical' }}/>
            </LabelIn>
          </div>

          {/* Notification toggles */}
          <div style={{ gridColumn:'1/-1', background:T.bgP, borderRadius:8, padding:'12px 14px', border:`1px solid ${T.border}` }}>
            <div style={{ fontSize:10, color:T.textMuted, letterSpacing:'.1em', fontFamily:"'Courier New',monospace", marginBottom:10 }}>NOTIFICATIONS</div>
            <div style={{ display:'flex', gap:16, flexWrap:'wrap' }}>
              {[['send_email','📧 Email'],['send_telegram','✈️ Telegram'],['send_sms','📱 SMS'],['send_webhook','🔗 Webhook']].map(([k,l])=>(
                <label key={k} style={{ display:'flex', alignItems:'center', gap:7, cursor:'pointer', fontSize:12, color:T.text }}>
                  <input type="checkbox" checked={!!form[k]} onChange={e=>set(k,e.target.checked)}/> {l}
                </label>
              ))}
            </div>
            {form.send_webhook && (
              <div style={{ marginTop:10 }}>
                <LabelIn label="WEBHOOK URL">
                  <input value={form.webhook_url} onChange={e=>set('webhook_url',e.target.value)} placeholder="https://..." style={INP_STYLE}/>
                </LabelIn>
              </div>
            )}
          </div>

          <div style={{ gridColumn:'1/-1', display:'flex', alignItems:'center', gap:10 }}>
            <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', fontSize:12, color:T.text }}>
              <input type="checkbox" checked={!!form.is_active} onChange={e=>set('is_active',e.target.checked)}/> Rule Active
            </label>
          </div>
        </div>

        <div style={{ display:'flex', gap:10, marginTop:20 }}>
          <button onClick={onClose} style={{ flex:1, background:T.border, border:`1px solid ${T.borderMd}`, borderRadius:8, padding:11, color:T.textMuted, fontSize:11, cursor:'pointer', fontFamily:"'Courier New',monospace" }}>CANCEL</button>
          <button onClick={submit} disabled={saving} style={{ flex:2, background:`${T.primary}20`, border:`1px solid ${T.borderSt}`, borderRadius:8, padding:11, color:T.primary, fontSize:11, fontWeight:700, cursor:'pointer', fontFamily:"'Courier New',monospace", display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
            {saving?<Spin />:<Icon d={IC.check} size={12}/>} {saving?'SAVING…':isEdit?'UPDATE RULE':'CREATE RULE'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── LOG RESOLVE MODAL ────────────────────────────────────────────────────────
const ResolveModal = ({ log, onClose, onDone, toast }) => {
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const resolve = async () => {
    setSaving(true);
    try {
      await client.post(`/alerts/logs/${log.id}/resolve/`, { note: note||'Manually resolved' });
      toast('Alert resolved ✓'); onDone(); onClose();
    } catch(e) { toast(e?.response?.data?.error||'Failed','err'); }
    finally { setSaving(false); }
  };
  return (
    <div style={{ position:'fixed', inset:0, zIndex:1000, background:'#000c', backdropFilter:'blur(6px)', display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ background:T.bgC, border:`1px solid ${T.borderSt}`, borderRadius:12, padding:24, width:400, maxWidth:'92vw', animation:'afadeUp .2s ease' }}>
        <div style={{ fontSize:13, fontWeight:700, color:T.text, fontFamily:"'Courier New',monospace", marginBottom:14 }}>RESOLVE ALERT</div>
        <div style={{ fontSize:12, color:T.textMuted, marginBottom:14, fontFamily:"'Courier New',monospace" }}>{log.message}</div>
        <LabelIn label="RESOLUTION NOTE">
          <textarea value={note} onChange={e=>setNote(e.target.value)} rows={2} placeholder="What was done to fix this?"
            style={{ ...INP_STYLE, resize:'vertical' }}/>
        </LabelIn>
        <div style={{ display:'flex', gap:10, marginTop:14 }}>
          <button onClick={onClose} style={{ flex:1, background:T.border, border:`1px solid ${T.borderMd}`, borderRadius:8, padding:10, color:T.textMuted, fontSize:11, cursor:'pointer', fontFamily:"'Courier New',monospace" }}>CANCEL</button>
          <button onClick={resolve} disabled={saving} style={{ flex:2, background:'#00ff8820', border:'1px solid #00ff8855', borderRadius:8, padding:10, color:'#00ff88', fontSize:11, fontWeight:700, cursor:'pointer', fontFamily:"'Courier New',monospace", display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
            {saving?<Spin />:<Icon d={IC.check} size={12}/>} RESOLVE
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function AlertsPage() {
  const [tab, setTab]           = useState('logs');
  const [overview, setOverview] = useState(null);
  const [rules, setRules]       = useState([]);
  const [logs, setLogs]         = useState([]);
  const [health, setHealth]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch]     = useState('');
  const [sevFilter, setSevFilter] = useState('');
  const [resolvedFilter, setResolvedFilter] = useState('');
  const [page, setPage]         = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selected, setSelected] = useState([]);
  const [ruleModal, setRuleModal] = useState(null);
  const [resolveModal, setResolveModal] = useState(null);
  const [toggling, setToggling] = useState(null);
  const [testing, setTesting]   = useState(null);
  const [deleting, setDeleting] = useState(null);
  const { list: toasts, add: toast } = useToast();

  const fetchAll = useCallback(async (silent=false) => {
    if (!silent) setLoading(true); else setRefreshing(true);
    try {
      const [ov, rl, lg, hl] = await Promise.all([
        client.get('/alerts/'),
        client.get('/alerts/rules/'),
        client.get(`/alerts/logs/?page=${page}${sevFilter?`&severity=${sevFilter}`:''}${resolvedFilter!==''?`&is_resolved=${resolvedFilter}`:''}`),
        client.get('/alerts/health/'),
      ]);
      setOverview(ov.data);
      setRules(rl.data || []);
      setLogs(lg.data?.results || lg.data || []);
      setTotalPages(lg.data?.total_pages || 1);
      setHealth(hl.data);
    } catch(_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, [page, sevFilter, resolvedFilter]);

  useEffect(() => { fetchAll(); }, [page, sevFilter, resolvedFilter]);

  const toggleRule = async (rule) => {
    setToggling(rule.id);
    try {
      await client.post(`/alerts/rules/${rule.id}/toggle/`);
      setRules(x => x.map(r => r.id===rule.id ? {...r, is_active:!r.is_active} : r));
      toast(`"${rule.name}" ${rule.is_active?'paused':'activated'}`);
    } catch { toast('Failed','err'); }
    finally { setToggling(null); }
  };

  const testRule = async (rule) => {
    setTesting(rule.id);
    try {
      await client.post(`/alerts/rules/${rule.id}/test/`);
      toast(`Test alert sent for "${rule.name}"`);
    } catch { toast('Test failed','err'); }
    finally { setTesting(null); }
  };

  const deleteRule = async (rule) => {
    if (!window.confirm(`Delete rule "${rule.name}"?`)) return;
    try {
      await client.delete(`/alerts/rules/${rule.id}/`);
      setRules(x => x.filter(r => r.id!==rule.id));
      toast('Rule deleted');
    } catch { toast('Delete failed','err'); }
  };

  const deleteLog = async (log) => {
    setDeleting(log.id);
    try {
      await client.delete(`/alerts/logs/${log.id}/delete/`);
      setLogs(x => x.filter(l => l.id!==log.id));
      toast('Log deleted');
    } catch { toast('Failed','err'); }
    finally { setDeleting(null); }
  };

  const bulkResolve = async () => {
    if (!selected.length) return;
    try {
      await client.post('/alerts/logs/bulk-resolve/', { ids: selected });
      toast(`${selected.length} alerts resolved`);
      setSelected([]); fetchAll(true);
    } catch { toast('Bulk resolve failed','err'); }
  };

  const filteredRules = rules.filter(r =>
    !search || r.name?.toLowerCase().includes(search.toLowerCase()) || r.alert_type?.includes(search.toLowerCase())
  );
  const filteredLogs = logs.filter(l =>
    !search || l.message?.toLowerCase().includes(search.toLowerCase()) || l.rule__name?.toLowerCase().includes(search.toLowerCase())
  );

  const TH = ({ children, w }) => <th style={{ padding:'10px 14px', fontSize:9, color:T.textMuted, letterSpacing:'.1em', fontFamily:"'Courier New',monospace", fontWeight:700, textAlign:'left', borderBottom:`1px solid ${T.border}`, whiteSpace:'nowrap', width:w }}>{children}</th>;
  const TD = ({ children, style:st={} }) => <td style={{ padding:'10px 14px', fontSize:11, color:T.text, fontFamily:"'Courier New',monospace", borderBottom:`1px solid ${T.border}18`, ...st }}>{children}</td>;

  const statusColor = health?.overall_status === 'healthy' ? '#00ff88' : health?.overall_status === 'degraded' ? '#ffcc00' : '#ff2244';

  return (
    <div style={{ minHeight:'100vh', background:T.bg, color:T.text, fontFamily:"'Segoe UI',sans-serif" }}>
      <style>{`
        @keyframes afadeUp  { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes ashimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes apulse   { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes aspin    { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-thumb{background:${T.borderMd};border-radius:4px}
        .arow:hover td{background:#0a1628!important}
        select option{background:#020c18}
      `}</style>

      {/* Header */}
      <div style={{ borderBottom:`1px solid ${T.border}`, padding:'18px 26px 14px', background:'linear-gradient(180deg,#040c18,transparent)' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:12 }}>
          <div style={{ display:'flex', alignItems:'center', gap:14 }}>
            <div style={{ width:44, height:44, borderRadius:10, background:T.grad, border:`1px solid ${T.borderSt}`, display:'flex', alignItems:'center', justifyContent:'center', boxShadow:`0 0 20px ${T.glow}` }}>
              <span style={{ color:T.primary }}><Icon d={IC.bell} size={20}/></span>
            </div>
            <div>
              <h1 style={{ fontSize:20, fontWeight:900, letterSpacing:'.08em', fontFamily:"'Courier New',monospace", margin:0, color:T.primary, textShadow:`0 0 20px ${T.glow}` }}>ALERTS & MONITORING</h1>
              <p style={{ fontSize:10, color:T.textMuted, margin:0, fontFamily:"'Courier New',monospace" }}>
                {overview ? `${overview.active_rules} ACTIVE RULES · ${overview.unresolved_alerts} UNRESOLVED · System: ` : 'Loading… · System: '}
                <span style={{ color: statusColor }}>{health?.overall_status?.toUpperCase() || '—'}</span>
              </p>
            </div>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            <Btn icon={IC.refresh} label="REFRESH" color={T.primary} onClick={()=>fetchAll(true)} loading={refreshing}/>
            <Btn icon={IC.plus} label="NEW RULE" color="#00ff88" onClick={()=>setRuleModal({})}/>
          </div>
        </div>
      </div>

      <div style={{ padding:'18px 26px' }}>
        {/* Stats */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(140px,1fr))', gap:12, marginBottom:22 }}>
          <Stat label="TOTAL RULES"    value={overview?.total_rules??'—'}       icon={IC.shield}  color={T.primary}  loading={loading&&!overview}/>
          <Stat label="ACTIVE RULES"   value={overview?.active_rules??'—'}      icon={IC.toggle}  color="#00ff88"    loading={loading&&!overview}/>
          <Stat label="TODAY"          value={overview?.alerts_today??'—'}       icon={IC.bell}    color="#ffcc00"    loading={loading&&!overview}/>
          <Stat label="THIS WEEK"      value={overview?.alerts_this_week??'—'}   icon={IC.bell}    color="#f97316"    loading={loading&&!overview}/>
          <Stat label="UNRESOLVED"     value={overview?.unresolved_alerts??'—'}  icon={IC.alert}   color="#ff2244"    loading={loading&&!overview}/>
          <Stat label="CRITICAL"       value={overview?.critical_active??'—'}    icon={IC.alert}   color="#ff2244"    loading={loading&&!overview}/>
          <Stat label="SYSTEM"         value={health?.overall_status?.toUpperCase()||'—'} icon={IC.heart} color={statusColor} loading={loading&&!health}/>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex', borderBottom:`1px solid ${T.border}`, marginBottom:18 }}>
          {[{k:'logs',l:'ALERT LOGS'},{k:'rules',l:'RULES'},{k:'health',l:'SYSTEM HEALTH'}].map(t=>(
            <button key={t.k} onClick={()=>setTab(t.k)} style={{ background:'none', border:'none', borderBottom:`2px solid ${tab===t.k?T.primary:'transparent'}`, padding:'8px 18px', color:tab===t.k?T.primary:T.textMuted, fontSize:11, cursor:'pointer', fontFamily:"'Courier New',monospace", fontWeight:700, letterSpacing:'.08em', marginBottom:-1 }}>
              {t.l}
            </button>
          ))}
        </div>

        {/* Search + Filters */}
        {tab !== 'health' && (
          <div style={{ display:'flex', gap:10, marginBottom:14, flexWrap:'wrap', alignItems:'center' }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, background:T.bgC, border:`1px solid ${T.border}`, borderRadius:8, padding:'8px 14px', flex:1, minWidth:200 }}>
              <Icon d={IC.search} size={12}/>
              <input placeholder={tab==='rules'?"Search rules…":"Search alerts…"} value={search} onChange={e=>setSearch(e.target.value)}
                style={{ background:'none', border:'none', outline:'none', color:T.text, fontSize:11, width:'100%', fontFamily:"'Courier New',monospace" }}/>
            </div>
            {/* Severity filter */}
            {['','critical','high','medium','low','info'].map(s=>(
              <button key={s} onClick={()=>{ setSevFilter(s); setPage(1); }}
                style={{ background:sevFilter===s?`${T.primary}20`:'transparent', border:`1px solid ${sevFilter===s?T.primary:T.border}`, borderRadius:20, padding:'6px 12px', color:sevFilter===s?T.primary:T.textMuted, fontSize:10, cursor:'pointer', fontFamily:"'Courier New',monospace" }}>
                {s===''?'ALL SEV':s.toUpperCase()}
              </button>
            ))}
            {/* Resolved filter (logs only) */}
            {tab==='logs' && (
              <>
                {[{v:'',l:'ALL'},{v:'false',l:'OPEN'},{v:'true',l:'RESOLVED'}].map(f=>(
                  <button key={f.v} onClick={()=>{ setResolvedFilter(f.v); setPage(1); }}
                    style={{ background:resolvedFilter===f.v?`${T.primary}20`:'transparent', border:`1px solid ${resolvedFilter===f.v?T.primary:T.border}`, borderRadius:20, padding:'6px 12px', color:resolvedFilter===f.v?T.primary:T.textMuted, fontSize:10, cursor:'pointer', fontFamily:"'Courier New',monospace" }}>
                    {f.l}
                  </button>
                ))}
              </>
            )}
          </div>
        )}

        {/* Bulk bar */}
        {tab==='logs' && selected.length>0 && (
          <div style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 14px', background:`${T.primary}10`, border:`1px solid ${T.borderMd}`, borderRadius:8, marginBottom:12, animation:'afadeUp .2s ease' }}>
            <span style={{ fontSize:11, color:T.primary, fontFamily:"'Courier New',monospace", fontWeight:700 }}>{selected.length} SELECTED</span>
            <Btn icon={IC.check} label="BULK RESOLVE" color="#00ff88" onClick={bulkResolve}/>
            <button onClick={()=>setSelected([])} style={{ marginLeft:'auto', background:'none', border:'none', color:T.textMuted, cursor:'pointer' }}><Icon d={IC.x} size={14}/></button>
          </div>
        )}

        {/* ── LOGS TAB ─────────────────────────────────────────────────────── */}
        {tab==='logs' && (
          <div style={{ overflowX:'auto', borderRadius:12, border:`1px solid ${T.border}`, animation:'afadeUp .3s ease' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:T.bgC }}>
              <thead><tr style={{ background:T.bgP }}>
                <TH w={36}><div onClick={()=>setSelected(selected.length===filteredLogs.length?[]:filteredLogs.map(l=>l.id))} style={{ cursor:'pointer', color:T.textMuted }}><Icon d={selected.length===filteredLogs.length&&filteredLogs.length>0?IC.sqOk:IC.sq} size={13}/></div></TH>
                <TH>RULE</TH><TH>SEVERITY</TH><TH>MESSAGE</TH><TH>TRIGGERED</TH><TH>STATUS</TH><TH>ACTIONS</TH>
              </tr></thead>
              <tbody>
                {loading
                  ? Array(8).fill(0).map((_,i)=><tr key={i}>{[0,1,2,3,4,5,6].map(j=><td key={j} style={{ padding:'12px 14px' }}><SK/></td>)}</tr>)
                  : filteredLogs.length===0
                    ? <tr><td colSpan={7} style={{ padding:'50px', textAlign:'center', color:T.textMuted, fontFamily:"'Courier New',monospace" }}>🔔 NO ALERTS FOUND</td></tr>
                    : filteredLogs.map(l=>(
                      <tr key={l.id} className="arow">
                        <TD><div onClick={()=>setSelected(p=>p.includes(l.id)?p.filter(x=>x!==l.id):[...p,l.id])} style={{ cursor:'pointer', color:selected.includes(l.id)?T.primary:T.textMuted }}><Icon d={selected.includes(l.id)?IC.sqOk:IC.sq} size={13}/></div></TD>
                        <TD><div style={{ color:T.primary, fontWeight:700 }}>{l.rule__name||'—'}</div><div style={{ color:T.textMuted, fontSize:9 }}>{l.rule__alert_type?.replace(/_/g,' ')}</div></TD>
                        <TD><SevBadge severity={l.rule__severity}/></TD>
                        <TD style={{ maxWidth:280 }}><div style={{ overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:T.text }}>{l.message}</div></TD>
                        <TD style={{ color:T.textMuted, fontSize:10 }}>{l.triggered_at?new Date(l.triggered_at).toLocaleString():'—'}</TD>
                        <TD>{l.is_resolved
                          ? <span style={{ color:'#00ff88', fontSize:11, fontFamily:"'Courier New',monospace" }}>✓ Resolved</span>
                          : <span style={{ color:'#ff2244', fontSize:11, fontFamily:"'Courier New',monospace" }}>● Open</span>}
                        </TD>
                        <TD>
                          <div style={{ display:'flex', gap:5 }}>
                            {!l.is_resolved && <Btn icon={IC.check} label="RESOLVE" color="#00ff88" onClick={()=>setResolveModal(l)} small/>}
                            <Btn icon={IC.trash} label="" color="#ff2244" onClick={()=>deleteLog(l)} loading={deleting===l.id} small/>
                          </div>
                        </TD>
                      </tr>
                    ))}
              </tbody>
            </table>
            {/* Pagination */}
            {totalPages>1 && (
              <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8, padding:'14px' }}>
                <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1} style={{ background:T.bgC, border:`1px solid ${T.borderMd}`, borderRadius:6, padding:'6px 10px', color:page===1?T.border:T.textMuted, cursor:page===1?'not-allowed':'pointer' }}><Icon d={IC.chevL} size={12}/></button>
                <span style={{ fontSize:11, color:T.textMuted, fontFamily:"'Courier New',monospace" }}>PAGE <span style={{ color:T.primary, fontWeight:700 }}>{page}</span> / {totalPages}</span>
                <button onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages} style={{ background:T.bgC, border:`1px solid ${T.borderMd}`, borderRadius:6, padding:'6px 10px', color:page===totalPages?T.border:T.textMuted, cursor:page===totalPages?'not-allowed':'pointer' }}><Icon d={IC.chevR} size={12}/></button>
              </div>
            )}
          </div>
        )}

        {/* ── RULES TAB ────────────────────────────────────────────────────── */}
        {tab==='rules' && (
          <div style={{ overflowX:'auto', borderRadius:12, border:`1px solid ${T.border}`, animation:'afadeUp .3s ease' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:T.bgC }}>
              <thead><tr style={{ background:T.bgP }}>
                <TH>RULE NAME</TH><TH>TYPE</TH><TH>SEVERITY</TH><TH>THRESHOLD</TH><TH>TRIGGERS</TH><TH>STATUS</TH><TH>LAST TRIGGERED</TH><TH>ACTIONS</TH>
              </tr></thead>
              <tbody>
                {loading
                  ? Array(6).fill(0).map((_,i)=><tr key={i}>{[0,1,2,3,4,5,6,7].map(j=><td key={j} style={{ padding:'12px 14px' }}><SK/></td>)}</tr>)
                  : filteredRules.length===0
                    ? <tr><td colSpan={8} style={{ padding:'50px', textAlign:'center', color:T.textMuted, fontFamily:"'Courier New',monospace" }}>🛡️ NO RULES FOUND</td></tr>
                    : filteredRules.map(r=>(
                      <tr key={r.id} className="arow">
                        <TD><div style={{ color:T.primary, fontWeight:700 }}>{r.name}</div></TD>
                        <TD><span style={{ color:'#bb44ff', fontSize:11 }}>{r.alert_type?.replace(/_/g,' ')}</span></TD>
                        <TD><SevBadge severity={r.severity}/></TD>
                        <TD style={{ color:T.textMuted }}>{r.threshold_value} / {r.time_window_minutes}min</TD>
                        <TD><div style={{ color:T.primary, fontWeight:700 }}>{r.trigger_count||0}</div></TD>
                        <TD><span className={`badge`} style={{ color:r.is_active?'#00ff88':'#ff2244', background:r.is_active?'#00ff8818':'#ff224418', border:`1px solid ${r.is_active?'#00ff8844':'#ff224444'}`, borderRadius:20, padding:'3px 9px', fontSize:10, fontFamily:"'Courier New',monospace" }}>{r.is_active?'ACTIVE':'PAUSED'}</span></TD>
                        <TD style={{ color:T.textMuted, fontSize:10 }}>{r.last_triggered?new Date(r.last_triggered).toLocaleString():'Never'}</TD>
                        <TD>
                          <div style={{ display:'flex', gap:5 }}>
                            <Btn icon={IC.play} label="" color="#ffcc00" onClick={()=>testRule(r)} loading={testing===r.id} small title="Test"/>
                            <Btn icon={r.is_active?IC.x:IC.check} label="" color={r.is_active?'#ff6600':'#00ff88'} onClick={()=>toggleRule(r)} loading={toggling===r.id} small/>
                            <Btn icon={IC.edit} label="" color={T.primary} onClick={()=>setRuleModal(r)} small/>
                            <Btn icon={IC.trash} label="" color="#ff2244" onClick={()=>deleteRule(r)} small/>
                          </div>
                        </TD>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── HEALTH TAB ───────────────────────────────────────────────────── */}
        {tab==='health' && (
          <div style={{ animation:'afadeUp .3s ease' }}>
            <div style={{ display:'flex', alignItems:'center', gap:12, padding:'16px 20px', background:`${statusColor}12`, border:`1px solid ${statusColor}33`, borderRadius:10, marginBottom:18 }}>
              <Icon d={IC.heart} size={18}/>
              <div>
                <div style={{ fontSize:11, color:T.textMuted, fontFamily:"'Courier New',monospace", marginBottom:4 }}>OVERALL SYSTEM STATUS</div>
                <div style={{ fontSize:20, fontWeight:900, color:statusColor, fontFamily:"'Courier New',monospace" }}>{health?.overall_status?.toUpperCase()||'UNKNOWN'}</div>
              </div>
            </div>
            {loading
              ? <div style={{ display:'grid', gap:10 }}>{Array(5).fill(0).map((_,i)=><SK key={i} h={52}/>)}</div>
              : (health?.checks||[]).length===0
                ? <div style={{ textAlign:'center', padding:40, color:T.textMuted, fontFamily:"'Courier New',monospace" }}>No health check data available.</div>
                : (health?.checks||[]).map((c,i)=>{
                    const col = c.status==='healthy'?'#00ff88':c.status==='degraded'?'#ffcc00':'#ff2244';
                    return (
                      <div key={i} style={{ display:'flex', alignItems:'center', gap:14, padding:'12px 16px', background:T.bgC, border:`1px solid ${col}22`, borderRadius:8, marginBottom:8 }}>
                        <div style={{ width:8, height:8, borderRadius:'50%', background:col, flexShrink:0 }}/>
                        <div style={{ flex:1 }}>
                          <div style={{ fontSize:12, fontWeight:700, color:T.text, fontFamily:"'Courier New',monospace" }}>{c.component}</div>
                          {c.message && <div style={{ fontSize:11, color:T.textMuted }}>{c.message}</div>}
                        </div>
                        <div style={{ textAlign:'right' }}>
                          <span style={{ color:col, fontSize:11, fontWeight:700, fontFamily:"'Courier New',monospace" }}>{c.status?.toUpperCase()}</span>
                          {c.response_time_ms && <div style={{ fontSize:10, color:T.textMuted, fontFamily:"'Courier New',monospace" }}>{c.response_time_ms}ms</div>}
                        </div>
                      </div>
                    );
                  })}
          </div>
        )}
      </div>

      {ruleModal !== null && <RuleModal rule={ruleModal?.id?ruleModal:null} onClose={()=>setRuleModal(null)} onSaved={()=>fetchAll(true)} toast={toast}/>}
      {resolveModal && <ResolveModal log={resolveModal} onClose={()=>setResolveModal(null)} onDone={()=>fetchAll(true)} toast={toast}/>}
      <Toasts list={toasts}/>
    </div>
  );
}



// // src/pages/Alerts.jsx
// import React, { useState, useEffect, useRef, useCallback } from 'react';
// import client from '../api/client';

// // ─── THEMES ───────────────────────────────────────────────────────────────────
// const THEMES = [
//   {
//     name: "EMERALD OPS",
//     primary: "#00ff88", secondary: "#00cc6a",
//     bg: "radial-gradient(ellipse at 20% 50%, #001a0e 0%, #000a05 60%, #000000 100%)",
//     glass: "rgba(0,255,136,0.05)", glassBorder: "rgba(0,255,136,0.14)",
//     glassHover: "rgba(0,255,136,0.09)",
//     glow: "0 0 40px rgba(0,255,136,0.12)",
//     glowStrong: "0 0 80px rgba(0,255,136,0.22)",
//     text: "#e0fff0", textMuted: "#4d9966",
//     orb1: "#00ff8822", orb2: "#00cc6a14",
//   },
//   {
//     name: "OCEAN COMMAND",
//     primary: "#00d4ff", secondary: "#0088cc",
//     bg: "radial-gradient(ellipse at 80% 20%, #001020 0%, #000810 60%, #000000 100%)",
//     glass: "rgba(0,212,255,0.05)", glassBorder: "rgba(0,212,255,0.14)",
//     glassHover: "rgba(0,212,255,0.09)",
//     glow: "0 0 40px rgba(0,212,255,0.12)",
//     glowStrong: "0 0 80px rgba(0,212,255,0.22)",
//     text: "#e0f8ff", textMuted: "#3d8899",
//     orb1: "#00d4ff22", orb2: "#0088cc14",
//   },
//   {
//     name: "CRIMSON FORCE",
//     primary: "#ff2244", secondary: "#cc0033",
//     bg: "radial-gradient(ellipse at 50% 80%, #1a0005 0%, #0a0002 60%, #000000 100%)",
//     glass: "rgba(255,34,68,0.05)", glassBorder: "rgba(255,34,68,0.14)",
//     glassHover: "rgba(255,34,68,0.09)",
//     glow: "0 0 40px rgba(255,34,68,0.12)",
//     glowStrong: "0 0 80px rgba(255,34,68,0.22)",
//     text: "#ffe0e5", textMuted: "#994455",
//     orb1: "#ff224422", orb2: "#cc003314",
//   },
//   {
//     name: "GOLDEN INTEL",
//     primary: "#ffcc00", secondary: "#cc9900",
//     bg: "radial-gradient(ellipse at 30% 70%, #1a1400 0%, #0a0800 60%, #000000 100%)",
//     glass: "rgba(255,204,0,0.05)", glassBorder: "rgba(255,204,0,0.14)",
//     glassHover: "rgba(255,204,0,0.09)",
//     glow: "0 0 40px rgba(255,204,0,0.12)",
//     glowStrong: "0 0 80px rgba(255,204,0,0.22)",
//     text: "#fff8e0", textMuted: "#997733",
//     orb1: "#ffcc0022", orb2: "#cc990014",
//   },
//   {
//     name: "VIOLET CIPHER",
//     primary: "#bb44ff", secondary: "#8822cc",
//     bg: "radial-gradient(ellipse at 70% 30%, #0e0020 0%, #060010 60%, #000000 100%)",
//     glass: "rgba(187,68,255,0.05)", glassBorder: "rgba(187,68,255,0.14)",
//     glassHover: "rgba(187,68,255,0.09)",
//     glow: "0 0 40px rgba(187,68,255,0.12)",
//     glowStrong: "0 0 80px rgba(187,68,255,0.22)",
//     text: "#f0e0ff", textMuted: "#7744aa",
//     orb1: "#bb44ff22", orb2: "#8822cc14",
//   },
// ];

// const SEV = {
//   critical: { color: "#ff2244", label: "CRITICAL", dot: "🔴" },
//   high:     { color: "#ff6600", label: "HIGH",     dot: "🟠" },
//   medium:   { color: "#ffcc00", label: "MEDIUM",   dot: "🟡" },
//   low:      { color: "#00ff88", label: "LOW",      dot: "🟢" },
//   info:     { color: "#00d4ff", label: "INFO",     dot: "🔵" },
// };

// // ─── COMPONENTS ───────────────────────────────────────────────────────────────
// const Glass = ({ children, t, style = {}, hover = false }) => {
//   const [hov, setHov] = useState(false);
//   return (
//     <div
//       onMouseEnter={() => hover && setHov(true)}
//       onMouseLeave={() => hover && setHov(false)}
//       style={{
//         background: hov ? t.glassHover : t.glass,
//         border: `1px solid ${t.glassBorder}`,
//         borderRadius: 16,
//         backdropFilter: "blur(24px)",
//         WebkitBackdropFilter: "blur(24px)",
//         boxShadow: `${t.glow}, inset 0 1px 0 ${t.glassBorder}`,
//         transition: "background 0.3s",
//         ...style,
//       }}
//     >{children}</div>
//   );
// };

// const StatCard = ({ label, value, icon, color, t, loading }) => (
//   <Glass t={t} style={{ padding: "20px 22px", position: "relative", overflow: "hidden" }}>
//     <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at top right, ${color}10 0%, transparent 60%)`, pointerEvents: "none" }} />
//     <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${color}80, transparent)` }} />
//     <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
//       <span style={{ fontSize: 18 }}>{icon}</span>
//       <span style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", fontFamily: "'Courier New', monospace" }}>{label}</span>
//     </div>
//     {loading
//       ? <div style={{ height: 36, width: 80, borderRadius: 8, background: `${color}15`, animation: "shimmer 1.4s infinite" }} />
//       : <div style={{ fontSize: 36, fontWeight: 900, color, fontFamily: "'Courier New', monospace", lineHeight: 1, textShadow: `0 0 24px ${color}70` }}>{value}</div>
//     }
//   </Glass>
// );

// const Tag = ({ children, color }) => (
//   <span style={{
//     color, background: `${color}18`, border: `1px solid ${color}35`,
//     padding: "2px 9px", borderRadius: 4, fontSize: 9, fontWeight: 700,
//     letterSpacing: "0.1em", fontFamily: "'Courier New', monospace",
//     display: "inline-flex", alignItems: "center", gap: 4,
//   }}>
//     <span style={{ width: 4, height: 4, borderRadius: "50%", background: color, display: "inline-block" }} />
//     {children}
//   </span>
// );

// const AlertRow = ({ log, t, i }) => {
//   const sev = SEV[log.rule__severity] || SEV.medium;
//   return (
//     <div style={{
//       display: "grid", gridTemplateColumns: "8px 1fr auto auto",
//       gap: 16, padding: "14px 20px", alignItems: "center",
//       borderBottom: `1px solid ${t.glassBorder}`,
//       animation: `fadeIn .3s ease ${i * 0.04}s both`,
//       cursor: "default", transition: "background .2s",
//     }}
//       onMouseEnter={e => e.currentTarget.style.background = t.glassHover}
//       onMouseLeave={e => e.currentTarget.style.background = "transparent"}
//     >
//       <div style={{ width: 8, height: 8, borderRadius: "50%", background: sev.color, boxShadow: `0 0 10px ${sev.color}`, flexShrink: 0, animation: !log.is_resolved ? "pulse 1.8s infinite" : "none" }} />
//       <div>
//         <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
//           <span style={{ color: t.text, fontSize: 13, fontWeight: 600 }}>{log.rule__name || "—"}</span>
//           <Tag color={sev.color}>{sev.label}</Tag>
//         </div>
//         <div style={{ color: t.textMuted, fontSize: 11 }}>{log.message?.slice(0, 90)}{log.message?.length > 90 ? "…" : ""}</div>
//       </div>
//       <Tag color={log.is_resolved ? "#00ff88" : "#ffcc00"}>
//         {log.is_resolved ? "RESOLVED" : "ACTIVE"}
//       </Tag>
//       <div style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", textAlign: "right", minWidth: 130 }}>
//         {log.triggered_at ? new Date(log.triggered_at).toLocaleString() : "—"}
//       </div>
//     </div>
//   );
// };

// const RuleCard = ({ rule, t, i }) => {
//   const sev = SEV[rule.severity] || SEV.medium;
//   return (
//     <Glass t={t} hover style={{ padding: "16px 18px", animation: `fadeIn .35s ease ${i * 0.05}s both`, cursor: "default" }}>
//       <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
//         <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
//           <div style={{ width: 34, height: 34, borderRadius: 9, background: `${sev.color}20`, border: `1px solid ${sev.color}35`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15, flexShrink: 0 }}>
//             {sev.dot}
//           </div>
//           <div>
//             <div style={{ color: t.text, fontSize: 13, fontWeight: 700, marginBottom: 2 }}>{rule.name}</div>
//             <div style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>
//               {rule.alert_type?.replace(/_/g, " ").toUpperCase() || "—"}
//             </div>
//           </div>
//         </div>
//         <Tag color={sev.color}>{sev.label}</Tag>
//       </div>
//       <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 10, borderTop: `1px solid ${t.glassBorder}` }}>
//         <span style={{ color: rule.is_active ? "#00ff88" : t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", display: "flex", alignItems: "center", gap: 5 }}>
//           <span style={{ width: 5, height: 5, borderRadius: "50%", background: rule.is_active ? "#00ff88" : t.textMuted, display: "inline-block", ...(rule.is_active ? { animation: "pulse 1.5s infinite" } : {}) }} />
//           {rule.is_active ? "ACTIVE" : "INACTIVE"}
//         </span>
//         <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>
//           {rule.last_triggered ? new Date(rule.last_triggered).toLocaleDateString() : "Never"}
//         </span>
//       </div>
//     </Glass>
//   );
// };

// // ─── MAIN ─────────────────────────────────────────────────────────────────────
// export default function AlertsPage() {
//   const [themeIdx, setThemeIdx] = useState(0);
//   const [progress, setProgress]  = useState(0);
//   const progressRef = useRef(null);
//   const t = THEMES[themeIdx];

//   const [overview, setOverview] = useState(null);
//   const [rules, setRules]       = useState([]);
//   const [logs, setLogs]         = useState([]);
//   const [health, setHealth]     = useState(null);
//   const [loading, setLoading]   = useState(true);
//   const [tab, setTab]           = useState("overview");
//   const [clock, setClock]       = useState("");
//   const [sevFilter, setSevFilter] = useState("all");

//   // 60-second theme rotation
//   useEffect(() => {
//     let t = 0;
//     progressRef.current = setInterval(() => {
//       t += 1;
//       setProgress((t / 600) * 100);
//       if (t >= 600) { t = 0; setProgress(0); setThemeIdx(i => (i + 1) % THEMES.length); }
//     }, 100);
//     return () => clearInterval(progressRef.current);
//   }, []);

//   // Clock
//   useEffect(() => {
//     const tick = () => setClock(new Date().toUTCString().slice(17, 25) + " UTC");
//     tick(); const id = setInterval(tick, 1000); return () => clearInterval(id);
//   }, []);

//   // Fetch
//   const fetchAll = useCallback(async () => {
//     setLoading(true);
//     const [ov, ru, lo, he] = await Promise.allSettled([
//       client.get('/alerts/'),
//       client.get('/alerts/rules/'),
//       client.get('/alerts/logs/'),
//       client.get('/alerts/health/'),
//     ]);
//     if (ov.status === "fulfilled") setOverview(ov.value.data);
//     if (ru.status === "fulfilled") { const d = ru.value.data; setRules(Array.isArray(d) ? d : d?.results || []); }
//     if (lo.status === "fulfilled") { const d = lo.value.data; setLogs(Array.isArray(d) ? d : d?.results || []); }
//     if (he.status === "fulfilled") setHealth(he.value.data);
//     setLoading(false);
//   }, []);

//   useEffect(() => { fetchAll(); }, [fetchAll]);

//   const filteredLogs = logs.filter(l => sevFilter === "all" || l.rule__severity === sevFilter);
//   const healthStatus = health?.overall_status;
//   const healthColor = healthStatus === "healthy" ? "#00ff88" : healthStatus === "degraded" ? "#ffcc00" : healthStatus === "critical" ? "#ff2244" : t.primary;

//   const TABS = [
//     { id: "overview", label: "OVERVIEW", icon: "⚡" },
//     { id: "rules",    label: "RULES",    icon: "📋" },
//     { id: "logs",     label: "LOGS",     icon: "📜" },
//   ];

//   return (
//     <div style={{ minHeight: "100vh", background: t.bg, color: t.text, fontFamily: "'Segoe UI', -apple-system, sans-serif", transition: "background 1.2s ease" }}>
//       <style>{`
//         @keyframes fadeIn  { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
//         @keyframes pulse   { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.35;transform:scale(.75)} }
//         @keyframes float   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-24px)} }
//         @keyframes shimmer { 0%,100%{opacity:.25} 50%{opacity:.7} }
//         @keyframes spin    { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
//         * { box-sizing:border-box; }
//         ::-webkit-scrollbar{width:3px}
//         ::-webkit-scrollbar-thumb{background:${t.glassBorder};border-radius:2px}
//       `}</style>

//       {/* Ambient background orbs */}
//       <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0, overflow: "hidden" }}>
//         <div style={{ position: "absolute", top: "8%", left: "3%", width: 500, height: 500, borderRadius: "50%", background: t.orb1, filter: "blur(90px)", animation: "float 9s ease-in-out infinite" }} />
//         <div style={{ position: "absolute", bottom: "10%", right: "5%", width: 350, height: 350, borderRadius: "50%", background: t.orb2, filter: "blur(70px)", animation: "float 11s ease-in-out infinite reverse" }} />
//         <div style={{ position: "absolute", top: "45%", left: "45%", width: 700, height: 700, borderRadius: "50%", background: `${t.primary}04`, filter: "blur(120px)", transform: "translate(-50%,-50%)" }} />
//         {/* Subtle grid */}
//         <div style={{ position: "absolute", inset: 0, backgroundImage: `linear-gradient(${t.glassBorder} 1px, transparent 1px), linear-gradient(90deg, ${t.glassBorder} 1px, transparent 1px)`, backgroundSize: "60px 60px", opacity: 0.3 }} />
//       </div>

//       {/* ── TOP BAR ── */}
//       <div style={{ position: "sticky", top: 0, zIndex: 200, background: "rgba(0,0,0,0.65)", backdropFilter: "blur(32px)", WebkitBackdropFilter: "blur(32px)", borderBottom: `1px solid ${t.glassBorder}`, padding: "10px 26px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
//         <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
//           <div style={{ width: 8, height: 8, borderRadius: "50%", background: t.primary, animation: "pulse 1.5s infinite", boxShadow: `0 0 12px ${t.primary}` }} />
//           <span style={{ color: t.primary, fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", fontFamily: "'Courier New', monospace" }}>{t.name}</span>
//           <div style={{ width: 1, height: 14, background: t.glassBorder }} />
//           <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>ALERT COMMAND CENTER v2.0</span>
//         </div>
//         <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
//           {/* Progress */}
//           <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//             <span style={{ color: t.textMuted, fontSize: 9, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>THEME</span>
//             <div style={{ width: 80, height: 2, background: t.glassBorder, borderRadius: 1 }}>
//               <div style={{ height: "100%", width: `${progress}%`, background: `linear-gradient(90deg, ${t.primary}, ${t.secondary})`, borderRadius: 1, transition: "width 0.1s linear" }} />
//             </div>
//           </div>
//           {/* Health */}
//           {health && (
//             <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
//               <div style={{ width: 8, height: 8, borderRadius: "50%", background: healthColor, boxShadow: `0 0 8px ${healthColor}`, animation: "pulse 2s infinite" }} />
//               <span style={{ color: healthColor, fontSize: 10, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.08em" }}>{(healthStatus || "UNKNOWN").toUpperCase()}</span>
//             </div>
//           )}
//           <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>{clock}</span>
//           <button onClick={fetchAll} disabled={loading} style={{
//             background: t.glass, border: `1px solid ${t.glassBorder}`, borderRadius: 8,
//             padding: "6px 16px", color: t.primary, fontSize: 10, cursor: "pointer",
//             fontFamily: "'Courier New', monospace", letterSpacing: "0.08em", fontWeight: 700,
//             backdropFilter: "blur(10px)", transition: "all .2s",
//           }}>
//             {loading ? "…" : "↻ SYNC"}
//           </button>
//         </div>
//       </div>

//       <div style={{ position: "relative", zIndex: 1, padding: "28px 28px 48px", maxWidth: 1400, margin: "0 auto" }}>

//         {/* ── HEADER ── */}
//         <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 30, animation: "fadeIn .5s ease both" }}>
//           <div style={{ width: 56, height: 56, borderRadius: 14, background: t.glass, border: `1px solid ${t.glassBorder}`, backdropFilter: "blur(20px)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, boxShadow: t.glowStrong, flexShrink: 0 }}>🚨</div>
//           <div>
//             <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900, letterSpacing: "0.07em", fontFamily: "'Courier New', monospace", background: `linear-gradient(135deg, ${t.text} 30%, ${t.primary})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
//               ALERTS COMMAND CENTER
//             </h1>
//             <p style={{ margin: "4px 0 0", color: t.textMuted, fontSize: 11, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace" }}>
//               REAL-TIME MONITORING · THREAT DETECTION · SYSTEM INTELLIGENCE
//             </p>
//           </div>
//         </div>

//         {/* ── STATS ── */}
//         <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 26 }}>
//           <StatCard label="Total Rules"    value={overview?.total_rules ?? 0}      icon="📋" color={t.primary}  t={t} loading={loading} />
//           <StatCard label="Active Rules"   value={overview?.active_rules ?? 0}     icon="✅" color="#00ff88"    t={t} loading={loading} />
//           <StatCard label="Alerts Today"   value={overview?.alerts_today ?? 0}     icon="⚡" color="#ffcc00"    t={t} loading={loading} />
//           <StatCard label="Unresolved"     value={overview?.unresolved_alerts ?? 0} icon="🔴" color="#ff2244"   t={t} loading={loading} />
//         </div>

//         {/* ── TABS ── */}
//         <div style={{ display: "flex", gap: 3, marginBottom: 22, background: "rgba(0,0,0,0.4)", border: `1px solid ${t.glassBorder}`, borderRadius: 13, padding: 4, backdropFilter: "blur(20px)", width: "fit-content" }}>
//           {TABS.map(tb => (
//             <button key={tb.id} onClick={() => setTab(tb.id)} style={{
//               display: "flex", alignItems: "center", gap: 7, padding: "9px 22px",
//               borderRadius: 10, border: tab === tb.id ? `1px solid ${t.glassBorder}` : "1px solid transparent",
//               cursor: "pointer", fontFamily: "'Courier New', monospace",
//               fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
//               background: tab === tb.id ? `linear-gradient(135deg, ${t.primary}28, ${t.secondary}18)` : "transparent",
//               color: tab === tb.id ? t.primary : t.textMuted,
//               boxShadow: tab === tb.id ? `0 0 20px ${t.primary}25` : "none",
//               transition: "all .25s",
//             }}>
//               <span>{tb.icon}</span>{tb.label}
//             </button>
//           ))}
//         </div>

//         {/* ── OVERVIEW ── */}
//         {tab === "overview" && (
//           <div style={{ animation: "fadeIn .4s ease both" }}>
//             <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, marginBottom: 20 }}>

//               {/* Recent Logs */}
//               <Glass t={t} style={{ overflow: "hidden" }}>
//                 <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.glassBorder}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
//                   <span style={{ color: t.text, fontWeight: 700, fontSize: 13, fontFamily: "'Courier New', monospace", letterSpacing: "0.04em" }}>⚡ RECENT ALERTS</span>
//                   <Tag color={t.primary}>{logs.length} TOTAL</Tag>
//                 </div>
//                 {loading ? (
//                   <div style={{ padding: 50, textAlign: "center", color: t.textMuted, fontSize: 11, fontFamily: "'Courier New', monospace", animation: "shimmer 1.4s infinite" }}>LOADING…</div>
//                 ) : logs.length === 0 ? (
//                   <div style={{ padding: 50, textAlign: "center", color: t.textMuted, fontSize: 12 }}>No alerts found</div>
//                 ) : logs.slice(0, 6).map((log, i) => <AlertRow key={log.id} log={log} t={t} i={i} />)}
//               </Glass>

//               {/* Rules */}
//               <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
//                 <Glass t={t} style={{ padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
//                   <span style={{ color: t.text, fontWeight: 700, fontSize: 13, fontFamily: "'Courier New', monospace" }}>📋 ACTIVE RULES</span>
//                   <Tag color={t.primary}>{rules.length}</Tag>
//                 </Glass>
//                 {loading
//                   ? [1,2,3].map(k => <div key={k} style={{ height: 88, borderRadius: 16, background: t.glass, border: `1px solid ${t.glassBorder}`, animation: "shimmer 1.4s infinite" }} />)
//                   : rules.slice(0, 4).map((r, i) => <RuleCard key={r.id} rule={r} t={t} i={i} />)
//                 }
//               </div>
//             </div>

//             {/* Severity Bar */}
//             {logs.length > 0 && (
//               <Glass t={t} style={{ padding: "20px 24px" }}>
//                 <div style={{ color: t.text, fontWeight: 700, fontSize: 13, fontFamily: "'Courier New', monospace", marginBottom: 18, letterSpacing: "0.04em" }}>📊 SEVERITY BREAKDOWN</div>
//                 <div style={{ display: "flex", gap: 16 }}>
//                   {Object.entries(SEV).map(([key, cfg]) => {
//                     const count = logs.filter(l => l.rule__severity === key).length;
//                     const pct = logs.length ? Math.round((count / logs.length) * 100) : 0;
//                     return (
//                       <div key={key} style={{ flex: 1 }}>
//                         <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 7 }}>
//                           <span style={{ color: cfg.color, fontSize: 10, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{cfg.dot} {cfg.label}</span>
//                           <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>{count}</span>
//                         </div>
//                         <div style={{ height: 5, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden", border: `1px solid ${t.glassBorder}` }}>
//                           <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${cfg.color}, ${cfg.color}88)`, borderRadius: 3, boxShadow: `0 0 8px ${cfg.color}60`, transition: "width .8s ease" }} />
//                         </div>
//                         <div style={{ color: t.textMuted, fontSize: 9, marginTop: 4, fontFamily: "'Courier New', monospace" }}>{pct}%</div>
//                       </div>
//                     );
//                   })}
//                 </div>
//               </Glass>
//             )}
//           </div>
//         )}

//         {/* ── RULES TAB ── */}
//         {tab === "rules" && (
//           <div style={{ animation: "fadeIn .4s ease both" }}>
//             {loading ? (
//               <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 14 }}>
//                 {[1,2,3,4,5,6].map(k => <div key={k} style={{ height: 100, borderRadius: 16, background: t.glass, border: `1px solid ${t.glassBorder}`, animation: "shimmer 1.4s infinite" }} />)}
//               </div>
//             ) : rules.length === 0 ? (
//               <Glass t={t} style={{ padding: 80, textAlign: "center" }}>
//                 <div style={{ fontSize: 36, marginBottom: 14 }}>📋</div>
//                 <div style={{ color: t.textMuted, fontFamily: "'Courier New', monospace", fontSize: 12, letterSpacing: "0.1em" }}>NO ACTIVE RULES FOUND</div>
//               </Glass>
//             ) : (
//               <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 14 }}>
//                 {rules.map((r, i) => <RuleCard key={r.id} rule={r} t={t} i={i} />)}
//               </div>
//             )}
//           </div>
//         )}

//         {/* ── LOGS TAB ── */}
//         {tab === "logs" && (
//           <div style={{ animation: "fadeIn .4s ease both" }}>
//             {/* Severity filter */}
//             <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center", flexWrap: "wrap" }}>
//               <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>FILTER:</span>
//               {["all", ...Object.keys(SEV)].map(s => (
//                 <button key={s} onClick={() => setSevFilter(s)} style={{
//                   background: sevFilter === s ? `${(SEV[s]?.color || t.primary)}20` : "rgba(255,255,255,0.03)",
//                   border: `1px solid ${sevFilter === s ? (SEV[s]?.color || t.primary) : t.glassBorder}`,
//                   borderRadius: 20, padding: "5px 14px",
//                   color: sevFilter === s ? (SEV[s]?.color || t.primary) : t.textMuted,
//                   fontSize: 10, cursor: "pointer",
//                   fontFamily: "'Courier New', monospace", fontWeight: 700, letterSpacing: "0.08em",
//                   transition: "all .2s", backdropFilter: "blur(8px)",
//                 }}>
//                   {s === "all" ? "ALL" : `${SEV[s].dot} ${SEV[s].label}`}
//                 </button>
//               ))}
//               <span style={{ marginLeft: "auto", color: t.textMuted, fontSize: 11, fontFamily: "'Courier New', monospace" }}>
//                 <span style={{ color: t.primary, fontWeight: 700 }}>{filteredLogs.length}</span> RECORDS
//               </span>
//             </div>

//             <Glass t={t} style={{ overflow: "hidden" }}>
//               <div style={{ display: "grid", gridTemplateColumns: "8px 1fr auto auto", gap: 16, padding: "10px 20px", borderBottom: `1px solid ${t.glassBorder}`, background: "rgba(0,0,0,0.3)" }}>
//                 {["", "RULE / MESSAGE", "STATUS", "TRIGGERED AT"].map(h => (
//                   <span key={h} style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace" }}>{h}</span>
//                 ))}
//               </div>
//               {loading ? (
//                 <div style={{ padding: 60, textAlign: "center", color: t.textMuted, fontFamily: "'Courier New', monospace", animation: "shimmer 1.4s infinite", fontSize: 11 }}>LOADING LOGS…</div>
//               ) : filteredLogs.length === 0 ? (
//                 <div style={{ padding: 70, textAlign: "center" }}>
//                   <div style={{ fontSize: 30, marginBottom: 10 }}>📜</div>
//                   <div style={{ color: t.textMuted, fontFamily: "'Courier New', monospace", fontSize: 11, letterSpacing: "0.1em" }}>NO LOGS FOUND</div>
//                 </div>
//               ) : filteredLogs.map((log, i) => <AlertRow key={log.id} log={log} t={t} i={i} />)}
//             </Glass>
//           </div>
//         )}

//         {/* Theme dots */}
//         <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 36 }}>
//           {THEMES.map((th, i) => (
//             <button key={i} onClick={() => { setThemeIdx(i); setProgress(0); }} title={th.name} style={{
//               width: i === themeIdx ? 36 : 10, height: 10, borderRadius: 5, border: "none", cursor: "pointer",
//               background: i === themeIdx ? `linear-gradient(90deg, ${th.primary}, ${th.secondary})` : `${th.primary}44`,
//               boxShadow: i === themeIdx ? `0 0 14px ${th.primary}70` : "none",
//               transition: "all .4s ease",
//             }} />
//           ))}
//         </div>
//       </div>
//     </div>
//   );
// }