import React, { useState, useEffect } from "react";
const API_BASE = "https://earning-backend-c-production.up.railway.app/api";
const getToken = () => localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || "";
const apiFetch = async (path, options = {}) => {
  const res = await fetch(API_BASE + path, { ...options, headers: { "Content-Type": "application/json", Authorization: "Bearer " + getToken(), ...(options.headers || {}) } });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
};
const SYSTEMS = [
  { key: "registration", label: "User Registration", icon: "U", path: "/api/auth/register/", method: "POST" },
  { key: "withdrawal", label: "Withdrawal", icon: "W", path: "/api/wallet/", method: "ALL" },
  { key: "kyc", label: "KYC", icon: "K", path: "/api/kyc/", method: "ALL" },
  { key: "referral", label: "Referral", icon: "R", path: "/api/referral/", method: "ALL" },
  { key: "tasks", label: "Tasks", icon: "T", path: "/api/tasks/", method: "ALL" },
  { key: "offers", label: "Offers", icon: "O", path: "/api/offers/", method: "ALL" },
  { key: "notifications", label: "Notifications", icon: "N", path: "/api/notifications/", method: "ALL" },
  { key: "payments", label: "Payments", icon: "P", path: "/api/payment_gateways/", method: "ALL" },
  { key: "promotions", label: "Promotions", icon: "PR", path: "/api/promotions/", method: "ALL" },
  { key: "subscription", label: "Subscription", icon: "S", path: "/api/subscription/", method: "ALL" },
  { key: "gamification", label: "Gamification", icon: "G", path: "/api/gamification/", method: "ALL" },
  { key: "support", label: "Support", icon: "SP", path: "/api/support/", method: "ALL" },
  { key: "messaging", label: "Messaging", icon: "M", path: "/api/messaging/", method: "ALL" },
  { key: "cms", label: "CMS", icon: "C", path: "/api/cms/", method: "ALL" },
  { key: "security", label: "Security", icon: "SC", path: "/api/security/", method: "ALL" },
  { key: "fraud", label: "Fraud Detection", icon: "F", path: "/api/fraud-detection/", method: "ALL" },
  { key: "backup", label: "Backup", icon: "B", path: "/api/backup/", method: "ALL" },
  { key: "audit", label: "Audit Logs", icon: "A", path: "/api/audit_logs/", method: "ALL" },
  { key: "localization", label: "Localization", icon: "L", path: "/api/localization/", method: "ALL" },
  { key: "rate_limit", label: "Rate Limiting", icon: "RL", path: "/api/rate-limit/", method: "ALL" },
  { key: "version", label: "Version Control", icon: "V", path: "/api/version-control/", method: "ALL" },
  { key: "inventory", label: "Inventory", icon: "I", path: "/api/inventory/", method: "ALL" },
  { key: "payout_queue", label: "Payout Queue", icon: "PQ", path: "/api/payout-queue/", method: "ALL" },
  { key: "postback", label: "Postback", icon: "PB", path: "/api/postback/", method: "ALL" },
  { key: "engagement", label: "Engagement", icon: "E", path: "/api/engagement/", method: "ALL" },
  { key: "behavior", label: "Behavior Analytics", icon: "BA", path: "/api/behavior-analytics/", method: "ALL" },
  { key: "djoyalty", label: "Loyalty Program", icon: "LP", path: "/api/djoyalty/", method: "ALL" },
  { key: "ad_networks", label: "Ad Networks", icon: "AD", path: "/api/ad-networks/", method: "ALL" },
  { key: "auto_mod", label: "Auto Moderation", icon: "AM", path: "/api/auto-mod/", method: "ALL" },
  { key: "cache", label: "Cache System", icon: "CA", path: "/api/cache/", method: "ALL" },
  { key: "alerts", label: "Alerts", icon: "AL", path: "/api/alerts/", method: "ALL" },
  { key: "analytics", label: "Analytics", icon: "AN", path: "/api/analytics/", method: "ALL" },
  { key: "ad_network2", label: "Ad Network (Alt)", icon: "AD2", path: "/api/ad_networks/", method: "ALL" },
];
export default function EndpointControl() {
  const [states, setStates] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState("");
  const [customPath, setCustomPath] = useState("");
  const [customMethod, setCustomMethod] = useState("ALL");
  const [showCustom, setShowCustom] = useState(false);
  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };
  useEffect(() => {
    apiFetch("/admin-panel/endpoint-toggles/").then(data => {
      const results = data.results || (Array.isArray(data) ? data : []);
      const s = {};
      results.forEach(t => { s[t.path + "_" + t.method] = { id: t.id, is_enabled: t.is_enabled }; });
      setStates(s);
    }).catch(() => showToast("Could not load states", "error")).finally(() => setLoading(false));
  }, []);
  const isEnabled = (path, method) => states[path + "_" + method]?.is_enabled !== false;
  const toggle = async (item) => {
    const key = item.path + "_" + item.method;
    const newState = !isEnabled(item.path, item.method);
    setSaving(p => ({ ...p, [key]: true }));
    try {
      const existing = states[key];
      let result;
      if (existing?.id) {
        result = await apiFetch("/admin-panel/endpoint-toggles/" + existing.id + "/", { method: "PATCH", body: JSON.stringify({ is_enabled: newState }) });
      } else {
        result = await apiFetch("/admin-panel/endpoint-toggles/", { method: "POST", body: JSON.stringify({ path: item.path, method: item.method, group: item.key, label: item.label, is_enabled: newState, disabled_message: "This feature is temporarily disabled." }) });
      }
      setStates(p => ({ ...p, [key]: { id: result.id, is_enabled: newState } }));
      showToast(item.label + (newState ? " Enabled" : " Disabled"));
    } catch { showToast("Failed!", "error"); }
    finally { setSaving(p => ({ ...p, [key]: false })); }
  };
  const toggleAll = async (enabled) => {
    try {
      const toggles = SYSTEMS.map(t => ({ path: t.path, method: t.method, group: t.key, label: t.label, is_enabled: enabled, message: "System maintenance." }));
      await apiFetch("/admin-panel/endpoint-toggles/bulk_toggle/", { method: "POST", body: JSON.stringify({ toggles }) });
      const ns = {};
      SYSTEMS.forEach(t => { ns[t.path + "_" + t.method] = { ...states[t.path + "_" + t.method], is_enabled: enabled }; });
      setStates(p => ({ ...p, ...ns }));
      showToast(enabled ? "All Enabled" : "All Disabled");
    } catch { showToast("Failed!", "error"); }
  };
  const addCustom = async () => {
    if (!customPath) return;
    await toggle({ path: customPath, method: customMethod, key: "custom", label: customPath });
    setCustomPath(""); setShowCustom(false);
  };
  const filtered = SYSTEMS.filter(t => t.label.toLowerCase().includes(search.toLowerCase()) || t.path.includes(search));
  const activeCount = SYSTEMS.filter(t => isEnabled(t.path, t.method)).length;
  const S = { bg: "#020817", card: "#0a1628", border: "#1e293b", text: "#e2e8f0", muted: "#64748b" };
  return (
    <div style={{ background: S.bg, minHeight: "100vh", color: S.text, fontFamily: "Inter,sans-serif", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#fff" }}>System Control Panel</h1>
          <p style={{ margin: "4px 0 0", color: S.muted, fontSize: 13 }}>Turn any system on or off instantly</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: S.card, padding: "8px 14px", borderRadius: 8, border: "1px solid " + S.border }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: activeCount === SYSTEMS.length ? "#22c55e" : activeCount === 0 ? "#ef4444" : "#f59e0b" }} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>{activeCount}/{SYSTEMS.length} Active</span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={() => toggleAll(true)} style={{ padding: "7px 14px", background: "#16a34a", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>Enable All</button>
        <button onClick={() => toggleAll(false)} style={{ padding: "7px 14px", background: "#dc2626", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>Disable All</button>
        <button onClick={() => setShowCustom(!showCustom)} style={{ padding: "7px 14px", background: "#7c3aed", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>+ Custom</button>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." style={{ padding: "7px 12px", background: S.card, border: "1px solid " + S.border, borderRadius: 7, color: S.text, fontSize: 13 }} />
      </div>
      {showCustom && (
        <div style={{ background: S.card, border: "1px solid #7c3aed", borderRadius: 8, padding: 14, marginBottom: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input value={customPath} onChange={e => setCustomPath(e.target.value)} placeholder="/api/custom/" style={{ padding: "7px 12px", background: S.bg, border: "1px solid " + S.border, borderRadius: 7, color: S.text, fontSize: 13, flex: 1 }} />
          <select value={customMethod} onChange={e => setCustomMethod(e.target.value)} style={{ padding: "7px 12px", background: S.bg, border: "1px solid " + S.border, borderRadius: 7, color: S.text, fontSize: 13 }}>
            {["ALL","GET","POST","PUT","PATCH","DELETE"].map(m => <option key={m}>{m}</option>)}
          </select>
          <button onClick={addCustom} style={{ padding: "7px 14px", background: "#7c3aed", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600 }}>Disable</button>
        </div>
      )}
      {loading ? <div style={{ textAlign: "center", padding: 60, color: S.muted }}>Loading...</div> : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 10 }}>
          {filtered.map(item => {
            const on = isEnabled(item.path, item.method);
            const busy = saving[item.path + "_" + item.method];
            return (
              <div key={item.key} style={{ background: S.card, border: "1px solid " + (on ? "#1e3a5f" : "#7f1d1d"), borderRadius: 10, padding: "13px 15px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: on ? S.text : S.muted }}>{item.label}</div>
                  <div style={{ fontSize: 10, color: "#334155", marginTop: 2 }}>{item.method} {item.path}</div>
                </div>
                <div onClick={() => !busy && toggle(item)} style={{ width: 42, height: 22, borderRadius: 11, cursor: busy ? "not-allowed" : "pointer", background: on ? "#16a34a" : "#374151", position: "relative", transition: "background 0.2s", flexShrink: 0 }}>
                  <div style={{ position: "absolute", top: 2, left: on ? 21 : 2, width: 18, height: 18, borderRadius: "50%", background: "#fff", transition: "left 0.2s" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {toast && <div style={{ position: "fixed", bottom: 24, right: 24, zIndex: 9999, background: toast.type === "error" ? "#7f1d1d" : "#14532d", color: "#fff", padding: "12px 20px", borderRadius: 10, fontSize: 14, fontWeight: 500 }}>{toast.msg}</div>}
    </div>
  );
}
