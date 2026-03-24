// src/components/common/PageEndpointPanel.jsx
// Drop-in endpoint control panel for any page
import React, { useState } from "react";
import { useEndpointToggle } from "../../hooks/useEndpointToggle";
import "./PageEndpointPanel.css";

const METHOD_COLORS = {
  GET:    { bg: "rgba(10,31,77,0.9)",  text: "#3b9eff", border: "#1a4d8c" },
  POST:   { bg: "rgba(10,42,20,0.9)",  text: "#00ff88", border: "#0d5a1f" },
  PUT:    { bg: "rgba(45,31,0,0.9)",   text: "#ff9500", border: "#7a4a00" },
  PATCH:  { bg: "rgba(30,10,64,0.9)",  text: "#b266ff", border: "#5a2090" },
  DELETE: { bg: "rgba(61,10,10,0.9)",  text: "#ff3355", border: "#8a0a1a" },
};

export default function PageEndpointPanel({ pageGroups = [], title = "API Endpoints" }) {
  const [open, setOpen]         = useState(false);
  const [search, setSearch]     = useState("");
  const [mFilter, setMFilter]   = useState("ALL");
  const { loading, saving, isOn, toggle, bulkToggle } = useEndpointToggle(pageGroups);

  // Flatten all endpoints for this page
  const allEps = pageGroups.flatMap(g =>
    g.endpoints.map(ep => ({ ...ep, group: g.key, groupLabel: g.label }))
  );

  const filtered = allEps.filter(ep =>
    (mFilter === "ALL" || ep.method === mFilter) &&
    (ep.path.toLowerCase().includes(search.toLowerCase()) ||
     ep.method.toLowerCase().includes(search.toLowerCase()))
  );

  const activeCount = allEps.filter(ep => isOn(ep.method, ep.path)).length;
  const totalCount  = allEps.length;
  const allOn       = activeCount === totalCount && totalCount > 0;

  return (
    <div className="pep-wrap">
      {/* Toggle button */}
      <button className={"pep-toggle-btn" + (allOn ? " pep-btn--on" : " pep-btn--off")}
        onClick={() => setOpen(o => !o)}>
        <span className="pep-dot"
          style={{ background: allOn ? "#00ff88" : activeCount === 0 ? "#ff3355" : "#ff9500" }} />
        <span className="pep-btn-txt">
          {title} — {activeCount}/{totalCount} ACTIVE
        </span>
        <span className="pep-arrow">{open ? "▲" : "▼"}</span>
      </button>

      {/* Panel */}
      {open && (
        <div className="pep-panel">
          {/* Panel header */}
          <div className="pep-panel-hd">
            <div className="pep-panel-actions">
              <button className="pep-act-btn pep-en"
                onClick={() => bulkToggle(allEps, true)}>✓ Enable All</button>
              <button className="pep-act-btn pep-dis"
                onClick={() => bulkToggle(allEps, false)}>✕ Disable All</button>
            </div>
            <div className="pep-filters">
              {["ALL","GET","POST","PUT","PATCH","DELETE"].map(m => (
                <button key={m}
                  className={"pep-mf" + (mFilter === m ? " pep-mf--on" : "")}
                  style={mFilter === m && m !== "ALL"
                    ? { color: METHOD_COLORS[m].text, borderColor: METHOD_COLORS[m].border,
                        background: METHOD_COLORS[m].bg } : {}}
                  onClick={() => setMFilter(m)}>{m}</button>
              ))}
              <input className="pep-search" value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search..." />
            </div>
          </div>

          {/* Endpoint list */}
          {loading ? (
            <div className="pep-loading">Loading...</div>
          ) : (
            <div className="pep-list">
              {filtered.map((ep, i) => {
                const on   = isOn(ep.method, ep.path);
                const busy = !!saving[ep.method + "::" + ep.path];
                const mc   = METHOD_COLORS[ep.method] || METHOD_COLORS.GET;
                return (
                  <div key={i} className={"pep-ep" + (on ? " pep-ep--on" : " pep-ep--off")}
                    style={{ borderColor: on ? mc.border : "#2a0808" }}>
                    <span className="pep-badge"
                      style={{ background: mc.bg, color: mc.text, borderColor: mc.border }}>
                      {ep.method}
                    </span>
                    <span className="pep-path" title={ep.path}>{ep.path}</span>
                    <div className="pep-right">
                      <span className="pep-status"
                        style={{ color: on ? "#00ff88" : "#ff3355" }}>
                        <span className="pep-sdot"
                          style={{ background: on ? "#00ff88" : "#ff3355" }} />
                        {on ? "ON" : "OFF"}
                      </span>
                      <div className={"pep-sw" + (on ? " pep-sw--on" : "")}
                        style={{ cursor: busy ? "wait" : "pointer", opacity: busy ? 0.6 : 1 }}
                        onClick={() => !busy && toggle(ep)}>
                        <div className="pep-sw-k" />
                      </div>
                    </div>
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <div className="pep-empty">No endpoints found</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
