// pages/Backup.jsx
// Backup Management — Ultra Glass Professional
// ✅ REAL API — সব backend endpoints connected
// ✅ CSS: ../styles/backup.css

import React, { useState, useEffect, useCallback, useRef } from 'react';
import '../styles/backup.css';

// ─────────────────────────────────────────────────────────────
// CONFIG & AUTH — unchanged
// ─────────────────────────────────────────────────────────────
const BASE = '/api/backup';

const authHeaders = () => ({
  'Authorization': `Bearer ${
    localStorage.getItem('adminAccessToken') ||
    localStorage.getItem('access_token') ||
    localStorage.getItem('auth_token') || ''
  }`,
  'Content-Type': 'application/json',
});

// ─────────────────────────────────────────────────────────────
// ALL API ENDPOINTS — real backend, unchanged
// ─────────────────────────────────────────────────────────────
const API = {
  // Backups CRUD
  backups:          () => fetch(`${BASE}/backups/?page_size=20&ordering=-start_time`, { headers: authHeaders() }),
  createBackup:     (d) => fetch(`${BASE}/backups/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  updateBackup:     (id,d) => fetch(`${BASE}/backups/${id}/`, { method:'PATCH', headers:authHeaders(), body:JSON.stringify(d) }),
  deleteBackup:     (id) => fetch(`${BASE}/backups/${id}/`, { method:'DELETE', headers:authHeaders() }),
  verifyBackup:     (id) => fetch(`${BASE}/backups/${id}/verify/`, { method:'POST', headers:authHeaders() }),
  healthCheck:      (id) => fetch(`${BASE}/backups/${id}/health_check/`, { method:'POST', headers:authHeaders(), body:JSON.stringify({full_check:true}) }),
  backupLogs:       (id) => fetch(`${BASE}/backups/${id}/logs/`, { headers:authHeaders() }),
  downloadBackup:   (id) => fetch(`${BASE}/backups/${id}/download/`, { headers:authHeaders() }),
  redundantCopy:    (id) => fetch(`${BASE}/backups/${id}/create_redundant_copy/`, { method:'POST', headers:authHeaders() }),
  cloneBackup:      (id) => fetch(`${BASE}/backups/${id}/clone/`, { method:'POST', headers:authHeaders() }),

  // Schedules CRUD
  schedules:        () => fetch(`${BASE}/schedules/`, { headers:authHeaders() }),
  createSchedule:   (d) => fetch(`${BASE}/schedules/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  updateSchedule:   (id,d) => fetch(`${BASE}/schedules/${id}/`, { method:'PATCH', headers:authHeaders(), body:JSON.stringify(d) }),
  deleteSchedule:   (id) => fetch(`${BASE}/schedules/${id}/`, { method:'DELETE', headers:authHeaders() }),
  toggleSchedule:   (id) => fetch(`${BASE}/schedules/${id}/toggle_active/`, { method:'POST', headers:authHeaders() }),
  runScheduleNow:   (id) => fetch(`${BASE}/schedules/${id}/run_now/`, { method:'POST', headers:authHeaders() }),

  // Storage Locations CRUD
  storages:         () => fetch(`${BASE}/storage-locations/`, { headers:authHeaders() }),
  createStorage:    (d) => fetch(`${BASE}/storage-locations/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  updateStorage:    (id,d) => fetch(`${BASE}/storage-locations/${id}/`, { method:'PATCH', headers:authHeaders(), body:JSON.stringify(d) }),
  deleteStorage:    (id) => fetch(`${BASE}/storage-locations/${id}/`, { method:'DELETE', headers:authHeaders() }),
  testConnection:   (id) => fetch(`${BASE}/storage-locations/${id}/test_connection/`, { method:'POST', headers:authHeaders() }),

  // Retention Policies CRUD
  retentions:       () => fetch(`${BASE}/retention-policies/`, { headers:authHeaders() }),
  createRetention:  (d) => fetch(`${BASE}/retention-policies/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  updateRetention:  (id,d) => fetch(`${BASE}/retention-policies/${id}/`, { method:'PATCH', headers:authHeaders(), body:JSON.stringify(d) }),
  deleteRetention:  (id) => fetch(`${BASE}/retention-policies/${id}/`, { method:'DELETE', headers:authHeaders() }),
  executeRetention: (id) => fetch(`${BASE}/retention-policies/${id}/execute/`, { method:'POST', headers:authHeaders() }),

  // System
  dashboard:        () => fetch(`${BASE}/dashboard-stats/`, { headers:authHeaders() }),
  metrics:          () => fetch(`${BASE}/system-metrics/`, { headers:authHeaders() }),
  backupStatus:     () => fetch(`${BASE}/backup-status/`, { headers:authHeaders() }),
  startBackup:      (d) => fetch(`${BASE}/start-backup/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  cancelBackup:     (id) => fetch(`${BASE}/cancel-backup/${id}/`, { method:'POST', headers:authHeaders() }),
  restoreBackup:    (d) => fetch(`${BASE}/restore-backup/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),
  cleanup:          () => fetch(`${BASE}/cleanup-old-backups/`, { method:'POST', headers:authHeaders() }),
  maintenance:      (d) => fetch(`${BASE}/maintenance-mode/`, { method:'POST', headers:authHeaders(), body:JSON.stringify(d) }),

  // Analytics
  growth:           () => fetch(`${BASE}/analytics/backup-growth/`, { headers:authHeaders() }),
  storageUsage:     () => fetch(`${BASE}/analytics/storage-usage/`, { headers:authHeaders() }),
  healthReport:     () => fetch(`${BASE}/reports/health-report/`, { headers:authHeaders() }),
};

// ─────────────────────────────────────────────────────────────
// SAFE FETCH — unchanged
// ─────────────────────────────────────────────────────────────
async function sf(fn) {
  try {
    const r = await fn();
    if (r.status === 204) return { success: true };
    const t = await r.text();
    if (!r.ok) { console.warn('[Backup]', r.status, t); return null; }
    try { return JSON.parse(t); } catch { return null; }
  } catch (e) { console.warn('[Backup]', e.message); return null; }
}
const exList = (r) => {
  if (!r) return [];
  if (Array.isArray(r)) return r;
  return r.results || r.data || r.backups || [];
};
const exObj = (r, fb = {}) => {
  if (!r) return fb;
  if (r.data && !Array.isArray(r.data)) return r.data;
  if (typeof r === 'object' && !Array.isArray(r)) return r;
  return fb;
};

// ─────────────────────────────────────────────────────────────
// FALLBACK DATA
// ─────────────────────────────────────────────────────────────
const FB_BACKUPS = [
  { id:'b001', backup_id:'BK-2026-001', name:'Full DB Backup',       backup_type:'full',         status:'completed',  file_size_human:'2.4 GB',  duration_human:'12m 34s', database_name:'earning_db', created_at:'2026-03-01T06:00:00Z', is_encrypted:true,  compression_type:'gzip', storage_type:'local', health_score:98, is_healthy:true  },
  { id:'b002', backup_id:'BK-2026-002', name:'Incremental Backup',   backup_type:'incremental',  status:'completed',  file_size_human:'380 MB',  duration_human:'3m 12s',  database_name:'earning_db', created_at:'2026-03-01T12:00:00Z', is_encrypted:true,  compression_type:'gzip', storage_type:'s3',    health_score:95, is_healthy:true  },
  { id:'b003', backup_id:'BK-2026-003', name:'Media Files Backup',   backup_type:'differential', status:'running',    file_size_human:'1.1 GB',  duration_human:'—',       database_name:'media',      created_at:'2026-03-02T06:00:00Z', is_encrypted:false, compression_type:'lz4',  storage_type:'local', health_score:80, is_healthy:true  },
  { id:'b004', backup_id:'BK-2026-004', name:'Config Backup',        backup_type:'full',         status:'failed',     file_size_human:'12 MB',   duration_human:'0m 45s',  database_name:'config',     created_at:'2026-03-01T18:00:00Z', is_encrypted:true,  compression_type:'none', storage_type:'ftp',   health_score:30, is_healthy:false },
  { id:'b005', backup_id:'BK-2026-005', name:'User Data Backup',     backup_type:'delta',        status:'completed',  file_size_human:'640 MB',  duration_human:'5m 22s',  database_name:'earning_db', created_at:'2026-03-01T00:00:00Z', is_encrypted:true,  compression_type:'zstd', storage_type:'s3',    health_score:92, is_healthy:true  },
  { id:'b006', backup_id:'BK-2026-006', name:'Weekly Full Backup',   backup_type:'full',         status:'pending',    file_size_human:'—',       duration_human:'—',       database_name:'earning_db', created_at:'2026-03-02T07:00:00Z', is_encrypted:true,  compression_type:'gzip', storage_type:'local', health_score:100,is_healthy:true  },
];
const FB_SCHEDULES = [
  { id:1, name:'Daily Full Backup',  schedule_type:'daily',   is_active:true,  next_run:'2026-03-03T06:00:00Z', backup_type:'full',        retention_days:30,  description:'Daily full database backup' },
  { id:2, name:'Hourly Incremental', schedule_type:'hourly',  is_active:true,  next_run:'2026-03-02T08:00:00Z', backup_type:'incremental', retention_days:7,   description:'Hourly incremental changes' },
  { id:3, name:'Weekly Archive',     schedule_type:'weekly',  is_active:true,  next_run:'2026-03-07T00:00:00Z', backup_type:'full',        retention_days:90,  description:'Weekly full archive backup' },
  { id:4, name:'Monthly Snapshot',   schedule_type:'monthly', is_active:false, next_run:'2026-04-01T00:00:00Z', backup_type:'full',        retention_days:365, description:'Monthly snapshot for compliance' },
  { id:5, name:'Delta Tracker Sync', schedule_type:'daily',   is_active:true,  next_run:'2026-03-03T02:00:00Z', backup_type:'delta',       retention_days:14,  description:'Daily delta sync' },
];
const FB_STORAGES = [
  { id:1, name:'Primary Local',  storage_type:'local', is_active:true,  host:'localhost',         total_size_human:'500 GB', used_size_human:'142 GB', available_size_human:'358 GB', used_percent:28.4, is_connected:true  },
  { id:2, name:'AWS S3 Bucket',  storage_type:'s3',    is_active:true,  host:'s3.amazonaws.com',  total_size_human:'∞',      used_size_human:'86 GB',  available_size_human:'∞',      used_percent:0,    is_connected:true  },
  { id:3, name:'FTP Archive',    storage_type:'ftp',   is_active:false, host:'ftp.backup.server', total_size_human:'200 GB', used_size_human:'44 GB',  available_size_human:'156 GB', used_percent:22.0, is_connected:false },
];
const FB_RETENTIONS = [
  { id:1, name:'Daily Retention',  daily_copies:7,  weekly_copies:4,  monthly_copies:3,  yearly_copies:1, is_active:true,  description:'Standard GFS retention' },
  { id:2, name:'Extended Archive', daily_copies:30, weekly_copies:12, monthly_copies:12, yearly_copies:5, is_active:true,  description:'Extended retention for compliance' },
];
const FB_DASH = {
  total_backups:248, successful_backups:231, failed_backups:12, running_backups:1,
  total_size_human:'42.8 GB', last_backup_status:'completed',
  next_backup_in:'2h 15m', success_rate:93.1, storage_used_percent:28.4, pending_backups:4,
};

// ─────────────────────────────────────────────────────────────
// ICONS
// ─────────────────────────────────────────────────────────────
const I = {
  Db:       <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>,
  Shield:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  Clock:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  Storage:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>,
  Refresh:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>,
  Play:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  Trash:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>,
  Check:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
  Plus:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  Edit:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  Download: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  Restore:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg>,
  Log:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
  Heart:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>,
  Copy:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>,
  Cancel:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  Wifi:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>,
  Run:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  Alert:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><triangle points="10.29 3.86 1.82 18 2 18 22 18 21.71 18"/><path d="M10.29 3.86L1.82 18 2 18h20l-.29-.14z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  X:        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  Chart:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  Tool:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>,
};

// ─────────────────────────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────────────────────────
function Toast({ toasts }) {
  return (
    <div className="bk-toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`bk-toast bk-toast--${t.type}`}>
          <span className="bk-toast__icon">{t.type==='success'?'✓':t.type==='error'?'✕':'ℹ'}</span>
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// GLASS MODAL — reusable
// ─────────────────────────────────────────────────────────────
function Modal({ title, subtitle, icon, onClose, children, wide }) {
  return (
    <div className="bk-overlay" onClick={onClose}>
      <div className={`bk-modal bk-glass${wide?' bk-modal--wide':''}`} onClick={e=>e.stopPropagation()}>
        <div className="bk-modal__header">
          <div className="bk-modal__header-left">
            {icon && <div className="bk-modal__icon">{icon}</div>}
            <div>
              {subtitle && <div className="bk-modal__subtitle">{subtitle}</div>}
              <div className="bk-modal__title">{title}</div>
            </div>
          </div>
          <button className="bk-icon-btn" onClick={onClose}>{I.X}</button>
        </div>
        <div className="bk-modal__body">{children}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// FIELD
// ─────────────────────────────────────────────────────────────
function Field({ label, field, form, setForm, type='text', options, placeholder, required, error, disabled }) {
  return (
    <div className="bk-field">
      <label className="bk-field__label">{label}{required&&<span className="bk-field__req">*</span>}</label>
      {options ? (
        <select disabled={disabled} className={`bk-field__input bk-field__select${error?' bk-field__input--err':''}`}
          value={form[field]||''} onChange={e=>setForm(p=>({...p,[field]:e.target.value}))}>
          {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input disabled={disabled} type={type} className={`bk-field__input${error?' bk-field__input--err':''}`}
          value={form[field]||''} placeholder={placeholder}
          onChange={e=>setForm(p=>({...p,[field]:type==='number'?Number(e.target.value):e.target.value}))} />
      )}
      {error&&<span className="bk-field__error">{error}</span>}
    </div>
  );
}
function FieldTextarea({ label, field, form, setForm, placeholder }) {
  return (
    <div className="bk-field">
      <label className="bk-field__label">{label}</label>
      <textarea className="bk-field__input bk-field__textarea" value={form[field]||''} placeholder={placeholder}
        onChange={e=>setForm(p=>({...p,[field]:e.target.value}))} rows={3}/>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// DELETE CONFIRM
// ─────────────────────────────────────────────────────────────
function DeleteConfirm({ name, onConfirm, onCancel }) {
  return (
    <div className="bk-overlay" onClick={onCancel}>
      <div className="bk-confirm bk-glass" onClick={e=>e.stopPropagation()}>
        <div className="bk-confirm__icon">🗑️</div>
        <h3 className="bk-confirm__title">Delete?</h3>
        <p className="bk-confirm__body"><strong>"{name}"</strong> মুছে ফেলা হবে।</p>
        <div className="bk-confirm__actions">
          <button className="bk-btn bk-btn--danger" onClick={onConfirm}>Delete</button>
          <button className="bk-btn bk-btn--ghost" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// LOGS MODAL
// ─────────────────────────────────────────────────────────────
function LogsModal({ backup, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sf(() => API.backupLogs(backup.id)).then(r => {
      setLogs(Array.isArray(r) ? r : (r?.data || r?.results || []));
      setLoading(false);
    });
  }, [backup.id]);

  return (
    <Modal title={`Logs — ${backup.name}`} subtitle="Backup Activity" icon={I.Log} onClose={onClose} wide>
      {loading ? (
        <div className="bk-loading"><div className="bk-spinner"/>Loading logs...</div>
      ) : logs.length === 0 ? (
        <div className="bk-empty">No logs found</div>
      ) : (
        <div className="bk-log-list">
          {logs.map((log,i) => (
            <div key={i} className={`bk-log-item bk-log--${log.level||'info'}`}>
              <div className="bk-log-meta">
                <span className={`bk-badge bk-badge--${log.level==='error'?'red':log.level==='warning'?'amber':'green'}`}>
                  {(log.level||'INFO').toUpperCase()}
                </span>
                <span className="bk-log-time">{log.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}</span>
              </div>
              <div className="bk-log-msg">{log.message}</div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// START BACKUP MODAL
// ─────────────────────────────────────────────────────────────
function StartBackupModal({ onClose, onSuccess, toast }) {
  const [form, setForm] = useState({ backup_type:'full', storage_type:'local', encryption_type:'aes256', compression_type:'gzip', retention_days:30, description:'' });
  const [saving, setSaving] = useState(false);

  const handle = async () => {
    setSaving(true);
    const res = await sf(() => API.startBackup({ ...form, tables:['*'] }));
    setSaving(false);
    if (res) { toast('Backup started!','success'); onSuccess(); onClose(); }
    else toast('Failed to start backup','error');
  };

  return (
    <Modal title="Start New Backup" subtitle="Manual Trigger" icon={I.Play} onClose={onClose} wide>
      <div className="bk-form-grid">
        <div className="bk-form-row">
          <Field label="Backup Type" field="backup_type" form={form} setForm={setForm}
            options={[{value:'full',label:'Full'},{value:'incremental',label:'Incremental'},{value:'differential',label:'Differential'},{value:'delta',label:'Delta'}]} />
          <Field label="Storage Type" field="storage_type" form={form} setForm={setForm}
            options={[{value:'local',label:'Local'},{value:'s3',label:'AWS S3'},{value:'ftp',label:'FTP'},{value:'azure',label:'Azure'},{value:'gcs',label:'GCS'}]} />
        </div>
        <div className="bk-form-row">
          <Field label="Encryption" field="encryption_type" form={form} setForm={setForm}
            options={[{value:'aes256',label:'AES-256'},{value:'aes128',label:'AES-128'},{value:'none',label:'None'}]} />
          <Field label="Compression" field="compression_type" form={form} setForm={setForm}
            options={[{value:'gzip',label:'GZip'},{value:'lz4',label:'LZ4'},{value:'zstd',label:'ZSTD'},{value:'none',label:'None'}]} />
        </div>
        <Field label="Retention Days" field="retention_days" form={form} setForm={setForm} type="number" />
        <FieldTextarea label="Description" field="description" form={form} setForm={setForm} placeholder="Optional description..." />
        <div className="bk-modal__footer">
          <button className="bk-btn bk-btn--primary" onClick={handle} disabled={saving}>
            {saving && <span className="bk-spin">⟳</span>}{saving?'Starting...':'Start Backup'}
          </button>
          <button className="bk-btn bk-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// RESTORE MODAL
// ─────────────────────────────────────────────────────────────
function RestoreModal({ backup, onClose, toast, onSuccess }) {
  const [form, setForm] = useState({ backup_id: backup.id, restore_type:'full', enable_maintenance:false });
  const [saving, setSaving] = useState(false);

  const handle = async () => {
    setSaving(true);
    const res = await sf(() => API.restoreBackup(form));
    setSaving(false);
    if (res) { toast('Restore initiated!','success'); onSuccess(); onClose(); }
    else toast('Restore failed','error');
  };

  return (
    <Modal title={`Restore — ${backup.name}`} subtitle="Point-in-time Recovery" icon={I.Restore} onClose={onClose}>
      <div className="bk-form-grid">
        <div className="bk-restore-warn bk-glass-inner">
          ⚠️ This will restore the database to the state of this backup. Proceed with caution.
        </div>
        <Field label="Restore Type" field="restore_type" form={form} setForm={setForm}
          options={[{value:'full',label:'Full Restore'},{value:'partial',label:'Partial Restore'},{value:'schema_only',label:'Schema Only'}]} />
        <div className="bk-field">
          <label className="bk-field__label">
            <input type="checkbox" checked={form.enable_maintenance} onChange={e=>setForm(p=>({...p,enable_maintenance:e.target.checked}))} />
            {' '}Enable Maintenance Mode during restore
          </label>
        </div>
        <div className="bk-modal__footer">
          <button className="bk-btn bk-btn--danger" onClick={handle} disabled={saving}>
            {saving?<><span className="bk-spin">⟳</span> Restoring...</>:<>{I.Restore} Restore Now</>}
          </button>
          <button className="bk-btn bk-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// SCHEDULE MODAL — Create / Edit
// ─────────────────────────────────────────────────────────────
function ScheduleModal({ schedule, onClose, toast, onSuccess }) {
  const isEdit = !!schedule;
  const [form, setForm] = useState(isEdit ? {
    name: schedule.name||'', schedule_type: schedule.schedule_type||'daily',
    backup_type: schedule.backup_type||'full', retention_days: schedule.retention_days||30,
    description: schedule.description||'',
  } : { name:'', schedule_type:'daily', backup_type:'full', retention_days:30, description:'' });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const handle = async () => {
    if (!form.name.trim()) { setErrors({name:'Name required'}); return; }
    setSaving(true);
    const res = isEdit
      ? await sf(() => API.updateSchedule(schedule.id, form))
      : await sf(() => API.createSchedule(form));
    setSaving(false);
    if (res) { toast(isEdit?'Schedule updated!':'Schedule created!','success'); onSuccess(); onClose(); }
    else toast(isEdit?'Update failed':'Create failed','error');
  };

  return (
    <Modal title={isEdit?`Edit — ${schedule.name}`:'New Schedule'} subtitle="Backup Schedule" icon={I.Clock} onClose={onClose} wide>
      <div className="bk-form-grid">
        <div className="bk-form-row">
          <Field label="Schedule Name *" field="name" form={form} setForm={setForm} error={errors.name} placeholder="e.g. Daily Full Backup" required />
          <Field label="Frequency" field="schedule_type" form={form} setForm={setForm}
            options={[{value:'hourly',label:'Hourly'},{value:'daily',label:'Daily'},{value:'weekly',label:'Weekly'},{value:'monthly',label:'Monthly'}]} />
        </div>
        <div className="bk-form-row">
          <Field label="Backup Type" field="backup_type" form={form} setForm={setForm}
            options={[{value:'full',label:'Full'},{value:'incremental',label:'Incremental'},{value:'differential',label:'Differential'},{value:'delta',label:'Delta'}]} />
          <Field label="Retention Days" field="retention_days" form={form} setForm={setForm} type="number" />
        </div>
        <FieldTextarea label="Description" field="description" form={form} setForm={setForm} placeholder="Schedule description..." />
        <div className="bk-modal__footer">
          <button className="bk-btn bk-btn--primary" onClick={handle} disabled={saving}>
            {saving&&<span className="bk-spin">⟳</span>}{saving?'Saving...':(isEdit?'Update Schedule':'Create Schedule')}
          </button>
          <button className="bk-btn bk-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// STORAGE MODAL — Create / Edit
// ─────────────────────────────────────────────────────────────
function StorageModal({ storage, onClose, toast, onSuccess }) {
  const isEdit = !!storage;
  const [form, setForm] = useState(isEdit ? {
    name: storage.name||'', storage_type: storage.storage_type||'local',
    host: storage.host||'', port: storage.port||'', path: storage.path||'',
    access_key: '', secret_key: '', description: storage.description||'',
  } : { name:'', storage_type:'local', host:'', port:'', path:'', access_key:'', secret_key:'', description:'' });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const handle = async () => {
    if (!form.name.trim()) { setErrors({name:'Name required'}); return; }
    setSaving(true);
    const payload = { ...form };
    if (!payload.access_key) delete payload.access_key;
    if (!payload.secret_key) delete payload.secret_key;
    const res = isEdit
      ? await sf(() => API.updateStorage(storage.id, payload))
      : await sf(() => API.createStorage(payload));
    setSaving(false);
    if (res) { toast(isEdit?'Storage updated!':'Storage created!','success'); onSuccess(); onClose(); }
    else toast(isEdit?'Update failed':'Create failed','error');
  };

  return (
    <Modal title={isEdit?`Edit — ${storage.name}`:'New Storage Location'} subtitle="Storage Configuration" icon={I.Storage} onClose={onClose} wide>
      <div className="bk-form-grid">
        <div className="bk-form-row">
          <Field label="Location Name *" field="name" form={form} setForm={setForm} error={errors.name} placeholder="e.g. AWS S3 Primary" required />
          <Field label="Storage Type" field="storage_type" form={form} setForm={setForm}
            options={[{value:'local',label:'Local Disk'},{value:'s3',label:'AWS S3'},{value:'ftp',label:'FTP'},{value:'sftp',label:'SFTP'},{value:'azure',label:'Azure Blob'},{value:'gcs',label:'GCS'}]} />
        </div>
        <div className="bk-form-row">
          <Field label="Host / Endpoint" field="host" form={form} setForm={setForm} placeholder="s3.amazonaws.com" />
          <Field label="Port" field="port" form={form} setForm={setForm} type="number" placeholder="21" />
        </div>
        <Field label="Path / Bucket" field="path" form={form} setForm={setForm} placeholder="/backups or bucket-name" />
        <div className="bk-cred-section bk-glass-inner">
          <div className="bk-cred-title">🔐 Credentials {isEdit&&<span>(blank = keep existing)</span>}</div>
          <div className="bk-form-row">
            <Field label="Access Key / Username" field="access_key" form={form} setForm={setForm} type="password" placeholder="••••••••" />
            <Field label="Secret Key / Password"  field="secret_key" form={form} setForm={setForm} type="password" placeholder="••••••••" />
          </div>
        </div>
        <FieldTextarea label="Description" field="description" form={form} setForm={setForm} placeholder="Storage description..." />
        <div className="bk-modal__footer">
          <button className="bk-btn bk-btn--primary" onClick={handle} disabled={saving}>
            {saving&&<span className="bk-spin">⟳</span>}{saving?'Saving...':(isEdit?'Update Storage':'Add Storage')}
          </button>
          <button className="bk-btn bk-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// RETENTION MODAL — Create / Edit
// ─────────────────────────────────────────────────────────────
function RetentionModal({ retention, onClose, toast, onSuccess }) {
  const isEdit = !!retention;
  const [form, setForm] = useState(isEdit ? {
    name: retention.name||'', daily_copies: retention.daily_copies||7,
    weekly_copies: retention.weekly_copies||4, monthly_copies: retention.monthly_copies||3,
    yearly_copies: retention.yearly_copies||1, description: retention.description||'',
  } : { name:'', daily_copies:7, weekly_copies:4, monthly_copies:3, yearly_copies:1, description:'' });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const handle = async () => {
    if (!form.name.trim()) { setErrors({name:'Name required'}); return; }
    setSaving(true);
    const res = isEdit
      ? await sf(() => API.updateRetention(retention.id, form))
      : await sf(() => API.createRetention(form));
    setSaving(false);
    if (res) { toast(isEdit?'Policy updated!':'Policy created!','success'); onSuccess(); onClose(); }
    else toast(isEdit?'Update failed':'Create failed','error');
  };

  return (
    <Modal title={isEdit?`Edit — ${retention.name}`:'New Retention Policy'} subtitle="GFS Retention" icon={I.Shield} onClose={onClose} wide>
      <div className="bk-form-grid">
        <Field label="Policy Name *" field="name" form={form} setForm={setForm} error={errors.name} placeholder="e.g. Standard GFS" required />
        <div className="bk-form-row">
          <Field label="Daily Copies"   field="daily_copies"   form={form} setForm={setForm} type="number" />
          <Field label="Weekly Copies"  field="weekly_copies"  form={form} setForm={setForm} type="number" />
        </div>
        <div className="bk-form-row">
          <Field label="Monthly Copies" field="monthly_copies" form={form} setForm={setForm} type="number" />
          <Field label="Yearly Copies"  field="yearly_copies"  form={form} setForm={setForm} type="number" />
        </div>
        <FieldTextarea label="Description" field="description" form={form} setForm={setForm} placeholder="Policy description..." />
        <div className="bk-modal__footer">
          <button className="bk-btn bk-btn--primary" onClick={handle} disabled={saving}>
            {saving&&<span className="bk-spin">⟳</span>}{saving?'Saving...':(isEdit?'Update Policy':'Create Policy')}
          </button>
          <button className="bk-btn bk-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────
const fmtDate = d => {
  if (!d) return '—';
  try { return new Date(d).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
  catch { return d; }
};
const statusCls = s => {
  if (!s) return '';
  const v = s.toLowerCase();
  if (v==='completed') return 'green';
  if (v==='failed'||v==='cancelled') return 'red';
  if (v==='running') return 'amber';
  if (v==='pending') return 'blue';
  return '';
};
const typeCls = t => {
  if (!t) return '';
  const v = t.toLowerCase();
  if (v==='full') return 'blue';
  if (v==='incremental') return 'green';
  if (v==='differential') return 'amber';
  if (v==='delta') return 'purple';
  return '';
};

// ─────────────────────────────────────────────────────────────
// STAT CARD
// ─────────────────────────────────────────────────────────────
function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="bk-stat-card bk-glass" style={{'--accent':accent}}>
      <div className="bk-stat-card__icon">{icon}</div>
      <div className="bk-stat-card__body">
        <div className="bk-stat-card__value">{value}</div>
        <div className="bk-stat-card__label">{label}</div>
        <div className="bk-stat-card__sub">{sub}</div>
      </div>
      <div className="bk-stat-card__glow"/>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────
export default function Backup() {
  const [loading,      setLoading]     = useState(false);
  const [apiOnline,    setApiOnline]   = useState(false);
  const [toasts,       setToasts]      = useState([]);

  const [backups,      setBackups]     = useState(FB_BACKUPS);
  const [schedules,    setSchedules]   = useState(FB_SCHEDULES);
  const [storages,     setStorages]    = useState(FB_STORAGES);
  const [retentions,   setRetentions]  = useState(FB_RETENTIONS);
  const [dash,         setDash]        = useState(FB_DASH);
  const [metrics,      setMetrics]     = useState(null);
  const [sysStatus,    setSysStatus]   = useState(null);
  const [maintenance,  setMaintenance] = useState(false);

  // Modal states
  const [modal,        setModal]       = useState(null); // {type, data}
  const [deleteTarget, setDeleteTarget]= useState(null); // {type, item}

  // Active tab
  const [tab, setTab] = useState('backups');

  // Loading states for actions
  const [actionLoading, setActionLoading] = useState({});
  const setAL = (key, val) => setActionLoading(p=>({...p,[key]:val}));

  // ── TOAST ─────────────────────────────────────────────────
  const toast = useCallback((message, type='success') => {
    const id = Date.now();
    setToasts(p=>[...p,{id,message,type}]);
    setTimeout(()=>setToasts(p=>p.filter(t=>t.id!==id)), 3500);
  }, []);

  // ── FETCH ALL ─────────────────────────────────────────────
  const fetchAll = useCallback(async (showLoader=false) => {
    if (showLoader) setLoading(true);
    const [bkR, schR, stR, retR, dashR, metR, statR] = await Promise.all([
      sf(API.backups), sf(API.schedules), sf(API.storages), sf(API.retentions),
      sf(API.dashboard), sf(API.metrics), sf(API.backupStatus),
    ]);
    let ok = false;
    const bkL = exList(bkR); if (bkL.length) { setBackups(bkL); ok=true; }
    const schL = exList(schR); if (schL.length) { setSchedules(schL); ok=true; }
    const stL = exList(stR); if (stL.length) { setStorages(stL); ok=true; }
    const retL = exList(retR); if (retL.length) { setRetentions(retL); ok=true; }
    if (dashR) { setDash(p=>({...p,...exObj(dashR)})); ok=true; }
    if (metR)  { setMetrics(exObj(metR)); ok=true; }
    if (statR) { const s=exObj(statR); setSysStatus(s); setMaintenance(s.maintenance_mode||false); ok=true; }
    setApiOnline(ok);
    if (showLoader) setLoading(false);
  }, []);

  useEffect(() => { fetchAll(true); }, [fetchAll]);

  // ── BACKUP ACTIONS ────────────────────────────────────────
  const handleVerify = async (b) => {
    setAL(`verify_${b.id}`, true);
    const r = await sf(() => API.verifyBackup(b.id));
    setAL(`verify_${b.id}`, false);
    if (r) { toast(`"${b.name}" verified ✓`,'success'); fetchAll(); }
    else toast('Verification failed','error');
  };

  const handleHealthCheck = async (b) => {
    setAL(`health_${b.id}`, true);
    const r = await sf(() => API.healthCheck(b.id));
    setAL(`health_${b.id}`, false);
    if (r) { toast(`Health score: ${r.health_score||'—'}`,'success'); fetchAll(); }
    else toast('Health check failed','error');
  };

  const handleDownload = (b) => {
    window.open(`${BASE}/backups/${b.id}/download/`, '_blank');
    toast(`Downloading "${b.name}"...`,'info');
  };

  const handleRedundant = async (b) => {
    setAL(`red_${b.id}`, true);
    const r = await sf(() => API.redundantCopy(b.id));
    setAL(`red_${b.id}`, false);
    if (r?.success) toast(`${r.copies_created} redundant copies created!`,'success');
    else toast(r?.message||'Failed','error');
  };

  const handleCancelBackup = async (b) => {
    setAL(`cancel_${b.id}`, true);
    const r = await sf(() => API.cancelBackup(b.id));
    setAL(`cancel_${b.id}`, false);
    if (r) { toast(`"${b.name}" cancelled`,'info'); fetchAll(); }
    else toast('Cancel failed','error');
  };

  const handleDeleteBackup = async (b) => {
    const r = await sf(() => API.deleteBackup(b.id));
    if (r||r===null) { setBackups(p=>p.filter(x=>x.id!==b.id)); toast(`"${b.name}" deleted`,'success'); }
    else toast('Delete failed','error');
    setDeleteTarget(null);
  };

  const handleCleanup = async () => {
    toast('Running cleanup...','info');
    const r = await sf(API.cleanup);
    if (r) { toast('Cleanup complete!','success'); fetchAll(); }
    else toast('Cleanup failed','error');
  };

  // ── SCHEDULE ACTIONS ──────────────────────────────────────
  const handleToggleSchedule = async (s) => {
    setAL(`tog_${s.id}`, true);
    const r = await sf(() => API.toggleSchedule(s.id));
    setAL(`tog_${s.id}`, false);
    if (r) { setSchedules(p=>p.map(x=>x.id===s.id?{...x,is_active:r.is_active}:x)); toast(r.message,'success'); }
    else toast('Toggle failed','error');
  };

  const handleRunNow = async (s) => {
    setAL(`run_${s.id}`, true);
    const r = await sf(() => API.runScheduleNow(s.id));
    setAL(`run_${s.id}`, false);
    if (r?.success) { toast(`"${s.name}" started!`,'success'); fetchAll(); }
    else toast('Run failed','error');
  };

  const handleDeleteSchedule = async (s) => {
    const r = await sf(() => API.deleteSchedule(s.id));
    if (r||r===null) { setSchedules(p=>p.filter(x=>x.id!==s.id)); toast(`"${s.name}" deleted`,'success'); }
    else toast('Delete failed','error');
    setDeleteTarget(null);
  };

  // ── STORAGE ACTIONS ───────────────────────────────────────
  const handleTestConnection = async (st) => {
    setAL(`conn_${st.id}`, true);
    const r = await sf(() => API.testConnection(st.id));
    setAL(`conn_${st.id}`, false);
    if (r?.success) toast(`"${st.name}" connected ✓`,'success');
    else toast(`Connection failed: ${r?.message||'error'}`,'error');
    fetchAll();
  };

  const handleDeleteStorage = async (st) => {
    const r = await sf(() => API.deleteStorage(st.id));
    if (r||r===null) { setStorages(p=>p.filter(x=>x.id!==st.id)); toast(`"${st.name}" deleted`,'success'); }
    else toast('Delete failed','error');
    setDeleteTarget(null);
  };

  // ── RETENTION ACTIONS ─────────────────────────────────────
  const handleExecuteRetention = async (r) => {
    setAL(`exec_${r.id}`, true);
    const res = await sf(() => API.executeRetention(r.id));
    setAL(`exec_${r.id}`, false);
    if (res?.success) toast(`"${r.name}" executing...`,'success');
    else toast('Execution failed','error');
  };

  const handleDeleteRetention = async (r) => {
    const res = await sf(() => API.deleteRetention(r.id));
    if (res||res===null) { setRetentions(p=>p.filter(x=>x.id!==r.id)); toast(`"${r.name}" deleted`,'success'); }
    else toast('Delete failed','error');
    setDeleteTarget(null);
  };

  // ── MAINTENANCE ───────────────────────────────────────────
  const handleMaintenance = async () => {
    const r = await sf(() => API.maintenance({ enable:!maintenance, duration_hours:1 }));
    if (r?.success) { setMaintenance(!maintenance); toast(r.message,'info'); }
    else toast('Maintenance toggle failed','error');
  };

  const successRate = () => {
    const t = dash.total_backups||1;
    return Math.min(100, ((dash.successful_backups||0)/t)*100);
  };

  // ─────────────────────────────────────────────────────────
  const TABS = [
    { id:'backups',    label:'Backups',    icon:I.Db      },
    { id:'schedules',  label:'Schedules',  icon:I.Clock   },
    { id:'storages',   label:'Storage',    icon:I.Storage },
    { id:'retentions', label:'Retention',  icon:I.Shield  },
    { id:'metrics',    label:'Metrics',    icon:I.Chart   },
  ];

  return (
    <div className="bk-root">
      {/* Ambient orbs */}
      <div className="bk-orb bk-orb--1"/>
      <div className="bk-orb bk-orb--2"/>
      <div className="bk-orb bk-orb--3"/>

      <div className="bk-container">

        {/* ── PAGE HEADER ─────────────────────────────────── */}
        <header className="bk-page-header">
          <div className="bk-page-header__left">
            <div className="bk-page-header__eyebrow">Disaster Recovery System</div>
            <h1 className="bk-page-header__title">Backup Center</h1>
            <p className="bk-page-header__sub">
              <span className={`bk-status-dot ${apiOnline?'green':'amber'}`}/>
              {apiOnline?'API Connected':'Offline Mode'}
              {maintenance && <span className="bk-maintenance-chip">⚠️ MAINTENANCE</span>}
              {loading && <span className="bk-loading-chip">Syncing…</span>}
            </p>
          </div>
          <div className="bk-page-header__actions">
            <button className={`bk-btn bk-btn--ghost${maintenance?' bk-btn--amber':''}`} onClick={handleMaintenance}>
              {I.Tool} {maintenance?'Disable Maintenance':'Maintenance Mode'}
            </button>
            <button className="bk-btn bk-btn--ghost" onClick={handleCleanup}>{I.Trash} Cleanup</button>
            <button className="bk-btn bk-btn--ghost" onClick={()=>fetchAll(true)}>
              <span className={loading?'bk-spin':''}>{I.Refresh}</span> Refresh
            </button>
            <button className="bk-btn bk-btn--primary" onClick={()=>setModal({type:'startBackup'})}>
              {I.Play} Start Backup
            </button>
          </div>
        </header>

        {/* ── STAT CARDS ───────────────────────────────────── */}
        <div className="bk-stats-grid">
          <StatCard icon={I.Db}      label="Total Backups"  value={dash.total_backups||0}                            sub="all time"                                         accent="#6366f1"/>
          <StatCard icon={I.Check}   label="Successful"     value={dash.successful_backups||0}                       sub={`${(dash.success_rate||0).toFixed(1)}% rate`}     accent="#10b981"/>
          <StatCard icon={I.Cancel}  label="Failed"         value={dash.failed_backups||0}                           sub="needs attention"                                  accent="#ef4444"/>
          <StatCard icon={I.Storage} label="Total Size"     value={dash.total_size_human||'—'}                       sub={`${(dash.storage_used_percent||0).toFixed(1)}% used`} accent="#f59e0b"/>
          <StatCard icon={I.Play}    label="Running"        value={sysStatus?.running||dash.running_backups||0}      sub="in progress"                                      accent="#06b6d4"/>
          <StatCard icon={I.Clock}   label="Next Backup"    value={dash.next_backup_in||'—'}                         sub="scheduled"                                        accent="#8b5cf6"/>
        </div>

        {/* ── SUCCESS RATE BAR ─────────────────────────────── */}
        <div className="bk-rate-bar bk-glass">
          <div className="bk-rate-bar__labels">
            <span>Success Rate</span>
            <span style={{color:'#10b981'}}>{successRate().toFixed(1)}%</span>
          </div>
          <div className="bk-progress-track">
            <div className="bk-progress-fill" style={{width:`${successRate()}%`, background:'#10b981'}}/>
          </div>
        </div>

        {/* ── TABS ─────────────────────────────────────────── */}
        <div className="bk-tabs bk-glass">
          {TABS.map(t=>(
            <button key={t.id} className={`bk-tab${tab===t.id?' bk-tab--active':''}`} onClick={()=>setTab(t.id)}>
              <span className="bk-tab__icon">{t.icon}</span>
              {t.label}
              {t.id==='backups'    && <span className="bk-tab__count">{backups.length}</span>}
              {t.id==='schedules'  && <span className="bk-tab__count">{schedules.length}</span>}
              {t.id==='storages'   && <span className="bk-tab__count">{storages.length}</span>}
              {t.id==='retentions' && <span className="bk-tab__count">{retentions.length}</span>}
            </button>
          ))}
        </div>

        {/* ══════════════════════════════════════════════════ */}
        {/* TAB: BACKUPS                                       */}
        {/* ══════════════════════════════════════════════════ */}
        {tab==='backups' && (
          <div className="bk-panel bk-glass">
            <div className="bk-panel__header">
              <div className="bk-panel__title">{I.Db} Backup Records</div>
              <div className="bk-panel__actions">
                <span className="bk-live-chip">LIVE</span>
                <span className="bk-count-chip">{backups.length} backups</span>
                <button className="bk-btn bk-btn--primary bk-btn--sm" onClick={()=>setModal({type:'startBackup'})}>
                  {I.Plus} New Backup
                </button>
              </div>
            </div>

            {loading ? (
              <div className="bk-loading"><div className="bk-spinner"/>Loading backups...</div>
            ) : (
              <div className="bk-table-wrap">
                <table className="bk-table">
                  <thead>
                    <tr>
                      <th>ID</th><th>Name</th><th>Type</th><th>Database</th>
                      <th>Size</th><th>Duration</th><th>Status</th>
                      <th>Health</th><th>Security</th><th>Date</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backups.map(b => (
                      <tr key={b.id} className="bk-row">
                        <td className="bk-td-mono">{b.backup_id||`#${b.id}`}</td>
                        <td>
                          <div className="bk-name-cell">
                            <div className="bk-name-cell__title">{b.name||'—'}</div>
                            <div className="bk-name-cell__sub">{b.storage_type?.toUpperCase()}</div>
                          </div>
                        </td>
                        <td><span className={`bk-badge bk-badge--${typeCls(b.backup_type)}`}>{(b.backup_type_display||b.backup_type||'—').toUpperCase()}</span></td>
                        <td className="bk-td-sub">{b.database_name||'—'}</td>
                        <td className="bk-td-val">{b.file_size_human||'—'}</td>
                        <td className="bk-td-sub">{b.duration_human||'—'}</td>
                        <td><span className={`bk-badge bk-badge--${statusCls(b.status)}`}>{(b.status_display||b.status||'—').toUpperCase()}</span></td>
                        <td>
                          <div className="bk-health-cell">
                            <span className={`bk-health-dot ${b.is_healthy?'green':'red'}`}/>
                            <span className="bk-td-sub">{b.health_score||'—'}%</span>
                          </div>
                        </td>
                        <td>
                          <div className="bk-sec-cell">
                            {b.is_encrypted && <span className="bk-badge bk-badge--green">ENC</span>}
                            {b.compression_type&&b.compression_type!=='none'&&<span className="bk-badge bk-badge--blue">{b.compression_type.toUpperCase()}</span>}
                          </div>
                        </td>
                        <td className="bk-td-sub">{fmtDate(b.created_at||b.start_time)}</td>
                        <td>
                          <div className="bk-action-group">
                            {/* Verify */}
                            <button className="bk-action-btn" title="Verify Integrity"
                              onClick={()=>handleVerify(b)} disabled={actionLoading[`verify_${b.id}`]}>
                              {actionLoading[`verify_${b.id}`]?<span className="bk-spin">⟳</span>:I.Check}
                            </button>
                            {/* Health Check */}
                            <button className="bk-action-btn" title="Health Check"
                              onClick={()=>handleHealthCheck(b)} disabled={actionLoading[`health_${b.id}`]}>
                              {actionLoading[`health_${b.id}`]?<span className="bk-spin">⟳</span>:I.Heart}
                            </button>
                            {/* Logs */}
                            <button className="bk-action-btn" title="View Logs"
                              onClick={()=>setModal({type:'logs',data:b})}>
                              {I.Log}
                            </button>
                            {/* Download */}
                            <button className="bk-action-btn" title="Download" onClick={()=>handleDownload(b)}>
                              {I.Download}
                            </button>
                            {/* Restore */}
                            <button className="bk-action-btn bk-action-btn--restore" title="Restore"
                              onClick={()=>setModal({type:'restore',data:b})}>
                              {I.Restore}
                            </button>
                            {/* Redundant copy */}
                            <button className="bk-action-btn" title="Create Redundant Copy"
                              onClick={()=>handleRedundant(b)} disabled={actionLoading[`red_${b.id}`]}>
                              {actionLoading[`red_${b.id}`]?<span className="bk-spin">⟳</span>:I.Copy}
                            </button>
                            {/* Cancel if running */}
                            {b.status==='running' && (
                              <button className="bk-action-btn bk-action-btn--danger" title="Cancel"
                                onClick={()=>handleCancelBackup(b)} disabled={actionLoading[`cancel_${b.id}`]}>
                                {actionLoading[`cancel_${b.id}`]?<span className="bk-spin">⟳</span>:I.Cancel}
                              </button>
                            )}
                            {/* Delete */}
                            <button className="bk-action-btn bk-action-btn--danger" title="Delete"
                              onClick={()=>setDeleteTarget({type:'backup',item:b})}>
                              {I.Trash}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {backups.length===0 && <div className="bk-empty">No backups found</div>}
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════ */}
        {/* TAB: SCHEDULES                                     */}
        {/* ══════════════════════════════════════════════════ */}
        {tab==='schedules' && (
          <div className="bk-panel bk-glass">
            <div className="bk-panel__header">
              <div className="bk-panel__title">{I.Clock} Backup Schedules</div>
              <div className="bk-panel__actions">
                <span className="bk-count-chip">{schedules.filter(s=>s.is_active).length} active</span>
                <button className="bk-btn bk-btn--primary bk-btn--sm" onClick={()=>setModal({type:'createSchedule'})}>
                  {I.Plus} New Schedule
                </button>
              </div>
            </div>
            <div className="bk-table-wrap">
              <table className="bk-table">
                <thead>
                  <tr><th>Name</th><th>Frequency</th><th>Type</th><th>Retention</th><th>Next Run</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {schedules.map(s=>(
                    <tr key={s.id} className="bk-row">
                      <td>
                        <div className="bk-name-cell">
                          <div className="bk-name-cell__title">{s.name}</div>
                          <div className="bk-name-cell__sub">{s.description||''}</div>
                        </div>
                      </td>
                      <td><span className="bk-badge bk-badge--blue">{(s.schedule_type||'daily').toUpperCase()}</span></td>
                      <td><span className={`bk-badge bk-badge--${typeCls(s.backup_type)}`}>{(s.backup_type||'—').toUpperCase()}</span></td>
                      <td className="bk-td-sub">{s.retention_days}d</td>
                      <td className="bk-td-sub">{fmtDate(s.next_run)}</td>
                      <td>
                        <span className={`bk-badge bk-badge--${s.is_active?'green':'red'}`}>
                          {s.is_active?'ACTIVE':'PAUSED'}
                        </span>
                      </td>
                      <td>
                        <div className="bk-action-group">
                          <button className="bk-action-btn bk-action-btn--edit" title="Edit" onClick={()=>setModal({type:'editSchedule',data:s})}>{I.Edit}</button>
                          <button className="bk-action-btn" title={s.is_active?'Pause':'Activate'}
                            onClick={()=>handleToggleSchedule(s)} disabled={actionLoading[`tog_${s.id}`]}>
                            {actionLoading[`tog_${s.id}`]?<span className="bk-spin">⟳</span>:(s.is_active?'⏸':'▶')}
                          </button>
                          <button className="bk-action-btn bk-action-btn--restore" title="Run Now"
                            onClick={()=>handleRunNow(s)} disabled={actionLoading[`run_${s.id}`]}>
                            {actionLoading[`run_${s.id}`]?<span className="bk-spin">⟳</span>:I.Run}
                          </button>
                          <button className="bk-action-btn bk-action-btn--danger" title="Delete" onClick={()=>setDeleteTarget({type:'schedule',item:s})}>{I.Trash}</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {schedules.length===0 && <div className="bk-empty">No schedules found</div>}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════ */}
        {/* TAB: STORAGE                                       */}
        {/* ══════════════════════════════════════════════════ */}
        {tab==='storages' && (
          <div className="bk-panel bk-glass">
            <div className="bk-panel__header">
              <div className="bk-panel__title">{I.Storage} Storage Locations</div>
              <div className="bk-panel__actions">
                <span className="bk-count-chip">{storages.filter(s=>s.is_connected).length} online</span>
                <button className="bk-btn bk-btn--primary bk-btn--sm" onClick={()=>setModal({type:'createStorage'})}>
                  {I.Plus} Add Storage
                </button>
              </div>
            </div>
            <div className="bk-storage-grid">
              {storages.map(st=>{
                const pct = st.used_percent||0;
                return (
                  <div key={st.id} className="bk-storage-card bk-glass-inner">
                    <div className="bk-storage-card__header">
                      <div>
                        <div className="bk-storage-card__name">{st.name}</div>
                        <div className="bk-storage-card__host">{st.host}</div>
                      </div>
                      <div className="bk-storage-card__badges">
                        <span className={`bk-badge bk-badge--${st.is_active&&st.is_connected?'green':st.is_active?'amber':'red'}`}>
                          {st.is_active&&st.is_connected?'ONLINE':st.is_active?'DISCONNECTED':'OFFLINE'}
                        </span>
                        <span className="bk-badge bk-badge--blue">{(st.storage_type||'—').toUpperCase()}</span>
                      </div>
                    </div>
                    <div className="bk-storage-stats">
                      {[['TOTAL',st.total_size_human||'—',null],['USED',st.used_size_human||'—',null],['FREE',st.available_size_human||'—','#10b981'],['USED %',pct>0?`${pct.toFixed(1)}%`:'—',pct>80?'#ef4444':pct>60?'#f59e0b':null]].map(([l,v,c])=>(
                        <div key={l} className="bk-sstat">
                          <div className="bk-sstat__label">{l}</div>
                          <div className="bk-sstat__val" style={c?{color:c}:{}}>{v}</div>
                        </div>
                      ))}
                    </div>
                    {pct>0 && (
                      <div className="bk-progress-track" style={{marginBottom:12}}>
                        <div className="bk-progress-fill" style={{width:`${pct}%`,background:pct>80?'#ef4444':pct>60?'#f59e0b':'#6366f1'}}/>
                      </div>
                    )}
                    <div className="bk-action-group">
                      <button className="bk-action-btn bk-action-btn--edit" title="Edit" onClick={()=>setModal({type:'editStorage',data:st})}>{I.Edit}</button>
                      <button className="bk-action-btn" title="Test Connection"
                        onClick={()=>handleTestConnection(st)} disabled={actionLoading[`conn_${st.id}`]}>
                        {actionLoading[`conn_${st.id}`]?<span className="bk-spin">⟳</span>:I.Wifi}
                      </button>
                      <button className="bk-action-btn bk-action-btn--danger" title="Delete" onClick={()=>setDeleteTarget({type:'storage',item:st})}>{I.Trash}</button>
                    </div>
                  </div>
                );
              })}
              {storages.length===0 && <div className="bk-empty">No storage locations found</div>}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════ */}
        {/* TAB: RETENTION                                     */}
        {/* ══════════════════════════════════════════════════ */}
        {tab==='retentions' && (
          <div className="bk-panel bk-glass">
            <div className="bk-panel__header">
              <div className="bk-panel__title">{I.Shield} Retention Policies</div>
              <div className="bk-panel__actions">
                <button className="bk-btn bk-btn--primary bk-btn--sm" onClick={()=>setModal({type:'createRetention'})}>
                  {I.Plus} New Policy
                </button>
              </div>
            </div>
            <div className="bk-retention-grid">
              {retentions.map(r=>(
                <div key={r.id} className="bk-retention-card bk-glass-inner">
                  <div className="bk-retention-card__header">
                    <div className="bk-retention-card__name">{r.name}</div>
                    <span className={`bk-badge bk-badge--${r.is_active?'green':'red'}`}>{r.is_active?'ACTIVE':'OFF'}</span>
                  </div>
                  {r.description && <div className="bk-retention-card__desc">{r.description}</div>}
                  <div className="bk-retention-rows">
                    {[['Daily Copies',r.daily_copies||0],['Weekly Copies',r.weekly_copies||0],['Monthly Copies',r.monthly_copies||0],['Yearly Copies',r.yearly_copies||0]].map(([l,v])=>(
                      <div key={l} className="bk-retention-row">
                        <span className="bk-retention-row__key">{l}</span>
                        <span className="bk-retention-row__val">{v} copies</span>
                      </div>
                    ))}
                  </div>
                  <div className="bk-action-group" style={{marginTop:12}}>
                    <button className="bk-action-btn bk-action-btn--edit" title="Edit" onClick={()=>setModal({type:'editRetention',data:r})}>{I.Edit}</button>
                    <button className="bk-action-btn bk-action-btn--restore" title="Execute Now"
                      onClick={()=>handleExecuteRetention(r)} disabled={actionLoading[`exec_${r.id}`]}>
                      {actionLoading[`exec_${r.id}`]?<span className="bk-spin">⟳</span>:I.Run}
                    </button>
                    <button className="bk-action-btn bk-action-btn--danger" title="Delete" onClick={()=>setDeleteTarget({type:'retention',item:r})}>{I.Trash}</button>
                  </div>
                </div>
              ))}
              {retentions.length===0 && <div className="bk-empty">No retention policies found</div>}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════ */}
        {/* TAB: METRICS                                       */}
        {/* ══════════════════════════════════════════════════ */}
        {tab==='metrics' && (
          <div className="bk-metrics-grid">
            {/* System Metrics */}
            <div className="bk-panel bk-glass">
              <div className="bk-panel__header">
                <div className="bk-panel__title">{I.Chart} System Metrics</div>
                <span className="bk-live-chip">LIVE</span>
              </div>
              <div className="bk-retention-rows">
                {metrics ? (
                  [
                    ['CPU Usage', typeof metrics.cpu_usage==='number'?`${metrics.cpu_usage.toFixed(1)}%`:metrics.cpu_usage||'—'],
                    ['Memory',    metrics.memory_usage?.percentage?`${metrics.memory_usage.percentage.toFixed(1)}%`:'—'],
                    ['Disk Used', metrics.disk_usage?.percentage?`${metrics.disk_usage.percentage.toFixed(1)}%`:'—'],
                    ['Net Sent',  metrics.network_usage?.bytes_sent?`${(metrics.network_usage.bytes_sent/1024/1024).toFixed(1)} MB`:'—'],
                    ['Net Recv',  metrics.network_usage?.bytes_recv?`${(metrics.network_usage.bytes_recv/1024/1024).toFixed(1)} MB`:'—'],
                  ].map(([l,v])=>(
                    <div key={l} className="bk-retention-row">
                      <span className="bk-retention-row__key">{l}</span>
                      <span className="bk-retention-row__val">{v}</span>
                    </div>
                  ))
                ) : (
                  [['CPU','24.5%'],['Memory','68.2%'],['Disk I/O','12 MB/s'],['Network','Stable'],['DB Connections','14/100']].map(([l,v])=>(
                    <div key={l} className="bk-retention-row">
                      <span className="bk-retention-row__key">{l}</span>
                      <span className="bk-retention-row__val">{v}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Backup Status */}
            <div className="bk-panel bk-glass">
              <div className="bk-panel__header">
                <div className="bk-panel__title">{I.Db} Backup Status</div>
              </div>
              <div className="bk-retention-rows">
                {[
                  ['Running',    sysStatus?.running||dash.running_backups||0],
                  ['Pending',    sysStatus?.pending||dash.pending_backups||0],
                  ['Failed 24h', sysStatus?.failed_24h||dash.failed_backups||0],
                  ['Maintenance',maintenance?'ON':'OFF'],
                  ['Success Rate',`${(dash.success_rate||0).toFixed(1)}%`],
                  ['Total Size',  dash.total_size_human||'—'],
                ].map(([l,v])=>(
                  <div key={l} className="bk-retention-row">
                    <span className="bk-retention-row__key">{l}</span>
                    <span className="bk-retention-row__val">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>{/* /container */}

      {/* ── MODALS ──────────────────────────────────────────── */}
      {modal?.type==='startBackup'   && <StartBackupModal   onClose={()=>setModal(null)} onSuccess={()=>fetchAll()} toast={toast}/>}
      {modal?.type==='logs'          && <LogsModal           backup={modal.data}          onClose={()=>setModal(null)}/>}
      {modal?.type==='restore'       && <RestoreModal        backup={modal.data}          onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='createSchedule'&& <ScheduleModal       schedule={null}              onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='editSchedule'  && <ScheduleModal       schedule={modal.data}        onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='createStorage' && <StorageModal        storage={null}               onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='editStorage'   && <StorageModal        storage={modal.data}         onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='createRetention'&&<RetentionModal      retention={null}             onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}
      {modal?.type==='editRetention' && <RetentionModal      retention={modal.data}       onClose={()=>setModal(null)} toast={toast} onSuccess={()=>fetchAll()}/>}

      {/* Delete Confirms */}
      {deleteTarget?.type==='backup'    && <DeleteConfirm name={deleteTarget.item.name} onConfirm={()=>handleDeleteBackup(deleteTarget.item)}    onCancel={()=>setDeleteTarget(null)}/>}
      {deleteTarget?.type==='schedule'  && <DeleteConfirm name={deleteTarget.item.name} onConfirm={()=>handleDeleteSchedule(deleteTarget.item)}  onCancel={()=>setDeleteTarget(null)}/>}
      {deleteTarget?.type==='storage'   && <DeleteConfirm name={deleteTarget.item.name} onConfirm={()=>handleDeleteStorage(deleteTarget.item)}   onCancel={()=>setDeleteTarget(null)}/>}
      {deleteTarget?.type==='retention' && <DeleteConfirm name={deleteTarget.item.name} onConfirm={()=>handleDeleteRetention(deleteTarget.item)} onCancel={()=>setDeleteTarget(null)}/>}

      <Toast toasts={toasts}/>
    </div>
  );
}



// // pages/Backup.jsx
// // Backup Command Center — Ultra Military Dark Operations
// // ✅ REAL API — /api/backup/ endpoints

// import React, { useState, useEffect, useCallback, useRef } from 'react';
// import '../styles/backup.css';

// // ─────────────────────────────────────────────────────────────────────────────
// // CONFIG
// // ─────────────────────────────────────────────────────────────────────────────
// const BASE         = '/api/backup';
// const THEME_COUNT  = 5;
// const COLOR_ROTATE = 60;
// const DATA_REFRESH = 30;
// const THEME_NAMES  = ['EMERALD OPS', 'OCEAN INTEL', 'CRIMSON ALERT', 'GOLDEN VAULT', 'VIOLET CIPHER'];

// // ─────────────────────────────────────────────────────────────────────────────
// // AUTH
// // ─────────────────────────────────────────────────────────────────────────────
// const authHeaders = () => ({
//   'Authorization': `Bearer ${
//     localStorage.getItem('adminAccessToken') ||
//     localStorage.getItem('access_token') ||
//     localStorage.getItem('auth_token') || ''
//   }`,
//   'Content-Type': 'application/json',
// });

// // ─────────────────────────────────────────────────────────────────────────────
// // API ENDPOINTS
// // GET  /api/backup/backups/                → BackupViewSet.list()
// // GET  /api/backup/schedules/              → BackupScheduleViewSet.list()
// // GET  /api/backup/storage-locations/      → BackupStorageLocationViewSet.list()
// // GET  /api/backup/retention-policies/     → RetentionPolicyViewSet.list()
// // GET  /api/backup/delta-trackers/         → DeltaBackupTrackerViewSet.list()
// // GET  /api/backup/restorations/           → BackupRestorationViewSet.list()
// // GET  /api/backup/dashboard-stats/        → DashboardStatsView
// // GET  /api/backup/system-metrics/         → SystemMetricsView
// // GET  /api/backup/backup-status/          → BackupStatusView
// // POST /api/backup/start-backup/           → StartBackupView
// // POST /api/backup/cleanup-old-backups/    → CleanupOldBackupsView
// // GET  /api/backup/backups/{id}/logs/      → BackupLogsView
// // POST /api/backup/backups/{id}/verify/    → BackupVerifyView
// // GET  /api/backup/analytics/backup-growth/   → BackupGrowthAnalyticsView
// // GET  /api/backup/analytics/storage-usage/   → StorageUsageAnalyticsView
// // GET  /api/backup/reports/health-report/     → HealthReportView
// // ─────────────────────────────────────────────────────────────────────────────
// const API = {
//   backups:      () => fetch(`${BASE}/backups/?page_size=12&ordering=-created_at`, { headers: authHeaders() }),
//   schedules:    () => fetch(`${BASE}/schedules/`, { headers: authHeaders() }),
//   storages:     () => fetch(`${BASE}/storage-locations/`, { headers: authHeaders() }),
//   retentions:   () => fetch(`${BASE}/retention-policies/`, { headers: authHeaders() }),
//   restorations: () => fetch(`${BASE}/restorations/?page_size=8`, { headers: authHeaders() }),
//   dashboard:    () => fetch(`${BASE}/dashboard-stats/`, { headers: authHeaders() }),
//   metrics:      () => fetch(`${BASE}/system-metrics/`, { headers: authHeaders() }),
//   status:       () => fetch(`${BASE}/backup-status/`, { headers: authHeaders() }),
//   health:       () => fetch(`${BASE}/reports/health-report/`, { headers: authHeaders() }),
//   growth:       () => fetch(`${BASE}/analytics/backup-growth/`, { headers: authHeaders() }),
//   startBackup:  (data) => fetch(`${BASE}/start-backup/`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(data) }),
//   cleanup:      () => fetch(`${BASE}/cleanup-old-backups/`, { method: 'POST', headers: authHeaders() }),
//   verifyBackup: (id) => fetch(`${BASE}/backups/${id}/verify/`, { method: 'POST', headers: authHeaders() }),
//   backupLogs:   (id) => fetch(`${BASE}/backups/${id}/logs/`, { headers: authHeaders() }),
//   deleteBackup: (id) => fetch(`${BASE}/backups/${id}/`, { method: 'DELETE', headers: authHeaders() }),
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // SAFE FETCH
// // ─────────────────────────────────────────────────────────────────────────────
// async function safeFetch(fn) {
//   try {
//     const res = await fn();
//     const text = await res.text();
//     if (!res.ok) { console.warn(`[Backup API] ${res.status}`); return null; }
//     try { return JSON.parse(text); } catch { return null; }
//   } catch (e) { console.warn('[Backup API]', e.message); return null; }
// }
// const extract = (res) => {
//   if (!res) return [];
//   if (Array.isArray(res)) return res;
//   if (Array.isArray(res.results)) return res.results;
//   if (Array.isArray(res.data)) return res.data;
//   if (Array.isArray(res.backups)) return res.backups;
//   return [];
// };
// const extractObj = (res, fb = {}) => {
//   if (!res) return fb;
//   if (res.data && typeof res.data === 'object' && !Array.isArray(res.data)) return res.data;
//   if (typeof res === 'object' && !Array.isArray(res)) return res;
//   return fb;
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // FALLBACK DATA
// // ─────────────────────────────────────────────────────────────────────────────
// const FB_BACKUPS = [
//   { id:'b001', backup_id:'BK-2026-001', name:'Full DB Backup', backup_type:'full', status:'completed', file_size_human:'2.4 GB', duration_human:'12m 34s', database_name:'earning_db', created_at:'2026-03-01T06:00:00Z', is_encrypted:true, compression_type:'gzip', storage_type:'local' },
//   { id:'b002', backup_id:'BK-2026-002', name:'Incremental Backup', backup_type:'incremental', status:'completed', file_size_human:'380 MB', duration_human:'3m 12s', database_name:'earning_db', created_at:'2026-03-01T12:00:00Z', is_encrypted:true, compression_type:'gzip', storage_type:'s3' },
//   { id:'b003', backup_id:'BK-2026-003', name:'Media Files Backup', backup_type:'differential', status:'running', file_size_human:'1.1 GB', duration_human:'—', database_name:'media', created_at:'2026-03-02T06:00:00Z', is_encrypted:false, compression_type:'lz4', storage_type:'local' },
//   { id:'b004', backup_id:'BK-2026-004', name:'Config Backup', backup_type:'full', status:'failed', file_size_human:'12 MB', duration_human:'0m 45s', database_name:'config', created_at:'2026-03-01T18:00:00Z', is_encrypted:true, compression_type:'none', storage_type:'ftp' },
//   { id:'b005', backup_id:'BK-2026-005', name:'User Data Backup', backup_type:'delta', status:'completed', file_size_human:'640 MB', duration_human:'5m 22s', database_name:'earning_db', created_at:'2026-03-01T00:00:00Z', is_encrypted:true, compression_type:'zstd', storage_type:'s3' },
//   { id:'b006', backup_id:'BK-2026-006', name:'Weekly Full Backup', backup_type:'full', status:'pending', file_size_human:'—', duration_human:'—', database_name:'earning_db', created_at:'2026-03-02T07:00:00Z', is_encrypted:true, compression_type:'gzip', storage_type:'local' },
// ];
// const FB_SCHEDULES = [
//   { id:1, name:'Daily Full Backup',    schedule_type:'daily',   is_active:true,  next_run:'2026-03-03T06:00:00Z', backup_type:'full',        retention_days:30 },
//   { id:2, name:'Hourly Incremental',   schedule_type:'hourly',  is_active:true,  next_run:'2026-03-02T08:00:00Z', backup_type:'incremental', retention_days:7 },
//   { id:3, name:'Weekly Archive',       schedule_type:'weekly',  is_active:true,  next_run:'2026-03-07T00:00:00Z', backup_type:'full',        retention_days:90 },
//   { id:4, name:'Monthly Snapshot',     schedule_type:'monthly', is_active:false, next_run:'2026-04-01T00:00:00Z', backup_type:'full',        retention_days:365 },
//   { id:5, name:'Delta Tracker Sync',   schedule_type:'daily',   is_active:true,  next_run:'2026-03-03T02:00:00Z', backup_type:'delta',       retention_days:14 },
// ];
// const FB_STORAGES = [
//   { id:1, name:'Primary Local',  storage_type:'local', is_active:true,  host:'localhost', total_size_human:'500 GB', used_size_human:'142 GB', available_size_human:'358 GB' },
//   { id:2, name:'AWS S3 Bucket',  storage_type:'s3',    is_active:true,  host:'s3.amazonaws.com', total_size_human:'∞', used_size_human:'86 GB', available_size_human:'∞' },
//   { id:3, name:'FTP Archive',    storage_type:'ftp',   is_active:false, host:'ftp.backup.server', total_size_human:'200 GB', used_size_human:'44 GB', available_size_human:'156 GB' },
// ];
// const FB_RETENTIONS = [
//   { id:1, name:'Daily Retention',   daily_copies:7,   weekly_copies:4,  monthly_copies:3,  yearly_copies:1, is_active:true },
//   { id:2, name:'Extended Archive',  daily_copies:30,  weekly_copies:12, monthly_copies:12, yearly_copies:5, is_active:true },
// ];
// const FB_DASH = {
//   total_backups: 248, successful_backups: 231, failed_backups: 12, running_backups: 1,
//   total_size_human: '42.8 GB', last_backup_status: 'completed',
//   next_backup_in: '2h 15m', success_rate: 93.1,
//   storage_used_percent: 28.4, pending_backups: 4,
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // TICKER
// // ─────────────────────────────────────────────────────────────────────────────
// const TICKER_ITEMS = [
//   { key:'SYSTEM STATUS',     val:'OPERATIONAL', cls:'t-green'  },
//   { key:'TOTAL BACKUPS',     val:'248',         cls:'t-accent' },
//   { key:'SUCCESS RATE',      val:'93.1%',       cls:'t-green'  },
//   { key:'FAILED',            val:'12',          cls:'t-red'    },
//   { key:'STORAGE USED',      val:'42.8 GB',     cls:'t-accent' },
//   { key:'NEXT BACKUP',       val:'2h 15m',      cls:'t-amber'  },
//   { key:'ACTIVE SCHEDULES',  val:'4',           cls:'t-green'  },
//   { key:'STORAGE LOCATIONS', val:'3',           cls:''         },
//   { key:'RUNNING NOW',       val:'1',           cls:'t-amber'  },
//   { key:'RETENTION ACTIVE',  val:'2 POLICIES',  cls:''         },
//   { key:'LAST SYNC',         val:'4m AGO',      cls:''         },
// ];

// // ─────────────────────────────────────────────────────────────────────────────
// // ICONS
// // ─────────────────────────────────────────────────────────────────────────────
// const Ico = {
//   Db:       () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>,
//   Shield:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
//   Clock:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
//   Storage:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>,
//   Refresh:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>,
//   Play:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
//   Trash:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>,
//   Check:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
//   Bell:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
//   User:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
//   Chart:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
//   Restore:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg>,
//   Lock:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
//   Download: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // TOAST
// // ─────────────────────────────────────────────────────────────────────────────
// function Toast({ msg, type, onClose }) {
//   useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
//   return <div className={`bk-toast ${type}`}>{msg}</div>;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // MAIN COMPONENT
// // ─────────────────────────────────────────────────────────────────────────────
// export default function Backup() {
//   const [theme,        setTheme]       = useState(0);
//   const [themeTimer,   setThemeTimer]  = useState(COLOR_ROTATE);
//   const [dataTimer,    setDataTimer]   = useState(DATA_REFRESH);
//   const [loading,      setLoading]     = useState(false);
//   const [apiOnline,    setApiOnline]   = useState(false);
//   const [toast,        setToast]       = useState(null);

//   const [backups,      setBackups]     = useState(FB_BACKUPS);
//   const [schedules,    setSchedules]   = useState(FB_SCHEDULES);
//   const [storages,     setStorages]    = useState(FB_STORAGES);
//   const [retentions,   setRetentions]  = useState(FB_RETENTIONS);
//   const [dash,         setDash]        = useState(FB_DASH);
//   const [metrics,      setMetrics]     = useState(null);
//   const [status,       setStatus]      = useState(null);

//   const themeRef = useRef(null);
//   const dataRef  = useRef(null);

//   const showToast = (msg, type = 'success') => setToast({ msg, type, key: Date.now() });

//   // ── FETCH ALL ─────────────────────────────────────────────────────────────
//   const fetchAll = useCallback(async (showLoader = false) => {
//     if (showLoader) setLoading(true);

//     const [bkRes, schRes, stRes, retRes, dashRes, metricsRes, statusRes] = await Promise.all([
//       safeFetch(API.backups),
//       safeFetch(API.schedules),
//       safeFetch(API.storages),
//       safeFetch(API.retentions),
//       safeFetch(API.dashboard),
//       safeFetch(API.metrics),
//       safeFetch(API.status),
//     ]);

//     let anySuccess = false;

//     // backups — BackupSerializer fields:
//     // id, backup_id, name, description, backup_type, backup_type_display,
//     // status, status_display, storage_type, storage_type_display, storage_path,
//     // file_name, file_size, file_size_human, file_hash, is_encrypted,
//     // encryption_type, compression_type, compression_ratio,
//     // database_engine, database_name, database_version, table_count, row_count,
//     // start_time, end_time, duration, duration_human, backup_speed,
//     // created_by_username, verified_by_username, parent_backup_name,
//     // schedule_name, is_expired, health_status, log_count, restoration_count
//     const bkList = extract(bkRes);
//     if (bkList.length) { setBackups(bkList); anySuccess = true; }

//     // schedules — BackupScheduleSerializer
//     const schList = extract(schRes);
//     if (schList.length) { setSchedules(schList); anySuccess = true; }

//     // storage-locations — BackupStorageLocationSerializer
//     const stList = extract(stRes);
//     if (stList.length) { setStorages(stList); anySuccess = true; }

//     // retention-policies — RetentionPolicySerializer
//     const retList = extract(retRes);
//     if (retList.length) { setRetentions(retList); anySuccess = true; }

//     // dashboard-stats — DashboardStatsView
//     if (dashRes) { setDash(prev => ({ ...prev, ...extractObj(dashRes) })); anySuccess = true; }

//     // system-metrics — SystemMetricsView
//     if (metricsRes) { setMetrics(extractObj(metricsRes)); anySuccess = true; }

//     // backup-status — BackupStatusView
//     if (statusRes) { setStatus(extractObj(statusRes)); anySuccess = true; }

//     setApiOnline(anySuccess);
//     setDataTimer(DATA_REFRESH);
//     if (showLoader) setLoading(false);
//   }, []);

//   // ── THEME TIMER ───────────────────────────────────────────────────────────
//   useEffect(() => {
//     themeRef.current = setInterval(() => {
//       setThemeTimer(prev => {
//         if (prev <= 1) { setTheme(t => (t + 1) % THEME_COUNT); return COLOR_ROTATE; }
//         return prev - 1;
//       });
//     }, 1000);
//     return () => clearInterval(themeRef.current);
//   }, []);

//   // ── DATA TIMER ────────────────────────────────────────────────────────────
//   useEffect(() => {
//     fetchAll(true);
//     dataRef.current = setInterval(() => {
//       setDataTimer(prev => {
//         if (prev <= 1) { fetchAll(); return DATA_REFRESH; }
//         return prev - 1;
//       });
//     }, 1000);
//     return () => clearInterval(dataRef.current);
//   }, [fetchAll]);

//   // ── ACTIONS ───────────────────────────────────────────────────────────────
//   const handleStartBackup = async () => {
//     showToast('Starting backup...', 'info');
//     const res = await safeFetch(() => API.startBackup({ backup_type: 'full' }));
//     if (res !== null) { showToast('Backup started!', 'success'); fetchAll(); }
//     else { showToast('Start backup failed', 'error'); }
//   };

//   const handleCleanup = async () => {
//     showToast('Cleaning old backups...', 'info');
//     const res = await safeFetch(API.cleanup);
//     if (res !== null) { showToast('Cleanup completed!', 'success'); fetchAll(); }
//     else { showToast('Cleanup failed', 'error'); }
//   };

//   const handleVerify = async (id) => {
//     const res = await safeFetch(() => API.verifyBackup(id));
//     if (res !== null) { showToast('Backup verified!', 'success'); }
//     else { showToast('Verification failed', 'error'); }
//   };

//   const handleDelete = async (id) => {
//     const res = await safeFetch(() => API.deleteBackup(id));
//     if (res !== null || res === null) {
//       setBackups(prev => prev.filter(b => b.id !== id));
//       showToast('Backup deleted', 'success');
//     }
//   };

//   // ── HELPERS ───────────────────────────────────────────────────────────────
//   const fmtDate = (d) => {
//     if (!d) return '—';
//     try { return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
//     catch { return d; }
//   };

//   const statusCls = (s) => {
//     if (!s) return 'bk-badge-accent';
//     const st = s.toLowerCase();
//     if (st === 'completed')  return 'bk-badge-green';
//     if (st === 'failed')     return 'bk-badge-red';
//     if (st === 'running')    return 'bk-badge-amber';
//     if (st === 'pending')    return 'bk-badge-blue';
//     if (st === 'cancelled')  return 'bk-badge-red';
//     return 'bk-badge-accent';
//   };

//   const typeCls = (t) => {
//     if (!t) return 'bk-badge-accent';
//     const tp = t.toLowerCase();
//     if (tp === 'full')        return 'bk-badge-blue';
//     if (tp === 'incremental') return 'bk-badge-green';
//     if (tp === 'differential')return 'bk-badge-amber';
//     if (tp === 'delta')       return 'bk-badge-purple';
//     return 'bk-badge-accent';
//   };

//   const scheduleDotCls = (s) => {
//     if (!s) return '';
//     const is_active = s.is_active;
//     return is_active ? 'active' : 'inactive';
//   };

//   const successRate = () => {
//     const total = dash.total_backups || 1;
//     const success = dash.successful_backups || 0;
//     return Math.min(100, (success / total) * 100);
//   };

//   // ── OVERVIEW STATS ────────────────────────────────────────────────────────
//   const STATS = [
//     { label:'TOTAL BACKUPS',    val: dash.total_backups || 0,     cls:'',       icon: <Ico.Db />,      sub: 'all time' },
//     { label:'SUCCESSFUL',       val: dash.successful_backups || 0,cls:'green',  icon: <Ico.Check />,   sub: `${(dash.success_rate || 0).toFixed(1)}% rate`, up: true },
//     { label:'FAILED',           val: dash.failed_backups || 0,    cls:'red',    icon: <Ico.Shield />,  sub: 'needs attention', up: false },
//     { label:'RUNNING',          val: dash.running_backups || 0,   cls:'amber',  icon: <Ico.Chart />,   sub: 'in progress' },
//     { label:'TOTAL SIZE',       val: dash.total_size_human || '—',cls:'blue',   icon: <Ico.Storage />, sub: `${(dash.storage_used_percent || 0).toFixed(1)}% used` },
//     { label:'NEXT BACKUP',      val: dash.next_backup_in || '—',  cls:'purple', icon: <Ico.Clock />,   sub: 'scheduled' },
//   ];

//   // ─────────────────────────────────────────────────────────────────────────
//   return (
//     <div className={`bk-root bk-theme-${theme}`}>

//       {toast && (
//         <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={() => setToast(null)}/>
//       )}

//       {/* ── TOPBAR ──────────────────────────────────────────────────────── */}
//       <header className="bk-topbar">
//         <div className="bk-brand">
//           <div className="bk-brand-icon"><Ico.Db /></div>
//           <div>
//             <div className="bk-brand-name">BACKUP CMD</div>
//             <div className="bk-brand-sub">DISASTER RECOVERY SYSTEM v4.2</div>
//           </div>
//         </div>

//         <div className="bk-topbar-center">
//           <div className={`bk-pill ${apiOnline ? 'green' : ''}`}>
//             <span className={`bk-dot ${apiOnline ? '' : 'amber'}`}/>
//             {apiOnline ? 'API CONNECTED' : 'MOCK DATA'}
//           </div>
//           <div className="bk-pill green">
//             <span className="bk-dot"/>
//             {(dash.last_backup_status || 'unknown').toUpperCase()}
//           </div>
//           <div className="bk-pill">{THEME_NAMES[theme]}</div>
//         </div>

//         <div className="bk-topbar-right">
//           <div className="bk-timer">COLOR <span>{String(themeTimer).padStart(2,'0')}s</span></div>
//           <div className="bk-timer">DATA <span>{String(dataTimer).padStart(2,'0')}s</span></div>
//           <button className="bk-btn solid" onClick={handleStartBackup}>
//             <Ico.Play /> START BACKUP
//           </button>
//           <button className="bk-icon-btn" onClick={() => fetchAll(true)}><Ico.Refresh /></button>
//           <button className="bk-icon-btn"><Ico.Bell /></button>
//           <button className="bk-icon-btn"><Ico.User /></button>
//         </div>
//       </header>

//       {/* ── TICKER ──────────────────────────────────────────────────────── */}
//       <div className="bk-ticker">
//         <div className="bk-ticker-inner">
//           {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
//             <span className={`bk-ticker-item ${item.cls || ''}`} key={i}>
//               <span className="bk-tkey">{item.key}</span>
//               {item.val}
//             </span>
//           ))}
//         </div>
//       </div>

//       {/* ── CONTENT ─────────────────────────────────────────────────────── */}
//       <div className="bk-content">

//         {/* ── OVERVIEW STATS ────────────────────────────────────────── */}
//         <div className="bk-overview">
//           {STATS.map((s, i) => (
//             <div className="bk-stat" key={i}>
//               <div className="bk-stat-icon">{s.icon}</div>
//               <div className="bk-stat-label">{s.label}</div>
//               <div className={`bk-stat-val ${s.cls || ''}`}>{s.val}</div>
//               <div className={`bk-stat-sub ${s.up === true ? 'up' : s.up === false ? 'down' : ''}`}>{s.sub}</div>
//             </div>
//           ))}
//         </div>

//         {/* ── BACKUPS TABLE ──────────────────────────────────────────── */}
//         {/* GET /api/backup/backups/ → BackupViewSet.list() */}
//         <div className="bk-panel" style={{gridColumn:'1 / 3'}}>
//           <div className="bk-scanline"/>
//           <div className="bk-panel-hdr">
//             <div className="bk-panel-title"><Ico.Db /> BACKUP RECORDS</div>
//             <div className="bk-panel-meta">
//               <span className="bk-live">LIVE</span>
//               <span className="bk-badge bk-badge-accent">{backups.length} BACKUPS</span>
//               <button className="bk-btn amber" onClick={handleCleanup}>
//                 <Ico.Trash /> CLEANUP
//               </button>
//             </div>
//           </div>
//           {loading ? (
//             <div className="bk-loading"><div className="bk-spinner"/> LOADING BACKUPS...</div>
//           ) : (
//             <div className="bk-table-wrap">
//               <table className="bk-table">
//                 <thead>
//                   <tr>
//                     <th>BACKUP ID</th>
//                     <th>NAME</th>
//                     <th>TYPE</th>
//                     <th>DATABASE</th>
//                     <th>SIZE</th>
//                     <th>DURATION</th>
//                     <th>STATUS</th>
//                     <th>SECURITY</th>
//                     <th>DATE</th>
//                     <th>ACTIONS</th>
//                   </tr>
//                 </thead>
//                 <tbody>
//                   {backups.slice(0, 10).map(b => (
//                     // BackupSerializer fields:
//                     // backup_id, name, backup_type, status, file_size_human,
//                     // duration_human, database_name, is_encrypted, compression_type,
//                     // storage_type, created_at, health_status
//                     <tr key={b.id}>
//                       <td>
//                         <span style={{fontFamily:'var(--bk-font-mono)', fontSize:'10px', color:'var(--bk-text3)'}}>
//                           {b.backup_id || `#${b.id}`}
//                         </span>
//                       </td>
//                       <td><span className="bk-tname">{b.name || '—'}</span></td>
//                       <td>
//                         <span className={`bk-badge ${typeCls(b.backup_type)}`}>
//                           {(b.backup_type_display || b.backup_type || '—').toUpperCase()}
//                         </span>
//                       </td>
//                       <td style={{fontSize:'10px', color:'var(--bk-text2)'}}>{b.database_name || '—'}</td>
//                       <td><span className="bk-tval">{b.file_size_human || '—'}</span></td>
//                       <td style={{fontSize:'10px', color:'var(--bk-text3)'}}>{b.duration_human || '—'}</td>
//                       <td>
//                         <span className={`bk-badge ${statusCls(b.status)}`}>
//                           {(b.status_display || b.status || '—').toUpperCase()}
//                         </span>
//                       </td>
//                       <td>
//                         <div style={{display:'flex', gap:'4px'}}>
//                           {b.is_encrypted && <span className="bk-badge bk-badge-green">ENC</span>}
//                           {b.compression_type && b.compression_type !== 'none' && (
//                             <span className="bk-badge bk-badge-accent">{b.compression_type.toUpperCase()}</span>
//                           )}
//                         </div>
//                       </td>
//                       <td style={{fontSize:'10px', color:'var(--bk-text3)'}}>{fmtDate(b.created_at)}</td>
//                       <td>
//                         <div style={{display:'flex', gap:'5px'}}>
//                           <button className="bk-btn" onClick={() => handleVerify(b.id)}>
//                             <Ico.Check />
//                           </button>
//                           <button className="bk-btn" title="Download">
//                             <Ico.Download />
//                           </button>
//                           <button className="bk-btn red" onClick={() => handleDelete(b.id)}>
//                             <Ico.Trash />
//                           </button>
//                         </div>
//                       </td>
//                     </tr>
//                   ))}
//                 </tbody>
//               </table>
//               {backups.length === 0 && <div className="bk-empty">// NO_BACKUPS_FOUND</div>}
//             </div>
//           )}

//           {/* Success Rate Bar */}
//           <div style={{padding:'12px 16px', borderTop:'1px solid var(--bk-border)'}}>
//             <div style={{display:'flex', justifyContent:'space-between', marginBottom:'6px'}}>
//               <span style={{fontFamily:'var(--bk-font-mono)', fontSize:'9px', color:'var(--bk-text3)', letterSpacing:'2px'}}>
//                 SUCCESS RATE
//               </span>
//               <span style={{fontFamily:'var(--bk-font-mono)', fontSize:'9px', color:'var(--bk-green)'}}>
//                 {successRate().toFixed(1)}%
//               </span>
//             </div>
//             <div className="bk-progress-wrap">
//               <div className="bk-progress-bar green" style={{width:`${successRate()}%`}}/>
//             </div>
//           </div>
//         </div>

//         {/* ── SCHEDULES ──────────────────────────────────────────────── */}
//         {/* GET /api/backup/schedules/ → BackupScheduleViewSet.list() */}
//         <div className="bk-panel">
//           <div className="bk-panel-hdr">
//             <div className="bk-panel-title"><Ico.Clock /> SCHEDULES</div>
//             <div className="bk-panel-meta">
//               <span className="bk-badge bk-badge-accent">{schedules.length}</span>
//             </div>
//           </div>
//           <div className="bk-schedule-list">
//             {schedules.map(s => (
//               // BackupScheduleSerializer fields:
//               // id, name, schedule_type, is_active, next_run, backup_type, retention_days
//               <div className="bk-schedule-item" key={s.id}>
//                 <div className={`bk-schedule-dot ${scheduleDotCls(s)}`}/>
//                 <div className="bk-schedule-body">
//                   <div className="bk-schedule-name">{s.name || '—'}</div>
//                   <div className="bk-schedule-meta">
//                     <span className={`bk-badge ${typeCls(s.backup_type)}`} style={{marginRight:'5px'}}>
//                       {(s.backup_type || '—').toUpperCase()}
//                     </span>
//                     {s.retention_days && <span>{s.retention_days}d retain</span>}
//                   </div>
//                 </div>
//                 <div style={{textAlign:'right'}}>
//                   <span className={`bk-badge ${s.is_active ? 'bk-badge-green' : 'bk-badge-red'}`}>
//                     {s.is_active ? 'ON' : 'OFF'}
//                   </span>
//                   <div style={{fontFamily:'var(--bk-font-mono)', fontSize:'8px', color:'var(--bk-text3)', marginTop:'3px'}}>
//                     {s.schedule_type ? s.schedule_type.toUpperCase() : '—'}
//                   </div>
//                 </div>
//               </div>
//             ))}
//             {schedules.length === 0 && <div className="bk-empty">// NO_SCHEDULES</div>}
//           </div>
//         </div>

//         {/* ── STORAGE LOCATIONS ──────────────────────────────────────── */}
//         {/* GET /api/backup/storage-locations/ → BackupStorageLocationViewSet.list() */}
//         <div className="bk-panel" style={{gridColumn:'1 / 3'}}>
//           <div className="bk-panel-hdr">
//             <div className="bk-panel-title"><Ico.Storage /> STORAGE LOCATIONS</div>
//             <div className="bk-panel-meta">
//               <span className="bk-live">LIVE</span>
//               <span className="bk-badge bk-badge-accent">{storages.length} LOCATIONS</span>
//             </div>
//           </div>
//           <div className="bk-storage-grid">
//             {storages.map(st => {
//               // BackupStorageLocationSerializer fields:
//               // id, name, storage_type, is_active, host,
//               // total_size_human, used_size_human, available_size_human
//               const usedPct = st.used_percent || 0;
//               return (
//                 <div className="bk-storage-card" key={st.id}>
//                   <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'10px'}}>
//                     <div>
//                       <div className="bk-storage-name">{st.name || '—'}</div>
//                       <div className="bk-storage-type">{(st.host || '').toUpperCase()}</div>
//                     </div>
//                     <div style={{display:'flex', flexDirection:'column', gap:'4px', alignItems:'flex-end'}}>
//                       <span className={`bk-badge ${st.is_active ? 'bk-badge-green' : 'bk-badge-red'}`}>
//                         {st.is_active ? 'ONLINE' : 'OFFLINE'}
//                       </span>
//                       <span className="bk-badge bk-badge-blue">
//                         {(st.storage_type || '—').toUpperCase()}
//                       </span>
//                     </div>
//                   </div>
//                   <div className="bk-storage-stats">
//                     <div className="bk-sstat">
//                       <div className="bk-sstat-label">TOTAL</div>
//                       <div className="bk-sstat-val">{st.total_size_human || '—'}</div>
//                     </div>
//                     <div className="bk-sstat">
//                       <div className="bk-sstat-label">USED</div>
//                       <div className="bk-sstat-val">{st.used_size_human || '—'}</div>
//                     </div>
//                     <div className="bk-sstat">
//                       <div className="bk-sstat-label">FREE</div>
//                       <div className="bk-sstat-val" style={{color:'var(--bk-green)'}}>{st.available_size_human || '—'}</div>
//                     </div>
//                     <div className="bk-sstat">
//                       <div className="bk-sstat-label">USED %</div>
//                       <div className="bk-sstat-val" style={{color: usedPct > 80 ? 'var(--bk-red)' : usedPct > 60 ? 'var(--bk-amber)' : 'var(--bk-accent)'}}>
//                         {usedPct > 0 ? `${usedPct.toFixed(1)}%` : '—'}
//                       </div>
//                     </div>
//                   </div>
//                   {usedPct > 0 && (
//                     <div className="bk-progress-wrap">
//                       <div className={`bk-progress-bar ${usedPct > 80 ? 'red' : usedPct > 60 ? 'amber' : ''}`}
//                         style={{width:`${usedPct}%`}}/>
//                     </div>
//                   )}
//                 </div>
//               );
//             })}
//             {storages.length === 0 && <div className="bk-empty">// NO_STORAGE_LOCATIONS</div>}
//           </div>
//         </div>

//         {/* ── RETENTION POLICIES ─────────────────────────────────────── */}
//         {/* GET /api/backup/retention-policies/ → RetentionPolicyViewSet.list() */}
//         <div className="bk-panel">
//           <div className="bk-panel-hdr">
//             <div className="bk-panel-title"><Ico.Shield /> RETENTION POLICIES</div>
//             <div className="bk-panel-meta">
//               <span className="bk-badge bk-badge-accent">{retentions.length}</span>
//             </div>
//           </div>
//           <div className="bk-retention-list">
//             {retentions.map(r => (
//               // RetentionPolicySerializer fields:
//               // id, name, daily_copies, weekly_copies, monthly_copies, yearly_copies, is_active
//               <div key={r.id} style={{marginBottom:'12px'}}>
//                 <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'8px'}}>
//                   <span style={{fontFamily:'var(--bk-font-mono)', fontSize:'11px', color:'var(--bk-text)'}}>{r.name}</span>
//                   <span className={`bk-badge ${r.is_active ? 'bk-badge-green' : 'bk-badge-red'}`}>
//                     {r.is_active ? 'ACTIVE' : 'OFF'}
//                   </span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">DAILY</span>
//                   <span className="bk-retention-val">{r.daily_copies || 0} copies</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">WEEKLY</span>
//                   <span className="bk-retention-val">{r.weekly_copies || 0} copies</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">MONTHLY</span>
//                   <span className="bk-retention-val">{r.monthly_copies || 0} copies</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">YEARLY</span>
//                   <span className="bk-retention-val">{r.yearly_copies || 0} copies</span>
//                 </div>
//               </div>
//             ))}
//             {retentions.length === 0 && <div className="bk-empty">// NO_POLICIES</div>}
//           </div>
//         </div>

//         {/* ── SYSTEM METRICS ─────────────────────────────────────────── */}
//         {/* GET /api/backup/system-metrics/ → SystemMetricsView */}
//         <div className="bk-panel">
//           <div className="bk-panel-hdr">
//             <div className="bk-panel-title"><Ico.Chart /> SYSTEM METRICS</div>
//             <div className="bk-panel-meta">
//               <span className="bk-live">LIVE</span>
//             </div>
//           </div>
//           <div className="bk-retention-list">
//             {metrics ? Object.entries(metrics)
//               .filter(([k]) => !['id','created_at','updated_at'].includes(k))
//               .slice(0, 10)
//               .map(([key, val]) => (
//                 <div className="bk-retention-row" key={key}>
//                   <span className="bk-retention-key">
//                     {key.replace(/_/g, ' ').toUpperCase()}
//                   </span>
//                   <span className="bk-retention-val">
//                     {String(val).toUpperCase()}
//                   </span>
//                 </div>
//               )) : (
//               <>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">CPU USAGE</span>
//                   <span className="bk-retention-val">24.5%</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">MEMORY</span>
//                   <span className="bk-retention-val amber">68.2%</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">DISK I/O</span>
//                   <span className="bk-retention-val">12 MB/s</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">NETWORK</span>
//                   <span className="bk-retention-val green">STABLE</span>
//                 </div>
//                 <div className="bk-retention-row">
//                   <span className="bk-retention-key">DB CONNECTIONS</span>
//                   <span className="bk-retention-val">14 / 100</span>
//                 </div>
//               </>
//             )}
//           </div>
//         </div>

//       </div>
//     </div>
//   );
// }