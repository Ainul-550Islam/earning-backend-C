// pages/Tasks.jsx — Ultra Professional Tasks Dashboard
// Real API connected · Full CRUD · Holographic Glowing Cards

import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../styles/tasks.css';

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────────────────
const BASE = '/api/tasks';
const REFRESH_SECONDS = 60;

// ─────────────────────────────────────────────────────────────────────────────
// AUTH
// ─────────────────────────────────────────────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// API ENDPOINTS  (real — unchanged)
// ─────────────────────────────────────────────────────────────────────────────
const API = {
  // GET /api/tasks/tasks/
  getTasks: (userLevel = 1) =>
    fetch(`${BASE}/tasks/?user_level=${userLevel}&page_size=50`, { headers: authHeaders() }),

  // GET /api/tasks/completions/?page_size=6
  getActivity: () =>
    fetch(`${BASE}/completions/?page_size=6`, { headers: authHeaders() }),

  // GET /api/tasks/statistics/
  getStatistics: () =>
    fetch(`${BASE}/statistics/`, { headers: authHeaders() }),

  // GET /api/tasks/completions/history/
  getHistory: () =>
    fetch(`${BASE}/completions/history/`, { headers: authHeaders() }),

  // GET /api/tasks/health/
  getHealth: () =>
    fetch(`${BASE}/health/`, { headers: authHeaders() }),

  // GET /api/tasks/tasks/featured/
  getFeatured: () =>
    fetch(`${BASE}/tasks/featured/`, { headers: authHeaders() }),

  // GET /api/tasks/tasks/by-system/
  getBySystem: () =>
    fetch(`${BASE}/tasks/by-system/`, { headers: authHeaders() }),

  // POST /api/tasks/completions/  body: { task: <pk> }
  startTask: (taskPk) =>
    fetch(`${BASE}/completions/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ task: taskPk }),
    }),

  // POST /api/tasks/completions/{id}/complete/
  completeTask: (completionId, proof = {}) =>
    fetch(`${BASE}/completions/${completionId}/complete/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ proof }),
    }),

  // ── ADMIN CRUD ──────────────────────────────────────────────────────────
  // POST /api/tasks/tasks/   (AdminTaskViewSet.create)
  createTask: (data) =>
    fetch(`${BASE}/tasks/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  // PATCH /api/tasks/tasks/{task_id}/  (AdminTaskViewSet.update)
  updateTask: (taskId, data) =>
    fetch(`${BASE}/tasks/${taskId}/`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  // DELETE /api/tasks/tasks/{task_id}/  (AdminTaskViewSet.destroy)
  deleteTask: (taskId) =>
    fetch(`${BASE}/tasks/${taskId}/`, {
      method: 'DELETE',
      headers: authHeaders(),
    }),

  // POST /api/tasks/tasks/bulk-operation/  (AdminTaskViewSet.bulk_operation)
  bulkOperation: (data) =>
    fetch(`${BASE}/tasks/bulk-operation/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  // POST /api/tasks/completions/{id}/verify/
  verifyCompletion: (id) =>
    fetch(`${BASE}/completions/${id}/verify/`, {
      method: 'POST',
      headers: authHeaders(),
    }),

  // GET /api/tasks/tasks/{task_id}/check-availability/
  checkAvailability: (taskId) =>
    fetch(`${BASE}/tasks/${taskId}/check-availability/`, { headers: authHeaders() }),

  // GET /api/tasks/tasks/{task_id}/statistics/
  taskStats: (taskId) =>
    fetch(`${BASE}/tasks/${taskId}/statistics/`, { headers: authHeaders() }),
};

// ─────────────────────────────────────────────────────────────────────────────
// SAFE FETCH
// ─────────────────────────────────────────────────────────────────────────────
async function safeFetch(apiFn) {
  try {
    const res = await apiFn();
    if (!res || !res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error('Network:', e.message);
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// MOCK FALLBACK
// ─────────────────────────────────────────────────────────────────────────────
const MOCK_TASKS = [
  { id: 1, task_id: 'publish_post',    name: 'Publish Sponsored Post',    category: 'marketing',   reward_amount: 50,  system_type: 'click_visit', is_active: true, is_featured: true,  total_completions: 128 },
  { id: 2, task_id: 'affiliate_surv',  name: 'Complete Affiliate Surveys', category: 'affiliate',   reward_amount: 100, system_type: 'advanced_api', is_active: true, is_featured: false, total_completions: 85  },
  { id: 3, task_id: 'signup_users',    name: 'Sign Up New Users',          category: 'refer_team',  reward_amount: 25,  system_type: 'refer_team', is_active: true, is_featured: true,  total_completions: 210 },
  { id: 4, task_id: 'install_app',     name: 'Download & Install App',     category: 'app_social',  reward_amount: 75,  system_type: 'app_social', is_active: true, is_featured: false, total_completions: 64  },
  { id: 5, task_id: 'daily_checkin',   name: 'Daily Check-in Streak',      category: 'daily_retention', reward_amount: 10, system_type: 'gamified', is_active: true, is_featured: true, total_completions: 340 },
  { id: 6, task_id: 'watch_video',     name: 'Watch Sponsored Video',      category: 'ads_multimedia', reward_amount: 30, system_type: 'ads_multimedia', is_active: false, is_featured: false, total_completions: 45 },
];

const MOCK_ACTIVITY = [
  { id: 1, user: { username: 'arun_dev' },  task: { name: 'Publish Sponsored Post' },   status: 'completed' },
  { id: 2, user: { username: 'maria_w'  },  task: { name: 'Affiliate Surveys' },         status: 'pending'   },
  { id: 3, user: { username: 'james_c'  },  task: { name: 'Sign Up New Users' },          status: 'completed' },
  { id: 4, user: { username: 'sara_k'   },  task: { name: 'Daily Check-in' },             status: 'started'   },
];

// ─────────────────────────────────────────────────────────────────────────────
// CARD COLOR CONFIG — প্রতিটা category আলাদা glowing color
// ─────────────────────────────────────────────────────────────────────────────
const CARD_COLORS = {
  marketing:        { primary: '#00f3ff', secondary: '#0066ff', glow: 'rgba(0,243,255,0.35)',  label: 'MARKETING'   },
  affiliate:        { primary: '#00ff88', secondary: '#00cc44', glow: 'rgba(0,255,136,0.35)',  label: 'AFFILIATE'   },
  refer_team:       { primary: '#ffd700', secondary: '#ff8c00', glow: 'rgba(255,215,0,0.35)',  label: 'REFER'       },
  app_social:       { primary: '#a78bfa', secondary: '#7c3aed', glow: 'rgba(167,139,250,0.35)',label: 'SOCIAL'      },
  daily_retention:  { primary: '#f472b6', secondary: '#ec4899', glow: 'rgba(244,114,182,0.35)',label: 'DAILY'       },
  ads_multimedia:   { primary: '#fb923c', secondary: '#ea580c', glow: 'rgba(251,146,60,0.35)', label: 'ADS'         },
  gamified:         { primary: '#34d399', secondary: '#059669', glow: 'rgba(52,211,153,0.35)', label: 'GAME'        },
  web_content:      { primary: '#60a5fa', secondary: '#2563eb', glow: 'rgba(96,165,250,0.35)', label: 'WEB'         },
  advanced_api:     { primary: '#f87171', secondary: '#dc2626', glow: 'rgba(248,113,113,0.35)',label: 'API'         },
  default:          { primary: '#00f3ff', secondary: '#0066ff', glow: 'rgba(0,243,255,0.35)',  label: 'TASK'        },
};
const SYSTEM_COLOR_MAP = {
  game: CARD_COLORS.gamified, gamified: CARD_COLORS.gamified,
  click_visit: CARD_COLORS.marketing, refer_team: CARD_COLORS.refer_team,
  app_social: CARD_COLORS.app_social, ads_multimedia: CARD_COLORS.ads_multimedia,
  web_content: CARD_COLORS.web_content, advanced_api: CARD_COLORS.advanced_api,
  daily_retention: CARD_COLORS.daily_retention,
};
const cardColor = (cat = '', sys = '') => {
  if (cat) return CARD_COLORS[cat.toLowerCase()] || CARD_COLORS.default;
  if (sys) return SYSTEM_COLOR_MAP[sys.toLowerCase()] || CARD_COLORS.default;
  return CARD_COLORS.default;
};

const STATUS_COLORS = {
  completed:  { color: '#00ff88', bg: 'rgba(0,255,136,0.12)',  border: 'rgba(0,255,136,0.3)'  },
  pending:    { color: '#ffd700', bg: 'rgba(255,215,0,0.12)',  border: 'rgba(255,215,0,0.3)'  },
  started:    { color: '#00f3ff', bg: 'rgba(0,243,255,0.12)',  border: 'rgba(0,243,255,0.3)'  },
  verified:   { color: '#a78bfa', bg: 'rgba(167,139,250,0.12)',border: 'rgba(167,139,250,0.3)'},
  failed:     { color: '#ff2244', bg: 'rgba(255,34,68,0.12)',  border: 'rgba(255,34,68,0.3)'  },
};
const statusStyle = (s) => STATUS_COLORS[s] || STATUS_COLORS.pending;

const getReward = t => t.reward_amount || t.rewards?.points || 0;

// ─────────────────────────────────────────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────────────────────────────────────────
function Toast({ toasts, remove }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast-item toast-${t.type}`} onClick={() => remove(t.id)}>
          <span className="toast-icon">
            {t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️'}
          </span>
          {t.msg}
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const add = useCallback((msg, type = 'success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, msg, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500);
  }, []);
  const remove = useCallback(id => setToasts(p => p.filter(t => t.id !== id)), []);
  return { toasts, add, remove };
}

// ─────────────────────────────────────────────────────────────────────────────
// CREATE / EDIT MODAL
// ─────────────────────────────────────────────────────────────────────────────
const CATEGORIES = ['marketing','affiliate','refer_team','app_social','daily_retention','ads_multimedia','gamified','web_content','advanced_api'];
const SYSTEM_TYPES = ['click_visit','gamified','refer_team','app_social','ads_multimedia','web_content','advanced_api','daily_retention'];

function TaskModal({ task, onClose, onSaved, toast }) {
  const isEdit = !!task;
  const [form, setForm] = useState({
    name: task?.name || '',
    description: task?.description || '',
    category: task?.category || 'marketing',
    system_type: task?.system_type || 'click_visit',
    reward_amount: task?.reward_amount || '',
    is_active: task?.is_active ?? true,
    is_featured: task?.is_featured ?? false,
    min_user_level: task?.min_user_level || 1,
  });
  const [loading, setLoading] = useState(false);
  const cc = cardColor(form.category);

  const handleSave = async () => {
    if (!form.name) { toast('Task name required', 'error'); return; }
    setLoading(true);
    try {
      const res = isEdit
        ? await safeFetch(() => API.updateTask(task.task_id, form))
        : await safeFetch(() => API.createTask(form));

      if (res?.data || res?.status === 'success' || res?.id || res?.task_id) {
        toast(isEdit ? '✅ Task updated!' : '✅ Task created!', 'success');
        onSaved?.();
        onClose();
      } else {
        toast(res?.error || 'Save failed', 'error');
      }
    } catch { toast('Network error', 'error'); }
    finally { setLoading(false); }
  };

  return (
    <div className="tm-overlay" onClick={onClose}>
      <div className="tm-box" style={{ '--card-primary': cc.primary, '--card-glow': cc.glow }} onClick={e => e.stopPropagation()}>
        <div className="tm-header">
          <div className="tm-header-accent" style={{ background: `linear-gradient(90deg, ${cc.primary}, transparent)` }} />
          <div className="tm-title-row">
            <div className="tm-icon" style={{ color: cc.primary, borderColor: `${cc.primary}40`, background: `${cc.primary}12` }}>
              {isEdit ? '✏️' : '➕'}
            </div>
            <div>
              <div className="tm-title">{isEdit ? 'Edit Task' : 'Create New Task'}</div>
              <div className="tm-sub">{isEdit ? `task_id: ${task.task_id}` : 'AdminTaskViewSet.create()'}</div>
            </div>
          </div>
          <button className="tm-close" onClick={onClose}>✕</button>
        </div>

        <div className="tm-body">
          <div className="tm-grid">
            <div className="tm-field full">
              <label>Task Name *</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Enter task name..." />
            </div>
            <div className="tm-field full">
              <label>Description</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Task description..." rows={2} />
            </div>
            <div className="tm-field">
              <label>Category</label>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ').toUpperCase()}</option>)}
              </select>
            </div>
            <div className="tm-field">
              <label>System Type</label>
              <select value={form.system_type} onChange={e => setForm({ ...form, system_type: e.target.value })}>
                {SYSTEM_TYPES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ').toUpperCase()}</option>)}
              </select>
            </div>
            <div className="tm-field">
              <label>Reward Amount ($)</label>
              <input type="number" value={form.reward_amount} onChange={e => setForm({ ...form, reward_amount: e.target.value })} placeholder="0.00" />
            </div>
            <div className="tm-field">
              <label>Min User Level</label>
              <input type="number" value={form.min_user_level} onChange={e => setForm({ ...form, min_user_level: e.target.value })} min={1} />
            </div>
            <div className="tm-toggles">
              <label className="tm-toggle">
                <input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />
                <span className="toggle-track" style={{ '--tc': '#00ff88' }} />
                <span>Active</span>
              </label>
              <label className="tm-toggle">
                <input type="checkbox" checked={form.is_featured} onChange={e => setForm({ ...form, is_featured: e.target.checked })} />
                <span className="toggle-track" style={{ '--tc': '#ffd700' }} />
                <span>Featured</span>
              </label>
            </div>
          </div>
        </div>

        <div className="tm-footer">
          <button className="tm-btn tm-cancel" onClick={onClose}>Cancel</button>
          <button className="tm-btn tm-save" style={{ '--sc': cc.primary, '--sg': cc.glow }} onClick={handleSave} disabled={loading}>
            {loading ? <span className="spin-sm">↻</span> : (isEdit ? '💾 Save Changes' : '✨ Create Task')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE MODAL
// ─────────────────────────────────────────────────────────────────────────────
function DeleteModal({ task, onClose, onDeleted, toast }) {
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    if (confirm !== task.task_id) { toast('Type task_id to confirm', 'error'); return; }
    setLoading(true);
    try {
      await fetch(`${BASE}/tasks/${task.task_id}/`, { method: 'DELETE', headers: authHeaders() });
      toast('🗑️ Task deleted!', 'success');
      onDeleted?.();
      onClose();
    } catch { toast('Delete failed', 'error'); }
    finally { setLoading(false); }
  };

  return (
    <div className="tm-overlay" onClick={onClose}>
      <div className="tm-box delete-box" onClick={e => e.stopPropagation()}>
        <div className="tm-header">
          <div className="tm-header-accent" style={{ background: 'linear-gradient(90deg, #ff2244, transparent)' }} />
          <div className="tm-title-row">
            <div className="tm-icon" style={{ color: '#ff2244', borderColor: 'rgba(255,34,68,0.3)', background: 'rgba(255,34,68,0.1)' }}>🗑️</div>
            <div>
              <div className="tm-title">Delete Task</div>
              <div className="tm-sub">This action is permanent</div>
            </div>
          </div>
          <button className="tm-close" onClick={onClose}>✕</button>
        </div>
        <div className="tm-body">
          <div className="delete-warn">
            ⚠️ Delete <strong style={{ color: '#ff2244' }}>{task.name}</strong>?<br />
            <span>All completions data will be permanently lost.</span>
          </div>
          <div className="tm-field" style={{ marginTop: 16 }}>
            <label>Type <strong style={{ color: '#ff2244' }}>{task.task_id}</strong> to confirm</label>
            <input value={confirm} onChange={e => setConfirm(e.target.value)} placeholder={task.task_id} className="danger-input" />
          </div>
        </div>
        <div className="tm-footer">
          <button className="tm-btn tm-cancel" onClick={onClose}>Cancel</button>
          <button className="tm-btn tm-delete" onClick={handleDelete} disabled={loading || confirm !== task.task_id}>
            {loading ? <span className="spin-sm">↻</span> : '🗑️ Delete Task'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STATS MODAL
// ─────────────────────────────────────────────────────────────────────────────
function StatsModal({ task, onClose }) {
  const [stats, setStats] = useState(null);
  const cc = cardColor(task.category, task.system_type);

  useEffect(() => {
    safeFetch(() => API.taskStats(task.task_id)).then(r => {
      if (r?.data) setStats(r.data);
    });
  }, [task.task_id]);

  return (
    <div className="tm-overlay" onClick={onClose}>
      <div className="tm-box" style={{ '--card-primary': cc.primary, '--card-glow': cc.glow }} onClick={e => e.stopPropagation()}>
        <div className="tm-header">
          <div className="tm-header-accent" style={{ background: `linear-gradient(90deg, ${cc.primary}, transparent)` }} />
          <div className="tm-title-row">
            <div className="tm-icon" style={{ color: cc.primary, borderColor: `${cc.primary}40`, background: `${cc.primary}12` }}>📊</div>
            <div>
              <div className="tm-title">Task Statistics</div>
              <div className="tm-sub">{task.name}</div>
            </div>
          </div>
          <button className="tm-close" onClick={onClose}>✕</button>
        </div>
        <div className="tm-body">
          {!stats ? (
            <div className="stats-loading">Loading statistics...</div>
          ) : (
            <div className="stats-grid">
              {[
                { label: 'Total Completions', val: stats.total_completions ?? task.total_completions ?? 0, color: cc.primary },
                { label: 'Unique Users',       val: stats.unique_users ?? 0,        color: '#00ff88' },
                { label: 'Completion Rate',    val: `${stats.completion_rate ?? 0}%`, color: '#ffd700' },
                { label: 'Daily Average',      val: stats.daily_average ?? 0,       color: '#a78bfa' },
                { label: 'Users (30d)',         val: stats.unique_users_30d ?? 0,    color: '#f472b6' },
                { label: 'Avg Time (min)',      val: stats.avg_completion_time ?? '—', color: '#fb923c' },
              ].map(({ label, val, color }) => (
                <div key={label} className="stat-box" style={{ '--sb-color': color }}>
                  <div className="sb-val" style={{ color }}>{val}</div>
                  <div className="sb-label">{label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="tm-footer">
          <button className="tm-btn tm-cancel" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GLOWING TASK CARD
// ─────────────────────────────────────────────────────────────────────────────
function TaskCard({ task, idx, taskState, onComplete, onEdit, onDelete, onStats }) {
  const cc = cardColor(task.category, task.system_type);
  const reward = getReward(task);
  const ph = taskState[task.id]?.phase || 'idle';
  const isDone = ph === 'done';
  const isBusy = ph === 'starting' || ph === 'completing';

  const btnLabel = () => {
    if (ph === 'starting')   return '⟳ Starting...';
    if (ph === 'completing') return '⟳ Completing...';
    if (ph === 'done')       return '✓ Done';
    return 'Complete Task';
  };

  return (
    <div
      className={`task-card ${isDone ? 'task-card-done' : ''} ${!task.is_active ? 'task-card-inactive' : ''}`}
      style={{
        '--cp': cc.primary,
        '--cs': cc.secondary,
        '--cg': cc.glow,
        animationDelay: `${idx * 0.06}s`,
      }}
    >
      {/* Glow layer */}
      <div className="tc-glow-layer" />

      {/* Top accent */}
      <div className="tc-accent-bar" style={{ background: `linear-gradient(90deg, ${cc.primary}, ${cc.secondary}, transparent)` }} />

      {/* Category badge */}
      <div className="tc-cat-badge" style={{ color: cc.primary, borderColor: `${cc.primary}35`, background: `${cc.primary}10` }}>
        <span className="tc-cat-dot" style={{ background: cc.primary, boxShadow: `0 0 6px ${cc.primary}` }} />
        {task.category ? cc.label : (task.system_type || 'TASK').toUpperCase()}
      </div>

      {/* Status badge */}
      {!task.is_active && <div className="tc-inactive-badge">INACTIVE</div>}
      {task.is_featured && <div className="tc-featured-badge" style={{ color: '#ffd700' }}>⭐ Featured</div>}

      {/* Reward orb */}
      <div className="tc-reward-orb" style={{ '--rp': cc.primary, '--rg': cc.glow }}>
        <div className="tc-reward-val" style={{ color: cc.primary }}>${reward}</div>
        <div className="tc-reward-lbl">REWARD</div>
      </div>

      {/* Task name */}
      <div className="tc-name" style={{ color: 'rgba(255,255,255,0.92)' }}>{task.name}</div>

      {/* Meta */}
      <div className="tc-meta">
        <span className="tc-meta-item">
          <span style={{ color: cc.primary }}>⚡</span> {task.system_type?.replace(/_/g, ' ') || 'task'}
        </span>
        <span className="tc-meta-item">
          <span style={{ color: '#ffd700' }}>✓</span> {task.total_completions || 0}
        </span>
        <span className="tc-meta-item">
          <span style={{ color: '#00ff88' }}>Lv.</span> {task.min_user_level || 1}+
        </span>
      </div>

      {/* Progress bar (fake visual) */}
      <div className="tc-progress-wrap">
        <div className="tc-progress-track">
          <div
            className="tc-progress-fill"
            style={{
              width: isDone ? '100%' : `${Math.min(100, (task.total_completions || 0) % 100)}%`,
              background: `linear-gradient(90deg, ${cc.primary}, ${cc.secondary})`,
              boxShadow: `0 0 8px ${cc.glow}`,
            }}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="tc-actions">
        <button
          className="tc-complete-btn"
          style={{ '--cp': cc.primary, '--cg': cc.glow, '--cs': cc.secondary }}
          onClick={() => onComplete(task)}
          disabled={isBusy || isDone || !task.is_active}
        >
          {btnLabel()}
        </button>

        <div className="tc-icon-btns">
          <button className="tc-icon-btn edit-btn" onClick={() => onEdit(task)} title="Edit Task">✏️</button>
          <button className="tc-icon-btn stats-btn" onClick={() => onStats(task)} title="Statistics">📊</button>
          <button className="tc-icon-btn delete-btn" onClick={() => onDelete(task)} title="Delete Task">🗑️</button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
export default function TasksDashboard() {
  const [tasks,      setTasks]      = useState(MOCK_TASKS);
  const [activity,   setActivity]   = useState(MOCK_ACTIVITY);
  const [globalStats,setGlobalStats]= useState(null);
  const [histStats,  setHistStats]  = useState(null);
  const [health,     setHealth]     = useState(null);
  const [timer,      setTimer]      = useState(REFRESH_SECONDS);
  const [lastUp,     setLastUp]     = useState('just now');
  const [loading,    setLoading]    = useState(false);
  const [search,     setSearch]     = useState('');
  const [catFilter,  setCatFilter]  = useState('all');
  const [taskState,  setTaskState]  = useState({});

  // CRUD modals
  const [showCreate, setShowCreate] = useState(false);
  const [editTask,   setEditTask]   = useState(null);
  const [deleteTask, setDeleteTask] = useState(null);
  const [statsTask,  setStatsTask]  = useState(null);

  const timerRef  = useRef(null);
  const userLevel = parseInt(localStorage.getItem('user_level') || '1', 10);
  const { toasts, add: toast, remove: removeToast } = useToast();

  // ── FETCH ALL ──────────────────────────────────────────────────────────────
  const fetchAll = useCallback(async (showLoader = false) => {
    if (showLoader) setLoading(true);
    try {
      const [tasksRes, actRes, statsRes, histRes, healthRes] = await Promise.all([
        safeFetch(() => API.getTasks(userLevel)),
        safeFetch(() => API.getActivity()),
        safeFetch(() => API.getStatistics()),
        safeFetch(() => API.getHistory()),
        safeFetch(() => API.getHealth()),
      ]);

      // API: { status:'success', data:[...], pagination:{...} }
      const taskList = Array.isArray(tasksRes?.data) ? tasksRes.data
                     : Array.isArray(tasksRes?.results) ? tasksRes.results
                     : null;
      if (taskList) setTasks(taskList);

      const actList = Array.isArray(actRes?.data) ? actRes.data
                    : Array.isArray(actRes?.results) ? actRes.results
                    : null;
      if (actList) setActivity(actList);

      if (statsRes?.data)  setGlobalStats(statsRes.data);
      if (histRes?.stats)  setHistStats(histRes.stats);
      if (healthRes)       setHealth(healthRes);

      const now = new Date();
      setLastUp(`${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`);
      setTimer(REFRESH_SECONDS);
    } finally {
      if (showLoader) setLoading(false);
    }
  }, [userLevel]);

  useEffect(() => {
    fetchAll(true);
    timerRef.current = setInterval(() => {
      setTimer(p => { if (p <= 1) { fetchAll(); return REFRESH_SECONDS; } return p - 1; });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [fetchAll]);

  // ── COMPLETE TASK ─────────────────────────────────────────────────────────
  const handleComplete = async (task) => {
    const tid = task.id;
    const ph  = taskState[tid]?.phase || 'idle';
    if (ph === 'starting' || ph === 'completing') return;

    setTaskState(p => ({ ...p, [tid]: { phase: 'starting' } }));
    const startRes = await safeFetch(() => API.startTask(task.id));

    if (!startRes || !startRes.data?.id) {
      setTaskState(p => ({ ...p, [tid]: { phase: 'idle' } }));
      toast(startRes?.error || 'Task not available', 'error');
      return;
    }

    const completionId = startRes.data.id;
    setTaskState(p => ({ ...p, [tid]: { phase: 'completing', completionId } }));

    const completeRes = await safeFetch(() => API.completeTask(completionId));

    if (completeRes?.status === 'completed' || completeRes?.status === 'already_completed') {
      const pts = completeRes.rewards?.points || 0;
      toast(pts > 0 ? `✅ +${pts} points earned!` : '✅ Task completed!', 'success');
      setTaskState(p => ({ ...p, [tid]: { phase: 'done', completionId } }));
      setTimeout(() => fetchAll(), 800);
    } else {
      toast(completeRes?.error || 'Failed to complete task', 'error');
      setTaskState(p => ({ ...p, [tid]: { phase: 'idle' } }));
    }
  };

  // ── FILTER ────────────────────────────────────────────────────────────────
  const filtered = tasks.filter(t => {
    const matchSearch = !search ||
      (t.name || '').toLowerCase().includes(search.toLowerCase()) ||
      (t.category || '').toLowerCase().includes(search.toLowerCase()) ||
      (t.task_id || '').toLowerCase().includes(search.toLowerCase());
    const matchCat = catFilter === 'all' || t.category === catFilter || t.system_type === catFilter;
    return matchSearch && matchCat;
  });

  const uniqueCats = ['all', ...new Set(tasks.map(t => t.category || t.system_type).filter(Boolean))];
  const timerFmt   = `00:${String(timer).padStart(2, '0')}`;

  const dbStatus = health?.services?.database?.healthy;

  // ── STATS SUMMARY ─────────────────────────────────────────────────────────
  const summaryStats = [
    { label: 'Total Tasks',      val: globalStats?.total_tasks      ?? tasks.length,                                        color: '#00f3ff' },
    { label: 'Active Tasks',     val: globalStats?.active_tasks      ?? tasks.filter(t => t.is_active).length,               color: '#00ff88' },
    { label: 'Completions Today',val: globalStats?.completions_today ?? 0,                                                   color: '#ffd700' },
    { label: 'Featured Tasks',   val: globalStats?.featured_tasks    ?? tasks.filter(t => t.is_featured).length,             color: '#a78bfa' },
    { label: 'Total Earned (pts)',val: histStats?.total_points        ?? 0,                                                  color: '#f472b6' },
    { label: 'My Streak',        val: histStats?.streak_days          != null ? `${histStats.streak_days}d` : '—',           color: '#fb923c' },
  ];

  return (
    <div className="tasks-page">
      <Toast toasts={toasts} remove={removeToast} />

      {/* ── HEADER ── */}
      <div className="tasks-header">
        <div className="th-left">
          <div className="th-logo">
            <svg viewBox="0 0 24 24" width="22" height="22">
              <polygon points="12,2 15.5,8.5 22,9.5 17,14.5 18,22 12,18.5 6,22 7,14.5 2,9.5 8.5,8.5" fill="#00f3ff" opacity="0.9"/>
            </svg>
          </div>
          <div>
            <div className="th-title">TASKS DASHBOARD</div>
            <div className="th-sub">
              {loading ? 'Loading...' : <>Refresh in <span className="th-timer">{timerFmt}</span> · Last: <span className="th-last">{lastUp}</span></>}
              {dbStatus !== undefined && (
                <span className={`th-health ${dbStatus ? 'health-ok' : 'health-bad'}`}>
                  {dbStatus ? '● DB OK' : '● DB ERR'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="th-right">
          <div className="th-search">
            <span>🔍</span>
            <input placeholder="Search tasks..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <button className="th-create-btn" onClick={() => setShowCreate(true)}>
            <span>✨</span> New Task
          </button>
          <button className="th-refresh-btn" onClick={() => fetchAll(true)}>
            <span className={loading ? 'spin-sm' : ''}>↻</span>
          </button>
        </div>
      </div>

      {/* ── CRUD OPS ROW ── */}
      <div className="crud-ops-row">
        {[
          { op: 'CREATE', icon: '✨', color: '#00ff88', glow: 'rgba(0,255,136,0.3)',  desc: 'New task',         action: () => setShowCreate(true) },
          { op: 'READ',   icon: '👁️', color: '#00f3ff', glow: 'rgba(0,243,255,0.3)',  desc: `${tasks.length} tasks` },
          { op: 'UPDATE', icon: '✏️', color: '#ffd700', glow: 'rgba(255,215,0,0.3)',  desc: 'Edit any task' },
          { op: 'DELETE', icon: '🗑️', color: '#ff2244', glow: 'rgba(255,34,68,0.3)',  desc: 'Remove task' },
          { op: 'COMPLETE',icon:'⚡', color: '#a78bfa', glow: 'rgba(167,139,250,0.3)',desc: 'Run task' },
          { op: 'STATS',  icon: '📊', color: '#f472b6', glow: 'rgba(244,114,182,0.3)',desc: 'Analytics' },
        ].map(({ op, icon, color, glow, desc, action }) => (
          <div key={op} className="crud-op-tile" style={{ '--col': color, '--glow': glow }} onClick={action}>
            <div className="cot-glow" />
            <div className="cot-icon">{icon}</div>
            <div className="cot-op" style={{ color }}>{op}</div>
            <div className="cot-desc">{desc}</div>
          </div>
        ))}
      </div>

      {/* ── STATS SUMMARY ROW ── */}
      <div className="summary-stats-row">
        {summaryStats.map(({ label, val, color }) => (
          <div key={label} className="ss-card" style={{ '--sc': color }}>
            <div className="ss-glow" style={{ background: color }} />
            <div className="ss-val" style={{ color }}>{loading ? '...' : val}</div>
            <div className="ss-label">{label}</div>
          </div>
        ))}
      </div>

      {/* ── CATEGORY FILTER ── */}
      <div className="cat-filter-row">
        {uniqueCats.map(cat => {
          const cc = cat === 'all' ? { primary: '#ffffff' } : cardColor(cat);
          return (
            <button
              key={cat}
              className={`cat-filter-btn ${catFilter === cat ? 'active' : ''}`}
              style={{ '--fc': cc.primary }}
              onClick={() => setCatFilter(cat)}
            >
              {cat === 'all' ? 'All Tasks' : cat.replace(/_/g, ' ').toUpperCase()}
            </button>
          );
        })}
      </div>

      {/* ── MAIN GRID ── */}
      <div className="tasks-main-grid">

        {/* TASK CARDS */}
        <div className="task-cards-area">
          {loading && tasks.length === 0 ? (
            <div className="tasks-empty">
              <span className="spin-lg">↻</span>
              <span>Loading tasks...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="tasks-empty">
              <span style={{ fontSize: 32 }}>🔍</span>
              <span>No tasks found{search && ` for "${search}"`}</span>
            </div>
          ) : (
            <div className="task-cards-grid">
              {filtered.map((task, idx) => (
                <TaskCard
                  key={task.id || task.task_id}
                  task={task}
                  idx={idx}
                  taskState={taskState}
                  onComplete={handleComplete}
                  onEdit={setEditTask}
                  onDelete={setDeleteTask}
                  onStats={setStatsTask}
                />
              ))}
            </div>
          )}
        </div>

        {/* RIGHT PANEL */}
        <div className="tasks-right-panel">

          {/* Recent Activity */}
          <div className="rp-card activity-rp">
            <div className="rp-title" style={{ color: '#00f3ff' }}>⚡ Recent Activity</div>
            {activity.slice(0, 6).map((item, i) => {
              const uname = item.user?.username || 'User';
              const tname = item.task?.name || item.task?.task_id || 'Task';
              const st    = item.status || 'pending';
              const sc    = statusStyle(st);
              return (
                <div key={item.id || i} className="act-item">
                  <div className="act-avatar" style={{ background: `${sc.color}18`, border: `1px solid ${sc.color}30`, color: sc.color }}>
                    {uname[0]?.toUpperCase()}
                  </div>
                  <div className="act-info">
                    <div className="act-user">{uname}</div>
                    <div className="act-task">{tname}</div>
                  </div>
                  <div className="act-status" style={{ color: sc.color, background: sc.bg, border: `1px solid ${sc.border}` }}>
                    {st}
                  </div>
                </div>
              );
            })}
          </div>

          {/* API Endpoints Reference */}
          <div className="rp-card endpoints-rp">
            <div className="rp-title" style={{ color: '#00ff88' }}>🔌 API Endpoints</div>
            {[
              { method: 'GET',    color: '#00f3ff', ep: '/api/tasks/tasks/',              label: 'List Tasks'       },
              { method: 'POST',   color: '#00ff88', ep: '/api/tasks/tasks/ (create)',     label: 'Create Task'      },
              { method: 'PATCH',  color: '#ffd700', ep: '/api/tasks/tasks/{id}/',         label: 'Update Task'      },
              { method: 'DELETE', color: '#ff2244', ep: '/api/tasks/tasks/{id}/ (del)',   label: 'Delete Task'      },
              { method: 'POST',   color: '#a78bfa', ep: '/api/tasks/completions/',        label: 'Start Task'       },
              { method: 'POST',   color: '#f472b6', ep: '/completions/{id}/complete/',    label: 'Complete Task'    },
            ].map(({ method, color, ep, label }) => (
              <div key={label} className="ep-item">
                <span className="ep-method" style={{ color, background: `${color}12`, border: `1px solid ${color}25` }}>{method}</span>
                <span className="ep-path">{ep}</span>
              </div>
            ))}
          </div>

          {/* Health Status */}
          {health && (
            <div className="rp-card health-rp">
              <div className="rp-title" style={{ color: '#34d399' }}>🩺 System Health</div>
              {Object.entries(health.services || {}).map(([svc, info]) => (
                <div key={svc} className="health-item">
                  <span className={`health-dot ${info.healthy ? 'healthy' : 'unhealthy'}`} />
                  <span className="health-svc">{svc}</span>
                  <span className="health-msg">{info.message}</span>
                </div>
              ))}
              {health.stats && (
                <div className="health-stats">
                  <span>Tasks: <strong style={{ color: '#00f3ff' }}>{health.stats.tasks_count}</strong></span>
                  <span>Today: <strong style={{ color: '#00ff88' }}>{health.stats.completions_today}</strong></span>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {/* ── MODALS ── */}
      {showCreate && <TaskModal onClose={() => setShowCreate(false)} onSaved={fetchAll} toast={toast} />}
      {editTask   && <TaskModal task={editTask} onClose={() => setEditTask(null)} onSaved={fetchAll} toast={toast} />}
      {deleteTask && <DeleteModal task={deleteTask} onClose={() => setDeleteTask(null)} onDeleted={fetchAll} toast={toast} />}
      {statsTask  && <StatsModal task={statsTask} onClose={() => setStatsTask(null)} />}
    </div>
  );
}



// // pages/tasks.jsx
// // Tasks Dashboard — Space Dark Theme
// // 100% connected to your Django DRF backend (views.py + urls.py)

// import React, { useState, useEffect, useCallback, useRef } from 'react';
// import '../styles/tasks.css';

// // ─────────────────────────────────────────────────────────────────────────────
// // CONFIG — .env এ রাখুন:  REACT_APP_API_URL=http://localhost:8000/api/tasks
// // ─────────────────────────────────────────────────────────────────────────────
// // const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/tasks';
// const BASE = '/api/tasks';
// const REFRESH_SECONDS = 60;

// // ─────────────────────────────────────────────────────────────────────────────
// // AUTH HELPER
// // ─────────────────────────────────────────────────────────────────────────────
// function authHeaders() {
//   const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
//   return {
//     'Content-Type': 'application/json',
//     ...(token ? { Authorization: `Bearer ${token}` } : {}),
//   };
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // EXACT ENDPOINTS — আপনার urls.py থেকে:
// //
// //   router.register(r'tasks',       MasterTaskViewSet,      basename='task')
// //   router.register(r'completions', TaskCompletionViewSet,  basename='completion')
// //   path('statistics/',   TaskStatisticsView.as_view())
// //   path('health/',       HealthCheckView.as_view())
// //
// //   Main urls.py → path('api/tasks/', include('api.tasks.urls'))
// //
// //   Final URL map:
// //   GET  /api/tasks/tasks/                              → task list
// //   GET  /api/tasks/tasks/featured/                     → featured tasks
// //   GET  /api/tasks/tasks/by-system/                    → tasks grouped
// //   GET  /api/tasks/tasks/{task_id}/check-availability/ → availability
// //   GET  /api/tasks/tasks/{task_id}/statistics/         → task stats
// //   GET  /api/tasks/completions/                        → my completions
// //   POST /api/tasks/completions/                        → start task
// //   POST /api/tasks/completions/{id}/complete/          → complete task
// //   GET  /api/tasks/completions/history/                → user history
// //   GET  /api/tasks/statistics/                         → global stats
// //   GET  /api/tasks/health/                             → health
// // ─────────────────────────────────────────────────────────────────────────────

// const API = {
//   // MasterTaskViewSet.list() — GET /api/tasks/tasks/
//   getTasks: (userLevel = 1) =>
//     fetch(`${BASE}/tasks/?user_level=${userLevel}&available_only=true`, {
//       headers: authHeaders(),
//     }),

//   // TaskCompletionViewSet.list() — GET /api/tasks/completions/?page_size=4
//   getActivity: () =>
//     fetch(`${BASE}/completions/?page_size=4`, { headers: authHeaders() }),

//   // TaskStatisticsView.get() — GET /api/tasks/statistics/
//   getStatistics: () =>
//     fetch(`${BASE}/statistics/`, { headers: authHeaders() }),

//   // TaskCompletionViewSet.user_history() — GET /api/tasks/completions/history/
//   getHistory: () =>
//     fetch(`${BASE}/completions/history/`, { headers: authHeaders() }),

//   // TaskCompletionViewSet.create() — POST /api/tasks/completions/
//   // body: { task: <task primary key (integer)> }
//   startTask: (taskPk) =>
//     fetch(`${BASE}/completions/`, {
//       method: 'POST',
//       headers: authHeaders(),
//       body: JSON.stringify({ task: taskPk }),
//     }),

//   // TaskCompletionViewSet.mark_complete() — POST /api/tasks/completions/{id}/complete/
//   completeTask: (completionId, proof = {}) =>
//     fetch(`${BASE}/completions/${completionId}/complete/`, {
//       method: 'POST',
//       headers: authHeaders(),
//       body: JSON.stringify({ proof }),
//     }),
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // SAFE FETCH
// // ─────────────────────────────────────────────────────────────────────────────
// async function safeFetch(apiFn) {
//   try {
//     const res = await apiFn();
//     if (!res.ok) {
//       const err = await res.json().catch(() => ({}));
//       console.error(`API ${res.status}:`, err);
//       return null;
//     }
//     return await res.json();
//   } catch (e) {
//     console.error('Network:', e.message);
//     return null;
//   }
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // MOCK FALLBACK DATA (API না থাকলে দেখাবে)
// // ─────────────────────────────────────────────────────────────────────────────
// const MOCK_TASKS = [
//   { id: 1, task_id: 'publish_sponsored', name: 'Publish Sponsored Post',   category: 'marketing',   rewards: { points: 50  } },
//   { id: 2, task_id: 'affiliate_surveys', name: 'Complete Affiliate Surveys',category: 'affiliate',   rewards: { points: 100 } },
//   { id: 3, task_id: 'signup_users',      name: 'Sign Up New Users',         category: 'acquisition', rewards: { points: 25  } },
//   { id: 4, task_id: 'install_app',       name: 'Download & Install App',    category: 'offers',      rewards: { points: 75  } },
// ];

// const MOCK_ACTIVITY = [
//   { id: 1, user: { username: 'Arun Dev' }, task: { task_id: 'Affiliate#1250' }, status: 'completed' },
//   { id: 2, user: { username: 'maria_w'  }, task: { task_id: 'Signature#1245' }, status: 'pending'   },
//   { id: 3, user: { username: 'james_c'  }, task: { task_id: 'Affiliate#1203' }, status: 'completed' },
//   { id: 4, user: { username: 'system'   }, task: { task_id: 'Affiliate#1203' }, status: 'completed' },
// ];

// const MOCK_PERF = [
//   { name: 'Complete Affiliate Surveys', pct: 62.8, sub: 62.6, cls: 'perf-bar-1' },
//   { name: 'Sign Up New Users',          pct: 50.9, sub: 50.3, cls: 'perf-bar-2' },
//   { name: 'Publish Sponsored Post',     pct: 44.2, sub: 44.2, cls: 'perf-bar-3' },
// ];

// // ─────────────────────────────────────────────────────────────────────────────
// // HELPERS
// // ─────────────────────────────────────────────────────────────────────────────
// const CAT_CLS = {
//   marketing: 'cat-marketing', affiliate: 'cat-affiliate',
//   acquisition: 'cat-acquisition', offers: 'cat-offers',
//   daily_retention: 'cat-affiliate', gamified: 'cat-offers',
//   ads_multimedia: 'cat-acquisition', app_social: 'cat-marketing',
// };
// const catCls  = (c = '') => CAT_CLS[c.toLowerCase()] || 'cat-marketing';
// const getReward = t => t.reward_amount || t.rewards?.points || 0;
// const getRefId  = item => `#${String(item.id || '').slice(-4) || '0000'}`;
// const AVTR = { 'arun dev': '👨‍💻', 'maria_w': '👩', 'james_c': '👨', 'system': '🖥️' };
// const avtr  = (n = '') => AVTR[n.toLowerCase()] || '👤';

// // ─────────────────────────────────────────────────────────────────────────────
// // ICONS
// // ─────────────────────────────────────────────────────────────────────────────
// const Ico = {
//   Users:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
//   Act:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
//   Bar:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
//   Lock:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
//   Bell:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
//   User:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
//   Cal:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>,
//   Search: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // LOADING RING
// // ─────────────────────────────────────────────────────────────────────────────
// function LoadingRing() {
//   return (
//     <div className="loading-ring">
//       <svg viewBox="0 0 120 120">
//         <defs>
//           <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="100%">
//             <stop offset="0%"   stopColor="#00b4ff" stopOpacity="0"/>
//             <stop offset="50%"  stopColor="#00e5ff" stopOpacity="1"/>
//             <stop offset="100%" stopColor="#00b4ff" stopOpacity="0.2"/>
//           </linearGradient>
//         </defs>
//         <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(0,180,255,0.08)" strokeWidth="8"/>
//         <circle cx="60" cy="60" r="50" fill="none" stroke="url(#rg)" strokeWidth="8"
//           strokeLinecap="round" strokeDasharray="240 80"/>
//         <circle cx="60" cy="60" r="35" fill="none" stroke="rgba(0,229,255,0.05)" strokeWidth="4"/>
//         <circle cx="60" cy="60" r="35" fill="none" stroke="rgba(0,229,255,0.4)" strokeWidth="4"
//           strokeLinecap="round" strokeDasharray="120 100"/>
//         <circle cx="60" cy="60" r="8" fill="rgba(0,229,255,0.1)"/>
//         <circle cx="60" cy="60" r="4" fill="rgba(0,229,255,0.3)"/>
//       </svg>
//     </div>
//   );
// }

// function ProgressSkeleton() {
//   return (
//     <div className="progress-table">
//       {[0,1,2].map(r => (
//         <React.Fragment key={r}>
//           <div className="progress-row">
//             <div className="skeleton-block sk-wide"   style={{width:`${70+r*10}%`}}/>
//             <div className="skeleton-block sk-medium" style={{width:`${50+r*8}%`}}/>
//             <div className="skeleton-block sk-narrow" style={{width:`${60+r*5}%`}}/>
//           </div>
//           <div className="progress-row">
//             <div className="skeleton-block sk-wide"   style={{width:`${80-r*5}%`}}/>
//             <div className="skeleton-block sk-medium" style={{width:`${45+r*12}%`}}/>
//           </div>
//         </React.Fragment>
//       ))}
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // TOAST
// // ─────────────────────────────────────────────────────────────────────────────
// function Toast({ msg, type, onClose }) {
//   useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
//   return <div className={`toast toast-${type}`}>{msg}</div>;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // MAIN DASHBOARD COMPONENT
// // ─────────────────────────────────────────────────────────────────────────────
// export default function TasksDashboard() {
//   const [tasks,     setTasks]     = useState(MOCK_TASKS);
//   const [activity,  setActivity]  = useState(MOCK_ACTIVITY);
//   const [perf,      setPerf]      = useState(MOCK_PERF);
//   const [histStats, setHistStats] = useState(null);
//   const [timer,     setTimer]     = useState(REFRESH_SECONDS);
//   const [lastUp,    setLastUp]    = useState('just now');
//   const [loading,   setLoading]   = useState(false);
//   const [search,    setSearch]    = useState('');
//   const [toast,     setToast]     = useState(null);
//   // { [task.id]: { phase: 'idle'|'starting'|'completing'|'done', completionId } }
//   const [taskState, setTaskState] = useState({});
//   useEffect(() => {
//   const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || '';
//   const h = { 'Authorization': `Bearer ${token}` };

//   fetch('/api/tasks/tasks/?page_size=10', { headers: h })
//     .then(r => r.ok ? r.json() : null)
//     .then(data => {
//       if (!data) return;
//       const list = data.data || data.results || [];
//       if (list.length > 0) setTasks(list.map(t => ({
//         id: t.id || t.task_id,
//         name: t.name || t.title || 'Task',
//         status: t.status || 'active',
//         reward: t.reward_amount || t.points || 0,
//         completions: t.total_completions || t.completion_count || 0,
//       })));
//     }).catch(() => {});

//   fetch('/api/tasks/statistics/', { headers: h })
//     .then(r => r.ok ? r.json() : null)
//     .then(data => {
//       if (!data) return;
//       const s = data.data || data;
//       if (s.total_tasks != null) setPerf([
//         { label: 'Total Tasks',    value: s.total_tasks || 0 },
//         { label: 'Active',         value: s.active_tasks || 0 },
//         { label: 'Completions',    value: s.total_completions || 0 },
//         { label: 'Featured',       value: s.featured_tasks || 0 },
//       ]);
//     }).catch(() => {});
// }, []);

//   const timerRef  = useRef(null);
//   const userLevel = parseInt(localStorage.getItem('user_level') || '1', 10);
//   const dateStr   = new Date().toLocaleDateString('en-US', { month:'long', day:'numeric', year:'numeric' });

//   const showToast = useCallback((msg, type = 'success') =>
//     setToast({ msg, type, key: Date.now() }), []);

//   // ── FETCH ALL ─────────────────────────────────────────────────────────────
//   const fetchAll = useCallback(async (showLoader = false) => {
//     if (showLoader) setLoading(true);

//     const [tasksRes, actRes, statsRes, histRes] = await Promise.all([
//       safeFetch(() => API.getTasks(userLevel)),
//       safeFetch(() => API.getActivity()),
//       safeFetch(() => API.getStatistics()),
//       safeFetch(() => API.getHistory()),
//     ]);

//     // ── MasterTaskViewSet → { status:'success', data:[...], pagination:{...} }
//     if (tasksRes?.data)    setTasks(tasksRes.data);
//     else if (tasksRes?.results) setTasks(tasksRes.results);

//     // ── TaskCompletionViewSet list → { status:'success', data:[...] }
//     if (actRes?.data)      setActivity(actRes.data);
//     else if (actRes?.results) setActivity(actRes.results);

//     // ── TaskStatisticsView → { status:'success', data:{ top_tasks:[...], ... } }
//     if (statsRes?.data?.top_tasks) {
//       setPerf(statsRes.data.top_tasks.slice(0, 3).map((t, i) => ({
//         name: t.name || t.task_name || 'Task',
//         pct:  parseFloat(t.conversion_rate || t.completion_rate || 0),
//         sub:  parseFloat(t.conversion_rate || t.completion_rate || 0),
//         cls:  `perf-bar-${i + 1}`,
//       })));
//     }

//     // ── TaskCompletionViewSet.history → { status:'success', data:[...], stats:{...} }
//     if (histRes?.stats) setHistStats(histRes.stats);

//     const now = new Date();
//     setLastUp(`${now.getHours()}:${String(now.getMinutes()).padStart(2,'0')}`);
//     setTimer(REFRESH_SECONDS);
//     if (showLoader) setLoading(false);
//   }, [userLevel]);

//   // ── COUNTDOWN AUTO-REFRESH ────────────────────────────────────────────────
//   useEffect(() => {
//     fetchAll(true);
//     timerRef.current = setInterval(() => {
//       setTimer(p => { if (p <= 1) { fetchAll(); return REFRESH_SECONDS; } return p - 1; });
//     }, 1000);
//     return () => clearInterval(timerRef.current);
//   }, [fetchAll]);

//   // ── COMPLETE TASK (2 steps) ───────────────────────────────────────────────
//   const handleComplete = async (task) => {
//     const tid   = task.id;
//     const phase = taskState[tid]?.phase || 'idle';
//     if (phase === 'starting' || phase === 'completing') return;

//     // STEP 1 — POST /api/tasks/completions/ { task: task.id }
//     // TaskCompletionViewSet.create() response:
//     //   { status: 'started',         data: { id: completionId, ... } }
//     //   { status: 'already_started', data: { id: completionId, ... } }
//     //   { error: '...', error_code: 'TASK_UNAVAILABLE' }
//     setTaskState(p => ({ ...p, [tid]: { phase: 'starting' } }));
//     const startRes = await safeFetch(() => API.startTask(task.id));

//     if (!startRes || (!startRes.data?.id)) {
//       setTaskState(p => ({ ...p, [tid]: { phase: 'idle' } }));
//       showToast(startRes?.error || 'Task not available', 'error');
//       return;
//     }

//     const completionId = startRes.data.id;
//     setTaskState(p => ({ ...p, [tid]: { phase: 'completing', completionId } }));

//     // STEP 2 — POST /api/tasks/completions/{id}/complete/
//     // TaskCompletionViewSet.mark_complete() response:
//     //   { status: 'completed',          data:{...}, rewards:{ points:N }, breakdown:{...} }
//     //   { status: 'already_completed',  data:{...} }
//     //   { status: 'completed_with_warning', data:{...}, warning:'...' }
//     const completeRes = await safeFetch(() => API.completeTask(completionId));

//     if (completeRes?.status === 'completed' || completeRes?.status === 'already_completed') {
//       const pts = completeRes.rewards?.points || 0;
//       showToast(pts > 0 ? `✅ +${pts} points earned!` : '✅ Task completed!', 'success');
//       setTaskState(p => ({ ...p, [tid]: { phase: 'done', completionId } }));
//       setTimeout(() => fetchAll(), 800);
//     } else {
//       showToast(completeRes?.error || 'Failed to complete task', 'error');
//       setTaskState(p => ({ ...p, [tid]: { phase: 'idle' } }));
//     }
//   };

//   // ── UI HELPERS ────────────────────────────────────────────────────────────
//   const filtered = tasks.filter(t =>
//     (t.name || '').toLowerCase().includes(search.toLowerCase()) ||
//     (t.category || '').toLowerCase().includes(search.toLowerCase())
//   );

//   const timerFmt = `00:${String(timer).padStart(2, '0')}`;

//   function btnLabel(task) {
//     const ph = taskState[task.id]?.phase || 'idle';
//     if (ph === 'starting')   return 'Starting...';
//     if (ph === 'completing') return 'Completing...';
//     if (ph === 'done')       return '✓ Done';
//     return 'Complete Task';
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   return (
//     <div className="tasks-dashboard">

//       {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={() => setToast(null)}/>}

//       {/* NAV */}
//       <nav className="dashboard-nav">
//         <div className="nav-brand">
//           <div className="brand-logo">
//             <svg viewBox="0 0 24 24">
//               <polygon points="12,2 15.5,8.5 22,9.5 17,14.5 18,22 12,18.5 6,22 7,14.5 2,9.5 8.5,8.5" fill="#020b18"/>
//             </svg>
//           </div>
//           <span className="brand-name">TASKS <span>DASHBOARD</span></span>
//         </div>

//         <div className="nav-search">
//           <span className="search-icon"><Ico.Search /></span>
//           <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}/>
//         </div>

//         <div className="nav-actions">
//           <button className="nav-btn"><Ico.Bell /><span className="notif-badge">1</span></button>
//           <button className="nav-btn"><Ico.User /></button>
//           <button className="date-btn"><Ico.Cal /> {dateStr}</button>
//         </div>
//       </nav>

//       {/* REFRESH BAR */}
//       <div className="refresh-bar">
//         {loading
//           ? <span>Loading data...</span>
//           : <>Data refresh in <span className="timer">{timerFmt}</span> last update <span className="last-update">{lastUp}</span></>
//         }
//       </div>

//       {/* GRID */}
//       <div className="dashboard-content">

//         {/* MY TASKS — MasterTaskViewSet.list() */}
//         <div className="glass-card my-tasks-card">
//           <div className="card-header">
//             <h2 className="card-title"><Ico.Users /> My Tasks</h2>
//           </div>
//           <div className="tasks-grid">
//             {filtered.slice(0, 4).map(task => {
//               const reward = getReward(task);
//               const ph     = taskState[task.id]?.phase || 'idle';
//               const isDone = ph === 'done';
//               const isBusy = ph === 'starting' || ph === 'completing';
//               const cat    = (task.category || 'marketing').replace(/_/g, ' ');

//               return (
//                 <div className={`task-item${isDone ? ' task-done' : ''}`} key={task.id}>
//                   <div className="task-header">
//                     <span className="task-name">{task.name}</span>
//                     <div className="reward-badge-top">
//                       <span className="reward-amount-top">${reward}</span>
//                       <span className="reward-label-badge">REWARD</span>
//                     </div>
//                   </div>
//                   <div className="task-category">
//                     <span className={`category-dot ${catCls(task.category)}`}/>
//                     {cat.charAt(0).toUpperCase() + cat.slice(1)}
//                   </div>
//                   <div className="task-footer">
//                     <div className="task-reward-display">
//                       <span className="reward-big">${reward}</span>
//                       <span className="reward-small-label">REWARD</span>
//                     </div>
//                     <button
//                       className={`complete-btn${isDone ? ' btn-done' : ''}`}
//                       onClick={() => handleComplete(task)}
//                       disabled={isBusy || isDone}
//                     >
//                       {btnLabel(task)}
//                     </button>
//                   </div>
//                 </div>
//               );
//             })}
//             {filtered.length === 0 && (
//               <div className="no-tasks">No tasks{search && ` for "${search}"`}</div>
//             )}
//           </div>
//         </div>

//         {/* RECENT ACTIVITY — TaskCompletionViewSet.list() */}
//         <div className="glass-card activity-card">
//           <div className="card-header">
//             <h2 className="card-title"><Ico.Act /> Recent Activity Log</h2>
//             <button className="view-all-btn">View All</button>
//           </div>
//           <div className="activity-list">
//             {activity.slice(0, 4).map((item, i) => {
//               // TaskCompletionSerializer fields: user.username, task.task_id, status
//               const uname = item.user?.username || item.username || 'User';
//               const ref   = item.task?.task_id || item.task?.name || 'Task';
//               const refId = getRefId(item);
//               const st    = item.status || 'pending';
//               return (
//                 <div className="activity-item" key={item.id || i}>
//                   <div className="activity-avatar"><span>{avtr(uname)}</span></div>
//                   <div className="activity-info">
//                     <div className="activity-user">{uname}<span className="activity-id">{refId}</span></div>
//                     <div className="activity-sub">{ref}</div>
//                   </div>
//                   <div className={`status-badge status-${st}`}>
//                     <span className="status-dot"/>
//                     {st.charAt(0).toUpperCase() + st.slice(1)}
//                   </div>
//                 </div>
//               );
//             })}
//           </div>
//         </div>

//         {/* PROGRESS — TaskCompletionViewSet.user_history() stats */}
//         <div className="glass-card progress-card">
//           <div className="card-header">
//             <h2 className="card-title"><Ico.Lock /> Progresss</h2>
//             {histStats && (
//               <div className="hist-badges">
//                 <span className="hist-badge">✅ {histStats.total_completed} done</span>
//                 <span className="hist-badge">🔥 {histStats.streak_days}d</span>
//               </div>
//             )}
//           </div>
//           <div className="progress-inner">
//             <ProgressSkeleton />
//             <div className="progress-center">
//               <LoadingRing />
//               <div className="reloading-text">Reloading data...</div>
//               {histStats && (
//                 <div className="hist-points">
//                   <span className="pts-label">Points</span>
//                   <span className="pts-value">{(histStats.total_points || 0).toLocaleString()}</span>
//                 </div>
//               )}
//             </div>
//           </div>
//         </div>

//         {/* TASK PERFORMANCE — TaskStatisticsView.get() */}
//         <div className="glass-card performance-card">
//           <div className="card-header">
//             <h2 className="card-title"><Ico.Bar /> Task Performance</h2>
//             <button className="view-all-btn">View All</button>
//           </div>
//           <div className="performance-inner">
//             <div className="performance-subtitle">Top Tasks by Conversion</div>
//             {perf.map((item, i) => (
//               <div className="perf-item" key={i}>
//                 <div className="perf-header">
//                   <span className="perf-percent-big">{Number(item.pct).toFixed(1)}%</span>
//                 </div>
//                 <div className="perf-bar-container">
//                   <div className={`perf-bar ${item.cls}`} style={{width:`${item.pct}%`}}/>
//                 </div>
//                 <div className="perf-label-row">
//                   <span className="perf-name">{item.name}</span>
//                   <span className="perf-percent-small">{Number(item.sub).toFixed(1)}%</span>
//                 </div>
//               </div>
//             ))}
//           </div>
//         </div>

//       </div>
//     </div>
//   );
// }