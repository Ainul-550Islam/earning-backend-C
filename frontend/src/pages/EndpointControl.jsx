import { useState, useEffect } from "react";
import "./EndpointControl.css";

const API_BASE = "https://earning-backend-c-production.up.railway.app/api";
const getToken = () => localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || "";

const apiFetch = async (path, options = {}) => {
  const res = await fetch(API_BASE + path, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + getToken(), ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
};

const METHOD_META = {
  GET:    { bg: "#0f2456", glow: "#3b82f6", text: "#93c5fd", border: "#1d4ed8" },
  POST:   { bg: "#052e16", glow: "#22c55e", text: "#86efac", border: "#15803d" },
  PUT:    { bg: "#431407", glow: "#f97316", text: "#fdba74", border: "#c2410c" },
  PATCH:  { bg: "#2e1065", glow: "#a855f7", text: "#d8b4fe", border: "#7e22ce" },
  DELETE: { bg: "#450a0a", glow: "#ef4444", text: "#fca5a5", border: "#b91c1c" },
};

// Group icons
const GROUP_ICONS = {
  auth: "🔑", users: "👥", wallet: "💰", tasks: "✅", offers: "📢",
  notifications: "🔔", analytics: "📊", payments: "💳", promotions: "🎯",
  subscription: "⭐", subscriptions: "⭐", gamification: "🎮", support: "🎫",
  messaging: "💬", cms: "📝", security: "🔒", "fraud-detection": "🚨",
  fraud_detection: "🚨", backup: "💾", audit_logs: "📋", localization: "🌍",
  "rate-limit": "⏱️", "version-control": "📱", inventory: "📦",
  "payout-queue": "🏦", postback: "🔄", engagement: "🎯",
  "behavior-analytics": "🧠", djoyalty: "🏆", "ad-networks": "📡",
  ad_networks: "📡", "auto-mod": "🤖", cache: "⚡", alerts: "🚨",
  kyc: "🪪", referral: "👥", "admin-panel": "⚙️", ALL: "🌐",
  "2fa": "🛡️", GatewayTransactions: "💳", dashboard: "📊", dashboards: "📊",
  devices: "📱", bans: "🚫", "auto-block-rules": "🛡️", "fraud-patterns": "🔍",
  health: "💊", "ip-blacklist": "🚫", login: "🔐", logs: "📜",
  loyalty: "🏆", "my-payment-requests": "💸", "mylead-postback": "🔄",
  notices: "📢", "payment-history": "📜", "payment-request": "💸",
  payment_gateways: "💳", profile: "👤", "real-time-detections": "🔍",
  register: "📝", "risk-scores": "⚠️", "security-logs": "📋",
  sessions: "🔐", statistics: "📊", status: "✅", user: "👤",
  "version-control": "📱", wallets: "💰", withdrawals: "💸",
  completions: "✅", customers: "👥", "admin-ledger": "📒",
  "complete-ad": "📢",
};

export default function EndpointControl() {
  const [endpoints, setEndpoints] = useState([]);
  const [toggleStates, setToggleStates] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [bulkLoading, setBulkLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("ALL");
  const [groups, setGroups] = useState([]);
  const [groupCounts, setGroupCounts] = useState({});

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const schema = await fetch(API_BASE.replace("/api", "") + "/api/schema/?format=json").then(r => r.json());
        const allEndpoints = [];
        Object.entries(schema.paths || {}).forEach(([path, methods]) => {
          Object.keys(methods).forEach(method => {
            if (["get","post","put","patch","delete"].includes(method)) {
              const group = path.split("/").filter(Boolean)[1] || "other";
              allEndpoints.push({ path, method: method.toUpperCase(), group, label: methods[method].summary || path });
            }
          });
        });
        setEndpoints(allEndpoints);

        // Count per group
        const counts = { ALL: allEndpoints.length };
        allEndpoints.forEach(e => { counts[e.group] = (counts[e.group] || 0) + 1; });
        setGroupCounts(counts);
        setGroups(["ALL", ...new Set(allEndpoints.map(e => e.group))].sort());

        const td = await apiFetch("/admin-panel/endpoint-toggles/?limit=5000");
        const results = td.results || (Array.isArray(td) ? td : []);
        const states = {};
        results.forEach(t => { states[t.path + "_" + t.method] = { id: t.id, is_enabled: t.is_enabled }; });
        setToggleStates(states);
      } catch (e) {
        showToast("Load failed: " + e.message, "error");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const isEnabled = (path, method) => toggleStates[path + "_" + method]?.is_enabled !== false;

  const toggle = async (item) => {
    const key = item.path + "_" + item.method;
    const newState = !isEnabled(item.path, item.method);
    setSaving(p => ({ ...p, [key]: true }));
    try {
      const existing = toggleStates[key];
      let result;
      if (existing?.id) {
        result = await apiFetch("/admin-panel/endpoint-toggles/" + existing.id + "/", {
          method: "PATCH", body: JSON.stringify({ is_enabled: newState }),
        });
      } else {
        result = await apiFetch("/admin-panel/endpoint-toggles/", {
          method: "POST",
          body: JSON.stringify({ path: item.path, method: item.method, group: item.group, label: item.label, is_enabled: newState, disabled_message: "This endpoint is temporarily disabled." }),
        });
      }
      setToggleStates(p => ({ ...p, [key]: { id: result.id, is_enabled: newState } }));
      showToast((newState ? "✅ " : "❌ ") + item.method + " " + item.path);
    } catch (e) { showToast("Failed: " + e.message, "error"); }
    finally { setSaving(p => ({ ...p, [key]: false })); }
  };

  const toggleGroup = async (enabled) => {
    const list = endpoints.filter(e => selectedGroup === "ALL" || e.group === selectedGroup);
    setBulkLoading(true);
    try {
      const chunkSize = 100;
      for (let i = 0; i < list.length; i += chunkSize) {
        const chunk = list.slice(i, i + chunkSize);
        await apiFetch("/admin-panel/endpoint-toggles/bulk_toggle/", {
          method: "POST",
          body: JSON.stringify({ toggles: chunk.map(e => ({ path: e.path, method: e.method, group: e.group, label: e.label, is_enabled: enabled, message: "Temporarily disabled by admin." })) }),
        });
      }
      const ns = {};
      list.forEach(e => { ns[e.path + "_" + e.method] = { ...toggleStates[e.path + "_" + e.method], is_enabled: enabled }; });
      setToggleStates(p => ({ ...p, ...ns }));
      showToast((enabled ? "✅ Enabled " : "❌ Disabled ") + list.length + " endpoints!");
    } catch (e) { showToast("Bulk failed: " + e.message, "error"); }
    finally { setBulkLoading(false); }
  };

  const filtered = endpoints.filter(e =>
    (selectedGroup === "ALL" || e.group === selectedGroup) &&
    (!search || e.path.toLowerCase().includes(search.toLowerCase()))
  );

  const activeCount = endpoints.filter(e => isEnabled(e.path, e.method)).length;
  const filteredActive = filtered.filter(e => isEnabled(e.path, e.method)).length;

  // Group active counts
  const groupActiveCount = (g) => {
    const list = g === "ALL" ? endpoints : endpoints.filter(e => e.group === g);
    return list.filter(e => isEnabled(e.path, e.method)).length;
  };

  return (
    <div className="ec-root">
      <div className="ec-bg-orbs">
        <div className="ec-orb ec-orb-1" />
        <div className="ec-orb ec-orb-2" />
        <div className="ec-orb ec-orb-3" />
      </div>

      {/* Header */}
      <div className="ec-header">
        <div className="ec-header-left">
          <h1 className="ec-title"><span className="ec-title-icon">⚡</span>API Endpoint Control</h1>
          <p className="ec-subtitle">Individual on/off control over all {endpoints.length} API endpoints</p>
        </div>
        <div className="ec-live-badge">
          <span className="ec-live-dot" />
          <div>
            <div className="ec-live-nums">
              <span className="ec-live-active">{activeCount}</span>
              <span className="ec-live-sep"> / </span>
              <span className="ec-live-total">{endpoints.length}</span>
            </div>
            <div className="ec-live-label">ACTIVE</div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="ec-controls">
        <button className="ec-btn ec-btn-enable" onClick={() => toggleGroup(true)} disabled={bulkLoading}>
          {bulkLoading ? <span className="ec-btn-spinner" /> : "✅"} Enable {selectedGroup === "ALL" ? "All" : selectedGroup}
        </button>
        <button className="ec-btn ec-btn-disable" onClick={() => toggleGroup(false)} disabled={bulkLoading}>
          {bulkLoading ? <span className="ec-btn-spinner" /> : "❌"} Disable {selectedGroup === "ALL" ? "All" : selectedGroup}
        </button>
        <div className="ec-searchbox">
          <span className="ec-search-icon">🔍</span>
          <input className="ec-search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search endpoints..." />
          {search && <button className="ec-clear-btn" onClick={() => setSearch("")}>✕</button>}
        </div>
        <div className="ec-count-badge">{filteredActive}/{filtered.length}</div>
      </div>

      {/* Group Cards — like reference image */}
      <div className="ec-groups">
        {groups.map(g => {
          const total = groupCounts[g] || 0;
          const active = groupActiveCount(g);
          const isActive = selectedGroup === g;
          const allOn = active === total;
          const dotColor = allOn ? "#22c55e" : active > 0 ? "#f59e0b" : "#ef4444";
          const icon = GROUP_ICONS[g] || "🔧";
          return (
            <div key={g} className={"ec-group-card" + (isActive ? " ec-group-card-active" : "")} onClick={() => setSelectedGroup(g)}>
              <div className="ec-group-card-shine" />
              <div className="ec-group-card-icon">{icon}</div>
              <div className="ec-group-card-name">{g}</div>
              <div className="ec-group-card-footer">
                <span className="ec-group-card-dot" style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}` }} />
                <span className="ec-group-card-count">{active}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Endpoint Grid */}
      {loading ? (
        <div className="ec-loading">
          <div className="ec-loading-ring"><div /><div /><div /><div /></div>
          <p>Loading endpoints from API schema...</p>
        </div>
      ) : (
        <div className="ec-grid">
          {filtered.map((item, i) => {
            const on = isEnabled(item.path, item.method);
            const busy = saving[item.path + "_" + item.method];
            const mc = METHOD_META[item.method] || METHOD_META.GET;
            return (
              <div key={i} className={"ec-card" + (on ? " ec-card-on" : " ec-card-off")} style={{ "--glow": mc.glow, "--border": mc.border, "--bg": mc.bg }}>
                <div className="ec-card-shine" />
                <div className="ec-card-line" style={{ background: `linear-gradient(90deg, transparent, ${mc.glow}99, transparent)` }} />
                <div className="ec-card-content">
                  <div className="ec-card-info">
                    <span className="ec-method-badge" style={{ background: mc.bg, color: mc.text, borderColor: mc.border, boxShadow: on ? `0 0 10px ${mc.glow}44` : "none" }}>
                      {item.method}
                    </span>
                    <span className="ec-path-text" title={item.path}>{item.path}</span>
                  </div>
                  <div className="ec-toggle-wrap" onClick={() => !busy && toggle(item)}>
                    <div className={"ec-toggle" + (on ? " on" : "")} style={on ? { background: mc.glow, boxShadow: `0 0 14px ${mc.glow}88` } : {}}>
                      <div className={"ec-knob" + (busy ? " busy" : "")} />
                    </div>
                  </div>
                </div>
                <div className="ec-card-status">
                  <span className="ec-status-pip" style={{ background: on ? mc.glow : "#374151", boxShadow: on ? `0 0 6px ${mc.glow}` : "none" }} />
                  <span className="ec-status-label" style={{ color: on ? mc.text : "#4b5563" }}>{busy ? "saving..." : on ? "ACTIVE" : "DISABLED"}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {toast && (
        <div className={"ec-toast" + (toast.type === "error" ? " err" : " ok")}>{toast.msg}</div>
      )}
    </div>
  );
}