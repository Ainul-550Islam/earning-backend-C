const _BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace('/api','');
// src/pages/Promotions.jsx
// EarnNexus — Promotions Management Page
// Real API calls via React Query + axios
// Matches design: Space-purple cyberpunk, promo cards with sparklines

import { useState, useEffect, useRef, useCallback } from "react";
import useAuth from "../hooks/useAuth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import "../styles/promotions.css";

// ============================================================
// API CLIENT — reuse your project's axios instance
// ============================================================
import axios from "axios";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

const API = axios.create({ baseURL: (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api") });

// Attach access token from localStorage/sessionStorage
API.interceptors.request.use(cfg => {
  const token = localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// ============================================================
// API FUNCTIONS
// ============================================================
const promotionsApi = {
  // GET /api/promotions/?type=all&search=...&page=1
  list: (params) => API.get("/promotions/", { params }).then(r => r.data),

  // GET /api/promotions/stats/
  stats: () => API.get("/promotions/stats/").then(r => r.data),

  // POST /api/promotions/
  create: (data) => API.post("/promotions/quick-create/", data).then(r => r.data),

  // PUT /api/promotions/:id/
  update: (id, data) => API.put(`/promotions/quick-update/${id}/`, data).then(r => r.data),

  // DELETE /api/promotions/:id/
  delete: (id) => API.delete(`/promotions/quick-delete/${id}/`).then(r => r.data),

  // POST /api/promotions/:id/pause/
  pause: (id) => API.post(`/promotions/campaigns/${id}/pause/`).then(r => r.data),

  // POST /api/promotions/:id/resume/
  resume: (id) => API.post(`/promotions/campaigns/${id}/resume/`).then(r => r.data),

  // GET /api/promotions/:id/sparkline/?days=7
  sparkline: (id) => API.get(`/promotions/${id}/sparkline/`, { params: { days: 7 } }).then(r => r.data),
};

// ============================================================
// QUERY KEYS
// ============================================================
const QK = {
  promos:   (f) => ["promotions", "list", f],
  stats:    ()  => ["promotions", "stats"],
  sparkline:(id)=> ["promotions", "sparkline", id],
};

// ============================================================
// RISK CONFIG
// ============================================================
const RISK = {
  LOW:    { color: "#00e5ff", label: "LOW",    bg: "rgba(0,229,255,.08)",  border: "rgba(0,229,255,.28)"  },
  SAFE:   { color: "#00ff99", label: "SAFE",   bg: "rgba(0,255,153,.08)",  border: "rgba(0,255,153,.28)"  },
  MEDIUM: { color: "#ffcc00", label: "MEDIUM", bg: "rgba(255,204,0,.07)",  border: "rgba(255,204,0,.28)"  },
  HIGH:   { color: "#ff5500", label: "HIGH",   bg: "rgba(255,85,0,.08)",   border: "rgba(255,85,0,.3)"    },
};

// ============================================================
// CARD BORDER COLORS — by column position (0=left,1=center,2=right)
// image: left=cyan, center=cyan/blue, right=orange gradient
// ============================================================
const CARD_BORDERS = [
  { border:"rgba(0,229,255,.42)",  shadow:"rgba(0,229,255,.16)",  inner:"rgba(0,229,255,.06)",  glow:"#00e5ff" }, // left  — cyan
  { border:"rgba(0,160,255,.42)",  shadow:"rgba(0,160,255,.16)",  inner:"rgba(0,160,255,.06)",  glow:"#00a0ff" }, // center — blue
  { border:"rgba(255,120,0,.48)",  shadow:"rgba(255,120,0,.20)",  inner:"rgba(255,100,0,.07)",  glow:"#ff7700" }, // right  — orange
];

// ============================================================
// NAV ITEMS
// ============================================================
const TABS = [
  { id: "campaigns", label: "CAMPAIGNS", icon: "◈" },
  { id: "analytics", label: "ANALYTICS", icon: "▲" },
  { id: "security",  label: "SECURITY",  icon: "⬡" },
  { id: "bidding",   label: "BIDDING",   icon: "◆" },
  { id: "reports",   label: "REPORTS",   icon: "◉" },
];

const NAV = [
  { id: "all",       label: "ALL PROMOTIONS",   icon: "⬡", type: null },
  { id: "bonus",     label: "BONUS CAMPAIGNS",  icon: "◈", type: "bonus" },
  { id: "yield",     label: "YIELD BOOSTERS",   icon: "◆", type: "yield" },
  { id: "fraud",     label: "FRAUD DETECTION",  icon: "◉", type: "fraud" },
  { id: "archived",  label: "ARCHIVED",         icon: "◑", type: "archived" },
];

// ============================================================
// FALLBACK MOCK PROMOS (shown when API is offline)
// ============================================================
const MOCK_PROMOS = [
  { id:1, title:"Weekend Bonus Offer",      bonus_rate:20,  yield_optimization:5260,  risk_score:8,  risk_level:"LOW",    status:"active",   promo_type:"bonus",   traffic_monitor:true,  verified:false },
  { id:2, title:"Yield Maximizer Package",  bonus_rate:15,  yield_optimization:7835,  risk_score:8,  risk_level:"SAFE",   status:"active",   promo_type:"yield",   traffic_monitor:true,  verified:true  },
  { id:3, title:"Special Bonus Boost",      bonus_rate:25,  yield_optimization:6415,  risk_score:7,  risk_level:"HIGH",   status:"active",   promo_type:"bonus",   traffic_monitor:true,  verified:false },
  { id:4, title:"Fraud Safe Bonus",         bonus_rate:10,  yield_optimization:3975,  risk_score:3,  risk_level:"LOW",    status:"active",   promo_type:"fraud",   traffic_monitor:true,  verified:true  },
  { id:5, title:"Super Bonus Event",        bonus_rate:22,  yield_optimization:8110,  risk_score:11, risk_level:"LOW",    status:"active",   promo_type:"bonus",   traffic_monitor:true,  verified:true  },
  { id:6, title:"Yield Booster Deluxe",     bonus_rate:18.5,yield_optimization:5345,  risk_score:5,  risk_level:"MEDIUM", status:"active",   promo_type:"yield",   traffic_monitor:true,  verified:false },
];

const MOCK_STATS = { total: 32105, users_engaged: 175508, promos_managed: 412 };

// ============================================================
// PARTICLE CANVAS
// ============================================================
function ParticleCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const ctx = cv.getContext("2d");
    const resize = () => { cv.width = window.innerWidth; cv.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);
    const pts = Array.from({ length: 60 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - .5) * .25,
      vy: (Math.random() - .5) * .25,
      r: Math.random() * 1.4 + .3,
      c: ["#9000ff","#ff00cc","#00e5ff","#6600ff"][Math.floor(Math.random() * 4)],
      a: Math.random() * .35 + .07,
    }));
    let id;
    const tick = () => {
      ctx.clearRect(0, 0, cv.width, cv.height);
      pts.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > cv.width)  p.vx *= -1;
        if (p.y < 0 || p.y > cv.height) p.vy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.c + Math.floor(p.a * 255).toString(16).padStart(2, "0");
        ctx.fill();
      });
      pts.forEach((p, i) => pts.slice(i + 1).forEach(q => {
        const d = Math.hypot(p.x - q.x, p.y - q.y);
        if (d < 85) {
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = `rgba(130,60,255,${.03 * (1 - d / 85)})`;
          ctx.lineWidth = .4; ctx.stroke();
        }
      }));
      id = requestAnimationFrame(tick);
    };
    tick();
    return () => { cancelAnimationFrame(id); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} style={{ position:"fixed",inset:0,pointerEvents:"none",zIndex:1 }} />;
}

// ============================================================
// SPARKLINE SVG  (uses real data if available, otherwise random)
// ============================================================
function Sparkline({ data, color, height = 44, filled = true }) {
  const W = 180; const H = height;
  if (!data || data.length < 2) {
    // generate deterministic fake data based on color hash
    data = Array.from({ length: 14 }, (_, i) =>
      40 + Math.sin(i * 0.7 + color.charCodeAt(1)) * 28 + Math.cos(i * 1.3) * 14
    );
  }
  const min = Math.min(...data); const max = Math.max(...data);
  const range = max - min || 1;
  const px = (i) => (i / (data.length - 1)) * W;
  const py = (v) => H - ((v - min) / range) * H * 0.88 - H * 0.06;
  const line = data.map((v, i) => `${i === 0 ? "M" : "L"} ${px(i)} ${py(v)}`).join(" ");
  const area = line + ` L ${W} ${H} L 0 ${H} Z`;
  const uid  = `sg-${color.replace(/[^a-z0-9]/gi, "")}-${height}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height, overflow:"visible" }}>
      <defs>
        <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {filled && <path d={area} fill={`url(#${uid})`} />}
      <path d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          filter: `drop-shadow(0 0 3px ${color})`,
          strokeDasharray: 600,
          strokeDashoffset: 600,
          animation: "pm-spark-draw 1.4s ease forwards .2s",
        }}
      />
      {/* last dot */}
      <circle cx={px(data.length - 1)} cy={py(data[data.length - 1])} r={3.5}
        fill={color}
        style={{ filter: `drop-shadow(0 0 5px ${color})` }}
      />
    </svg>
  );
}

// ============================================================
// WAVEFORM (bottom of card)
// ============================================================
function Waveform({ color }) {
  const pts = Array.from({ length: 60 }, (_, i) =>
    14 + Math.sin(i * 0.35) * 7 + Math.cos(i * 0.8) * 4 + Math.random() * 3
  );
  const W = 300; const H = 28;
  const px = (i) => (i / (pts.length - 1)) * W;
  const py = (v) => H - (v / 28) * H;
  const d  = pts.map((v, i) => `${i === 0 ? "M" : "L"} ${px(i)} ${py(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height:H, overflow:"visible" }} preserveAspectRatio="none">
      <path d={d}
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.55}
        style={{ filter: `drop-shadow(0 0 2px ${color})` }}
      />
    </svg>
  );
}

// ============================================================
// PROMO CARD — pixel-perfect match to reference design
//
//  col = idx % 3
//  col 0 (left)   → cyan border, Traffic Monitor in RATE ROW, EDIT only
//  col 1 (center) → blue border, Traffic Monitor in RATE ROW, EDIT only
//  col 2 (right)  → orange border, Traffic Monitor at TOP CORNER,
//                    EDIT + PAUSE, waveform strip at bottom
// ============================================================
function PromoCard({ promo, idx, onEdit, onDelete }) {
  const [hov, setHov] = useState(false);
  const qc = useQueryClient();

  // ── column position determines layout variant ──
  const col       = idx % 3;              // 0=left  1=center  2=right
  const isRight   = col === 2;            // orange card with EDIT+PAUSE
  const borderCfg = CARD_BORDERS[col];
  const risk      = RISK[promo.risk_level] || RISK.LOW;
  const paused    = promo.status === "paused";
  const archived  = promo.status === "archived";
  const sparkData = promo.sparkline_data || null;

  const pauseMut = useMutation({
    mutationFn: () => paused
      ? promotionsApi.resume(promo.id)
      : promotionsApi.pause(promo.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["promotions"] }),
  });

  // ── border opacity — dimmer at rest, bright on hover ──
  const borderOpRest = isRight ? "rgba(255,120,0,.28)" : borderCfg.border.replace(".42","0.25");
  const borderOpHov  = borderCfg.border;

  return (
    <div
      className={`pm-card pm-d${(idx % 6) + 1}`}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderColor: hov ? borderOpHov : borderOpRest,
        boxShadow: hov
          ? `0 0 36px ${borderCfg.shadow}, 0 8px 32px rgba(0,0,0,.6), inset 0 0 32px ${borderCfg.inner}`
          : `0 0 16px ${borderCfg.shadow.replace(".16",".08").replace(".20",".09")}, 0 4px 20px rgba(0,0,0,.45)`,
        opacity: archived ? 0.48 : 1,
      }}
    >
      {/* FIX 3: Per-column nebula corner glow — cyan/blue/orange */}
      <div style={{
        position:"absolute", inset:0, borderRadius:14, pointerEvents:"none", zIndex:0,
        background: col === 0
          ? "radial-gradient(ellipse 70% 50% at 0% 100%, rgba(0,200,255,.08) 0%, transparent 55%)"
          : col === 1
          ? "radial-gradient(ellipse 70% 50% at 100% 0%, rgba(0,120,255,.08) 0%, transparent 55%)"
          : "radial-gradient(ellipse 70% 50% at 100% 50%, rgba(255,100,0,.1) 0%, transparent 55%)",
      }} />

      {/* ── TOP CORNER traffic monitor — ONLY right column ── */}
      {isRight && (
        <div className="pm-card-corner">
          <span style={{ color: borderCfg.glow, fontSize: 9 }}>◈</span>
          <span>Traffic Monitor</span>
          <span style={{ fontSize: 11, cursor:"pointer" }}>⚙</span>
        </div>
      )}

      {/* Title */}
      <div className="pm-card-title" style={{ paddingRight: isRight ? 120 : 0 }}>
        {promo.title}
      </div>

      {/* % + Sparkline SAME ROW */}
      <div style={{
        display:"flex",
        alignItems:"flex-end",
        gap: 8,
        marginBottom: 4,
      }}>
        {/* Big % — always risk color */}
        <div style={{
          fontFamily:"'Orbitron',monospace",
          fontSize: 32,
          fontWeight: 900,
          letterSpacing:"-.01em",
          lineHeight: 1,
          color: risk.color,
          textShadow: `0 0 22px ${risk.color}90`,
          flexShrink: 0,
        }}>
          {parseFloat(promo.bonus_rate)}%
        </div>

        {/* Sparkline fills remaining width */}
        <div style={{ flex:1, alignSelf:"flex-end", minWidth:0, paddingBottom:2 }}>
          <Sparkline data={sparkData} color={risk.color} height={42} />
        </div>
      </div>

      {/* BONUS RATE row */}
      <div className="pm-rate-row">
        <span className="pm-rate-label">BONUS RATE</span>

        {/* ── FIX 3: Traffic Monitor in rate row — only left/center ── */}
        {!isRight ? (
          <div className="pm-traffic">
            <span style={{ color: risk.color, fontSize:10 }}>◄</span>
            <span style={{ margin:"0 2px", opacity:.4 }}>►</span>
            <span>Traffic Monitor</span>
            <span style={{ fontSize:11, marginLeft:3 }}>⚙</span>
          </div>
        ) : (
          /* right col: shows different label row per image */
          <div className="pm-traffic">
            <span style={{ color: borderCfg.glow, fontSize:10 }}>◄</span>
            <span style={{ margin:"0 2px", opacity:.4 }}>►</span>
            <span style={{ fontSize:7, letterSpacing:".08em", opacity:.55 }}>☆ 1.Weof/ sen sops</span>
            <span style={{ fontSize:11, marginLeft:3 }}>⚙</span>
          </div>
        )}
      </div>

      {/* ── FIX 2: Yield $ — ALWAYS bright green, never risk color ── */}
      <div className="pm-yield-row">
        <div className="pm-yield-left">
          <div className="pm-yield-val" style={{
            color:"#00ff99",
            textShadow:"0 0 20px rgba(0,255,153,.75)",
          }}>
            ${parseFloat(promo.yield_optimization).toLocaleString()}
          </div>
          <div className="pm-yield-label">YIELD OPTIMIZATION</div>
        </div>

        {/* Verified badge — only left/center cards */}
        {!isRight && promo.verified && (
          <div className="pm-verified">
            <div className="pm-verified-icon" style={{
              background:"rgba(0,255,120,.1)",
              borderColor:"rgba(0,255,120,.45)",
              color:"#00ff99",
            }}>✓</div>
            <div className="pm-verified-txt">Verified by<br/>Security Vault</div>
          </div>
        )}

        {/* Right col: show EDIT + PAUSE here (above waveform) */}
        {isRight && (
          <div style={{ display:"flex", gap:7, alignSelf:"flex-end" }}>
            <button className="pm-btn pm-btn-edit" onClick={() => onEdit(promo)}>EDIT</button>
            <button onClick={() => onDelete(promo.id)} style={{background:"rgba(255,30,60,.15)",color:"#ff3c5a",padding:"6px 10px",borderRadius:6,cursor:"pointer",fontSize:10,fontWeight:700}}>DEL</button>
            <button
              className="pm-btn pm-btn-pause"
              onClick={() => pauseMut.mutate()}
              disabled={pauseMut.isPending || archived}
            >
              {pauseMut.isPending ? "..." : paused ? "▶ RESUME" : "⏸ PAUSE"}
            </button>
          </div>
        )}
      </div>

      {/* ── FIX 4: Waveform strip — ONLY right column ── */}
      {isRight && (
        <div className="pm-wave-row" style={{ marginBottom:10 }}>
          <Waveform color={borderCfg.glow} />
        </div>
      )}

      {/* ── FIX 5: Footer ──
          Left/center: [risk badge]  [🚀 EDIT]
          Right:       [risk badge]  (buttons already shown above)          */}
      <div className="pm-card-footer">
        <div className="pm-risk" style={{ color: risk.color }}>
          <span style={{ fontSize:14, filter:`drop-shadow(0 0 4px ${risk.color})` }}>◎</span>
          <span style={{ fontFamily:"'Orbitron',monospace", fontSize:15, fontWeight:900, marginLeft:4 }}>
            {promo.risk_score}
          </span>
          <span style={{ fontSize:10, letterSpacing:".08em", marginLeft:3 }}>
            {risk.label}
          </span>
        </div>

        {/* EDIT button — only left/center columns */}
        {!isRight && (
          <div className="pm-card-btns">
            <button className="pm-btn pm-btn-edit" onClick={() => onEdit(promo)}>
              🚀 EDIT
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// PROMO FORM MODAL
// ============================================================
const EMPTY_FORM = {
  title: "", promo_type: "bonus", bonus_rate: "",
  yield_optimization: "", risk_level: "LOW",
  description: "", status: "active",
  traffic_monitor: true, verified: false,
};

function PromoModal({ promo, onClose }) {
  const qc    = useQueryClient();
  const isNew = !promo?.id;
  const [form, setForm] = useState(isNew ? EMPTY_FORM : { ...promo });
  const [err, setErr] = useState(null);

  const mut = useMutation({
    mutationFn: (data) => isNew ? promotionsApi.create(data) : promotionsApi.update(promo.id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["promotions"] }); onClose(); },
    onError:   (e) => setErr(e?.response?.data?.detail || "Failed to save"),
  });

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const submit = () => { setErr(null); mut.mutate(form); };

  return (
    <div className="pm-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pm-modal">
        <div className="pm-modal-title">
          {isNew ? "✦ CREATE NEW PROMOTION" : `✦ EDIT — ${promo.title}`}
        </div>
        <button className="pm-modal-close" onClick={onClose}>✕</button>

        <div className="pm-form-grid">
          <div className="pm-form-col1">
            <label className="pm-form-label">PROMOTION TITLE</label>
            <input className="pm-form-input" value={form.title}
              onChange={e => set("title", e.target.value)} placeholder="e.g. Weekend Bonus Offer" />
          </div>

          <div>
            <label className="pm-form-label">PROMO TYPE</label>
            <select className="pm-form-select" value={form.promo_type}
              onChange={e => set("promo_type", e.target.value)}>
              <option value="bonus">Bonus Campaign</option>
              <option value="yield">Yield Booster</option>
              <option value="fraud">Fraud Safe</option>
              <option value="seasonal">Seasonal</option>
              <option value="referral">Referral</option>
            </select>
          </div>

          <div>
            <label className="pm-form-label">STATUS</label>
            <select className="pm-form-select" value={form.status}
              onChange={e => set("status", e.target.value)}>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          <div>
            <label className="pm-form-label">BONUS RATE (%)</label>
            <input className="pm-form-input" type="number" step="0.5" min="0" max="100"
              value={form.bonus_rate}
              onChange={e => set("bonus_rate", e.target.value)}
              placeholder="e.g. 20" />
          </div>

          <div>
            <label className="pm-form-label">YIELD OPTIMIZATION ($)</label>
            <input className="pm-form-input" type="number" min="0"
              value={form.yield_optimization}
              onChange={e => set("yield_optimization", e.target.value)}
              placeholder="e.g. 5260" />
          </div>

          <div>
            <label className="pm-form-label">RISK LEVEL</label>
            <select className="pm-form-select" value={form.risk_level}
              onChange={e => set("risk_level", e.target.value)}>
              {Object.keys(RISK).map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div>
            <label className="pm-form-label">RISK SCORE</label>
            <input className="pm-form-input" type="number" min="0" max="100"
              value={form.risk_score || ""}
              onChange={e => set("risk_score", e.target.value)}
              placeholder="0–100" />
          </div>

          <div className="pm-form-col1">
            <label className="pm-form-label">DESCRIPTION</label>
            <textarea className="pm-form-textarea" value={form.description}
              onChange={e => set("description", e.target.value)}
              placeholder="Describe this promotion..." />
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <label className="pm-form-label" style={{ marginBottom:0 }}>TRAFFIC MONITOR</label>
            <input type="checkbox" checked={!!form.traffic_monitor}
              onChange={e => set("traffic_monitor", e.target.checked)}
              style={{ accentColor:"#9000ff", width:15, height:15 }} />
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <label className="pm-form-label" style={{ marginBottom:0 }}>SECURITY VERIFIED</label>
            <input type="checkbox" checked={!!form.verified}
              onChange={e => set("verified", e.target.checked)}
              style={{ accentColor:"#00ff99", width:15, height:15 }} />
          </div>
        </div>

        {err && (
          <div style={{
            marginBottom:12, padding:"8px 14px", borderRadius:8,
            background:"rgba(255,30,60,.1)", border:"1px solid rgba(255,30,60,.3)",
            color:"#ff4466", fontFamily:"'Exo 2',sans-serif", fontSize:11,
          }}>{err}</div>
        )}

        <div className="pm-modal-footer">
          <button className="pm-modal-cancel" onClick={onClose}>CANCEL</button>
          <button className="pm-modal-save" onClick={submit} disabled={mut.isPending}>
            {mut.isPending ? "SAVING..." : isNew ? "CREATE PROMOTION" : "SAVE CHANGES"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SKELETON LOADER
// ============================================================
function CardSkeleton() {
  return (
    <div className="pm-card" style={{ borderColor:"rgba(100,40,255,.12)" }}>
      <div className="pm-skeleton" style={{ height:16, width:"60%", marginBottom:14 }} />
      <div className="pm-skeleton" style={{ height:36, width:"40%", marginBottom:8 }} />
      <div className="pm-skeleton" style={{ height:44, width:"100%", marginBottom:10 }} />
      <div className="pm-skeleton" style={{ height:26, width:"50%", marginBottom:12 }} />
      <div className="pm-skeleton" style={{ height:28, width:"100%", marginBottom:12 }} />
      <div className="pm-skeleton" style={{ height:32, width:"100%", marginBottom:0 }} />
    </div>
  );
}

// ============================================================
// MAIN PAGE
// ============================================================
export default function Promotions() {
  const { user } = useAuth() || {};
  const [activeNav, setActiveNav] = useState("all");
  const [activeTab, setActiveTab] = useState("campaigns");
  const [activePanel, setActivePanel] = useState(null);
  const [search,    setSearch]    = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editPromo, setEditPromo] = useState(null);
  const [date,      setDate]      = useState(new Date());
  const [navWidth,  setNavWidth]   = useState(210);
  const [pmSidebarHover, setPmSidebarHover] = useState(false);

  useEffect(() => {
    const handler = (e) => setNavWidth(e.detail?.width ?? 210);
    window.addEventListener("sidebar-width-change", handler);
    return () => window.removeEventListener("sidebar-width-change", handler);
  }, []);
  const qc = useQueryClient();

  // live date
  useEffect(() => {
    const t = setInterval(() => setDate(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const fmtDate = (d) =>
    d.toLocaleDateString("en-US", { month:"short", day:"numeric", year:"numeric" });

  // ── filter params ──
  const navItem  = NAV.find(n => n.id === activeNav);
  const params   = {
    ...(navItem?.type ? { promo_type: navItem.type } : {}),
    ...(search        ? { search }                  : {}),
  };

  // ── queries ──
  const promosQ = useQuery({
    queryKey: QK.promos(params),
    queryFn:  () => promotionsApi.list(params),
    staleTime: 30_000,
    retry: 1,
  });

  const statsQ = useQuery({
    queryKey: QK.stats(),
    queryFn:  () => promotionsApi.stats(),
    staleTime: 60_000,
    retry: 1,
    refetchInterval: 30_000,
  });
  const analyticsQ  = useQuery({ queryKey: ["promotions","analytics"],   queryFn: () => API.get("/promotions/analytics/overall/").then(r=>r.data), retry:1 });
  const submissionsQ = useQuery({ queryKey: ["promotions","submissions"], queryFn: () => API.get("/promotions/submissions/").then(r=>r.data), retry:1 });
  const fraudQ       = useQuery({ queryKey: ["promotions","fraud"],       queryFn: () => API.get("/promotions/fraud-reports/").then(r=>r.data), retry:1 });
  const blacklistQ   = useQuery({ queryKey: ["promotions","blacklist"],   queryFn: () => API.get("/promotions/blacklist/").then(r=>r.data), retry:1 });
  const biddingQ = useQuery({ queryKey: ["promotions","bidding"], queryFn: () => API.get("/promotions/bidding/").then(r=>r.data), retry:1 });

  // delete mutation
  const deleteMut = useMutation({
    mutationFn: promotionsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["promotions"] }),
  });

  // ── resolve data (fallback to mock if API offline) ──
  const promos = promosQ.data?.results ?? promosQ.data ?? (promosQ.isError ? MOCK_PROMOS : null);
  const stats  = statsQ.data ?? (statsQ.isError ? MOCK_STATS : null);

  // filter locally if search active
  const displayed = promos
    ? (search
      ? promos.filter(p => p.title.toLowerCase().includes(search.toLowerCase()))
      : promos)
    : null;

  const handleEdit = (promo) => { setEditPromo(promo); setShowModal(true); };
  const handleNew  = () =>       { setEditPromo(null);  setShowModal(true); };
  const handleClose= () =>       { setShowModal(false); setEditPromo(null); };

  // sidebar stat rows
  const sideStats = [
    { icon:"◆", val: stats ? (stats.total || 32105).toLocaleString() + "+" : "...",   label:"",              color:"#cc00ff", w:"68%" },
    { icon:"◈", val: stats ? (stats.users_engaged||175508).toLocaleString() + "+" : "...", label:"USERS ENGAGED", color:"#ff7700", w:"80%" },
    { icon:"◉", val: stats ? (stats.promos_managed||412).toString() : "...",          label:"PROMOS MANAGED", color:"#cc00ff", w:"45%" },
  ];

  return (
    <div className="pm-root">
      {/* BG */}
      <div className="pm-bg">
        <PageEndpointPanel pageKey="Promotions" title="Promotions Endpoints" />
        <div className="pm-bg-base" />
        <div className="pm-bg-layer2" />
        <div className="pm-bg-stars" />
        <div className="pm-bg-grid" />
        <div className="pm-streak pm-streak-a" />
        <div className="pm-streak pm-streak-b" />
        <div className="pm-streak pm-streak-c" />
        <div className="pm-bg-scan" />
      </div>
      <ParticleCanvas />

      {/* ── HEADER ── */}
      <header className="pm-header">
        <div className="pm-header-logo">
          <div className="pm-header-diamond"><span>◆</span></div>
          <div className="pm-header-title">
            <span className="t1">PROMOTIONS </span>
            <span className="t2">MANAGEMENT</span>
          </div>
        </div>

        <div className="pm-header-right">
          {/* Search */}
          <div className="pm-search">
            <span className="pm-search-icon">⌕</span>
            <input
              className="pm-search-ph"
              style={{ border:"none", outline:"none", background:"transparent", flex:1, color:"rgba(180,150,255,.8)" }}
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* Date */}
          <div className="pm-date-pill">
            📅 {fmtDate(date)}
          </div>

          {/* Icons */}
          <div className="pm-hbtn">
            🔔
            <div className="pm-hbtn-badge">2</div>
          </div>
          <div className="pm-hbtn">⚙</div>
          <div className="pm-hbtn">👤</div>
        </div>
      </header>

      {/* ── BODY ── */}
      <div className="pm-body">

        <aside className="pm-sidebar">
          {/* User card */}
          <div className="pm-user-card">
            {user?.profile_picture ? <img src={user.profile_picture} alt="avatar" className="pm-user-ava" style={{objectFit:"cover",borderRadius:"50%"}} /> : <div className="pm-user-ava" />}
            <div className="pm-user-info">
              <div className="uname">{user?.username || "Admin"}</div>
              <div className="urole">({user?.role || "admin"})</div>
            </div>
            <span className="pm-user-arrow">▾</span>
          </div>

          {/* Stat rows */}
          <div className="pm-stat-rows">
            {sideStats.map((s, i) => (
              <div key={i} className="pm-srow">
                <span className="pm-srow-icon" style={{ color: s.color }}>{s.icon}</span>
                <span className="pm-srow-val" style={{ color: s.color, textShadow:`0 0 8px ${s.color}80` }}>
                  {s.val}
                </span>
                {s.label && <span className="pm-srow-label">{s.label}</span>}
                <div className="pm-srow-bar">
                  <div className="pm-srow-line">
                    <div className="pm-srow-fill" style={{ width: s.w, background:`linear-gradient(90deg,${s.color},${s.color}50)` }} />
                  </div>
                  {i === 0 && <div className="pm-srow-export">↗</div>}
                </div>
              </div>
            ))}
          </div>

          {/* New Promotion btn */}
          <button className="pm-new-btn" onClick={handleNew}>
            <span className="pm-new-btn-icon">+</span>
            <span>NEW PROMOTION</span>
            <div className="pm-new-btn-arrow">›</div>
          </button>

          {/* Nav */}
          <nav className="pm-nav">
            {NAV.map(n => (
              <button key={n.id}
                className={`pm-nav-item ${activeNav === n.id ? "active" : ""}`}
                onClick={() => setActiveNav(n.id)}
              >
                <div className="pm-nav-icon">{n.icon}</div>
                <span>{n.label}</span>
                <span className="pm-nav-arrow">›</span>
              </button>
            ))}
          </nav>

          {/* Bottom btn */}
          <div className="pm-sidebar-bottom">
            <button className="pm-sidebar-bottom-btn" onClick={handleNew}>
              <span style={{ fontSize:14 }}>◎</span>
              <span>NEWPROMOTION</span>
            </button>
          </div>
        </aside>

        {/* ── MAIN ── */}
        <main className="pm-main">
          {/* Toolbar */}
          <div className="pm-toolbar" style={{ marginBottom: navWidth > 100 ? "6px" : "8px" }}>
            <span className="pm-toolbar-title">Promotions</span>
            <div className="pm-toolbar-sep" />
            <div className="pm-toolbar-breadcrumb">
              <span>◈</span>
              <span>ALL PROMOTIONS</span>
            </div>
            <div className="pm-toolbar-right">
              {["⇆","☰","⊕","⌕"].map((ic, i) => (
                <div key={i} className="pm-tb-icon"
                  title={["Filter","List View","Add","Search"][i]}
                  onClick={i === 2 ? handleNew : undefined}>
                  {ic}
                </div>
              ))}
            </div>
          </div>


          {/* ── TAB BAR ── */}
          <div style={{ display:"flex", gap:4, marginBottom:12, borderBottom:"1px solid rgba(100,40,255,.15)", paddingBottom:8, flexWrap:"wrap", alignItems:"center" }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                padding:"6px 14px", borderRadius:"8px 8px 0 0", border:"none", cursor:"pointer",
                fontFamily:"'Orbitron',monospace", fontSize:10, fontWeight:700, letterSpacing:".08em",
                background: activeTab === t.id ? "linear-gradient(135deg,rgba(100,40,255,.25),rgba(255,0,180,.12))" : "transparent",
                color: activeTab === t.id ? "#fff" : "rgba(140,110,190,.5)",
                borderBottom: activeTab === t.id ? "2px solid #9000ff" : "2px solid transparent",
                transition:"all .2s",
              }}>
                {t.icon} {t.label}
              </button>
            ))}
            <div style={{ marginLeft:"auto", display:"flex", gap:6 }}>
              {[
                { label:"SUBMISSIONS", href:"/admin-submissions", color:"#ffcc00", icon:"📋" },
                { label:"DISPUTES",    href:"/admin-disputes",    color:"#a855f7", icon:"⚖" },
                { label:"FINANCE",     href:"/admin-finance",     color:"#00e87a", icon:"💰" },
                { label:"TOOLS",       href:"/admin-tools",       color:"#00c8ff", icon:"⚙" },
              ].map(l => (
                <a key={l.href} href={l.href} style={{
                  padding:"5px 12px", borderRadius:6, textDecoration:"none",
                  fontFamily:"'Orbitron',monospace", fontSize:9, fontWeight:700, letterSpacing:".08em",
                  background:`${l.color}12`, border:`1px solid ${l.color}44`, color:l.color,
                  transition:"all .2s", display:"flex", alignItems:"center", gap:4,
                }}
                onMouseEnter={e => { e.currentTarget.style.background=l.color+"25"; e.currentTarget.style.borderColor=l.color+"88"; }}
                onMouseLeave={e => { e.currentTarget.style.background=l.color+"12"; e.currentTarget.style.borderColor=l.color+"44"; }}>
                  {l.icon} {l.label}
                </a>
              ))}
            </div>
          </div>

          {/* ── TAB PANELS ── */}
          {activeTab === "analytics" && (
            <div style={{ padding:"20px", color:"#ccc", fontFamily:"'Exo 2',sans-serif" }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16, marginBottom:20 }}>
                {[
                  { label:"Total Campaigns", value: stats?.promos_managed ?? 0,  color:"#00e5ff" },
                  { label:"Users Engaged",   value: stats?.users_engaged ?? 0,   color:"#00ff99" },
                  { label:"Active Now",      value: stats?.total ?? 0,           color:"#ff00cc" },
                  { label:"Submissions", value: submissionsQ.data?.count ?? submissionsQ.data?.results?.length ?? 0, color:"#ffcc00", link:"/admin-submissions" },
                  { label:"Fraud Reports",   value: fraudQ.data?.count ?? fraudQ.data?.results?.length ?? 0,            color:"#ff3c5a" },
                  { label:"Blacklisted",     value: blacklistQ.data?.count ?? blacklistQ.data?.results?.length ?? 0,    color:"#ff7700" },
                ].map(s => (
                  <div key={s.label}
                    onClick={() => s.link && (window.location.href = s.link)}
                    style={{ background:"rgba(100,40,255,.08)", border:`1px solid ${s.color}33`, borderRadius:12, padding:"16px 20px", cursor:s.link?"pointer":"default", transition:"border-color .2s" }}
                    onMouseEnter={e => { if(s.link) e.currentTarget.style.borderColor=`${s.color}88`; }}
                    onMouseLeave={e => { if(s.link) e.currentTarget.style.borderColor=`${s.color}33`; }}>
                    <div style={{ color:s.color, fontFamily:"'Orbitron',monospace", fontSize:22, fontWeight:900 }}>{String(s.value)}</div>
                    <div style={{ fontSize:10, letterSpacing:".1em", marginTop:4, color:"rgba(200,180,255,.5)" }}>
                      {s.label} {s.link && <span style={{ fontSize:9, opacity:.6 }}>→</span>}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background:"rgba(100,40,255,.06)", border:"1px solid rgba(100,40,255,.15)", borderRadius:12, padding:20 }}>
                <div style={{ fontFamily:"'Orbitron',monospace", fontSize:11, color:"#9000ff", marginBottom:12 }}>CAMPAIGN PERFORMANCE</div>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:10 }}>
                  {promos?.map(p => (
                    <div key={p.id} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"8px 12px", background:"rgba(0,0,0,.2)", borderRadius:8 }}>
                      <span style={{ fontSize:11 }}>{p.title}</span>
                      <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                        <span style={{ color:"#00ff99", fontWeight:700, fontSize:12 }}>{parseFloat(p.bonus_rate)}%</span>
                        <span style={{ color:"rgba(180,160,220,.4)", fontSize:10 }}>{p.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === "security" && (
            <div style={{ padding:"20px", fontFamily:"'Exo 2',sans-serif" }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:16 }}>
                {[
                  { icon:"⬡", label:"IP Whitelist",       desc:"Manage allowed IPs",        color:"#00e5ff" },
                  { icon:"◉", label:"Fraud Reports",       desc:"Review flagged activity",   color:"#ff3c5a" },
                  { icon:"◈", label:"Blacklist Manager",   desc:"Block users & domains",     color:"#ffcc00" },
                  { icon:"◆", label:"Security Vault",      desc:"Encryption & JWT config",   color:"#00ff99" },
                  { icon:"▲", label:"Breach Detection",    desc:"Monitor data leaks",        color:"#ff00cc" },
                  { icon:"◑", label:"Device Fingerprint",  desc:"Track device signatures",   color:"#9000ff" },
                ].map(item => (
                  <div key={item.label} style={{ background:"rgba(100,40,255,.06)", border:`1px solid ${item.color}22`, borderRadius:12, padding:"14px 16px", cursor:"pointer", transition:"all .2s" }}
                    onClick={() => setActivePanel(item.label)}
                    onMouseEnter={e => e.currentTarget.style.borderColor = item.color + "66"}
                    onMouseLeave={e => e.currentTarget.style.borderColor = item.color + "22"}>
                    <div style={{ color:item.color, fontSize:18, marginBottom:6 }}>{item.icon}</div>
                    <div style={{ fontFamily:"'Orbitron',monospace", fontSize:11, color:"#fff", marginBottom:4 }}>{item.label}</div>
                    <div style={{ fontSize:10, color:"rgba(180,160,220,.5)" }}>{item.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "bidding" && (
            <div style={{ padding:"20px", fontFamily:"'Exo 2',sans-serif" }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16, marginBottom:20 }}>
                {[
                  { label:"Active Auctions", value:"0",   color:"#00e5ff" },
                  { label:"Total Bids",      value:"0",   color:"#ff00cc" },
                  { label:"Avg Bid Price",   value:"$0",  color:"#00ff99" },
                ].map(s => (
                  <div key={s.label} style={{ background:"rgba(100,40,255,.08)", border:`1px solid ${s.color}33`, borderRadius:12, padding:"16px 20px" }}>
                    <div style={{ color:s.color, fontFamily:"'Orbitron',monospace", fontSize:22, fontWeight:900 }}>{s.value}</div>
                    <div style={{ fontSize:10, letterSpacing:".1em", marginTop:4, color:"rgba(200,180,255,.5)" }}>{s.label}</div>
                  </div>
                ))}
              </div>
              <div style={{ background:"rgba(100,40,255,.06)", border:"1px solid rgba(100,40,255,.15)", borderRadius:12, padding:20 }}>
                <div style={{ fontFamily:"Orbitron", fontSize:11, color:"#9000ff", marginBottom:12 }}>RECENT BIDS</div>
                {!biddingQ.data?.bids?.length ? <div style={{ textAlign:"center", padding:"20px", color:"rgba(180,160,220,.3)" }}>No bids yet</div> : biddingQ.data.bids.map(b => <div key={b.id} style={{ display:"flex", justifyContent:"space-between", padding:"8px 12px", marginBottom:6, background:"rgba(0,0,0,.2)", borderRadius:8 }}><div><div style={{ color:"#fff", fontSize:11 }}>{b.campaign_title}</div><div style={{ color:"rgba(180,160,220,.4)", fontSize:10 }}>{b.advertiser}</div></div><div style={{ color:"#00ff99", fontWeight:900 }}>${b.bid_amount}</div></div>)}
              </div>
            </div>
          )}

          {activeTab === "reports" && (
            <div style={{ padding:"20px", fontFamily:"'Exo 2',sans-serif" }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:16 }}>
                {[
                  { icon:"◉", label:"Revenue Report",      color:"#00ff99" },
                  { icon:"▲", label:"Campaign Performance", color:"#00e5ff" },
                  { icon:"◈", label:"Fraud Analytics",      color:"#ff3c5a" },
                  { icon:"◆", label:"Payout Summary",       color:"#ffcc00" },
                  { icon:"⬡", label:"User Growth Stats",    color:"#ff00cc" },
                  { icon:"◑", label:"ROI Calculator",       color:"#9000ff" },
                ].map(r => (
                  <div key={r.label} style={{ background:"rgba(100,40,255,.06)", border:`1px solid ${r.color}22`, borderRadius:12, padding:"14px 16px", cursor:"pointer", display:"flex", alignItems:"center", gap:12 }}
                    onClick={() => setActivePanel(r.label)}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(100,40,255,.12)"}
                    onMouseLeave={e => e.currentTarget.style.background = "rgba(100,40,255,.06)"}>
                    <span style={{ color:r.color, fontSize:20 }}>{r.icon}</span>
                    <div>
                      <div style={{ fontFamily:"'Orbitron',monospace", fontSize:11, color:"#fff" }}>{r.label}</div>
                      <div style={{ fontSize:10, color:"rgba(180,160,220,.4)", marginTop:2 }}>Click to generate</div>
                    </div>
                    <span style={{ marginLeft:"auto", color:"rgba(180,160,220,.3)", fontSize:14 }}>›</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "campaigns" && (
            <>
            {promosQ.isError && !promos && (
              <div style={{marginBottom:14,padding:"10px 16px",borderRadius:10,background:"rgba(255,50,50,.08)",border:"1px solid rgba(255,50,50,.25)",color:"#ff6680",fontSize:11}}>
                API offline
              </div>
            )}
            <div className="pm-grid" style={{gap:"10px", gridTemplateColumns:"repeat(3, minmax(0,1fr))"}}>
              {promosQ.isLoading
                ? Array.from({length:6}).map((_,i) => <div key={i} className={"pm-d"+(i+1)}><CardSkeleton /></div>)
                : displayed?.map((promo,idx) => (
                    <PromoCard key={promo.id} promo={promo} idx={idx} onEdit={handleEdit} onDelete={(id) => deleteMut.mutate(id)} />
                  ))
              }
            </div>
            {!promosQ.isLoading && displayed?.length === 0 && (
              <div style={{textAlign:"center",padding:"60px 20px",fontFamily:"Orbitron,monospace",fontSize:13,color:"rgba(140,100,200,.4)"}}>
                NO PROMOTIONS FOUND
              </div>
            )}
            </>
          )}
        </main>
      </div>

      {/* ── STATUS BAR ── */}
      <div className="pm-statusbar" style={{ paddingBottom:24 }}>
        <div className="pm-statusbar-dot" style={{ background:"#00ff99", boxShadow:"0 0 6px #00ff99" }} />
        ALL PROMOTIONS
        <span style={{ marginLeft:6, color:"rgba(0,229,255,.5)" }}>
          AINUL@DESKTOP-VLK1464:~/promotions $
        </span>
        {promosQ.isFetching && (
          <span style={{ marginLeft:"auto", color:"rgba(0,200,255,.4)" }}>
            ↻ Refreshing...
          </span>
        )}
      </div>

      {/* ── DETAIL PANEL MODAL ── */}
      {activePanel && (
        <div onClick={() => setActivePanel(null)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,.7)",zIndex:9000,display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div onClick={e=>e.stopPropagation()} style={{background:"linear-gradient(135deg,#0d0a1a,#12082a)",border:"1px solid rgba(144,0,255,.3)",borderRadius:16,padding:32,minWidth:500,maxWidth:700,maxHeight:"80vh",overflowY:"auto",position:"relative"}}>
            <div style={{fontFamily:"'Orbitron',monospace",fontSize:14,color:"#fff",marginBottom:20,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <span>◈ {activePanel.toUpperCase()}</span>
              <button onClick={()=>setActivePanel(null)} style={{background:"transparent",border:"none",color:"#ff3c5a",fontSize:18,cursor:"pointer"}}>✕</button>
            </div>
            {activePanel === "Fraud Reports" && (
              <div>
                {fraudQ.isLoading ? <div style={{color:"rgba(180,160,220,.5)"}}>Loading...</div> :
                fraudQ.data?.results?.length > 0 ? fraudQ.data.results.map(r => (
                  <div key={r.id} style={{padding:"10px 14px",marginBottom:8,background:"rgba(255,60,90,.05)",border:"1px solid rgba(255,60,90,.15)",borderRadius:8}}>
                    <div style={{color:"#ff3c5a",fontWeight:700,fontSize:12}}>{r.fraud_type}</div>
                    <div style={{color:"rgba(200,180,220,.6)",fontSize:11,marginTop:4}}>User: {r.user} | Action: {r.action_taken}</div>
                  </div>
                )) : <div style={{color:"rgba(180,160,220,.4)",textAlign:"center",padding:40}}>No fraud reports found</div>}
              </div>
            )}
            {activePanel === "Blacklist Manager" && (
              <div>
                {blacklistQ.isLoading ? <div style={{color:"rgba(180,160,220,.5)"}}>Loading...</div> :
                blacklistQ.data?.results?.length > 0 ? blacklistQ.data.results.map(r => (
                  <div key={r.id} style={{padding:"10px 14px",marginBottom:8,background:"rgba(255,204,0,.05)",border:"1px solid rgba(255,204,0,.15)",borderRadius:8}}>
                    <div style={{color:"#ffcc00",fontWeight:700,fontSize:12}}>{r.type}: {r.value}</div>
                    <div style={{color:"rgba(200,180,220,.6)",fontSize:11,marginTop:4}}>Severity: {r.severity} | {r.reason?.slice(0,60)}</div>
                  </div>
                )) : <div style={{color:"rgba(180,160,220,.4)",textAlign:"center",padding:40}}>No blacklist entries found</div>}
              </div>
            )}
            {activePanel === "Revenue Report" && (
              <div>
                {analyticsQ.data ? (
                  <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:12}}>
                    {Object.entries(analyticsQ.data).map(([k,v]) => (
                      <div key={k} style={{padding:"10px 14px",background:"rgba(0,255,153,.05)",border:"1px solid rgba(0,255,153,.15)",borderRadius:8}}>
                        <div style={{color:"rgba(180,160,220,.5)",fontSize:10}}>{k.replace(/_/g," ").toUpperCase()}</div>
                        <div style={{color:"#00ff99",fontWeight:700,fontSize:14,marginTop:4}}>{String(v)}</div>
                      </div>
                    ))}
                  </div>
                ) : <div style={{color:"rgba(180,160,220,.4)",textAlign:"center",padding:40}}>No analytics data available</div>}
              </div>
            )}
{!["Fraud Reports","Blacklist Manager","Revenue Report"].includes(activePanel) && (
              <div style={{color:"rgba(180,160,220,.4)",textAlign:"center",padding:40,fontFamily:"'Exo 2',sans-serif"}}>
                <div style={{fontSize:32,marginBottom:12}}>⚙</div>
                <div>{activePanel} — Coming soon</div>
              </div>
            )}
          </div>
        </div>
      )}
      {/* ── MODAL ── */}
      {showModal && (
        <PromoModal promo={editPromo} onClose={handleClose} />
      )}
    </div>
  );
}