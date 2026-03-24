// src/pages/Cache.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import client from '../api/client';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── THEMES ───────────────────────────────────────────────────────────────────
const THEMES = [
  {
    name: "REDIS CORE",
    primary: "#ff4400", secondary: "#cc3300",
    bg: "radial-gradient(ellipse at 20% 50%, #1a0800 0%, #0a0400 60%, #000 100%)",
    glass: "rgba(255,68,0,0.05)", glassBorder: "rgba(255,68,0,0.15)",
    glassHover: "rgba(255,68,0,0.10)",
    glow: "0 0 40px rgba(255,68,0,0.12)", glowStrong: "0 0 80px rgba(255,68,0,0.24)",
    text: "#fff0e8", textMuted: "#996644",
    orb1: "#ff440020", orb2: "#cc330012",
  },
  {
    name: "ARCTIC CACHE",
    primary: "#00d4ff", secondary: "#0088cc",
    bg: "radial-gradient(ellipse at 80% 20%, #001020 0%, #000810 60%, #000 100%)",
    glass: "rgba(0,212,255,0.05)", glassBorder: "rgba(0,212,255,0.15)",
    glassHover: "rgba(0,212,255,0.10)",
    glow: "0 0 40px rgba(0,212,255,0.12)", glowStrong: "0 0 80px rgba(0,212,255,0.24)",
    text: "#e0f8ff", textMuted: "#3d8899",
    orb1: "#00d4ff20", orb2: "#0088cc12",
  },
  {
    name: "EMERALD SERVER",
    primary: "#00ff88", secondary: "#00cc6a",
    bg: "radial-gradient(ellipse at 30% 70%, #001a0e 0%, #000a05 60%, #000 100%)",
    glass: "rgba(0,255,136,0.05)", glassBorder: "rgba(0,255,136,0.15)",
    glassHover: "rgba(0,255,136,0.10)",
    glow: "0 0 40px rgba(0,255,136,0.12)", glowStrong: "0 0 80px rgba(0,255,136,0.24)",
    text: "#e0fff0", textMuted: "#3d9960",
    orb1: "#00ff8820", orb2: "#00cc6a12",
  },
  {
    name: "GOLDEN MEMORY",
    primary: "#ffcc00", secondary: "#cc9900",
    bg: "radial-gradient(ellipse at 60% 40%, #1a1400 0%, #0a0800 60%, #000 100%)",
    glass: "rgba(255,204,0,0.05)", glassBorder: "rgba(255,204,0,0.15)",
    glassHover: "rgba(255,204,0,0.10)",
    glow: "0 0 40px rgba(255,204,0,0.12)", glowStrong: "0 0 80px rgba(255,204,0,0.24)",
    text: "#fff8e0", textMuted: "#997733",
    orb1: "#ffcc0020", orb2: "#cc990012",
  },
  {
    name: "VIOLET MATRIX",
    primary: "#bb44ff", secondary: "#8822cc",
    bg: "radial-gradient(ellipse at 70% 30%, #0e0020 0%, #060010 60%, #000 100%)",
    glass: "rgba(187,68,255,0.05)", glassBorder: "rgba(187,68,255,0.15)",
    glassHover: "rgba(187,68,255,0.10)",
    glow: "0 0 40px rgba(187,68,255,0.12)", glowStrong: "0 0 80px rgba(187,68,255,0.24)",
    text: "#f0e0ff", textMuted: "#7744aa",
    orb1: "#bb44ff20", orb2: "#8822cc12",
  },
];

// ─── GLASS ────────────────────────────────────────────────────────────────────
const Glass = ({ children, t, style = {}, hover = false, glow = false }) => {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => hover && setHov(true)}
      onMouseLeave={() => hover && setHov(false)}
      style={{
        background: hov ? t.glassHover : t.glass,
        border: `1px solid ${t.glassBorder}`,
        borderRadius: 16, backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        boxShadow: glow ? `${t.glowStrong}, inset 0 1px 0 ${t.glassBorder}` : `${t.glow}, inset 0 1px 0 ${t.glassBorder}`,
        transition: "all 0.3s ease", ...style,
      }}>{children}</div>
  );
};

// ─── STAT CARD ────────────────────────────────────────────────────────────────
const StatCard = ({ icon, label, value, color, t, loading, sub }) => (
  <Glass t={t} style={{ padding: "20px 22px", position: "relative", overflow: "hidden" }}>
    <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at top right, ${color}12, transparent 65%)`, pointerEvents: "none" }} />
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${color}80, transparent)` }} />
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <span style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", fontFamily: "'Courier New', monospace" }}>{label}</span>
    </div>
    {loading
      ? <div style={{ height: 34, width: 80, borderRadius: 8, background: `${color}15`, animation: "shimmer 1.4s infinite" }} />
      : <div style={{ fontSize: 26, fontWeight: 900, color, fontFamily: "'Courier New', monospace", lineHeight: 1, textShadow: `0 0 20px ${color}70`, marginBottom: 4 }}>{value}</div>
    }
    {sub && <div style={{ color: t.textMuted, fontSize: 10, marginTop: 4, fontFamily: "'Courier New', monospace" }}>{sub}</div>}
  </Glass>
);

// ─── GAUGE ────────────────────────────────────────────────────────────────────
const Gauge = ({ label, value, max, color, t, unit = "" }) => {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const danger = pct > 80;
  const warn = pct > 60;
  const gaugeColor = danger ? "#ff2244" : warn ? "#ffcc00" : color;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ color: t.textMuted, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", fontFamily: "'Courier New', monospace" }}>{label}</span>
        <span style={{ color: gaugeColor, fontSize: 12, fontWeight: 800, fontFamily: "'Courier New', monospace" }}>{value}{unit} <span style={{ color: t.textMuted, fontSize: 9 }}>/ {max}{unit}</span></span>
      </div>
      <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden", border: `1px solid ${t.glassBorder}` }}>
        <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${gaugeColor}, ${gaugeColor}88)`, borderRadius: 3, boxShadow: `0 0 8px ${gaugeColor}60`, transition: "width 1s ease" }} />
      </div>
      <div style={{ color: t.textMuted, fontSize: 9, marginTop: 4, fontFamily: "'Courier New', monospace" }}>{pct.toFixed(1)}% used</div>
    </div>
  );
};

// ─── METRIC ROW ───────────────────────────────────────────────────────────────
const MetricRow = ({ label, value, color, t, icon }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "11px 0", borderBottom: `1px solid ${t.glassBorder}` }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {icon && <span style={{ fontSize: 14 }}>{icon}</span>}
      <span style={{ color: t.textMuted, fontSize: 11, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em" }}>{label}</span>
    </div>
    <span style={{ color: color || t.primary, fontSize: 13, fontWeight: 700, fontFamily: "'Courier New', monospace", textShadow: `0 0 10px ${color || t.primary}50` }}>{value}</span>
  </div>
);

// ─── HIT RATIO RING ───────────────────────────────────────────────────────────
const HitRatioRing = ({ hits, misses, t }) => {
  const total = hits + misses;
  const ratio = total > 0 ? ((hits / total) * 100).toFixed(1) : 0;
  const color = ratio >= 80 ? "#00ff88" : ratio >= 50 ? "#ffcc00" : "#ff2244";
  const circumference = 2 * Math.PI * 40;
  const strokeDash = (ratio / 100) * circumference;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <div style={{ position: "relative", width: 110, height: 110 }}>
        <svg width="110" height="110" style={{ transform: "rotate(-90deg)" }}>
          <circle cx="55" cy="55" r="40" fill="none" stroke={t.glassBorder} strokeWidth="8" />
          <circle cx="55" cy="55" r="40" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={`${strokeDash} ${circumference}`}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "stroke-dasharray 1s ease" }}
          />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div style={{ color, fontSize: 20, fontWeight: 900, fontFamily: "'Courier New', monospace", textShadow: `0 0 12px ${color}80` }}>{ratio}%</div>
          <div style={{ color: t.textMuted, fontSize: 8, fontFamily: "'Courier New', monospace", letterSpacing: "0.08em" }}>HIT RATE</div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, fontSize: 11 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#00ff88", fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{hits.toLocaleString()}</div>
          <div style={{ color: t.textMuted, fontSize: 9, letterSpacing: "0.08em" }}>HITS</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#ff2244", fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{misses.toLocaleString()}</div>
          <div style={{ color: t.textMuted, fontSize: 9, letterSpacing: "0.08em" }}>MISSES</div>
        </div>
      </div>
    </div>
  );
};

// ─── UPTIME DISPLAY ───────────────────────────────────────────────────────────
const formatUptime = (seconds) => {
  if (!seconds) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
};

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────

// ─── CACHE KEY MANAGER (CRUD Panel) ──────────────────────────────────────────
function CacheKeyManager({ t }) {
  const [tab,      setTab]     = React.useState('list');
  const [pattern,  setPattern] = React.useState('*');
  const [keys,     setKeys]    = React.useState([]);
  const [keyCount, setKeyCount]= React.useState(0);
  const [kLoading, setKLoad]   = React.useState(false);
  const [kError,   setKError]  = React.useState('');

  // CREATE form
  const [newKey,     setNewKey]     = React.useState('');
  const [newValue,   setNewValue]   = React.useState('');
  const [newTimeout, setNewTimeout] = React.useState(300);
  const [creating,   setCreating]   = React.useState(false);
  const [createMsg,  setCreateMsg]  = React.useState('');

  // DELETE form
  const [delKey,     setDelKey]    = React.useState('');
  const [delPattern, setDelPattern]= React.useState('');
  const [deleting,   setDeleting]  = React.useState(false);
  const [delMsg,     setDelMsg]    = React.useState('');

  const fetchKeys = async () => {
    setKLoad(true); setKError('');
    try {
      const r = await client.get('/cache/keys/', { params: { pattern, limit: 50 } });
      setKeys(r.data?.keys || []);
      setKeyCount(r.data?.count || 0);
    } catch(e) {
      setKError(e?.response?.data?.error || e?.response?.status === 403 ? 'Admin access required' : 'Failed to load keys');
    } finally { setKLoad(false); }
  };

  React.useEffect(() => { if (tab === 'list') fetchKeys(); }, [tab]);

  const handleCreate = async () => {
    if (!newKey.trim()) { setCreateMsg('Key is required'); return; }
    setCreating(true); setCreateMsg('');
    try {
      await client.post('/cache/set/', { key: newKey, value: newValue, timeout: +newTimeout });
      setCreateMsg('✓ Key set successfully!');
      setNewKey(''); setNewValue(''); setNewTimeout(300);
      setTimeout(() => setCreateMsg(''), 2500);
      if (tab === 'list') fetchKeys();
    } catch(e) {
      setCreateMsg('✗ ' + (e?.response?.data?.error || 'Failed'));
    } finally { setCreating(false); }
  };

  const handleDeleteKey = async () => {
    if (!delKey.trim()) return;
    setDeleting(true); setDelMsg('');
    try {
      const r = await client.delete('/cache/key/', { data: { key: delKey } });
      setDelMsg();
      setDelKey('');
      setTimeout(() => setDelMsg(''), 2500);
      if (tab === 'list') fetchKeys();
    } catch(e) {
      setDelMsg('✗ ' + (e?.response?.data?.error || 'Failed'));
    } finally { setDeleting(false); }
  };

  const handleDeletePattern = async () => {
    if (!delPattern.trim()) return;
    setDeleting(true); setDelMsg('');
    try {
      const r = await client.delete('/cache/key/', { data: { pattern: delPattern } });
      setDelMsg();
      setDelPattern('');
      setTimeout(() => setDelMsg(''), 2500);
      if (tab === 'list') fetchKeys();
    } catch(e) {
      setDelMsg('✗ ' + (e?.response?.data?.error || 'Failed'));
    } finally { setDeleting(false); }
  };

  const INP = {
    background: 'rgba(255,255,255,0.04)', border: '1px solid ' + t.glassBorder,
    borderRadius: 8, padding: '9px 13px', color: t.text, fontSize: 12,
    outline: 'none', fontFamily: "'Courier New',monospace", width: '100%', boxSizing: 'border-box',
  };
  const BTN = (color) => ({
    background: color + '18', border: '1px solid ' + color + '44', borderRadius: 8,
    padding: '9px 18px', color, fontSize: 11, fontWeight: 700, cursor: 'pointer',
    fontFamily: "'Courier New',monospace", letterSpacing: '.06em',
  });

  const TABS = [
    { k:'list',   l:'LIST KEYS',   icon:'🔑' },
    { k:'create', l:'SET KEY',     icon:'➕' },
    { k:'delete', l:'DELETE KEY',  icon:'🗑️' },
  ];

  return (
    <div style={{ background: t.glass, border: '1px solid ' + t.glassBorder, borderRadius: 16, padding: '22px 24px', marginBottom: 18, backdropFilter:'blur(24px)' }}>
      <div style={{ color: t.text, fontSize: 13, fontWeight: 700, fontFamily:"'Courier New',monospace", letterSpacing:'.05em', marginBottom: 16 }}>
        🗂️ CACHE KEYS — CRUD MANAGER
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:18, background:'rgba(0,0,0,0.3)', borderRadius:10, padding:4 }}>
        {TABS.map(tb => (
          <button key={tb.k} onClick={()=>setTab(tb.k)} style={{
            flex:1, padding:'8px 0', borderRadius:8, border:'1px solid ' + (tab===tb.k ? t.primary : 'transparent'),
            background: tab===tb.k ? t.primary+'20' : 'transparent',
            color: tab===tb.k ? t.primary : t.textMuted,
            fontSize:10, fontWeight:700, cursor:'pointer', fontFamily:"'Courier New',monospace", letterSpacing:'.06em',
          }}>{tb.icon} {tb.l}</button>
        ))}
      </div>

      {/* LIST tab */}
      {tab==='list' && (
        <div>
          <div style={{ display:'flex', gap:10, marginBottom:14 }}>
            <input value={pattern} onChange={e=>setPattern(e.target.value)}
              placeholder="Pattern (e.g. user:* or *)" style={{...INP, flex:1}}
              onKeyDown={e=>e.key==='Enter'&&fetchKeys()} />
            <button onClick={fetchKeys} disabled={kLoading} style={BTN(t.primary)}>
              {kLoading ? '…' : '🔍 SEARCH'}
            </button>
          </div>
          {kError && <div style={{ color:'#ff2244', fontSize:11, marginBottom:10, fontFamily:"'Courier New',monospace" }}>⚠ {kError}</div>}
          <div style={{ fontSize:10, color:t.textMuted, fontFamily:"'Courier New',monospace", marginBottom:8 }}>
            {keyCount} KEY{keyCount!==1?'S':''} FOUND
          </div>
          <div style={{ maxHeight:260, overflowY:'auto' }}>
            {kLoading ? (
              <div style={{ color:t.textMuted, fontSize:11, textAlign:'center', padding:30 }}>Loading…</div>
            ) : keys.length === 0 ? (
              <div style={{ color:t.textMuted, fontSize:11, textAlign:'center', padding:30 }}>No keys found</div>
            ) : keys.map((k,i) => (
              <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                padding:'8px 12px', borderRadius:8, marginBottom:4,
                background:'rgba(255,255,255,0.03)', border:'1px solid ' + t.glassBorder,
              }}>
                <div>
                  <div style={{ color:t.text, fontSize:11, fontFamily:"'Courier New',monospace" }}>{k.key}</div>
                  <div style={{ color:t.textMuted, fontSize:9, marginTop:2 }}>
                    TTL: {k.ttl != null ? k.ttl + 's' : 'no expiry'}
                  </div>
                </div>
                <button onClick={async()=>{ await client.delete('/cache/key/',{data:{key:k.key}}); fetchKeys(); }}
                  style={{ background:'#ff224410', border:'1px solid #ff224430', borderRadius:6,
                    padding:'5px 10px', color:'#ff2244', fontSize:10, cursor:'pointer' }}>
                  DEL
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CREATE tab */}
      {tab==='create' && (
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          <div>
            <div style={{ color:t.textMuted, fontSize:9, fontFamily:"'Courier New',monospace", marginBottom:5, letterSpacing:'.1em' }}>CACHE KEY *</div>
            <input value={newKey} onChange={e=>setNewKey(e.target.value)} placeholder="e.g. user:123:profile" style={INP} />
          </div>
          <div>
            <div style={{ color:t.textMuted, fontSize:9, fontFamily:"'Courier New',monospace", marginBottom:5, letterSpacing:'.1em' }}>VALUE *</div>
            <input value={newValue} onChange={e=>setNewValue(e.target.value)} placeholder="any string value" style={INP} />
          </div>
          <div>
            <div style={{ color:t.textMuted, fontSize:9, fontFamily:"'Courier New',monospace", marginBottom:5, letterSpacing:'.1em' }}>TIMEOUT (seconds)</div>
            <input type="number" value={newTimeout} onChange={e=>setNewTimeout(e.target.value)} style={{...INP, width:140}} />
          </div>
          {createMsg && (
            <div style={{ color:createMsg.startsWith('✓')?'#00ff88':'#ff2244', fontSize:11, fontFamily:"'Courier New',monospace" }}>{createMsg}</div>
          )}
          <button onClick={handleCreate} disabled={creating} style={{...BTN('#00ff88'), width:'fit-content'}}>
            {creating ? '…' : '➕ SET KEY'}
          </button>
        </div>
      )}

      {/* DELETE tab */}
      {tab==='delete' && (
        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
          {/* Delete by exact key */}
          <div style={{ background:'rgba(255,34,68,0.04)', border:'1px solid #ff224420', borderRadius:10, padding:'14px 16px' }}>
            <div style={{ color:'#ff2244', fontSize:10, fontWeight:700, fontFamily:"'Courier New',monospace", marginBottom:10, letterSpacing:'.08em' }}>
              DELETE EXACT KEY
            </div>
            <div style={{ display:'flex', gap:10 }}>
              <input value={delKey} onChange={e=>setDelKey(e.target.value)}
                placeholder="e.g. user:123:profile" style={{...INP, flex:1}} />
              <button onClick={handleDeleteKey} disabled={deleting||!delKey.trim()} style={BTN('#ff2244')}>
                {deleting ? '…' : '🗑️ DELETE'}
              </button>
            </div>
          </div>
          {/* Delete by pattern */}
          <div style={{ background:'rgba(255,204,0,0.04)', border:'1px solid #ffcc0020', borderRadius:10, padding:'14px 16px' }}>
            <div style={{ color:'#ffcc00', fontSize:10, fontWeight:700, fontFamily:"'Courier New',monospace", marginBottom:10, letterSpacing:'.08em' }}>
              DELETE BY PATTERN
            </div>
            <div style={{ display:'flex', gap:10 }}>
              <input value={delPattern} onChange={e=>setDelPattern(e.target.value)}
                placeholder="e.g. user:* or stats:*" style={{...INP, flex:1}} />
              <button onClick={handleDeletePattern} disabled={deleting||!delPattern.trim()} style={BTN('#ffcc00')}>
                {deleting ? '…' : '🧹 DELETE ALL'}
              </button>
            </div>
          </div>
          {delMsg && (
            <div style={{ color:delMsg.startsWith('✓')?'#00ff88':'#ff2244', fontSize:11, fontFamily:"'Courier New',monospace" }}>{delMsg}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CachePage() {
  const [themeIdx, setThemeIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const progressRef = useRef(null);
  const t = THEMES[themeIdx];

  const [stats, setStats]       = useState(null);
  const [sysStats, setSysStats] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [clock, setClock]       = useState("");
  const [clearing, setClearing] = useState(false);
  const [clearMsg, setClearMsg] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRef = useRef(null);

  // 60s theme rotation
  useEffect(() => {
    let ticks = 0;
    progressRef.current = setInterval(() => {
      ticks++;
      setProgress((ticks / 600) * 100);
      if (ticks >= 600) { ticks = 0; setProgress(0); setThemeIdx(i => (i + 1) % THEMES.length); }
    }, 100);
    return () => clearInterval(progressRef.current);
  }, []);

  // Clock
  useEffect(() => {
    const tick = () => setClock(new Date().toUTCString().slice(17, 25) + " UTC");
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id);
  }, []);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const [cacheRes, sysRes] = await Promise.allSettled([
        client.get('/cache/'),
        client.get('/cache/stats/'),
      ]);
      if (cacheRes.status === "fulfilled") setStats(cacheRes.value.data);
      if (sysRes.status === "fulfilled") setSysStats(sysRes.value.data);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  // Auto-refresh every 10s
  useEffect(() => {
    if (autoRefresh) {
      autoRef.current = setInterval(fetchStats, 10000);
    } else {
      clearInterval(autoRef.current);
    }
    return () => clearInterval(autoRef.current);
  }, [autoRefresh, fetchStats]);

  const handleClearCache = async (type = "all") => {
    setClearing(true); setClearMsg("");
    try {
      await client.post(`/cache/clear/`, { type });
      setClearMsg(`✓ ${type.toUpperCase()} cache cleared!`);
      setTimeout(() => setClearMsg(""), 3000);
      fetchStats();
    } catch (e) {
      setClearMsg(`Cache clear: ${e?.response?.status === 404 ? "Endpoint not available" : "Done"}`);
      setTimeout(() => setClearMsg(""), 3000);
    } finally { setClearing(false); }
  };

  const isActive = stats?.status === "active";
  const hits = stats?.keyspace_hits || 0;
  const misses = stats?.keyspace_misses || 0;
  const memUsed = parseFloat(stats?.used_memory?.replace("K", "") || 0);

  return (
    <div style={{ minHeight: "100vh", background: t.bg, color: t.text, fontFamily: "'Segoe UI', -apple-system, sans-serif", transition: "background 1.2s ease" }}>
      <style>{`
        @keyframes fadeIn  { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes shimmer { 0%,100%{opacity:.25} 50%{opacity:.7} }
        @keyframes float   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-20px)} }
        @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:.35} }
        @keyframes blink   { 0%,100%{opacity:1} 50%{opacity:0} }
        * { box-sizing:border-box; }
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-thumb{background:${t.glassBorder};border-radius:2px}
      `}</style>

      {/* Ambient orbs */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0, overflow: "hidden" }}>
        <div style={{ position: "absolute", top: "5%", left: "2%", width: 500, height: 500, borderRadius: "50%", background: t.orb1, filter: "blur(90px)", animation: "float 9s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: "8%", right: "4%", width: 380, height: 380, borderRadius: "50%", background: t.orb2, filter: "blur(70px)", animation: "float 11s ease-in-out infinite reverse" }} />
        <div style={{ position: "absolute", inset: 0, backgroundImage: `linear-gradient(${t.glassBorder} 1px,transparent 1px),linear-gradient(90deg,${t.glassBorder} 1px,transparent 1px)`, backgroundSize: "55px 55px", opacity: .2 }} />
      </div>

      {/* TOP BAR */}
      <div style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(32px)", borderBottom: `1px solid ${t.glassBorder}`, padding: "10px 26px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: isActive ? "#00ff88" : "#ff2244", animation: "pulse 1.5s infinite", boxShadow: `0 0 12px ${isActive ? "#00ff88" : "#ff2244"}` }} />
          <span style={{ color: t.primary, fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", fontFamily: "'Courier New', monospace" }}>{t.name}</span>
          <div style={{ width: 1, height: 14, background: t.glassBorder }} />
          <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>CACHE CONTROL PANEL</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Theme progress */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: t.textMuted, fontSize: 9, fontFamily: "'Courier New', monospace" }}>THEME</span>
            <div style={{ width: 80, height: 2, background: t.glassBorder, borderRadius: 1 }}>
              <div style={{ height: "100%", width: `${progress}%`, background: `linear-gradient(90deg,${t.primary},${t.secondary})`, borderRadius: 1, transition: "width 0.1s linear" }} />
            </div>
          </div>
          {/* Auto refresh toggle */}
          <button onClick={() => setAutoRefresh(v => !v)} style={{
            background: autoRefresh ? `${t.primary}20` : t.glass,
            border: `1px solid ${autoRefresh ? t.primary : t.glassBorder}`,
            borderRadius: 8, padding: "5px 12px", color: autoRefresh ? t.primary : t.textMuted,
            fontSize: 9, cursor: "pointer", fontFamily: "'Courier New', monospace", fontWeight: 700, letterSpacing: "0.08em",
            display: "flex", alignItems: "center", gap: 5,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: autoRefresh ? t.primary : t.textMuted, display: "inline-block", ...(autoRefresh ? { animation: "blink 1s infinite" } : {}) }} />
            AUTO
          </button>
          <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>{clock}</span>
          <button onClick={fetchStats} disabled={loading} style={{ background: t.glass, border: `1px solid ${t.glassBorder}`, borderRadius: 8, padding: "6px 14px", color: t.primary, fontSize: 10, cursor: "pointer", fontFamily: "'Courier New', monospace", fontWeight: 700 }}>
            {loading ? "…" : "↻ SYNC"}
          </button>
        </div>
      </div>

      <div style={{ position: "relative", zIndex: 1, padding: "28px 28px 48px", maxWidth: 1300, margin: "0 auto" }}>

        {/* HEADER */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, animation: "fadeIn .5s ease both" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 54, height: 54, borderRadius: 14, background: t.glass, border: `1px solid ${t.glassBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, boxShadow: t.glowStrong }}>⚡</div>
            <div>
              <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900, letterSpacing: "0.07em", fontFamily: "'Courier New', monospace", background: `linear-gradient(135deg, ${t.text} 30%, ${t.primary})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                CACHE CONTROL CENTER
              </h1>
              <p style={{ margin: "4px 0 0", color: t.textMuted, fontSize: 11, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace" }}>
                REDIS MONITORING · MEMORY MANAGEMENT · PERFORMANCE CONTROL
              </p>
            </div>
          </div>
          {/* Status badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 18px", borderRadius: 12, background: isActive ? "#00ff8810" : "#ff224410", border: `1px solid ${isActive ? "#00ff8833" : "#ff224433"}` }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: isActive ? "#00ff88" : "#ff2244", boxShadow: `0 0 10px ${isActive ? "#00ff88" : "#ff2244"}`, animation: "pulse 2s infinite" }} />
            <span style={{ color: isActive ? "#00ff88" : "#ff2244", fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.08em" }}>
              {loading ? "CHECKING…" : isActive ? "REDIS ACTIVE" : "REDIS INACTIVE"}
            </span>
          </div>
        </div>

        {/* STATS ROW */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 22 }}>
          <StatCard icon="🖥️" label="Backend"      value={stats?.backend || "—"}         color={t.primary} t={t} loading={loading} />
          <StatCard icon="📦" label="Memory Used"  value={stats?.used_memory || "—"}      color="#00d4ff"   t={t} loading={loading} sub="Redis memory" />
          <StatCard icon="⏱️" label="Uptime"       value={formatUptime(stats?.uptime_seconds)} color="#00ff88" t={t} loading={loading} />
          <StatCard icon="🔑" label="Redis Version" value={stats?.redis_version || "—"}   color="#ffcc00"   t={t} loading={loading} />
        </div>

        {/* MAIN CONTENT */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18, marginBottom: 18 }}>

          {/* Hit Ratio */}
          <Glass t={t} glow style={{ padding: "24px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <div style={{ color: t.text, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em", marginBottom: 8 }}>📊 CACHE HIT RATIO</div>
            <HitRatioRing hits={hits} misses={misses} t={t} />
            <div style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", textAlign: "center", marginTop: 4 }}>
              {hits + misses > 0 ? `${(hits + misses).toLocaleString()} total requests` : "No requests yet"}
            </div>
          </Glass>

          {/* Redis Metrics */}
          <Glass t={t} style={{ padding: "20px 22px" }}>
            <div style={{ color: t.text, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em", marginBottom: 14 }}>🔴 REDIS METRICS</div>
            <MetricRow label="Status"         value={stats?.status?.toUpperCase() || "—"}  color={isActive ? "#00ff88" : "#ff2244"} t={t} icon="●" />
            <MetricRow label="Keyspace Hits"  value={hits.toLocaleString()}   color="#00ff88" t={t} icon="✓" />
            <MetricRow label="Keyspace Misses" value={misses.toLocaleString()} color="#ff2244" t={t} icon="✕" />
            <MetricRow label="Memory"         value={stats?.used_memory || "—"} color="#00d4ff" t={t} icon="💾" />
            <MetricRow label="Uptime"         value={formatUptime(stats?.uptime_seconds)} color="#ffcc00" t={t} icon="⏱" />
          </Glass>

          {/* System Stats */}
          <Glass t={t} style={{ padding: "20px 22px" }}>
            <div style={{ color: t.text, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em", marginBottom: 14 }}>🖥️ SYSTEM STATS</div>
            {sysStats ? (
              <>
                <MetricRow label="Total Users" value={sysStats?.total_users || "—"} color={t.primary} t={t} icon="👥" />
                {sysStats?.leaderboard && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 8 }}>TOP EARNERS</div>
                    {sysStats.leaderboard.slice(0, 3).map((u, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${t.glassBorder}` }}>
                        <span style={{ color: t.textMuted, fontSize: 11 }}>{["🥇","🥈","🥉"][i]} {u.username}</span>
                        <span style={{ color: t.primary, fontSize: 11, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>৳{u.total_earned}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: t.textMuted, fontSize: 11, textAlign: "center", padding: 20 }}>
                {loading ? "LOADING…" : "Stats unavailable"}
              </div>
            )}
          </Glass>
        </div>

        {/* CACHE CONTROLS */}
        <Glass t={t} style={{ padding: "22px 24px", marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <div style={{ color: t.text, fontSize: 13, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em" }}>🛠️ CACHE CONTROLS</div>
            {clearMsg && (
              <div style={{ color: clearMsg.startsWith("✓") ? "#00ff88" : "#ffcc00", fontSize: 11, fontFamily: "'Courier New', monospace", background: clearMsg.startsWith("✓") ? "#00ff8815" : "#ffcc0015", padding: "5px 12px", borderRadius: 8, border: `1px solid ${clearMsg.startsWith("✓") ? "#00ff8833" : "#ffcc0033"}` }}>
                {clearMsg}
              </div>
            )}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
            {[
              { label: "FLUSH ALL", desc: "Clear entire cache", color: "#ff2244", icon: "🗑️", type: "all" },
              { label: "USER CACHE", desc: "Clear user profiles", color: "#ffcc00", icon: "👤", type: "users" },
              { label: "STATS CACHE", desc: "Clear system stats", color: "#00d4ff", icon: "📊", type: "stats" },
              { label: "TASK CACHE", desc: "Clear task data", color: "#00ff88", icon: "✅", type: "tasks" },
            ].map(btn => (
              <button key={btn.type} onClick={() => handleClearCache(btn.type)} disabled={clearing}
                style={{
                  padding: "16px 12px", borderRadius: 12,
                  background: `${btn.color}10`, border: `1px solid ${btn.color}30`,
                  cursor: clearing ? "not-allowed" : "pointer",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
                  transition: "all .25s", opacity: clearing ? 0.6 : 1,
                }}
                onMouseEnter={e => { if (!clearing) { e.currentTarget.style.background = `${btn.color}20`; e.currentTarget.style.borderColor = `${btn.color}55`; e.currentTarget.style.boxShadow = `0 0 20px ${btn.color}20`; }}}
                onMouseLeave={e => { e.currentTarget.style.background = `${btn.color}10`; e.currentTarget.style.borderColor = `${btn.color}30`; e.currentTarget.style.boxShadow = "none"; }}
              >
                <span style={{ fontSize: 22 }}>{btn.icon}</span>
                <span style={{ color: btn.color, fontSize: 10, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.08em" }}>{btn.label}</span>
                <span style={{ color: t.textMuted, fontSize: 9 }}>{btn.desc}</span>
              </button>
            ))}
          </div>
        </Glass>


        {/* ═══════════════ CRUD: CACHE KEYS MANAGER ═══════════════════════════ */}
        <CacheKeyManager t={t} />

        {/* PERFORMANCE VISUALIZATION */}
        <Glass t={t} style={{ padding: "22px 24px" }}>
          <div style={{ color: t.text, fontSize: 13, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em", marginBottom: 20 }}>📈 PERFORMANCE OVERVIEW</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Gauge label="HIT RATE" value={hits} max={hits + misses || 1} color="#00ff88" t={t} />
            <Gauge label="MISS RATE" value={misses} max={hits + misses || 1} color="#ff2244" t={t} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, paddingTop: 8, borderTop: `1px solid ${t.glassBorder}` }}>
              <div>
                <div style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 10 }}>CACHE EFFICIENCY</div>
                {[
                  { label: "Hit Ratio", value: hits + misses > 0 ? `${((hits / (hits + misses)) * 100).toFixed(1)}%` : "N/A", color: "#00ff88" },
                  { label: "Total Requests", value: (hits + misses).toLocaleString(), color: t.primary },
                  { label: "Successful Hits", value: hits.toLocaleString(), color: "#00ff88" },
                  { label: "Cache Misses", value: misses.toLocaleString(), color: "#ff2244" },
                ].map(m => (
                  <div key={m.label} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: `1px solid ${t.glassBorder}` }}>
                    <span style={{ color: t.textMuted, fontSize: 11 }}>{m.label}</span>
                    <span style={{ color: m.color, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{m.value}</span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 10 }}>REDIS INFO</div>
                {[
                  { label: "Backend", value: stats?.backend || "—", color: t.primary },
                  { label: "Version", value: stats?.redis_version || "—", color: "#00d4ff" },
                  { label: "Memory", value: stats?.used_memory || "—", color: "#ffcc00" },
                  { label: "Uptime", value: formatUptime(stats?.uptime_seconds), color: "#00ff88" },
                ].map(m => (
                  <div key={m.label} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: `1px solid ${t.glassBorder}` }}>
                    <span style={{ color: t.textMuted, fontSize: 11 }}>{m.label}</span>
                    <span style={{ color: m.color, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{m.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Glass>

        {/* Theme dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 36 }}>
          {THEMES.map((th, i) => (
            <button key={i} onClick={() => { setThemeIdx(i); setProgress(0); }} title={th.name} style={{
              width: i === themeIdx ? 36 : 10, height: 10, borderRadius: 5, border: "none", cursor: "pointer",
              background: i === themeIdx ? `linear-gradient(90deg,${th.primary},${th.secondary})` : `${th.primary}44`,
              boxShadow: i === themeIdx ? `0 0 14px ${th.primary}70` : "none",
              transition: "all .4s ease",
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}