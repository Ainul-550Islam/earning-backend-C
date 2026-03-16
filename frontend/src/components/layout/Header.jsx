// src/components/layout/Header.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Bell, User, ChevronDown, LogOut, Settings,
  Shield, Activity, UserCircle, Key, ChevronRight,
  Calendar, Cpu
} from 'lucide-react';

const MENU_ITEMS = [
  { icon: UserCircle, label: 'My Profile',        path: '/profile', tab: 'profile',  color: '#22d3ee' },
  { icon: Settings,   label: 'Account Settings',  path: '/profile', tab: 'settings', color: '#a855f7' },
  { icon: Activity,   label: 'Activity Logs',     path: '/profile', tab: 'activity', color: '#f7c948' },
  { divider: true },
  { icon: Key,        label: 'Change Password',   path: '/profile', tab: 'security', color: '#ff8c00' },
  { icon: Shield,     label: '2FA Security',      path: '/profile', tab: 'twofa',    color: '#22d3ee' },
  { divider: true },
  { icon: Cpu,        label: 'System Preferences',path: '/profile', tab: 'settings', color: '#a855f7' },
  { divider: true },
  { icon: LogOut,     label: 'Logout',            logout: true,                      color: '#ff2d78' },
];

const token = () =>
  localStorage.getItem('adminAccessToken') ||
  localStorage.getItem('access_token') || '';

const timeAgo = (d) => {
  if (!d) return '';
  const diff = Math.floor((Date.now() - new Date(d)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
};

export default function Header({ user, onLogout }) {
  const navigate = useNavigate();
  const [showMenu,    setShowMenu]    = useState(false);
  const [showNotif,   setShowNotif]   = useState(false);
  const [notifs,      setNotifs]      = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [search,      setSearch]      = useState('');
  const menuRef  = useRef(null);
  const notifRef = useRef(null);

  // ── Fetch notifications from real API ──────────────────────────────────
  // GET /api/notifications/notifications/?page_size=5
  // GET /api/notifications/unread-count/
  const fetchNotifs = () => {
    const t = token();
    if (!t) return;
    const headers = { 'Authorization': `Bearer ${t}` };

    Promise.all([
      fetch('/api/notifications/notifications/?page_size=8&ordering=-created_at', { headers }),
      fetch('/api/notifications/unread-count/', { headers }),
    ])
      .then(([r1, r2]) => Promise.all([
        r1.ok ? r1.json() : null,
        r2.ok ? r2.json() : null,
      ]))
      .then(([listData, countData]) => {
        if (listData) {
          const list = Array.isArray(listData) ? listData : (listData.results || []);
          setNotifs(list);
        }
        if (countData) {
          setUnreadCount(countData.count ?? countData.unread_count ?? 0);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchNotifs();
    // Refresh every 30 seconds
    const interval = setInterval(fetchNotifs, 30000);
    return () => clearInterval(interval);
  }, []);

  // ── Close dropdowns on outside click ──────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current  && !menuRef.current.contains(e.target))  setShowMenu(false);
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotif(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Mark notification as read ─────────────────────────────────────────
  const markRead = (id) => {
    const t = token();
    if (!t || !id) return;
    fetch(`/api/notifications/notifications/${id}/mark_read/`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${t}` },
    }).then(() => {
      setNotifs(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    }).catch(() => {});
  };

  const dateStr = new Date().toLocaleDateString('en-US', {
    month: 'short', day: '2-digit', year: 'numeric'
  });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Rajdhani:wght@500;600;700&display=swap');
        .hdr-root {
          height: 58px;
          background: linear-gradient(90deg, #0d0618 0%, #080312 100%);
          border-bottom: 1px solid #1a0830;
          display: flex; align-items: center; justify-content: space-between;
          padding: 0 22px; flex-shrink: 0;
          position: relative; z-index: 100;
          font-family: 'Rajdhani', sans-serif;
        }
        .hdr-root::after {
          content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
          background: linear-gradient(90deg, transparent 0%, #ff2d78 20%, #a855f7 50%, #22d3ee 80%, transparent 100%);
          opacity: .5;
        }
        .hdr-title { font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 2px; color: #c8a8e8; }
        .hdr-title span { color: #a855f7; }
        .hdr-search {
          display: flex; align-items: center; gap: 8px;
          background: #12052a; border: 1px solid #2a1245;
          border-radius: 20px; padding: 7px 16px; width: 220px;
          transition: border-color .2s, box-shadow .2s;
        }
        .hdr-search:focus-within { border-color: #a855f7; box-shadow: 0 0 0 2px #a855f722; }
        .hdr-search input {
          background: none; border: none; outline: none;
          color: #c8a8e8; font-size: 12px;
          font-family: 'Rajdhani', sans-serif; font-weight: 500; width: 100%;
        }
        .hdr-search input::placeholder { color: #4a2a6a; }
        .hdr-right { display: flex; align-items: center; gap: 14px; }
        .hdr-date {
          display: flex; align-items: center; gap: 6px;
          font-size: 12px; font-weight: 600; color: #7a5a9a;
          font-family: 'Orbitron', sans-serif; letter-spacing: .5px;
        }
        .hdr-icon-btn {
          position: relative; width: 36px; height: 36px;
          border-radius: 8px; background: #12052a; border: 1px solid #2a1245;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; transition: all .2s;
        }
        .hdr-icon-btn:hover { border-color: #a855f7; box-shadow: 0 0 10px #a855f733; background: #1a0830; }
        .hdr-badge {
          position: absolute; top: -4px; right: -4px;
          min-width: 16px; height: 16px; border-radius: 8px;
          background: #ff2d78; color: #fff; font-size: 9px; font-weight: 700;
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 0 6px #ff2d78; font-family: 'Orbitron', sans-serif; padding: 0 3px;
        }
        .hdr-user-chip {
          display: flex; align-items: center; gap: 9px;
          background: #12052a; border: 1px solid #2a1245;
          border-radius: 22px; padding: 4px 12px 4px 4px;
          cursor: pointer; transition: all .2s; position: relative;
        }
        .hdr-user-chip:hover { border-color: #a855f7; box-shadow: 0 0 12px #a855f733; }
        .hdr-avatar { width: 30px; height: 30px; border-radius: 50%; border: 2px solid #ff2d78; box-shadow: 0 0 8px #ff2d7844; overflow: hidden; flex-shrink: 0; }
        .hdr-avatar img { width: 100%; height: 100%; object-fit: cover; }
        .hdr-uname { font-size: 13px; font-weight: 700; color: #e8d0ff; }
        .hdr-urole { font-size: 10px; color: #a855f7; font-family: 'Orbitron', sans-serif; letter-spacing: .5px; }
        .hdr-dropdown {
          position: absolute; top: calc(100% + 10px); right: 0; width: 230px;
          background: linear-gradient(135deg, #0d0618, #120524);
          border: 1px solid #2a1245; border-radius: 12px; overflow: hidden;
          box-shadow: 0 20px 60px #00000088, 0 0 0 1px #ff2d7822;
          animation: dropIn .2s ease; z-index: 1000;
        }
        @keyframes dropIn { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:translateY(0); } }
        .hdr-dd-header {
          padding: 14px 16px;
          background: linear-gradient(90deg, #ff2d7812, #a855f712);
          border-bottom: 1px solid #1a0830;
          display: flex; align-items: center; gap: 10px;
        }
        .hdr-dd-avatar { width: 38px; height: 38px; border-radius: 50%; border: 2px solid #ff2d78; box-shadow: 0 0 10px #ff2d7855; overflow: hidden; flex-shrink: 0; }
        .hdr-dd-avatar img { width: 100%; height: 100%; object-fit: cover; }
        .hdr-dd-name { font-size: 14px; font-weight: 700; color: #fff; }
        .hdr-dd-role { font-size: 10px; color: #a855f7; font-family: 'Orbitron', sans-serif; letter-spacing: .5px; }
        .hdr-dd-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; cursor: pointer; transition: background .15s; position: relative; }
        .hdr-dd-item:hover { background: rgba(168,85,247,.1); }
        .hdr-dd-icon { width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .hdr-dd-label { font-size: 13px; font-weight: 600; color: #c8a8e8; flex: 1; }
        .hdr-dd-item.logout .hdr-dd-label { color: #ff2d78; }
        .hdr-dd-item.logout:hover { background: rgba(255,45,120,.12); }
        .hdr-divider { height: 1px; background: #1a0830; margin: 3px 0; }
        .hdr-notif-panel {
          position: absolute; top: calc(100% + 10px); right: 0; width: 300px;
          background: linear-gradient(135deg, #0d0618, #120524);
          border: 1px solid #2a1245; border-radius: 12px; overflow: hidden;
          box-shadow: 0 20px 60px #00000088;
          animation: dropIn .2s ease; z-index: 1000;
        }
        .hdr-notif-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 12px 16px; border-bottom: 1px solid #1a0830;
        }
        .hdr-notif-title { font-family: 'Orbitron', sans-serif; font-size: 11px; font-weight: 700; color: #e8d0ff; letter-spacing: 1px; }
        .hdr-notif-all { font-size: 10px; color: #a855f7; cursor: pointer; font-family: 'Orbitron', sans-serif; }
        .hdr-notif-all:hover { color: #c8a8e8; }
        .hdr-notif-item { padding: 11px 16px; border-bottom: 1px solid #1a0830; cursor: pointer; transition: background .15s; }
        .hdr-notif-item:hover { background: rgba(168,85,247,.08); }
        .hdr-notif-item.unread { background: rgba(168,85,247,.05); }
        .hdr-notif-msg { font-size: 12px; color: #c8a8e8; font-weight: 500; }
        .hdr-notif-msg.read { color: #7a5a9a; }
        .hdr-notif-time { font-size: 10px; color: #4a2a6a; margin-top: 3px; font-family: 'Orbitron', sans-serif; }
        .hdr-notif-dot { width: 8px; height: 8px; border-radius: 50%; background: #ff2d78; box-shadow: 0 0 5px #ff2d78; flex-shrink: 0; margin-top: 3px; }
        .hdr-notif-dot.read { background: #2a1245; box-shadow: none; }
        .hdr-notif-empty { padding: 20px 16px; text-align: center; font-size: 11px; color: #4a2a6a; font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }
      `}</style>

      <header className="hdr-root">

        <div className="hdr-title">
          EARNING PLATFORM <span>ADMIN PANEL</span>
        </div>

        <div className="hdr-search">
          <Search style={{ width:14, height:14, color:'#4a2a6a', flexShrink:0 }} />
          <input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} />
          <ChevronDown style={{ width:12, height:12, color:'#4a2a6a', flexShrink:0 }} />
        </div>

        <div className="hdr-right">

          <div className="hdr-date">
            <Calendar style={{ width:13, height:13, color:'#a855f7' }} />
            {dateStr}
          </div>

          {/* ── Notifications ── real API: /api/notifications/notifications/ ── */}
          <div style={{ position:'relative' }} ref={notifRef}>
            <div className="hdr-icon-btn" onClick={() => { setShowNotif(v => !v); setShowMenu(false); }}>
              <Bell style={{ width:16, height:16, color:'#c8a8e8' }} />
              {unreadCount > 0 && <span className="hdr-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
            </div>

            {showNotif && (
              <div className="hdr-notif-panel">
                <div className="hdr-notif-header">
                  <div className="hdr-notif-title">NOTIFICATIONS</div>
                  <span className="hdr-notif-all" onClick={() => { setShowNotif(false); navigate('/notifications'); }}>
                    View all →
                  </span>
                </div>

                {notifs.length === 0 ? (
                  <div className="hdr-notif-empty">NO NEW NOTIFICATIONS</div>
                ) : (
                  notifs.slice(0, 6).map((n) => (
                    // NotificationSerializer fields:
                    // id, title, message, body, is_read, created_at, notification_type
                    <div
                      key={n.id}
                      className={`hdr-notif-item ${!n.is_read ? 'unread' : ''}`}
                      onClick={() => {
                        if (!n.is_read) markRead(n.id);
                        setShowNotif(false);
                        navigate('/notifications');
                      }}
                    >
                      <div style={{ display:'flex', gap:10 }}>
                        <div className={`hdr-notif-dot ${n.is_read ? 'read' : ''}`} />
                        <div style={{ flex:1, minWidth:0 }}>
                          <div className={`hdr-notif-msg ${n.is_read ? 'read' : ''}`}>
                            {n.title || n.message || n.body || 'Notification'}
                          </div>
                          {(n.message || n.body) && n.title && (
                            <div style={{ fontSize:'11px', color:'#4a2a6a', marginTop:'2px', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                              {n.message || n.body}
                            </div>
                          )}
                          <div className="hdr-notif-time">{timeAgo(n.created_at)}</div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="hdr-icon-btn">
            <User style={{ width:16, height:16, color:'#c8a8e8' }} />
          </div>

          {/* ── User Chip + Dropdown ── */}
          <div style={{ position:'relative' }} ref={menuRef}>
            <div className="hdr-user-chip" onClick={() => { setShowMenu(v => !v); setShowNotif(false); }}>
              <div className="hdr-avatar">
                <img src={user?.avatar || 'https://i.pravatar.cc/30?img=3'} alt="avatar" />
              </div>
              <div>
                <div className="hdr-uname">{user?.name || 'Admin User'}</div>
                <div className="hdr-urole">{user?.role || 'Super Admin'}</div>
              </div>
              <ChevronDown style={{
                width:12, height:12, color:'#7a5a9a', marginLeft:2,
                transition:'transform .2s', transform: showMenu ? 'rotate(180deg)' : 'none'
              }} />
            </div>

            {showMenu && (
              <div className="hdr-dropdown">
                <div className="hdr-dd-header">
                  <div className="hdr-dd-avatar">
                    <img src={user?.avatar || 'https://i.pravatar.cc/38?img=3'} alt="" />
                  </div>
                  <div>
                    <div className="hdr-dd-name">{user?.name || 'Admin User'}</div>
                    <div className="hdr-dd-role">{user?.role || 'Super Admin'}</div>
                  </div>
                </div>

                {MENU_ITEMS.map((item, i) => {
                  if (item.divider) return <div key={i} className="hdr-divider" />;
                  const Icon = item.icon;
                  return (
                    <div
                      key={i}
                      className={`hdr-dd-item ${item.logout ? 'logout' : ''}`}
                      onClick={() => {
                        setShowMenu(false);
                        if (item.logout) { onLogout?.(); }
                        else if (item.path) { navigate(item.path, { state: { tab: item.tab } }); }
                      }}
                    >
                      <div className="hdr-dd-icon" style={{ background:`${item.color}18`, border:`1px solid ${item.color}33` }}>
                        <Icon style={{ width:14, height:14, color:item.color }} />
                      </div>
                      <span className="hdr-dd-label">{item.label}</span>
                      {!item.logout && <ChevronRight style={{ width:12, height:12, color:'#4a2a6a' }} />}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>
      </header>
    </>
  );
}