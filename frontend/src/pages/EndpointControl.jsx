import React, { useState, useEffect, useMemo, useCallback } from "react";
import "./EndpointControl.css";
import axiosInstance from "../api/axiosInstance";

const METHOD_COLORS = {
  GET:    { bg: "rgba(10,31,77,0.9)",  text: "#3b9eff", border: "#1a4d8c", glow: "#3b9eff" },
  POST:   { bg: "rgba(10,42,20,0.9)",  text: "#00ff88", border: "#0d5a1f", glow: "#00ff88" },
  PUT:    { bg: "rgba(45,31,0,0.9)",   text: "#ff9500", border: "#7a4a00", glow: "#ff9500" },
  PATCH:  { bg: "rgba(30,10,64,0.9)",  text: "#b266ff", border: "#5a2090", glow: "#b266ff" },
  DELETE: { bg: "rgba(61,10,10,0.9)",  text: "#ff3355", border: "#8a0a1a", glow: "#ff3355" },
};

const ICONS = {
  auth:"\u{1F511}",users:"\u{1F465}",wallet:"\u{1F45B}",wallets:"\u{1F45B}",
  security:"\u{1F512}",notifications:"\u{1F514}",analytics:"\u{1F4CA}",
  "admin-panel":"\u2699\uFE0F","fraud-detection":"\u{1F6E1}\uFE0F",
  "fraud_detection":"\u{1F6E1}\uFE0F",backup:"\u{1F4BE}",tasks:"\u2705",
  kyc:"\u{1FAAA}",promotions:"\u{1F3AF}",offers:"\u{1F381}",
  gamification:"\u{1F3AE}",messaging:"\u{1F4AC}",referral:"\u{1F91D}",
  "rate-limit":"\u23F1\uFE0F",localization:"\u{1F30D}",cms:"\u{1F4DD}",
  "ad-networks":"\u{1F4E1}",ad_networks:"\u{1F4E1}","behavior-analytics":"\u{1F9E0}",
  audit_logs:"\u{1F4CB}",alerts:"\u{1F6A8}",engagement:"\u{1F4E3}",
  inventory:"\u{1F4E6}",loyalty:"\u2B50",djoyalty:"\u{1F3C6}",
  customers:"\u{1F465}",dashboard:"\u{1F4C8}",cache:"\u26A1",
  postback:"\u{1F504}",support:"\u{1F3A7}","version-control":"\u{1F516}",
  payment_gateways:"\u{1F4B0}","payout-queue":"\u{1F4E4}",subscription:"\u{1F4C5}",
  subscriptions:"\u{1F4C5}",profile:"\u{1F464}",withdrawals:"\u{1F4B8}",
  register:"\u{1F4CB}",login:"\u{1F510}",user:"\u{1F464}",
  GatewayTransactions:"\u{1F4B3}","auto-mod":"\u{1F916}","complete-ad":"\u2705",
  "my-payment-requests":"\u{1F4B0}","mylead-postback":"\u{1F504}",
  notices:"\u{1F4E2}","payment-history":"\u{1F4DC}","payment-request":"\u{1F4B3}",
};

const getIcon = (key) => ICONS[key] || "\u{1F527}";
const epKey = (method, path) => method + "::" + path;

const api = {
  loadSchema: async () => {
    const schemaEpSet = new Set();
    const groupMap = {};

    // Source 1: Django schema (auto-generated)
    try {
      const schemaRes = await axiosInstance.get("/schema/?format=json");
      const paths = schemaRes.data?.paths || {};
      Object.entries(paths).forEach(([p, methods]) => {
        const seg = p.replace(/^\/api\//, "").split("/");
        const key = seg[0] || "root";
        // Skip regex/invalid keys from Django URL patterns
        if (!key || /[\^\(\)\[\]\?\+\*]/.test(key) || key.includes("<")) return;
        if (!groupMap[key]) groupMap[key] = [];
        Object.keys(methods).forEach(m => {
          const mu = m.toUpperCase();
          if (["GET","POST","PUT","PATCH","DELETE"].includes(mu)) {
            const k = mu + "::" + p;
            if (!schemaEpSet.has(k)) {
              schemaEpSet.add(k);
              groupMap[key].push({ method: mu, path: p, source: "schema" });
            }
          }
        });
      });
    } catch(e) { console.warn("schema load failed", e); }

    // Source 2: Local JSON (management command export)
    try {
      const localRes = await fetch("/all_endpoints.json");
      const localGroups = await localRes.json();
      localGroups.forEach(g => {
        if (!groupMap[g.key]) groupMap[g.key] = [];
        (g.endpoints || []).forEach(ep => {
          const k = ep.method + "::" + ep.path;
          if (!schemaEpSet.has(k)) {
            schemaEpSet.add(k);
            groupMap[g.key].push({ method: ep.method, path: ep.path, source: "local" });
          } else {
            let found = false;
            for (const grpKey of Object.keys(groupMap)) {
              const ex = groupMap[grpKey].find(e => e.method === ep.method && e.path === ep.path);
              if (ex) { ex.source = "both"; found = true; break; }
            }
            if (!found) groupMap[g.key].push({ method: ep.method, path: ep.path, source: "both" });
          }
        });
      });
    } catch(e) { console.warn("local JSON load failed", e); }

    const groups = Object.entries(groupMap)
      .sort(([a],[b]) => a.localeCompare(b))
      .map(([key, eps]) => ({
        key,
        label: key.replace(/-/g," ").replace(/_/g," "),
        icon: getIcon(key),
        count: eps.length,
        endpoints: eps,
      }));

    const allEndpoints = groups.flatMap(g =>
      g.endpoints.map(ep => ({
        ...ep, group: g.key, groupLabel: g.label, icon: g.icon
      }))
    );

    return { groups, allEndpoints };
  },

  loadToggles: async () => {
    let all = [], page = 1, hasMore = true;
    while (hasMore) {
      const res = await axiosInstance.get(
        `/admin-panel/endpoint-toggles/?limit=500&offset=${(page-1)*500}`
      );
      const data = res.data;
      const items = Array.isArray(data) ? data : (data.results || []);
      all = all.concat(items);
      const total = data.count || items.length;
      hasMore = !Array.isArray(data) && all.length < total;
      page++;
      if (page > 20) break;
    }
    const map = {};
    all.forEach(t => { map[epKey(t.method, t.path)] = { id: t.id, is_enabled: t.is_enabled }; });
    return map;
  },

  patch: async (id, is_enabled) => {
    const r = await axiosInstance.patch(`/admin-panel/endpoint-toggles/${id}/`, { is_enabled });
    return r.data;
  },

  create: async (payload) => {
    const r = await axiosInstance.post("/admin-panel/endpoint-toggles/", payload);
    return r.data;
  },

  bulk: async (toggles) => {
    for (let i = 0; i < toggles.length; i += 200) {
      await axiosInstance.post("/admin-panel/endpoint-toggles/bulk-toggle/", {
        toggles: toggles.slice(i, i + 200)
      });
    }
  },
};

function Toggle({ on, busy, onToggle }) {
  return (
    <div
      className={"ec-sw " + (on ? "ec-sw--on" : "")}
      style={{ cursor: busy ? "wait" : "pointer", opacity: busy ? 0.6 : 1 }}
      onClick={() => !busy && onToggle()}
    >
      <div className="ec-sw-knob" />
    </div>
  );
}

function Badge({ method }) {
  const c = METHOD_COLORS[method] || METHOD_COLORS.GET;
  return (
    <span
      className="ec-badge"
      style={{ background: c.bg, color: c.text, borderColor: c.border, boxShadow: `0 0 6px ${c.glow}44` }}
    >
      {method}
    </span>
  );
}

const SRC_STYLE = {
  schema: { color: "#22d3ee", bg: "#22d3ee22", border: "#22d3ee44", label: "SCHEMA" },
  local:  { color: "#f59e0b", bg: "#f59e0b22", border: "#f59e0b44", label: "LOCAL"  },
  both:   { color: "#a78bfa", bg: "#a78bfa22", border: "#a78bfa44", label: "BOTH"   },
};

export default function EndpointControl() {
  const [groups,       setGroups]       = useState([]);
  const [allEndpoints, setAllEndpoints] = useState([]);
  const [epStates,     setEpStates]     = useState({});
  const [loading,      setLoading]      = useState(true);
  const [loadMsg,      setLoadMsg]      = useState("Loading...");
  const [saving,       setSaving]       = useState({});
  const [toast,        setToast]        = useState(null);
  const [tab,          setTab]          = useState("groups");
  const [search,       setSearch]       = useState("");
  const [mFilter,      setMFilter]      = useState("ALL");
  const [gFilter,      setGFilter]      = useState("ALL");
  const [selGroup,     setSelGroup]     = useState(null);
  const [srcFilter,    setSrcFilter]    = useState("ALL");
  const [page,         setPage]         = useState(1);
  const PG = 60;

  const showToast = useCallback((msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        setLoadMsg("Loading schema...");
        const { groups, allEndpoints } = await api.loadSchema();
        setGroups(groups);
        setAllEndpoints(allEndpoints);
        setLoadMsg("Loading toggle states...");
        const map = await api.loadToggles();
        setEpStates(map);
        showToast("Loaded " + allEndpoints.length + " endpoints from " + groups.length + " groups");
      } catch(e) {
        showToast("Load error: " + e.message, "error");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const isOn = (method, path) => epStates[epKey(method, path)]?.is_enabled !== false;

  const doToggle = async (ep) => {
    const k = epKey(ep.method, ep.path);
    const next = !isOn(ep.method, ep.path);
    setSaving(p => ({ ...p, [k]: true }));
    try {
      const ex = epStates[k];
      let r;
      if (ex?.id) {
        r = await api.patch(ex.id, next);
      } else {
        r = await api.create({
          path: ep.path, method: ep.method,
          group: ep.group, label: ep.groupLabel || ep.path,
          is_enabled: next,
          disabled_message: "This feature is temporarily disabled.",
        });
      }
      setEpStates(p => ({ ...p, [k]: { id: r.id, is_enabled: next } }));
      showToast((next ? "\u2713 ENABLED" : "\u2715 DISABLED") + ": " + ep.method + " " + ep.path);
    } catch(e) {
      showToast("Error: " + e.message, "error");
    } finally {
      setSaving(p => ({ ...p, [k]: false }));
    }
  };

  const doBulk = async (eps, label, next) => {
    try {
      await api.bulk(eps.map(ep => ({
        path: ep.path, method: ep.method,
        group: ep.group || ep.key, label: ep.groupLabel || label,
        is_enabled: next,
        disabled_message: next ? "Feature enabled." : "This feature is temporarily disabled.",
      })));
      setEpStates(p => {
        const n = { ...p };
        eps.forEach(ep => {
          n[epKey(ep.method, ep.path)] = { ...p[epKey(ep.method, ep.path)], is_enabled: next };
        });
        return n;
      });
      showToast((next ? "\u2713 ENABLED: " : "\u2715 DISABLED: ") + label);
    } catch(e) {
      showToast("Bulk error: " + e.message, "error");
    }
  };

  const doAll   = n => doBulk(allEndpoints, "All " + allEndpoints.length + " Endpoints", n);
  const doGroup = (g, n) => doBulk(
    g.endpoints.map(ep => ({ ...ep, group: g.key, groupLabel: g.label })), g.label, n
  );

  const totalActive = useMemo(
    () => allEndpoints.filter(ep => isOn(ep.method, ep.path)).length,
    [epStates, allEndpoints]
  );

  const gActive = g => g.endpoints.filter(ep => isOn(ep.method, ep.path)).length;
  const selGData = selGroup ? groups.find(g => g.key === selGroup) : null;

  const filtGroups = useMemo(() =>
    groups.filter(g =>
      g.label.toLowerCase().includes(search.toLowerCase()) ||
      g.key.toLowerCase().includes(search.toLowerCase())
    ), [groups, search]);

  const drillEps = useMemo(() => {
    if (!selGData) return [];
    return selGData.endpoints.filter(ep =>
      (mFilter === "ALL" || ep.method === mFilter) &&
      (srcFilter === "ALL" || ep.source === srcFilter || ep.source === "both") &&
      (ep.path.toLowerCase().includes(search.toLowerCase()) ||
       ep.method.toLowerCase().includes(search.toLowerCase()))
    );
  }, [selGData, search, mFilter, srcFilter]);

  const filtAll = useMemo(() =>
    allEndpoints.filter(ep =>
      (mFilter === "ALL" || ep.method === mFilter) &&
      (gFilter === "ALL" || ep.group === gFilter) &&
      (srcFilter === "ALL" || ep.source === srcFilter || ep.source === "both") &&
      (ep.path.toLowerCase().includes(search.toLowerCase()) ||
       ep.method.toLowerCase().includes(search.toLowerCase()) ||
       (ep.groupLabel||"").toLowerCase().includes(search.toLowerCase()))
    ), [allEndpoints, search, mFilter, gFilter, srcFilter]);

  const pages = Math.ceil(filtAll.length / PG);
  const paged = filtAll.slice((page-1)*PG, page*PG);
  useEffect(() => setPage(1), [search, mFilter, gFilter, srcFilter]);

  const EpCard = ({ ep }) => {
    const on   = isOn(ep.method, ep.path);
    const busy = !!saving[epKey(ep.method, ep.path)];
    const mc   = METHOD_COLORS[ep.method] || METHOD_COLORS.GET;
    const src  = SRC_STYLE[ep.source] || SRC_STYLE.schema;
    return (
      <div
        className={"ec-ep-card" + (on ? " ec-ep-on" : " ec-ep-off")}
        style={{ borderColor: on ? mc.border : "#2a0808", boxShadow: on ? `0 0 12px ${mc.glow}22` : "none" }}
      >
        <div className="ec-ep-left">
          <Badge method={ep.method} />
          <span className="ec-ep-path" title={ep.path}>{ep.path}</span>
          <span style={{
            fontSize:"9px", padding:"2px 5px", borderRadius:"4px",
            background: src.bg, color: src.color, border: "1px solid " + src.border,
            flexShrink: 0, fontFamily: "monospace", letterSpacing: "0.05em",
          }}>{src.label}</span>
        </div>
        <div className="ec-ep-right">
          <span className="ec-ep-status" style={{ color: on ? "#00ff88" : "#ff3355" }}>
            <span className="ec-dot" style={{
              background: on ? "#00ff88" : "#ff3355",
              boxShadow: `0 0 8px ${on ? "#00ff88" : "#ff3355"}`
            }}/>
            {on ? "ACTIVE" : "DISABLED"}
          </span>
          <Toggle on={on} busy={busy} onToggle={() => doToggle(ep)} />
        </div>
      </div>
    );
  };

  const GroupCard = ({ group }) => {
    const active = gActive(group);
    const total  = group.count;
    const allOn  = active === total && total > 0;
    const allOff = active === 0;
    const col    = allOn ? "#00ff88" : allOff ? "#ff3355" : "#ff9500";
    const pct    = total > 0 ? Math.round((active / total) * 100) : 100;
    return (
      <div
        className={"ec-gcard" + (allOn ? " ec-gcard--on" : allOff ? " ec-gcard--off" : " ec-gcard--partial")}
        style={{ "--glow": col }}
        onClick={() => group.endpoints.length > 0 && setSelGroup(group.key)}
      >
        <div className="ec-gcard-shine" />
        <div className="ec-gcard-bar" style={{ background: col, boxShadow: `0 0 8px ${col}` }} />
        <div className="ec-gcard-icon">{group.icon}</div>
        <div className="ec-gcard-name">{group.key}</div>
        <div className="ec-gcard-foot">
          <span className="ec-gcard-dot" style={{ background: col, boxShadow: `0 0 6px ${col}` }} />
          <span className="ec-gcard-count" style={{ color: col }}>{active}</span>
        </div>
        <div className="ec-gcard-btns" onClick={e => e.stopPropagation()}>
          <button
            className={"ec-gcard-btn ec-gcard-btn--on" + (allOn ? " ec-gcard-btn--active" : "")}
            title="Enable all endpoints in this group"
            onClick={() => doGroup(group, true)}
          >ON</button>
          <button
            className={"ec-gcard-btn ec-gcard-btn--off" + (allOff ? " ec-gcard-btn--active" : "")}
            title="Disable all endpoints in this group"
            onClick={() => doGroup(group, false)}
          >OFF</button>
        </div>
        <svg className="ec-gcard-arc" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2.5" />
          <circle cx="18" cy="18" r="15" fill="none"
            stroke={col} strokeWidth="2.5"
            strokeDasharray={`${pct * 0.942} 94.2`}
            strokeLinecap="round" transform="rotate(-90 18 18)"
            style={{ filter: `drop-shadow(0 0 3px ${col})` }}
          />
        </svg>
      </div>
    );
  };

  return (
    <div className="ec-root">
      <div className="ec-header">
        <div className="ec-header-l">
          <div className="ec-hicon">&#x26A1;</div>
          <div>
            <h1 className="ec-htitle">API Endpoint Control</h1>
            <p className="ec-hsub">
              {loading ? loadMsg : `Live control over all ${allEndpoints.length} API endpoints`}
            </p>
          </div>
        </div>
        <div className="ec-hbadge">
          <span className="ec-hbadge-dot" style={{
            background: loading ? "#ff9500" :
              totalActive === allEndpoints.length ? "#00ff88" :
              totalActive === 0 ? "#ff3355" : "#ff9500"
          }} />
          <div>
            <div className="ec-hnum">{loading ? "..." : `${totalActive} / ${allEndpoints.length}`}</div>
            <div className="ec-hlbl">{loading ? "LOADING" : "ACTIVE"}</div>
          </div>
        </div>
      </div>

      <div className="ec-tabs">
        {[
          ["groups",    "&#x1F5C2; GROUP VIEW",    groups.length,      "ALL"],
          ["endpoints", "&#x1F50C; ALL ENDPOINTS", allEndpoints.length,"ALL"],
          ["schema",    "&#x2601; SCHEMA",          allEndpoints.filter(e=>e.source==="schema"||e.source==="both").length, "schema"],
          ["local",     "&#x1F4C4; LOCAL JSON",     allEndpoints.filter(e=>e.source==="local"||e.source==="both").length,  "local"],
        ].map(([id, lbl, cnt, src]) => (
          <button key={id}
            className={"ec-tab" + (tab === id ? " ec-tab--on" : "")}
            onClick={() => {
              setTab(id); setSrcFilter(src);
              setSelGroup(null); setSearch(""); setMFilter("ALL"); setGFilter("ALL");
            }}
            dangerouslySetInnerHTML={{ __html: lbl + ' <span class="ec-tab-n">' + cnt + '</span>' }}
          />
        ))}
      </div>

      <div className="ec-bar">
        <button className="ec-btn ec-btn-en"  onClick={() => doAll(true)}>&#x2713; Enable All</button>
        <button className="ec-btn ec-btn-dis" onClick={() => doAll(false)}>&#x2715; Disable All</button>

        {tab === "groups" && selGData && (<>
          <button className="ec-btn ec-btn-gen"  onClick={() => doGroup(selGData, true)}>&#x2713; Group ON</button>
          <button className="ec-btn ec-btn-gdis" onClick={() => doGroup(selGData, false)}>&#x2715; Group OFF</button>
          <button className="ec-btn ec-btn-back"
            onClick={() => { setSelGroup(null); setSearch(""); setMFilter("ALL"); }}>
            &#x2190; BACK
          </button>
        </>)}

        <div className="ec-mf">
          {["ALL","GET","POST","PUT","PATCH","DELETE"].map(m => {
            const mc = METHOD_COLORS[m];
            return (
              <button key={m}
                className={"ec-mfb" + (mFilter === m ? " ec-mfb--on" : "")}
                style={mFilter === m && m !== "ALL"
                  ? { color: mc.text, borderColor: mc.border, background: mc.bg } : {}}
                onClick={() => setMFilter(m)}
              >{m}</button>
            );
          })}
        </div>

        {tab === "endpoints" && (
          <select className="ec-sel" value={gFilter} onChange={e => setGFilter(e.target.value)}>
            <option value="ALL">ALL GROUPS</option>
            {groups.map(g => (
              <option key={g.key} value={g.key}>{g.label.toUpperCase()}</option>
            ))}
          </select>
        )}

        <div className="ec-srch">
          <span className="ec-srch-ic">&#x2315;</span>
          <input className="ec-srch-inp" value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search endpoints..." />
        </div>
      </div>

      {loading ? (
        <div className="ec-load">
          <div className="ec-spin" />
          <span className="ec-load-txt">{loadMsg.toUpperCase()}</span>
        </div>

      ) : tab === "groups" && !selGData ? (
        <div className="ec-ggrid">
          {filtGroups.map(g => <GroupCard key={g.key} group={g} />)}
        </div>

      ) : tab === "groups" && selGData ? (
        <div>
          <div className="ec-drill-hd">
            <span style={{ fontSize: 34 }}>{selGData.icon}</span>
            <div>
              <h2 className="ec-drill-title">{selGData.label.toUpperCase()}</h2>
              <span className="ec-drill-sub">
                {gActive(selGData)} / {selGData.count} ACTIVE
                {search && ` \u2014 ${drillEps.length} results`}
              </span>
            </div>
          </div>
          <div className="ec-epgrid">
            {drillEps.map((ep, i) => (
              <EpCard key={i} ep={{ ...ep, group: selGData.key, groupLabel: selGData.label }} />
            ))}
            {drillEps.length === 0 && <div className="ec-empty">NO ENDPOINTS MATCH</div>}
          </div>
        </div>

      ) : (tab === "endpoints" || tab === "schema" || tab === "local") ? (
        <div>
          <div className="ec-ep-info">
            SHOWING <strong>{filtAll.length}</strong> OF {allEndpoints.length} ENDPOINTS
            {pages > 1 && <span> \u2014 PAGE {page}/{pages}</span>}
          </div>
          <div className="ec-epgrid">
            {paged.map((ep, i) => <EpCard key={i} ep={ep} />)}
          </div>
          {pages > 1 && (
            <div className="ec-pag">
              <button className="ec-pb" disabled={page===1} onClick={() => setPage(1)}>&laquo;</button>
              <button className="ec-pb" disabled={page===1} onClick={() => setPage(p => p-1)}>&lsaquo;</button>
              {Array.from({ length: Math.min(7, pages) }, (_, i) => {
                const p = page <= 4 ? i+1 : page+i-3;
                if (p < 1 || p > pages) return null;
                return (
                  <button key={p}
                    className={"ec-pb" + (p === page ? " ec-pb--on" : "")}
                    onClick={() => setPage(p)}>{p}</button>
                );
              })}
              <button className="ec-pb" disabled={page===pages} onClick={() => setPage(p => p+1)}>&rsaquo;</button>
              <button className="ec-pb" disabled={page===pages} onClick={() => setPage(pages)}>&raquo;</button>
            </div>
          )}
        </div>
      ) : null}

      {toast && (
        <div className={"ec-toast" + (toast.type === "error" ? " ec-toast--err" : " ec-toast--ok")}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
