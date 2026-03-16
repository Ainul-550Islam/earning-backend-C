// src/pages/Support.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import client from '../api/client';

// ─── THEMES ───────────────────────────────────────────────────────────────────
const THEMES = [
  {
    name: "ARCTIC NEXUS",
    primary: "#00d4ff", secondary: "#0088cc", accent: "#44eeff",
    bg: "radial-gradient(ellipse at 15% 40%, #00101a 0%, #000810 55%, #000000 100%)",
    glass: "rgba(0,212,255,0.05)", glassBorder: "rgba(0,212,255,0.15)",
    glassHover: "rgba(0,212,255,0.10)", glassActive: "rgba(0,212,255,0.18)",
    glow: "0 0 40px rgba(0,212,255,0.12)", glowStrong: "0 0 80px rgba(0,212,255,0.24)",
    text: "#e0f8ff", textMuted: "#3d8899", textDim: "#1a4455",
    orb1: "#00d4ff18", orb2: "#0088cc10",
    statusOnline: "#00ff88", statusOffline: "#ff2244",
  },
  {
    name: "EMERALD VAULT",
    primary: "#00ff88", secondary: "#00cc6a", accent: "#44ffaa",
    bg: "radial-gradient(ellipse at 80% 60%, #001a0e 0%, #000a05 55%, #000000 100%)",
    glass: "rgba(0,255,136,0.05)", glassBorder: "rgba(0,255,136,0.15)",
    glassHover: "rgba(0,255,136,0.10)", glassActive: "rgba(0,255,136,0.18)",
    glow: "0 0 40px rgba(0,255,136,0.12)", glowStrong: "0 0 80px rgba(0,255,136,0.24)",
    text: "#e0fff0", textMuted: "#3d9960", textDim: "#1a4430",
    orb1: "#00ff8818", orb2: "#00cc6a10",
    statusOnline: "#00ff88", statusOffline: "#ff2244",
  },
  {
    name: "CRIMSON OPS",
    primary: "#ff2244", secondary: "#cc0033", accent: "#ff5566",
    bg: "radial-gradient(ellipse at 50% 20%, #1a0005 0%, #0a0002 55%, #000000 100%)",
    glass: "rgba(255,34,68,0.05)", glassBorder: "rgba(255,34,68,0.15)",
    glassHover: "rgba(255,34,68,0.10)", glassActive: "rgba(255,34,68,0.18)",
    glow: "0 0 40px rgba(255,34,68,0.12)", glowStrong: "0 0 80px rgba(255,34,68,0.24)",
    text: "#ffe0e5", textMuted: "#994455", textDim: "#552233",
    orb1: "#ff224418", orb2: "#cc003310",
    statusOnline: "#00ff88", statusOffline: "#ff2244",
  },
  {
    name: "GOLDEN CIRCUIT",
    primary: "#ffcc00", secondary: "#cc9900", accent: "#ffdd44",
    bg: "radial-gradient(ellipse at 30% 80%, #1a1400 0%, #0a0800 55%, #000000 100%)",
    glass: "rgba(255,204,0,0.05)", glassBorder: "rgba(255,204,0,0.15)",
    glassHover: "rgba(255,204,0,0.10)", glassActive: "rgba(255,204,0,0.18)",
    glow: "0 0 40px rgba(255,204,0,0.12)", glowStrong: "0 0 80px rgba(255,204,0,0.24)",
    text: "#fff8e0", textMuted: "#997733", textDim: "#554400",
    orb1: "#ffcc0018", orb2: "#cc990010",
    statusOnline: "#00ff88", statusOffline: "#ff2244",
  },
  {
    name: "VIOLET GRID",
    primary: "#bb44ff", secondary: "#8822cc", accent: "#cc66ff",
    bg: "radial-gradient(ellipse at 70% 30%, #0e0020 0%, #060010 55%, #000000 100%)",
    glass: "rgba(187,68,255,0.05)", glassBorder: "rgba(187,68,255,0.15)",
    glassHover: "rgba(187,68,255,0.10)", glassActive: "rgba(187,68,255,0.18)",
    glow: "0 0 40px rgba(187,68,255,0.12)", glowStrong: "0 0 80px rgba(187,68,255,0.24)",
    text: "#f0e0ff", textMuted: "#7744aa", textDim: "#3a2255",
    orb1: "#bb44ff18", orb2: "#8822cc10",
    statusOnline: "#00ff88", statusOffline: "#ff2244",
  },
];

// ─── STATUS / PRIORITY CONFIG ─────────────────────────────────────────────────
const TICKET_STATUS = {
  open:        { color: "#00d4ff", label: "OPEN",        icon: "◉" },
  in_progress: { color: "#ffcc00", label: "IN PROGRESS", icon: "◎" },
  resolved:    { color: "#00ff88", label: "RESOLVED",    icon: "◉" },
  closed:      { color: "#666688", label: "CLOSED",      icon: "◌" },
};
const PRIORITY = {
  low:    { color: "#00ff88", label: "LOW" },
  medium: { color: "#00d4ff", label: "MEDIUM" },
  high:   { color: "#ffcc00", label: "HIGH" },
  urgent: { color: "#ff2244", label: "URGENT" },
};
const CATEGORY_ICONS = {
  payment: "💳", coins: "🪙", account: "👤", technical: "⚙️", other: "📌",
};

// ─── GLASS CARD ───────────────────────────────────────────────────────────────
const Glass = ({ children, t, style = {}, glow = false, hover = false }) => {
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

// ─── TAG ──────────────────────────────────────────────────────────────────────
const Tag = ({ children, color, size = "sm" }) => (
  <span style={{
    color, background: `${color}18`, border: `1px solid ${color}35`,
    padding: size === "sm" ? "2px 9px" : "4px 12px",
    borderRadius: 20, fontSize: size === "sm" ? 9 : 11,
    fontWeight: 700, letterSpacing: "0.08em",
    fontFamily: "'Courier New', monospace",
    display: "inline-flex", alignItems: "center", gap: 4,
  }}>
    <span style={{ width: 4, height: 4, borderRadius: "50%", background: color, display: "inline-block" }} />
    {children}
  </span>
);

// ─── CONTACT CARD ─────────────────────────────────────────────────────────────
const ContactCard = ({ icon, label, value, color, link, t }) => (
  <Glass t={t} hover style={{ padding: "16px 18px", cursor: link ? "pointer" : "default" }}
    onClick={() => link && window.open(link, "_blank")}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 38, height: 38, borderRadius: 10, background: `${color}20`, border: `1px solid ${color}33`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: "'Courier New', monospace", marginBottom: 3 }}>{label}</div>
        <div style={{ color: value ? t.text : t.textMuted, fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {value || "Not configured"}
        </div>
      </div>
      {link && value && <span style={{ color: t.textMuted, fontSize: 12 }}>→</span>}
    </div>
  </Glass>
);

// ─── TICKET ROW ───────────────────────────────────────────────────────────────
const TicketRow = ({ ticket, t, i, onView }) => {
  const st = TICKET_STATUS[ticket.status] || TICKET_STATUS.open;
  const pr = PRIORITY[ticket.priority] || PRIORITY.medium;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "auto 1fr auto auto auto",
      gap: 14, padding: "13px 20px", alignItems: "center",
      borderBottom: `1px solid ${t.glassBorder}`,
      animation: `fadeIn .3s ease ${i * 0.04}s both`,
      cursor: "pointer", transition: "background .2s",
    }}
      onMouseEnter={e => e.currentTarget.style.background = t.glassHover}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      onClick={() => onView(ticket)}
    >
      <div style={{ fontSize: 16 }}>{CATEGORY_ICONS[ticket.category] || "📌"}</div>
      <div>
        <div style={{ color: t.text, fontSize: 13, fontWeight: 600, marginBottom: 3 }}>
          {ticket.subject}
        </div>
        <div style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>
          {ticket.ticket_id} · {new Date(ticket.created_at).toLocaleDateString()}
        </div>
      </div>
      <Tag color={pr.color}>{pr.label}</Tag>
      <Tag color={st.color}>{st.label}</Tag>
      <span style={{ color: t.textMuted, fontSize: 12 }}>→</span>
    </div>
  );
};

// ─── FAQ ITEM ─────────────────────────────────────────────────────────────────
const FAQItem = ({ question, answer, t, i }) => {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: `1px solid ${t.glassBorder}`, animation: `fadeIn .3s ease ${i * 0.05}s both` }}>
      <button onClick={() => setOpen(v => !v)} style={{
        width: "100%", padding: "14px 20px", background: open ? t.glassHover : "transparent",
        border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        transition: "background .2s",
      }}>
        <span style={{ color: t.text, fontSize: 13, fontWeight: 600, textAlign: "left" }}>{question}</span>
        <span style={{ color: t.primary, fontSize: 16, flexShrink: 0, transform: open ? "rotate(180deg)" : "none", transition: "transform .3s" }}>⌄</span>
      </button>
      {open && (
        <div style={{ padding: "0 20px 16px", color: t.textMuted, fontSize: 12, lineHeight: 1.7, animation: "fadeIn .2s ease both" }}>
          {answer}
        </div>
      )}
    </div>
  );
};

// ─── TICKET MODAL ─────────────────────────────────────────────────────────────
const TicketModal = ({ ticket, onClose, t }) => {
  if (!ticket) return null;
  const st = TICKET_STATUS[ticket.status] || TICKET_STATUS.open;
  const pr = PRIORITY[ticket.priority] || PRIORITY.medium;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <Glass t={t} style={{ width: 560, maxWidth: "90vw", maxHeight: "85vh", overflow: "auto", padding: 28, animation: "fadeIn .25s ease both" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22 }}>
          <div>
            <div style={{ color: t.primary, fontSize: 11, fontFamily: "'Courier New', monospace", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 4 }}>{ticket.ticket_id}</div>
            <div style={{ color: t.text, fontSize: 17, fontWeight: 800 }}>{ticket.subject}</div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: t.textMuted, fontSize: 20, padding: 4 }}>✕</button>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
          <Tag color={st.color} size="md">{st.label}</Tag>
          <Tag color={pr.color} size="md">{pr.label}</Tag>
          <Tag color={t.primary} size="md">{ticket.category?.toUpperCase()}</Tag>
        </div>
        <Glass t={t} style={{ padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ color: t.textMuted, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", fontFamily: "'Courier New', monospace", marginBottom: 8 }}>DESCRIPTION</div>
          <div style={{ color: t.text, fontSize: 13, lineHeight: 1.7 }}>{ticket.description}</div>
        </Glass>
        {ticket.admin_response && (
          <Glass t={t} style={{ padding: "14px 16px", border: `1px solid ${t.primary}33` }}>
            <div style={{ color: t.primary, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", fontFamily: "'Courier New', monospace", marginBottom: 8 }}>⚡ ADMIN RESPONSE</div>
            <div style={{ color: t.text, fontSize: 13, lineHeight: 1.7 }}>{ticket.admin_response}</div>
          </Glass>
        )}
        <div style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", marginTop: 16 }}>
          Created: {new Date(ticket.created_at).toLocaleString()}
        </div>
      </Glass>
    </div>
  );
};

// ─── CREATE TICKET FORM ───────────────────────────────────────────────────────
const CreateTicketModal = ({ onClose, onSuccess, t }) => {
  const [form, setForm] = useState({ subject: "", category: "payment", priority: "medium", description: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!form.subject.trim() || !form.description.trim()) { setError("Subject and description required"); return; }
    setSaving(true); setError("");
    try {
      // ✅ FIXED: was /support/create-ticket/ — now POST /support/tickets/
      await client.post('/support/tickets/', form);
      onSuccess();
      onClose();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to create ticket");
    } finally { setSaving(false); }
  };

  const inputStyle = { width: "100%", background: "rgba(0,0,0,0.4)", border: `1px solid ${t.glassBorder}`, borderRadius: 10, padding: "11px 14px", color: t.text, fontSize: 13, outline: "none", fontFamily: "inherit", transition: "border-color .2s", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <Glass t={t} style={{ width: 520, maxWidth: "90vw", padding: 28, animation: "fadeIn .25s ease both" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div style={{ color: t.text, fontSize: 16, fontWeight: 800, fontFamily: "'Courier New', monospace", letterSpacing: "0.05em" }}>🎫 NEW SUPPORT TICKET</div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: t.textMuted, fontSize: 20 }}>✕</button>
        </div>

        {[
          { label: "SUBJECT", key: "subject", type: "input", placeholder: "Brief description of issue" },
        ].map(f => (
          <div key={f.key} style={{ marginBottom: 16 }}>
            <div style={{ color: t.textMuted, fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 6 }}>{f.label}</div>
            <input value={form[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder}
              style={inputStyle} onFocus={e => e.target.style.borderColor = t.primary} onBlur={e => e.target.style.borderColor = t.glassBorder} />
          </div>
        ))}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
          {[
            { label: "CATEGORY", key: "category", options: [["payment","💳 Payment"],["coins","🪙 Coins"],["account","👤 Account"],["technical","⚙️ Technical"],["other","📌 Other"]] },
            { label: "PRIORITY", key: "priority", options: [["low","Low"],["medium","Medium"],["high","High"],["urgent","🚨 Urgent"]] },
          ].map(f => (
            <div key={f.key}>
              <div style={{ color: t.textMuted, fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 6 }}>{f.label}</div>
              <select value={form[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                style={{ ...inputStyle, cursor: "pointer" }}>
                {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 20 }}>
          <div style={{ color: t.textMuted, fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 6 }}>DESCRIPTION</div>
          <textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
            placeholder="Describe your issue in detail…" rows={4}
            style={{ ...inputStyle, resize: "vertical" }}
            onFocus={e => e.target.style.borderColor = t.primary} onBlur={e => e.target.style.borderColor = t.glassBorder} />
        </div>

        {error && <div style={{ color: "#ff2244", fontSize: 12, marginBottom: 14, padding: "8px 12px", background: "#ff224415", borderRadius: 8, border: "1px solid #ff224433" }}>{error}</div>}

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, background: t.glass, border: `1px solid ${t.glassBorder}`, borderRadius: 10, padding: "11px", color: t.textMuted, fontSize: 12, cursor: "pointer", fontFamily: "'Courier New', monospace" }}>CANCEL</button>
          <button onClick={handleSubmit} disabled={saving} style={{
            flex: 2, background: `linear-gradient(135deg, ${t.primary}30, ${t.secondary}20)`,
            border: `1px solid ${t.primary}55`, borderRadius: 10, padding: "11px",
            color: t.primary, fontSize: 12, fontWeight: 700, cursor: saving ? "not-allowed" : "pointer",
            fontFamily: "'Courier New', monospace", letterSpacing: "0.05em",
            boxShadow: `0 0 20px ${t.primary}20`,
          }}>
            {saving ? "SUBMITTING…" : "🎫 SUBMIT TICKET"}
          </button>
        </div>
      </Glass>
    </div>
  );
};

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function SupportPage() {
  const [themeIdx, setThemeIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const progressRef = useRef(null);
  const t = THEMES[themeIdx];

  const [settings, setSettings] = useState(null);
  const [tickets, setTickets]   = useState([]);
  const [faqs, setFaqs]         = useState({});
  const [loading, setLoading]   = useState(true);
  const [tab, setTab]           = useState("overview");
  const [clock, setClock]       = useState("");
  const [viewTicket, setViewTicket]   = useState(null);
  const [showCreate, setShowCreate]   = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  // 60-second theme rotation
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

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [sRes, tRes, fRes] = await Promise.allSettled([
      // ✅ FIXED: was /support/ — now /support/settings/
      client.get('/support/settings/'),
      client.get('/support/tickets/'),
      client.get('/support/faqs/'),
    ]);
    if (sRes.status === "fulfilled") setSettings(sRes.value.data);
    if (tRes.status === "fulfilled") { const d = tRes.value.data; setTickets(Array.isArray(d) ? d : d?.results || []); }
    // ✅ FIXED: backend now returns {results, grouped, count}
    if (fRes.status === "fulfilled") setFaqs(fRes.value.data?.grouped || fRes.value.data || {});
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const filteredTickets = tickets.filter(tk => statusFilter === "all" || tk.status === statusFilter);

  const TABS = [
    { id: "overview", label: "OVERVIEW",  icon: "🏠" },
    { id: "tickets",  label: "TICKETS",   icon: "🎫" },
    { id: "faq",      label: "FAQ",       icon: "❓" },
    { id: "channels", label: "CHANNELS",  icon: "📡" },
  ];

  const totalTickets   = tickets.length;
  const openTickets    = tickets.filter(t => t.status === "open").length;
  const resolvedTickets = tickets.filter(t => t.status === "resolved").length;
  const urgentTickets  = tickets.filter(t => t.priority === "urgent").length;

  return (
    <div style={{ minHeight: "100vh", background: t.bg, color: t.text, fontFamily: "'Segoe UI', -apple-system, sans-serif", transition: "background 1.2s ease" }}>
      <style>{`
        @keyframes fadeIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes pulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.35;transform:scale(.75)} }
        @keyframes float  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-20px)} }
        * { box-sizing:border-box; }
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-thumb{background:${t.glassBorder};border-radius:2px}
        textarea, input, select { color-scheme: dark; }
      `}</style>

      {/* Ambient orbs */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0, overflow: "hidden" }}>
        <div style={{ position: "absolute", top: "5%", left: "2%", width: 500, height: 500, borderRadius: "50%", background: t.orb1, filter: "blur(90px)", animation: "float 9s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: "8%", right: "4%", width: 380, height: 380, borderRadius: "50%", background: t.orb2, filter: "blur(70px)", animation: "float 11s ease-in-out infinite reverse" }} />
        <div style={{ position: "absolute", top: "50%", left: "50%", width: 800, height: 800, borderRadius: "50%", background: `${t.primary}04`, filter: "blur(130px)", transform: "translate(-50%,-50%)" }} />
        <div style={{ position: "absolute", inset: 0, backgroundImage: `linear-gradient(${t.glassBorder} 1px, transparent 1px), linear-gradient(90deg, ${t.glassBorder} 1px, transparent 1px)`, backgroundSize: "50px 50px", opacity: 0.25 }} />
      </div>

      {/* TOP BAR */}
      <div style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(32px)", borderBottom: `1px solid ${t.glassBorder}`, padding: "10px 26px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: t.primary, animation: "pulse 1.5s infinite", boxShadow: `0 0 12px ${t.primary}` }} />
          <span style={{ color: t.primary, fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", fontFamily: "'Courier New', monospace" }}>{t.name}</span>
          <div style={{ width: 1, height: 14, background: t.glassBorder }} />
          <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>SUPPORT CONTROL CENTER</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {/* Theme progress */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: t.textMuted, fontSize: 9, fontFamily: "'Courier New', monospace" }}>THEME</span>
            <div style={{ width: 80, height: 2, background: t.glassBorder, borderRadius: 1 }}>
              <div style={{ height: "100%", width: `${progress}%`, background: `linear-gradient(90deg, ${t.primary}, ${t.secondary})`, borderRadius: 1, transition: "width 0.1s linear" }} />
            </div>
          </div>
          {/* Support online status */}
          {settings && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: settings.is_support_online ? t.statusOnline : t.statusOffline, boxShadow: `0 0 8px ${settings.is_support_online ? t.statusOnline : t.statusOffline}`, animation: "pulse 2s infinite" }} />
              <span style={{ color: settings.is_support_online ? t.statusOnline : t.statusOffline, fontSize: 10, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>
                {settings.is_support_online ? "ONLINE" : "OFFLINE"}
              </span>
            </div>
          )}
          <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace" }}>{clock}</span>
          <button onClick={fetchAll} style={{ background: t.glass, border: `1px solid ${t.glassBorder}`, borderRadius: 8, padding: "6px 14px", color: t.primary, fontSize: 10, cursor: "pointer", fontFamily: "'Courier New', monospace", fontWeight: 700 }}>↻ SYNC</button>
        </div>
      </div>

      <div style={{ position: "relative", zIndex: 1, padding: "28px 28px 48px", maxWidth: 1400, margin: "0 auto" }}>

        {/* HEADER */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, animation: "fadeIn .5s ease both" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 54, height: 54, borderRadius: 14, background: t.glass, border: `1px solid ${t.glassBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, boxShadow: t.glowStrong }}>🛟</div>
            <div>
              <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900, letterSpacing: "0.07em", fontFamily: "'Courier New', monospace", background: `linear-gradient(135deg, ${t.text} 30%, ${t.primary})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                SUPPORT CENTER
              </h1>
              <p style={{ margin: "4px 0 0", color: t.textMuted, fontSize: 11, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace" }}>
                TICKET MANAGEMENT · FAQ · CONTACT CHANNELS
              </p>
            </div>
          </div>
          <button onClick={() => setShowCreate(true)} style={{
            display: "flex", alignItems: "center", gap: 8,
            background: `linear-gradient(135deg, ${t.primary}30, ${t.secondary}20)`,
            border: `1px solid ${t.primary}55`, borderRadius: 10, padding: "11px 22px",
            color: t.primary, fontSize: 12, fontWeight: 700, cursor: "pointer",
            fontFamily: "'Courier New', monospace", letterSpacing: "0.05em",
            boxShadow: `0 0 24px ${t.primary}20`,
          }}>
            🎫 NEW TICKET
          </button>
        </div>

        {/* STATS */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 26 }}>
          {[
            { label: "Total Tickets", value: totalTickets,    icon: "🎫", color: t.primary },
            { label: "Open",          value: openTickets,     icon: "◉",  color: "#00d4ff" },
            { label: "Resolved",      value: resolvedTickets, icon: "✅", color: "#00ff88" },
            { label: "Urgent",        value: urgentTickets,   icon: "🚨", color: "#ff2244" },
          ].map(s => (
            <Glass key={s.label} t={t} style={{ padding: "20px 22px", position: "relative", overflow: "hidden" }}>
              <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at top right, ${s.color}10, transparent 60%)`, pointerEvents: "none" }} />
              <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${s.color}80, transparent)` }} />
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <span style={{ fontSize: 16 }}>{s.icon}</span>
                <span style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", fontFamily: "'Courier New', monospace" }}>{s.label}</span>
              </div>
              {loading
                ? <div style={{ height: 36, width: 60, borderRadius: 8, background: `${s.color}15`, animation: "pulse 1.4s infinite" }} />
                : <div style={{ fontSize: 34, fontWeight: 900, color: s.color, fontFamily: "'Courier New', monospace", lineHeight: 1, textShadow: `0 0 20px ${s.color}60` }}>{s.value}</div>
              }
            </Glass>
          ))}
        </div>

        {/* TABS */}
        <div style={{ display: "flex", gap: 3, marginBottom: 22, background: "rgba(0,0,0,0.4)", border: `1px solid ${t.glassBorder}`, borderRadius: 13, padding: 4, backdropFilter: "blur(20px)", width: "fit-content" }}>
          {TABS.map(tb => (
            <button key={tb.id} onClick={() => setTab(tb.id)} style={{
              display: "flex", alignItems: "center", gap: 7, padding: "9px 20px",
              borderRadius: 10, border: tab === tb.id ? `1px solid ${t.glassBorder}` : "1px solid transparent",
              cursor: "pointer", fontFamily: "'Courier New', monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
              background: tab === tb.id ? `linear-gradient(135deg, ${t.primary}28, ${t.secondary}18)` : "transparent",
              color: tab === tb.id ? t.primary : t.textMuted,
              boxShadow: tab === tb.id ? `0 0 20px ${t.primary}25` : "none",
              transition: "all .25s",
            }}>
              <span>{tb.icon}</span>{tb.label}
            </button>
          ))}
        </div>

        {/* OVERVIEW TAB */}
        {tab === "overview" && (
          <div style={{ animation: "fadeIn .4s ease both" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

              {/* Recent Tickets */}
              <Glass t={t} style={{ overflow: "hidden" }}>
                <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.glassBorder}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: t.text, fontWeight: 700, fontSize: 13, fontFamily: "'Courier New', monospace" }}>🎫 RECENT TICKETS</span>
                  <button onClick={() => setTab("tickets")} style={{ background: "none", border: "none", color: t.primary, fontSize: 11, cursor: "pointer", fontFamily: "'Courier New', monospace" }}>VIEW ALL →</button>
                </div>
                {loading ? (
                  <div style={{ padding: 50, textAlign: "center", color: t.textMuted, fontFamily: "'Courier New', monospace", fontSize: 11, animation: "pulse 1.4s infinite" }}>LOADING…</div>
                ) : tickets.length === 0 ? (
                  <div style={{ padding: 50, textAlign: "center", color: t.textMuted, fontSize: 12 }}>No tickets yet</div>
                ) : tickets.slice(0, 5).map((tk, i) => (
                  <TicketRow key={tk.id} ticket={tk} t={t} i={i} onView={setViewTicket} />
                ))}
              </Glass>

              {/* Support Info + Quick FAQs */}
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Maintenance alert */}
                {settings?.maintenance_mode && (
                  <div style={{ background: "#ffcc0015", border: "1px solid #ffcc0044", borderRadius: 12, padding: "14px 18px", display: "flex", gap: 12, alignItems: "flex-start" }}>
                    <span style={{ fontSize: 20 }}>⚠️</span>
                    <div>
                      <div style={{ color: "#ffcc00", fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", marginBottom: 4 }}>MAINTENANCE MODE</div>
                      <div style={{ color: "#ffcc00aa", fontSize: 12 }}>{settings.maintenance_message || "System under maintenance"}</div>
                    </div>
                  </div>
                )}

                {/* Status card */}
                <Glass t={t} style={{ padding: "18px 20px" }}>
                  <div style={{ color: t.text, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", marginBottom: 14, letterSpacing: "0.05em" }}>📊 TICKET STATUS BREAKDOWN</div>
                  {Object.entries(TICKET_STATUS).map(([key, cfg]) => {
                    const count = tickets.filter(tk => tk.status === key).length;
                    const pct = tickets.length ? Math.round((count / tickets.length) * 100) : 0;
                    return (
                      <div key={key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                        <span style={{ color: cfg.color, fontSize: 10, fontWeight: 700, fontFamily: "'Courier New', monospace", width: 90, flexShrink: 0 }}>{cfg.icon} {cfg.label}</span>
                        <div style={{ flex: 1, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${cfg.color}, ${cfg.color}88)`, borderRadius: 2, transition: "width .8s ease" }} />
                        </div>
                        <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", width: 20, textAlign: "right" }}>{count}</span>
                      </div>
                    );
                  })}
                </Glass>

                {/* App version */}
                {settings && (
                  <Glass t={t} style={{ padding: "14px 18px" }}>
                    <div style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace", marginBottom: 10 }}>APP VERSION INFO</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ color: t.text, fontSize: 14, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>v{settings.latest_version_name}</span>
                      {settings.force_update && <Tag color="#ff2244" size="md">UPDATE REQUIRED</Tag>}
                    </div>
                  </Glass>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TICKETS TAB */}
        {tab === "tickets" && (
          <div style={{ animation: "fadeIn .4s ease both" }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ color: t.textMuted, fontSize: 10, fontFamily: "'Courier New', monospace", letterSpacing: "0.1em" }}>STATUS:</span>
              {["all", ...Object.keys(TICKET_STATUS)].map(s => (
                <button key={s} onClick={() => setStatusFilter(s)} style={{
                  background: statusFilter === s ? `${(TICKET_STATUS[s]?.color || t.primary)}20` : "rgba(255,255,255,0.03)",
                  border: `1px solid ${statusFilter === s ? (TICKET_STATUS[s]?.color || t.primary) : t.glassBorder}`,
                  borderRadius: 20, padding: "5px 14px",
                  color: statusFilter === s ? (TICKET_STATUS[s]?.color || t.primary) : t.textMuted,
                  fontSize: 10, cursor: "pointer", fontFamily: "'Courier New', monospace", fontWeight: 700, letterSpacing: "0.08em", transition: "all .2s",
                }}>
                  {s === "all" ? "ALL" : TICKET_STATUS[s].label}
                </button>
              ))}
              <span style={{ marginLeft: "auto", color: t.textMuted, fontSize: 11, fontFamily: "'Courier New', monospace" }}>
                <span style={{ color: t.primary, fontWeight: 700 }}>{filteredTickets.length}</span> TICKETS
              </span>
            </div>
            <Glass t={t} style={{ overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto auto auto", gap: 14, padding: "10px 20px", borderBottom: `1px solid ${t.glassBorder}`, background: "rgba(0,0,0,0.3)" }}>
                {["", "SUBJECT", "PRIORITY", "STATUS", ""].map((h, i) => (
                  <span key={i} style={{ color: t.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", fontFamily: "'Courier New', monospace" }}>{h}</span>
                ))}
              </div>
              {loading ? (
                <div style={{ padding: 60, textAlign: "center", color: t.textMuted, fontFamily: "'Courier New', monospace", animation: "pulse 1.4s infinite", fontSize: 11 }}>LOADING…</div>
              ) : filteredTickets.length === 0 ? (
                <div style={{ padding: 70, textAlign: "center" }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>🎫</div>
                  <div style={{ color: t.textMuted, fontFamily: "'Courier New', monospace", fontSize: 11, letterSpacing: "0.1em" }}>NO TICKETS FOUND</div>
                  <button onClick={() => setShowCreate(true)} style={{ marginTop: 14, background: `${t.primary}20`, border: `1px solid ${t.primary}44`, borderRadius: 8, padding: "8px 20px", color: t.primary, fontSize: 11, cursor: "pointer", fontFamily: "'Courier New', monospace" }}>
                    CREATE FIRST TICKET
                  </button>
                </div>
              ) : filteredTickets.map((tk, i) => (
                <TicketRow key={tk.id} ticket={tk} t={t} i={i} onView={setViewTicket} />
              ))}
            </Glass>
          </div>
        )}

        {/* FAQ TAB */}
        {tab === "faq" && (
          <div style={{ animation: "fadeIn .4s ease both" }}>
            {loading ? (
              <div style={{ padding: 60, textAlign: "center", color: t.textMuted, fontFamily: "'Courier New', monospace", animation: "pulse 1.4s infinite" }}>LOADING…</div>
            ) : Object.keys(faqs).length === 0 ? (
              <Glass t={t} style={{ padding: 80, textAlign: "center" }}>
                <div style={{ fontSize: 36, marginBottom: 14 }}>❓</div>
                <div style={{ color: t.textMuted, fontFamily: "'Courier New', monospace", fontSize: 12 }}>NO FAQS AVAILABLE</div>
              </Glass>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {Object.entries(faqs).map(([category, items]) => (
                  <Glass key={category} t={t} style={{ overflow: "hidden" }}>
                    <div style={{ padding: "14px 20px", borderBottom: `1px solid ${t.glassBorder}`, background: "rgba(0,0,0,0.2)" }}>
                      <span style={{ color: t.primary, fontSize: 12, fontWeight: 700, fontFamily: "'Courier New', monospace", letterSpacing: "0.08em" }}>
                        {CATEGORY_ICONS[category] || "📂"} {category.toUpperCase()}
                      </span>
                    </div>
                    {items.map((faq, i) => (
                      <FAQItem key={i} question={faq.question} answer={faq.answer} t={t} i={i} />
                    ))}
                  </Glass>
                ))}
              </div>
            )}
          </div>
        )}

        {/* CHANNELS TAB */}
        {tab === "channels" && (
          <div style={{ animation: "fadeIn .4s ease both" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px,1fr))", gap: 14 }}>
              {settings ? (
                <>
                  <ContactCard icon="✈️" label="Telegram Group" value={settings.telegram_group} color="#00d4ff" link={settings.telegram_group} t={t} />
                  <ContactCard icon="💬" label="Telegram Admin" value={settings.telegram_admin} color="#00d4ff" link={settings.telegram_admin} t={t} />
                  <ContactCard icon="📱" label="WhatsApp" value={settings.whatsapp_number} color="#00ff88" link={settings.whatsapp_number ? `https://wa.me/${settings.whatsapp_number}` : null} t={t} />
                  <ContactCard icon="👥" label="WhatsApp Group" value={settings.whatsapp_group} color="#00ff88" link={settings.whatsapp_group} t={t} />
                  <ContactCard icon="📘" label="Facebook Page" value={settings.facebook_page} color="#4488ff" link={settings.facebook_page} t={t} />
                  <ContactCard icon="📧" label="Email Support" value={settings.email_support} color="#ffcc00" link={settings.email_support ? `mailto:${settings.email_support}` : null} t={t} />
                </>
              ) : (
                <div style={{ padding: 60, textAlign: "center", color: t.textMuted, gridColumn: "1/-1" }}>
                  {loading ? "LOADING…" : "No contact channels configured"}
                </div>
              )}
            </div>

            {/* Business Hours */}
            {settings && (
              <Glass t={t} style={{ padding: "20px 24px", marginTop: 16 }}>
                <div style={{ color: t.text, fontSize: 13, fontWeight: 700, fontFamily: "'Courier New', monospace", marginBottom: 16 }}>🕐 BUSINESS HOURS</div>
                <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                  <div style={{ color: t.textMuted, fontSize: 12 }}>
                    <span style={{ color: t.primary, fontWeight: 700 }}>{settings.support_hours_start}</span>
                    {" — "}
                    <span style={{ color: t.primary, fontWeight: 700 }}>{settings.support_hours_end}</span>
                  </div>
                  <Tag color={settings.is_support_online ? "#00ff88" : "#ff2244"} size="md">
                    {settings.is_support_online ? "SUPPORT ONLINE" : "SUPPORT OFFLINE"}
                  </Tag>
                </div>
              </Glass>
            )}
          </div>
        )}

        {/* Theme dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 36 }}>
          {THEMES.map((th, i) => (
            <button key={i} onClick={() => { setThemeIdx(i); setProgress(0); }} title={th.name} style={{
              width: i === themeIdx ? 36 : 10, height: 10, borderRadius: 5, border: "none", cursor: "pointer",
              background: i === themeIdx ? `linear-gradient(90deg, ${th.primary}, ${th.secondary})` : `${th.primary}44`,
              boxShadow: i === themeIdx ? `0 0 14px ${th.primary}70` : "none",
              transition: "all .4s ease",
            }} />
          ))}
        </div>
      </div>

      {/* Modals */}
      {viewTicket && <TicketModal ticket={viewTicket} onClose={() => setViewTicket(null)} t={t} />}
      {showCreate && <CreateTicketModal onClose={() => setShowCreate(false)} onSuccess={fetchAll} t={t} />}
    </div>
  );
}