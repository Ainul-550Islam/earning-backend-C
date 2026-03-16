// src/components/layout/Sidebar.jsx — Smart Sidebar v2
// ✅ = বাটন → collapse/expand
// ✅ Mouse scroll → sidebar ছোট/বড়
// ✅ Left/Right slide → সম্পূর্ণ hide/show
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Wallet, ClipboardList, Zap, GitBranch,
  ShieldAlert, ScanSearch, UserCheck, History, Monitor,
  BarChart3, MessageSquare, Gift, Star,
  ChevronDown, ChevronRight, Circle, Bell, Globe,
  Database, AlertTriangle, Settings, Lock, CreditCard,
  BookOpen, RefreshCw, Layers, FlaskConical, Megaphone,
  PanelLeftClose, PanelLeftOpen, AlignJustify,
} from 'lucide-react';

/* ── Colors ── */
const COLORS = [
  '#ff2d78','#ffd700','#00f3ff','#00ff88',
  '#a855f7','#ff8c00','#4d79ff','#ff2df7',
  '#39ff14','#0ff0fc','#ff6b35','#22d3ee',
];

/* ── Nav config ── */
const NAV = [
  {
    section: 'MAIN',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard',        path: '' },
      // { icon: History,         label: 'Audit Logs',  path: 'audit-logs' },
    ]
  },
  {
    section: 'MANAGEMENT',
    items: [
      { icon: Users,           label: 'Users',            path: 'users' },
      { icon: Wallet,          label: 'Wallet',           path: 'wallet' },
      { icon: ClipboardList,   label: 'Tasks',            path: 'tasks' },
      { icon: Zap,             label: 'Offerwall',        path: 'offerwall' },
      { icon: GitBranch,       label: 'Referral',         path: 'referral' },
    ]
  },
  {
    section: 'SECURITY & COMPLIANCE',
    items: [
      { icon: ShieldAlert,     label: 'Security',         path: 'security' },
      { icon: ScanSearch,      label: 'Fraud Detection',  path: 'fraud-detection', badge: true },
      { icon: UserCheck,       label: 'KYC',              path: 'kyc' },
      { icon: History,         label: 'Audit Logs',       path: 'audit-logs' },
    ]
  },
  {
    section: 'ANALYTICS & GROWTH',
    items: [
      { icon: BarChart3,       label: 'Analytics',        path: 'analytics' },
      { icon: MessageSquare,   label: 'Engagement',       path: 'engagement' },
      { icon: Gift,            label: 'Loyalty',          path: 'loyalty' },
    ]
  },
  {
    section: 'FINANCE & GATEWAYS',
    items: [
      { icon: CreditCard,      label: 'Payment Gateways', path: 'payment-gateways' },
      { icon: Layers,          label: 'Ad Networks',      path: 'ad-networks' },
    ]
  },
  {
    section: 'SYSTEM & CONFIG',
    items: [
      { icon: Bell,            label: 'Notifications',    path: 'notifications' },
      { icon: Globe,           label: 'Localization',     path: 'localization' },
      { icon: BookOpen,        label: 'CMS',              path: 'cms' },
      { icon: AlertTriangle,   label: 'Alerts',           path: 'alerts' },
      { icon: MessageSquare,   label: 'Support',          path: 'support' },
      { icon: RefreshCw,       label: 'Cache',            path: 'cache' },
      { icon: Database,        label: 'Backup',           path: 'backup' },
      { icon: Lock,            label: 'Rate Limit',       path: 'rate-limit' },
      { icon: Settings,        label: 'Admin Panel',      path: 'settings' },
      { icon: FlaskConical,    label: 'Tests',            path: 'tests' },
      { icon: Megaphone,       label: 'Promotions',       path: 'promotions' },
    ]
  },
  {
    section: 'MONETIZATION',
    items: [
      { icon: CreditCard,      label: 'Subscription',     path: 'subscriptions' },
      { icon: Star,            label: 'Gamification',     path: 'gamification' },
      { icon: Layers,          label: 'Inventory',        path: 'inventory' },
      { icon: MessageSquare,   label: 'Messaging',        path: 'messaging' },
      { icon: Wallet,          label: 'Payout Queue',     path: 'payout-queue' },
    ]
  },
  {
    section: 'ADVANCED',
    items: [
      { icon: Monitor,         label: 'Auto Mod',         path: 'auto-mod' },
      { icon: GitBranch,       label: 'Version Control',  path: 'version-control' },
      { icon: BarChart3,       label: 'Behavior Analytics', path: 'behavior-analytics' },
      { icon: RefreshCw,       label: 'Postback',         path: 'postback' },
    ]
  },
];

/* ── Width constants ── */
const W_COLLAPSED = 58;   // icon only
const W_EXPANDED  = 210;  // icon + text
const W_HIDDEN    = 0;    // সম্পূর্ণ লুকানো

export default function Sidebar({ user, onWidthChange }) {
  const navigate  = useNavigate();
  const location  = useLocation();
  const sidebarRef = useRef(null);

  /* ── States ── */
  const [expanded,  setExpanded]  = useState(true);   // true = expanded (210px)
  const [hidden,    setHidden]    = useState(false);   // true = slide out
  const [collapsed, setCollapsed] = useState({});      // section collapse
  const [colorOffset, setColorOffset] = useState(0);

  /* ── Color cycle ── */
  useEffect(() => {
    const t = setInterval(() => setColorOffset(p => (p + 1) % COLORS.length), 60000);
    return () => clearInterval(t);
  }, []);

  /* ── Width calculation ── */
  const currentW = hidden ? W_HIDDEN : expanded ? W_EXPANDED : W_COLLAPSED;

  /* ── Parent কে width জানানো (layout margin এর জন্য) ── */
  useEffect(() => {
    onWidthChange?.(currentW);
    window.dispatchEvent(new CustomEvent("sidebar-width-change", { detail: { width: currentW } }));
  }, [currentW, onWidthChange]);

  /* ── = বাটন: collapse ↔ expand ── */
  const toggleExpand = useCallback(() => {
    setExpanded(p => !p);
  }, []);

  /* ── Slide বাটন: hide ↔ show ── */
  const toggleHide = useCallback(() => {
    setHidden(p => {
      if (!p) setExpanded(false); // hide করার আগে collapse
      return !p;
    });
  }, []);

  /* ── Hover → expand, mouse সরালে → collapse ── */
  const hoverTimer = useRef(null);
  const handleMouseEnter = () => {
    if (hidden) return;
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setExpanded(true), 60);
  };
  const handleMouseLeave = () => {
    if (hidden) return;
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setExpanded(false), 150);
  };

  /* ── Active path ── */
  const activePath = location.pathname.replace('/', '') || '';
  const toggleSection = (s) => setCollapsed(p => ({ ...p, [s]: !p[s] }));
  const handleNav = (path) => navigate(path ? `/${path}` : '/');

  /* ── Colors ── */
  const getColor = (idx) => COLORS[(idx + colorOffset) % COLORS.length];
  const getSectionColor = (sIdx) => COLORS[(sIdx * 3 + colorOffset) % COLORS.length];

  /* ── Show button যখন hidden ── */
  if (hidden) {
    return (
      <>
        <style>{SIDEBAR_CSS}</style>
        {/* Sidebar সম্পূর্ণ লুকানো → ছোট show বাটন দেখাবে */}
        <button className="sb-show-btn" onClick={toggleHide} title="Show Sidebar">
          <PanelLeftOpen style={{ width: 16, height: 16, color: '#a855f7' }} />
        </button>
      </>
    );
  }

  return (
    <>
      <style>{SIDEBAR_CSS}</style>

      <aside
        ref={sidebarRef}
        className={`sidebar-root ${expanded ? 'sb-expanded' : 'sb-collapsed'}`}
        style={{ width: currentW }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {/* Glow border */}
        <div className="sb-glow-border" />

        {/* ══ TOP CONTROLS ══ */}
        <div className="sb-controls">
          {/* = বাটন — collapse/expand */}
          <button
            className="sb-eq-btn"
            onClick={toggleExpand}
            title={expanded ? 'Collapse' : 'Expand'}
          >
            <AlignJustify style={{ width: 15, height: 15, color: expanded ? '#a855f7' : '#4a2a6a' }} />
          </button>

          {/* Logo — শুধু expanded এ */}
          {expanded && (
            <div className="sb-logo-text">
              <span style={{ color: getColor(0), textShadow: `0 0 10px ${getColor(0)}` }}>
                EARNING PLATFORM
              </span><br />
              <span style={{ color: getColor(2), textShadow: `0 0 10px ${getColor(2)}` }}>
                ADMIN PANEL
              </span>
            </div>
          )}

          {/* Diamond logo — সবসময় */}
          {!expanded && (
            <div className="sb-logo-diamond-sm" style={{
              background: `linear-gradient(135deg, ${getColor(0)}, ${getColor(4)})`,
            }} />
          )}

          {/* ◀ বাটন — sidebar সম্পূর্ণ hide */}
          <button
            className="sb-hide-btn"
            onClick={toggleHide}
            title="Hide Sidebar"
          >
            <PanelLeftClose style={{ width: 14, height: 14, color: '#4a2a6a' }} />
          </button>
        </div>

        {/* ══ NAV ══ */}
        <nav className="sb-nav">
          {(() => {
            let globalIdx = 0;
            return NAV.map(({ section, items }, sIdx) => (
              <div key={section}>
                {/* Section header */}
                <div
                  className="sb-section-header"
                  onClick={() => toggleSection(section)}
                  title={!expanded ? section : ''}
                >
                  {expanded && (
                    <>
                      <span className="sb-section-title" style={{
                        color: getSectionColor(sIdx),
                        textShadow: `0 0 8px ${getSectionColor(sIdx)}`,
                      }}>
                        {section}
                      </span>
                      {collapsed[section]
                        ? <ChevronRight style={{ width: 9, height: 9, color: '#4a2a6a', flexShrink: 0 }} />
                        : <ChevronDown  style={{ width: 9, height: 9, color: '#4a2a6a', flexShrink: 0 }} />
                      }
                    </>
                  )}
                  {!expanded && (
                    <div className="sb-section-dot" style={{ background: getSectionColor(sIdx) }} />
                  )}
                </div>

                {/* Items */}
                {!collapsed[section] && items.map(({ icon: Icon, label, path, badge }) => {
                  const ic = getColor(globalIdx++);
                  const isActive = activePath === path;
                  return (
                    <div
                      key={`${section}-${label}`}
                      className={`sb-item ${isActive ? 'active' : ''}`}
                      onClick={() => handleNav(path)}
                      title={!expanded ? label : ''}
                      style={{ borderLeftColor: isActive ? ic : 'transparent' }}
                    >
                      {/* Icon */}
                      <div className="sb-icon" style={{
                        background: `${ic}18`,
                        border: `1px solid ${ic}40`,
                        boxShadow: isActive ? `0 0 12px ${ic}66` : 'none',
                        minWidth: 26,
                      }}>
                        <Icon style={{ width: 13, height: 13, color: ic }} />
                      </div>

                      {/* Label — শুধু expanded এ */}
                      {expanded && (
                        <span className="sb-label" style={{
                          color: ic,
                          textShadow: `0 0 10px ${ic}, 0 0 20px ${ic}88`,
                        }}>
                          {label}
                        </span>
                      )}

                      {/* Badge */}
                      {badge && expanded && <span className="sb-badge" />}
                      {badge && !expanded && <span className="sb-badge-sm" />}
                    </div>
                  );
                })}
              </div>
            ));
          })()}
        </nav>

        {/* ══ STATUS ══ */}
        <div className="sb-status" title={!expanded ? 'System Online' : ''}>
          <Circle style={{ width: 6, height: 6, fill: '#22d3ee', color: '#22d3ee', flexShrink: 0 }} />
          {expanded && (
            <span style={{ color: getColor(colorOffset), fontSize: 9, fontFamily: 'Orbitron,sans-serif', letterSpacing: 1 }}>
              System Status · Online
            </span>
          )}
        </div>

        {/* ══ USER ══ */}
        <div className="sb-user" title={!expanded ? (user?.name || 'Admin') : ''}>
          <div className="sb-avatar">
            <img src={user?.avatar || 'https://i.pravatar.cc/34?img=3'} alt="avatar" />
          </div>
          {expanded && (
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontSize: 13, fontWeight: 700,
                color: getColor(1), textShadow: `0 0 8px ${getColor(1)}`,
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {user?.name || 'Admin User'}
              </div>
              <div style={{
                fontSize: 9, fontFamily: 'Orbitron,sans-serif', letterSpacing: 1,
                color: getColor(3), textShadow: `0 0 6px ${getColor(3)}`,
              }}>
                {user?.role || 'Super Admin'}
              </div>
            </div>
          )}
        </div>

      </aside>
    </>
  );
}

/* ══════════════════════════════════════════════════════
   CSS
══════════════════════════════════════════════════════ */
const SIDEBAR_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

/* Root */
.sidebar-root {
  height: 100vh;
  background: linear-gradient(180deg,#0d0618 0%,#080312 60%,#0a0215 100%);
  border-right: 1px solid #2a1245;
  display: flex; flex-direction: column;
  flex-shrink: 0; position: relative; overflow: hidden;
  font-family: 'Rajdhani', sans-serif;

  /* ✅ Smooth width transition */
  transition: width .32s cubic-bezier(.4,0,.2,1);
  will-change: width;
}
.sidebar-root::before {
  content:''; position:absolute; inset:0;
  background-image:
    linear-gradient(rgba(168,85,247,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(168,85,247,.04) 1px,transparent 1px);
  background-size:28px 28px; pointer-events:none; z-index:0;
}

/* Glow border */
.sb-glow-border {
  position:absolute; left:0; top:0; bottom:0; width:2px;
  background:linear-gradient(180deg,transparent 0%,#ff2d78 20%,#a855f7 50%,#22d3ee 80%,transparent 100%);
  animation:sbGlow 4s ease-in-out infinite alternate; z-index:2;
  pointer-events:none;
}
@keyframes sbGlow { 0%{opacity:.3} 100%{opacity:.9} }

/* ══ TOP CONTROLS ══ */
.sb-controls {
  display:flex; align-items:center; gap:6px;
  padding:10px 10px 8px;
  border-bottom:1px solid #1a0830; flex-shrink:0;
  position:relative; z-index:1; min-height:52px;
  overflow:hidden;
}

/* = বাটন */
.sb-eq-btn {
  width:30px; height:30px; border-radius:7px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  background:rgba(168,85,247,.08); border:1px solid rgba(168,85,247,.25);
  cursor:pointer; transition:all .2s;
}
.sb-eq-btn:hover {
  background:rgba(168,85,247,.2); border-color:rgba(168,85,247,.6);
  box-shadow:0 0 12px rgba(168,85,247,.3);
}

/* Logo text */
.sb-logo-text {
  flex:1; font-family:'Orbitron',sans-serif; font-size:9.5px;
  font-weight:700; letter-spacing:1px; line-height:1.4;
  white-space:nowrap; overflow:hidden;
  animation:fadeIn .25s ease;
}
@keyframes fadeIn { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }

/* Diamond icon (collapsed) */
.sb-logo-diamond-sm {
  width:28px; height:28px; flex-shrink:0;
  clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);
  animation:diamondPulse 2s ease-in-out infinite alternate;
}
@keyframes diamondPulse { 0%{opacity:.7} 100%{opacity:1;filter:brightness(1.3)} }

/* ◀ hide বাটন */
.sb-hide-btn {
  width:24px; height:24px; border-radius:5px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.06);
  cursor:pointer; transition:all .2s; margin-left:auto;
}
.sb-hide-btn:hover {
  background:rgba(255,45,120,.1); border-color:rgba(255,45,120,.3);
  box-shadow:0 0 8px rgba(255,45,120,.2);
}

/* Show বাটন (sidebar hidden হলে) */
.sb-show-btn {
  position:fixed; left:0; top:50%; transform:translateY(-50%);
  width:22px; height:48px; z-index:200;
  background:rgba(10,2,30,.95); border:1px solid rgba(168,85,247,.4);
  border-left:none; border-radius:0 8px 8px 0;
  display:flex; align-items:center; justify-content:center;
  cursor:pointer; transition:all .25s;
  box-shadow:4px 0 16px rgba(168,85,247,.2);
}
.sb-show-btn:hover {
  width:28px; background:rgba(168,85,247,.15);
  box-shadow:4px 0 24px rgba(168,85,247,.4);
}

/* ══ NAV ══ */
.sb-nav {
  flex:1; overflow-y:auto; overflow-x:hidden;
  padding:6px 0 8px; position:relative; z-index:1;
  scrollbar-width:thin; scrollbar-color:rgba(168,85,247,.4) transparent;
}
.sb-nav::-webkit-scrollbar { width:3px; }
.sb-nav::-webkit-scrollbar-track { background:transparent; }
.sb-nav::-webkit-scrollbar-thumb {
  background:linear-gradient(180deg,#ff2d78,#a855f7,#22d3ee);
  border-radius:2px;
}

/* Section header */
.sb-section-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:10px 10px 3px; cursor:pointer; user-select:none;
  min-height:28px;
}
.sb-section-title {
  font-family:'Orbitron',sans-serif; font-size:8px;
  font-weight:700; letter-spacing:1.5px;
}
.sb-section-dot {
  width:5px; height:5px; border-radius:50%;
  margin:0 auto; flex-shrink:0;
  box-shadow:0 0 5px currentColor;
}

/* Nav item */
.sb-item {
  display:flex; align-items:center; gap:0;
  padding:8px 8px 8px 10px; cursor:pointer; position:relative;
  transition:all .2s ease; border-left:2px solid transparent; margin:1px 0;
  min-height:38px; overflow:hidden;
}
.sb-item:hover { background:linear-gradient(90deg,rgba(168,85,247,.1),transparent); }
.sb-item.active {
  background:linear-gradient(90deg,rgba(255,45,120,.15),rgba(168,85,247,.07),transparent);
}
.sb-item.active::after {
  content:''; position:absolute; right:0; top:50%; transform:translateY(-50%);
  width:3px; height:55%; background:#ff2d78;
  border-radius:2px 0 0 2px; box-shadow:0 0 8px #ff2d78;
}

/* Icon */
.sb-icon {
  width:26px; height:26px; border-radius:6px;
  display:flex; align-items:center; justify-content:center;
  flex-shrink:0; transition:all .2s;
}
.sb-item:hover .sb-icon { transform:scale(1.1); }

/* Label */
.sb-label {
  font-size:13px; font-weight:700;
  flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  letter-spacing:.4px; padding-left:9px;
  animation:fadeIn .2s ease;
}

/* Badge */
.sb-badge {
  width:7px; height:7px; border-radius:50%;
  background:#ff2d78; box-shadow:0 0 6px #ff2d78;
  animation:sbPulse 1.5s ease-in-out infinite; flex-shrink:0;
}
.sb-badge-sm {
  width:6px; height:6px; border-radius:50%;
  background:#ff2d78; box-shadow:0 0 5px #ff2d78;
  animation:sbPulse 1.5s ease-in-out infinite;
  position:absolute; top:6px; right:6px;
}
@keyframes sbPulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.65)} }

/* ══ STATUS ══ */
.sb-status {
  display:flex; align-items:center; gap:5px;
  padding:5px 10px 8px; position:relative; z-index:1; flex-shrink:0;
  min-height:24px;
}

/* ══ USER ══ */
.sb-user {
  padding:10px 10px; border-top:1px solid #1a0830;
  display:flex; align-items:center; gap:8px;
  cursor:pointer; position:relative; z-index:1;
  transition:background .2s; flex-shrink:0; overflow:hidden;
}
.sb-user:hover { background:rgba(168,85,247,.07); }
.sb-avatar {
  width:34px; height:34px; border-radius:50%;
  border:2px solid #a855f7; box-shadow:0 0 10px #a855f744;
  overflow:hidden; flex-shrink:0;
}
.sb-avatar img { width:100%; height:100%; object-fit:cover; }

/* Scroll indicator — sidebar এর উপর scroll করলে hint দেখাবে */
.sidebar-root::after {
  content:''; position:absolute; top:52px; right:0; left:0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(168,85,247,.3), transparent);
  pointer-events:none; z-index:1;
}
`;



// // src/components/layout/Sidebar.jsx
// import React, { useState, useEffect } from 'react';
// import { useNavigate, useLocation } from 'react-router-dom';
// import {
//   LayoutDashboard, Users, Wallet, ClipboardList, Zap, GitBranch,
//   ShieldAlert, ScanSearch, UserCheck, History, Monitor,
//   BarChart3, MessageSquare, Gift, Star,
//   ChevronDown, ChevronRight, Circle, Bell, Globe,
//   Database, AlertTriangle, Settings, Lock, CreditCard,
//   BookOpen, RefreshCw, Layers, FlaskConical, Megaphone
// } from 'lucide-react';

// const COLORS = [
//   '#ff2d78','#ffd700','#00f3ff','#00ff88',
//   '#a855f7','#ff8c00','#4d79ff','#ff2df7',
//   '#39ff14','#0ff0fc','#ff6b35','#22d3ee',
// ];

// const NAV = [
//   {
//     section: 'MAIN',
//     items: [
//       { icon: LayoutDashboard, label: 'Dashboard',        path: '' },
//     ]
//   },
//   {
//     section: 'MANAGEMENT',
//     items: [
//       { icon: Users,           label: 'Users',            path: 'users' },
//       { icon: Wallet,          label: 'Wallet',           path: 'wallet' },
//       { icon: ClipboardList,   label: 'Tasks',            path: 'tasks' },
//       { icon: Zap,             label: 'Offerwall',        path: 'offerwall' },
//       { icon: GitBranch,       label: 'Referral',         path: 'referral' },
//     ]
//   },
//   {
//     section: 'SECURITY & COMPLIANCE',
//     items: [
//       { icon: ShieldAlert,     label: 'Security',         path: 'security' },
//       { icon: ScanSearch,      label: 'Fraud Detection',  path: 'fraud-detection', badge: true },
//       { icon: UserCheck,       label: 'KYC',              path: 'kyc' },
//       { icon: History,         label: 'Audit Logs',       path: 'audit-logs' },
//     ]
//   },
//   {
//     section: 'ANALYTICS & GROWTH',
//     items: [
//       { icon: BarChart3,       label: 'Analytics',        path: 'analytics' },
//       { icon: MessageSquare,   label: 'Engagement',       path: 'engagement' },
//       { icon: Gift,            label: 'Djoyalty',         path: 'djoyalty' },
//     ]
//   },
//   {
//     section: 'FINANCE & GATEWAYS',
//     items: [
//       { icon: CreditCard,      label: 'Payment Gateways', path: 'payment-gateways' },
//       { icon: Layers,          label: 'Ad Networks',      path: 'ad-networks' },
//     ]
//   },
//   {
//     section: 'SYSTEM & CONFIG',
//     items: [
//       { icon: Bell,            label: 'Notifications',    path: 'notifications' },
//       { icon: Globe,           label: 'Localization',     path: 'localization' },
//       { icon: BookOpen,        label: 'CMS',              path: 'cms' },
//       { icon: AlertTriangle,   label: 'Alerts',           path: 'alerts' },
//       { icon: MessageSquare,   label: 'Support',          path: 'support' },
//       { icon: RefreshCw,       label: 'Cache',            path: 'cache' },
//       { icon: Database,        label: 'Backup',           path: 'backup' },
//       { icon: Lock,            label: 'Rate Limit',       path: 'rate-limit' },
//       { icon: Settings,        label: 'Admin Panel',      path: 'settings' },
//       { icon: FlaskConical,    label: 'Tests',            path: 'tests' },
//       { icon: Megaphone,       label: 'Promotions',       path: 'promotions' },
//     ]
//   },
// ];

// export default function Sidebar({ user }) {
//   const navigate   = useNavigate();
//   const location   = useLocation();
//   const [collapsed, setCollapsed] = useState({});
//   const [colorOffset, setColorOffset] = useState(0);

//   useEffect(() => {
//     const timer = setInterval(() => {
//       setColorOffset(prev => (prev + 1) % COLORS.length);
//     }, 60000); // প্রতি ১ মিনিটে color shift
//     return () => clearInterval(timer);
//   }, []);

//   const activePath = location.pathname.replace('/', '') || '';
//   const toggle     = (s) => setCollapsed(p => ({ ...p, [s]: !p[s] }));
//   const handleNav  = (path) => navigate(path ? `/${path}` : '/');

//   // প্রতিটা item আলাদা color, offset দিয়ে cycle
//   const getColor = (globalIdx) => COLORS[(globalIdx + colorOffset) % COLORS.length];

//   // section title color
//   const getSectionColor = (sIdx) => COLORS[(sIdx * 3 + colorOffset) % COLORS.length];

//   return (
//     <>
//       <style>{`
//         @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

//         .sidebar-root {
//           width: 210px; height: 100vh;
//           background: linear-gradient(180deg,#0d0618 0%,#080312 60%,#0a0215 100%);
//           border-right: 1px solid #2a1245;
//           display: flex; flex-direction: column;
//           flex-shrink: 0; position: relative; overflow: hidden;
//           font-family: 'Rajdhani', sans-serif;
//         }
//         .sidebar-root::before {
//           content:''; position:absolute; inset:0;
//           background-image:
//             linear-gradient(rgba(168,85,247,.04) 1px,transparent 1px),
//             linear-gradient(90deg,rgba(168,85,247,.04) 1px,transparent 1px);
//           background-size:28px 28px; pointer-events:none; z-index:0;
//         }
//         .sidebar-root::after {
//           content:''; position:absolute; left:0; top:0; bottom:0; width:2px;
//           background:linear-gradient(180deg,transparent 0%,#ff2d78 20%,#a855f7 50%,#22d3ee 80%,transparent 100%);
//           animation:sbGlow 4s ease-in-out infinite alternate; z-index:2;
//         }
//         @keyframes sbGlow { 0%{opacity:.3} 100%{opacity:.9} }

//         .sb-logo {
//           padding:16px 16px 12px; display:flex; align-items:center; gap:10px;
//           position:relative; z-index:1; border-bottom:1px solid #1a0830; flex-shrink:0;
//         }
//         .sb-logo-diamond {
//           width:36px; height:36px;
//           background:linear-gradient(135deg,#ff2d78,#a855f7);
//           clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);
//           flex-shrink:0;
//           animation:diamondPulse 2s ease-in-out infinite alternate;
//         }
//         @keyframes diamondPulse {
//           0%  { box-shadow:0 0 10px #ff2d7866; }
//           100%{ box-shadow:0 0 28px #a855f7aa,0 0 50px #ff2d7844; }
//         }
//         .sb-logo-text {
//           font-family:'Orbitron',sans-serif; font-size:9.5px;
//           font-weight:700; letter-spacing:1px; line-height:1.4;
//         }

//         .sb-nav {
//           flex:1; overflow-y:auto; overflow-x:hidden;
//           padding:6px 0 8px; position:relative; z-index:1;
//         }
//         .sb-nav::-webkit-scrollbar { width:3px; }
//         .sb-nav::-webkit-scrollbar-track { background:transparent; }
//         .sb-nav::-webkit-scrollbar-thumb {
//           background:linear-gradient(180deg,#ff2d78,#a855f7,#22d3ee);
//           border-radius:2px;
//         }

//         .sb-section-header {
//           display:flex; align-items:center; justify-content:space-between;
//           padding:10px 16px 3px; cursor:pointer; user-select:none;
//         }
//         .sb-section-title {
//           font-family:'Orbitron',sans-serif; font-size:8px;
//           font-weight:700; letter-spacing:1.5px;
//           transition: color 1s ease, text-shadow 1s ease;
//         }

//         .sb-item {
//           display:flex; align-items:center; gap:9px;
//           padding:8px 14px 8px 16px; cursor:pointer; position:relative;
//           transition:all .2s ease; border-left:2px solid transparent; margin:1px 0;
//         }
//         .sb-item:hover { background:linear-gradient(90deg,rgba(168,85,247,.1),transparent); }
//         .sb-item.active {
//           background:linear-gradient(90deg,rgba(255,45,120,.15),rgba(168,85,247,.07),transparent);
//           border-left-color:#ff2d78;
//         }
//         .sb-item.active::after {
//           content:''; position:absolute; right:0; top:50%; transform:translateY(-50%);
//           width:3px; height:55%; background:#ff2d78;
//           border-radius:2px 0 0 2px; box-shadow:0 0 8px #ff2d78;
//         }

//         .sb-icon {
//           width:26px; height:26px; border-radius:6px;
//           display:flex; align-items:center; justify-content:center;
//           flex-shrink:0; transition:all 1s ease;
//         }

//         .sb-label {
//           font-size:13px; font-weight:700;
//           flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
//           transition: color 1s ease, text-shadow 1s ease;
//           letter-spacing:.4px;
//         }

//         .sb-badge {
//           width:7px; height:7px; border-radius:50%;
//           background:#ff2d78; box-shadow:0 0 6px #ff2d78;
//           animation:sbPulse 1.5s ease-in-out infinite; flex-shrink:0;
//         }
//         @keyframes sbPulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.65)} }

//         .sb-status {
//           display:flex; align-items:center; gap:5px; font-size:9px;
//           font-family:'Orbitron',sans-serif;
//           padding:5px 16px 8px; position:relative; z-index:1; flex-shrink:0;
//           transition: color 1s ease;
//         }
//         .sb-user {
//           padding:10px 14px; border-top:1px solid #1a0830;
//           display:flex; align-items:center; gap:10px;
//           cursor:pointer; position:relative; z-index:1;
//           transition:background .2s; flex-shrink:0;
//         }
//         .sb-user:hover { background:rgba(168,85,247,.07); }
//         .sb-avatar {
//           width:34px; height:34px; border-radius:50%;
//           border:2px solid #a855f7; box-shadow:0 0 10px #a855f744;
//           overflow:hidden; flex-shrink:0;
//         }
//         .sb-avatar img { width:100%; height:100%; object-fit:cover; }
//       `}</style>

//       <aside className="sidebar-root">

//         {/* Logo */}
//         <div className="sb-logo">
//           <div className="sb-logo-diamond" />
//           <div className="sb-logo-text">
//             <span style={{ color: getColor(0), textShadow: `0 0 10px ${getColor(0)}`, transition:'color 1s ease,text-shadow 1s ease' }}>
//               EARNING PLATFORM
//             </span><br />
//             <span style={{ color: getColor(2), textShadow: `0 0 10px ${getColor(2)}`, transition:'color 1s ease,text-shadow 1s ease' }}>
//               ADMIN PANEL
//             </span>
//           </div>
//         </div>

//         {/* Nav */}
//         <nav className="sb-nav">
//           {(() => {
//             let globalIdx = 0;
//             return NAV.map(({ section, items }, sIdx) => (
//               <div key={section}>
//                 <div className="sb-section-header" onClick={() => toggle(section)}>
//                   <span
//                     className="sb-section-title"
//                     style={{
//                       color: getSectionColor(sIdx),
//                       textShadow: `0 0 8px ${getSectionColor(sIdx)}`,
//                     }}
//                   >
//                     {section}
//                   </span>
//                   {collapsed[section]
//                     ? <ChevronRight style={{ width:9, height:9, color:'#4a2a6a', flexShrink:0 }} />
//                     : <ChevronDown  style={{ width:9, height:9, color:'#4a2a6a', flexShrink:0 }} />
//                   }
//                 </div>

//                 {!collapsed[section] && items.map(({ icon: Icon, label, path, badge }) => {
//                   const ic = getColor(globalIdx++);
//                   return (
//                     <div
//                       key={`${section}-${label}`}
//                       className={`sb-item ${activePath === path ? 'active' : ''}`}
//                       onClick={() => handleNav(path)}
//                     >
//                       <div className="sb-icon" style={{
//                         background: `${ic}18`,
//                         border: `1px solid ${ic}40`,
//                         boxShadow: activePath === path ? `0 0 12px ${ic}` : 'none',
//                       }}>
//                         <Icon style={{ width:13, height:13, color: ic }} />
//                       </div>

//                       <span className="sb-label" style={{
//                         color: ic,
//                         textShadow: `0 0 10px ${ic}, 0 0 20px ${ic}88`,
//                       }}>
//                         {label}
//                       </span>

//                       {badge && <span className="sb-badge" />}
//                     </div>
//                   );
//                 })}
//               </div>
//             ));
//           })()}
//         </nav>

//         {/* Status */}
//         <div className="sb-status" style={{ color: getColor(colorOffset) }}>
//           <Circle style={{ width:6, height:6, fill:'#22d3ee', color:'#22d3ee' }} />
//           System Status · Online
//         </div>

//         {/* User */}
//         <div className="sb-user">
//           <div className="sb-avatar">
//             <img src={user?.avatar || 'https://i.pravatar.cc/34?img=3'} alt="avatar" />
//           </div>
//           <div>
//             <div style={{
//               fontSize:13, fontWeight:700,
//               color: getColor(1),
//               textShadow: `0 0 8px ${getColor(1)}`,
//               transition:'color 1s ease',
//             }}>
//               {user?.name || 'Admin User'}
//             </div>
//             <div style={{
//               fontSize:9, fontFamily:'Orbitron,sans-serif', letterSpacing:1,
//               color: getColor(3),
//               textShadow: `0 0 6px ${getColor(3)}`,
//               transition:'color 1s ease',
//             }}>
//               {user?.role || 'Super Admin'}
//             </div>
//           </div>
//         </div>

//       </aside>
//     </>
//   );
// }
