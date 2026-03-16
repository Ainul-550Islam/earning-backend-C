// src/pages/VersionControl.jsx
// Version Control Admin Page — Cyberpunk Theme
// Tabs: Update Policies | Maintenance | Platform Redirects

import { useState, useCallback } from 'react';
import * as Icon from 'react-feather';
import { usePolicies, useMaintenance, useRedirects } from '../hooks/useVersionControl';
import '../styles/VersionControl.css';

// ── Helpers ───────────────────────────────────────────────────────
const PLATFORMS      = ['android','ios','web','windows','macos'];
const UPDATE_TYPES   = ['OPTIONAL','REQUIRED','CRITICAL'];
const POLICY_STATUS  = ['draft','active','inactive','archived'];
const MAINT_STATUS   = ['SCHEDULED','ACTIVE','COMPLETED','CANCELLED'];
const REDIRECT_TYPES = ['STORE','DIRECT','CDN','CUSTOM'];

const STATUS_COLORS = {
  active:'cyan', draft:'gold', inactive:'muted', archived:'muted',
  SCHEDULED:'gold', ACTIVE:'green', COMPLETED:'muted', CANCELLED:'red',
  OPTIONAL:'cyan', REQUIRED:'gold', CRITICAL:'red',
};
const PLATFORM_ICONS = { android:'📱', ios:'🍎', web:'🌐', windows:'🪟', macos:'💻' };

const fmtDate = (d) => d ? new Date(d).toLocaleString([], { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '—';
const fmtDateInput = (d) => d ? new Date(d).toISOString().slice(0,16) : '';

function Badge({ value }) {
  const color = STATUS_COLORS[value] || 'muted';
  return <span className={`vc-badge vc-badge--${color}`}>{value}</span>;
}

function EmptyState({ icon, text, onAdd }) {
  return (
    <div className="vc-empty">
      <div className="vc-empty-icon">{icon}</div>
      <p className="vc-empty-text">{text}</p>
      {onAdd && <button className="vc-btn vc-btn--cyan" onClick={onAdd}>+ Add First</button>}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="vc-loading-rows">
      {[1,2,3].map(i => <div key={i} className="vc-loading-row"/>)}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────
function Modal({ title, onClose, children }) {
  return (
    <div className="vc-modal-bg" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="vc-modal">
        <div className="vc-modal-header">
          <h3 className="vc-modal-title">{title}</h3>
          <button className="vc-modal-close" onClick={onClose}><Icon.X size={18}/></button>
        </div>
        <div className="vc-modal-body">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="vc-field">
      <label className="vc-field-label">{label}</label>
      {children}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// TAB 1 — Update Policies
// ══════════════════════════════════════════════════════════════════
function PoliciesTab() {
  const { policies, loading, error, createPolicy, updatePolicy, deletePolicy, activatePolicy, deactivatePolicy } = usePolicies();
  const [modal, setModal] = useState(null); // null | 'create' | {policy}
  const [form,  setForm]  = useState({});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');

  const openCreate = () => {
    setForm({ platform:'android', update_type:'OPTIONAL', status:'draft', min_version:'', target_version:'', release_notes:'' });
    setModal('create'); setErr('');
  };
  const openEdit = (p) => {
    setForm({ ...p, force_update_after: fmtDateInput(p.force_update_after) });
    setModal(p); setErr('');
  };

  const handleSave = async () => {
    if (!form.min_version?.trim()) { setErr('Min version required'); return; }
    if (!form.target_version?.trim()) { setErr('Target version required'); return; }
    setSaving(true); setErr('');
    try {
      const payload = {
        ...form,
        force_update_after: form.force_update_after || null,
      };
      if (modal === 'create') await createPolicy(payload);
      else await updatePolicy(modal.id, payload);
      setModal(null);
    } catch (e) {
      setErr(e?.response?.data ? JSON.stringify(e.response.data) : e.message);
    } finally { setSaving(false); }
  };

  const handleActivate = async (p) => {
    try { await activatePolicy(p.id); } catch (e) { alert(e.message); }
  };
  const handleDeactivate = async (p) => {
    try { await deactivatePolicy(p.id); } catch (e) { alert(e.message); }
  };
  const handleDelete = async (p) => {
    if (!confirm(`Delete policy for ${p.platform} ${p.min_version}→${p.target_version}?`)) return;
    try { await deletePolicy(p.id); } catch (e) { alert(e.message); }
  };

  return (
    <div className="vc-tab-content">
      <div className="vc-tab-header">
        <div>
          <h2 className="vc-tab-title">App Update Policies</h2>
          <p className="vc-tab-sub">Control force-update and optional-update behaviour per platform</p>
        </div>
        <button className="vc-btn vc-btn--cyan" onClick={openCreate}>
          <Icon.Plus size={14}/> New Policy
        </button>
      </div>

      {error && <div className="vc-error">{error}</div>}
      {loading ? <LoadingRows/> : policies.length === 0
        ? <EmptyState icon="🔖" text="No update policies yet" onAdd={openCreate}/>
        : (
          <div className="vc-table-wrap">
            <table className="vc-table">
              <thead>
                <tr>
                  <th>Platform</th><th>Version Range</th><th>Target</th>
                  <th>Type</th><th>Status</th><th>Force After</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map(p => (
                  <tr key={p.id} className="vc-table-row">
                    <td><span className="vc-platform">{PLATFORM_ICONS[p.platform]||'📦'} {p.platform}</span></td>
                    <td><code className="vc-code">{p.min_version} → {p.max_version||'∞'}</code></td>
                    <td><code className="vc-code vc-code--cyan">{p.target_version}</code></td>
                    <td><Badge value={p.update_type}/></td>
                    <td><Badge value={p.status}/></td>
                    <td className="vc-muted">{fmtDate(p.force_update_after)}</td>
                    <td>
                      <div className="vc-actions">
                        {p.status === 'draft' && (
                          <button className="vc-icon-btn vc-icon-btn--green" title="Activate" onClick={() => handleActivate(p)}>
                            <Icon.CheckCircle size={14}/>
                          </button>
                        )}
                        {p.status === 'active' && (
                          <button className="vc-icon-btn vc-icon-btn--gold" title="Deactivate" onClick={() => handleDeactivate(p)}>
                            <Icon.PauseCircle size={14}/>
                          </button>
                        )}
                        <button className="vc-icon-btn" title="Edit" onClick={() => openEdit(p)}>
                          <Icon.Edit2 size={14}/>
                        </button>
                        <button className="vc-icon-btn vc-icon-btn--red" title="Delete" onClick={() => handleDelete(p)}>
                          <Icon.Trash2 size={14}/>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }

      {modal && (
        <Modal title={modal === 'create' ? 'New Update Policy' : 'Edit Policy'} onClose={() => setModal(null)}>
          <div className="vc-form">
            <div className="vc-form-row">
              <Field label="Platform">
                <select className="vc-select" value={form.platform||''} onChange={e=>setForm(f=>({...f,platform:e.target.value}))}>
                  {PLATFORMS.map(p=><option key={p} value={p}>{PLATFORM_ICONS[p]} {p}</option>)}
                </select>
              </Field>
              <Field label="Update Type">
                <select className="vc-select" value={form.update_type||''} onChange={e=>setForm(f=>({...f,update_type:e.target.value}))}>
                  {UPDATE_TYPES.map(t=><option key={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <select className="vc-select" value={form.status||''} onChange={e=>setForm(f=>({...f,status:e.target.value}))}>
                  {POLICY_STATUS.map(s=><option key={s}>{s}</option>)}
                </select>
              </Field>
            </div>
            <div className="vc-form-row">
              <Field label="Min Version *">
                <input className="vc-input" placeholder="e.g. 1.0.0" value={form.min_version||''} onChange={e=>setForm(f=>({...f,min_version:e.target.value}))}/>
              </Field>
              <Field label="Max Version">
                <input className="vc-input" placeholder="e.g. 2.0.0 (blank=all)" value={form.max_version||''} onChange={e=>setForm(f=>({...f,max_version:e.target.value}))}/>
              </Field>
              <Field label="Target Version *">
                <input className="vc-input" placeholder="e.g. 2.1.0" value={form.target_version||''} onChange={e=>setForm(f=>({...f,target_version:e.target.value}))}/>
              </Field>
            </div>
            <Field label="Force Update After">
              <input className="vc-input" type="datetime-local" value={form.force_update_after||''} onChange={e=>setForm(f=>({...f,force_update_after:e.target.value}))}/>
            </Field>
            <Field label="Release Notes URL">
              <input className="vc-input" placeholder="https://..." value={form.release_notes_url||''} onChange={e=>setForm(f=>({...f,release_notes_url:e.target.value}))}/>
            </Field>
            <Field label="Release Notes (Markdown)">
              <textarea className="vc-textarea" rows={5} placeholder="## What's new..." value={form.release_notes||''} onChange={e=>setForm(f=>({...f,release_notes:e.target.value}))}/>
            </Field>
            {err && <div className="vc-form-error">{err}</div>}
            <div className="vc-form-actions">
              <button className="vc-btn vc-btn--ghost" onClick={() => setModal(null)}>Cancel</button>
              <button className="vc-btn vc-btn--cyan" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Policy'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// TAB 2 — Maintenance Schedules
// ══════════════════════════════════════════════════════════════════
function MaintenanceTab() {
  const { schedules, loading, error, createSchedule, updateSchedule, deleteSchedule, startMaintenance, endMaintenance, cancelMaintenance } = useMaintenance();
  const [modal,  setModal]  = useState(null);
  const [form,   setForm]   = useState({});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');

  const openCreate = () => {
    const now = new Date();
    const later = new Date(now.getTime() + 60*60*1000);
    setForm({
      title:'', description:'', platforms: [], notify_users: true,
      scheduled_start: fmtDateInput(now),
      scheduled_end:   fmtDateInput(later),
    });
    setModal('create'); setErr('');
  };
  const openEdit = (s) => {
    setForm({
      ...s,
      scheduled_start: fmtDateInput(s.scheduled_start),
      scheduled_end:   fmtDateInput(s.scheduled_end),
    });
    setModal(s); setErr('');
  };

  const togglePlatform = (p) => {
    setForm(f => ({
      ...f,
      platforms: f.platforms?.includes(p)
        ? f.platforms.filter(x => x !== p)
        : [...(f.platforms||[]), p],
    }));
  };

  const handleSave = async () => {
    if (!form.title?.trim()) { setErr('Title required'); return; }
    if (!form.scheduled_start) { setErr('Start time required'); return; }
    if (!form.scheduled_end) { setErr('End time required'); return; }
    setSaving(true); setErr('');
    try {
      const payload = {
        ...form,
        scheduled_start: new Date(form.scheduled_start).toISOString(),
        scheduled_end:   new Date(form.scheduled_end).toISOString(),
      };
      if (modal === 'create') await createSchedule(payload);
      else await updateSchedule(modal.id, payload);
      setModal(null);
    } catch (e) {
      setErr(e?.response?.data ? JSON.stringify(e.response.data) : e.message);
    } finally { setSaving(false); }
  };

  return (
    <div className="vc-tab-content">
      <div className="vc-tab-header">
        <div>
          <h2 className="vc-tab-title">Maintenance Schedules</h2>
          <p className="vc-tab-sub">Plan and manage maintenance windows — users see 503 during ACTIVE windows</p>
        </div>
        <button className="vc-btn vc-btn--cyan" onClick={openCreate}>
          <Icon.Plus size={14}/> Schedule Maintenance
        </button>
      </div>

      {error && <div className="vc-error">{error}</div>}
      {loading ? <LoadingRows/> : schedules.length === 0
        ? <EmptyState icon="🔧" text="No maintenance scheduled" onAdd={openCreate}/>
        : (
          <div className="vc-cards">
            {schedules.map(s => (
              <div key={s.id} className={`vc-maint-card vc-maint-card--${(s.status||'').toLowerCase()}`}>
                <div className="vc-maint-card-top">
                  <div>
                    <h3 className="vc-maint-title">{s.title}</h3>
                    {s.description && <p className="vc-maint-desc">{s.description}</p>}
                  </div>
                  <Badge value={s.status}/>
                </div>
                <div className="vc-maint-meta">
                  <span>🕐 {fmtDate(s.scheduled_start)} — {fmtDate(s.scheduled_end)}</span>
                  <span>⏱ {s.duration_minutes||'?'} min</span>
                  <span>📱 {s.platforms?.length ? s.platforms.join(', ') : 'All platforms'}</span>
                  {s.notify_users && <span>🔔 Notify users</span>}
                </div>
                <div className="vc-actions">
                  {s.status === 'SCHEDULED' && <>
                    <button className="vc-icon-btn vc-icon-btn--red" title="Start now" onClick={() => startMaintenance(s.id)}>
                      <Icon.AlertTriangle size={14}/> Start
                    </button>
                    <button className="vc-icon-btn vc-icon-btn--gold" title="Cancel" onClick={() => cancelMaintenance(s.id)}>
                      <Icon.XCircle size={14}/> Cancel
                    </button>
                  </>}
                  {s.status === 'ACTIVE' && (
                    <button className="vc-icon-btn vc-icon-btn--green" title="End maintenance" onClick={() => endMaintenance(s.id)}>
                      <Icon.CheckCircle size={14}/> End
                    </button>
                  )}
                  <button className="vc-icon-btn" title="Edit" onClick={() => openEdit(s)}>
                    <Icon.Edit2 size={14}/>
                  </button>
                  <button className="vc-icon-btn vc-icon-btn--red" title="Delete" onClick={() => { if(confirm('Delete this schedule?')) deleteSchedule(s.id); }}>
                    <Icon.Trash2 size={14}/>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      }

      {modal && (
        <Modal title={modal === 'create' ? 'Schedule Maintenance' : 'Edit Schedule'} onClose={() => setModal(null)}>
          <div className="vc-form">
            <Field label="Title *">
              <input className="vc-input" placeholder="e.g. Database migration" value={form.title||''} onChange={e=>setForm(f=>({...f,title:e.target.value}))}/>
            </Field>
            <Field label="Description / User Message">
              <textarea className="vc-textarea" rows={3} placeholder="We're performing scheduled maintenance..." value={form.description||''} onChange={e=>setForm(f=>({...f,description:e.target.value}))}/>
            </Field>
            <div className="vc-form-row">
              <Field label="Scheduled Start *">
                <input className="vc-input" type="datetime-local" value={form.scheduled_start||''} onChange={e=>setForm(f=>({...f,scheduled_start:e.target.value}))}/>
              </Field>
              <Field label="Scheduled End *">
                <input className="vc-input" type="datetime-local" value={form.scheduled_end||''} onChange={e=>setForm(f=>({...f,scheduled_end:e.target.value}))}/>
              </Field>
            </div>
            <Field label="Affected Platforms (empty = all)">
              <div className="vc-platform-pills">
                {PLATFORMS.map(p => (
                  <button key={p} type="button"
                    className={`vc-pill ${form.platforms?.includes(p) ? 'vc-pill--active' : ''}`}
                    onClick={() => togglePlatform(p)}>
                    {PLATFORM_ICONS[p]} {p}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="">
              <label className="vc-checkbox-label">
                <input type="checkbox" checked={!!form.notify_users} onChange={e=>setForm(f=>({...f,notify_users:e.target.checked}))}/>
                <span>Send push notifications before maintenance</span>
              </label>
            </Field>
            {err && <div className="vc-form-error">{err}</div>}
            <div className="vc-form-actions">
              <button className="vc-btn vc-btn--ghost" onClick={() => setModal(null)}>Cancel</button>
              <button className="vc-btn vc-btn--cyan" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Schedule'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// TAB 3 — Platform Redirects
// ══════════════════════════════════════════════════════════════════
function RedirectsTab() {
  const { redirects, loading, error, createRedirect, updateRedirect, deleteRedirect, toggleRedirect } = useRedirects();
  const [modal,  setModal]  = useState(null);
  const [form,   setForm]   = useState({});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');

  const openCreate = () => {
    setForm({ platform:'android', redirect_type:'STORE', url:'', notes:'', is_active:true });
    setModal('create'); setErr('');
  };
  const openEdit = (r) => { setForm({ ...r }); setModal(r); setErr(''); };

  const handleSave = async () => {
    if (!form.url?.trim()) { setErr('URL required'); return; }
    setSaving(true); setErr('');
    try {
      if (modal === 'create') await createRedirect(form);
      else await updateRedirect(modal.id, form);
      setModal(null);
    } catch (e) {
      setErr(e?.response?.data ? JSON.stringify(e.response.data) : e.message);
    } finally { setSaving(false); }
  };

  return (
    <div className="vc-tab-content">
      <div className="vc-tab-header">
        <div>
          <h2 className="vc-tab-title">Platform Redirects</h2>
          <p className="vc-tab-sub">Store links and download URLs per platform</p>
        </div>
        <button className="vc-btn vc-btn--cyan" onClick={openCreate}>
          <Icon.Plus size={14}/> Add Redirect
        </button>
      </div>

      {error && <div className="vc-error">{error}</div>}
      {loading ? <LoadingRows/> : redirects.length === 0
        ? <EmptyState icon="🔗" text="No platform redirects configured" onAdd={openCreate}/>
        : (
          <div className="vc-redirect-grid">
            {redirects.map(r => (
              <div key={r.id} className={`vc-redirect-card ${!r.is_active ? 'vc-redirect-card--inactive' : ''}`}>
                <div className="vc-redirect-top">
                  <span className="vc-redirect-platform">{PLATFORM_ICONS[r.platform]||'📦'} {r.platform}</span>
                  <div className="vc-actions">
                    <button
                      className={`vc-toggle ${r.is_active ? 'vc-toggle--on' : ''}`}
                      onClick={() => toggleRedirect(r.id, !r.is_active)}
                      title={r.is_active ? 'Deactivate' : 'Activate'}
                    />
                    <button className="vc-icon-btn" onClick={() => openEdit(r)}><Icon.Edit2 size={14}/></button>
                    <button className="vc-icon-btn vc-icon-btn--red" onClick={() => { if(confirm('Delete redirect?')) deleteRedirect(r.id); }}><Icon.Trash2 size={14}/></button>
                  </div>
                </div>
                <Badge value={r.redirect_type}/>
                <a href={r.url} target="_blank" rel="noreferrer" className="vc-redirect-url">{r.url}</a>
                {r.notes && <p className="vc-redirect-notes">{r.notes}</p>}
              </div>
            ))}
          </div>
        )
      }

      {modal && (
        <Modal title={modal === 'create' ? 'Add Platform Redirect' : 'Edit Redirect'} onClose={() => setModal(null)}>
          <div className="vc-form">
            <div className="vc-form-row">
              <Field label="Platform">
                <select className="vc-select" value={form.platform||''} onChange={e=>setForm(f=>({...f,platform:e.target.value}))}>
                  {PLATFORMS.map(p=><option key={p} value={p}>{PLATFORM_ICONS[p]} {p}</option>)}
                </select>
              </Field>
              <Field label="Redirect Type">
                <select className="vc-select" value={form.redirect_type||''} onChange={e=>setForm(f=>({...f,redirect_type:e.target.value}))}>
                  {REDIRECT_TYPES.map(t=><option key={t}>{t}</option>)}
                </select>
              </Field>
            </div>
            <Field label="URL *">
              <input className="vc-input" placeholder="https://play.google.com/store/..." value={form.url||''} onChange={e=>setForm(f=>({...f,url:e.target.value}))}/>
            </Field>
            <Field label="Internal Notes">
              <textarea className="vc-textarea" rows={2} value={form.notes||''} onChange={e=>setForm(f=>({...f,notes:e.target.value}))}/>
            </Field>
            <Field label="">
              <label className="vc-checkbox-label">
                <input type="checkbox" checked={!!form.is_active} onChange={e=>setForm(f=>({...f,is_active:e.target.checked}))}/>
                <span>Active</span>
              </label>
            </Field>
            {err && <div className="vc-form-error">{err}</div>}
            <div className="vc-form-actions">
              <button className="vc-btn vc-btn--ghost" onClick={() => setModal(null)}>Cancel</button>
              <button className="vc-btn vc-btn--cyan" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Redirect'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════
const TABS = [
  { id:'policies',    label:'Update Policies',  icon:<Icon.Shield size={15}/> },
  { id:'maintenance', label:'Maintenance',       icon:<Icon.Tool size={15}/> },
  { id:'redirects',   label:'Platform Redirects',icon:<Icon.Link size={15}/> },
];

export default function VersionControl() {
  const [activeTab, setActiveTab] = useState('policies');

  return (
    <div className="vc-root">
      {/* Page header */}
      <div className="vc-page-header">
        <div className="vc-page-header-inner">
          <div className="vc-page-title-wrap">
            <span className="vc-page-icon">⚙️</span>
            <div>
              <h1 className="vc-page-title">VERSION CONTROL</h1>
              <p className="vc-page-sub">Manage app updates, maintenance windows and store redirects</p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="vc-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`vc-tab ${activeTab === t.id ? 'vc-tab--active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="vc-content">
        {activeTab === 'policies'    && <PoliciesTab/>}
        {activeTab === 'maintenance' && <MaintenanceTab/>}
        {activeTab === 'redirects'   && <RedirectsTab/>}
      </div>
    </div>
  );
}
