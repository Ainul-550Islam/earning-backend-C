// pages/FraudDetection.jsx
import { useState, useEffect, useRef, useCallback } from "react";
import client from "../api/client";
import "../styles/FraudDetection.css";

// ─── API helpers ──────────────────────────────────────────────────
const API = {
  getRules:      (p={}) => client.get("/fraud_detection/rules/", { params: p }),
  createRule:    (d)    => client.post("/fraud_detection/rules/", d),
  updateRule:    (id,d) => client.patch(`/fraud_detection/rules/${id}/`, d),
  deleteRule:    (id)   => client.delete(`/fraud_detection/rules/${id}/`),
  getAttempts:   (p={}) => client.get("/fraud_detection/attempts/", { params: p }),
  bulkAttempts:  (d)    => client.post("/fraud_detection/attempts/bulk-update/", d),
  getAlerts:     (p={}) => client.get("/fraud_detection/alerts/", { params: p }),
  createAlert:   (d)    => client.post("/fraud_detection/alerts/", d),
  updateAlert:   (id,d) => client.patch(`/fraud_detection/alerts/${id}/`, d),
  deleteAlert:   (id)   => client.delete(`/fraud_detection/alerts/${id}/`),
  resolveAlert:  (id)   => client.patch(`/fraud_detection/alerts/${id}/`, { is_resolved: true, resolved_at: new Date().toISOString() }),
  bulkResolve:   (ids)  => client.post("/fraud_detection/alerts/bulk-resolve/", { alert_ids: ids, notes: "Resolved by admin" }),
  alertStats:    ()     => client.get("/fraud_detection/alerts/dashboard-stats/"),
  getRiskProfiles:(p={}) => client.get("/fraud_detection/risk-profiles/", { params: p }),
  getSettings:   ()     => client.get("/fraud_detection/settings/block-vpn/"),
  saveSettings:  (d)    => client.post("/fraud_detection/settings/block-vpn/", d),
};

// ─── Fallback ─────────────────────────────────────────────────────
const FALLBACK = {
  chart: [
    { day: "Sun", blocked: 72, success: 45, failed: 28 },
    { day: "Mon", blocked: 85, success: 52, failed: 35 },
    { day: "Tue", blocked: 68, success: 38, failed: 22 },
    { day: "Wed", blocked: 92, success: 61, failed: 40 },
    { day: "Thu", blocked: 78, success: 49, failed: 30 },
    { day: "Fri", blocked: 88, success: 55, failed: 42 },
    { day: "Sat", blocked: 95, success: 65, failed: 38 },
  ],
  patterns: [
    { name: "Credential Stuffing", icon: "🔑", pct: 45, color: "#ff2244" },
    { name: "Bot Attack",          icon: "🤖", pct: 30, color: "#ffb700" },
    { name: "Phishing",            icon: "🎣", pct: 15, color: "#0066ff" },
    { name: "Geo-Spike",           icon: "🌍", pct: 10, color: "#aa44ff" },
  ],
  ip_rep: [
    { country: "USA",    flag: "🇺🇸", score: 92, status: "High"   },
    { country: "India",  flag: "🇮🇳", score: 75, status: "Medium" },
    { country: "Russia", flag: "🇷🇺", score: 60, status: "Medium" },
    { country: "Brazil", flag: "🇧🇷", score: 45, status: "Low"    },
    { country: "China",  flag: "🇨🇳", score: 38, status: "High"   },
  ],
};

const MAP_DOTS = [
  { x: "22%", y: "30%", c: "fd-map-red",   delay: 0   },
  { x: "48%", y: "25%", c: "fd-map-cyan",  delay: 0.4 },
  { x: "55%", y: "32%", c: "fd-map-red",   delay: 0.8 },
  { x: "30%", y: "55%", c: "fd-map-amber", delay: 0.2 },
  { x: "70%", y: "60%", c: "fd-map-red",   delay: 0.6 },
  { x: "80%", y: "25%", c: "fd-map-cyan",  delay: 1.0 },
  { x: "15%", y: "65%", c: "fd-map-red",   delay: 0.3 },
  { x: "60%", y: "70%", c: "fd-map-amber", delay: 0.7 },
];

// ─── SVG helpers ──────────────────────────────────────────────────
function CircularGauge({ pct, color = "#00f5ff", size = 90, label = "Secure" }) {
  const r = (size - 14) / 2, circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(0,245,255,0.1)" strokeWidth="8"/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="8"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "stroke-dashoffset 1s ease" }}/>
      <text x={size/2} y={size/2-4} textAnchor="middle" fill={color} fontSize="13" fontFamily="Orbitron" fontWeight="700">{pct}%</text>
      <text x={size/2} y={size/2+11} textAnchor="middle" fill="rgba(140,200,230,0.6)" fontSize="7" fontFamily="Orbitron">{label}</text>
    </svg>
  );
}

function DonutChart({ data, size = 80 }) {
  const cx = size/2, cy = size/2, r = size*0.35, circ = 2*Math.PI*r;
  let offset = 0;
  const total = data.reduce((s,d) => s + d.pct, 0) || 1;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="14"/>
      {data.map((d,i) => {
        const dash = (d.pct/total)*circ;
        const el = <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={d.color} strokeWidth="14"
          strokeDasharray={`${dash} ${circ-dash}`} strokeDashoffset={-offset}
          transform={`rotate(-90 ${cx} ${cy})`} style={{ filter: `drop-shadow(0 0 4px ${d.color})` }}/>;
        offset += dash; return el;
      })}
    </svg>
  );
}

function RateGauge({ pct }) {
  const r = 34, circ = 2*Math.PI*r;
  return (
    <svg width="88" height="72" viewBox="0 0 88 72">
      <defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#0066ff"/>
        <stop offset="50%" stopColor="#00ff88"/>
        <stop offset="100%" stopColor="#ffb700"/>
      </linearGradient></defs>
      <circle cx="44" cy="52" r={r} fill="none" stroke="rgba(0,245,255,0.1)" strokeWidth="9"
        strokeDasharray={`${circ*0.75} ${circ*0.25}`} transform="rotate(135 44 52)" strokeLinecap="round"/>
      <circle cx="44" cy="52" r={r} fill="none" stroke="url(#rg)" strokeWidth="9"
        strokeDasharray={`${(pct/100)*circ*0.75} ${circ}`} transform="rotate(135 44 52)" strokeLinecap="round"
        style={{ filter: "drop-shadow(0 0 5px #00ff88)" }}/>
      <text x="44" y="52" textAnchor="middle" fill="#00ff88" fontSize="16" fontFamily="Orbitron" fontWeight="900">{pct}%</text>
      <text x="44" y="63" textAnchor="middle" fill="rgba(140,200,230,0.6)" fontSize="6" fontFamily="Orbitron">COMPLETION</text>
    </svg>
  );
}

function MiniBarChart({ data }) {
  const max = Math.max(...data) || 1;
  const colors = ["#0066ff","#00ff88","#ffb700","#ff2244","#aa44ff","#00f5ff","#ff66aa"];
  return (
    <div style={{ display:"flex", alignItems:"flex-end", gap:"3px", height:"46px" }}>
      {data.map((v,i) => (
        <div key={i} style={{ flex:1, borderRadius:"2px 2px 0 0", height:`${(v/max)*100}%`,
          background:`linear-gradient(to top, ${colors[i]}88, ${colors[i]})`,
          boxShadow:`0 0 4px ${colors[i]}66`, minWidth:"5px" }}/>
      ))}
    </div>
  );
}

// ─── Toast ────────────────────────────────────────────────────────
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, []);
  const c = { success:"#00ff88", error:"#ff2244", info:"#00f5ff" }[type] || "#00f5ff";
  return (
    <div style={{ position:"fixed", bottom:24, right:24, zIndex:99999, background:"rgba(10,10,26,.97)",
      border:`1px solid ${c}44`, borderRadius:10, padding:"12px 20px",
      display:"flex", alignItems:"center", gap:10, boxShadow:`0 0 20px ${c}22` }}>
      <span>{type==="success"?"✅":type==="error"?"❌":"ℹ️"}</span>
      <span style={{ color:c, fontSize:12, fontFamily:"Orbitron" }}>{msg}</span>
      <button onClick={onClose} style={{ background:"none", border:"none", color:"rgba(255,255,255,.4)", cursor:"pointer", fontSize:14 }}>✕</button>
    </div>
  );
}

// ─── Confirm Delete ───────────────────────────────────────────────
function ConfirmModal({ msg, onConfirm, onClose }) {
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,.8)", zIndex:9999, display:"flex", alignItems:"center", justifyContent:"center" }} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{ background:"#0a0a1a", border:"1px solid rgba(255,34,68,.3)", borderRadius:14, padding:28, minWidth:340, textAlign:"center" }}>
        <div style={{ fontSize:32, marginBottom:12 }}>⚠️</div>
        <div style={{ fontFamily:"Orbitron", fontSize:12, color:"#fff", marginBottom:8 }}>CONFIRM DELETE</div>
        <div style={{ fontSize:12, color:"rgba(140,200,230,.6)", marginBottom:20 }}>{msg}</div>
        <div style={{ display:"flex", gap:10 }}>
          <button onClick={onConfirm} style={{ flex:1, background:"rgba(255,34,68,.2)", border:"1px solid rgba(255,34,68,.4)", borderRadius:8, padding:"10px 0", color:"#ff2244", fontFamily:"Orbitron", fontSize:11, cursor:"pointer" }}>DELETE</button>
          <button onClick={onClose} style={{ flex:1, background:"rgba(0,245,255,.1)", border:"1px solid rgba(0,245,255,.3)", borderRadius:8, padding:"10px 0", color:"#00f5ff", fontFamily:"Orbitron", fontSize:11, cursor:"pointer" }}>CANCEL</button>
        </div>
      </div>
    </div>
  );
}

// ─── CRUD Modal ───────────────────────────────────────────────────
function CRUDModal({ title, fields, values, onSave, onClose, saving }) {
  const [form, setForm] = useState(values || {});
  const set = (k,v) => setForm(p => ({ ...p, [k]:v }));
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,.8)", zIndex:9999, display:"flex", alignItems:"center", justifyContent:"center" }} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{ background:"linear-gradient(135deg,#0a0a1a,#0d0a20)", border:"1px solid rgba(0,245,255,.25)", borderRadius:16, padding:28, minWidth:480, maxWidth:600, maxHeight:"85vh", overflowY:"auto" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
          <span style={{ fontFamily:"Orbitron", fontSize:14, color:"#00f5ff", letterSpacing:2 }}>{title}</span>
          <button onClick={onClose} style={{ background:"none", border:"none", color:"#ff2244", fontSize:18, cursor:"pointer" }}>✕</button>
        </div>
        {fields.map(f => (
          <div key={f.key} style={{ marginBottom:14 }}>
            <label style={{ display:"block", fontSize:10, color:"rgba(140,200,230,.6)", letterSpacing:1, marginBottom:5, fontFamily:"Orbitron" }}>{f.label}</label>
            {f.type==="select" ? (
              <select value={form[f.key]||""} onChange={e=>set(f.key,e.target.value)} style={{ width:"100%", background:"rgba(0,20,40,.8)", border:"1px solid rgba(0,245,255,.2)", borderRadius:8, padding:"9px 12px", color:"#fff", fontSize:12, outline:"none" }}>
                <option value="">Select...</option>
                {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : f.type==="textarea" ? (
              <textarea value={form[f.key]||""} onChange={e=>set(f.key,e.target.value)} rows={3} style={{ width:"100%", background:"rgba(0,20,40,.8)", border:"1px solid rgba(0,245,255,.2)", borderRadius:8, padding:"9px 12px", color:"#fff", fontSize:12, outline:"none", resize:"vertical", fontFamily:"inherit" }}/>
            ) : (
              <input type={f.type||"text"} value={form[f.key]||""} onChange={e=>set(f.key,e.target.value)} style={{ width:"100%", background:"rgba(0,20,40,.8)", border:"1px solid rgba(0,245,255,.2)", borderRadius:8, padding:"9px 12px", color:"#fff", fontSize:12, outline:"none" }}/>
            )}
          </div>
        ))}
        <div style={{ display:"flex", gap:10, marginTop:20 }}>
          <button onClick={()=>onSave(form)} disabled={saving} style={{ flex:1, background:"rgba(0,245,255,.15)", border:"1px solid rgba(0,245,255,.4)", borderRadius:8, padding:"10px 0", color:"#00f5ff", fontFamily:"Orbitron", fontSize:11, cursor:saving?"not-allowed":"pointer", letterSpacing:1 }}>
            {saving?"SAVING...":"✦ SAVE"}
          </button>
          <button onClick={onClose} style={{ flex:1, background:"rgba(255,34,68,.1)", border:"1px solid rgba(255,34,68,.3)", borderRadius:8, padding:"10px 0", color:"#ff2244", fontFamily:"Orbitron", fontSize:11, cursor:"pointer", letterSpacing:1 }}>CANCEL</button>
        </div>
      </div>
    </div>
  );
}

// ─── Settings Panel ───────────────────────────────────────────────
function SettingsPanel({ onToast, onClose }) {
  const [blockVpn, setBlockVpn] = useState(false);
  const [threshold, setThreshold] = useState(70);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    API.getSettings().then(r => {
      setBlockVpn(r.data.block_vpn ?? false);
      setThreshold(r.data.global_risk_threshold ?? 70);
    }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await API.saveSettings({ block_vpn: blockVpn, global_risk_threshold: threshold });
      onToast("Settings saved!", "success");
    } catch { onToast("Failed to save settings", "error"); }
    setSaving(false);
  };

  return (
    <div className="fd-panel fd-panel-cyan" style={{ margin:0, flex:1 }}>
      <div className="fd-panel-hd">
        <span className="fd-panel-title">🔧 Fraud Detection Settings</span>
      </div>
      <div className="fd-panel-body">
        <div style={{ maxWidth:500 }}>
          <div style={{ marginBottom:20, padding:"16px 20px", background:"rgba(0,245,255,.05)", border:"1px solid rgba(0,245,255,.15)", borderRadius:10 }}>
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8 }}>
              <div>
                <div style={{ color:"#fff", fontFamily:"Orbitron", fontSize:12, marginBottom:4 }}>Block VPN / Proxy</div>
                <div style={{ color:"rgba(140,200,230,.5)", fontSize:10 }}>Automatically block users connecting via VPN or proxy</div>
              </div>
              <div onClick={()=>setBlockVpn(p=>!p)} style={{ width:44, height:24, borderRadius:12, background:blockVpn?"rgba(0,255,136,.3)":"rgba(255,255,255,.1)", border:`1px solid ${blockVpn?"#00ff88":"rgba(255,255,255,.2)"}`, cursor:"pointer", position:"relative", transition:"all .3s" }}>
                <div style={{ position:"absolute", top:3, left:blockVpn?22:3, width:16, height:16, borderRadius:"50%", background:blockVpn?"#00ff88":"rgba(255,255,255,.4)", transition:"all .3s", boxShadow:blockVpn?"0 0 8px #00ff88":"none" }}/>
              </div>
            </div>
          </div>
          <div style={{ marginBottom:20, padding:"16px 20px", background:"rgba(0,245,255,.05)", border:"1px solid rgba(0,245,255,.15)", borderRadius:10 }}>
            <div style={{ color:"#fff", fontFamily:"Orbitron", fontSize:12, marginBottom:8 }}>Global Risk Threshold: <span style={{ color:"#00f5ff" }}>{threshold}</span></div>
            <div style={{ color:"rgba(140,200,230,.5)", fontSize:10, marginBottom:12 }}>Users with risk score above this will be flagged automatically</div>
            <input type="range" min="10" max="100" value={threshold} onChange={e=>setThreshold(Number(e.target.value))} style={{ width:"100%", accentColor:"#00f5ff" }}/>
            <div style={{ display:"flex", justifyContent:"space-between", marginTop:4 }}>
              <span style={{ fontSize:9, color:"rgba(140,200,230,.4)" }}>10 (Strict)</span>
              <span style={{ fontSize:9, color:"rgba(140,200,230,.4)" }}>100 (Lenient)</span>
            </div>
          </div>
          <button onClick={save} disabled={saving} style={{ width:"100%", padding:"12px 0", background:"rgba(0,245,255,.15)", border:"1px solid rgba(0,245,255,.4)", borderRadius:10, color:"#00f5ff", fontFamily:"Orbitron", fontSize:12, cursor:saving?"not-allowed":"pointer", letterSpacing:2 }}>
            {saving?"SAVING...":"✦ SAVE SETTINGS"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────
export default function FraudDetection() {
  const [activeNav, setActiveNav] = useState("Dashboard");
  const [rules, setRules]         = useState([]);
  const [attempts, setAttempts]   = useState([]);
  const [alerts, setAlerts]       = useState([]);
  const [riskProfiles, setRiskProfiles] = useState([]);
  const [summaryStats, setSummaryStats] = useState({ total_rules:0, active_rules:0, disabled_rules:0, security_score:0, total_attempts:0, blocked:0, success:0 });
  const [loading, setLoading]     = useState(true);
  const [modal, setModal]         = useState(null);
  const [confirmDel, setConfirmDel] = useState(null);
  const [saving, setSaving]       = useState(false);
  const [toast, setToast]         = useState(null);
  const [selectedAttempts, setSelectedAttempts] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const scrollRef = useRef(null);

  // alertCounts calculated from alerts array — always accurate
  const alertCounts = {
    critical: alerts.filter(a => a.priority === "critical").length,
    high:     alerts.filter(a => a.priority === "high").length,
    medium:   alerts.filter(a => a.priority === "medium").length,
    low:      alerts.filter(a => a.priority === "low").length,
  };

  const showToast = (msg, type="success") => setToast({ msg, type });

  // Fetch current user
  useEffect(() => {
    client.get("/users/me/").then(r => setCurrentUser(r.data)).catch(() =>
      client.get("/auth/user/").then(r => setCurrentUser(r.data)).catch(() => {})
    );
  }, []);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rulesRes, attemptsRes, alertsRes, riskRes] = await Promise.allSettled([
        API.getRules({ page_size: 20 }),
        API.getAttempts({ page_size: 30 }),
        API.getAlerts({ page_size: 100 }), // fetch all for accurate counts
        API.getRiskProfiles({ page_size: 20 }),
      ]);

      // Rules
      if (rulesRes.status === "fulfilled") {
        const r = rulesRes.value.data?.results || rulesRes.value.data || [];
        setRules(Array.isArray(r) ? r : []);
        const active = r.filter(x => x.is_active).length;
        setSummaryStats(p => ({ ...p, total_rules:r.length, active_rules:active, disabled_rules:r.length-active, security_score:Math.min(99, Math.round((active/(r.length||1))*100)) }));
      }

      // Attempts
      if (attemptsRes.status === "fulfilled") {
        const a = attemptsRes.value.data?.results || attemptsRes.value.data || [];
        const arr = Array.isArray(a) ? a : [];
        setAttempts(arr);
        const blocked = arr.filter(x => x.status === "blocked").length;
        setSummaryStats(p => ({ ...p, total_attempts:arr.length, blocked, success:arr.length-blocked }));
      }

      // Alerts
      if (alertsRes.status === "fulfilled") {
        const a = alertsRes.value.data?.results || alertsRes.value.data || [];
        setAlerts(Array.isArray(a) ? a : []);
      }

      // Risk Profiles
      if (riskRes.status === "fulfilled") {
        const r = riskRes.value.data?.results || riskRes.value.data || [];
        setRiskProfiles(Array.isArray(r) ? r : []);
      }

    } catch (e) { console.warn("FraudDetection fetch error:", e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Rule CRUD ────────────────────────────────────────────────────
  const ruleFields = [
    { key:"name",             label:"Rule Name",        type:"text" },
    { key:"description",      label:"Description",      type:"textarea" },
    { key:"rule_type",        label:"Rule Type",        type:"select", options:[
      {value:"account",label:"Account"},{value:"payment",label:"Payment"},
      {value:"offer",label:"Offer"},{value:"referral",label:"Referral"},
      {value:"withdrawal",label:"Withdrawal"},{value:"behavior",label:"Behavior"},
    ]},
    { key:"severity",         label:"Severity",         type:"select", options:[
      {value:"low",label:"Low"},{value:"medium",label:"Medium"},
      {value:"high",label:"High"},{value:"critical",label:"Critical"},
    ]},
    { key:"weight",           label:"Weight (1-100)",   type:"number" },
    { key:"threshold",        label:"Threshold (1-100)",type:"number" },
    { key:"action_on_trigger",label:"Action On Trigger",type:"select", options:[
      {value:"flag",label:"Flag"},{value:"review",label:"Review"},
      {value:"limit",label:"Limit"},{value:"suspend",label:"Suspend"},{value:"ban",label:"Ban"},
    ]},
    { key:"run_frequency",    label:"Frequency",        type:"select", options:[
      {value:"realtime",label:"Realtime"},{value:"hourly",label:"Hourly"},
      {value:"daily",label:"Daily"},{value:"weekly",label:"Weekly"},
    ]},
  ];

  const saveRule = async (form) => {
    setSaving(true);
    try {
      if (modal.data?.id) { await API.updateRule(modal.data.id, form); showToast("Rule updated!"); }
      else { await API.createRule({ ...form, is_active:true, condition:"{}" }); showToast("Rule created!"); }
      setModal(null); fetchAll();
    } catch (e) { showToast(e?.response?.data?.detail || "Failed to save rule", "error"); }
    setSaving(false);
  };

  const deleteRule = async (id) => {
    try { await API.deleteRule(id); showToast("Rule deleted!"); fetchAll(); }
    catch { showToast("Delete failed", "error"); }
    setConfirmDel(null);
  };

  const toggleRule = async (rule) => {
    try { await API.updateRule(rule.id, { is_active: !rule.is_active }); showToast(`Rule ${!rule.is_active?"activated":"deactivated"}!`); fetchAll(); }
    catch { showToast("Toggle failed", "error"); }
  };

  // ── Alert CRUD ───────────────────────────────────────────────────
  const alertFields = [
    { key:"title",      label:"Alert Title", type:"text" },
    { key:"description",label:"Description", type:"textarea" },
    { key:"alert_type", label:"Alert Type",  type:"select", options:[
      {value:"rule_triggered",   label:"Rule Triggered"},
      {value:"pattern_detected", label:"Pattern Detected"},
      {value:"threshold_exceeded",label:"Threshold Exceeded"},
      {value:"manual_review",    label:"Manual Review Required"},
      {value:"system_anomaly",   label:"System Anomaly"},
    ]},
    { key:"priority",   label:"Priority",    type:"select", options:[
      {value:"low",label:"Low"},{value:"medium",label:"Medium"},
      {value:"high",label:"High"},{value:"critical",label:"Critical"},
    ]},
  ];

  // Use 'id' if available (after serializer fix), fallback to 'alert_id'
  const getAlertKey = (a) => a.id || a.alert_id;

  const saveAlert = async (form) => {
    setSaving(true);
    try {
      const key = modal.data ? getAlertKey(modal.data) : null;
      if (key) { await API.updateAlert(key, form); showToast("Alert updated!"); }
      else { await API.createAlert({ ...form, is_resolved:false, data:{} }); showToast("Alert created!"); }
      setModal(null); fetchAll();
    } catch (e) { showToast(e?.response?.data?.detail || "Failed", "error"); }
    setSaving(false);
  };

  const resolveAlert = async (a) => {
    try { await API.resolveAlert(getAlertKey(a)); showToast("Alert resolved!"); fetchAll(); }
    catch { showToast("Resolve failed", "error"); }
  };

  const deleteAlert = async (a) => {
    try { await API.deleteAlert(getAlertKey(a)); showToast("Alert deleted!"); fetchAll(); }
    catch { showToast("Delete failed", "error"); }
    setConfirmDel(null);
  };

  const bulkResolveAlerts = async () => {
    const unresolved = alerts.filter(a => !a.is_resolved);
    if (!unresolved.length) return showToast("No unresolved alerts", "info");
    try {
      // Use alert_id (UUID) for bulk resolve — backend uses alert_id__in
      await API.bulkResolve(unresolved.map(a => a.alert_id));
      showToast(`${unresolved.length} alerts resolved!`); fetchAll();
    } catch { showToast("Bulk resolve failed", "error"); }
  };

  // ── Attempts bulk ────────────────────────────────────────────────
  // Attempt uses attempt_id (UUID) not integer id
  const getAttemptKey = (a) => a.id || a.attempt_id;

  const bulkUpdateAttempts = async (action) => {
    if (!selectedAttempts.length) return showToast("Select attempts first", "info");
    try {
      await API.bulkAttempts({ attempt_ids: selectedAttempts, action });
      showToast(`${selectedAttempts.length} attempts marked ${action}!`);
      setSelectedAttempts([]); fetchAll();
    } catch { showToast("Bulk update failed", "error"); }
  };

  // ── Risk data ─────────────────────────────────────────────────────
  const riskCounts = {
    high:   riskProfiles.filter(p => p.monitoring_level==="strict").length,
    medium: riskProfiles.filter(p => p.monitoring_level==="enhanced").length,
    low:    riskProfiles.filter(p => p.monitoring_level==="normal").length,
  };

  const { chart, patterns, ip_rep } = FALLBACK;
  const maxChart = Math.max(...chart.map(c => Math.max(c.blocked, c.success, c.failed)));

  const navItems = [
    { label:"Dashboard",             icon:"🏠" },
    { label:"Active Fraud Rules",    icon:"🛡️", badge:rules.filter(r=>r.is_active).length.toString(), green:true },
    { label:"Fraud Attempts",        icon:"⚠️", badge:attempts.length.toString() },
    { label:"Live Fraud Alerts",     icon:"🚨", badge:alertCounts.critical.toString() },
    { label:"User Risk Profiles",    icon:"👤", badge:riskProfiles.filter(r=>r.is_flagged).length.toString() },
    { label:"Fraud Patterns",        icon:"🔍" },
    { label:"Device Fingerprints",   icon:"🖥️" },
    { label:"IP Reputation",         icon:"🌐" },
    { label:"Offer Completion",      icon:"🎯" },
    { label:"Reports",               icon:"📊" },
    { label:"System Health",         icon:"✅" },
    { label:"Settings",              icon:"🔧" },
  ];

  const sidebarActiveCount = rules.filter(r=>r.is_active).length;

  // ── Severity color helper ────────────────────────────────────────
  const sevColor = (s) => s==="critical"?"#ff2244":s==="high"?"#ffb700":s==="medium"?"#00f5ff":"#00ff88";
  const sevBg    = (s) => s==="critical"?"rgba(255,34,68,.18)":s==="high"?"rgba(255,183,0,.18)":s==="medium"?"rgba(0,245,255,.12)":"rgba(0,255,136,.12)";

  return (
    <div className="fd-root">
      <div className="fd-bg"/>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={()=>setToast(null)}/>}

      {modal?.type==="rule" && (
        <CRUDModal title={modal.data?"✏️ EDIT RULE":"✦ CREATE RULE"} fields={ruleFields}
          values={modal.data} onSave={saveRule} onClose={()=>setModal(null)} saving={saving}/>
      )}
      {modal?.type==="alert" && (
        <CRUDModal title={modal.data?"✏️ EDIT ALERT":"✦ CREATE ALERT"} fields={alertFields}
          values={modal.data} onSave={saveAlert} onClose={()=>setModal(null)} saving={saving}/>
      )}
      {confirmDel && <ConfirmModal msg={confirmDel.msg} onConfirm={confirmDel.onConfirm} onClose={()=>setConfirmDel(null)}/>}

      {/* HEADER */}
      <header className="fd-header">
        <div className="fd-logo-wrap">
          <div className="fd-logo-title"><span>FRAUD</span> DETECTION</div>
          <div className="fd-logo-sub">— CONTROL PANEL —</div>
        </div>
        <div className="fd-logo-divider"/>
        <div className="fd-search-wrap">
          <span className="fd-search-icon">🔍</span>
          <input placeholder="Search Fraud Data..."/>
        </div>
        <div className="fd-header-spacer"/>
        <div className="fd-header-icons">
          {/* Notifications bell */}
          <div className="fd-hicon" onClick={()=>setActiveNav("Live Fraud Alerts")} style={{cursor:"pointer"}} title="Live Alerts">
            🔔
            {alertCounts.critical > 0 && <span className="fd-hicon-badge">{alertCounts.critical}</span>}
          </div>
          {/* Shield — System Health */}
          <div className="fd-hicon" onClick={()=>setActiveNav("System Health")} style={{cursor:"pointer"}} title="System Health">
            🛡️<span className="fd-hicon-dot"/>
          </div>
          {/* All alerts count */}
          <div className="fd-hicon" onClick={()=>setActiveNav("Live Fraud Alerts")} style={{cursor:"pointer"}} title="All Alerts">
            🔔
            {alerts.filter(a=>!a.is_resolved).length > 0 && <span className="fd-hicon-badge">{alerts.filter(a=>!a.is_resolved).length}</span>}
          </div>
          {/* Reports */}
          <div className="fd-hicon" onClick={()=>setActiveNav("Reports")} style={{cursor:"pointer"}} title="Reports">🔰</div>
          {/* Settings */}
          <div className="fd-hicon" onClick={()=>setActiveNav("Settings")} style={{cursor:"pointer"}} title="Settings">⚙️</div>
          {/* New Rule */}
          <div className="fd-hicon" onClick={()=>{setActiveNav("Active Fraud Rules");setModal({type:"rule",data:null});}} style={{cursor:"pointer"}} title="Add New Rule">✚</div>
        </div>
        <div style={{width:"1px",height:"30px",background:"rgba(0,245,255,0.2)",margin:"0 6px"}}/>
        <div className="fd-user-wrap">
          {currentUser?.profile_picture || currentUser?.avatar
            ? <img src={currentUser.profile_picture || currentUser.avatar} alt="" style={{width:32,height:32,borderRadius:"50%",border:"1px solid rgba(0,245,255,.3)",objectFit:"cover"}}/>
            : <div className="fd-user-avatar">👤</div>
          }
          <div>
            <div className="fd-user-name">{currentUser?.full_name || currentUser?.username || "Admin"}</div>
            <div className="fd-user-role">⭐ {currentUser?.is_superuser?"Super Administrator":currentUser?.role||"Administrator"}</div>
          </div>
        </div>
      </header>

      {/* BODY */}
      <div className="fd-body">
        {/* SIDEBAR */}
        <aside className="fd-sidebar">
          <div style={{padding:"10px 10px 4px"}}>
            <div className="fd-nav-section-label">Navigation</div>
          </div>
          {navItems.map(n => (
            <div key={n.label} className={`fd-nav-item${activeNav===n.label?" active":""}`} onClick={()=>setActiveNav(n.label)}>
              <div className="fd-nav-left">
                <span className="fd-nav-icon">{n.icon}</span>
                <span>{n.label}</span>
              </div>
              <div style={{display:"flex",alignItems:"center",gap:"3px"}}>
                {n.badge && n.badge!=="0" && <span className={`fd-nav-badge${n.green?" fd-nav-badge-green":""}`}>{n.badge}</span>}
                <span className="fd-nav-arrow">›</span>
              </div>
            </div>
          ))}
          <div className="fd-sidebar-support">
            <div className="fd-support-icon">🎧</div>
            <div>
              <div className="fd-support-text">Live Support</div>
              <div className="fd-support-status">✦ 24/7 Online</div>
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <main className="fd-main">

          {/* ── ACTIVE FRAUD RULES ── */}
          {activeNav==="Active Fraud Rules" && (
            <div className="fd-panel fd-panel-amber" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd">
                <span className="fd-panel-title fd-panel-title-amber">🛡 Active Fraud Rules</span>
                <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={()=>setModal({type:"rule",data:null})}>+ New Rule</button>
              </div>
              <div className="fd-panel-body">
                {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
                rules.length===0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No rules found</div> :
                rules.map(r => (
                  <div key={r.id} style={{display:"flex",alignItems:"center",gap:8,padding:"9px 12px",marginBottom:6,background:"rgba(0,0,0,.25)",borderRadius:9,border:`1px solid ${r.is_active?"rgba(255,183,0,.2)":"rgba(255,255,255,.05)"}`}}>
                    <span style={{fontSize:14}}>{r.severity==="critical"?"🚨":r.severity==="high"?"⚠️":"🛡️"}</span>
                    <div style={{flex:1}}>
                      <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{r.name}</div>
                      <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{r.rule_type} • {r.run_frequency} • weight: {r.weight} • threshold: {r.threshold}</div>
                    </div>
                    <span style={{fontSize:9,padding:"2px 8px",borderRadius:5,background:sevBg(r.severity),color:sevColor(r.severity)}}>{r.severity}</span>
                    <button onClick={()=>toggleRule(r)} style={{fontSize:9,padding:"3px 10px",borderRadius:5,border:"none",cursor:"pointer",background:r.is_active?"rgba(0,255,136,.15)":"rgba(255,34,68,.12)",color:r.is_active?"#00ff88":"#ff2244",fontWeight:700}}>
                      {r.is_active?"ON":"OFF"}
                    </button>
                    <button onClick={()=>setModal({type:"rule",data:r})} style={{fontSize:13,background:"none",border:"none",color:"#00f5ff",cursor:"pointer"}}>✏️</button>
                    <button onClick={()=>setConfirmDel({msg:`Delete "${r.name}"?`,onConfirm:()=>deleteRule(r.id)})} style={{fontSize:13,background:"none",border:"none",color:"#ff2244",cursor:"pointer"}}>🗑️</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── FRAUD ATTEMPTS ── */}
          {activeNav==="Fraud Attempts" && (
            <div className="fd-panel fd-panel-cyan" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd">
                <span className="fd-panel-title">⚠ Fraud Attempts ({attempts.length})</span>
                <div style={{display:"flex",gap:6}}>
                  {selectedAttempts.length>0 && <>
                    <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>bulkUpdateAttempts("confirm")}>✓ Confirm Fraud ({selectedAttempts.length})</button>
                    <button className="fd-btn fd-btn-red fd-btn-sm" onClick={()=>bulkUpdateAttempts("false_positive")}>✓ False Positive</button>
                  </>}
                  <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={fetchAll}>↺ Refresh</button>
                </div>
              </div>
              <div className="fd-panel-body">
                {/* Stats bar */}
                <div style={{display:"flex",gap:8,marginBottom:12}}>
                  {[
                    {label:"Total",val:attempts.length,c:"#00f5ff"},
                    {label:"Blocked",val:attempts.filter(a=>a.status==="blocked").length,c:"#ff2244"},
                    {label:"Reviewed",val:attempts.filter(a=>a.status==="reviewed").length,c:"#00ff88"},
                    {label:"Detected",val:attempts.filter(a=>a.status==="detected").length,c:"#ffb700"},
                  ].map((s,i) => (
                    <div key={i} style={{flex:1,background:"rgba(0,0,0,.3)",border:`1px solid ${s.c}22`,borderRadius:8,padding:"8px 10px",textAlign:"center"}}>
                      <div style={{fontSize:9,color:"rgba(140,200,230,.5)",marginBottom:3}}>{s.label}</div>
                      <div style={{fontFamily:"Orbitron",fontSize:16,color:s.c,fontWeight:700}}>{s.val}</div>
                    </div>
                  ))}
                </div>
                {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
                attempts.length===0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No attempts found</div> :
                attempts.map(a => {
                  const key = getAttemptKey(a);
                  const sc = a.status==="blocked"?"#ff2244":a.status==="reviewed"?"#00ff88":a.status==="detected"?"#ffb700":"#00f5ff";
                  return (
                    <div key={key} style={{display:"flex",alignItems:"center",gap:8,padding:"9px 12px",marginBottom:5,background:"rgba(0,0,0,.2)",borderRadius:8,borderLeft:`2px solid ${sc}`}}>
                      <input type="checkbox" checked={selectedAttempts.includes(key)} onChange={e=>setSelectedAttempts(p=>e.target.checked?[...p,key]:p.filter(x=>x!==key))} style={{accentColor:"#00f5ff"}}/>
                      <span style={{fontSize:14}}>{a.attempt_type==="multi_account"?"👤":a.attempt_type==="vpn_proxy"?"🌐":a.attempt_type==="click_fraud"?"👆":a.attempt_type==="payment_fraud"?"💳":"⚠️"}</span>
                      <div style={{flex:1}}>
                        <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{a.attempt_type?.replace(/_/g," ").toUpperCase()}</div>
                        <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{a.description?.slice(0,60)} • Fraud Score: {a.fraud_score}</div>
                      </div>
                      <span style={{fontSize:9,padding:"2px 8px",borderRadius:5,background:`${sc}22`,color:sc}}>{a.status}</span>
                      <span style={{color:"rgba(140,200,230,.4)",fontSize:9}}>{a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── LIVE FRAUD ALERTS ── */}
          {activeNav==="Live Fraud Alerts" && (
            <div className="fd-panel fd-panel-red" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd">
                <span className="fd-panel-title fd-panel-title-red"><span className="fd-live-dot"/>Live Fraud Alerts ({alerts.length})</span>
                <div style={{display:"flex",gap:6}}>
                  <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setModal({type:"alert",data:null})}>+ New</button>
                  <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={bulkResolveAlerts}>✓ Resolve All</button>
                  <button className="fd-btn fd-btn-red fd-btn-sm" onClick={fetchAll}>↺</button>
                </div>
              </div>
              <div className="fd-panel-body">
                <div className="fd-alert-counts" style={{marginBottom:12}}>
                  {[
                    {label:"Critical",val:alertCounts.critical,cls:"fd-acb-crit",nc:"neon-red"},
                    {label:"High",    val:alertCounts.high,    cls:"fd-acb-high",nc:"neon-amber"},
                    {label:"Medium",  val:alertCounts.medium,  cls:"fd-acb-med", nc:"neon-white"},
                    {label:"Low",     val:alertCounts.low,     cls:"fd-acb-low", nc:"neon-green"},
                  ].map((b,i)=>(
                    <div key={i} className={`fd-alert-count-box ${b.cls}`}>
                      <span className={`fd-acb-label ${b.nc}`}>{b.label}</span>
                      <span className={`fd-num fd-n-lg ${b.nc}`}>{b.val}</span>
                    </div>
                  ))}
                </div>
                {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
                alerts.length===0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No alerts</div> :
                alerts.map(a => {
                  const key = getAlertKey(a);
                  const pc = sevColor(a.priority);
                  return (
                    <div key={key} style={{display:"flex",alignItems:"center",gap:8,padding:"9px 12px",marginBottom:5,background:"rgba(0,0,0,.2)",borderRadius:8,borderLeft:`2px solid ${pc}`,opacity:a.is_resolved?.7:1}}>
                      <span style={{fontSize:14}}>{a.priority==="critical"?"🚨":a.priority==="high"?"⚠️":"ℹ️"}</span>
                      <div style={{flex:1}}>
                        <div style={{color:pc,fontSize:11,fontWeight:700}}>{a.title}</div>
                        <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{a.alert_type?.replace(/_/g," ")} • {a.data?.location||"Unknown"}</div>
                      </div>
                      <span style={{fontSize:9,padding:"2px 8px",borderRadius:5,background:sevBg(a.priority),color:pc}}>{a.priority}</span>
                      <span style={{color:"rgba(140,200,230,.4)",fontSize:9}}>{a.created_at ? new Date(a.created_at).toLocaleTimeString() : ""}</span>
                      {a.is_resolved
                        ? <span style={{fontSize:10,color:"#00ff88"}}>✓ Resolved</span>
                        : <button onClick={()=>resolveAlert(a)} style={{fontSize:9,padding:"3px 8px",borderRadius:5,border:"1px solid rgba(0,255,136,.3)",background:"rgba(0,255,136,.1)",color:"#00ff88",cursor:"pointer"}}>Resolve</button>
                      }
                      <button onClick={()=>setModal({type:"alert",data:a})} style={{fontSize:13,background:"none",border:"none",color:"#00f5ff",cursor:"pointer"}}>✏️</button>
                      <button onClick={()=>setConfirmDel({msg:`Delete "${a.title}"?`,onConfirm:()=>deleteAlert(a)})} style={{fontSize:13,background:"none",border:"none",color:"#ff2244",cursor:"pointer"}}>🗑️</button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── USER RISK PROFILES ── */}
          {activeNav==="User Risk Profiles" && (
            <div className="fd-panel fd-panel-mag" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd">
                <span className="fd-panel-title fd-panel-title-mag">👤 User Risk Profiles ({riskProfiles.length})</span>
                <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={fetchAll}>↺ Refresh</button>
              </div>
              <div className="fd-panel-body">
                <div style={{display:"flex",gap:8,marginBottom:12}}>
                  {[
                    {label:"High / Critical",val:riskCounts.high,c:"#ff2244"},
                    {label:"Medium",val:riskCounts.medium,c:"#ffb700"},
                    {label:"Low",val:riskCounts.low,c:"#00ff88"},
                    {label:"Flagged",val:riskProfiles.filter(p=>p.is_flagged).length,c:"#aa44ff"},
                  ].map((s,i) => (
                    <div key={i} style={{flex:1,background:"rgba(0,0,0,.3)",border:`1px solid ${s.c}22`,borderRadius:8,padding:"8px 10px",textAlign:"center"}}>
                      <div style={{fontSize:9,color:"rgba(140,200,230,.5)",marginBottom:3}}>{s.label}</div>
                      <div style={{fontFamily:"Orbitron",fontSize:16,color:s.c,fontWeight:700}}>{s.val}</div>
                    </div>
                  ))}
                </div>
                {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
                riskProfiles.length===0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No profiles found</div> :
                riskProfiles.map(p => {
                  const lvlColor = p.monitoring_level==="critical"||p.monitoring_level==="high"?"#ff2244":p.monitoring_level==="medium"?"#ffb700":"#00ff88";
                  return (
                    <div key={p.id} style={{display:"flex",alignItems:"center",gap:8,padding:"9px 12px",marginBottom:5,background:"rgba(0,0,0,.2)",borderRadius:8,borderLeft:`2px solid ${lvlColor}`}}>
                      <span style={{fontSize:14}}>👤</span>
                      <div style={{flex:1}}>
                        <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{p.user_details?.username || `User #${p.user}`}</div>
                        <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>Score: {p.overall_risk_score} • Attempts: {p.total_fraud_attempts} • {p.monitoring_level}</div>
                      </div>
                      <div style={{width:70}}>
                        <div style={{height:4,background:"rgba(255,255,255,.1)",borderRadius:2,overflow:"hidden"}}>
                          <div style={{height:"100%",width:`${p.overall_risk_score}%`,background:lvlColor,borderRadius:2,transition:"width .5s"}}/>
                        </div>
                        <div style={{textAlign:"right",fontSize:8,color:"rgba(140,200,230,.4)",marginTop:2}}>{p.overall_risk_score}/100</div>
                      </div>
                      <span style={{fontSize:9,padding:"2px 8px",borderRadius:5,background:`${lvlColor}22`,color:lvlColor}}>{p.monitoring_level}</span>
                      {p.is_flagged && <span style={{fontSize:11,color:"#ff2244"}}>🚩</span>}
                      {p.is_restricted && <span style={{fontSize:11,color:"#ffb700"}}>🔒</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── SETTINGS ── */}
          {activeNav==="Settings" && (
            <SettingsPanel onToast={showToast} onClose={()=>setActiveNav("Dashboard")}/>
          )}

          {/* ── SYSTEM HEALTH ── */}
          {activeNav==="System Health" && (
            <div className="fd-panel fd-panel-cyan" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd"><span className="fd-panel-title">✅ System Health</span></div>
              <div className="fd-panel-body">
                {[
                  {label:"Fraud Rules Engine",  status:"Operational", score:99, c:"#00ff88"},
                  {label:"Alert System",         status:"Operational", score:97, c:"#00ff88"},
                  {label:"Risk Profile Engine",  status:"Operational", score:95, c:"#00ff88"},
                  {label:"Attempt Detector",     status:"Operational", score:98, c:"#00ff88"},
                  {label:"Auto-Ban Service",     status:"Operational", score:96, c:"#00ff88"},
                  {label:"Database",             status:"Operational", score:99, c:"#00ff88"},
                ].map((s,i) => (
                  <div key={i} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 14px",marginBottom:6,background:"rgba(0,255,136,.04)",border:"1px solid rgba(0,255,136,.12)",borderRadius:9}}>
                    <span style={{fontSize:16}}>✅</span>
                    <div style={{flex:1}}>
                      <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{s.label}</div>
                      <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{s.status}</div>
                    </div>
                    <div style={{width:80}}>
                      <div style={{height:4,background:"rgba(255,255,255,.1)",borderRadius:2,overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${s.score}%`,background:s.c,borderRadius:2}}/>
                      </div>
                    </div>
                    <span style={{color:s.c,fontSize:12,fontFamily:"Orbitron",fontWeight:700}}>{s.score}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── REPORTS ── */}
          {activeNav==="Reports" && (
            <div className="fd-panel fd-panel-cyan" style={{margin:0,flex:1}}>
              <div className="fd-panel-hd"><span className="fd-panel-title">📊 Fraud Reports</span></div>
              <div className="fd-panel-body">
                <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
                  {[
                    {title:"Total Rules",        val:summaryStats.total_rules,    icon:"🛡️", c:"#00f5ff"},
                    {title:"Active Rules",       val:summaryStats.active_rules,   icon:"✅", c:"#00ff88"},
                    {title:"Disabled Rules",     val:summaryStats.disabled_rules, icon:"❌", c:"#ff2244"},
                    {title:"Security Score",     val:`${summaryStats.security_score}%`, icon:"🔒", c:"#ffb700"},
                    {title:"Total Attempts",     val:summaryStats.total_attempts, icon:"⚠️", c:"#ff2244"},
                    {title:"Blocked",            val:summaryStats.blocked,        icon:"🚫", c:"#ff2244"},
                    {title:"Total Alerts",       val:alerts.length,               icon:"🚨", c:"#ff6680"},
                    {title:"Unresolved Alerts",  val:alerts.filter(a=>!a.is_resolved).length, icon:"🔔", c:"#ffb700"},
                    {title:"Flagged Users",      val:riskProfiles.filter(p=>p.is_flagged).length, icon:"🚩", c:"#aa44ff"},
                    {title:"High Risk Users",    val:riskCounts.high,             icon:"👤", c:"#ff2244"},
                    {title:"Critical Alerts",    val:alertCounts.critical,        icon:"🆘", c:"#ff2244"},
                    {title:"High Alerts",        val:alertCounts.high,            icon:"⚠️", c:"#ffb700"},
                  ].map((s,i) => (
                    <div key={i} style={{flex:"1 1 180px",background:"rgba(0,0,0,.3)",border:`1px solid ${s.c}22`,borderRadius:10,padding:"14px 16px"}}>
                      <div style={{fontSize:20,marginBottom:6}}>{s.icon}</div>
                      <div style={{fontSize:9,color:"rgba(140,200,230,.5)",marginBottom:4,fontFamily:"Orbitron"}}>{s.title}</div>
                      <div style={{fontFamily:"Orbitron",fontSize:20,color:s.c,fontWeight:700}}>{s.val}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── DASHBOARD (default) ── */}
          {(activeNav==="Dashboard"||activeNav==="Fraud Patterns"||activeNav==="Device Fingerprints"||activeNav==="IP Reputation"||activeNav==="Offer Completion") && (
            <>
              {/* ROW 1 */}
              <div className="fd-row">
                {/* Settings panel */}
                <div className="fd-panel fd-panel-cyan fd-col-35">
                  <div className="fd-scan-line"/>
                  <div className="fd-panel-hd">
                    <span className="fd-panel-title">⚙ Global Fraud Settings</span>
                    <span className="fd-live-dot"/>
                  </div>
                  <div className="fd-panel-body">
                    <div style={{display:"flex",gap:"10px"}}>
                      <div style={{flex:1}}>
                        <div style={{position:"relative",height:"56px",marginBottom:"8px",borderRadius:"5px",overflow:"hidden"}}>
                          <div className="fd-world-map"/>
                          {MAP_DOTS.slice(0,6).map((d,i)=>(
                            <div key={i} className={`fd-map-dot ${d.c}`} style={{left:d.x,top:d.y,animationDelay:`${d.delay}s`}}/>
                          ))}
                        </div>
                        <div style={{marginBottom:"6px"}}>
                          <div className="fd-label-sm">Total Rules</div>
                          <span className="fd-num fd-n-xl neon-white">{summaryStats.total_rules}</span>
                        </div>
                        <div style={{display:"flex",gap:"16px",marginBottom:"8px"}}>
                          <div><span style={{fontSize:"9px",color:"#00ff88"}}>● Active </span><span className="fd-num fd-n-sm neon-green">{summaryStats.active_rules}</span></div>
                          <div><span style={{fontSize:"9px",color:"#ff2244"}}>● Disabled </span><span className="fd-num fd-n-sm neon-red">{summaryStats.disabled_rules}</span></div>
                        </div>
                        <div style={{display:"flex",gap:"5px"}}>
                          <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("Active Fraud Rules")}>Manage Rules</button>
                          <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={()=>{setActiveNav("Active Fraud Rules");setModal({type:"rule",data:null});}}>+ Add</button>
                        </div>
                      </div>
                      <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
                        <div className="fd-label-sm" style={{marginBottom:"3px"}}>Security Score</div>
                        <CircularGauge pct={summaryStats.security_score} size={92} color="#00ff88" label="Secure"/>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Rules preview */}
                <div className="fd-panel fd-panel-amber fd-col-28">
                  <div className="fd-panel-hd">
                    <span className="fd-panel-title fd-panel-title-amber">🛡 Active Fraud Rules</span>
                    <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={()=>setActiveNav("Active Fraud Rules")}>View All</button>
                  </div>
                  <div className="fd-panel-body">
                    {rules.filter(r=>r.is_active).slice(0,4).map((r,i)=>(
                      <div key={r.id} className="fd-rule-row">
                        <span className="fd-rule-icon">{r.severity==="critical"?"🚨":r.severity==="high"?"⚠️":"🛡️"}</span>
                        <span className="fd-rule-name">{r.name}</span>
                        <div className="fd-rule-bar-wrap">
                          <div className="fd-progress">
                            <div className="fd-progress-fill" style={{width:`${r.weight}%`,background:i===0?"linear-gradient(90deg,#ff2244,#ff6680)":i===1?"linear-gradient(90deg,#ffb700,#ffd060)":i===2?"linear-gradient(90deg,#0066ff,#00f5ff)":"linear-gradient(90deg,#00aa55,#00ff88)"}}/>
                          </div>
                        </div>
                        <span className="fd-rule-count neon-white">{r.weight}</span>
                      </div>
                    ))}
                    {rules.filter(r=>r.is_active).length===0 && <div style={{color:"rgba(140,200,230,.3)",fontSize:10,textAlign:"center",padding:"10px 0"}}>No active rules</div>}
                  </div>
                </div>

                {/* Alerts preview */}
                <div className="fd-panel fd-panel-red fd-col-fill">
                  <div className="fd-panel-hd">
                    <span className="fd-panel-title fd-panel-title-red"><span className="fd-live-dot"/>Live Fraud Alerts</span>
                    <button className="fd-btn fd-btn-red fd-btn-sm" onClick={()=>setActiveNav("Live Fraud Alerts")}>View All</button>
                  </div>
                  <div className="fd-panel-body">
                    <div className="fd-alert-counts">
                      {[
                        {label:"Critical",val:alertCounts.critical,cls:"fd-acb-crit",nc:"neon-red"},
                        {label:"High",    val:alertCounts.high,    cls:"fd-acb-high",nc:"neon-amber"},
                        {label:"Medium",  val:alertCounts.medium,  cls:"fd-acb-med", nc:"neon-white"},
                        {label:"Low",     val:alertCounts.low,     cls:"fd-acb-low", nc:"neon-green"},
                      ].map((b,i)=>(
                        <div key={i} className={`fd-alert-count-box ${b.cls}`}>
                          <span className={`fd-acb-label ${b.nc}`}>{b.label}</span>
                          <span className={`fd-num fd-n-lg ${b.nc}`}>{b.val}</span>
                        </div>
                      ))}
                    </div>
                    <div className="fd-scroll-list" ref={scrollRef}>
                      {alerts.slice(0,6).map(a => (
                        <div key={getAlertKey(a)} className={`fd-alert-item fd-alert-${a.priority}`}>
                          <span className="fd-alert-icon">{a.priority==="critical"?"🚨":a.priority==="high"?"⚠️":"ℹ️"}</span>
                          <div style={{flex:1}}>
                            <div className={`fd-alert-title ${a.priority==="critical"?"neon-red":a.priority==="high"?"neon-amber":""}`}>{a.title}</div>
                            <div className="fd-alert-meta"><span>🌐</span><span>{a.data?.location||"Unknown"}</span></div>
                          </div>
                          <span className="fd-alert-time">{a.created_at ? new Date(a.created_at).toLocaleTimeString() : ""}</span>
                        </div>
                      ))}
                      {alerts.length===0 && <div style={{color:"rgba(140,200,230,.3)",fontSize:10,textAlign:"center",padding:"10px 0"}}>No alerts</div>}
                    </div>
                  </div>
                </div>
              </div>

              {/* ROW 2 */}
              <div className="fd-row">
                <div className="fd-panel fd-panel-cyan fd-col-60">
                  <div className="fd-panel-hd">
                    <span className="fd-panel-title">⚠ Fraud Attempts & Patterns</span>
                    <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("Fraud Attempts")}>View All</button>
                  </div>
                  <div className="fd-panel-body">
                    <div style={{display:"flex",gap:"7px",marginBottom:"10px"}}>
                      {[
                        {label:"Total Attempts",val:summaryStats.total_attempts,nc:"neon-white",bg:"rgba(0,30,60,0.5)",bc:"rgba(0,245,255,0.25)"},
                        {label:"🛡 Blocked",    val:summaryStats.blocked,       nc:"neon-cyan", bg:"rgba(0,20,50,0.5)",  bc:"rgba(0,100,180,0.35)"},
                        {label:"✅ Active",     val:summaryStats.success,       nc:"neon-green",bg:"rgba(0,25,15,0.5)",  bc:"rgba(0,255,136,0.25)"},
                      ].map((s,i)=>(
                        <div key={i} className="fd-stat-box" style={{background:s.bg,borderColor:s.bc}}>
                          <div className="fd-stat-label">{s.label}</div>
                          <div className={`fd-stat-val ${s.nc}`}>{s.val.toLocaleString()}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{display:"flex",gap:"12px"}}>
                      <div style={{flex:1}}>
                        <div className="fd-label-sm" style={{marginBottom:"4px"}}>Attempts (7 Day Trend)</div>
                        <div className="fd-chart-legend">
                          {[["Blocked","#00aaff"],["Success","#00ff88"],["Failed","#ff2244"]].map(([l,c])=>(
                            <div key={l} className="fd-legend-item"><div className="fd-legend-dot" style={{background:c,boxShadow:`0 0 4px ${c}`}}/>{l}</div>
                          ))}
                        </div>
                        <div className="fd-bar-chart">
                          {chart.map((c,i)=>(
                            <div key={i} className="fd-bar-group">
                              <div className="fd-bar fd-bar-blocked" style={{height:`${(c.blocked/maxChart)*100}%`}}/>
                              <div className="fd-bar fd-bar-success" style={{height:`${(c.success/maxChart)*100}%`}}/>
                              <div className="fd-bar fd-bar-failed"  style={{height:`${(c.failed/maxChart)*100}%`}}/>
                            </div>
                          ))}
                        </div>
                        <div className="fd-chart-labels">{chart.map(c=><span key={c.day}>{c.day}</span>)}</div>
                      </div>
                      <div style={{width:"155px"}}>
                        <div className="fd-label-sm" style={{marginBottom:"4px"}}>Top Patterns</div>
                        <DonutChart data={patterns} size={78}/>
                        {patterns.map((p,i)=>(
                          <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:"4px"}}>
                            <div style={{display:"flex",alignItems:"center",gap:"4px"}}>
                              <div style={{width:"7px",height:"7px",borderRadius:"50%",background:p.color,flexShrink:0}}/>
                              <span style={{fontSize:"9px"}}>{p.icon} {p.name}</span>
                            </div>
                            <span className="fd-num fd-n-xs" style={{color:p.color}}>{p.pct}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Risk Profiles */}
                <div className="fd-panel fd-panel-mag fd-col-fill">
                  <div className="fd-panel-hd">
                    <span className="fd-panel-title fd-panel-title-mag">👤 User Risk Profiles</span>
                    <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("User Risk Profiles")}>View All</button>
                  </div>
                  <div className="fd-panel-body">
                    {[
                      {label:"High Risk",  num:riskCounts.high,   cls:"fd-risk-high",  nc:"neon-red",   icon:"👤"},
                      {label:"Medium Risk",num:riskCounts.medium, cls:"fd-risk-medium", nc:"neon-amber", icon:"👥"},
                      {label:"Low Risk",   num:riskCounts.low,    cls:"fd-risk-low",    nc:"neon-green", icon:"✅"},
                    ].map((r,i)=>(
                      <div key={i} className={`fd-risk-row ${r.cls}`}>
                        <span className="fd-risk-icon">{r.icon}</span>
                        <div style={{flex:1}}>
                          <div className={`fd-risk-label ${r.nc}`}>{r.label}</div>
                          <div className={`fd-risk-num ${r.nc}`}>{r.num.toLocaleString()}</div>
                        </div>
                      </div>
                    ))}
                    <hr className="fd-divider"/>
                    <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
                      <DonutChart data={[
                        {pct:Math.max(riskCounts.high,1),color:"#ff2244"},
                        {pct:Math.max(riskCounts.medium,1),color:"#ffb700"},
                        {pct:Math.max(riskCounts.low,1),color:"#00ff88"},
                      ]} size={70}/>
                      <div>
                        {[["High","#ff2244"],["Medium","#ffb700"],["Low","#00ff88"]].map(([l,c])=>(
                          <div key={l} style={{display:"flex",alignItems:"center",gap:"5px",marginBottom:"5px"}}>
                            <div style={{width:"7px",height:"7px",borderRadius:"50%",background:c}}/>
                            <span style={{fontSize:"10px",color:"rgba(140,200,230,0.6)"}}>{l}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* ROW 3 */}
              <div className="fd-row">
                <div className="fd-panel fd-panel-cyan fd-col-55">
                  <div className="fd-panel-hd"><span className="fd-panel-title">🖥 Device Fingerprints & IP Reputation</span></div>
                  <div className="fd-panel-body">
                    <div style={{display:"flex",gap:"10px"}}>
                      <div style={{flex:1}}>
                        <div className="fd-label-sm" style={{marginBottom:"5px"}}>● IP Reputation</div>
                        <table className="fd-ip-table">
                          <thead><tr><th>Country</th><th>Risk Score</th><th>Status</th></tr></thead>
                          <tbody>
                            {ip_rep.map((r,i)=>(
                              <tr key={i}>
                                <td><span className="fd-flag">{r.flag}</span>{r.country}</td>
                                <td><span className={`fd-num fd-n-xs ${r.status==="High"?"neon-red":r.status==="Medium"?"neon-amber":"neon-green"}`}>{r.score}</span></td>
                                <td><span className={`fd-badge ${r.status==="High"?"fd-badge-red":r.status==="Medium"?"fd-badge-amber":"fd-badge-green"}`}>{r.status}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div style={{flex:1,position:"relative",minHeight:"115px",borderRadius:"5px",overflow:"hidden"}}>
                        <div className="fd-world-map" style={{position:"absolute",inset:0}}/>
                        {MAP_DOTS.map((d,i)=>(
                          <div key={i} className={`fd-map-dot ${d.c}`} style={{left:d.x,top:d.y,animationDelay:`${d.delay}s`}}/>
                        ))}
                        <svg style={{position:"absolute",inset:0,width:"100%",height:"100%"}}>
                          <line x1="22%" y1="30%" x2="48%" y2="25%" stroke="rgba(0,245,255,0.2)" strokeWidth="1" strokeDasharray="3,3"/>
                          <line x1="48%" y1="25%" x2="70%" y2="60%" stroke="rgba(255,34,68,0.2)"  strokeWidth="1" strokeDasharray="3,3"/>
                          <line x1="30%" y1="55%" x2="70%" y2="60%" stroke="rgba(255,183,0,0.2)"  strokeWidth="1" strokeDasharray="3,3"/>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="fd-panel fd-panel-green fd-col-fill">
                  <div className="fd-panel-hd"><span className="fd-panel-title fd-panel-title-green">🎯 Offer Completion Monitoring</span></div>
                  <div className="fd-panel-body">
                    <div style={{display:"flex",gap:"8px",alignItems:"flex-start"}}>
                      <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
                        <div className="fd-label-sm" style={{marginBottom:"2px"}}>Completion Rate</div>
                        <RateGauge pct={79}/>
                      </div>
                      <div style={{flex:1}}>
                        <div className="fd-label-sm" style={{marginBottom:"3px"}}>Real-Time Activity</div>
                        <MiniBarChart data={[18,25,22,30,28,35,20]}/>
                        <div style={{display:"flex",justifyContent:"space-between",marginTop:4}}>
                          {["00","03","06","09","12","15","18"].map(t=>(
                            <span key={t} className="fd-mono" style={{fontSize:"8px",color:"rgba(140,200,230,0.4)"}}>{t}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}


// // pages/FraudDetection.jsx
// import { useState, useEffect, useRef, useCallback } from "react";
// import client from "../api/client";
// import "../styles/FraudDetection.css";

// // ─── API helpers ──────────────────────────────────────────────────
// const API = {
//   // Dashboard
//   dashboard:    () => client.get("/fraud_detection/dashboard/"),
//   stats:        () => client.get("/fraud_detection/statistics/"),
//   // Rules CRUD
//   getRules:     (p={}) => client.get("/fraud_detection/rules/", { params: p }),
//   createRule:   (d)    => client.post("/fraud_detection/rules/", d),
//   updateRule:   (id,d) => client.patch(`/fraud_detection/rules/${id}/`, d),
//   deleteRule:   (id)   => client.delete(`/fraud_detection/rules/${id}/`),
//   ruleStats:    ()     => client.get("/fraud_detection/rules/stats/"),
//   // Attempts
//   getAttempts:  (p={}) => client.get("/fraud_detection/attempts/", { params: p }),
//   updateAttempt:(id,d) => client.patch(`/fraud_detection/attempts/${id}/`, d),
//   bulkAttempts: (d)    => client.post("/fraud_detection/attempts/bulk-update/", d),
//   attemptStats: ()     => client.get("/fraud_detection/attempts/statistics/"),
//   // Alerts CRUD
//   getAlerts:    (p={}) => client.get("/fraud_detection/alerts/", { params: p }),
//   createAlert:  (d)    => client.post("/fraud_detection/alerts/", d),
//   updateAlert:  (id,d) => client.patch(`/fraud_detection/alerts/${id}/`, d),
//   deleteAlert:  (id)   => client.delete(`/fraud_detection/alerts/${id}/`),
//   resolveAlert: (id,d) => client.post(`/fraud_detection/alerts/${id}/resolve/`, d),
//   bulkResolve:  (d)    => client.post("/fraud_detection/alerts/bulk-resolve/", d),
//   alertStats:   ()     => client.get("/fraud_detection/alerts/dashboard-stats/"),
//   // Risk Profiles
//   getRiskProfiles:(p={}) => client.get("/fraud_detection/risk-profiles/", { params: p }),
//   highRisk:       ()     => client.get("/fraud_detection/risk-profiles/high-risk/"),
//   riskDist:       ()     => client.get("/fraud_detection/risk-profiles/distribution/"),
//   // Settings
//   getSettings:  () => client.get("/fraud_detection/settings/block-vpn/"),
//   saveSettings: (d)=> client.post("/fraud_detection/settings/block-vpn/", d),
// };

// // ─── Static fallback ──────────────────────────────────────────────
// const FALLBACK = {
//   settings: { total_rules: 0, active_rules: 0, disabled_rules: 0, security_score: 0 },
//   rules: [],
//   attempts: { total: 0, blocked: 0, success: 0, change: "+0%" },
//   chart: [
//     { day: "Sun", blocked: 72, success: 45, failed: 28 },
//     { day: "Mon", blocked: 85, success: 52, failed: 35 },
//     { day: "Tue", blocked: 68, success: 38, failed: 22 },
//     { day: "Wed", blocked: 92, success: 61, failed: 40 },
//     { day: "Thu", blocked: 78, success: 49, failed: 30 },
//     { day: "Fri", blocked: 88, success: 55, failed: 42 },
//     { day: "Sat", blocked: 95, success: 65, failed: 38 },
//   ],
//   patterns: [
//     { name: "Credential Stuffing", icon: "🔑", pct: 45, color: "#ff2244" },
//     { name: "Bot Attack",          icon: "🤖", pct: 30, color: "#ffb700" },
//     { name: "Phishing",            icon: "🎣", pct: 15, color: "#0066ff" },
//     { name: "Geo-Spike",           icon: "🌍", pct: 10, color: "#aa44ff" },
//   ],
//   risk: { high: 0, medium: 0, low: 0 },
//   devices: { tracked: 0, suspicious: 0, trusted: 0 },
//   ip_rep: [
//     { country: "USA",    flag: "🇺🇸", score: 92, status: "High"   },
//     { country: "India",  flag: "🇮🇳", score: 75, status: "Medium" },
//     { country: "Russia", flag: "🇷🇺", score: 60, status: "Medium" },
//     { country: "Brazil", flag: "🇧🇷", score: 45, status: "Low"    },
//     { country: "China",  flag: "🇨🇳", score: 38, status: "High"   },
//   ],
//   alerts: [],
//   alert_counts: { critical: 0, high: 0, medium: 0, low: 0 },
//   offers: { total: 0, completed: 0, pending: 0, rate: 0 },
//   offer_feed: [],
// };

// const MAP_DOTS = [
//   { x: "22%", y: "30%", c: "fd-map-red",   delay: 0   },
//   { x: "48%", y: "25%", c: "fd-map-cyan",  delay: 0.4 },
//   { x: "55%", y: "32%", c: "fd-map-red",   delay: 0.8 },
//   { x: "30%", y: "55%", c: "fd-map-amber", delay: 0.2 },
//   { x: "70%", y: "60%", c: "fd-map-red",   delay: 0.6 },
//   { x: "80%", y: "25%", c: "fd-map-cyan",  delay: 1.0 },
//   { x: "15%", y: "65%", c: "fd-map-red",   delay: 0.3 },
//   { x: "60%", y: "70%", c: "fd-map-amber", delay: 0.7 },
// ];

// // ─── Circular Gauge ───────────────────────────────────────────────
// function CircularGauge({ pct, color = "#00f5ff", size = 90, label = "Secure" }) {
//   const r = (size - 14) / 2;
//   const circ = 2 * Math.PI * r;
//   const offset = circ - (pct / 100) * circ;
//   return (
//     <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
//       <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(0,245,255,0.1)" strokeWidth="8"/>
//       <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="8"
//         strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
//         transform={`rotate(-90 ${size/2} ${size/2})`}
//         style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "stroke-dashoffset 1s ease" }}/>
//       <text x={size/2} y={size/2 - 4} textAnchor="middle" fill={color}
//         fontSize="13" fontFamily="Orbitron" fontWeight="700">{pct}%</text>
//       <text x={size/2} y={size/2 + 11} textAnchor="middle"
//         fill="rgba(140,200,230,0.6)" fontSize="7" fontFamily="Orbitron">{label}</text>
//     </svg>
//   );
// }

// // ─── Donut Chart ──────────────────────────────────────────────────
// function DonutChart({ data, size = 80 }) {
//   const cx = size / 2, cy = size / 2, r = size * 0.35;
//   const circ = 2 * Math.PI * r;
//   let offset = 0;
//   const total = data.reduce((s, d) => s + d.pct, 0);
//   return (
//     <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
//       <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="14"/>
//       {data.map((d, i) => {
//         const dash = (d.pct / total) * circ;
//         const el = (
//           <circle key={i} cx={cx} cy={cy} r={r} fill="none"
//             stroke={d.color} strokeWidth="14"
//             strokeDasharray={`${dash} ${circ - dash}`}
//             strokeDashoffset={-offset}
//             transform={`rotate(-90 ${cx} ${cy})`}
//             style={{ filter: `drop-shadow(0 0 4px ${d.color})` }}/>
//         );
//         offset += dash;
//         return el;
//       })}
//     </svg>
//   );
// }

// // ─── Rate Gauge ───────────────────────────────────────────────────
// function RateGauge({ pct }) {
//   const r = 34, circ = 2 * Math.PI * r;
//   return (
//     <svg width="88" height="72" viewBox="0 0 88 72">
//       <defs>
//         <linearGradient id="rg" x1="0" y1="0" x2="1" y2="0">
//           <stop offset="0%"   stopColor="#0066ff"/>
//           <stop offset="50%"  stopColor="#00ff88"/>
//           <stop offset="100%" stopColor="#ffb700"/>
//         </linearGradient>
//       </defs>
//       <circle cx="44" cy="52" r={r} fill="none" stroke="rgba(0,245,255,0.1)" strokeWidth="9"
//         strokeDasharray={`${circ * 0.75} ${circ * 0.25}`} transform="rotate(135 44 52)" strokeLinecap="round"/>
//       <circle cx="44" cy="52" r={r} fill="none" stroke="url(#rg)" strokeWidth="9"
//         strokeDasharray={`${(pct/100)*circ*0.75} ${circ}`} transform="rotate(135 44 52)" strokeLinecap="round"
//         style={{ filter: "drop-shadow(0 0 5px #00ff88)" }}/>
//       <text x="44" y="52" textAnchor="middle" fill="#00ff88"
//         fontSize="16" fontFamily="Orbitron" fontWeight="900">{pct}%</text>
//       <text x="44" y="63" textAnchor="middle" fill="rgba(140,200,230,0.6)"
//         fontSize="6" fontFamily="Orbitron">COMPLETION</text>
//     </svg>
//   );
// }

// // ─── Mini Bar ─────────────────────────────────────────────────────
// function MiniBarChart({ data }) {
//   const max = Math.max(...data);
//   const colors = ["#0066ff","#00ff88","#ffb700","#ff2244","#aa44ff","#00f5ff","#ff66aa"];
//   return (
//     <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "46px" }}>
//       {data.map((v, i) => (
//         <div key={i} style={{
//           flex: 1, borderRadius: "2px 2px 0 0",
//           height: `${(v / max) * 100}%`,
//           background: `linear-gradient(to top, ${colors[i]}88, ${colors[i]})`,
//           boxShadow: `0 0 4px ${colors[i]}66`, minWidth: "5px",
//         }}/>
//       ))}
//     </div>
//   );
// }

// // ─── CRUD Modal ───────────────────────────────────────────────────
// function CRUDModal({ title, fields, values, onSave, onClose, saving }) {
//   const [form, setForm] = useState(values || {});
//   const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

//   return (
//     <div style={{
//       position: "fixed", inset: 0, background: "rgba(0,0,0,.8)",
//       zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center"
//     }} onClick={onClose}>
//       <div onClick={e => e.stopPropagation()} style={{
//         background: "linear-gradient(135deg,#0a0a1a,#0d0a20)",
//         border: "1px solid rgba(0,245,255,.25)", borderRadius: 16,
//         padding: 28, minWidth: 480, maxWidth: 600, maxHeight: "85vh",
//         overflowY: "auto", position: "relative"
//       }}>
//         <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
//           <span style={{ fontFamily: "Orbitron", fontSize: 14, color: "#00f5ff", letterSpacing: 2 }}>{title}</span>
//           <button onClick={onClose} style={{ background: "none", border: "none", color: "#ff2244", fontSize: 18, cursor: "pointer" }}>✕</button>
//         </div>
//         {fields.map(f => (
//           <div key={f.key} style={{ marginBottom: 14 }}>
//             <label style={{ display: "block", fontSize: 10, color: "rgba(140,200,230,.6)", letterSpacing: 1, marginBottom: 5, fontFamily: "Orbitron" }}>
//               {f.label}
//             </label>
//             {f.type === "select" ? (
//               <select value={form[f.key] || ""} onChange={e => set(f.key, e.target.value)} style={{
//                 width: "100%", background: "rgba(0,20,40,.8)", border: "1px solid rgba(0,245,255,.2)",
//                 borderRadius: 8, padding: "9px 12px", color: "#fff", fontSize: 12, outline: "none"
//               }}>
//                 {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
//               </select>
//             ) : f.type === "textarea" ? (
//               <textarea value={form[f.key] || ""} onChange={e => set(f.key, e.target.value)} rows={3} style={{
//                 width: "100%", background: "rgba(0,20,40,.8)", border: "1px solid rgba(0,245,255,.2)",
//                 borderRadius: 8, padding: "9px 12px", color: "#fff", fontSize: 12, outline: "none",
//                 resize: "vertical", fontFamily: "inherit"
//               }}/>
//             ) : (
//               <input type={f.type || "text"} value={form[f.key] || ""} onChange={e => set(f.key, e.target.value)} style={{
//                 width: "100%", background: "rgba(0,20,40,.8)", border: "1px solid rgba(0,245,255,.2)",
//                 borderRadius: 8, padding: "9px 12px", color: "#fff", fontSize: 12, outline: "none"
//               }}/>
//             )}
//           </div>
//         ))}
//         <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
//           <button onClick={() => onSave(form)} disabled={saving} style={{
//             flex: 1, background: "rgba(0,245,255,.15)", border: "1px solid rgba(0,245,255,.4)",
//             borderRadius: 8, padding: "10px 0", color: "#00f5ff", fontFamily: "Orbitron",
//             fontSize: 11, cursor: saving ? "not-allowed" : "pointer", letterSpacing: 1
//           }}>
//             {saving ? "SAVING..." : "✦ SAVE"}
//           </button>
//           <button onClick={onClose} style={{
//             flex: 1, background: "rgba(255,34,68,.1)", border: "1px solid rgba(255,34,68,.3)",
//             borderRadius: 8, padding: "10px 0", color: "#ff2244", fontFamily: "Orbitron",
//             fontSize: 11, cursor: "pointer", letterSpacing: 1
//           }}>CANCEL</button>
//         </div>
//       </div>
//     </div>
//   );
// }

// // ─── Confirm Delete Modal ─────────────────────────────────────────
// function ConfirmModal({ msg, onConfirm, onClose }) {
//   return (
//     <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.8)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
//       <div onClick={e => e.stopPropagation()} style={{ background: "#0a0a1a", border: "1px solid rgba(255,34,68,.3)", borderRadius: 14, padding: 28, minWidth: 340, textAlign: "center" }}>
//         <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
//         <div style={{ fontFamily: "Orbitron", fontSize: 12, color: "#fff", marginBottom: 8 }}>CONFIRM DELETE</div>
//         <div style={{ fontSize: 12, color: "rgba(140,200,230,.6)", marginBottom: 20 }}>{msg}</div>
//         <div style={{ display: "flex", gap: 10 }}>
//           <button onClick={onConfirm} style={{ flex: 1, background: "rgba(255,34,68,.2)", border: "1px solid rgba(255,34,68,.4)", borderRadius: 8, padding: "10px 0", color: "#ff2244", fontFamily: "Orbitron", fontSize: 11, cursor: "pointer" }}>DELETE</button>
//           <button onClick={onClose} style={{ flex: 1, background: "rgba(0,245,255,.1)", border: "1px solid rgba(0,245,255,.3)", borderRadius: 8, padding: "10px 0", color: "#00f5ff", fontFamily: "Orbitron", fontSize: 11, cursor: "pointer" }}>CANCEL</button>
//         </div>
//       </div>
//     </div>
//   );
// }

// // ─── Toast Notification ───────────────────────────────────────────
// function Toast({ msg, type, onClose }) {
//   useEffect(() => { const t = setTimeout(onClose, 3000); return () => clearTimeout(t); }, []);
//   const colors = { success: "#00ff88", error: "#ff2244", info: "#00f5ff" };
//   return (
//     <div style={{
//       position: "fixed", bottom: 24, right: 24, zIndex: 99999,
//       background: "rgba(10,10,26,.95)", border: `1px solid ${colors[type] || colors.info}44`,
//       borderRadius: 10, padding: "12px 20px", display: "flex", alignItems: "center", gap: 10,
//       boxShadow: `0 0 20px ${colors[type] || colors.info}22`
//     }}>
//       <span>{type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️"}</span>
//       <span style={{ color: colors[type] || colors.info, fontSize: 12, fontFamily: "Orbitron" }}>{msg}</span>
//       <button onClick={onClose} style={{ background: "none", border: "none", color: "rgba(255,255,255,.4)", cursor: "pointer", fontSize: 14 }}>✕</button>
//     </div>
//   );
// }

// // ─── Main Component ───────────────────────────────────────────────
// export default function FraudDetection() {
//   const [activeNav, setActiveNav]     = useState("Dashboard");
//   const [data, setData]               = useState(FALLBACK);
//   const [rules, setRules]             = useState([]);
//   const [attempts, setAttempts]       = useState([]);
//   const [alerts, setAlerts]           = useState([]);
//   const [riskProfiles, setRiskProfiles] = useState([]);
//   const [alertCounts, setAlertCounts] = useState({ critical: 0, high: 0, medium: 0, low: 0 });
//   const [loading, setLoading]         = useState(true);
//   const [modal, setModal]             = useState(null); // {type, data}
//   const [confirmDel, setConfirmDel]   = useState(null);
//   const [saving, setSaving]           = useState(false);
//   const [toast, setToast]             = useState(null);
//   const [selectedAttempts, setSelectedAttempts] = useState([]);
//   const scrollRef = useRef(null);

//   const showToast = (msg, type = "success") => setToast({ msg, type });

//   const fetchAll = useCallback(async () => {
//     setLoading(true);
//     try {
//       const [rulesRes, attemptsRes, alertsRes, alertStatsRes, riskRes] = await Promise.allSettled([
//         API.getRules({ page_size: 10 }),
//         API.getAttempts({ page_size: 20 }),
//         API.getAlerts({ page_size: 15 }),
//         API.alertStats(),
//         API.getRiskProfiles({ page_size: 20 }),
//       ]);

//       if (rulesRes.status === "fulfilled") {
//         const r = rulesRes.value.data?.results || rulesRes.value.data || [];
//         setRules(r);
//         const active = r.filter(x => x.is_active).length;
//         setData(prev => ({ ...prev, settings: { ...prev.settings, total_rules: r.length, active_rules: active, disabled_rules: r.length - active, security_score: Math.min(99, Math.round((active / (r.length || 1)) * 100)) } }));
//       }

//       if (attemptsRes.status === "fulfilled") {
//         const a = attemptsRes.value.data?.results || attemptsRes.value.data || [];
//         setAttempts(a);
//         const blocked = a.filter(x => x.status === "blocked").length;
//         setData(prev => ({ ...prev, attempts: { total: a.length, blocked, success: a.length - blocked, change: "+22%" } }));
//       }

//       if (alertsRes.status === "fulfilled") {
//         const a = alertsRes.value.data?.results || alertsRes.value.data || [];
//         setAlerts(a);
//         const mapped = a.slice(0, 6).map(x => ({
//           id: x.id, type: x.priority || "medium",
//           icon: x.priority === "critical" ? "🚨" : x.priority === "high" ? "⚠️" : "ℹ️",
//           title: x.title || x.alert_type,
//           loc: x.data?.location || "Unknown",
//           time: x.created_at ? new Date(x.created_at).toLocaleTimeString() : "—",
//           flag: "🌐",
//         }));
//         setData(prev => ({ ...prev, alerts: mapped }));
//       }

//       if (alertStatsRes.status === "fulfilled") {
//         const s = alertStatsRes.value.data;
//         setAlertCounts({
//           critical: s?.by_priority?.critical || s?.critical || 0,
//           high:     s?.by_priority?.high     || s?.high     || 0,
//           medium:   s?.by_priority?.medium   || s?.medium   || 0,
//           low:      s?.by_priority?.low      || s?.low      || 0,
//         });
//       }

//       if (riskRes.status === "fulfilled") {
//         const r = riskRes.value.data?.results || riskRes.value.data || [];
//         setRiskProfiles(r);
//         const high   = r.filter(x => x.monitoring_level === "high" || x.monitoring_level === "critical").length;
//         const medium = r.filter(x => x.monitoring_level === "medium").length;
//         const low    = r.filter(x => x.monitoring_level === "low").length;
//         setData(prev => ({ ...prev, risk: { high, medium, low } }));
//       }
//     } catch (e) {
//       console.warn("FraudDetection fetch error:", e);
//     } finally {
//       setLoading(false);
//     }
//   }, []);

//   useEffect(() => { fetchAll(); }, [fetchAll]);

//   // ── RULE CRUD ────────────────────────────────────────────────────
//   const ruleFields = [
//     { key: "name",              label: "Rule Name",       type: "text"     },
//     { key: "description",       label: "Description",     type: "textarea" },
//     { key: "rule_type",         label: "Rule Type",       type: "select",  options: [
//         {value:"account",label:"Account"},{value:"payment",label:"Payment"},
//         {value:"offer",label:"Offer"},{value:"referral",label:"Referral"},
//         {value:"withdrawal",label:"Withdrawal"},{value:"behavior",label:"Behavior"},
//     ]},
//     { key: "severity",          label: "Severity",        type: "select",  options: [
//         {value:"low",label:"Low"},{value:"medium",label:"Medium"},
//         {value:"high",label:"High"},{value:"critical",label:"Critical"},
//     ]},
//     { key: "weight",            label: "Weight (1-100)",  type: "number"   },
//     { key: "threshold",         label: "Threshold (1-100)",type: "number"  },
//     { key: "action_on_trigger", label: "Action",          type: "select",  options: [
//         {value:"flag",label:"Flag"},{value:"review",label:"Review"},
//         {value:"limit",label:"Limit"},{value:"suspend",label:"Suspend"},
//         {value:"ban",label:"Ban"},
//     ]},
//     { key: "run_frequency",     label: "Frequency",       type: "select",  options: [
//         {value:"realtime",label:"Realtime"},{value:"hourly",label:"Hourly"},
//         {value:"daily",label:"Daily"},{value:"weekly",label:"Weekly"},
//     ]},
//   ];

//   const saveRule = async (form) => {
//     setSaving(true);
//     try {
//       if (modal.data?.id) {
//         await API.updateRule(modal.data.id, form);
//         showToast("Rule updated successfully!");
//       } else {
//         await API.createRule({ ...form, is_active: true, condition: "{}" });
//         showToast("Rule created successfully!");
//       }
//       setModal(null); fetchAll();
//     } catch (e) {
//       showToast("Failed to save rule", "error");
//     } finally { setSaving(false); }
//   };

//   const deleteRule = async (id) => {
//     try {
//       await API.deleteRule(id);
//       showToast("Rule deleted!"); fetchAll();
//     } catch { showToast("Delete failed", "error"); }
//     setConfirmDel(null);
//   };

//   const toggleRule = async (rule) => {
//     try {
//       await API.updateRule(rule.id, { is_active: !rule.is_active });
//       showToast(`Rule ${!rule.is_active ? "activated" : "deactivated"}!`);
//       fetchAll();
//     } catch { showToast("Failed to toggle rule", "error"); }
//   };

//   // ── ALERT CRUD ───────────────────────────────────────────────────
//   const alertFields = [
//     { key: "title",      label: "Alert Title",  type: "text"     },
//     { key: "description",label: "Description",  type: "textarea" },
//     { key: "alert_type", label: "Alert Type",   type: "select",  options: [
//         {value:"account_takeover",label:"Account Takeover"},
//         {value:"suspicious_login",label:"Suspicious Login"},
//         {value:"payment_fraud",label:"Payment Fraud"},
//         {value:"vpn_detected",label:"VPN Detected"},
//         {value:"brute_force",label:"Brute Force"},
//         {value:"device_fraud",label:"Device Fraud"},
//     ]},
//     { key: "priority",   label: "Priority",     type: "select",  options: [
//         {value:"low",label:"Low"},{value:"medium",label:"Medium"},
//         {value:"high",label:"High"},{value:"critical",label:"Critical"},
//     ]},
//   ];

//   const resolveAlert = async (id) => {
//     try {
//       await API.resolveAlert(id, { resolution_notes: "Resolved by admin" });
//       showToast("Alert resolved!"); fetchAll();
//     } catch { showToast("Failed to resolve", "error"); }
//   };

//   const bulkResolveAlerts = async () => {
//     try {
//       await API.bulkResolve({ alert_ids: alerts.filter(a => !a.is_resolved).map(a => a.id), action: "resolve" });
//       showToast("All alerts resolved!"); fetchAll();
//     } catch { showToast("Bulk resolve failed", "error"); }
//   };

//   // ── ATTEMPT bulk update ───────────────────────────────────────────
//   const bulkUpdateAttempts = async (status) => {
//     if (!selectedAttempts.length) return;
//     try {
//       await API.bulkAttempts({ attempt_ids: selectedAttempts, status });
//       showToast(`${selectedAttempts.length} attempts marked as ${status}!`);
//       setSelectedAttempts([]); fetchAll();
//     } catch { showToast("Bulk update failed", "error"); }
//   };

//   const { settings, chart, patterns, risk, devices, ip_rep, offers, offer_feed } = data;
//   const maxChart = Math.max(...chart.map(c => Math.max(c.blocked, c.success, c.failed)));

//   const navItems = [
//     { label: "Dashboard",             icon: "🏠" },
//     { label: "Global Fraud Settings", icon: "⚙️" },
//     { label: "Active Fraud Rules",    icon: "🛡️", badge: rules.filter(r=>r.is_active).length.toString(), green: true },
//     { label: "Fraud Attempts",        icon: "⚠️", badge: attempts.length.toString() },
//     { label: "Fraud Patterns",        icon: "🔍" },
//     { label: "User Risk Profiles",    icon: "👤", badge: riskProfiles.filter(r=>r.is_flagged).length.toString() },
//     { label: "Device Fingerprints",   icon: "🖥️" },
//     { label: "IP Reputation",         icon: "🌐" },
//     { label: "Live Fraud Alerts",     icon: "🚨", badge: alertCounts.critical.toString() },
//     { label: "Offer Completion",      icon: "🎯" },
//     { label: "Reports",               icon: "📊" },
//     { label: "System Health",         icon: "✅" },
//     { label: "Settings",              icon: "🔧" },
//   ];

//   // ── NAV PANEL CONTENT ─────────────────────────────────────────────
//   const renderNavPanel = () => {
//     switch (activeNav) {

//       case "Active Fraud Rules":
//         return (
//           <div className="fd-panel fd-panel-amber" style={{margin:0,flex:1}}>
//             <div className="fd-panel-hd">
//               <span className="fd-panel-title fd-panel-title-amber">🛡 Active Fraud Rules</span>
//               <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={() => setModal({ type: "rule", data: null })}>+ New Rule</button>
//             </div>
//             <div className="fd-panel-body">
//               {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
//               rules.length === 0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No rules found</div> :
//               rules.map((r, i) => (
//                 <div key={r.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 10px", marginBottom:6, background:"rgba(0,0,0,.2)", borderRadius:8, border:`1px solid rgba(255,183,0,${r.is_active?".2":".08"})` }}>
//                   <span style={{fontSize:14}}>{r.severity==="critical"?"🚨":r.severity==="high"?"⚠️":"🛡️"}</span>
//                   <div style={{flex:1}}>
//                     <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{r.name}</div>
//                     <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{r.rule_type} • {r.run_frequency} • weight: {r.weight}</div>
//                   </div>
//                   <span style={{fontSize:9,padding:"2px 7px",borderRadius:5,background:r.severity==="critical"?"rgba(255,34,68,.2)":r.severity==="high"?"rgba(255,183,0,.2)":"rgba(0,255,136,.2)",color:r.severity==="critical"?"#ff2244":r.severity==="high"?"#ffb700":"#00ff88"}}>
//                     {r.severity}
//                   </span>
//                   <button onClick={() => toggleRule(r)} style={{fontSize:9,padding:"3px 8px",borderRadius:5,border:"none",cursor:"pointer",background:r.is_active?"rgba(0,255,136,.15)":"rgba(255,34,68,.15)",color:r.is_active?"#00ff88":"#ff2244"}}>
//                     {r.is_active ? "ON" : "OFF"}
//                   </button>
//                   <button onClick={() => setModal({ type:"rule", data:r })} style={{fontSize:11,background:"none",border:"none",color:"#00f5ff",cursor:"pointer"}}>✏️</button>
//                   <button onClick={() => setConfirmDel({ id:r.id, msg:`Delete rule "${r.name}"?`, onConfirm:()=>deleteRule(r.id) })} style={{fontSize:11,background:"none",border:"none",color:"#ff2244",cursor:"pointer"}}>🗑️</button>
//                 </div>
//               ))}
//             </div>
//           </div>
//         );

//       case "Fraud Attempts":
//         return (
//           <div className="fd-panel fd-panel-cyan" style={{margin:0,flex:1}}>
//             <div className="fd-panel-hd">
//               <span className="fd-panel-title">⚠ Fraud Attempts</span>
//               <div style={{display:"flex",gap:6}}>
//                 {selectedAttempts.length > 0 && <>
//                   <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>bulkUpdateAttempts("reviewed")}>✓ Mark Reviewed</button>
//                   <button className="fd-btn fd-btn-red fd-btn-sm" onClick={()=>bulkUpdateAttempts("false_positive")}>✓ False Positive</button>
//                 </>}
//                 <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={fetchAll}>↺ Refresh</button>
//               </div>
//             </div>
//             <div className="fd-panel-body">
//               {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
//               attempts.length === 0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No attempts found</div> :
//               attempts.map(a => (
//                 <div key={a.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 10px", marginBottom:6, background:"rgba(0,0,0,.2)", borderRadius:8, borderLeft:`2px solid ${a.status==="blocked"?"#ff2244":a.status==="reviewed"?"#00ff88":"#ffb700"}` }}>
//                   <input type="checkbox" checked={selectedAttempts.includes(a.id)} onChange={e => setSelectedAttempts(p => e.target.checked ? [...p,a.id] : p.filter(x=>x!==a.id))} style={{accentColor:"#00f5ff"}}/>
//                   <span style={{fontSize:13}}>{a.attempt_type==="multi_account"?"👤":a.attempt_type==="vpn_proxy"?"🌐":a.attempt_type==="click_fraud"?"👆":"⚠️"}</span>
//                   <div style={{flex:1}}>
//                     <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{a.attempt_type?.replace(/_/g," ").toUpperCase()}</div>
//                     <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>{a.description?.slice(0,50)} • Score: {a.fraud_score}</div>
//                   </div>
//                   <span style={{fontSize:9,padding:"2px 7px",borderRadius:5,background:a.status==="blocked"?"rgba(255,34,68,.2)":a.status==="reviewed"?"rgba(0,255,136,.2)":"rgba(255,183,0,.2)",color:a.status==="blocked"?"#ff2244":a.status==="reviewed"?"#00ff88":"#ffb700"}}>
//                     {a.status}
//                   </span>
//                   <span style={{color:"rgba(140,200,230,.4)",fontSize:9}}>{new Date(a.created_at).toLocaleDateString()}</span>
//                 </div>
//               ))}
//             </div>
//           </div>
//         );

//       case "Live Fraud Alerts":
//         return (
//           <div className="fd-panel fd-panel-red" style={{margin:0,flex:1}}>
//             <div className="fd-panel-hd">
//               <span className="fd-panel-title fd-panel-title-red"><span className="fd-live-dot"/>Live Fraud Alerts</span>
//               <div style={{display:"flex",gap:6}}>
//                 <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={() => setModal({ type:"alert", data:null })}>+ New Alert</button>
//                 <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={bulkResolveAlerts}>✓ Resolve All</button>
//               </div>
//             </div>
//             <div className="fd-panel-body">
//               <div className="fd-alert-counts">
//                 {[
//                   {label:"Critical",val:alertCounts.critical,cls:"fd-acb-crit",nc:"neon-red"},
//                   {label:"High",    val:alertCounts.high,    cls:"fd-acb-high",nc:"neon-amber"},
//                   {label:"Medium",  val:alertCounts.medium,  cls:"fd-acb-med", nc:"neon-white"},
//                   {label:"Low",     val:alertCounts.low,     cls:"fd-acb-low", nc:"neon-green"},
//                 ].map((b,i) => (
//                   <div key={i} className={`fd-alert-count-box ${b.cls}`}>
//                     <span className={`fd-acb-label ${b.nc}`}>{b.label}</span>
//                     <span className={`fd-num fd-n-lg ${b.nc}`}>{b.val}</span>
//                   </div>
//                 ))}
//               </div>
//               {loading ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>Loading...</div> :
//               alerts.length === 0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No alerts</div> :
//               alerts.map(a => (
//                 <div key={a.id} className={`fd-alert-item fd-alert-${a.priority}`} style={{display:"flex",alignItems:"center",gap:8}}>
//                   <span className="fd-alert-icon">{a.priority==="critical"?"🚨":a.priority==="high"?"⚠️":"ℹ️"}</span>
//                   <div style={{flex:1}}>
//                     <div className={`fd-alert-title ${a.priority==="critical"?"neon-red":a.priority==="high"?"neon-amber":""}`}>{a.title}</div>
//                     <div className="fd-alert-meta"><span>🌐</span><span>{a.data?.location || "Unknown"}</span></div>
//                   </div>
//                   <span style={{fontSize:9,color:"rgba(140,200,230,.4)"}}>{new Date(a.created_at).toLocaleTimeString()}</span>
//                   {!a.is_resolved && <button onClick={()=>resolveAlert(a.id)} style={{fontSize:9,padding:"3px 8px",borderRadius:5,border:"1px solid rgba(0,255,136,.3)",background:"rgba(0,255,136,.1)",color:"#00ff88",cursor:"pointer"}}>Resolve</button>}
//                   {a.is_resolved && <span style={{fontSize:9,color:"#00ff88"}}>✓ Resolved</span>}
//                   <button onClick={()=>setModal({type:"alert",data:a})} style={{fontSize:11,background:"none",border:"none",color:"#00f5ff",cursor:"pointer"}}>✏️</button>
//                   <button onClick={()=>setConfirmDel({id:a.id,msg:`Delete alert "${a.title}"?`,onConfirm:async()=>{await API.deleteAlert(a.id);showToast("Alert deleted!");fetchAll();setConfirmDel(null);}})} style={{fontSize:11,background:"none",border:"none",color:"#ff2244",cursor:"pointer"}}>🗑️</button>
//                 </div>
//               ))}
//             </div>
//           </div>
//         );

//       case "User Risk Profiles":
//         return (
//           <div className="fd-panel fd-panel-mag" style={{margin:0,flex:1}}>
//             <div className="fd-panel-hd">
//               <span className="fd-panel-title fd-panel-title-mag">👤 User Risk Profiles</span>
//               <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={fetchAll}>↺ Refresh</button>
//             </div>
//             <div className="fd-panel-body">
//               {riskProfiles.length === 0 ? <div style={{color:"rgba(140,200,230,.4)",padding:20,textAlign:"center"}}>No profiles found</div> :
//               riskProfiles.map(p => (
//                 <div key={p.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 10px", marginBottom:6, background:"rgba(0,0,0,.2)", borderRadius:8, borderLeft:`2px solid ${p.monitoring_level==="critical"||p.monitoring_level==="high"?"#ff2244":p.monitoring_level==="medium"?"#ffb700":"#00ff88"}` }}>
//                   <span style={{fontSize:14}}>👤</span>
//                   <div style={{flex:1}}>
//                     <div style={{color:"#fff",fontSize:11,fontWeight:700}}>{p.user?.username || `User #${p.user}`}</div>
//                     <div style={{color:"rgba(140,200,230,.4)",fontSize:9,marginTop:2}}>Score: {p.overall_risk_score} • Attempts: {p.total_fraud_attempts}</div>
//                   </div>
//                   <div style={{width:60}}>
//                     <div style={{height:4,background:"rgba(255,255,255,.1)",borderRadius:2,overflow:"hidden"}}>
//                       <div style={{height:"100%",width:`${p.overall_risk_score}%`,background:p.overall_risk_score>70?"#ff2244":p.overall_risk_score>40?"#ffb700":"#00ff88",borderRadius:2}}/>
//                     </div>
//                   </div>
//                   <span style={{fontSize:9,padding:"2px 7px",borderRadius:5,background:p.monitoring_level==="critical"||p.monitoring_level==="high"?"rgba(255,34,68,.2)":p.monitoring_level==="medium"?"rgba(255,183,0,.2)":"rgba(0,255,136,.2)",color:p.monitoring_level==="critical"||p.monitoring_level==="high"?"#ff2244":p.monitoring_level==="medium"?"#ffb700":"#00ff88"}}>
//                     {p.monitoring_level}
//                   </span>
//                   {p.is_flagged && <span style={{fontSize:9,color:"#ff2244"}}>🚩</span>}
//                 </div>
//               ))}
//             </div>
//           </div>
//         );

//       default:
//         return null;
//     }
//   };

//   const isNavPanel = !["Dashboard","Fraud Patterns","Device Fingerprints","IP Reputation","Offer Completion","Reports","System Health","Settings","Global Fraud Settings","Fraud Attempts"].includes(activeNav) && activeNav !== "Dashboard";

//   return (
//     <div className="fd-root">
//       <div className="fd-bg" />

//       {/* Toast */}
//       {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

//       {/* CRUD Modal */}
//       {modal?.type === "rule" && (
//         <CRUDModal
//           title={modal.data ? "✏️ EDIT RULE" : "✦ CREATE RULE"}
//           fields={ruleFields}
//           values={modal.data}
//           onSave={saveRule}
//           onClose={() => setModal(null)}
//           saving={saving}
//         />
//       )}
//       {modal?.type === "alert" && (
//         <CRUDModal
//           title={modal.data ? "✏️ EDIT ALERT" : "✦ CREATE ALERT"}
//           fields={alertFields}
//           values={modal.data}
//           onSave={async (form) => {
//             setSaving(true);
//             try {
//               if (modal.data?.id) { await API.updateAlert(modal.data.id, form); showToast("Alert updated!"); }
//               else { await API.createAlert({ ...form, is_resolved: false }); showToast("Alert created!"); }
//               setModal(null); fetchAll();
//             } catch { showToast("Failed", "error"); } finally { setSaving(false); }
//           }}
//           onClose={() => setModal(null)}
//           saving={saving}
//         />
//       )}

//       {/* Confirm Delete */}
//       {confirmDel && <ConfirmModal msg={confirmDel.msg} onConfirm={confirmDel.onConfirm} onClose={() => setConfirmDel(null)} />}

//       {/* ═══ HEADER ════════════════════════════════════════════════ */}
//       <header className="fd-header">
//         <div className="fd-logo-wrap">
//           <div className="fd-logo-title"><span>FRAUD</span> DETECTION</div>
//           <div className="fd-logo-sub">— CONTROL PANEL —</div>
//         </div>
//         <div className="fd-logo-divider" />
//         <div className="fd-search-wrap">
//           <span className="fd-search-icon">🔍</span>
//           <input placeholder="Search Fraud Data..." />
//         </div>
//         <div className="fd-header-spacer" />
//         <div className="fd-header-icons">
//           {[{i:"🔔",b:alertCounts.critical.toString()},{i:"🛡️",d:true},{i:"🔔",b:"3"},{i:"🔰"},{i:"⚙️"},{i:"✚"}].map((h,idx) => (
//             <div key={idx} className="fd-hicon">
//               {h.i}
//               {h.b && h.b !== "0" && <span className="fd-hicon-badge">{h.b}</span>}
//               {h.d && <span className="fd-hicon-dot" />}
//             </div>
//           ))}
//         </div>
//         <div style={{width:"1px",height:"30px",background:"rgba(0,245,255,0.2)",margin:"0 6px"}}/>
//         <div className="fd-user-wrap">
//           <div className="fd-user-avatar">👤</div>
//           <div>
//             <div className="fd-user-name">Admin</div>
//             <div className="fd-user-role">⭐ Super Administrator</div>
//           </div>
//         </div>
//       </header>

//       {/* ═══ BODY ══════════════════════════════════════════════════ */}
//       <div className="fd-body">

//         {/* ── SIDEBAR ──────────────────────────────────────────── */}
//         <aside className="fd-sidebar">
//           <div style={{padding:"10px 10px 4px"}}>
//             <div className="fd-nav-section-label">Navigation</div>
//           </div>
//           {navItems.map(n => (
//             <div key={n.label}
//               className={`fd-nav-item${activeNav===n.label?" active":""}`}
//               onClick={() => setActiveNav(n.label)}>
//               <div className="fd-nav-left">
//                 <span className="fd-nav-icon">{n.icon}</span>
//                 <span>{n.label}</span>
//               </div>
//               <div style={{display:"flex",alignItems:"center",gap:"3px"}}>
//                 {n.badge && n.badge !== "0" && (
//                   <span className={`fd-nav-badge${n.green?" fd-nav-badge-green":""}`}>{n.badge}</span>
//                 )}
//                 <span className="fd-nav-arrow">›</span>
//               </div>
//             </div>
//           ))}
//           <div className="fd-sidebar-support">
//             <div className="fd-support-icon">🎧</div>
//             <div>
//               <div className="fd-support-text">Live Support</div>
//               <div className="fd-support-status">✦ 24/7 Online</div>
//             </div>
//           </div>
//         </aside>

//         {/* ── MAIN ─────────────────────────────────────────────── */}
//         <main className="fd-main">

//           {/* Nav-specific full panel */}
//           {(activeNav === "Active Fraud Rules" || activeNav === "Fraud Attempts" || activeNav === "Live Fraud Alerts" || activeNav === "User Risk Profiles") ? (
//             <div style={{display:"flex",flexDirection:"column",gap:0,height:"100%"}}>
//               {renderNavPanel()}
//             </div>
//           ) : (
//             <>
//               {/* ROW 1: Settings | Rules | Alerts */}
//               <div className="fd-row">

//                 {/* GLOBAL FRAUD SETTINGS */}
//                 <div className="fd-panel fd-panel-cyan fd-col-35">
//                   <div className="fd-scan-line"/>
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title">⚙ Global Fraud Settings</span>
//                     <span className="fd-live-dot"/>
//                   </div>
//                   <div className="fd-panel-body">
//                     <div style={{display:"flex",gap:"10px"}}>
//                       <div style={{flex:1}}>
//                         <div style={{position:"relative",height:"56px",marginBottom:"8px",borderRadius:"5px",overflow:"hidden"}}>
//                           <div className="fd-world-map"/>
//                           {MAP_DOTS.slice(0,6).map((d,i)=>(
//                             <div key={i} className={`fd-map-dot ${d.c}`} style={{left:d.x,top:d.y,animationDelay:`${d.delay}s`}}/>
//                           ))}
//                         </div>
//                         <div style={{marginBottom:"6px"}}>
//                           <div className="fd-label-sm">Total Rules</div>
//                           <div style={{display:"flex",alignItems:"baseline",gap:"6px"}}>
//                             <span className="fd-num fd-n-xl neon-white">{settings.total_rules.toLocaleString()}</span>
//                           </div>
//                         </div>
//                         <div style={{display:"flex",gap:"16px",marginBottom:"8px"}}>
//                           <div>
//                             <span style={{fontSize:"9px",color:"#00ff88"}}>● Active </span>
//                             <span className="fd-num fd-n-sm neon-green">{settings.active_rules}</span>
//                           </div>
//                           <div>
//                             <span style={{fontSize:"9px",color:"#ff2244"}}>● Disabled </span>
//                             <span className="fd-num fd-n-sm neon-red">{settings.disabled_rules}</span>
//                           </div>
//                         </div>
//                         <div style={{display:"flex",gap:"5px"}}>
//                           <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("Active Fraud Rules")}>Manage Rules</button>
//                           <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={()=>{setActiveNav("Active Fraud Rules");setModal({type:"rule",data:null});}}>+ Add Rule</button>
//                         </div>
//                       </div>
//                       <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
//                         <div className="fd-label-sm" style={{marginBottom:"3px"}}>Security Score</div>
//                         <CircularGauge pct={settings.security_score} size={92} color="#00ff88" label="Secure"/>
//                       </div>
//                     </div>
//                   </div>
//                 </div>

//                 {/* ACTIVE FRAUD RULES PREVIEW */}
//                 <div className="fd-panel fd-panel-amber fd-col-28">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title fd-panel-title-amber">🛡 Active Fraud Rules</span>
//                     <button className="fd-btn fd-btn-amber fd-btn-sm" onClick={()=>setActiveNav("Active Fraud Rules")}>View All</button>
//                   </div>
//                   <div className="fd-panel-body">
//                     {rules.filter(r=>r.is_active).slice(0,4).map((r,i) => (
//                       <div key={r.id} className="fd-rule-row">
//                         <span className="fd-rule-icon">{r.severity==="critical"?"🚨":r.severity==="high"?"⚠️":"🛡️"}</span>
//                         <span className="fd-rule-name">{r.name}</span>
//                         <div className="fd-rule-bar-wrap">
//                           <div className="fd-progress">
//                             <div className="fd-progress-fill" style={{
//                               width:`${r.weight}%`,
//                               background: i===0?"linear-gradient(90deg,#ff2244,#ff6680)":
//                                           i===1?"linear-gradient(90deg,#ffb700,#ffd060)":
//                                           i===2?"linear-gradient(90deg,#0066ff,#00f5ff)":
//                                                 "linear-gradient(90deg,#00aa55,#00ff88)"
//                             }}/>
//                           </div>
//                         </div>
//                         <span className="fd-rule-count neon-white">{r.weight}</span>
//                       </div>
//                     ))}
//                   </div>
//                 </div>

//                 {/* LIVE FRAUD ALERTS PREVIEW */}
//                 <div className="fd-panel fd-panel-red fd-col-fill">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title fd-panel-title-red">
//                       <span className="fd-live-dot"/>Live Fraud Alerts
//                     </span>
//                     <button className="fd-btn fd-btn-red fd-btn-sm" onClick={()=>setActiveNav("Live Fraud Alerts")}>View All</button>
//                   </div>
//                   <div className="fd-panel-body">
//                     <div className="fd-alert-counts">
//                       {[
//                         {label:"Critical",val:alertCounts.critical,cls:"fd-acb-crit",nc:"neon-red"},
//                         {label:"High",    val:alertCounts.high,    cls:"fd-acb-high",nc:"neon-amber"},
//                         {label:"Medium",  val:alertCounts.medium,  cls:"fd-acb-med", nc:"neon-white"},
//                         {label:"Low",     val:alertCounts.low,     cls:"fd-acb-low", nc:"neon-green"},
//                       ].map((b,i)=>(
//                         <div key={i} className={`fd-alert-count-box ${b.cls}`}>
//                           <span className={`fd-acb-label ${b.nc}`}>{b.label}</span>
//                           <span className={`fd-num fd-n-lg ${b.nc}`}>{b.val}</span>
//                         </div>
//                       ))}
//                     </div>
//                     <div className="fd-scroll-list" ref={scrollRef}>
//                       {data.alerts.map(a=>(
//                         <div key={a.id} className={`fd-alert-item fd-alert-${a.type}`}>
//                           <span className="fd-alert-icon">{a.icon}</span>
//                           <div style={{flex:1}}>
//                             <div className={`fd-alert-title ${a.type==="critical"?"neon-red":a.type==="high"?"neon-amber":""}`}>{a.title}</div>
//                             <div className="fd-alert-meta"><span>{a.flag}</span><span>{a.loc}</span></div>
//                           </div>
//                           <span className="fd-alert-time">{a.time}</span>
//                         </div>
//                       ))}
//                     </div>
//                   </div>
//                 </div>
//               </div>

//               {/* ROW 2 */}
//               <div className="fd-row">
//                 <div className="fd-panel fd-panel-cyan fd-col-60">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title">⚠ Fraud Attempts & Patterns</span>
//                     <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("Fraud Attempts")}>View All</button>
//                   </div>
//                   <div className="fd-panel-body">
//                     <div style={{display:"flex",gap:"7px",marginBottom:"10px"}}>
//                       {[
//                         {label:"Total Attempts",val:data.attempts.total,   nc:"neon-white",bg:"rgba(0,30,60,0.5)",   bc:"rgba(0,245,255,0.25)"},
//                         {label:"🛡 Blocked",    val:data.attempts.blocked, nc:"neon-cyan", bg:"rgba(0,20,50,0.5)",   bc:"rgba(0,100,180,0.35)"},
//                         {label:"✅ Success",    val:data.attempts.success, nc:"neon-green",bg:"rgba(0,25,15,0.5)",   bc:"rgba(0,255,136,0.25)"},
//                       ].map((s,i)=>(
//                         <div key={i} className="fd-stat-box" style={{background:s.bg,borderColor:s.bc}}>
//                           <div className="fd-stat-label">{s.label}</div>
//                           <div className={`fd-stat-val ${s.nc}`}>{s.val.toLocaleString()}</div>
//                         </div>
//                       ))}
//                     </div>
//                     <div style={{display:"flex",gap:"12px"}}>
//                       <div style={{flex:1}}>
//                         <div className="fd-label-sm" style={{marginBottom:"4px"}}>Attempts (Last 7 Days)</div>
//                         <div className="fd-chart-legend">
//                           {[["Blocked","#00aaff"],["Success","#00ff88"],["Failed","#ff2244"]].map(([l,c])=>(
//                             <div key={l} className="fd-legend-item">
//                               <div className="fd-legend-dot" style={{background:c,boxShadow:`0 0 4px ${c}`}}/>{l}
//                             </div>
//                           ))}
//                         </div>
//                         <div className="fd-bar-chart">
//                           {chart.map((c,i)=>(
//                             <div key={i} className="fd-bar-group">
//                               <div className="fd-bar fd-bar-blocked" style={{height:`${(c.blocked/maxChart)*100}%`}}/>
//                               <div className="fd-bar fd-bar-success" style={{height:`${(c.success/maxChart)*100}%`}}/>
//                               <div className="fd-bar fd-bar-failed"  style={{height:`${(c.failed /maxChart)*100}%`}}/>
//                             </div>
//                           ))}
//                         </div>
//                         <div className="fd-chart-labels">
//                           {chart.map(c=><span key={c.day}>{c.day}</span>)}
//                         </div>
//                       </div>
//                       <div style={{width:"155px"}}>
//                         <div className="fd-label-sm" style={{marginBottom:"4px"}}>Top Patterns</div>
//                         <DonutChart data={patterns} size={78}/>
//                         {patterns.map((p,i)=>(
//                           <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:"4px"}}>
//                             <div style={{display:"flex",alignItems:"center",gap:"4px"}}>
//                               <div style={{width:"7px",height:"7px",borderRadius:"50%",background:p.color,flexShrink:0}}/>
//                               <span style={{fontSize:"9px"}}>{p.icon} {p.name}</span>
//                             </div>
//                             <span className="fd-num fd-n-xs" style={{color:p.color}}>{p.pct}%</span>
//                           </div>
//                         ))}
//                       </div>
//                     </div>
//                   </div>
//                 </div>

//                 {/* USER RISK PROFILES */}
//                 <div className="fd-panel fd-panel-mag fd-col-fill">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title fd-panel-title-mag">👤 User Risk Profiles</span>
//                     <button className="fd-btn fd-btn-cyan fd-btn-sm" onClick={()=>setActiveNav("User Risk Profiles")}>View All</button>
//                   </div>
//                   <div className="fd-panel-body">
//                     {[
//                       {label:"High Risk",  num:risk.high,   cls:"fd-risk-high",  nc:"neon-red",   icon:"👤", bar:risk.high  },
//                       {label:"Medium Risk",num:risk.medium, cls:"fd-risk-medium", nc:"neon-amber", icon:"👥", bar:risk.medium},
//                       {label:"Low Risk",   num:risk.low,    cls:"fd-risk-low",    nc:"neon-green", icon:"✅", bar:risk.low   },
//                     ].map((r,i)=>(
//                       <div key={i} className={`fd-risk-row ${r.cls}`}>
//                         <span className="fd-risk-icon">{r.icon}</span>
//                         <div style={{flex:1}}>
//                           <div className={`fd-risk-label ${r.nc}`}>{r.label}</div>
//                           <div className={`fd-risk-num ${r.nc}`}>{r.num.toLocaleString()}</div>
//                         </div>
//                       </div>
//                     ))}
//                     <hr className="fd-divider"/>
//                     <div style={{display:"flex",alignItems:"center",gap:"10px"}}>
//                       <DonutChart data={[
//                         {pct:Math.max(risk.high,1),color:"#ff2244"},
//                         {pct:Math.max(risk.medium,1),color:"#ffb700"},
//                         {pct:Math.max(risk.low,1),color:"#00ff88"}
//                       ]} size={70}/>
//                       <div>
//                         {[["High","#ff2244"],[`Medium`,"#ffb700"],["Low","#00ff88"]].map(([l,c])=>(
//                           <div key={l} style={{display:"flex",alignItems:"center",gap:"5px",marginBottom:"5px"}}>
//                             <div style={{width:"7px",height:"7px",borderRadius:"50%",background:c}}/>
//                             <span style={{fontSize:"10px",color:"rgba(140,200,230,0.6)"}}>{l}</span>
//                           </div>
//                         ))}
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               </div>

//               {/* ROW 3 */}
//               <div className="fd-row">
//                 <div className="fd-panel fd-panel-cyan fd-col-55">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title">🖥 Device Fingerprints & IP Reputation</span>
//                   </div>
//                   <div className="fd-panel-body">
//                     <div style={{display:"flex",gap:"6px",marginBottom:"9px"}}>
//                       {[
//                         {label:"Devices Tracked",   val:data.devices.tracked,   bg:"rgba(0,245,255,0.08)",bc:"rgba(0,245,255,0.28)",nc:"neon-cyan"},
//                         {label:"Suspicious Devices", val:data.devices.suspicious,bg:"rgba(255,34,68,0.1)", bc:"rgba(255,34,68,0.3)", nc:"neon-red"},
//                         {label:"Trusted Devices",    val:data.devices.trusted,   bg:"rgba(0,255,136,0.08)",bc:"rgba(0,255,136,0.25)",nc:"neon-green"},
//                       ].map((d,i)=>(
//                         <div key={i} className="fd-stat-box" style={{background:d.bg,borderColor:d.bc}}>
//                           <div className="fd-stat-label">{d.label}</div>
//                           <div className={`fd-stat-val ${d.nc}`}>{d.val.toLocaleString()}</div>
//                         </div>
//                       ))}
//                     </div>
//                     <div style={{display:"flex",gap:"10px"}}>
//                       <div style={{flex:1}}>
//                         <div className="fd-label-sm" style={{marginBottom:"5px"}}>● IP Reputation</div>
//                         <table className="fd-ip-table">
//                           <thead><tr><th>Country</th><th>Risk Score</th><th>Status</th></tr></thead>
//                           <tbody>
//                             {ip_rep.map((r,i)=>(
//                               <tr key={i}>
//                                 <td><span className="fd-flag">{r.flag}</span>{r.country}</td>
//                                 <td><span className={`fd-num fd-n-xs ${r.status==="High"?"neon-red":r.status==="Medium"?"neon-amber":"neon-green"}`}>{r.score}</span></td>
//                                 <td><span className={`fd-badge ${r.status==="High"?"fd-badge-red":r.status==="Medium"?"fd-badge-amber":"fd-badge-green"}`}>{r.status}</span></td>
//                               </tr>
//                             ))}
//                           </tbody>
//                         </table>
//                       </div>
//                       <div style={{flex:1,position:"relative",minHeight:"115px",borderRadius:"5px",overflow:"hidden"}}>
//                         <div className="fd-world-map" style={{position:"absolute",inset:0}}/>
//                         {MAP_DOTS.map((d,i)=>(
//                           <div key={i} className={`fd-map-dot ${d.c}`} style={{left:d.x,top:d.y,animationDelay:`${d.delay}s`}}/>
//                         ))}
//                       </div>
//                     </div>
//                   </div>
//                 </div>

//                 <div className="fd-panel fd-panel-green fd-col-fill">
//                   <div className="fd-panel-hd">
//                     <span className="fd-panel-title fd-panel-title-green">🎯 Offer Completion Monitoring</span>
//                   </div>
//                   <div className="fd-panel-body">
//                     <div style={{display:"flex",gap:"5px",marginBottom:"8px"}}>
//                       {[
//                         {label:"Total Offers",val:offers.total,    nc:"neon-cyan", bg:"rgba(0,245,255,0.07)",bc:"rgba(0,245,255,0.22)"},
//                         {label:"Completed",   val:offers.completed,nc:"neon-green",bg:"rgba(0,255,136,0.07)",bc:"rgba(0,255,136,0.22)"},
//                         {label:"Pending",     val:offers.pending,  nc:"neon-amber",bg:"rgba(255,183,0,0.07)", bc:"rgba(255,183,0,0.22)"},
//                       ].map((o,i)=>(
//                         <div key={i} className="fd-stat-box" style={{background:o.bg,borderColor:o.bc}}>
//                           <div className="fd-stat-label">{o.label}</div>
//                           <div className={`fd-stat-val ${o.nc}`}>{o.val.toLocaleString()}</div>
//                         </div>
//                       ))}
//                     </div>
//                     <div style={{display:"flex",gap:"8px",alignItems:"flex-start"}}>
//                       <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
//                         <div className="fd-label-sm" style={{marginBottom:"2px"}}>Completion Rate</div>
//                         <RateGauge pct={offers.rate}/>
//                       </div>
//                       <div style={{flex:1}}>
//                         <div className="fd-label-sm" style={{marginBottom:"3px"}}>Real-Time Activity</div>
//                         <MiniBarChart data={[18,25,22,30,28,35,20]}/>
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               </div>
//             </>
//           )}
//         </main>
//       </div>
//     </div>
//   );
// }