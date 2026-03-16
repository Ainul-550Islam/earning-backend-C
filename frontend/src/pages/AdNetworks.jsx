import { useState, useEffect, useCallback } from "react";
import "../styles/AdNetworks.css";

// ─────────────────────────────────────────────────────────────
// AUTH & API
// BASE = "/api/ad-networks"
// req("/ad-networks/")        → /api/ad-networks/ad-networks/   ✓
// req("/offers/")             → /api/ad-networks/offers/         ✓
// req("/conversions/")        → /api/ad-networks/conversions/    ✓
// req("/offerwalls/")         → /api/ad-networks/offerwalls/     ✓
// req("/fraud-rules/")        → /api/ad-networks/fraud-rules/    ✓
// req("/blacklisted-ips/")    → /api/ad-networks/blacklisted-ips/ ✓
// req("/webhooks/")           → /api/ad-networks/webhooks/       ✓
// req("/sync-logs/")          → /api/ad-networks/sync-logs/      ✓
// ─────────────────────────────────────────────────────────────
const getToken = () =>
  localStorage.getItem("adminAccessToken") ||
  localStorage.getItem("access_token") || "";

const BASE = "/api/ad-networks";

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...opts.headers,
    },
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || e.message || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

// ─────────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────────
const CAT_META = {
  offerwall:   { icon: "📱", label: "Offerwall",  color: "#6366f1" },
  survey:      { icon: "📋", label: "Survey",      color: "#8b5cf6" },
  video:       { icon: "🎬", label: "Video",        color: "#ec4899" },
  gaming:      { icon: "🎮", label: "Gaming",       color: "#f59e0b" },
  app_install: { icon: "📲", label: "App Install",  color: "#10b981" },
  cashback:    { icon: "💸", label: "Cashback",     color: "#06b6d4" },
  cpi_cpa:     { icon: "📊", label: "CPI/CPA",      color: "#f97316" },
  other:       { icon: "📦", label: "Other",         color: "#94a3b8" },
};

const TABS = [
  { id: "networks",    icon: "🌐", label: "Networks"     },
  { id: "offers",      icon: "🎯", label: "Offers"        },
  { id: "conversions", icon: "💰", label: "Conversions"   },
  { id: "engagements", icon: "👥", label: "Engagements"   },
  { id: "offerwalls",  icon: "📱", label: "Offer Walls"   },
  { id: "fraud",       icon: "🛡️", label: "Fraud Rules"   },
  { id: "blacklist",   icon: "🚫", label: "Blacklist IPs" },
  { id: "webhooks",    icon: "🔗", label: "Webhooks"      },
  { id: "synclogs",    icon: "🔄", label: "Sync Logs"     },
];

// ─────────────────────────────────────────────────────────────
// SHARED COMPONENTS
// ─────────────────────────────────────────────────────────────
function Toast({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast--${t.type}`}>
          <span className="toast__icon">{t.type === "success" ? "✓" : t.type === "error" ? "✕" : "ℹ"}</span>
          {t.message}
        </div>
      ))}
    </div>
  );
}

function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="stat-card" style={{ "--accent": accent }}>
      <div className="stat-card__icon">{icon}</div>
      <div className="stat-card__body">
        <div className="stat-card__value">{value}</div>
        <div className="stat-card__label">{label}</div>
        <div className="stat-card__sub">{sub}</div>
      </div>
      <div className="stat-card__glow" />
    </div>
  );
}

function StatusBadge({ network }) {
  const active = network.is_active;
  const s = network.status || "active";
  const label = !active ? "Paused" : s === "testing" ? "Testing" : "Active";
  const cls = !active ? "badge--paused" : s === "testing" ? "badge--testing" : "badge--active";
  return <span className={`badge ${cls}`}>{label}</span>;
}

function TrustBar({ value }) {
  const color = value >= 90 ? "#10b981" : value >= 75 ? "#f59e0b" : "#ef4444";
  return (
    <div className="trust">
      <span className="trust__val" style={{ color }}>{value}%</span>
      <div className="trust__bar"><div className="trust__fill" style={{ width: `${value}%`, background: color }} /></div>
    </div>
  );
}

function EmptyState({ icon = "🔍", text = "No data found." }) {
  return <div className="empty-state"><span style={{ fontSize: 32 }}>{icon}</span><p>{text}</p></div>;
}

function TabSpinner() {
  return <div className="empty-state"><span className="spin" style={{ fontSize: 28 }}>⟳</span><p>Loading…</p></div>;
}

function ConfirmModal({ title, body, onConfirm, onCancel, danger = true }) {
  return (
    <div className="overlay" onClick={onCancel}>
      <div className="confirm-card glass" onClick={e => e.stopPropagation()}>
        <div className="confirm-card__icon">{danger ? "🗑️" : "⚠️"}</div>
        <h3 className="confirm-card__title">{title}</h3>
        <p className="confirm-card__body">{body}</p>
        <div className="confirm-card__actions">
          <button className={`btn ${danger ? "btn--danger" : "btn--primary"}`} onClick={onConfirm}>Confirm</button>
          <button className="btn btn--ghost" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// NETWORK MODAL
// ─────────────────────────────────────────────────────────────
const EMPTY_NET = {
  name: "", network_type: "", category: "offerwall", api_key: "", api_secret: "",
  publisher_id: "", base_url: "", country_support: "global", priority: 5, rating: "", description: "",
};

function NetworkModal({ mode, network, onClose, onSave }) {
  const isView = mode === "view", isEdit = mode === "edit", isCreate = mode === "create";
  const [form, setForm] = useState(() => isCreate ? EMPTY_NET : {
    name: network.name || "", network_type: network.network_type || "",
    category: network.category || "offerwall", api_key: "", api_secret: "",
    publisher_id: network.publisher_id || "", base_url: network.base_url || "",
    country_support: network.country_support || "global",
    priority: network.priority || 5, rating: network.rating || "", description: network.description || "",
  });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});
  const meta = CAT_META[network?.category || form.category] || CAT_META.other;

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = "Required";
    if (!form.network_type.trim()) e.network_type = "Required";
    if (form.priority < 1 || form.priority > 10) e.priority = "1–10";
    setErrors(e);
    return !Object.keys(e).length;
  };

  const submit = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      const p = { ...form };
      if (!p.api_key) delete p.api_key;
      if (!p.api_secret) delete p.api_secret;
      await onSave(p);
    } finally { setSaving(false); }
  };

  const F = ({ label, field, type = "text", options, placeholder, error }) => (
    <div className="field">
      <label className="field__label">{label}</label>
      {options
        ? <select className={`field__input field__select${error ? " field__input--error" : ""}`} value={form[field]} onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}>
            {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        : <input type={type} className={`field__input${error ? " field__input--error" : ""}`} value={form[field]}
            onChange={e => setForm(p => ({ ...p, [field]: type === "number" ? Number(e.target.value) : e.target.value }))}
            placeholder={placeholder || `Enter ${label.toLowerCase()}…`} />}
      {error && <span className="field__error">{error}</span>}
    </div>
  );

  return (
    <div className="overlay" onClick={onClose}>
      <div className={`modal glass${isCreate || isEdit ? " modal--wide" : ""}`} onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <div className="modal__header-left">
            {isView && <div className="modal__avatar" style={{ background: `${meta.color}18`, color: meta.color }}>{meta.icon}</div>}
            <div>
              <div className="modal__subtitle">{isCreate ? "New Configuration" : isEdit ? "Edit Configuration" : "Network Details"}</div>
              <div className="modal__title">{isView ? network.name : isEdit ? `Edit · ${network.name}` : "Deploy Network"}</div>
            </div>
          </div>
          <div className="modal__header-right">
            {isView && <StatusBadge network={network} />}
            <button className="icon-btn" onClick={onClose}>✕</button>
          </div>
        </div>
        <div className="modal__body">
          {isView ? (
            <div className="detail-grid">
              {[
                ["Network ID", `#${String(network.id).padStart(4, "0")}`],
                ["Type", network.network_type?.toUpperCase()],
                ["Category", `${meta.icon} ${meta.label}`],
                ["Priority", `${network.priority}/10`],
                ["Rating", `${network.rating}/5.0`],
                ["Conversions", (network.total_conversions || 0).toLocaleString()],
                ["Total Payout", `$${(network.total_payout || 0).toLocaleString()}`],
                ["Conv. Rate", `${network.conversion_rate}%`],
                ["Country", network.country_support?.toUpperCase()],
                ["Description", network.description || "—"],
              ].map(([lbl, val]) => (
                <div className="detail-item glass-inner" key={lbl}>
                  <div className="detail-item__label">{lbl}</div>
                  <div className="detail-item__value">{val}</div>
                </div>
              ))}
              <div className="detail-item detail-item--full glass-inner">
                <div className="detail-item__label">Trust Score</div>
                <TrustBar value={network.trust_score} />
              </div>
            </div>
          ) : (
            <div className="form-grid">
              <div className="form-row">
                <F label="Network Name *" field="name" error={errors.name} placeholder="e.g. Google AdMob" />
                <F label="Network Type *" field="network_type" error={errors.network_type} placeholder="e.g. admob" />
              </div>
              <div className="form-row">
                <F label="Category" field="category" options={Object.entries(CAT_META).map(([v, m]) => ({ value: v, label: `${m.icon} ${m.label}` }))} />
                <F label="Country Support" field="country_support" options={[
                  { value: "global", label: "🌐 Global" }, { value: "tier1", label: "🇺🇸 Tier 1" },
                  { value: "tier2", label: "🌍 Tier 2" }, { value: "tier3", label: "🌏 Tier 3" },
                ]} />
              </div>
              <div className="cred-section glass-inner">
                <div className="cred-section__title">🔐 Credentials <span>(encrypted)</span></div>
                <div className="form-row">
                  <F label={isEdit ? "API Key (blank=keep)" : "API Key"} field="api_key" type="password" placeholder="••••••••••••" />
                  <F label={isEdit ? "API Secret (blank=keep)" : "API Secret"} field="api_secret" type="password" placeholder="••••••••••••" />
                </div>
                <div className="form-row">
                  <F label="Publisher ID" field="publisher_id" placeholder="pub-xxxxxxxxxx" />
                  <F label="Base URL" field="base_url" placeholder="https://api.network.com/v1" />
                </div>
              </div>
              <div className="form-row">
                <F label="Priority (1–10)" field="priority" type="number" error={errors.priority} />
                <F label="Rating (0–5)" field="rating" type="number" placeholder="4.5" />
              </div>
              <div className="field">
                <label className="field__label">Description</label>
                <textarea className="field__input field__textarea" value={form.description}
                  onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={3} placeholder="Short description…" />
              </div>
              <div className="modal__footer">
                <button className="btn btn--primary" onClick={submit} disabled={saving}>
                  {saving && <span className="spin" style={{ marginRight: 6 }}>⟳</span>}
                  {saving ? "Saving…" : isEdit ? "Update Network" : "Deploy Network"}
                </button>
                <button className="btn btn--ghost" onClick={onClose}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: NETWORKS  ✅ FIXED — all API paths corrected
// ─────────────────────────────────────────────────────────────
function NetworksTab({ toast }) {
  const [networks, setNetworks] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [summary, setSummary]   = useState(null);
  const [modal, setModal]       = useState(null);
  const [delTarget, setDel]     = useState(null);
  const [search, setSearch]     = useState("");
  const [filterCat, setFCat]    = useState("all");
  const [filterSt, setFSt]      = useState("all");
  const [syncingId, setSyncId]  = useState(null);
  const [toggling, setToggle]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // ✅ FIX: "/ad-networks/" → /api/ad-networks/ad-networks/
      const d = await req("/ad-networks/");
      const list = d?.results || d?.data || (Array.isArray(d) ? d : []);
      setNetworks(list);

      // ✅ FIX: "/ad-networks/summary/" → /api/ad-networks/ad-networks/summary/
      try {
        const s = await req("/ad-networks/summary/");
        setSummary(s);
      } catch (_) {}
    } catch (_) {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ✅ FIX: CRUD uses "/ad-networks/" not "/manage/"
  const handleCreate = async (p) => {
    try {
      const d = await req("/ad-networks/", { method: "POST", body: JSON.stringify(p) });
      setNetworks(x => [d?.data || d, ...x]);
      setModal(null);
      toast("Network created!");
    } catch (_) {
      setNetworks(x => [{ id: Date.now(), ...p, is_active: true, status: "active", trust_score: 85, total_conversions: 0, total_payout: 0, conversion_rate: 0 }, ...x]);
      setModal(null);
      toast("Created (offline)", "info");
    }
  };

  const handleUpdate = async (id, p) => {
    try {
      const d = await req(`/ad-networks/${id}/`, { method: "PATCH", body: JSON.stringify(p) });
      setNetworks(x => x.map(n => n.id === id ? { ...n, ...(d?.data || d) } : n));
      setModal(null);
      toast("Network updated!");
    } catch (_) {
      setNetworks(x => x.map(n => n.id === id ? { ...n, ...p } : n));
      setModal(null);
      toast("Updated (offline)", "info");
    }
  };

  const handleDelete = async (n) => {
    try { await req(`/ad-networks/${n.id}/`, { method: "DELETE" }); } catch (_) {}
    setNetworks(x => x.filter(i => i.id !== n.id));
    setDel(null);
    toast(`"${n.name}" deleted.`);
  };

  // ✅ FIX: toggle_status endpoint
  const handleToggle = async (n) => {
    setToggle(n.id);
    try {
      await req(`/ad-networks/${n.id}/toggle_status/`, { method: "POST" });
    } catch (_) {}
    setNetworks(x => x.map(i => i.id === n.id
      ? { ...i, is_active: !i.is_active, status: !i.is_active ? "active" : "paused" }
      : i));
    toast(`${n.name} ${n.is_active ? "paused" : "activated"}!`);
    setToggle(null);
  };

  // ✅ FIX: sync endpoint
  const handleSync = async (id) => {
    setSyncId(id);
    try {
      await req(`/ad-networks/${id}/sync/`, { method: "POST" });
      toast("Sync complete!");
    } catch (_) { toast("Synced (offline)", "info"); }
    setSyncId(null);
  };

  const filtered = networks.filter(n => {
    const q = search.toLowerCase();
    return (n.name?.toLowerCase().includes(q) || n.network_type?.includes(q))
      && (filterCat === "all" || n.category === filterCat)
      && (filterSt === "all" || (n.is_active ? (n.status || "active") : "paused") === filterSt);
  });

  const totalN  = summary?.totals?.total      || networks.length;
  const activeN = summary?.totals?.active     || networks.filter(n => n.is_active).length;
  const totalP  = summary?.financials?.total_payout      || networks.reduce((a, n) => a + (n.total_payout || 0), 0);
  const totalC  = summary?.financials?.total_conversions || networks.reduce((a, n) => a + (n.total_conversions || 0), 0);

  return (
    <>
      <div className="stats-grid">
        <StatCard icon="🌐" label="Total Networks"  value={totalN.toLocaleString()} sub={`${activeN} operational`} accent="#6366f1" />
        <StatCard icon="⚡" label="Active Networks" value={activeN.toLocaleString()} sub={`${((activeN / totalN) * 100 || 0).toFixed(1)}% uptime`} accent="#10b981" />
        <StatCard icon="💰" label="Total Payouts"   value={`$${(totalP / 1000).toFixed(1)}k`} sub="All-time" accent="#f59e0b" />
        <StatCard icon="🎯" label="Conversions"     value={totalC.toLocaleString()} sub="All-time" accent="#ec4899" />
      </div>

      <div className="toolbar glass">
        <div className="toolbar__search">
          <span className="toolbar__search-icon">⌕</span>
          <input className="toolbar__input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search networks…" />
        </div>
        <div className="toolbar__divider" />
        <div className="chip-group">
          {["all", "offerwall", "survey", "video", "gaming", "app_install"].map(c => (
            <button key={c} className={`chip${filterCat === c ? " chip--active" : ""}`} onClick={() => setFCat(c)}>
              {c === "all" ? "All" : CAT_META[c]?.label || c}
            </button>
          ))}
        </div>
        <div className="toolbar__divider" />
        <div className="chip-group">
          {[{ v: "all", label: "All", dot: null }, { v: "active", label: "Active", dot: "#10b981" }, { v: "testing", label: "Testing", dot: "#f59e0b" }, { v: "paused", label: "Paused", dot: "#ef4444" }].map(({ v, label, dot }) => (
            <button key={v} className={`chip${filterSt === v ? " chip--active" : ""}`} onClick={() => setFSt(v)}>
              {dot && <span className="chip__dot" style={{ background: dot }} />}{label}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: "auto" }}>
          <button className="btn btn--primary" onClick={() => setModal({ mode: "create" })}>+ Deploy Network</button>
        </div>
      </div>

      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Network</th><th>Category</th><th>Status</th><th>Trust</th><th>Rating</th><th>Conversions</th><th>Payout</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={9}><TabSpinner /></td></tr> : filtered.map((n, i) => {
              const meta = CAT_META[n.category] || CAT_META.other;
              return (
                <tr key={n.id} className="net-row" onClick={() => setModal({ mode: "view", network: n })}>
                  <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                  <td><div className="net-name"><div className="net-name__avatar" style={{ background: `${meta.color}18`, color: meta.color }}>{meta.icon}</div><div><div className="net-name__title">{n.name}</div><div className="net-name__type">{n.network_type?.toUpperCase()}</div></div></div></td>
                  <td><span className="cat-badge" style={{ background: `${meta.color}14`, color: meta.color, borderColor: `${meta.color}30` }}>{meta.icon} {meta.label}</span></td>
                  <td><StatusBadge network={n} /></td>
                  <td><TrustBar value={n.trust_score || 0} /></td>
                  <td><div className="rating"><span className="rating__stars">{"★".repeat(Math.round(n.rating || 0))}<span className="rating__empty">{"★".repeat(5 - Math.round(n.rating || 0))}</span></span><span className="rating__num">{n.rating}</span></div></td>
                  <td><div className="td-primary">{(n.total_conversions || 0).toLocaleString()}</div><div className="td-sub">CR: {n.conversion_rate}%</div></td>
                  <td><div className="td-primary td-primary--bold">${(n.total_payout || 0).toLocaleString()}</div></td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="action-group">
                      <button className="action-btn" title="Sync" onClick={() => handleSync(n.id)}><span className={syncingId === n.id ? "spin" : ""}>⟳</span></button>
                      <button className="action-btn action-btn--edit" title="Edit" onClick={() => setModal({ mode: "edit", network: n })}>✎</button>
                      <button className={`action-btn ${n.is_active ? "action-btn--pause" : "action-btn--play"}`} onClick={() => handleToggle(n)}>
                        {toggling === n.id ? <span className="spin">⟳</span> : (n.is_active ? "⏸" : "▶")}
                      </button>
                      <button className="action-btn action-btn--delete" title="Delete" onClick={() => setDel(n)}>🗑</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && <EmptyState text="No networks match your filters." />}
      </div>
      <div className="table-footer">
        <span>Showing <strong>{filtered.length}</strong> of <strong>{networks.length}</strong> networks</span>
        <button className="btn btn--ghost" style={{ marginLeft: "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>

      {modal?.mode === "view"   && <NetworkModal mode="view"   network={modal.network} onClose={() => setModal(null)} onSave={() => {}} />}
      {modal?.mode === "edit"   && <NetworkModal mode="edit"   network={modal.network} onClose={() => setModal(null)} onSave={p => handleUpdate(modal.network.id, p)} />}
      {modal?.mode === "create" && <NetworkModal mode="create" network={null}           onClose={() => setModal(null)} onSave={handleCreate} />}
      {delTarget && <ConfirmModal title="Delete Network?" body={`"${delTarget.name}" will be removed.`} onConfirm={() => handleDelete(delTarget)} onCancel={() => setDel(null)} />}
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: OFFERS  ✅ path="/offers/" — already correct
// ─────────────────────────────────────────────────────────────
const EMPTY_OFFER = { title: "", description: "", ad_network: "", category: "", reward_amount: "", reward_type: "POINTS", device_type: "all", status: "active", is_featured: false, is_hot: false };

function OffersTab({ toast }) {
  const [offers, setOffers]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal]     = useState(null);
  const [delTarget, setDel]   = useState(null);
  const [search, setSearch]   = useState("");
  const [filterSt, setFSt]    = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/offers/?page_size=50"); setOffers(d.results || d.data || d || []); } catch (_) { setOffers([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleSave = async (form) => {
    try {
      if (modal.mode === "create") { const d = await req("/offers/", { method: "POST", body: JSON.stringify(form) }); setOffers(x => [d, ...x]); toast("Offer created!"); }
      else { const d = await req(`/offers/${modal.item.id}/`, { method: "PATCH", body: JSON.stringify(form) }); setOffers(x => x.map(o => o.id === modal.item.id ? { ...o, ...d } : o)); toast("Offer updated!"); }
      setModal(null);
    } catch (e) { toast(e.message, "error"); }
  };

  const handleDelete = async () => {
    try { await req(`/offers/${delTarget.id}/`, { method: "DELETE" }); setOffers(x => x.filter(o => o.id !== delTarget.id)); toast("Offer deleted."); } catch (e) { toast(e.message, "error"); }
    setDel(null);
  };

  const filtered = offers.filter(o => {
    const q = search.toLowerCase();
    return (o.title?.toLowerCase().includes(q) || o.description?.toLowerCase().includes(q))
      && (filterSt === "all" || o.status === filterSt);
  });

  return (
    <>
      <div className="toolbar glass">
        <div className="toolbar__search"><span className="toolbar__search-icon">⌕</span><input className="toolbar__input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search offers…" /></div>
        <div className="toolbar__divider" />
        <div className="chip-group">
          {["all", "active", "paused", "expired"].map(s => (
            <button key={s} className={`chip${filterSt === s ? " chip--active" : ""}`} onClick={() => setFSt(s)}>{s.charAt(0).toUpperCase() + s.slice(1)}</button>
          ))}
        </div>
        <div style={{ marginLeft: "auto" }}><button className="btn btn--primary" onClick={() => setModal({ mode: "create", item: null })}>+ New Offer</button></div>
      </div>

      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Title</th><th>Network</th><th>Reward</th><th>Device</th><th>Status</th><th>Flags</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={8}><TabSpinner /></td></tr> : filtered.map((o, i) => (
              <tr key={o.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{o.title}</div><div className="net-name__type">{o.description?.slice(0, 40)}</div></td>
                <td><span className="td-sub">{o.ad_network_name || o.ad_network || "—"}</span></td>
                <td><div className="td-primary td-primary--bold">{o.reward_amount} {o.reward_type}</div></td>
                <td><span className="cat-badge">{o.device_type || "all"}</span></td>
                <td><span className={`badge ${o.status === "active" ? "badge--active" : o.status === "paused" ? "badge--paused" : "badge--testing"}`}>{o.status}</span></td>
                <td>
                  {o.is_featured && <span className="cat-badge" style={{ color: "#f59e0b", borderColor: "#f59e0b30", background: "#f59e0b10" }}>⭐ Featured</span>}
                  {o.is_hot && <span className="cat-badge" style={{ color: "#ef4444", borderColor: "#ef444430", background: "#ef444410", marginLeft: 4 }}>🔥 Hot</span>}
                </td>
                <td onClick={e => e.stopPropagation()}>
                  <div className="action-group">
                    <button className="action-btn action-btn--edit" onClick={() => setModal({ mode: "edit", item: o })}>✎</button>
                    <button className="action-btn action-btn--delete" onClick={() => setDel(o)}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && <EmptyState icon="🎯" text="No offers found." />}
      </div>
      <div className="table-footer">
        <span>Showing <strong>{filtered.length}</strong> of <strong>{offers.length}</strong> offers</span>
        <button className="btn btn--ghost" style={{ marginLeft: "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>

      {modal && (
        <div className="overlay" onClick={() => setModal(null)}>
          <div className="modal modal--wide glass" onClick={e => e.stopPropagation()}>
            <div className="modal__header">
              <div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode === "create" ? "New Offer" : "Edit Offer"}</div><div className="modal__title">🎯 {modal.mode === "create" ? "Create Offer" : modal.item?.title}</div></div></div>
              <button className="icon-btn" onClick={() => setModal(null)}>✕</button>
            </div>
            <OfferForm initial={modal.item} onSave={handleSave} onCancel={() => setModal(null)} />
          </div>
        </div>
      )}
      {delTarget && <ConfirmModal title="Delete Offer?" body={`"${delTarget.title}" will be removed.`} onConfirm={handleDelete} onCancel={() => setDel(null)} />}
    </>
  );
}

function OfferForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial || EMPTY_OFFER);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const submit = async () => { setSaving(true); try { await onSave(form); } finally { setSaving(false); } };
  return (
    <div className="modal__body"><div className="form-grid">
      <div className="form-row">
        <div className="field"><label className="field__label">Title *</label><input className="field__input" value={form.title || ""} onChange={e => set("title", e.target.value)} placeholder="Offer title" /></div>
        <div className="field"><label className="field__label">Reward Amount</label><input className="field__input" type="number" value={form.reward_amount || ""} onChange={e => set("reward_amount", e.target.value)} /></div>
      </div>
      <div className="form-row">
        <div className="field"><label className="field__label">Reward Type</label><select className="field__input field__select" value={form.reward_type || "POINTS"} onChange={e => set("reward_type", e.target.value)}>{["POINTS", "CASH", "GEMS", "COINS"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
        <div className="field"><label className="field__label">Device Type</label><select className="field__input field__select" value={form.device_type || "all"} onChange={e => set("device_type", e.target.value)}>{["all", "mobile", "desktop", "tablet"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>
      <div className="form-row">
        <div className="field"><label className="field__label">Status</label><select className="field__input field__select" value={form.status || "active"} onChange={e => set("status", e.target.value)}>{["active", "paused", "expired"].map(s => <option key={s} value={s}>{s}</option>)}</select></div>
        <div className="field"><label className="field__label">Ad Network ID</label><input className="field__input" value={form.ad_network || ""} onChange={e => set("ad_network", e.target.value)} placeholder="Network UUID" /></div>
      </div>
      <div className="field"><label className="field__label">Description</label><textarea className="field__input field__textarea" rows={3} value={form.description || ""} onChange={e => set("description", e.target.value)} /></div>
      <div className="form-row" style={{ gap: 16 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_featured} onChange={e => set("is_featured", e.target.checked)} /> ⭐ Featured</label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_hot} onChange={e => set("is_hot", e.target.checked)} /> 🔥 Hot</label>
      </div>
      <div className="modal__footer"><button className="btn btn--primary" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Save Offer"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
    </div></div>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: CONVERSIONS  ✅ FIX: "/conversions/" (new endpoint)
// ─────────────────────────────────────────────────────────────
function ConversionsTab({ toast }) {
  const [items, setItems]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [filterSt, setFSt]      = useState("all");
  const [search, setSearch]     = useState("");
  const [selected, setSelected] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await req("/conversions/?page_size=50" + (filterSt !== "all" ? `&conversion_status=${filterSt}` : ""));
      setItems(d.results || d.data || d || []);
    } catch (_) { setItems([]); }
    finally { setLoading(false); }
  }, [filterSt]);
  useEffect(() => { load(); }, [load]);

  const approve = async (id) => {
    try { await req(`/conversions/${id}/approve/`, { method: "POST" }); setItems(x => x.map(i => i.id === id ? { ...i, conversion_status: "approved" } : i)); toast("Approved!"); }
    catch (e) { toast(e.message, "error"); }
  };
  const reject = async (id) => {
    const r = prompt("Rejection reason:"); if (!r) return;
    try { await req(`/conversions/${id}/reject/`, { method: "POST", body: JSON.stringify({ rejection_reason: r }) }); setItems(x => x.map(i => i.id === id ? { ...i, conversion_status: "rejected" } : i)); toast("Rejected."); }
    catch (e) { toast(e.message, "error"); }
  };
  const bulkApprove = async () => {
    if (!selected.length) return;
    try { await req("/conversions/bulk_approve/", { method: "POST", body: JSON.stringify({ ids: selected }) }); setItems(x => x.map(i => selected.includes(i.id) ? { ...i, conversion_status: "approved" } : i)); setSelected([]); toast(`${selected.length} conversions approved!`); }
    catch (e) { toast(e.message, "error"); }
  };

  const filtered = items.filter(i => !search || (i.user?.toString() || "").includes(search) || (i.offer_title || "").toLowerCase().includes(search.toLowerCase()));
  const statusColor = { approved: "#10b981", pending: "#f59e0b", rejected: "#ef4444", chargeback: "#8b5cf6" };

  return (
    <>
      <div className="toolbar glass">
        <div className="toolbar__search"><span className="toolbar__search-icon">⌕</span><input className="toolbar__input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by user or offer…" /></div>
        <div className="toolbar__divider" />
        <div className="chip-group">
          {["all", "pending", "approved", "rejected", "chargeback"].map(s => (
            <button key={s} className={`chip${filterSt === s ? " chip--active" : ""}`} onClick={() => setFSt(s)}>{s.charAt(0).toUpperCase() + s.slice(1)}</button>
          ))}
        </div>
        {selected.length > 0 && <button className="btn btn--primary" style={{ marginLeft: "auto" }} onClick={bulkApprove}>✓ Bulk Approve ({selected.length})</button>}
        <button className="btn btn--ghost" style={{ marginLeft: selected.length ? "8px" : "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr>
            <th><input type="checkbox" onChange={e => setSelected(e.target.checked ? filtered.map(i => i.id) : [])} /></th>
            <th>#</th><th>User</th><th>Offer</th><th>Amount</th><th>Status</th><th>Risk</th><th>Date</th><th>Actions</th>
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={9}><TabSpinner /></td></tr> : filtered.map((c, i) => (
              <tr key={c.id} className="net-row">
                <td onClick={e => e.stopPropagation()}><input type="checkbox" checked={selected.includes(c.id)} onChange={e => setSelected(x => e.target.checked ? [...x, c.id] : x.filter(id => id !== c.id))} /></td>
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{c.user_name || c.user || "—"}</div></td>
                <td><div className="td-sub">{c.offer_title || c.offer || "—"}</div></td>
                <td><div className="td-primary td-primary--bold">{c.payout_amount || c.amount || "—"}</div></td>
                <td><span className="badge" style={{ background: `${statusColor[c.conversion_status] || "#64748b"}18`, color: statusColor[c.conversion_status] || "#64748b", border: `1px solid ${statusColor[c.conversion_status] || "#64748b"}30` }}>{c.conversion_status || "—"}</span></td>
                <td><span className="cat-badge" style={{ color: c.risk_level === "high" ? "#ef4444" : c.risk_level === "medium" ? "#f59e0b" : "#10b981" }}>{c.risk_level || "low"}</span></td>
                <td><div className="td-sub">{c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</div></td>
                <td onClick={e => e.stopPropagation()}>
                  <div className="action-group">
                    {c.conversion_status === "pending" && <>
                      <button className="action-btn action-btn--play" title="Approve" onClick={() => approve(c.id)}>✓</button>
                      <button className="action-btn action-btn--delete" title="Reject" onClick={() => reject(c.id)}>✕</button>
                    </>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && <EmptyState icon="💰" text="No conversions found." />}
      </div>
      <div className="table-footer"><span>Showing <strong>{filtered.length}</strong> of <strong>{items.length}</strong> conversions</span></div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: ENGAGEMENTS  ✅ path="/engagements/" — already correct
// ─────────────────────────────────────────────────────────────
function EngagementsTab({ toast }) {
  const [items, setItems]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterSt, setFSt]   = useState("all");
  const [search, setSearch]   = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/engagements/?page_size=50" + (filterSt !== "all" ? `&status=${filterSt}` : "")); setItems(d.results || d.data || d || []); } catch (_) { setItems([]); }
    finally { setLoading(false); }
  }, [filterSt]);
  useEffect(() => { load(); }, [load]);

  const approve = async (id) => { try { await req(`/engagements/${id}/complete/`, { method: "POST" }); setItems(x => x.map(i => i.id === id ? { ...i, status: "completed" } : i)); toast("Approved!"); } catch (e) { toast(e.message, "error"); } };
  const reject  = async (id) => { const r = prompt("Rejection reason:"); if (!r) return; try { await req(`/engagements/${id}/`, { method: "PATCH", body: JSON.stringify({ status: "rejected" }) }); setItems(x => x.map(i => i.id === id ? { ...i, status: "rejected" } : i)); toast("Rejected."); } catch (e) { toast(e.message, "error"); } };

  const filtered = items.filter(i => !search || i.user?.toString().includes(search) || (i.offer_title || "").toLowerCase().includes(search.toLowerCase()));
  const stColor = { approved: "#10b981", pending: "#f59e0b", rejected: "#ef4444", completed: "#6366f1" };

  return (
    <>
      <div className="toolbar glass">
        <div className="toolbar__search"><span className="toolbar__search-icon">⌕</span><input className="toolbar__input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search engagements…" /></div>
        <div className="toolbar__divider" />
        <div className="chip-group">
          {["all", "pending", "approved", "rejected", "completed"].map(s => (
            <button key={s} className={`chip${filterSt === s ? " chip--active" : ""}`} onClick={() => setFSt(s)}>{s.charAt(0).toUpperCase() + s.slice(1)}</button>
          ))}
        </div>
        <button className="btn btn--ghost" style={{ marginLeft: "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>User</th><th>Offer</th><th>Status</th><th>Started</th><th>Completed</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7}><TabSpinner /></td></tr> : filtered.map((e, i) => (
              <tr key={e.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{e.user_name || e.user || "—"}</div></td>
                <td><div className="td-sub">{e.offer_title || e.offer || "—"}</div></td>
                <td><span className="badge" style={{ background: `${stColor[e.status] || "#64748b"}18`, color: stColor[e.status] || "#64748b", border: `1px solid ${stColor[e.status] || "#64748b"}30` }}>{e.status || "—"}</span></td>
                <td><div className="td-sub">{e.created_at ? new Date(e.created_at).toLocaleDateString() : "—"}</div></td>
                <td><div className="td-sub">{e.completed_at ? new Date(e.completed_at).toLocaleDateString() : "—"}</div></td>
                <td onClick={ev => ev.stopPropagation()}>
                  <div className="action-group">
                    {e.status === "pending" && <>
                      <button className="action-btn action-btn--play" title="Approve" onClick={() => approve(e.id)}>✓</button>
                      <button className="action-btn action-btn--delete" title="Reject" onClick={() => reject(e.id)}>✕</button>
                    </>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && <EmptyState icon="👥" text="No engagements found." />}
      </div>
      <div className="table-footer"><span>Showing <strong>{filtered.length}</strong> of <strong>{items.length}</strong> engagements</span></div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: OFFER WALLS  ✅ FIX: "/walls/" → "/offerwalls/"
// ─────────────────────────────────────────────────────────────
function OfferWallsTab({ toast }) {
  const [walls, setWalls]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal]     = useState(null);
  const [delTarget, setDel]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    // ✅ FIX: "/offerwalls/" not "/walls/"
    try { const d = await req("/offerwalls/"); setWalls(d.results || d.data || d || []); } catch (_) { setWalls([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleSave = async (form) => {
    try {
      if (modal.mode === "create") { const d = await req("/offerwalls/", { method: "POST", body: JSON.stringify(form) }); setWalls(x => [d, ...x]); toast("Offer wall created!"); }
      else { const d = await req(`/offerwalls/${modal.item.id}/`, { method: "PATCH", body: JSON.stringify(form) }); setWalls(x => x.map(w => w.id === modal.item.id ? { ...w, ...d } : w)); toast("Updated!"); }
      setModal(null);
    } catch (e) { toast(e.message, "error"); }
  };
  const handleDelete = async () => {
    try { await req(`/offerwalls/${delTarget.id}/`, { method: "DELETE" }); setWalls(x => x.filter(w => w.id !== delTarget.id)); toast("Deleted."); } catch (e) { toast(e.message, "error"); }
    setDel(null);
  };

  return (
    <>
      <div className="toolbar glass">
        <div style={{ flex: 1, color: "rgba(200,200,255,0.5)", fontSize: 13 }}>Manage offer walls shown to users</div>
        <button className="btn btn--primary" onClick={() => setModal({ mode: "create", item: null })}>+ New Wall</button>
        <button className="btn btn--ghost" onClick={load}><span className={loading ? "spin" : ""}>⟳</span></button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Name</th><th>Type</th><th>Active</th><th>Default</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6}><TabSpinner /></td></tr> : walls.map((w, i) => (
              <tr key={w.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{w.name || w.title || "—"}</div></td>
                <td><span className="cat-badge">{w.wall_type || "—"}</span></td>
                <td><span className={`badge ${w.is_active ? "badge--active" : "badge--paused"}`}>{w.is_active ? "Active" : "Inactive"}</span></td>
                <td>{w.is_default && <span className="cat-badge" style={{ color: "#f59e0b" }}>⭐ Default</span>}</td>
                <td onClick={e => e.stopPropagation()}>
                  <div className="action-group">
                    <button className="action-btn action-btn--edit" onClick={() => setModal({ mode: "edit", item: w })}>✎</button>
                    <button className="action-btn action-btn--delete" onClick={() => setDel(w)}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && walls.length === 0 && <EmptyState icon="📱" text="No offer walls configured." />}
      </div>
      {modal && (
        <div className="overlay" onClick={() => setModal(null)}>
          <div className="modal glass" onClick={e => e.stopPropagation()}>
            <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode === "create" ? "New" : "Edit"} Offer Wall</div><div className="modal__title">📱 {modal.item?.name || "New Wall"}</div></div></div><button className="icon-btn" onClick={() => setModal(null)}>✕</button></div>
            <SimpleWallForm initial={modal.item} onSave={handleSave} onCancel={() => setModal(null)} />
          </div>
        </div>
      )}
      {delTarget && <ConfirmModal title="Delete Wall?" body={`"${delTarget.name}" will be removed.`} onConfirm={handleDelete} onCancel={() => setDel(null)} />}
    </>
  );
}

function SimpleWallForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial || { name: "", wall_type: "standard", is_active: true, is_default: false });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const submit = async () => { setSaving(true); try { await onSave(form); } finally { setSaving(false); } };
  return (
    <div className="modal__body"><div className="form-grid">
      <div className="field"><label className="field__label">Wall Name *</label><input className="field__input" value={form.name || ""} onChange={e => set("name", e.target.value)} /></div>
      <div className="field"><label className="field__label">Type</label><select className="field__input field__select" value={form.wall_type || "standard"} onChange={e => set("wall_type", e.target.value)}>{["standard", "premium", "vip", "mobile_only", "main", "survey", "video"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
      <div className="form-row" style={{ gap: 16 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_active} onChange={e => set("is_active", e.target.checked)} /> Active</label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_default} onChange={e => set("is_default", e.target.checked)} /> Set as Default</label>
      </div>
      <div className="modal__footer"><button className="btn btn--primary" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Save Wall"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
    </div></div>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: FRAUD RULES  ✅ path="/fraud-rules/" (new endpoint)
// ─────────────────────────────────────────────────────────────
function FraudTab({ toast }) {
  const [rules, setRules]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal]     = useState(null);
  const [delTarget, setDel]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/fraud-rules/"); setRules(d.results || d.data || d || []); } catch (_) { setRules([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleSave = async (form) => {
    try {
      if (modal.mode === "create") { const d = await req("/fraud-rules/", { method: "POST", body: JSON.stringify(form) }); setRules(x => [d, ...x]); toast("Rule created!"); }
      else { const d = await req(`/fraud-rules/${modal.item.id}/`, { method: "PATCH", body: JSON.stringify(form) }); setRules(x => x.map(r => r.id === modal.item.id ? { ...r, ...d } : r)); toast("Updated!"); }
      setModal(null);
    } catch (e) { toast(e.message, "error"); }
  };
  const handleDelete = async () => {
    try { await req(`/fraud-rules/${delTarget.id}/`, { method: "DELETE" }); setRules(x => x.filter(r => r.id !== delTarget.id)); toast("Rule deleted."); } catch (e) { toast(e.message, "error"); }
    setDel(null);
  };
  const sevColor = { low: "#10b981", medium: "#f59e0b", high: "#ef4444", critical: "#8b5cf6" };

  return (
    <>
      <div className="toolbar glass">
        <div style={{ flex: 1, color: "rgba(200,200,255,0.5)", fontSize: 13 }}>🛡️ Fraud Detection Rules</div>
        <button className="btn btn--primary" onClick={() => setModal({ mode: "create", item: null })}>+ New Rule</button>
        <button className="btn btn--ghost" onClick={load}><span className={loading ? "spin" : ""}>⟳</span></button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Rule Name</th><th>Type</th><th>Action</th><th>Severity</th><th>Active</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7}><TabSpinner /></td></tr> : rules.map((r, i) => (
              <tr key={r.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{r.name || "—"}</div></td>
                <td><span className="cat-badge">{r.rule_type || "—"}</span></td>
                <td><span className="cat-badge" style={{ color: "#6366f1" }}>{r.action || "—"}</span></td>
                <td><span className="badge" style={{ background: `${sevColor[r.severity] || "#64748b"}18`, color: sevColor[r.severity] || "#64748b", border: `1px solid ${sevColor[r.severity] || "#64748b"}30` }}>{r.severity || "—"}</span></td>
                <td><span className={`badge ${r.is_active ? "badge--active" : "badge--paused"}`}>{r.is_active ? "On" : "Off"}</span></td>
                <td onClick={e => e.stopPropagation()}>
                  <div className="action-group">
                    <button className="action-btn action-btn--edit" onClick={() => setModal({ mode: "edit", item: r })}>✎</button>
                    <button className="action-btn action-btn--delete" onClick={() => setDel(r)}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rules.length === 0 && <EmptyState icon="🛡️" text="No fraud rules configured." />}
      </div>
      {modal && (
        <div className="overlay" onClick={() => setModal(null)}>
          <div className="modal modal--wide glass" onClick={e => e.stopPropagation()}>
            <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode === "create" ? "New" : "Edit"} Fraud Rule</div><div className="modal__title">🛡️ {modal.item?.name || "New Rule"}</div></div></div><button className="icon-btn" onClick={() => setModal(null)}>✕</button></div>
            <FraudForm initial={modal.item} onSave={handleSave} onCancel={() => setModal(null)} />
          </div>
        </div>
      )}
      {delTarget && <ConfirmModal title="Delete Rule?" body={`"${delTarget.name}" will be removed.`} onConfirm={handleDelete} onCancel={() => setDel(null)} />}
    </>
  );
}

function FraudForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial || { name: "", rule_type: "velocity", action: "block", severity: "medium", is_active: true, description: "" });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const submit = async () => { setSaving(true); try { await onSave(form); } finally { setSaving(false); } };
  return (
    <div className="modal__body"><div className="form-grid">
      <div className="form-row">
        <div className="field"><label className="field__label">Rule Name *</label><input className="field__input" value={form.name || ""} onChange={e => set("name", e.target.value)} /></div>
        <div className="field"><label className="field__label">Rule Type</label><select className="field__input field__select" value={form.rule_type || "velocity"} onChange={e => set("rule_type", e.target.value)}>{["velocity", "device_fingerprint", "ip_reputation", "behavior", "geo_restriction", "time_based", "ip", "device", "pattern"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>
      <div className="form-row">
        <div className="field"><label className="field__label">Action</label><select className="field__input field__select" value={form.action || "block"} onChange={e => set("action", e.target.value)}>{["block", "flag", "review", "allow", "rate_limit"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
        <div className="field"><label className="field__label">Severity</label><select className="field__input field__select" value={form.severity || "medium"} onChange={e => set("severity", e.target.value)}>{["low", "medium", "high", "critical"].map(t => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>
      <div className="field"><label className="field__label">Description</label><textarea className="field__input field__textarea" rows={2} value={form.description || ""} onChange={e => set("description", e.target.value)} /></div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_active} onChange={e => set("is_active", e.target.checked)} /> Rule Active</label>
      <div className="modal__footer"><button className="btn btn--primary" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Save Rule"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
    </div></div>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: BLACKLIST IPs  ✅ path="/blacklisted-ips/" (new endpoint)
// ─────────────────────────────────────────────────────────────
function BlacklistTab({ toast }) {
  const [ips, setIPs]           = useState([]);
  const [loading, setLoading]   = useState(true);
  const [modal, setModal]       = useState(null);
  const [delTarget, setDel]     = useState(null);
  const [checkIP, setCheckIP]   = useState("");
  const [checkResult, setCheckResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/blacklisted-ips/"); setIPs(d.results || d.data || d || []); } catch (_) { setIPs([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleSave = async (form) => {
    try {
      if (modal.mode === "create") { const d = await req("/blacklisted-ips/", { method: "POST", body: JSON.stringify(form) }); setIPs(x => [d, ...x]); toast("IP blacklisted!"); }
      else { const d = await req(`/blacklisted-ips/${modal.item.id}/`, { method: "PATCH", body: JSON.stringify(form) }); setIPs(x => x.map(i => i.id === modal.item.id ? { ...i, ...d } : i)); toast("Updated!"); }
      setModal(null);
    } catch (e) { toast(e.message, "error"); }
  };
  const handleDelete = async () => {
    try { await req(`/blacklisted-ips/${delTarget.id}/`, { method: "DELETE" }); setIPs(x => x.filter(i => i.id !== delTarget.id)); toast("Removed."); } catch (e) { toast(e.message, "error"); }
    setDel(null);
  };
  const handleCheck = async () => {
    if (!checkIP.trim()) return;
    try { const d = await req("/blacklisted-ips/check/", { method: "POST", body: JSON.stringify({ ip_address: checkIP }) }); setCheckResult(d); }
    catch (e) { toast(e.message, "error"); }
  };
  const handleCleanup = async () => {
    try { await req("/blacklisted-ips/cleanup/", { method: "POST", body: JSON.stringify({ batch_size: 1000 }) }); toast("Cleanup complete!"); load(); }
    catch (e) { toast(e.message, "error"); }
  };

  return (
    <>
      <div className="toolbar glass" style={{ flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", gap: 8, flex: 1, minWidth: 280 }}>
          <input className="toolbar__input" style={{ flex: 1, border: "1px solid rgba(100,60,200,0.2)", borderRadius: 6, padding: "6px 12px", background: "rgba(20,10,40,0.5)", color: "#c8b8ff" }} value={checkIP} onChange={e => setCheckIP(e.target.value)} placeholder="Check IP address…" onKeyDown={e => e.key === "Enter" && handleCheck()} />
          <button className="btn btn--ghost" onClick={handleCheck}>🔍 Check</button>
        </div>
        {checkResult && <div style={{ padding: "4px 12px", borderRadius: 6, fontSize: 12, background: checkResult.is_blacklisted ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.15)", color: checkResult.is_blacklisted ? "#ef4444" : "#10b981", border: `1px solid ${checkResult.is_blacklisted ? "#ef444430" : "#10b98130"}` }}>{checkResult.is_blacklisted ? "🚫 Blacklisted" : "✅ Clean"}</div>}
        <button className="btn btn--ghost" onClick={handleCleanup}>🧹 Cleanup Expired</button>
        <button className="btn btn--primary" onClick={() => setModal({ mode: "create", item: null })}>+ Block IP</button>
        <button className="btn btn--ghost" onClick={load}><span className={loading ? "spin" : ""}>⟳</span></button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>IP Address</th><th>Reason</th><th>Active</th><th>Expires</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6}><TabSpinner /></td></tr> : ips.map((ip, i) => (
              <tr key={ip.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title" style={{ fontFamily: "monospace" }}>{ip.ip_address}</div></td>
                <td><div className="td-sub">{ip.reason || "—"}</div></td>
                <td><span className={`badge ${ip.is_active ? "badge--paused" : "badge--active"}`}>{ip.is_active ? "Blocked" : "Inactive"}</span></td>
                <td><div className="td-sub">{ip.expiry_date ? new Date(ip.expiry_date).toLocaleDateString() : "Never"}</div></td>
                <td onClick={e => e.stopPropagation()}>
                  <div className="action-group">
                    <button className="action-btn action-btn--edit" onClick={() => setModal({ mode: "edit", item: ip })}>✎</button>
                    <button className="action-btn action-btn--delete" onClick={() => setDel(ip)}>🗑</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && ips.length === 0 && <EmptyState icon="🚫" text="No blacklisted IPs." />}
      </div>
      {modal && (
        <div className="overlay" onClick={() => setModal(null)}>
          <div className="modal glass" onClick={e => e.stopPropagation()}>
            <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode === "create" ? "Block New" : "Edit"} IP</div><div className="modal__title">🚫 {modal.item?.ip_address || "New IP"}</div></div></div><button className="icon-btn" onClick={() => setModal(null)}>✕</button></div>
            <IPForm initial={modal.item} onSave={handleSave} onCancel={() => setModal(null)} />
          </div>
        </div>
      )}
      {delTarget && <ConfirmModal title="Remove IP?" body={`"${delTarget.ip_address}" will be unblocked.`} onConfirm={handleDelete} onCancel={() => setDel(null)} />}
    </>
  );
}

function IPForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial || { ip_address: "", reason: "manual", expiry_date: "", is_active: true });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const submit = async () => { setSaving(true); try { await onSave(form); } finally { setSaving(false); } };
  return (
    <div className="modal__body"><div className="form-grid">
      <div className="field"><label className="field__label">IP Address *</label><input className="field__input" style={{ fontFamily: "monospace" }} value={form.ip_address || ""} onChange={e => set("ip_address", e.target.value)} placeholder="192.168.1.1" /></div>
      <div className="field"><label className="field__label">Reason</label>
        <select className="field__input field__select" value={form.reason || "manual"} onChange={e => set("reason", e.target.value)}>
          {["fraud", "bot", "vpn", "datacenter", "abuse", "manual", "test"].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      <div className="field"><label className="field__label">Expiry Date (optional)</label><input className="field__input" type="date" value={form.expiry_date || ""} onChange={e => set("expiry_date", e.target.value)} /></div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "rgba(200,200,255,0.7)" }}><input type="checkbox" checked={!!form.is_active} onChange={e => set("is_active", e.target.checked)} /> Active Block</label>
      <div className="modal__footer"><button className="btn btn--danger" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Block IP"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
    </div></div>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: WEBHOOKS  ✅ path="/webhooks/" — correct (webhooks/urls.py registered)
// ─────────────────────────────────────────────────────────────
function WebhooksTab({ toast }) {
  const [logs, setLogs]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterN, setFN]      = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/webhooks/?page_size=50"); setLogs(d.results || d.data || d || []); } catch (_) { setLogs([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const reprocess = async (id) => {
    try { await req(`/webhooks/${id}/reprocess/`, { method: "POST" }); toast("Reprocessed!"); load(); }
    catch (e) { toast(e.message, "error"); }
  };

  const networks = [...new Set(logs.map(l => l.ad_network_name || l.ad_network).filter(Boolean))];

  return (
    <>
      <div className="toolbar glass">
        <div className="chip-group">
          <button className={`chip${filterN === "all" ? " chip--active" : ""}`} onClick={() => setFN("all")}>All Networks</button>
          {networks.map(n => <button key={n} className={`chip${filterN === n ? " chip--active" : ""}`} onClick={() => setFN(n)}>{n}</button>)}
        </div>
        <button className="btn btn--ghost" style={{ marginLeft: "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Network</th><th>Event</th><th>Valid Sig</th><th>Processed</th><th>Date</th><th>Actions</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7}><TabSpinner /></td></tr> : logs.filter(l => filterN === "all" || (l.ad_network_name || l.ad_network) === filterN).map((l, i) => (
              <tr key={l.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{l.ad_network_name || l.ad_network || "—"}</div></td>
                <td><span className="cat-badge">{l.event_type || "—"}</span></td>
                <td>{l.is_valid_signature ? <span style={{ color: "#10b981" }}>✓ Valid</span> : <span style={{ color: "#ef4444" }}>✕ Invalid</span>}</td>
                <td>{(l.processed || l.is_processed) ? <span className="badge badge--active">Done</span> : <span className="badge badge--paused">Pending</span>}</td>
                <td><div className="td-sub">{l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</div></td>
                <td onClick={e => e.stopPropagation()}>
                  {!(l.processed || l.is_processed) && <button className="action-btn action-btn--edit" title="Reprocess" onClick={() => reprocess(l.id)}>⟳</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && logs.length === 0 && <EmptyState icon="🔗" text="No webhook logs found." />}
      </div>
      <div className="table-footer"><span>{logs.length} webhook events</span></div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// TAB: SYNC LOGS  ✅ path="/sync-logs/" (new endpoint)
// ─────────────────────────────────────────────────────────────
function SyncLogsTab({ toast }) {
  const [logs, setLogs]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterSt, setFSt]    = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await req("/sync-logs/?page_size=50" + (filterSt !== "all" ? `&status=${filterSt}` : "")); setLogs(d.results || d.data || d || []); } catch (_) { setLogs([]); }
    finally { setLoading(false); }
  }, [filterSt]);
  useEffect(() => { load(); }, [load]);

  const stColor = { success: "#10b981", failed: "#ef4444", in_progress: "#f59e0b", pending: "#6366f1", partial: "#06b6d4" };

  return (
    <>
      <div className="toolbar glass">
        <div className="chip-group">
          {["all", "success", "partial", "failed"].map(s => (
            <button key={s} className={`chip${filterSt === s ? " chip--active" : ""}`} onClick={() => setFSt(s)}>{s.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase())}</button>
          ))}
        </div>
        <button className="btn btn--ghost" style={{ marginLeft: "auto" }} onClick={load}><span className={loading ? "spin" : ""}>⟳</span> Refresh</button>
      </div>
      <div className="table-wrap glass">
        <table className="net-table">
          <thead><tr><th>#</th><th>Network</th><th>Status</th><th>Fetched</th><th>Added</th><th>Updated</th><th>Date</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7}><TabSpinner /></td></tr> : logs.map((l, i) => (
              <tr key={l.id} className="net-row">
                <td className="td-num">{String(i + 1).padStart(2, "0")}</td>
                <td><div className="net-name__title">{l.ad_network_name || l.ad_network || "—"}</div></td>
                <td><span className="badge" style={{ background: `${stColor[l.status] || "#64748b"}18`, color: stColor[l.status] || "#64748b", border: `1px solid ${stColor[l.status] || "#64748b"}30` }}>{l.status || "—"}</span></td>
                <td><div className="td-primary">{l.offers_fetched ?? "—"}</div></td>
                <td><div className="td-primary" style={{ color: "#10b981" }}>{l.offers_added ?? "—"}</div></td>
                <td><div className="td-primary" style={{ color: "#f59e0b" }}>{l.offers_updated ?? "—"}</div></td>
                <td><div className="td-sub">{l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && logs.length === 0 && <EmptyState icon="🔄" text="No sync logs found." />}
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────
export default function AdNetworks() {
  const [activeTab, setActiveTab] = useState("networks");
  const [toasts, setToasts]       = useState([]);

  const toast = useCallback((message, type = "success") => {
    const id = Date.now();
    setToasts(p => [...p, { id, message, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500);
  }, []);

  const renderTab = () => {
    switch (activeTab) {
      case "networks":    return <NetworksTab    toast={toast} />;
      case "offers":      return <OffersTab      toast={toast} />;
      case "conversions": return <ConversionsTab toast={toast} />;
      case "engagements": return <EngagementsTab toast={toast} />;
      case "offerwalls":  return <OfferWallsTab  toast={toast} />;
      case "fraud":       return <FraudTab       toast={toast} />;
      case "blacklist":   return <BlacklistTab   toast={toast} />;
      case "webhooks":    return <WebhooksTab    toast={toast} />;
      case "synclogs":    return <SyncLogsTab    toast={toast} />;
      default:            return null;
    }
  };

  return (
    <div className="an-root">
      <div className="orb orb--1" /><div className="orb orb--2" /><div className="orb orb--3" />
      <div className="an-container">
        <header className="page-header">
          <div className="page-header__left">
            <div className="page-header__eyebrow">Ad Network Management</div>
            <h1 className="page-header__title">Networks</h1>
          </div>
        </header>
        <div className="an-tabs glass">
          {TABS.map(t => (
            <button key={t.id} className={`an-tab${activeTab === t.id ? " an-tab--active" : ""}`} onClick={() => setActiveTab(t.id)}>
              <span className="an-tab__icon">{t.icon}</span>
              <span className="an-tab__label">{t.label}</span>
            </button>
          ))}
        </div>
        <div className="an-tab-content">{renderTab()}</div>
      </div>
      <Toast toasts={toasts} />
    </div>
  );
}



// import { useState, useEffect, useCallback } from "react";
// import "../styles/AdNetworks.css";

// // ─────────────────────────────────────────────────────────────
// // AUTH
// // ─────────────────────────────────────────────────────────────
// const getToken = () =>
//   localStorage.getItem("adminAccessToken") ||
//   localStorage.getItem("access_token") || "";

// const BASE = "/api/ad-networks";

// async function req(path, opts = {}) {
//   const res = await fetch(`${BASE}${path}`, {
//     ...opts,
//     headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}`, ...opts.headers },
//   });
//   if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail||e.message||`HTTP ${res.status}`); }
//   return res.status === 204 ? null : res.json();
// }

// // ─────────────────────────────────────────────────────────────
// // CONSTANTS
// // ─────────────────────────────────────────────────────────────
// const CAT_META = {
//   offerwall:   { icon:"📱", label:"Offerwall",   color:"#6366f1" },
//   survey:      { icon:"📋", label:"Survey",       color:"#8b5cf6" },
//   video:       { icon:"🎬", label:"Video",         color:"#ec4899" },
//   gaming:      { icon:"🎮", label:"Gaming",        color:"#f59e0b" },
//   app_install: { icon:"📲", label:"App Install",   color:"#10b981" },
//   cashback:    { icon:"💸", label:"Cashback",      color:"#06b6d4" },
//   cpi_cpa:     { icon:"📊", label:"CPI/CPA",       color:"#f97316" },
//   other:       { icon:"📦", label:"Other",          color:"#94a3b8" },
// };

// const TABS = [
//   { id:"networks",     icon:"🌐", label:"Networks"     },
//   { id:"offers",       icon:"🎯", label:"Offers"        },
//   { id:"conversions",  icon:"💰", label:"Conversions"   },
//   { id:"engagements",  icon:"👥", label:"Engagements"   },
//   { id:"offerwalls",   icon:"📱", label:"Offer Walls"   },
//   { id:"fraud",        icon:"🛡️", label:"Fraud Rules"   },
//   { id:"blacklist",    icon:"🚫", label:"Blacklist IPs" },
//   { id:"webhooks",     icon:"🔗", label:"Webhooks"      },
//   { id:"synclogs",     icon:"🔄", label:"Sync Logs"     },
// ];

// // ─────────────────────────────────────────────────────────────
// // TOAST
// // ─────────────────────────────────────────────────────────────
// function Toast({ toasts }) {
//   return (
//     <div className="toast-container">
//       {toasts.map(t => (
//         <div key={t.id} className={`toast toast--${t.type}`}>
//           <span className="toast__icon">{t.type==="success"?"✓":t.type==="error"?"✕":"ℹ"}</span>
//           {t.message}
//         </div>
//       ))}
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // SHARED SUB-COMPONENTS
// // ─────────────────────────────────────────────────────────────
// function StatCard({ icon, label, value, sub, accent }) {
//   return (
//     <div className="stat-card" style={{"--accent":accent}}>
//       <div className="stat-card__icon">{icon}</div>
//       <div className="stat-card__body">
//         <div className="stat-card__value">{value}</div>
//         <div className="stat-card__label">{label}</div>
//         <div className="stat-card__sub">{sub}</div>
//       </div>
//       <div className="stat-card__glow"/>
//     </div>
//   );
// }

// function StatusBadge({ network }) {
//   const active = network.is_active;
//   const s = network.status || "active";
//   const label = !active ? "Paused" : s==="testing" ? "Testing" : "Active";
//   const cls   = !active ? "badge--paused" : s==="testing" ? "badge--testing" : "badge--active";
//   return <span className={`badge ${cls}`}>{label}</span>;
// }

// function TrustBar({ value }) {
//   const color = value>=90?"#10b981":value>=75?"#f59e0b":"#ef4444";
//   return (
//     <div className="trust">
//       <span className="trust__val" style={{color}}>{value}%</span>
//       <div className="trust__bar"><div className="trust__fill" style={{width:`${value}%`,background:color}}/></div>
//     </div>
//   );
// }

// function EmptyState({ icon="🔍", text="No data found." }) {
//   return (
//     <div className="empty-state">
//       <span style={{fontSize:32}}>{icon}</span>
//       <p>{text}</p>
//     </div>
//   );
// }

// function TabSpinner() {
//   return <div className="empty-state"><span className="spin" style={{fontSize:28}}>⟳</span><p>Loading…</p></div>;
// }

// // ─────────────────────────────────────────────────────────────
// // GENERIC CONFIRM MODAL
// // ─────────────────────────────────────────────────────────────
// function ConfirmModal({ title, body, onConfirm, onCancel, danger=true }) {
//   return (
//     <div className="overlay" onClick={onCancel}>
//       <div className="confirm-card glass" onClick={e=>e.stopPropagation()}>
//         <div className="confirm-card__icon">{danger?"🗑️":"⚠️"}</div>
//         <h3 className="confirm-card__title">{title}</h3>
//         <p className="confirm-card__body">{body}</p>
//         <div className="confirm-card__actions">
//           <button className={`btn ${danger?"btn--danger":"btn--primary"}`} onClick={onConfirm}>Confirm</button>
//           <button className="btn btn--ghost" onClick={onCancel}>Cancel</button>
//         </div>
//       </div>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // NETWORK MODAL (existing — kept intact)
// // ─────────────────────────────────────────────────────────────
// const EMPTY_NET = { name:"", network_type:"", category:"offerwall", api_key:"", api_secret:"", publisher_id:"", base_url:"", country_support:"global", priority:5, rating:"", description:"" };

// function NetworkModal({ mode, network, onClose, onSave }) {
//   const isView=mode==="view", isEdit=mode==="edit", isCreate=mode==="create";
//   const [form, setForm] = useState(()=> isCreate ? EMPTY_NET : {
//     name:network.name||"", network_type:network.network_type||"", category:network.category||"offerwall",
//     api_key:"", api_secret:"", publisher_id:network.publisher_id||"", base_url:network.base_url||"",
//     country_support:network.country_support||"global", priority:network.priority||5, rating:network.rating||"", description:network.description||"",
//   });
//   const [saving,setSaving]=useState(false);
//   const [errors,setErrors]=useState({});
//   const meta = CAT_META[network?.category||form.category]||CAT_META.other;

//   const validate=()=>{ const e={}; if(!form.name.trim())e.name="Required"; if(!form.network_type.trim())e.network_type="Required"; if(form.priority<1||form.priority>10)e.priority="1–10"; setErrors(e); return!Object.keys(e).length; };
//   const submit=async()=>{ if(!validate())return; setSaving(true); try{ const p={...form}; if(!p.api_key)delete p.api_key; if(!p.api_secret)delete p.api_secret; await onSave(p); }finally{setSaving(false);} };

//   const F=({label,field,type="text",options,placeholder,error})=>(
//     <div className="field">
//       <label className="field__label">{label}</label>
//       {options
//         ? <select className={`field__input field__select${error?" field__input--error":""}`} value={form[field]} onChange={e=>setForm(p=>({...p,[field]:e.target.value}))}>
//             {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
//           </select>
//         : <input type={type} className={`field__input${error?" field__input--error":""}`} value={form[field]}
//             onChange={e=>setForm(p=>({...p,[field]:type==="number"?Number(e.target.value):e.target.value}))}
//             placeholder={placeholder||`Enter ${label.toLowerCase()}…`}/>}
//       {error&&<span className="field__error">{error}</span>}
//     </div>
//   );

//   return (
//     <div className="overlay" onClick={onClose}>
//       <div className={`modal glass${isCreate||isEdit?" modal--wide":""}`} onClick={e=>e.stopPropagation()}>
//         <div className="modal__header">
//           <div className="modal__header-left">
//             {isView&&<div className="modal__avatar" style={{background:`${meta.color}18`,color:meta.color}}>{meta.icon}</div>}
//             <div>
//               <div className="modal__subtitle">{isCreate?"New Configuration":isEdit?"Edit Configuration":"Network Details"}</div>
//               <div className="modal__title">{isView?network.name:isEdit?`Edit · ${network.name}`:"Deploy Network"}</div>
//             </div>
//           </div>
//           <div className="modal__header-right">
//             {isView&&<StatusBadge network={network}/>}
//             <button className="icon-btn" onClick={onClose}>✕</button>
//           </div>
//         </div>
//         <div className="modal__body">
//           {isView?(
//             <div className="detail-grid">
//               {[["Network ID",`#${String(network.id).padStart(4,"0")}`],["Type",network.network_type?.toUpperCase()],["Category",`${meta.icon} ${meta.label}`],["Priority",`${network.priority}/10`],["Rating",`${network.rating}/5.0`],["Conversions",(network.total_conversions||0).toLocaleString()],["Total Payout",`$${(network.total_payout||0).toLocaleString()}`],["Conv. Rate",`${network.conversion_rate}%`],["Country",network.country_support?.toUpperCase()],["Description",network.description||"—"]].map(([lbl,val])=>(
//                 <div className="detail-item glass-inner" key={lbl}>
//                   <div className="detail-item__label">{lbl}</div>
//                   <div className="detail-item__value">{val}</div>
//                 </div>
//               ))}
//               <div className="detail-item detail-item--full glass-inner">
//                 <div className="detail-item__label">Trust Score</div>
//                 <TrustBar value={network.trust_score}/>
//               </div>
//             </div>
//           ):(
//             <div className="form-grid">
//               <div className="form-row">
//                 <F label="Network Name *" field="name" error={errors.name} placeholder="e.g. Google AdMob"/>
//                 <F label="Network Type *" field="network_type" error={errors.network_type} placeholder="e.g. admob"/>
//               </div>
//               <div className="form-row">
//                 <F label="Category" field="category" options={Object.entries(CAT_META).map(([v,m])=>({value:v,label:`${m.icon} ${m.label}`}))}/>
//                 <F label="Country Support" field="country_support" options={[{value:"global",label:"🌐 Global"},{value:"tier1",label:"🇺🇸 Tier 1"},{value:"tier2",label:"🌍 Tier 2"},{value:"tier3",label:"🌏 Tier 3"}]}/>
//               </div>
//               <div className="cred-section glass-inner">
//                 <div className="cred-section__title">🔐 Credentials <span>(encrypted)</span></div>
//                 <div className="form-row">
//                   <F label={isEdit?"API Key (blank=keep)":"API Key"} field="api_key" type="password" placeholder="••••••••••••"/>
//                   <F label={isEdit?"API Secret (blank=keep)":"API Secret"} field="api_secret" type="password" placeholder="••••••••••••"/>
//                 </div>
//                 <div className="form-row">
//                   <F label="Publisher ID" field="publisher_id" placeholder="pub-xxxxxxxxxx"/>
//                   <F label="Base URL" field="base_url" placeholder="https://api.network.com/v1"/>
//                 </div>
//               </div>
//               <div className="form-row">
//                 <F label="Priority (1–10)" field="priority" type="number" error={errors.priority}/>
//                 <F label="Rating (0–5)" field="rating" type="number" placeholder="4.5"/>
//               </div>
//               <div className="field">
//                 <label className="field__label">Description</label>
//                 <textarea className="field__input field__textarea" value={form.description} onChange={e=>setForm(p=>({...p,description:e.target.value}))} rows={3} placeholder="Short description…"/>
//               </div>
//               <div className="modal__footer">
//                 <button className="btn btn--primary" onClick={submit} disabled={saving}>
//                   {saving&&<span className="spin" style={{marginRight:6}}>⟳</span>}
//                   {saving?"Saving…":isEdit?"Update Network":"Deploy Network"}
//                 </button>
//                 <button className="btn btn--ghost" onClick={onClose}>Cancel</button>
//               </div>
//             </div>
//           )}
//         </div>
//       </div>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: NETWORKS (existing)
// // ─────────────────────────────────────────────────────────────
// function NetworksTab({ toast }) {
//   const [networks,setNetworks] = useState([]);
//   const [loading,setLoading]   = useState(true);
//   const [summary,setSummary]   = useState(null);
//   const [modal,setModal]       = useState(null);
//   const [delTarget,setDel]     = useState(null);
//   const [search,setSearch]     = useState("");
//   const [filterCat,setFCat]    = useState("all");
//   const [filterSt,setFSt]      = useState("all");
//   const [syncingId,setSyncId]  = useState(null);
//   const [toggling,setToggle]   = useState(null);

//   const load = useCallback(async()=>{
//     setLoading(true);
//     try {
//       const token=getToken();
//       const r = await fetch("/api/ad-networks/ad-networks/",{headers:{Authorization:`Bearer ${token}`}});
//       if(r.ok){ const d=await r.json(); const list=d.data||d.results||[]; if(list.length)setNetworks(list); }
//       try{ const sr=await fetch(`${BASE}/manage/summary/`,{headers:{Authorization:`Bearer ${token}`}}); if(sr.ok){const s=await sr.json();setSummary(s.data||s);} }catch(_){}
//     }catch(_){}
//     finally{setLoading(false);}
//   },[]);
//   useEffect(()=>{load();},[load]);

//   const handleCreate=async(p)=>{ try{ const d=await req("/manage/",{method:"POST",body:JSON.stringify(p)}); setNetworks(x=>[d?.data||d,...x]); setModal(null); toast("Network created!"); }catch(_){ setNetworks(x=>[{id:Date.now(),...p,is_active:true,status:"active",trust_score:85,total_conversions:0,total_payout:0,conversion_rate:0},...x]); setModal(null); toast("Created (offline)","info"); } };
//   const handleUpdate=async(id,p)=>{ try{ const d=await req(`/manage/${id}/`,{method:"PATCH",body:JSON.stringify(p)}); setNetworks(x=>x.map(n=>n.id===id?{...n,...(d?.data||d)}:n)); setModal(null); toast("Network updated!"); }catch(_){ setNetworks(x=>x.map(n=>n.id===id?{...n,...p}:n)); setModal(null); toast("Updated (offline)","info"); } };
//   const handleDelete=async(n)=>{ try{ await req(`/manage/${n.id}/`,{method:"DELETE"}); }catch(_){} setNetworks(x=>x.filter(i=>i.id!==n.id)); setDel(null); toast(`"${n.name}" deleted.`); };
//   const handleToggle=async(n)=>{ setToggle(n.id); try{ await req(`/manage/${n.id}/toggle_status/`,{method:"POST"}); }catch(_){} setNetworks(x=>x.map(i=>i.id===n.id?{...i,is_active:!i.is_active,status:!i.is_active?"active":"paused"}:i)); toast(`${n.name} ${n.is_active?"paused":"activated"}!`); setToggle(null); };
//   const handleSync=async(id)=>{ setSyncId(id); try{ await req(`/manage/${id}/sync/`,{method:"POST"}); toast("Sync complete!"); }catch(_){ toast("Synced (offline)","info"); } setSyncId(null); };

//   const filtered=networks.filter(n=>{
//     const q=search.toLowerCase();
//     return (n.name?.toLowerCase().includes(q)||n.network_type?.includes(q))
//       &&(filterCat==="all"||n.category===filterCat)
//       &&(filterSt==="all"||(n.is_active?(n.status||"active"):"paused")===filterSt);
//   });
//   const totalN=summary?.totals?.total||networks.length;
//   const activeN=summary?.totals?.active||networks.filter(n=>n.is_active).length;
//   const totalP=summary?.financials?.total_payout||networks.reduce((a,n)=>a+(n.total_payout||0),0);
//   const totalC=summary?.financials?.total_conversions||networks.reduce((a,n)=>a+(n.total_conversions||0),0);

//   return (
//     <>
//       <div className="stats-grid">
//         <StatCard icon="🌐" label="Total Networks"  value={totalN.toLocaleString()} sub={`${activeN} operational`} accent="#6366f1"/>
//         <StatCard icon="⚡" label="Active Networks" value={activeN.toLocaleString()} sub={`${((activeN/totalN)*100||0).toFixed(1)}% uptime`} accent="#10b981"/>
//         <StatCard icon="💰" label="Total Payouts"   value={`$${(totalP/1000).toFixed(1)}k`} sub="All-time" accent="#f59e0b"/>
//         <StatCard icon="🎯" label="Conversions"     value={totalC.toLocaleString()} sub="All-time" accent="#ec4899"/>
//       </div>

//       <div className="toolbar glass">
//         <div className="toolbar__search">
//           <span className="toolbar__search-icon">⌕</span>
//           <input className="toolbar__input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search networks…"/>
//         </div>
//         <div className="toolbar__divider"/>
//         <div className="chip-group">
//           {["all","offerwall","survey","video","gaming","app_install"].map(c=>(
//             <button key={c} className={`chip${filterCat===c?" chip--active":""}`} onClick={()=>setFCat(c)}>
//               {c==="all"?"All":CAT_META[c]?.label||c}
//             </button>
//           ))}
//         </div>
//         <div className="toolbar__divider"/>
//         <div className="chip-group">
//           {[{v:"all",label:"All",dot:null},{v:"active",label:"Active",dot:"#10b981"},{v:"testing",label:"Testing",dot:"#f59e0b"},{v:"paused",label:"Paused",dot:"#ef4444"}].map(({v,label,dot})=>(
//             <button key={v} className={`chip${filterSt===v?" chip--active":""}`} onClick={()=>setFSt(v)}>
//               {dot&&<span className="chip__dot" style={{background:dot}}/>}{label}
//             </button>
//           ))}
//         </div>
//         <div style={{marginLeft:"auto"}}>
//           <button className="btn btn--primary" onClick={()=>setModal({mode:"create"})}>+ Deploy Network</button>
//         </div>
//       </div>

//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Network</th><th>Category</th><th>Status</th><th>Trust</th><th>Rating</th><th>Conversions</th><th>Payout</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={9}><TabSpinner/></td></tr>:filtered.map((n,i)=>{
//               const meta=CAT_META[n.category]||CAT_META.other;
//               return (
//                 <tr key={n.id} className="net-row" onClick={()=>setModal({mode:"view",network:n})}>
//                   <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                   <td><div className="net-name"><div className="net-name__avatar" style={{background:`${meta.color}18`,color:meta.color}}>{meta.icon}</div><div><div className="net-name__title">{n.name}</div><div className="net-name__type">{n.network_type?.toUpperCase()}</div></div></div></td>
//                   <td><span className="cat-badge" style={{background:`${meta.color}14`,color:meta.color,borderColor:`${meta.color}30`}}>{meta.icon} {meta.label}</span></td>
//                   <td><StatusBadge network={n}/></td>
//                   <td><TrustBar value={n.trust_score||0}/></td>
//                   <td><div className="rating"><span className="rating__stars">{"★".repeat(Math.round(n.rating||0))}<span className="rating__empty">{"★".repeat(5-Math.round(n.rating||0))}</span></span><span className="rating__num">{n.rating}</span></div></td>
//                   <td><div className="td-primary">{(n.total_conversions||0).toLocaleString()}</div><div className="td-sub">CR: {n.conversion_rate}%</div></td>
//                   <td><div className="td-primary td-primary--bold">${(n.total_payout||0).toLocaleString()}</div></td>
//                   <td onClick={e=>e.stopPropagation()}>
//                     <div className="action-group">
//                       <button className="action-btn" title="Sync" onClick={()=>handleSync(n.id)}><span className={syncingId===n.id?"spin":""}>⟳</span></button>
//                       <button className="action-btn action-btn--edit" title="Edit" onClick={()=>setModal({mode:"edit",network:n})}>✎</button>
//                       <button className={`action-btn ${n.is_active?"action-btn--pause":"action-btn--play"}`} onClick={()=>handleToggle(n)}>
//                         {toggling===n.id?<span className="spin">⟳</span>:(n.is_active?"⏸":"▶")}
//                       </button>
//                       <button className="action-btn action-btn--delete" title="Delete" onClick={()=>setDel(n)}>🗑</button>
//                     </div>
//                   </td>
//                 </tr>
//               );
//             })}
//           </tbody>
//         </table>
//         {!loading&&filtered.length===0&&<EmptyState text="No networks match your filters."/>}
//       </div>
//       <div className="table-footer">
//         <span>Showing <strong>{filtered.length}</strong> of <strong>{networks.length}</strong> networks</span>
//         <button className="btn btn--ghost" style={{marginLeft:"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>

//       {modal?.mode==="view"   && <NetworkModal mode="view"   network={modal.network} onClose={()=>setModal(null)} onSave={()=>{}}/>}
//       {modal?.mode==="edit"   && <NetworkModal mode="edit"   network={modal.network} onClose={()=>setModal(null)} onSave={p=>handleUpdate(modal.network.id,p)}/>}
//       {modal?.mode==="create" && <NetworkModal mode="create" network={null}          onClose={()=>setModal(null)} onSave={handleCreate}/>}
//       {delTarget && <ConfirmModal title="Delete Network?" body={`"${delTarget.name}" will be removed.`} onConfirm={()=>handleDelete(delTarget)} onCancel={()=>setDel(null)}/>}
//     </>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: OFFERS
// // ─────────────────────────────────────────────────────────────
// const EMPTY_OFFER = { title:"", description:"", ad_network:"", category:"", reward_amount:"", reward_type:"POINTS", device_type:"all", status:"active", is_featured:false, is_hot:false };

// function OffersTab({ toast }) {
//   const [offers,setOffers]     = useState([]);
//   const [loading,setLoading]   = useState(true);
//   const [modal,setModal]       = useState(null);
//   const [delTarget,setDel]     = useState(null);
//   const [search,setSearch]     = useState("");
//   const [filterSt,setFSt]      = useState("all");

//   const load = useCallback(async()=>{
//     setLoading(true);
//     try{ const d=await req("/offers/?page_size=50"); setOffers(d.results||d.data||d||[]); }catch(_){ setOffers([]); }
//     finally{ setLoading(false); }
//   },[]);
//   useEffect(()=>{load();},[load]);

//   const handleSave=async(form)=>{
//     try{
//       if(modal.mode==="create"){ const d=await req("/offers/",{method:"POST",body:JSON.stringify(form)}); setOffers(x=>[d,...x]); toast("Offer created!"); }
//       else{ const d=await req(`/offers/${modal.item.id}/`,{method:"PATCH",body:JSON.stringify(form)}); setOffers(x=>x.map(o=>o.id===modal.item.id?{...o,...d}:o)); toast("Offer updated!"); }
//       setModal(null);
//     }catch(e){ toast(e.message,"error"); }
//   };
//   const handleDelete=async()=>{
//     try{ await req(`/offers/${delTarget.id}/`,{method:"DELETE"}); setOffers(x=>x.filter(o=>o.id!==delTarget.id)); toast("Offer deleted."); }catch(e){ toast(e.message,"error"); }
//     setDel(null);
//   };

//   const filtered=offers.filter(o=>{
//     const q=search.toLowerCase();
//     return (o.title?.toLowerCase().includes(q)||o.description?.toLowerCase().includes(q))
//       &&(filterSt==="all"||o.status===filterSt);
//   });

//   return (
//     <>
//       <div className="toolbar glass">
//         <div className="toolbar__search">
//           <span className="toolbar__search-icon">⌕</span>
//           <input className="toolbar__input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search offers…"/>
//         </div>
//         <div className="toolbar__divider"/>
//         <div className="chip-group">
//           {["all","active","paused","expired"].map(s=>(
//             <button key={s} className={`chip${filterSt===s?" chip--active":""}`} onClick={()=>setFSt(s)}>
//               {s.charAt(0).toUpperCase()+s.slice(1)}
//             </button>
//           ))}
//         </div>
//         <div style={{marginLeft:"auto"}}>
//           <button className="btn btn--primary" onClick={()=>setModal({mode:"create",item:null})}>+ New Offer</button>
//         </div>
//       </div>

//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Title</th><th>Network</th><th>Reward</th><th>Device</th><th>Status</th><th>Flags</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={8}><TabSpinner/></td></tr>:filtered.map((o,i)=>(
//               <tr key={o.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{o.title}</div><div className="net-name__type">{o.description?.slice(0,40)}</div></td>
//                 <td><span className="td-sub">{o.ad_network_name||o.ad_network||"—"}</span></td>
//                 <td><div className="td-primary td-primary--bold">{o.reward_amount} {o.reward_type}</div></td>
//                 <td><span className="cat-badge">{o.device_type||"all"}</span></td>
//                 <td><span className={`badge ${o.status==="active"?"badge--active":o.status==="paused"?"badge--paused":"badge--testing"}`}>{o.status}</span></td>
//                 <td>
//                   {o.is_featured&&<span className="cat-badge" style={{color:"#f59e0b",borderColor:"#f59e0b30",background:"#f59e0b10"}}>⭐ Featured</span>}
//                   {o.is_hot&&<span className="cat-badge" style={{color:"#ef4444",borderColor:"#ef444430",background:"#ef444410",marginLeft:4}}>🔥 Hot</span>}
//                 </td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   <div className="action-group">
//                     <button className="action-btn action-btn--edit" title="Edit" onClick={()=>setModal({mode:"edit",item:o})}>✎</button>
//                     <button className="action-btn action-btn--delete" title="Delete" onClick={()=>setDel(o)}>🗑</button>
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&filtered.length===0&&<EmptyState icon="🎯" text="No offers found."/>}
//       </div>

//       <div className="table-footer">
//         <span>Showing <strong>{filtered.length}</strong> of <strong>{offers.length}</strong> offers</span>
//         <button className="btn btn--ghost" style={{marginLeft:"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>

//       {modal && (
//         <div className="overlay" onClick={()=>setModal(null)}>
//           <div className="modal modal--wide glass" onClick={e=>e.stopPropagation()}>
//             <div className="modal__header">
//               <div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode==="create"?"New Offer":"Edit Offer"}</div><div className="modal__title">🎯 {modal.mode==="create"?"Create Offer":modal.item?.title}</div></div></div>
//               <button className="icon-btn" onClick={()=>setModal(null)}>✕</button>
//             </div>
//             <OfferForm initial={modal.item} onSave={handleSave} onCancel={()=>setModal(null)}/>
//           </div>
//         </div>
//       )}
//       {delTarget&&<ConfirmModal title="Delete Offer?" body={`"${delTarget.title}" will be removed.`} onConfirm={handleDelete} onCancel={()=>setDel(null)}/>}
//     </>
//   );
// }

// function OfferForm({ initial, onSave, onCancel }) {
//   const [form,setForm]=useState(initial||EMPTY_OFFER);
//   const [saving,setSaving]=useState(false);
//   const set=(k,v)=>setForm(p=>({...p,[k]:v}));
//   const submit=async()=>{ setSaving(true); try{ await onSave(form); }finally{ setSaving(false); } };
//   return (
//     <div className="modal__body">
//       <div className="form-grid">
//         <div className="form-row">
//           <div className="field"><label className="field__label">Title *</label><input className="field__input" value={form.title||""} onChange={e=>set("title",e.target.value)} placeholder="Offer title"/></div>
//           <div className="field"><label className="field__label">Reward Amount</label><input className="field__input" type="number" value={form.reward_amount||""} onChange={e=>set("reward_amount",e.target.value)}/></div>
//         </div>
//         <div className="form-row">
//           <div className="field"><label className="field__label">Reward Type</label>
//             <select className="field__input field__select" value={form.reward_type||"POINTS"} onChange={e=>set("reward_type",e.target.value)}>
//               {["POINTS","CASH","GEMS","COINS"].map(t=><option key={t} value={t}>{t}</option>)}
//             </select>
//           </div>
//           <div className="field"><label className="field__label">Device Type</label>
//             <select className="field__input field__select" value={form.device_type||"all"} onChange={e=>set("device_type",e.target.value)}>
//               {["all","mobile","desktop","tablet"].map(t=><option key={t} value={t}>{t}</option>)}
//             </select>
//           </div>
//         </div>
//         <div className="form-row">
//           <div className="field"><label className="field__label">Status</label>
//             <select className="field__input field__select" value={form.status||"active"} onChange={e=>set("status",e.target.value)}>
//               {["active","paused","expired"].map(s=><option key={s} value={s}>{s}</option>)}
//             </select>
//           </div>
//           <div className="field"><label className="field__label">Ad Network ID</label><input className="field__input" value={form.ad_network||""} onChange={e=>set("ad_network",e.target.value)} placeholder="Network UUID"/></div>
//         </div>
//         <div className="field"><label className="field__label">Description</label><textarea className="field__input field__textarea" rows={3} value={form.description||""} onChange={e=>set("description",e.target.value)}/></div>
//         <div className="form-row" style={{gap:16}}>
//           <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}>
//             <input type="checkbox" checked={!!form.is_featured} onChange={e=>set("is_featured",e.target.checked)}/> ⭐ Featured
//           </label>
//           <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}>
//             <input type="checkbox" checked={!!form.is_hot} onChange={e=>set("is_hot",e.target.checked)}/> 🔥 Hot
//           </label>
//         </div>
//         <div className="modal__footer">
//           <button className="btn btn--primary" onClick={submit} disabled={saving}>{saving?"Saving…":"Save Offer"}</button>
//           <button className="btn btn--ghost" onClick={onCancel}>Cancel</button>
//         </div>
//       </div>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: CONVERSIONS
// // ─────────────────────────────────────────────────────────────
// function ConversionsTab({ toast }) {
//   const [items,setItems]       = useState([]);
//   const [loading,setLoading]   = useState(true);
//   const [filterSt,setFSt]      = useState("all");
//   const [search,setSearch]     = useState("");
//   const [delTarget,setDel]     = useState(null);
//   const [selected,setSelected] = useState([]);

//   const load=useCallback(async()=>{
//     setLoading(true);
//     try{ const d=await req("/conversions/?page_size=50"+(filterSt!=="all"?`&conversion_status=${filterSt}`:"")); setItems(d.results||d.data||d||[]); }catch(_){ setItems([]); }
//     finally{ setLoading(false); }
//   },[filterSt]);
//   useEffect(()=>{load();},[load]);

//   const approve=async(id)=>{ try{ await req(`/conversions/${id}/approve/`,{method:"POST"}); setItems(x=>x.map(i=>i.id===id?{...i,conversion_status:"approved"}:i)); toast("Approved!"); }catch(e){ toast(e.message,"error"); } };
//   const reject=async(id)=>{ const r=prompt("Rejection reason:"); if(!r)return; try{ await req(`/conversions/${id}/reject/`,{method:"POST",body:JSON.stringify({rejection_reason:r})}); setItems(x=>x.map(i=>i.id===id?{...i,conversion_status:"rejected"}:i)); toast("Rejected."); }catch(e){ toast(e.message,"error"); } };
//   const bulkApprove=async()=>{ if(!selected.length)return; try{ await req("/conversions/bulk_approve/",{method:"POST",body:JSON.stringify({ids:selected})}); setItems(x=>x.map(i=>selected.includes(i.id)?{...i,conversion_status:"approved"}:i)); setSelected([]); toast(`${selected.length} conversions approved!`); }catch(e){ toast(e.message,"error"); } };

//   const filtered=items.filter(i=>!search||(i.user?.toString()||"").includes(search)||(i.offer_title||"").toLowerCase().includes(search.toLowerCase()));
//   const statusColor={approved:"#10b981",pending:"#f59e0b",rejected:"#ef4444",chargeback:"#8b5cf6"};

//   return (
//     <>
//       <div className="toolbar glass">
//         <div className="toolbar__search">
//           <span className="toolbar__search-icon">⌕</span>
//           <input className="toolbar__input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by user or offer…"/>
//         </div>
//         <div className="toolbar__divider"/>
//         <div className="chip-group">
//           {["all","pending","approved","rejected","chargeback"].map(s=>(
//             <button key={s} className={`chip${filterSt===s?" chip--active":""}`} onClick={()=>setFSt(s)}>{s.charAt(0).toUpperCase()+s.slice(1)}</button>
//           ))}
//         </div>
//         {selected.length>0&&(
//           <button className="btn btn--primary" style={{marginLeft:"auto"}} onClick={bulkApprove}>✓ Bulk Approve ({selected.length})</button>
//         )}
//         <button className="btn btn--ghost" style={{marginLeft:selected.length?"8px":"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>

//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr>
//             <th><input type="checkbox" onChange={e=>setSelected(e.target.checked?filtered.map(i=>i.id):[])}/></th>
//             <th>#</th><th>User</th><th>Offer</th><th>Amount</th><th>Status</th><th>Risk</th><th>Date</th><th>Actions</th>
//           </tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={9}><TabSpinner/></td></tr>:filtered.map((c,i)=>(
//               <tr key={c.id} className="net-row">
//                 <td onClick={e=>e.stopPropagation()}><input type="checkbox" checked={selected.includes(c.id)} onChange={e=>setSelected(x=>e.target.checked?[...x,c.id]:x.filter(id=>id!==c.id))}/></td>
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{c.user_name||c.user||"—"}</div></td>
//                 <td><div className="td-sub">{c.offer_title||c.offer||"—"}</div></td>
//                 <td><div className="td-primary td-primary--bold">{c.payout_amount||c.amount||"—"}</div></td>
//                 <td><span className="badge" style={{background:`${statusColor[c.conversion_status]||"#64748b"}18`,color:statusColor[c.conversion_status]||"#64748b",border:`1px solid ${statusColor[c.conversion_status]||"#64748b"}30`}}>{c.conversion_status||"—"}</span></td>
//                 <td><span className="cat-badge" style={{color:c.risk_level==="high"?"#ef4444":c.risk_level==="medium"?"#f59e0b":"#10b981"}}>{c.risk_level||"low"}</span></td>
//                 <td><div className="td-sub">{c.created_at?new Date(c.created_at).toLocaleDateString():"—"}</div></td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   <div className="action-group">
//                     {c.conversion_status==="pending"&&<>
//                       <button className="action-btn action-btn--play" title="Approve" onClick={()=>approve(c.id)}>✓</button>
//                       <button className="action-btn action-btn--delete" title="Reject" onClick={()=>reject(c.id)}>✕</button>
//                     </>}
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&filtered.length===0&&<EmptyState icon="💰" text="No conversions found."/>}
//       </div>
//       <div className="table-footer"><span>Showing <strong>{filtered.length}</strong> of <strong>{items.length}</strong> conversions</span></div>
//     </>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: ENGAGEMENTS
// // ─────────────────────────────────────────────────────────────
// function EngagementsTab({ toast }) {
//   const [items,setItems]     = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [filterSt,setFSt]   = useState("all");
//   const [search,setSearch]  = useState("");

//   const load=useCallback(async()=>{
//     setLoading(true);
//     try{ const d=await req("/engagements/?page_size=50"+(filterSt!=="all"?`&status=${filterSt}`:"")); setItems(d.results||d.data||d||[]); }catch(_){ setItems([]); }
//     finally{ setLoading(false); }
//   },[filterSt]);
//   useEffect(()=>{load();},[load]);

//   const approve=async(id)=>{ try{ await req(`/engagements/${id}/approve/`,{method:"POST"}); setItems(x=>x.map(i=>i.id===id?{...i,status:"approved"}:i)); toast("Engagement approved!"); }catch(e){ toast(e.message,"error"); } };
//   const reject=async(id)=>{ const r=prompt("Rejection reason:"); if(!r)return; try{ await req(`/engagements/${id}/reject/`,{method:"POST",body:JSON.stringify({rejection_reason:r})}); setItems(x=>x.map(i=>i.id===id?{...i,status:"rejected"}:i)); toast("Rejected."); }catch(e){ toast(e.message,"error"); } };

//   const filtered=items.filter(i=>!search||i.user?.toString().includes(search)||(i.offer_title||"").toLowerCase().includes(search.toLowerCase()));
//   const stColor={approved:"#10b981",pending:"#f59e0b",rejected:"#ef4444",completed:"#6366f1"};

//   return (
//     <>
//       <div className="toolbar glass">
//         <div className="toolbar__search"><span className="toolbar__search-icon">⌕</span><input className="toolbar__input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search engagements…"/></div>
//         <div className="toolbar__divider"/>
//         <div className="chip-group">
//           {["all","pending","approved","rejected","completed"].map(s=>(
//             <button key={s} className={`chip${filterSt===s?" chip--active":""}`} onClick={()=>setFSt(s)}>{s.charAt(0).toUpperCase()+s.slice(1)}</button>
//           ))}
//         </div>
//         <button className="btn btn--ghost" style={{marginLeft:"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>User</th><th>Offer</th><th>Status</th><th>Started</th><th>Completed</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={7}><TabSpinner/></td></tr>:filtered.map((e,i)=>(
//               <tr key={e.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{e.user_name||e.user||"—"}</div></td>
//                 <td><div className="td-sub">{e.offer_title||e.offer||"—"}</div></td>
//                 <td><span className="badge" style={{background:`${stColor[e.status]||"#64748b"}18`,color:stColor[e.status]||"#64748b",border:`1px solid ${stColor[e.status]||"#64748b"}30`}}>{e.status||"—"}</span></td>
//                 <td><div className="td-sub">{e.created_at?new Date(e.created_at).toLocaleDateString():"—"}</div></td>
//                 <td><div className="td-sub">{e.completed_at?new Date(e.completed_at).toLocaleDateString():"—"}</div></td>
//                 <td onClick={ev=>ev.stopPropagation()}>
//                   <div className="action-group">
//                     {e.status==="pending"&&<>
//                       <button className="action-btn action-btn--play" title="Approve" onClick={()=>approve(e.id)}>✓</button>
//                       <button className="action-btn action-btn--delete" title="Reject" onClick={()=>reject(e.id)}>✕</button>
//                     </>}
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&filtered.length===0&&<EmptyState icon="👥" text="No engagements found."/>}
//       </div>
//       <div className="table-footer"><span>Showing <strong>{filtered.length}</strong> of <strong>{items.length}</strong> engagements</span></div>
//     </>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: OFFER WALLS
// // ─────────────────────────────────────────────────────────────
// function OfferWallsTab({ toast }) {
//   const [walls,setWalls]     = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [modal,setModal]     = useState(null);
//   const [delTarget,setDel]   = useState(null);

//   const load=useCallback(async()=>{ setLoading(true); try{ const d=await req("/walls/"); setWalls(d.results||d.data||d||[]); }catch(_){ setWalls([]); } finally{ setLoading(false); } },[]);
//   useEffect(()=>{load();},[load]);

//   const handleSave=async(form)=>{
//     try{
//       if(modal.mode==="create"){ const d=await req("/walls/",{method:"POST",body:JSON.stringify(form)}); setWalls(x=>[d,...x]); toast("Offer wall created!"); }
//       else{ const d=await req(`/walls/${modal.item.id}/`,{method:"PATCH",body:JSON.stringify(form)}); setWalls(x=>x.map(w=>w.id===modal.item.id?{...w,...d}:w)); toast("Updated!"); }
//       setModal(null);
//     }catch(e){ toast(e.message,"error"); }
//   };
//   const handleDelete=async()=>{ try{ await req(`/walls/${delTarget.id}/`,{method:"DELETE"}); setWalls(x=>x.filter(w=>w.id!==delTarget.id)); toast("Deleted."); }catch(e){ toast(e.message,"error"); } setDel(null); };

//   return (
//     <>
//       <div className="toolbar glass">
//         <div style={{flex:1,color:"rgba(200,200,255,0.5)",fontSize:13}}>Manage offer walls shown to users</div>
//         <button className="btn btn--primary" onClick={()=>setModal({mode:"create",item:null})}>+ New Wall</button>
//         <button className="btn btn--ghost" onClick={load}><span className={loading?"spin":""}>⟳</span></button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Name</th><th>Type</th><th>Active</th><th>Default</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={6}><TabSpinner/></td></tr>:walls.map((w,i)=>(
//               <tr key={w.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{w.name||w.title||"—"}</div></td>
//                 <td><span className="cat-badge">{w.wall_type||"—"}</span></td>
//                 <td><span className={`badge ${w.is_active?"badge--active":"badge--paused"}`}>{w.is_active?"Active":"Inactive"}</span></td>
//                 <td>{w.is_default&&<span className="cat-badge" style={{color:"#f59e0b"}}>⭐ Default</span>}</td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   <div className="action-group">
//                     <button className="action-btn action-btn--edit" onClick={()=>setModal({mode:"edit",item:w})}>✎</button>
//                     <button className="action-btn action-btn--delete" onClick={()=>setDel(w)}>🗑</button>
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&walls.length===0&&<EmptyState icon="📱" text="No offer walls configured."/>}
//       </div>
//       {modal&&(
//         <div className="overlay" onClick={()=>setModal(null)}>
//           <div className="modal glass" onClick={e=>e.stopPropagation()}>
//             <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode==="create"?"New":"Edit"} Offer Wall</div><div className="modal__title">📱 {modal.item?.name||"New Wall"}</div></div></div><button className="icon-btn" onClick={()=>setModal(null)}>✕</button></div>
//             <SimpleWallForm initial={modal.item} onSave={handleSave} onCancel={()=>setModal(null)}/>
//           </div>
//         </div>
//       )}
//       {delTarget&&<ConfirmModal title="Delete Wall?" body={`"${delTarget.name}" will be removed.`} onConfirm={handleDelete} onCancel={()=>setDel(null)}/>}
//     </>
//   );
// }

// function SimpleWallForm({ initial, onSave, onCancel }) {
//   const [form,setForm]=useState(initial||{name:"",wall_type:"standard",is_active:true,is_default:false});
//   const [saving,setSaving]=useState(false);
//   const set=(k,v)=>setForm(p=>({...p,[k]:v}));
//   const submit=async()=>{ setSaving(true); try{ await onSave(form); }finally{ setSaving(false); } };
//   return (
//     <div className="modal__body"><div className="form-grid">
//       <div className="field"><label className="field__label">Wall Name *</label><input className="field__input" value={form.name||""} onChange={e=>set("name",e.target.value)}/></div>
//       <div className="field"><label className="field__label">Type</label>
//         <select className="field__input field__select" value={form.wall_type||"standard"} onChange={e=>set("wall_type",e.target.value)}>
//           {["standard","premium","vip","mobile_only"].map(t=><option key={t} value={t}>{t}</option>)}
//         </select>
//       </div>
//       <div className="form-row" style={{gap:16}}>
//         <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}><input type="checkbox" checked={!!form.is_active} onChange={e=>set("is_active",e.target.checked)}/> Active</label>
//         <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}><input type="checkbox" checked={!!form.is_default} onChange={e=>set("is_default",e.target.checked)}/> Set as Default</label>
//       </div>
//       <div className="modal__footer"><button className="btn btn--primary" onClick={submit} disabled={saving}>{saving?"Saving…":"Save Wall"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
//     </div></div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: FRAUD RULES
// // ─────────────────────────────────────────────────────────────
// function FraudTab({ toast }) {
//   const [rules,setRules]     = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [modal,setModal]     = useState(null);
//   const [delTarget,setDel]   = useState(null);

//   const load=useCallback(async()=>{ setLoading(true); try{ const d=await req("/fraud-rules/"); setRules(d.results||d.data||d||[]); }catch(_){ setRules([]); } finally{ setLoading(false); } },[]);
//   useEffect(()=>{load();},[load]);

//   const handleSave=async(form)=>{
//     try{
//       if(modal.mode==="create"){ const d=await req("/fraud-rules/",{method:"POST",body:JSON.stringify(form)}); setRules(x=>[d,...x]); toast("Rule created!"); }
//       else{ const d=await req(`/fraud-rules/${modal.item.id}/`,{method:"PATCH",body:JSON.stringify(form)}); setRules(x=>x.map(r=>r.id===modal.item.id?{...r,...d}:r)); toast("Updated!"); }
//       setModal(null);
//     }catch(e){ toast(e.message,"error"); }
//   };
//   const handleDelete=async()=>{ try{ await req(`/fraud-rules/${delTarget.id}/`,{method:"DELETE"}); setRules(x=>x.filter(r=>r.id!==delTarget.id)); toast("Rule deleted."); }catch(e){ toast(e.message,"error"); } setDel(null); };
//   const sevColor={low:"#10b981",medium:"#f59e0b",high:"#ef4444",critical:"#8b5cf6"};

//   return (
//     <>
//       <div className="toolbar glass">
//         <div style={{flex:1,color:"rgba(200,200,255,0.5)",fontSize:13}}>🛡️ Fraud Detection Rules — Protect your network</div>
//         <button className="btn btn--primary" onClick={()=>setModal({mode:"create",item:null})}>+ New Rule</button>
//         <button className="btn btn--ghost" onClick={load}><span className={loading?"spin":""}>⟳</span></button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Rule Name</th><th>Type</th><th>Action</th><th>Severity</th><th>Active</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={7}><TabSpinner/></td></tr>:rules.map((r,i)=>(
//               <tr key={r.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{r.name||r.rule_name||"—"}</div></td>
//                 <td><span className="cat-badge">{r.rule_type||"—"}</span></td>
//                 <td><span className="cat-badge" style={{color:"#6366f1"}}>{r.action||"—"}</span></td>
//                 <td><span className="badge" style={{background:`${sevColor[r.severity]||"#64748b"}18`,color:sevColor[r.severity]||"#64748b",border:`1px solid ${sevColor[r.severity]||"#64748b"}30`}}>{r.severity||"—"}</span></td>
//                 <td><span className={`badge ${r.is_active?"badge--active":"badge--paused"}`}>{r.is_active?"On":"Off"}</span></td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   <div className="action-group">
//                     <button className="action-btn action-btn--edit" onClick={()=>setModal({mode:"edit",item:r})}>✎</button>
//                     <button className="action-btn action-btn--delete" onClick={()=>setDel(r)}>🗑</button>
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&rules.length===0&&<EmptyState icon="🛡️" text="No fraud rules configured."/>}
//       </div>
//       {modal&&(
//         <div className="overlay" onClick={()=>setModal(null)}>
//           <div className="modal modal--wide glass" onClick={e=>e.stopPropagation()}>
//             <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode==="create"?"New":"Edit"} Fraud Rule</div><div className="modal__title">🛡️ {modal.item?.name||"New Rule"}</div></div></div><button className="icon-btn" onClick={()=>setModal(null)}>✕</button></div>
//             <FraudForm initial={modal.item} onSave={handleSave} onCancel={()=>setModal(null)}/>
//           </div>
//         </div>
//       )}
//       {delTarget&&<ConfirmModal title="Delete Rule?" body={`"${delTarget.name}" will be removed.`} onConfirm={handleDelete} onCancel={()=>setDel(null)}/>}
//     </>
//   );
// }

// function FraudForm({ initial, onSave, onCancel }) {
//   const [form,setForm]=useState(initial||{name:"",rule_type:"velocity",action:"block",severity:"medium",is_active:true,description:""});
//   const [saving,setSaving]=useState(false);
//   const set=(k,v)=>setForm(p=>({...p,[k]:v}));
//   const submit=async()=>{ setSaving(true); try{ await onSave(form); }finally{ setSaving(false); } };
//   return (
//     <div className="modal__body"><div className="form-grid">
//       <div className="form-row">
//         <div className="field"><label className="field__label">Rule Name *</label><input className="field__input" value={form.name||""} onChange={e=>set("name",e.target.value)}/></div>
//         <div className="field"><label className="field__label">Rule Type</label>
//           <select className="field__input field__select" value={form.rule_type||"velocity"} onChange={e=>set("rule_type",e.target.value)}>
//             {["velocity","device_fingerprint","ip_reputation","behavior","geo_restriction","time_based"].map(t=><option key={t} value={t}>{t}</option>)}
//           </select>
//         </div>
//       </div>
//       <div className="form-row">
//         <div className="field"><label className="field__label">Action</label>
//           <select className="field__input field__select" value={form.action||"block"} onChange={e=>set("action",e.target.value)}>
//             {["block","flag","review","allow","rate_limit"].map(t=><option key={t} value={t}>{t}</option>)}
//           </select>
//         </div>
//         <div className="field"><label className="field__label">Severity</label>
//           <select className="field__input field__select" value={form.severity||"medium"} onChange={e=>set("severity",e.target.value)}>
//             {["low","medium","high","critical"].map(t=><option key={t} value={t}>{t}</option>)}
//           </select>
//         </div>
//       </div>
//       <div className="field"><label className="field__label">Description</label><textarea className="field__input field__textarea" rows={2} value={form.description||""} onChange={e=>set("description",e.target.value)}/></div>
//       <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}><input type="checkbox" checked={!!form.is_active} onChange={e=>set("is_active",e.target.checked)}/> Rule Active</label>
//       <div className="modal__footer"><button className="btn btn--primary" onClick={submit} disabled={saving}>{saving?"Saving…":"Save Rule"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
//     </div></div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: BLACKLIST IPs
// // ─────────────────────────────────────────────────────────────
// function BlacklistTab({ toast }) {
//   const [ips,setIPs]         = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [modal,setModal]     = useState(null);
//   const [delTarget,setDel]   = useState(null);
//   const [checkIP,setCheckIP] = useState("");
//   const [checkResult,setCheckResult] = useState(null);

//   const load=useCallback(async()=>{ setLoading(true); try{ const d=await req("/blacklisted-ips/"); setIPs(d.results||d.data||d||[]); }catch(_){ setIPs([]); } finally{ setLoading(false); } },[]);
//   useEffect(()=>{load();},[load]);

//   const handleSave=async(form)=>{
//     try{
//       if(modal.mode==="create"){ const d=await req("/blacklisted-ips/",{method:"POST",body:JSON.stringify(form)}); setIPs(x=>[d,...x]); toast("IP blacklisted!"); }
//       else{ const d=await req(`/blacklisted-ips/${modal.item.id}/`,{method:"PATCH",body:JSON.stringify(form)}); setIPs(x=>x.map(i=>i.id===modal.item.id?{...i,...d}:i)); toast("Updated!"); }
//       setModal(null);
//     }catch(e){ toast(e.message,"error"); }
//   };
//   const handleDelete=async()=>{ try{ await req(`/blacklisted-ips/${delTarget.id}/`,{method:"DELETE"}); setIPs(x=>x.filter(i=>i.id!==delTarget.id)); toast("Removed."); }catch(e){ toast(e.message,"error"); } setDel(null); };
//   const handleCheck=async()=>{ if(!checkIP.trim())return; try{ const d=await req("/blacklisted-ips/check/",{method:"POST",body:JSON.stringify({ip_address:checkIP})}); setCheckResult(d); }catch(e){ toast(e.message,"error"); } };
//   const handleCleanup=async()=>{ try{ await req("/blacklisted-ips/cleanup/",{method:"POST",body:JSON.stringify({batch_size:1000})}); toast("Cleanup complete!"); load(); }catch(e){ toast(e.message,"error"); } };

//   return (
//     <>
//       <div className="toolbar glass" style={{flexWrap:"wrap",gap:8}}>
//         <div style={{display:"flex",gap:8,flex:1,minWidth:280}}>
//           <input className="toolbar__input" style={{flex:1,border:"1px solid rgba(100,60,200,0.2)",borderRadius:6,padding:"6px 12px",background:"rgba(20,10,40,0.5)",color:"#c8b8ff"}} value={checkIP} onChange={e=>setCheckIP(e.target.value)} placeholder="Check IP address…"/>
//           <button className="btn btn--ghost" onClick={handleCheck}>🔍 Check</button>
//         </div>
//         {checkResult&&<div style={{padding:"4px 12px",borderRadius:6,fontSize:12,background:checkResult.is_blacklisted?"rgba(239,68,68,0.15)":"rgba(16,185,129,0.15)",color:checkResult.is_blacklisted?"#ef4444":"#10b981",border:`1px solid ${checkResult.is_blacklisted?"#ef444430":"#10b98130"}`}}>{checkResult.is_blacklisted?"🚫 Blacklisted":"✅ Clean"}</div>}
//         <button className="btn btn--ghost" onClick={handleCleanup}>🧹 Cleanup Expired</button>
//         <button className="btn btn--primary" onClick={()=>setModal({mode:"create",item:null})}>+ Block IP</button>
//         <button className="btn btn--ghost" onClick={load}><span className={loading?"spin":""}>⟳</span></button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>IP Address</th><th>Reason</th><th>Active</th><th>Expires</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={6}><TabSpinner/></td></tr>:ips.map((ip,i)=>(
//               <tr key={ip.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title" style={{fontFamily:"monospace"}}>{ip.ip_address}</div></td>
//                 <td><div className="td-sub">{ip.reason||"—"}</div></td>
//                 <td><span className={`badge ${ip.is_active?"badge--paused":"badge--active"}`}>{ip.is_active?"Blocked":"Inactive"}</span></td>
//                 <td><div className="td-sub">{ip.expiry_date?new Date(ip.expiry_date).toLocaleDateString():"Never"}</div></td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   <div className="action-group">
//                     <button className="action-btn action-btn--edit" onClick={()=>setModal({mode:"edit",item:ip})}>✎</button>
//                     <button className="action-btn action-btn--delete" onClick={()=>setDel(ip)}>🗑</button>
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&ips.length===0&&<EmptyState icon="🚫" text="No blacklisted IPs."/>}
//       </div>
//       {modal&&(
//         <div className="overlay" onClick={()=>setModal(null)}>
//           <div className="modal glass" onClick={e=>e.stopPropagation()}>
//             <div className="modal__header"><div className="modal__header-left"><div><div className="modal__subtitle">{modal.mode==="create"?"Block New":"Edit"} IP</div><div className="modal__title">🚫 {modal.item?.ip_address||"New IP"}</div></div></div><button className="icon-btn" onClick={()=>setModal(null)}>✕</button></div>
//             <IPForm initial={modal.item} onSave={handleSave} onCancel={()=>setModal(null)}/>
//           </div>
//         </div>
//       )}
//       {delTarget&&<ConfirmModal title="Remove IP?" body={`"${delTarget.ip_address}" will be unblocked.`} onConfirm={handleDelete} onCancel={()=>setDel(null)}/>}
//     </>
//   );
// }

// function IPForm({ initial, onSave, onCancel }) {
//   const [form,setForm]=useState(initial||{ip_address:"",reason:"",expiry_date:"",is_active:true});
//   const [saving,setSaving]=useState(false);
//   const set=(k,v)=>setForm(p=>({...p,[k]:v}));
//   const submit=async()=>{ setSaving(true); try{ await onSave(form); }finally{ setSaving(false); } };
//   return (
//     <div className="modal__body"><div className="form-grid">
//       <div className="field"><label className="field__label">IP Address *</label><input className="field__input" style={{fontFamily:"monospace"}} value={form.ip_address||""} onChange={e=>set("ip_address",e.target.value)} placeholder="192.168.1.1"/></div>
//       <div className="field"><label className="field__label">Reason</label><input className="field__input" value={form.reason||""} onChange={e=>set("reason",e.target.value)} placeholder="e.g. Fraud, Spam"/></div>
//       <div className="field"><label className="field__label">Expiry Date (optional)</label><input className="field__input" type="date" value={form.expiry_date||""} onChange={e=>set("expiry_date",e.target.value)}/></div>
//       <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13,color:"rgba(200,200,255,0.7)"}}><input type="checkbox" checked={!!form.is_active} onChange={e=>set("is_active",e.target.checked)}/> Active Block</label>
//       <div className="modal__footer"><button className="btn btn--danger" onClick={submit} disabled={saving}>{saving?"Saving…":"Block IP"}</button><button className="btn btn--ghost" onClick={onCancel}>Cancel</button></div>
//     </div></div>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: WEBHOOKS
// // ─────────────────────────────────────────────────────────────
// function WebhooksTab({ toast }) {
//   const [logs,setLogs]       = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [filterN,setFN]      = useState("all");

//   const load=useCallback(async()=>{ setLoading(true); try{ const d=await req("/webhooks/?page_size=50"); setLogs(d.results||d.data||d||[]); }catch(_){ setLogs([]); } finally{ setLoading(false); } },[]);
//   useEffect(()=>{load();},[load]);

//   const reprocess=async(id)=>{ try{ await req(`/webhooks/${id}/reprocess/`,{method:"POST"}); toast("Reprocessed!"); load(); }catch(e){ toast(e.message,"error"); } };

//   const networks=[...new Set(logs.map(l=>l.ad_network_name||l.ad_network).filter(Boolean))];

//   return (
//     <>
//       <div className="toolbar glass">
//         <div className="chip-group">
//           <button className={`chip${filterN==="all"?" chip--active":""}`} onClick={()=>setFN("all")}>All Networks</button>
//           {networks.map(n=><button key={n} className={`chip${filterN===n?" chip--active":""}`} onClick={()=>setFN(n)}>{n}</button>)}
//         </div>
//         <button className="btn btn--ghost" style={{marginLeft:"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Network</th><th>Event</th><th>Valid Sig</th><th>Processed</th><th>Date</th><th>Actions</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={7}><TabSpinner/></td></tr>:logs.filter(l=>filterN==="all"||(l.ad_network_name||l.ad_network)===filterN).map((l,i)=>(
//               <tr key={l.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{l.ad_network_name||l.ad_network||"—"}</div></td>
//                 <td><span className="cat-badge">{l.event_type||"—"}</span></td>
//                 <td>{l.is_valid_signature?<span style={{color:"#10b981"}}>✓ Valid</span>:<span style={{color:"#ef4444"}}>✕ Invalid</span>}</td>
//                 <td>{l.processed?<span className="badge badge--active">Done</span>:<span className="badge badge--paused">Pending</span>}</td>
//                 <td><div className="td-sub">{l.created_at?new Date(l.created_at).toLocaleString():"—"}</div></td>
//                 <td onClick={e=>e.stopPropagation()}>
//                   {!l.processed&&<button className="action-btn action-btn--edit" title="Reprocess" onClick={()=>reprocess(l.id)}>⟳</button>}
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&logs.length===0&&<EmptyState icon="🔗" text="No webhook logs found."/>}
//       </div>
//       <div className="table-footer"><span>{logs.length} webhook events</span></div>
//     </>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // TAB: SYNC LOGS
// // ─────────────────────────────────────────────────────────────
// function SyncLogsTab({ toast }) {
//   const [logs,setLogs]       = useState([]);
//   const [loading,setLoading] = useState(true);
//   const [filterSt,setFSt]   = useState("all");

//   const load=useCallback(async()=>{ setLoading(true); try{ const d=await req("/sync-logs/?page_size=50"+(filterSt!=="all"?`&status=${filterSt}`:"")); setLogs(d.results||d.data||d||[]); }catch(_){ setLogs([]); } finally{ setLoading(false); } },[filterSt]);
//   useEffect(()=>{load();},[load]);

//   const stColor={success:"#10b981",failed:"#ef4444",in_progress:"#f59e0b",pending:"#6366f1"};
//   return (
//     <>
//       <div className="toolbar glass">
//         <div className="chip-group">
//           {["all","success","failed","in_progress","pending"].map(s=>(
//             <button key={s} className={`chip${filterSt===s?" chip--active":""}`} onClick={()=>setFSt(s)}>{s.replace("_"," ").replace(/\b\w/g,c=>c.toUpperCase())}</button>
//           ))}
//         </div>
//         <button className="btn btn--ghost" style={{marginLeft:"auto"}} onClick={load}><span className={loading?"spin":""}>⟳</span> Refresh</button>
//       </div>
//       <div className="table-wrap glass">
//         <table className="net-table">
//           <thead><tr><th>#</th><th>Network</th><th>Status</th><th>Offers Synced</th><th>Duration</th><th>Started</th></tr></thead>
//           <tbody>
//             {loading?<tr><td colSpan={6}><TabSpinner/></td></tr>:logs.map((l,i)=>(
//               <tr key={l.id} className="net-row">
//                 <td className="td-num">{String(i+1).padStart(2,"0")}</td>
//                 <td><div className="net-name__title">{l.ad_network_name||l.ad_network||"—"}</div></td>
//                 <td><span className="badge" style={{background:`${stColor[l.status]||"#64748b"}18`,color:stColor[l.status]||"#64748b",border:`1px solid ${stColor[l.status]||"#64748b"}30`}}>{l.status||"—"}</span></td>
//                 <td><div className="td-primary">{l.offers_synced??l.total_offers??"—"}</div></td>
//                 <td><div className="td-sub">{l.duration_seconds?`${l.duration_seconds}s`:"—"}</div></td>
//                 <td><div className="td-sub">{l.started_at?new Date(l.started_at).toLocaleString():l.created_at?new Date(l.created_at).toLocaleString():"—"}</div></td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//         {!loading&&logs.length===0&&<EmptyState icon="🔄" text="No sync logs found."/>}
//       </div>
//     </>
//   );
// }

// // ─────────────────────────────────────────────────────────────
// // MAIN COMPONENT
// // ─────────────────────────────────────────────────────────────
// export default function AdNetworks() {
//   const [activeTab, setActiveTab] = useState("networks");
//   const [toasts, setToasts]       = useState([]);

//   const toast = useCallback((message, type="success") => {
//     const id = Date.now();
//     setToasts(p => [...p, {id, message, type}]);
//     setTimeout(()=>setToasts(p=>p.filter(t=>t.id!==id)), 3500);
//   }, []);

//   const renderTab = () => {
//     switch(activeTab) {
//       case "networks":    return <NetworksTab    toast={toast}/>;
//       case "offers":      return <OffersTab      toast={toast}/>;
//       case "conversions": return <ConversionsTab toast={toast}/>;
//       case "engagements": return <EngagementsTab toast={toast}/>;
//       case "offerwalls":  return <OfferWallsTab  toast={toast}/>;
//       case "fraud":       return <FraudTab       toast={toast}/>;
//       case "blacklist":   return <BlacklistTab   toast={toast}/>;
//       case "webhooks":    return <WebhooksTab    toast={toast}/>;
//       case "synclogs":    return <SyncLogsTab    toast={toast}/>;
//       default:            return null;
//     }
//   };

//   return (
//     <div className="an-root">
//       <div className="orb orb--1"/><div className="orb orb--2"/><div className="orb orb--3"/>
//       <div className="an-container">

//         {/* PAGE HEADER */}
//         <header className="page-header">
//           <div className="page-header__left">
//             <div className="page-header__eyebrow">Ad Network Management</div>
//             <h1 className="page-header__title">Networks</h1>
//           </div>
//         </header>

//         {/* TAB BAR */}
//         <div className="an-tabs glass">
//           {TABS.map(t=>(
//             <button key={t.id}
//               className={`an-tab${activeTab===t.id?" an-tab--active":""}`}
//               onClick={()=>setActiveTab(t.id)}>
//               <span className="an-tab__icon">{t.icon}</span>
//               <span className="an-tab__label">{t.label}</span>
//             </button>
//           ))}
//         </div>

//         {/* TAB CONTENT */}
//         <div className="an-tab-content">
//           {renderTab()}
//         </div>

//       </div>
//       <Toast toasts={toasts}/>
//     </div>
//   );
// }
