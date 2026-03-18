// src/pages/Users.jsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import '../styles/users.css';
import {
  Search, ChevronDown, Users, UserCheck, UserX,
  ShieldAlert, Star, CheckCircle, Activity,
  SkipBack, Square, Play, BarChart2, Smartphone,
  Shield, Eye, Plus, Edit3, Trash2, X, Save,
  RefreshCw, Lock, Unlock, AlertTriangle, UserPlus,
  Filter, MoreVertical, Phone, Mail, MapPin, Calendar,
  TrendingUp, Award, Key, Ban, CheckSquare
} from 'lucide-react';
import toast from 'react-hot-toast';

/* ══════════════════════════════════
   API HELPERS  (real API — unchanged)
══════════════════════════════════ */
const getToken = () => localStorage.getItem('adminAccessToken');
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
const apiFetch = (url, opts = {}) =>
  fetch(BASE_URL.replace('/api', '') + url, {
    headers: {
      Authorization: `Bearer ${getToken()}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
    ...opts,
  }).then(r => r.json());

/* ── Mini sparkline ── */
const MiniChart = ({ color, points = [30, 45, 28, 60, 42, 70, 55, 80] }) => {
  const max = Math.max(...points), min = Math.min(...points);
  const norm = v => 24 - ((v - min) / (max - min || 1)) * 22;
  const d = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (points.length - 1)) * 80},${norm(v)}`).join(' ');
  const uid = color.replace('#', '');
  return (
    <svg viewBox="0 0 80 26" style={{ width: '100%', height: 28, display: 'block' }}>
      <defs>
        <linearGradient id={`g-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${d}V26 L0,26 Z`} fill={`url(#g-${uid})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
    </svg>
  );
};

/* ── Dropdown ── */
const Dropdown = ({ label, items, onSelect, btnClass = 'actions' }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  return (
    <div className="dropdown-wrap" ref={ref}>
      <button className={`uc-action-btn ${btnClass}`} onClick={() => setOpen(!open)}>
        {label} <ChevronDown style={{ width: 11, height: 11 }} />
      </button>
      {open && (
        <div className="dropdown-menu">
          {items.map((item, i) => (
            <div key={i} className={`dropdown-item ${item.danger ? 'danger' : ''} ${item.warning ? 'warning' : ''}`}
              onClick={() => { onSelect?.(item); setOpen(false); }}>
              {item.icon && <span className="di-icon">{item.icon}</span>}
              {item.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Vertical Slider ── */
const VSlider = ({ defaultVal = 55 }) => {
  const [val, setVal] = useState(defaultVal);
  return (
    <div className="v-slider-wrap">
      <div className="v-slider-track" style={{ height: 70 }}
        onClick={e => {
          const r = e.currentTarget.getBoundingClientRect();
          setVal(Math.round((1 - (e.clientY - r.top) / r.height) * 100));
        }}>
        <div className="v-slider-fill" style={{ height: `${val}%` }} />
        <div className="v-slider-thumb" style={{ bottom: `calc(${val}% - 8px)` }} />
      </div>
      <span className="v-slider-label">{val}%</span>
    </div>
  );
};

/* ══════════════════════════════════
   CREATE USER MODAL
══════════════════════════════════ */
const CreateUserModal = ({ onClose, onCreated }) => {
  const [form, setForm] = useState({ phone: '', email: '', password: '', username: '', device_id: 'admin-created-' + Date.now() });
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    if (!form.phone || !form.password) {
      toast.error('Phone & password required');
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch('/api/auth/register/', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      if (res.user_id || res.message) {
        toast.success('✅ User created successfully!');
        onCreated?.();
        onClose();
      } else {
        toast.error(res.error || 'Creation failed');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box create-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header create-header">
          <div className="modal-title-row">
            <div className="modal-icon-wrap create-icon"><UserPlus size={18} /></div>
            <div>
              <div className="modal-title">Create New User</div>
              <div className="modal-sub">Register a new user account</div>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label"><Phone size={12} /> Phone Number *</label>
              <input className="form-input" placeholder="+880XXXXXXXXXX"
                value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label"><Mail size={12} /> Email</label>
              <input className="form-input" placeholder="user@example.com" type="email"
                value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label"><Key size={12} /> Username</label>
              <input className="form-input" placeholder="username"
                value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label"><Lock size={12} /> Password *</label>
              <input className="form-input" placeholder="••••••••" type="password"
                value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="modal-btn cancel-btn" onClick={onClose}>Cancel</button>
          <button className="modal-btn create-btn" onClick={handleCreate} disabled={loading}>
            {loading ? <RefreshCw size={14} className="spin" /> : <UserPlus size={14} />}
            {loading ? 'Creating...' : 'Create User'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════
   EDIT USER MODAL
══════════════════════════════════ */
const EditUserModal = ({ user, onClose, onUpdated }) => {
  const [form, setForm] = useState({
    username: user.username || '',
    email: user.email || '',
    phone: user.phone || '',
    first_name: user.first_name || '',
    last_name: user.last_name || '',
  });
  const [loading, setLoading] = useState(false);

  const handleUpdate = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/users/${user.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(form),
      });
      if (res.id || res.username) {
        toast.success('✅ User updated successfully!');
        onUpdated?.();
        onClose();
      } else {
        toast.error(res.error || 'Update failed');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box edit-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header edit-header">
          <div className="modal-title-row">
            <div className="modal-icon-wrap edit-icon"><Edit3 size={18} /></div>
            <div>
              <div className="modal-title">Edit User</div>
              <div className="modal-sub">@{user.username}</div>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label"><Key size={12} /> Username</label>
              <input className="form-input" value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label"><Mail size={12} /> Email</label>
              <input className="form-input" type="email" value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label"><Phone size={12} /> Phone</label>
              <input className="form-input" value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">First Name</label>
              <input className="form-input" value={form.first_name}
                onChange={e => setForm({ ...form, first_name: e.target.value })} />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="modal-btn cancel-btn" onClick={onClose}>Cancel</button>
          <button className="modal-btn edit-btn" onClick={handleUpdate} disabled={loading}>
            {loading ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════
   VIEW DETAIL MODAL
══════════════════════════════════ */
const ViewDetailModal = ({ user, onClose }) => (
  <div className="modal-overlay" onClick={onClose}>
    <div className="modal-box view-modal" onClick={e => e.stopPropagation()}>
      <div className="modal-header view-header">
        <div className="modal-title-row">
          <div className="modal-icon-wrap view-icon"><Eye size={18} /></div>
          <div>
            <div className="modal-title">User Details</div>
            <div className="modal-sub">Full profile information</div>
          </div>
        </div>
        <button className="modal-close" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="modal-body">
        <div className="view-avatar-section">
          <div className="view-avatar">
            {((user.first_name?.[0] || '') + (user.last_name?.[0] || '')) || user.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="view-name">{[user.first_name, user.last_name].filter(Boolean).join(' ') || user.username}</div>
          <div className="view-badges">
            {user.is_verified && <span className="vbadge verified"><CheckCircle size={10} /> Verified</span>}
            {user.is_active && <span className="vbadge active"><Activity size={10} /> Active</span>}
            {user.role && <span className="vbadge role">{user.role}</span>}
          </div>
        </div>
        <div className="detail-grid">
          {[
            { icon: <Mail size={12} />, label: 'Email', val: user.email || '—', color: '#00f3ff' },
            { icon: <Phone size={12} />, label: 'Phone', val: user.phone || '—', color: '#00ff88' },
            { icon: <Key size={12} />, label: 'Username', val: user.username || '—', color: '#ffd700' },
            { icon: <TrendingUp size={12} />, label: 'Balance', val: `$${user.balance || 0}`, color: '#00f3ff' },
            { icon: <Award size={12} />, label: 'Total Earned', val: `$${user.total_earned || 0}`, color: '#ffd700' },
            { icon: <Users size={12} />, label: 'Referrals', val: user.referral_count || 0, color: '#00ff88' },
            { icon: <MapPin size={12} />, label: 'Country', val: user.country || '—', color: '#a78bfa' },
            { icon: <Calendar size={12} />, label: 'Joined', val: user.created_at ? new Date(user.created_at).toLocaleDateString() : '—', color: '#f472b6' },
          ].map(({ icon, label, val, color }) => (
            <div key={label} className="detail-item">
              <div className="detail-icon" style={{ color }}>{icon}</div>
              <div>
                <div className="detail-label">{label}</div>
                <div className="detail-val" style={{ color }}>{val}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="modal-footer">
        <button className="modal-btn cancel-btn" onClick={onClose}>Close</button>
      </div>
    </div>
  </div>
);

/* ══════════════════════════════════
   DELETE CONFIRM MODAL
══════════════════════════════════ */
const DeleteModal = ({ user, onClose, onDeleted }) => {
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState('');

  const handleDelete = async () => {
    if (confirm !== user.username) {
      toast.error('Type username to confirm');
      return;
    }
    setLoading(true);
    try {
      await fetch(`/api/users/${user.id}/`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      toast.success('🗑 User deleted');
      onDeleted?.();
      onClose();
    } catch {
      toast.error('Delete failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box delete-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header delete-header">
          <div className="modal-title-row">
            <div className="modal-icon-wrap delete-icon"><Trash2 size={18} /></div>
            <div>
              <div className="modal-title">Delete User</div>
              <div className="modal-sub">This action is irreversible</div>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div className="delete-warning">
            <AlertTriangle size={20} />
            <div>
              <div className="dw-title">Permanently delete <strong>@{user.username}</strong>?</div>
              <div className="dw-sub">All data, transactions, referrals will be lost forever.</div>
            </div>
          </div>
          <div className="form-group" style={{ marginTop: 16 }}>
            <label className="form-label">Type <strong style={{ color: '#ff2244' }}>{user.username}</strong> to confirm</label>
            <input className="form-input danger-input" placeholder={user.username}
              value={confirm} onChange={e => setConfirm(e.target.value)} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="modal-btn cancel-btn" onClick={onClose}>Cancel</button>
          <button className="modal-btn delete-btn" onClick={handleDelete}
            disabled={loading || confirm !== user.username}>
            {loading ? <RefreshCw size={14} className="spin" /> : <Trash2 size={14} />}
            {loading ? 'Deleting...' : 'Delete User'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ══════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════ */
const UsersPage = () => {
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('role');
  const [tierFilter, setTierFilter] = useState('tier');
  const [verFilter, setVerFilter] = useState('verification');
  const [countryFilter, setCountryFilter] = useState('country');

  // Real data state
  const [users, setUsers] = useState([]);
  const [kycQueue, setKycQueue] = useState([]);
  const [fraudLogs, setFraudLogs] = useState([]);
  const [riskProfiles, setRiskProfiles] = useState({});
  const [stats, setStats] = useState({ total: 0, verified: 0, banned: 0, avgRisk: 0 });
  const [loading, setLoading] = useState(true);

  // CRUD modal state
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [viewUser, setViewUser] = useState(null);
  const [deleteUser, setDeleteUser] = useState(null);
  const [actionLoading, setActionLoading] = useState({});

  /* ── Load all data ── */
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [usersData, kycData, riskData] = await Promise.all([
        apiFetch('/api/users/'),
        apiFetch('/api/kyc/').catch(() => []),
        apiFetch('/api/fraud_detection/risk-profiles/').catch(() => []),
      ]);

      const userList = Array.isArray(usersData) ? usersData : (usersData?.results ?? []);
      setUsers(userList);

      const riskMap = {};
      if (Array.isArray(riskData)) riskData.forEach(r => { riskMap[r.user] = r; });
      setRiskProfiles(riskMap);

      const verifiedCount = userList.filter(u => u.is_verified).length;
      const bannedCount = userList.filter(u => u.is_banned || u.status === 'banned').length;
      const avgRisk = Array.isArray(riskData) && riskData.length > 0
        ? (riskData.reduce((s, r) => s + (r.risk_score || 0), 0) / riskData.length).toFixed(1) : 0;
      setStats({ total: userList.length, verified: verifiedCount, banned: bannedCount, avgRisk });

      const kycList = Array.isArray(kycData) ? kycData : (kycData?.results ?? []);
      const pendingKyc = kycList.filter(k => k.status === 'pending' || k.status === 'submitted').slice(0, 5)
        .map(k => ({ name: k.full_name || k.user?.username || 'User', status: k.status, id: k.id, userId: k.user, btn: 'approve', btnLabel: 'Approve' }));
      setKycQueue(pendingKyc.length > 0 ? pendingKyc : [{ name: 'No pending KYC', status: '—', btn: '', btnLabel: '' }]);

      try {
        const attempts = await apiFetch('/api/fraud_detection/attempts/');
        const attemptList = Array.isArray(attempts) ? attempts : (attempts?.results ?? []);
        setFraudLogs(attemptList.slice(0, 3).map(a => ({
          eventType: a.fraud_type || 'Fraud Event',
          event: a.description || 'Suspicious Activity',
          severity: 'Severity', sevVal: a.severity || 'Medium',
          sevClass: (a.severity || '').toLowerCase() === 'high' ? 'high' : (a.severity || '').toLowerCase() === 'low' ? 'low' : 'pulsed',
        })));
      } catch {
        setFraudLogs([{ eventType: 'No fraud logs', event: '—', severity: '—', sevVal: '—', sevClass: 'low' }]);
      }
    } catch (e) {
      console.error('Users page error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  /* ── Verify user ── */
  const handleVerify = async (user) => {
    setActionLoading(p => ({ ...p, [`verify_${user.id}`]: true }));
    try {
      await apiFetch(`/api/users/${user.id}/verify_user/`, { method: 'POST' });
      toast.success(`✅ ${user.username} verified!`);
      loadData();
    } catch {
      toast.error('Verification failed');
    } finally {
      setActionLoading(p => ({ ...p, [`verify_${user.id}`]: false }));
    }
  };

  /* ── Deactivate user ── */
  const handleDeactivate = async (user) => {
    setActionLoading(p => ({ ...p, [`deactivate_${user.id}`]: true }));
    try {
      await apiFetch(`/api/users/${user.id}/deactivate_user/`, { method: 'POST' });
      toast.success(`🚫 ${user.username} deactivated`);
      loadData();
    } catch {
      toast.error('Deactivate failed');
    } finally {
      setActionLoading(p => ({ ...p, [`deactivate_${user.id}`]: false }));
    }
  };

  /* ── Filter ── */
  const filteredUsers = users.filter(u => {
    if (search && !u.username?.toLowerCase().includes(search.toLowerCase()) &&
      !u.first_name?.toLowerCase().includes(search.toLowerCase()) &&
      !u.email?.toLowerCase().includes(search.toLowerCase())) return false;
    if (verFilter !== 'verification') {
      if (verFilter === 'Verified' && !u.is_verified) return false;
      if (verFilter === 'Unverified' && u.is_verified) return false;
    }
    if (countryFilter !== 'country' && u.country && u.country !== countryFilter) return false;
    return true;
  });

  const getRiskScore = (userId) => riskProfiles[userId]?.risk_score ?? Math.floor(Math.random() * 60 + 20);
  const getRiskClass = (score) => score >= 70 ? 'risk-high' : score >= 40 ? 'risk-medium' : 'risk-low';

  const statsMiniData = {
    cyan: [20, 35, 28, 50, 42, 38, 55, 48, 60, 52, 70, 65],
    green: [10, 18, 14, 22, 19, 28, 24, 30, 26, 35, 32, 40],
    red: [50, 45, 55, 48, 58, 52, 60, 55, 65, 58, 70, 62],
    gold: [30, 42, 38, 50, 44, 58, 52, 64, 60, 70, 65, 75],
  };

  return (
    <div className="users-page">

      {/* ── CRUD Operation Cards Header ── */}
      <div className="crud-cards-row">
        <div className="crud-op-card create-card" onClick={() => setShowCreate(true)}>
          <div className="crud-card-glow create-glow" />
          <div className="crud-card-icon"><UserPlus size={20} /></div>
          <div className="crud-card-label">CREATE</div>
          <div className="crud-card-sub">Add new user</div>
        </div>
        <div className="crud-op-card read-card">
          <div className="crud-card-glow read-glow" />
          <div className="crud-card-icon"><Eye size={20} /></div>
          <div className="crud-card-label">READ</div>
          <div className="crud-card-sub">{stats.total} total users</div>
        </div>
        <div className="crud-op-card update-card">
          <div className="crud-card-glow update-glow" />
          <div className="crud-card-icon"><Edit3 size={20} /></div>
          <div className="crud-card-label">UPDATE</div>
          <div className="crud-card-sub">Edit profiles</div>
        </div>
        <div className="crud-op-card delete-card">
          <div className="crud-card-glow delete-glow" />
          <div className="crud-card-icon"><Trash2 size={20} /></div>
          <div className="crud-card-label">DELETE</div>
          <div className="crud-card-sub">Remove users</div>
        </div>
        <div className="crud-op-card verify-card" >
          <div className="crud-card-glow verify-glow" />
          <div className="crud-card-icon"><CheckSquare size={20} /></div>
          <div className="crud-card-label">VERIFY</div>
          <div className="crud-card-sub">{stats.verified} verified</div>
        </div>
        <div className="crud-op-card ban-card">
          <div className="crud-card-glow ban-glow" />
          <div className="crud-card-icon"><Ban size={20} /></div>
          <div className="crud-card-label">DEACTIVATE</div>
          <div className="crud-card-sub">{stats.banned} banned</div>
        </div>
      </div>

      {/* ── Stats Row ── */}
      <div className="users-stats-row">
        <div className="stat-card cyan">
          <div className="stat-glow" />
          <div className="stat-header">
            <span className="stat-title">Total Users</span>
            <Users className="stat-icon" style={{ width: 16, height: 16 }} />
          </div>
          <div className="stat-value">{loading ? '...' : stats.total.toLocaleString()}</div>
          <MiniChart color="#00f3ff" points={statsMiniData.cyan} />
        </div>
        <div className="stat-card green">
          <div className="stat-glow" />
          <div className="stat-header">
            <span className="stat-title">Verified Users</span>
            <UserCheck className="stat-icon" style={{ width: 16, height: 16 }} />
          </div>
          <div className="stat-value">{loading ? '...' : stats.verified.toLocaleString()}</div>
          <MiniChart color="#00ff88" points={statsMiniData.green} />
        </div>
        <div className="stat-card red">
          <div className="stat-glow" />
          <div className="stat-header">
            <span className="stat-title">Banned Users</span>
            <UserX className="stat-icon" style={{ width: 16, height: 16 }} />
          </div>
          <div className="stat-value">{loading ? '...' : stats.banned.toLocaleString()}</div>
          <MiniChart color="#ff2244" points={statsMiniData.red} />
        </div>
        <div className="stat-card gold">
          <div className="stat-glow" />
          <div className="stat-header">
            <span className="stat-title">Avg Risk Score</span>
            <ShieldAlert className="stat-icon" style={{ width: 16, height: 16 }} />
          </div>
          <div className="stat-value">{loading ? '...' : stats.avgRisk}</div>
          <div className="risk-bar-wrap">
            <div className="risk-bar-track">
              <div className="risk-bar-fill" style={{ width: `${stats.avgRisk}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <div className="users-filter-bar">
        <div className="uf-search">
          <Search style={{ width: 14, height: 14, color: 'rgba(255,255,255,0.40)', flexShrink: 0 }} />
          <input placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        {[
          { label: roleFilter, set: setRoleFilter, opts: ['role', 'Admin', 'User', 'Moderator'] },
          { label: tierFilter, set: setTierFilter, opts: ['tier', 'FREE', 'SILVER', 'GOLD', 'PLATINUM'] },
          { label: verFilter, set: setVerFilter, opts: ['verification', 'Verified', 'Unverified'] },
          { label: countryFilter, set: setCountryFilter, opts: ['country', 'BD', 'US', 'GB', 'IN', 'DE'] },
        ].map(({ label, set, opts }) => (
          <div key={label} className="uf-select" onClick={() => {
            const cur = opts.indexOf(label);
            set(opts[(cur + 1) % opts.length]);
          }}>
            {label} <ChevronDown style={{ width: 12, height: 12 }} />
          </div>
        ))}
        <button className="uf-create-btn" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> New User
        </button>
        <button className="uf-refresh-btn" onClick={loadData}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {/* ── Main 3-Column Grid ── */}
      <div className="users-main-grid">

        {/* ── Left Action Sidebar ── */}
        <div className="action-sidebar">
          <button className="act-btn create-act-btn" onClick={() => setShowCreate(true)}>
            <UserPlus style={{ width: 13, height: 13 }} /> CREATE
          </button>
          <div className="act-divider" />
          <button className="act-btn cyan-btn" onClick={() => toast('📊 Stats')}>
            <BarChart2 style={{ width: 14, height: 14 }} /> STATS
          </button>
          <div className="act-divider" />
          <button className="act-btn gold-btn" onClick={() => toast('📱 Devices')}>
            <Smartphone style={{ width: 14, height: 14 }} /> DEVICES
          </button>
          <div className="act-divider" />
          <button className="act-btn red-btn" onClick={() => toast('🔒 Security')}>
            <Shield style={{ width: 14, height: 14 }} /> SECURITY
          </button>
          <div className="act-divider" />
          <button className="act-btn purple-btn" onClick={() => toast('📜 History')}>
            <Play style={{ width: 12, height: 12 }} /> HISTORY
          </button>
          <button className="act-btn purple-btn" onClick={() => toast('⏮ Prev')}>
            <SkipBack style={{ width: 14, height: 14 }} />
          </button>
          <button className="act-btn red-btn" onClick={() => toast('🚫 Block')}>
            <Square style={{ width: 12, height: 12 }} /> BLOCK
          </button>
          <div className="act-divider" />
          <VSlider defaultVal={55} />
        </div>

        {/* ── User Cards ── */}
        <div className="user-cards-col">
          {loading ? (
            <div className="loading-state">
              <RefreshCw size={24} className="spin" style={{ color: '#00f3ff' }} />
              <span>Loading users...</span>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="empty-state">
              <Users size={32} style={{ color: '#374151' }} />
              <span>No users found</span>
            </div>
          ) : filteredUsers.map((user, idx) => {
            const riskScore = getRiskScore(user.id);
            const riskClass = getRiskClass(riskScore);
            const initials = ((user.first_name?.[0] || '') + (user.last_name?.[0] || '')) || user.username?.[0]?.toUpperCase() || '?';
            const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username;
            const isVerifyLoading = actionLoading[`verify_${user.id}`];
            const isDeactivateLoading = actionLoading[`deactivate_${user.id}`];

            return (
              <div key={user.id} className="user-card" style={{ animationDelay: `${idx * 0.04}s` }}>
                {/* Card accent line based on status */}
                <div className={`card-accent-line ${user.is_verified ? 'accent-verified' : 'accent-unverified'}`} />

                <div className="uc-top">
                  {/* Avatar */}
                  <div className="uc-avatar-wrap">
                    <div className="uc-avatar">{initials}</div>
                    <div className="uc-badge-wrap">
                      <div className={`uc-tier-badge ${user.is_verified ? 'green-badge' : 'blue'}`}>
                        {user.is_verified ? <CheckCircle style={{ width: 8, height: 8 }} /> : <Star style={{ width: 8, height: 8 }} />}
                      </div>
                    </div>
                  </div>

                  {/* Info */}
                  <div className="uc-info">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div className="uc-name">{displayName}</div>
                        <div className="uc-username">{user.email}</div>
                        {user.is_verified && (
                          <div className="uc-verified">
                            <CheckCircle style={{ width: 11, height: 11 }} /> Verified
                          </div>
                        )}
                      </div>
                      <div className="uc-country">
                        {user.country || '—'}
                        {user.tier && (
                          <span className="tier-badge">{user.tier}</span>
                        )}
                      </div>
                    </div>

                    <div className="uc-stats-row">
                      <span>Balance: <span className="val-cyan">${user.balance || 0}</span></span>
                      <span>·</span>
                      <span>Earned: <span className="val-gold">${user.total_earned || 0}</span></span>
                      <span>·</span>
                      <span>Refs: <span className="val-green">{user.referral_count || 0}</span></span>
                    </div>

                    <div className="uc-risk">
                      <div className="uc-risk-label">Risk Score: {riskScore}</div>
                      <div className="uc-risk-track">
                        <div className={`uc-risk-fill ${riskClass}`} style={{ width: `${riskScore}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* ── CRUD Action Buttons ── */}
                <div className="uc-actions">

                  {/* READ */}
                  <button className="uc-action-btn view read-btn"
                    onClick={() => setViewUser(user)}
                    title="View Details">
                    <Eye style={{ width: 11, height: 11 }} /> View
                  </button>

                  {/* UPDATE */}
                  <button className="uc-action-btn edit update-btn"
                    onClick={() => setEditUser(user)}
                    title="Edit User">
                    <Edit3 style={{ width: 11, height: 11 }} /> Edit
                  </button>

                  {/* VERIFY (custom action) */}
                  {!user.is_verified && (
                    <button className="uc-action-btn verify-btn"
                      onClick={() => handleVerify(user)}
                      disabled={isVerifyLoading}
                      title="Verify User">
                      {isVerifyLoading
                        ? <RefreshCw style={{ width: 11, height: 11 }} className="spin" />
                        : <CheckSquare style={{ width: 11, height: 11 }} />}
                      Verify
                    </button>
                  )}

                  {/* More Actions Dropdown */}
                  <Dropdown
                    label={<><MoreVertical style={{ width: 11, height: 11 }} /> More</>}
                    items={[
                      { label: 'KYC Status', icon: <Shield size={12} /> },
                      { label: 'View Devices', icon: <Smartphone size={12} /> },
                      { label: 'Login History', icon: <Activity size={12} /> },
                      { label: 'Reset Password', icon: <Key size={12} />, warning: true },
                      {
                        label: user.is_active ? 'Deactivate' : 'Activate',
                        icon: user.is_active ? <Ban size={12} /> : <Unlock size={12} />,
                        danger: true,
                        action: () => handleDeactivate(user)
                      },
                      { label: 'Delete User', icon: <Trash2 size={12} />, danger: true, action: () => setDeleteUser(user) },
                    ]}
                    btnClass="actions more-btn"
                    onSelect={item => {
                      if (item.action) item.action();
                      else if (item.label === 'Delete User') setDeleteUser(user);
                      else if (item.label === 'Deactivate' || item.label === 'Activate') handleDeactivate(user);
                      else toast(`${item.label}: ${displayName}`);
                    }}
                  />

                  {/* DELETE */}
                  <button className="uc-action-btn delete delete-btn"
                    onClick={() => setDeleteUser(user)}
                    title="Delete User">
                    <Trash2 style={{ width: 11, height: 11 }} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Right Panel ── */}
        <div className="users-right">

          {/* Fraud Logs */}
          <div className="fraud-logs-panel">
            <div className="panel-title red">
              <AlertTriangle size={12} /> Fraud Logs
            </div>
            {fraudLogs.length === 0 ? (
              <div style={{ color: '#4b5563', fontSize: 11, padding: '8px 0' }}>No fraud logs</div>
            ) : fraudLogs.map((log, i) => (
              <div key={i} className="fraud-log-item">
                <div>
                  <div className="fl-type">{log.eventType}</div>
                  <div className={`fl-event ${log.sevClass}`}>{log.event}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="fl-sev-label">{log.severity}</div>
                  <div className={`fl-sev-val ${log.sevClass}`}>{log.sevVal}</div>
                </div>
              </div>
            ))}
          </div>

          {/* IP Reputation */}
          <div className="ip-rep-panel">
            <div className="panel-title green"><Shield size={12} /> IP Reputation</div>
            <div className="ip-sub">Summary</div>
            <div className="ip-link" onClick={() => toast('🌐 IP Reputations')}>
              View IP Reputations
            </div>
          </div>

          {/* Pending KYC */}
          <div className="pending-kyc-panel">
            <div className="panel-title green"><CheckCircle size={12} /> Pending KYC</div>
            {kycQueue.map((k, i) => (
              <div key={i} className="kyc-item">
                <div className="kyc-avatar">{k.name[0]}</div>
                <div className="kyc-info">
                  <div className="kyc-name">{k.name}</div>
                  <div className="kyc-status">{k.status}</div>
                </div>
                {k.btnLabel && (
                  <button className={`kyc-btn ${k.btn}`}
                    onClick={() => toast(`${k.btnLabel}: ${k.name}`)}>
                    {k.btnLabel}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Quick CRUD reference */}
          <div className="crud-ref-panel">
            <div className="panel-title cyan"><Activity size={12} /> CRUD Operations</div>
            {[
              { op: 'POST', label: 'Create User', color: '#00ff88', endpoint: '/api/users/register/' },
              { op: 'GET', label: 'List Users', color: '#00f3ff', endpoint: '/api/users/' },
              { op: 'PATCH', label: 'Update User', color: '#ffd700', endpoint: '/api/users/{id}/' },
              { op: 'DELETE', label: 'Delete User', color: '#ff2244', endpoint: '/api/users/{id}/' },
              { op: 'POST', label: 'Verify User', color: '#a78bfa', endpoint: '/api/users/{id}/verify_user/' },
              { op: 'POST', label: 'Deactivate', color: '#f97316', endpoint: '/api/users/{id}/deactivate_user/' },
            ].map(({ op, label, color, endpoint }) => (
              <div key={label} className="crud-ref-item">
                <span className="crud-method" style={{ color, borderColor: `${color}40`, background: `${color}10` }}>{op}</span>
                <div>
                  <div className="crud-ref-label">{label}</div>
                  <div className="crud-ref-endpoint">{endpoint}</div>
                </div>
              </div>
            ))}
          </div>

        </div>
      </div>

      {/* ══ MODALS ══ */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={loadData}
        />
      )}
      {editUser && (
        <EditUserModal
          user={editUser}
          onClose={() => setEditUser(null)}
          onUpdated={loadData}
        />
      )}
      {viewUser && (
        <ViewDetailModal
          user={viewUser}
          onClose={() => setViewUser(null)}
        />
      )}
      {deleteUser && (
        <DeleteModal
          user={deleteUser}
          onClose={() => setDeleteUser(null)}
          onDeleted={loadData}
        />
      )}
    </div>
  );
};

export default UsersPage;



// // src/pages/Users.jsx
// import React, { useState, useRef, useEffect } from 'react';
// import '../styles/users.css';
// import {
//   Search, ChevronDown, Users, UserCheck, UserX,
//   ShieldAlert, Star, CheckCircle,
//   Activity, SkipBack, Square, Play, BarChart2,
//   Smartphone, Shield, Eye
// } from 'lucide-react';
// import toast from 'react-hot-toast';

// const getToken = () => localStorage.getItem('adminAccessToken');
// const apiFetch = (url) =>
//   fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } }).then(r => r.json());

// /* ── Mini sparkline ── */
// const MiniChart = ({ color, points = [30,45,28,60,42,70,55,80] }) => {
//   const max = Math.max(...points), min = Math.min(...points);
//   const norm = v => 24 - ((v - min) / (max - min || 1)) * 22;
//   const d = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (points.length - 1)) * 80},${norm(v)}`).join(' ');
//   return (
//     <svg viewBox="0 0 80 26" style={{ width: '100%', height: 28, display: 'block' }}>
//       <defs>
//         <linearGradient id={`g-${color}`} x1="0" y1="0" x2="0" y2="1">
//           <stop offset="0%" stopColor={color} stopOpacity="0.35" />
//           <stop offset="100%" stopColor={color} stopOpacity="0" />
//         </linearGradient>
//       </defs>
//       <path d={`${d}V26 L0,26 Z`} fill={`url(#g-${color})`} />
//       <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round"
//         style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
//     </svg>
//   );
// };

// /* ── Dropdown ── */
// const Dropdown = ({ label, items, onSelect, btnClass = 'actions' }) => {
//   const [open, setOpen] = useState(false);
//   const ref = useRef(null);
//   useEffect(() => {
//     const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
//     document.addEventListener('mousedown', h);
//     return () => document.removeEventListener('mousedown', h);
//   }, []);
//   return (
//     <div className="dropdown-wrap" ref={ref}>
//       <button className={`uc-action-btn ${btnClass}`} onClick={() => setOpen(!open)}>
//         {label} <ChevronDown style={{ width: 11, height: 11 }} />
//       </button>
//       {open && (
//         <div className="dropdown-menu">
//           {items.map((item, i) => (
//             <div key={i} className={`dropdown-item ${item.danger ? 'danger' : ''}`}
//               onClick={() => { onSelect?.(item); setOpen(false); toast(item.label); }}>
//               {item.label}
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// };

// /* ── Vertical Slider ── */
// const VSlider = ({ defaultVal = 55 }) => {
//   const [val, setVal] = useState(defaultVal);
//   return (
//     <div className="v-slider-wrap">
//       <div className="v-slider-track" style={{ height: 70 }}
//         onClick={e => {
//           const r = e.currentTarget.getBoundingClientRect();
//           setVal(Math.round((1 - (e.clientY - r.top) / r.height) * 100));
//         }}>
//         <div className="v-slider-fill" style={{ height: `${val}%` }} />
//         <div className="v-slider-thumb" style={{ bottom: `calc(${val}% - 8px)` }} />
//       </div>
//       <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 9, fontFamily: 'Orbitron, sans-serif' }}>{val}%</span>
//     </div>
//   );
// };

// /* ══════════════════════════════════
//    MAIN COMPONENT
// ══════════════════════════════════ */
// const UsersPage = () => {
//   const [search, setSearch] = useState('');
//   const [roleFilter, setRoleFilter]     = useState('role');
//   const [tierFilter, setTierFilter]     = useState('tier');
//   const [verFilter, setVerFilter]       = useState('verification');
//   const [countryFilter, setCountryFilter] = useState('country');

//   // Real data state
//   const [users, setUsers]         = useState([]);
//   const [kycQueue, setKycQueue]   = useState([]);
//   const [fraudLogs, setFraudLogs] = useState([]);
//   const [riskProfiles, setRiskProfiles] = useState({});
//   const [stats, setStats]         = useState({ total: 0, verified: 0, banned: 0, avgRisk: 0 });
//   const [loading, setLoading]     = useState(true);

//   useEffect(() => {
//     const load = async () => {
//       try {
//         const [usersData, kycData, fraudData, riskData] = await Promise.all([
//           apiFetch('/api/users/'),
//           apiFetch('/api/kyc/').catch(() => []),
//           apiFetch('/api/fraud-detection/').catch(() => ({})),
//           apiFetch('/api/fraud_detection/risk-profiles/').catch(() => []),
//         ]);

//         // Users
//         const userList = Array.isArray(usersData) ? usersData : (usersData?.results ?? []);
//         setUsers(userList);

//         // Risk profiles map
//         const riskMap = {};
//         if (Array.isArray(riskData)) {
//           riskData.forEach(r => { riskMap[r.user] = r; });
//         }
//         setRiskProfiles(riskMap);

//         // Stats
//         const verifiedCount = userList.filter(u => u.is_verified).length;
//         const bannedCount   = userList.filter(u => u.is_banned || u.status === 'banned').length;
//         const avgRisk = Array.isArray(riskData) && riskData.length > 0
//           ? (riskData.reduce((s, r) => s + (r.risk_score || 0), 0) / riskData.length).toFixed(1)
//           : 0;
//         setStats({ total: userList.length, verified: verifiedCount, banned: bannedCount, avgRisk });

//         // KYC queue
//         const kycList = Array.isArray(kycData) ? kycData : (kycData?.results ?? []);
//         const pendingKyc = kycList
//           .filter(k => k.status === 'pending' || k.status === 'submitted')
//           .slice(0, 5)
//           .map(k => ({
//             name: k.full_name || k.user?.username || 'User',
//             status: k.status,
//             id: k.id,
//             userId: k.user,
//             btn: 'approve',
//             btnLabel: 'Approve',
//           }));
//         setKycQueue(pendingKyc.length > 0 ? pendingKyc : [
//           { name: 'No pending KYC', status: '—', btn: '', btnLabel: '' }
//         ]);

//         // Fraud logs — fraud_detection sub-endpoints
//         try {
//           const attempts = await apiFetch('/api/fraud_detection/attempts/');
//           const attemptList = Array.isArray(attempts) ? attempts : (attempts?.results ?? []);
//           setFraudLogs(attemptList.slice(0, 3).map(a => ({
//             eventType: a.fraud_type || 'Fraud Event',
//             event: a.description || 'Suspicious Activity',
//             severity: 'Severity',
//             sevVal: a.severity || 'Medium',
//             sevClass: (a.severity || '').toLowerCase() === 'high' ? 'high' : (a.severity || '').toLowerCase() === 'low' ? 'low' : 'pulsed',
//           })));
//         } catch {
//           setFraudLogs([{ eventType: 'No fraud logs', event: '—', severity: '—', sevVal: '—', sevClass: 'low' }]);
//         }

//       } catch (e) {
//         console.error('Users page error:', e);
//       } finally {
//         setLoading(false);
//       }
//     };
//     load();
//   }, []);

//   // Filter users
//   const filteredUsers = users.filter(u => {
//     if (search && !u.username?.toLowerCase().includes(search.toLowerCase()) &&
//         !u.first_name?.toLowerCase().includes(search.toLowerCase()) &&
//         !u.email?.toLowerCase().includes(search.toLowerCase())) return false;
//     if (verFilter !== 'verification') {
//       if (verFilter === 'Verified' && !u.is_verified) return false;
//       if (verFilter === 'Unverified' && u.is_verified) return false;
//     }
//     if (countryFilter !== 'country' && u.country && u.country !== countryFilter) return false;
//     return true;
//   });

//   const getRiskScore = (userId) => riskProfiles[userId]?.risk_score ?? Math.floor(Math.random() * 60 + 20);
//   const getRiskClass = (score) => score >= 70 ? 'risk-high' : score >= 40 ? 'risk-medium' : 'risk-low';

//   const statsMiniData = {
//     cyan:  [20,35,28,50,42,38,55,48,60,52,70,65],
//     green: [10,18,14,22,19,28,24,30,26,35,32,40],
//     red:   [50,45,55,48,58,52,60,55,65,58,70,62],
//     gold:  [30,42,38,50,44,58,52,64,60,70,65,75],
//   };

//   return (
//     <div className="users-page">

//       {/* ── Stats Row ── */}
//       <div className="users-stats-row">
//         <div className="stat-card cyan">
//           <div className="stat-glow" />
//           <div className="stat-header">
//             <span className="stat-title">Total Users</span>
//             <Users className="stat-icon" style={{ width: 16, height: 16 }} />
//           </div>
//           <div className="stat-value">{loading ? '...' : stats.total.toLocaleString()}</div>
//           <MiniChart color="#00f3ff" points={statsMiniData.cyan} />
//         </div>

//         <div className="stat-card green">
//           <div className="stat-glow" />
//           <div className="stat-header">
//             <span className="stat-title">Verified Users</span>
//             <UserCheck className="stat-icon" style={{ width: 16, height: 16 }} />
//           </div>
//           <div className="stat-value">{loading ? '...' : stats.verified.toLocaleString()}</div>
//           <MiniChart color="#00ff88" points={statsMiniData.green} />
//         </div>

//         <div className="stat-card red">
//           <div className="stat-glow" />
//           <div className="stat-header">
//             <span className="stat-title">Banned Users</span>
//             <UserX className="stat-icon" style={{ width: 16, height: 16 }} />
//           </div>
//           <div className="stat-value">{loading ? '...' : stats.banned.toLocaleString()}</div>
//           <MiniChart color="#ff2244" points={statsMiniData.red} />
//         </div>

//         <div className="stat-card gold">
//           <div className="stat-glow" />
//           <div className="stat-header">
//             <span className="stat-title">Avg Risk Score</span>
//             <ShieldAlert className="stat-icon" style={{ width: 16, height: 16 }} />
//           </div>
//           <div className="stat-value">{loading ? '...' : stats.avgRisk}</div>
//           <div className="risk-bar-wrap">
//             <div className="risk-bar-track">
//               <div className="risk-bar-fill" style={{ width: `${stats.avgRisk}%` }} />
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* ── Filter Bar ── */}
//       <div className="users-filter-bar">
//         <div className="uf-search">
//           <Search style={{ width: 14, height: 14, color: 'rgba(255,255,255,0.40)', flexShrink: 0 }} />
//           <input placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
//         </div>
//         {[
//           { label: roleFilter,    set: setRoleFilter,    opts: ['role','Admin','User','Moderator'] },
//           { label: tierFilter,    set: setTierFilter,    opts: ['tier','FREE','SILVER','GOLD','PLATINUM'] },
//           { label: verFilter,     set: setVerFilter,     opts: ['verification','Verified','Unverified'] },
//           { label: countryFilter, set: setCountryFilter, opts: ['country','BD','US','GB','IN','DE'] },
//         ].map(({ label, set, opts }) => (
//           <div key={label} className="uf-select" onClick={() => {
//             const cur = opts.indexOf(label);
//             set(opts[(cur + 1) % opts.length]);
//           }}>
//             {label} <ChevronDown style={{ width: 12, height: 12 }} />
//           </div>
//         ))}
//       </div>

//       {/* ── Main 3-Column Grid ── */}
//       <div className="users-main-grid">

//         {/* ── Left Action Sidebar ── */}
//         <div className="action-sidebar">
//           <button className="act-btn gold-btn" onClick={() => toast('👤 Profile')}>
//             <Users style={{ width: 13, height: 13 }} /> PROFILE
//           </button>
//           <div className="act-divider" />
//           <button className="act-btn cyan-btn" onClick={() => toast('📊 Stats')}>
//             <BarChart2 style={{ width: 14, height: 14 }} /> STATS
//           </button>
//           <div className="act-divider" />
//           <button className="act-btn gold-btn" onClick={() => toast('📱 Devices')}>
//             <Smartphone style={{ width: 14, height: 14 }} /> DEVICES
//           </button>
//           <div className="act-divider" />
//           <button className="act-btn red-btn" onClick={() => toast('🔒 Security')}>
//             <Shield style={{ width: 14, height: 14 }} /> SECURITY
//           </button>
//           <div className="act-divider" />
//           <button className="act-btn purple-btn" onClick={() => toast('📜 History')}>
//             <Play style={{ width: 12, height: 12 }} /> View History
//           </button>
//           <button className="act-btn purple-btn" onClick={() => toast('⏮ Prev')}>
//             <SkipBack style={{ width: 14, height: 14 }} />
//           </button>
//           <button className="act-btn red-btn" onClick={() => toast('🚫 Block')}>
//             <Square style={{ width: 12, height: 12 }} /> Block
//           </button>
//           <div className="act-divider" />
//           <VSlider defaultVal={55} />
//         </div>

//         {/* ── User Cards ── */}
//         <div className="user-cards-col">
//           {loading ? (
//             <div style={{ color: '#4b5563', textAlign: 'center', padding: '40px 0', fontSize: 13 }}>
//               Loading users...
//             </div>
//           ) : filteredUsers.length === 0 ? (
//             <div style={{ color: '#4b5563', textAlign: 'center', padding: '40px 0', fontSize: 13 }}>
//               No users found
//             </div>
//           ) : filteredUsers.map(user => {
//             const riskScore = getRiskScore(user.id);
//             const riskClass = getRiskClass(riskScore);
//             const initials = ((user.first_name?.[0] || '') + (user.last_name?.[0] || '')) || user.username?.[0]?.toUpperCase() || '?';
//             const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username;

//             return (
//               <div key={user.id} className="user-card">
//                 <div className="uc-top">
//                   {/* Avatar */}
//                   <div className="uc-avatar-wrap">
//                     <div className="uc-avatar">{initials}</div>
//                     <div className="uc-badge-wrap">
//                       <div className="uc-tier-badge blue"><Star style={{ width: 8, height: 8 }} /></div>
//                     </div>
//                   </div>

//                   {/* Info */}
//                   <div className="uc-info">
//                     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
//                       <div>
//                         <div className="uc-name">{displayName}</div>
//                         <div className="uc-username">{user.email}</div>
//                         {user.is_verified && (
//                           <div className="uc-verified">
//                             <CheckCircle style={{ width: 11, height: 11 }} /> Verified
//                           </div>
//                         )}
//                       </div>
//                       <div className="uc-country">
//                         {user.country || '—'}
//                         {user.tier && (
//                           <span style={{ marginLeft: 6, fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(0,243,255,0.1)', color: '#00f3ff', border: '1px solid rgba(0,243,255,0.2)' }}>
//                             {user.tier}
//                           </span>
//                         )}
//                       </div>
//                     </div>

//                     <div style={{ fontSize: 10, color: '#6b7280', marginTop: 4 }}>
//                       Balance: <span style={{ color: '#00f3ff' }}>${user.balance}</span>
//                       {' · '}
//                       Earned: <span style={{ color: '#ffd700' }}>${user.total_earned}</span>
//                       {' · '}
//                       Refs: <span style={{ color: '#00ff88' }}>{user.referral_count || 0}</span>
//                     </div>

//                     <div className="uc-risk" style={{ marginTop: 6 }}>
//                       <div className="uc-risk-label">Risk Score: {riskScore}</div>
//                       <div className="uc-risk-track">
//                         <div className={`uc-risk-fill ${riskClass}`} style={{ width: `${riskScore}%` }} />
//                       </div>
//                     </div>
//                   </div>
//                 </div>

//                 {/* Action buttons */}
//                 <div className="uc-actions">
//                   <button className="uc-action-btn view"
//                     onClick={() => toast(`👁 ${displayName}`)}>
//                     <Eye style={{ width: 11, height: 11, marginRight: 4 }} />View Detail
//                   </button>

//                   <button className="uc-action-btn kyc"
//                     onClick={() => toast(`📋 KYC: ${displayName}`)}>
//                     KYC Status
//                   </button>

//                   <Dropdown
//                     label="Actions"
//                     items={[
//                       { label: 'Edit User' },
//                       { label: 'Reset Password' },
//                       { label: 'Suspend', danger: true },
//                       { label: 'Ban User', danger: true },
//                     ]}
//                     btnClass="actions"
//                   />
//                 </div>
//               </div>
//             );
//           })}
//         </div>

//         {/* ── Right Panel ── */}
//         <div className="users-right">

//           {/* Fraud Logs */}
//           <div className="fraud-logs-panel">
//             <div className="panel-title red">Fraud Logs</div>
//             {fraudLogs.length === 0 ? (
//               <div style={{ color: '#4b5563', fontSize: 11, padding: '8px 0' }}>No fraud logs</div>
//             ) : fraudLogs.map((log, i) => (
//               <div key={i} className="fraud-log-item">
//                 <div>
//                   <div className="fl-type">{log.eventType}</div>
//                   <div className={`fl-event ${log.sevClass}`}>{log.event}</div>
//                 </div>
//                 <div style={{ textAlign: 'right' }}>
//                   <div className="fl-sev-label">{log.severity}</div>
//                   <div className={`fl-sev-val ${log.sevClass}`}>{log.sevVal}</div>
//                 </div>
//               </div>
//             ))}
//           </div>

//           {/* IP Reputation */}
//           <div className="ip-rep-panel">
//             <div className="panel-title green">IP Reputation</div>
//             <div className="ip-sub">Summary</div>
//             <div className="ip-link" onClick={() => toast('🌐 IP Reputations')}>
//               View IP Reputations
//             </div>
//           </div>

//           {/* Pending KYC */}
//           <div className="pending-kyc-panel">
//             <div className="panel-title green">Pending KYC</div>
//             {kycQueue.map((k, i) => (
//               <div key={i} className="kyc-item">
//                 <div className="kyc-avatar">{k.name[0]}</div>
//                 <div className="kyc-info">
//                   <div className="kyc-name">{k.name}</div>
//                   <div className="kyc-status">{k.status}</div>
//                 </div>
//                 {k.btnLabel && (
//                   <button className={`kyc-btn ${k.btn}`}
//                     onClick={() => toast(`${k.btnLabel}: ${k.name}`)}>
//                     {k.btnLabel}
//                   </button>
//                 )}
//               </div>
//             ))}
//           </div>

//         </div>
//       </div>
//     </div>
//   );
// };

// export default UsersPage;


