// src/pages/AdminPanel.jsx
// Tabs: Dashboard | Settings | Notifications | Contents | Reports | Action Log | Health

import { useState, useEffect, useCallback } from 'react';
import * as Icon from 'react-feather';
import client from '../api/client';
import '../styles/AdminPanel.css';

// ── API ────────────────────────────────────────────────────────────
const api = {
  // Dashboard
  dashboard:    ()    => client.get('/admin-panel/dashboard/dashboard/'),
  userStats:    ()    => client.get('/admin-panel/dashboard/user_stats/'),
  revenueStats: ()    => client.get('/admin-panel/dashboard/revenue_stats/'),
  exportData:   (type)=> client.post('/admin-panel/dashboard/export_data/', { type }),

  // Settings
  settingsPublic:    ()    => client.get('/admin-panel/settings/public/'),
  settingsAdmin:     ()    => client.get('/admin-panel/settings/'),
  updateSettings:    (d)   => client.patch('/admin-panel/settings/update_settings/', d),
  toggleMaintenance: (d)   => client.post('/admin-panel/settings/toggle_maintenance/', d),
  maintenanceStatus: ()    => client.get('/admin-panel/settings/maintenance_status/'),
  paymentGateways:   ()    => client.get('/admin-panel/settings/payment_gateways/'),
  referralSettings:  ()    => client.get('/admin-panel/settings/referral_settings/'),
  rewardPoints:      ()    => client.get('/admin-panel/settings/reward_points/'),
  withdrawalSettings:()    => client.get('/admin-panel/settings/withdrawal_settings/'),

  // Notifications
  notifList:    (p={})=> client.get('/admin-panel/notifications/', { params: p }),
  notifCreate:  (d)   => client.post('/admin-panel/notifications/', d),
  notifUpdate:  (id,d)=> client.patch(`/admin-panel/notifications/${id}/`, d),
  notifDelete:  (id)  => client.delete(`/admin-panel/notifications/${id}/`),
  notifActive:  ()    => client.get('/admin-panel/notifications/active_notifications/'),

  // Contents
  contentList:  (p={})=> client.get('/admin-panel/contents/', { params: p }),
  contentCreate:(d)   => client.post('/admin-panel/contents/', d),
  contentUpdate:(id,d)=> client.patch(`/admin-panel/contents/${id}/`, d),
  contentDelete:(id)  => client.delete(`/admin-panel/contents/${id}/`),

  // Reports
  reportList:   (p={})=> client.get('/admin-panel/reports/', { params: p }),
  generateReport:(d)  => client.post('/admin-panel/reports/generate_report/', d),

  // Actions
  actionList:   (p={})=> client.get('/admin-panel/actions/', { params: p }),

  // Health
  health:       ()    => client.get('/admin-panel/health/'),
};

// ── Helpers ────────────────────────────────────────────────────────
const safeArr = d => Array.isArray(d) ? d : (d?.results ?? d?.data ?? []);
const errMsg  = e => {
  const d = e?.response?.data;
  if (!d) return e?.message || 'Error';
  if (typeof d === 'string') return d;
  if (d.detail) return d.detail;
  return Object.entries(d).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
};
const fmtDate = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
const fmtNum  = n => n != null ? Number(n).toLocaleString() : '—';
const fmtCur  = n => n != null ? `৳${Number(n).toFixed(2)}` : '—';

// ── Shared UI ──────────────────────────────────────────────────────
function Skeleton(){ return <div className="ap-loading">{[1,2,3,4].map(i=><div key={i} className="ap-loading-row"/>)}</div>; }
function Empty({icon,text}){ return <div className="ap-empty"><div className="ap-empty-icon">{icon}</div><p className="ap-empty-txt">{text}</p></div>; }
function Field({label,children}){ return <div className="ap-field"><label className="ap-field-lbl">{label}</label>{children}</div>; }
function KV({k,v}){ return <div className="ap-kv"><span className="ap-kv-k">{k}</span><span className="ap-kv-v">{String(v??'—')}</span></div>; }

function Modal({title,onClose,children,wide,lg}){
  return <div className="ap-modal-bg" onClick={e=>e.target===e.currentTarget&&onClose()}>
    <div className={`ap-modal${wide?' ap-modal--wide':''}${lg?' ap-modal--lg':''}`}>
      <div className="ap-modal-hdr">
        <h3 className="ap-modal-title">{title}</h3>
        <button className="ap-modal-close" onClick={onClose}><Icon.X size={18}/></button>
      </div>
      <div className="ap-modal-body">{children}</div>
    </div>
  </div>;
}

const NOTIF_COLORS = { INFO:'cyan', SUCCESS:'green', WARNING:'gold', ERROR:'red', MAINTENANCE:'orange', UPDATE:'purple', PROMOTION:'pink' };
function NotifBadge({type}){ return <span className={`ap-badge ap-badge--${NOTIF_COLORS[type]||'muted'}`}>{type}</span>; }

// ══════════════════════════════════════════════════════════════════
// TAB 1 — Dashboard
// ══════════════════════════════════════════════════════════════════
function DashboardTab(){
  const [stats,    setStats]    = useState(null);
  const [uStats,   setUStats]   = useState(null);
  const [rStats,   setRStats]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [exporting,setExporting]= useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [d, u, r] = await Promise.allSettled([api.dashboard(), api.userStats(), api.revenueStats()]);
      if (d.status==='fulfilled') setStats(d.value?.data?.data || d.value?.data);
      if (u.status==='fulfilled') setUStats(u.value?.data?.data || u.value?.data);
      if (r.status==='fulfilled') setRStats(r.value?.data?.data || r.value?.data);
    } catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, []);

  useEffect(() => { load(); }, []);

  const handleExport = async type => {
    setExporting(true);
    try{ const res = await api.exportData(type); alert(`Exported: ${res.data?.data?.file_path || 'Done'}`); }
    catch(e){ alert(errMsg(e)); } finally{ setExporting(false); }
  };

  if(loading) return <Skeleton/>;
  if(error)   return <div className="ap-error">{error}</div>;

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">System Dashboard</h2><p className="ap-tab-sub">Platform overview and key metrics</p></div>
      <div className="ap-header-acts">
        <button className="ap-btn ap-btn--ghost ap-btn--sm" onClick={load}><Icon.RefreshCw size={13}/> Refresh</button>
        <button className="ap-btn ap-btn--cyan ap-btn--sm" onClick={()=>handleExport('users')} disabled={exporting}><Icon.Download size={13}/> Export Users</button>
      </div>
    </div>

    {/* Main Stats */}
    <div className="ap-stats-grid">
      <div className="ap-stat-card ap-stat-card--cyan">
        <div className="ap-stat-icon">👥</div>
        <div className="ap-stat-value">{fmtNum(stats?.total_users)}</div>
        <div className="ap-stat-label">Total Users</div>
        <div className="ap-stat-sub">+{fmtNum(stats?.today_registrations)} today</div>
      </div>
      <div className="ap-stat-card ap-stat-card--green">
        <div className="ap-stat-icon">✅</div>
        <div className="ap-stat-value">{fmtNum(stats?.active_users)}</div>
        <div className="ap-stat-label">Active Users</div>
      </div>
      <div className="ap-stat-card ap-stat-card--gold">
        <div className="ap-stat-icon">🏆</div>
        <div className="ap-stat-value">{fmtNum(stats?.verified_users)}</div>
        <div className="ap-stat-label">Verified Users</div>
      </div>
      <div className="ap-stat-card ap-stat-card--pink">
        <div className="ap-stat-icon">💰</div>
        <div className="ap-stat-value">{fmtCur(stats?.total_balance)}</div>
        <div className="ap-stat-label">Total Balance</div>
      </div>
      <div className="ap-stat-card ap-stat-card--purple">
        <div className="ap-stat-icon">📈</div>
        <div className="ap-stat-value">{fmtNum(uStats?.new_users_30d)}</div>
        <div className="ap-stat-label">New (30 Days)</div>
      </div>
      <div className="ap-stat-card ap-stat-card--orange">
        <div className="ap-stat-icon">⚖️</div>
        <div className="ap-stat-value">{fmtCur(uStats?.average_balance)}</div>
        <div className="ap-stat-label">Avg Balance</div>
      </div>
    </div>

    {/* Revenue + Users by Role */}
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(280px,1fr))',gap:'16px'}}>
      {rStats&&<div className="ap-settings-card">
        <div className="ap-settings-title">💵 Revenue Statistics</div>
        <div className="ap-kv-grid">
          <KV k="Total Revenue"    v={fmtCur(rStats.total_revenue)}/>
          <KV k="Monthly Revenue"  v={fmtCur(rStats.monthly_revenue)}/>
          <KV k="Pending Payouts"  v={fmtCur(rStats.pending_payouts)}/>
        </div>
      </div>}
      {uStats?.users_by_role&&<div className="ap-settings-card">
        <div className="ap-settings-title">👤 Users by Role</div>
        {Array.isArray(uStats.users_by_role)
          ? uStats.users_by_role.map(r=>(
              <div key={r.role} className="ap-setting-row">
                <span className="ap-setting-key">{r.role||'N/A'}</span>
                <span className="ap-badge ap-badge--cyan">{r.count}</span>
              </div>
            ))
          : <div className="ap-td-muted" style={{fontSize:'.82rem'}}>No role data</div>
        }
      </div>}
    </div>
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 2 — Settings
// ══════════════════════════════════════════════════════════════════
function SettingsTab(){
  const [settings,  setSettings]  = useState(null);
  const [maint,     setMaint]     = useState(null);
  const [payment,   setPayment]   = useState(null);
  const [referral,  setReferral]  = useState(null);
  const [rewards,   setRewards]   = useState(null);
  const [withdrawal,setWithdrawal]= useState(null);
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState('');
  const [success,   setSuccess]   = useState('');
  const [editModal, setEditModal] = useState(null);
  const [editForm,  setEditForm]  = useState({});
  const [maintForm, setMaintForm] = useState({enable:false,message:'',expected_end:''});

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.settingsAdmin(), api.maintenanceStatus(),
      api.paymentGateways(), api.referralSettings(),
      api.rewardPoints(), api.withdrawalSettings(),
    ]);
    const get = (r) => r.status==='fulfilled' ? (r.value?.data?.data || r.value?.data) : null;
    setSettings(get(results[0]));
    setMaint(get(results[1]));
    setPayment(get(results[2]));
    setReferral(get(results[3]));
    setRewards(get(results[4]));
    setWithdrawal(get(results[5]));
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const handleUpdate = async () => {
    setSaving(true); setError(''); setSuccess('');
    try{
      let payload = editForm;
      if(editForm.site_logo instanceof File || editForm.site_favicon instanceof File){
        const fd = new FormData();
        Object.entries(editForm).forEach(([k,v])=>{ if(v!==undefined && v!==null) fd.append(k,v); });
        payload = fd;
      }
      await api.updateSettings(payload);
      setSuccess('Settings updated!');
      setEditModal(null);
      load();
    } catch(e){ setError(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleMaintenance = async () => {
    setSaving(true); setError(''); setSuccess('');
    try{
      await api.toggleMaintenance(maintForm);
      setSuccess(`Maintenance mode ${maintForm.enable?'enabled':'disabled'}!`);
      load();
    } catch(e){ setError(errMsg(e)); } finally{ setSaving(false); }
  };

  if(loading) return <Skeleton/>;

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">System Settings</h2><p className="ap-tab-sub">Platform configuration and controls</p></div>
      <button className="ap-btn ap-btn--ghost ap-btn--sm" onClick={load}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {success&&<div className="ap-form-success">{success}</div>}

    {/* Maintenance Banner */}
    {maint?.active&&<div className="ap-maint-banner">
      <div className="ap-maint-icon">⚠️</div>
      <div className="ap-maint-txt"><strong>Maintenance Mode Active</strong> — {maint.message||'System under maintenance'}</div>
    </div>}

    <div className="ap-settings-grid">
      {/* Site Info */}
      {settings&&<div className="ap-settings-card">
        <div className="ap-settings-title">🌐 Site Information</div>
        {[['Site Name','site_name'],['Tagline','site_tagline'],['Currency','currency_code'],['Currency Symbol','currency_symbol'],['Contact Email','contact_email']].map(([label,key])=>(
          <div key={key} className="ap-setting-row">
            <span className="ap-setting-key">{label}</span>
            <span className="ap-setting-val">{settings[key]||'—'}</span>
          </div>
        ))}
        <button className="ap-btn ap-btn--cyan ap-btn--sm" style={{marginTop:'10px'}} onClick={()=>{ setEditForm({site_name:settings.site_name,site_tagline:settings.site_tagline,contact_email:settings.contact_email,currency_code:settings.currency_code,currency_symbol:settings.currency_symbol}); setEditModal('site'); }}>
          <Icon.Edit2 size={12}/> Edit
        </button>
      </div>}

      {/* Maintenance Control */}
      <div className="ap-settings-card">
        <div className="ap-settings-title">🔧 Maintenance Mode</div>
        <div className="ap-setting-row">
          <span className="ap-setting-key">Status</span>
          <span className={`ap-badge ap-badge--${maint?.active?'red':'green'}`}>{maint?.active?'ACTIVE':'INACTIVE'}</span>
        </div>
        {maint?.message&&<div className="ap-setting-row"><span className="ap-setting-key">Message</span><span className="ap-setting-val">{maint.message}</span></div>}
        <div style={{marginTop:'12px',display:'flex',flexDirection:'column',gap:'8px'}}>
          <Field label="Enable">
            <label className="ap-toggle" onClick={()=>setMaintForm(f=>({...f,enable:!f.enable}))}>
              <input type="checkbox" checked={!!maintForm.enable} readOnly/>
              <span className="ap-toggle-slider"/>
            </label>
          </Field>
          <Field label="Message">
            <input className="ap-input" value={maintForm.message} onChange={e=>setMaintForm(f=>({...f,message:e.target.value}))} placeholder="Maintenance message..."/>
          </Field>
          <button className="ap-btn ap-btn--orange ap-btn--sm" onClick={handleMaintenance} disabled={saving}>
            <Icon.Tool size={12}/> {maintForm.enable?'Enable':'Disable'} Maintenance
          </button>
        </div>
      </div>

      {/* Payment Gateways */}
      {payment&&<div className="ap-settings-card">
        <div className="ap-settings-title">💳 Payment Gateways</div>
        {[['bKash','enable_bkash'],['Nagad','enable_nagad'],['Rocket','enable_rocket'],['Stripe','enable_stripe'],['PayPal','enable_paypal'],['Bank Transfer','enable_bank_transfer']].map(([label,key])=>(
          <div key={key} className="ap-setting-row">
            <span className="ap-setting-key">{label}</span>
            <span className={`ap-badge ap-badge--${payment[key]?'green':'muted'}`}>{payment[key]?'ON':'OFF'}</span>
          </div>
        ))}
      </div>}

      {/* Withdrawal Settings */}
      {withdrawal&&<div className="ap-settings-card">
        <div className="ap-settings-title">💸 Withdrawal Settings</div>
        {[['Min Amount','min_withdrawal_amount'],['Max Amount','max_withdrawal_amount'],['Fee %','withdrawal_fee_percentage'],['Fixed Fee','withdrawal_fee_fixed'],['Tax %','tax_percentage']].map(([label,key])=>(
          <div key={key} className="ap-setting-row">
            <span className="ap-setting-key">{label}</span>
            <span className="ap-setting-val">{withdrawal[key]??'—'}</span>
          </div>
        ))}
        <button className="ap-btn ap-btn--cyan ap-btn--sm" style={{marginTop:'10px'}} onClick={()=>{ setEditForm({min_withdrawal_amount:withdrawal.min_withdrawal_amount,max_withdrawal_amount:withdrawal.max_withdrawal_amount,withdrawal_fee_percentage:withdrawal.withdrawal_fee_percentage}); setEditModal('withdrawal'); }}>
          <Icon.Edit2 size={12}/> Edit Limits
        </button>
      </div>}

      {/* Referral Settings */}
      {referral&&<div className="ap-settings-card">
        <div className="ap-settings-title">🔗 Referral System</div>
        {[['Enabled','enable_referral'],['Levels','referral_levels'],['Level 1 %','referral_percentage_level1'],['Level 2 %','referral_percentage_level2'],['Level 3 %','referral_percentage_level3'],['Expiry Days','referral_expiry_days']].map(([label,key])=>(
          <div key={key} className="ap-setting-row">
            <span className="ap-setting-key">{label}</span>
            <span className="ap-setting-val">{typeof referral[key]==='boolean'?(referral[key]?'Yes':'No'):(referral[key]??'—')}</span>
          </div>
        ))}
      </div>}

      {/* Reward Points */}
      {rewards&&<div className="ap-settings-card">
        <div className="ap-settings-title">⭐ Reward Points</div>
        {[['Point Value','point_value'],['Ad Click','ad_click_points'],['Video Watch','video_watch_points'],['Survey Complete','survey_complete_points'],['Task Complete','task_complete_points'],['Daily Login Bonus','daily_login_bonus'],['Welcome Bonus','welcome_bonus_points'],['Referral Bonus','referral_bonus_points']].map(([label,key])=>(
          <div key={key} className="ap-setting-row">
            <span className="ap-setting-key">{label}</span>
            <span className="ap-setting-val">{rewards[key]??'—'}</span>
          </div>
        ))}
        <button className="ap-btn ap-btn--cyan ap-btn--sm" style={{marginTop:'10px'}} onClick={()=>{ setEditForm({ad_click_points:rewards.ad_click_points,video_watch_points:rewards.video_watch_points,task_complete_points:rewards.task_complete_points,survey_complete_points:rewards.survey_complete_points}); setEditModal('rewards'); }}>
          <Icon.Edit2 size={12}/> Edit Points
        </button>
      </div>}
    </div>

    {/* Edit Modals */}
    {editModal&&<Modal title={editModal==='site'?'Edit Site Info':editModal==='withdrawal'?'Edit Withdrawal Limits':'Edit Reward Points'} onClose={()=>setEditModal(null)}>
      <div className="ap-form">
        {Object.entries(editForm).map(([k,v])=>(
          <Field key={k} label={k.replace(/_/g,' ')}>
            <input className="ap-input" value={v??''} onChange={e=>setEditForm(f=>({...f,[k]:e.target.value}))}/>
          </Field>
        ))}
        {editModal==='site'&&<>
          <Field label="Site Logo">
            <input type="file" accept="image/*" className="ap-input" onChange={e=>setEditForm(f=>({...f,site_logo:e.target.files[0]}))}/>
            {settings?.site_logo&&<img src={settings.site_logo} alt="logo" style={{height:40,marginTop:6}}/>}
          </Field>
          <Field label="Site Favicon">
            <input type="file" accept="image/*" className="ap-input" onChange={e=>setEditForm(f=>({...f,site_favicon:e.target.files[0]}))}/>
            {settings?.site_favicon&&<img src={settings.site_favicon} alt="favicon" style={{height:24,marginTop:6}}/>}
          </Field>
        </>}
        {error&&<div className="ap-form-error">{error}</div>}
        <div className="ap-form-actions">
          <button className="ap-btn ap-btn--ghost" onClick={()=>setEditModal(null)}>Cancel</button>
          <button className="ap-btn ap-btn--cyan" onClick={handleUpdate} disabled={saving}>{saving?'Saving…':'Save Changes'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 3 — Notifications
// ══════════════════════════════════════════════════════════════════
const NOTIF_TYPES = ['INFO','SUCCESS','WARNING','ERROR','MAINTENANCE','UPDATE','PROMOTION'];

function NotificationsTab(){
  const [notifs,  setNotifs]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [modal,   setModal]   = useState(null);
  const [target,  setTarget]  = useState(null);
  const [form,    setForm]    = useState({});
  const [saving,  setSaving]  = useState(false);

  const F = (k,v) => setForm(f=>({...f,[k]:v}));

  const load = useCallback(async () => {
    setLoading(true);
    try{ const r = await api.notifList(); setNotifs(safeArr(r.data)); }
    catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, []);

  useEffect(() => { load(); }, []);

  const openCreate = () => { setTarget(null); setForm({title:'',message:'',notification_type:'INFO',priority:0,is_active:true,show_on_login:false}); setModal('form'); };
  const openEdit   = t  => { setTarget(t); setForm({...t}); setModal('form'); };

  const handleSave = async () => {
    setSaving(true);
    try{
      if(target) await api.notifUpdate(target.id, form);
      else       await api.notifCreate(form);
      setModal(null); load();
    } catch(e){ setError(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleDelete = async t => {
    if(!confirm(`Delete "${t.title}"?`)) return;
    try{ await api.notifDelete(t.id); load(); } catch(e){ alert(errMsg(e)); }
  };

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">Site Notifications</h2><p className="ap-tab-sub">Platform-wide announcements and alerts</p></div>
      <button className="ap-btn ap-btn--cyan" onClick={openCreate}><Icon.Plus size={14}/> New Notification</button>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {loading?<Skeleton/>:notifs.length===0?<Empty icon="🔔" text="No notifications"/>:
      <div className="ap-notif-list">
        {notifs.map(n=>(
          <div key={n.id} className={`ap-notif-card ap-notif-card--${n.notification_type}`}>
            <div style={{flex:1}}>
              <div className="ap-notif-title">{n.title}</div>
              <div className="ap-notif-message">{n.message}</div>
              <div className="ap-notif-meta">
                <NotifBadge type={n.notification_type}/>
                <span className={`ap-badge ap-badge--${n.is_active?'green':'muted'}`}>{n.is_active?'Active':'Inactive'}</span>
                {n.show_on_login&&<span className="ap-badge ap-badge--purple">Show on Login</span>}
                <span style={{fontSize:'.72rem',color:'var(--ap-muted)'}}>Priority: {n.priority}</span>
                <span style={{fontSize:'.72rem',color:'var(--ap-muted)'}}>{fmtDate(n.created_at)}</span>
              </div>
            </div>
            <div className="ap-actions">
              <button className="ap-icon-btn ap-icon-btn--cyan" onClick={()=>openEdit(n)}><Icon.Edit2 size={13}/></button>
              <button className="ap-icon-btn ap-icon-btn--red"  onClick={()=>handleDelete(n)}><Icon.Trash2 size={13}/></button>
            </div>
          </div>
        ))}
      </div>
    }
    {modal==='form'&&<Modal title={target?'Edit Notification':'New Notification'} onClose={()=>setModal(null)}>
      <div className="ap-form">
        <Field label="Title *"><input className="ap-input" value={form.title||''} onChange={e=>F('title',e.target.value)} placeholder="Notification title"/></Field>
        <Field label="Message *"><textarea className="ap-textarea" rows={3} value={form.message||''} onChange={e=>F('message',e.target.value)} placeholder="Notification message..."/></Field>
        <div className="ap-form-row">
          <Field label="Type">
            <select className="ap-select" value={form.notification_type||'INFO'} onChange={e=>F('notification_type',e.target.value)}>
              {NOTIF_TYPES.map(t=><option key={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Priority"><input className="ap-input" type="number" value={form.priority??0} onChange={e=>F('priority',Number(e.target.value))}/></Field>
        </div>
        <div className="ap-form-row">
          <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
            <input type="checkbox" checked={!!form.is_active} onChange={e=>F('is_active',e.target.checked)} style={{accentColor:'var(--ap-green)',width:'15px',height:'15px'}}/> Active
          </label>
          <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
            <input type="checkbox" checked={!!form.show_on_login} onChange={e=>F('show_on_login',e.target.checked)} style={{accentColor:'var(--ap-cyan)',width:'15px',height:'15px'}}/> Show on Login
          </label>
        </div>
        <div className="ap-form-row">
          <Field label="Start Date"><input className="ap-input" type="datetime-local" value={form.start_date||''} onChange={e=>F('start_date',e.target.value)}/></Field>
          <Field label="End Date"><input className="ap-input" type="datetime-local" value={form.end_date||''} onChange={e=>F('end_date',e.target.value)}/></Field>
        </div>
        <div className="ap-form-actions">
          <button className="ap-btn ap-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="ap-btn ap-btn--cyan" onClick={handleSave} disabled={saving}>{saving?'Saving…':target?'Update':'Create'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 4 — Site Contents
// ══════════════════════════════════════════════════════════════════
const CONTENT_TYPES = ['PAGE','SECTION','BANNER','FOOTER','SIDEBAR','POPUP'];

function ContentsTab(){
  const [contents, setContents] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [typeF,    setTypeF]    = useState('');
  const [modal,    setModal]    = useState(null);
  const [target,   setTarget]   = useState(null);
  const [form,     setForm]     = useState({});
  const [saving,   setSaving]   = useState(false);

  const F = (k,v) => setForm(f=>({...f,[k]:v}));

  const load = useCallback(async () => {
    setLoading(true);
    try{
      const params = typeF ? { content_type: typeF } : {};
      const r = await api.contentList(params);
      setContents(safeArr(r.data));
    } catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, [typeF]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setTarget(null); setForm({identifier:'',title:'',content:'',content_type:'PAGE',language:'en',is_active:true,order:0}); setModal('form'); };
  const openEdit   = t  => { setTarget(t); setForm({...t}); setModal('form'); };

  const handleSave = async () => {
    setSaving(true);
    try{
      if(target) await api.contentUpdate(target.identifier, form);
      else       await api.contentCreate(form);
      setModal(null); load();
    } catch(e){ setError(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleDelete = async t => {
    if(!confirm(`Delete "${t.title}"?`)) return;
    try{ await api.contentDelete(t.identifier); load(); } catch(e){ alert(errMsg(e)); }
  };

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">Site Contents</h2><p className="ap-tab-sub">Dynamic pages, banners, and content blocks</p></div>
      <div className="ap-header-acts">
        <select className="ap-select" value={typeF} onChange={e=>setTypeF(e.target.value)} style={{width:'auto'}}>
          <option value="">All Types</option>{CONTENT_TYPES.map(t=><option key={t}>{t}</option>)}
        </select>
        <button className="ap-btn ap-btn--cyan" onClick={openCreate}><Icon.Plus size={14}/> New Content</button>
      </div>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {loading?<Skeleton/>:contents.length===0?<Empty icon="📄" text="No contents found"/>:
      <div className="ap-content-list">
        {contents.map(c=>(
          <div key={c.id||c.identifier} className="ap-content-card">
            <div style={{flex:1}}>
              <div className="ap-content-title">{c.title}</div>
              <div className="ap-content-id">{c.identifier}</div>
              <div className="ap-content-meta">
                <span className="ap-badge ap-badge--cyan">{c.content_type}</span>
                <span className={`ap-badge ap-badge--${c.is_active?'green':'muted'}`}>{c.is_active?'Active':'Inactive'}</span>
                <span className="ap-badge ap-badge--muted">{c.language?.toUpperCase()}</span>
                <span style={{fontSize:'.72rem',color:'var(--ap-muted)'}}>Order: {c.order}</span>
              </div>
              {c.content&&<div className="ap-content-preview">{c.content.slice(0,120)}{c.content.length>120?'…':''}</div>}
            </div>
            <div className="ap-actions">
              <button className="ap-icon-btn ap-icon-btn--cyan" onClick={()=>openEdit(c)}><Icon.Edit2 size={13}/></button>
              <button className="ap-icon-btn ap-icon-btn--red"  onClick={()=>handleDelete(c)}><Icon.Trash2 size={13}/></button>
            </div>
          </div>
        ))}
      </div>
    }
    {modal==='form'&&<Modal title={target?'Edit Content':'New Content'} onClose={()=>setModal(null)} wide>
      <div className="ap-form">
        <div className="ap-form-row">
          <Field label="Identifier (slug) *"><input className="ap-input" value={form.identifier||''} onChange={e=>F('identifier',e.target.value)} placeholder="e.g. about-us" disabled={!!target}/></Field>
          <Field label="Title *"><input className="ap-input" value={form.title||''} onChange={e=>F('title',e.target.value)}/></Field>
        </div>
        <div className="ap-form-row">
          <Field label="Content Type">
            <select className="ap-select" value={form.content_type||'PAGE'} onChange={e=>F('content_type',e.target.value)}>
              {CONTENT_TYPES.map(t=><option key={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Language"><input className="ap-input" value={form.language||'en'} onChange={e=>F('language',e.target.value)}/></Field>
          <Field label="Order"><input className="ap-input" type="number" value={form.order??0} onChange={e=>F('order',Number(e.target.value))}/></Field>
        </div>
        <Field label="Content *"><textarea className="ap-textarea" rows={6} value={form.content||''} onChange={e=>F('content',e.target.value)} placeholder="Page content or HTML..."/></Field>
        <div className="ap-form-row">
          <Field label="Meta Title"><input className="ap-input" value={form.meta_title||''} onChange={e=>F('meta_title',e.target.value)}/></Field>
          <Field label="Meta Keywords"><input className="ap-input" value={form.meta_keywords||''} onChange={e=>F('meta_keywords',e.target.value)}/></Field>
        </div>
        <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
          <input type="checkbox" checked={!!form.is_active} onChange={e=>F('is_active',e.target.checked)} style={{accentColor:'var(--ap-green)',width:'15px',height:'15px'}}/> Active
        </label>
        <div className="ap-form-actions">
          <button className="ap-btn ap-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="ap-btn ap-btn--cyan" onClick={handleSave} disabled={saving}>{saving?'Saving…':target?'Update':'Create'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 5 — Reports
// ══════════════════════════════════════════════════════════════════
const REPORT_TYPES = ['user','payment','revenue','activity'];
const STATUS_COLORS = { pending:'gold', processing:'cyan', completed:'green', failed:'red' };

function ReportsTab(){
  const [reports,  setReports]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [modal,    setModal]    = useState(false);
  const [form,     setForm]     = useState({ report_type:'user', parameters:{} });
  const [saving,   setSaving]   = useState(false);
  const [genMsg,   setGenMsg]   = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try{ const r = await api.reportList(); setReports(safeArr(r.data)); }
    catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, []);

  useEffect(() => { load(); }, []);

  const handleGenerate = async () => {
    setSaving(true); setGenMsg('');
    try{
      const r = await api.generateReport(form);
      setGenMsg(`Report queued: ${r.data?.data?.report_id || 'Processing...'}`);
      setModal(false); load();
    } catch(e){ setError(errMsg(e)); } finally{ setSaving(false); }
  };

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">Reports</h2><p className="ap-tab-sub">Generate and download system reports</p></div>
      <div className="ap-header-acts">
        <button className="ap-btn ap-btn--ghost ap-btn--sm" onClick={load}><Icon.RefreshCw size={13}/> Refresh</button>
        <button className="ap-btn ap-btn--cyan" onClick={()=>setModal(true)}><Icon.FileText size={14}/> Generate Report</button>
      </div>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {genMsg&&<div className="ap-form-success">{genMsg}</div>}
    {loading?<Skeleton/>:reports.length===0?<Empty icon="📊" text="No reports generated yet"/>:
      <div className="ap-report-list">
        {reports.map(r=>(
          <div key={r.id} className="ap-report-card">
            <div>
              <div className="ap-report-title">{r.title||r.report_type}</div>
              <div className="ap-report-id">{r.report_id}</div>
            </div>
            <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap'}}>
              <span className="ap-badge ap-badge--cyan">{r.report_type}</span>
              <span className={`ap-badge ap-badge--${STATUS_COLORS[r.status]||'muted'}`}>{r.status}</span>
              <span className="ap-td-muted">{fmtDate(r.generated_at)}</span>
              {r.report_file&&<a href={r.report_file} target="_blank" rel="noreferrer" className="ap-icon-btn ap-icon-btn--green"><Icon.Download size={13}/> Download</a>}
            </div>
          </div>
        ))}
      </div>
    }
    {modal&&<Modal title="Generate New Report" onClose={()=>setModal(false)}>
      <div className="ap-form">
        <Field label="Report Type">
          <select className="ap-select" value={form.report_type} onChange={e=>setForm(f=>({...f,report_type:e.target.value}))}>
            {REPORT_TYPES.map(t=><option key={t}>{t}</option>)}
          </select>
        </Field>
        <div className="ap-form-actions">
          <button className="ap-btn ap-btn--ghost" onClick={()=>setModal(false)}>Cancel</button>
          <button className="ap-btn ap-btn--cyan" onClick={handleGenerate} disabled={saving}>{saving?'Generating…':'Generate'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 6 — Action Log
// ══════════════════════════════════════════════════════════════════
const ACTION_ICONS = { user_ban:'🚫', user_unban:'✅', payment_approve:'💰', payment_reject:'❌', content_delete:'🗑️', setting_change:'⚙️' };

function ActionLogTab(){
  const [actions,  setActions]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try{ const r = await api.actionList(); setActions(safeArr(r.data)); }
    catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, []);

  useEffect(() => { load(); }, []);

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">Admin Action Log</h2><p className="ap-tab-sub">Audit trail of all admin actions</p></div>
      <button className="ap-btn ap-btn--ghost ap-btn--sm" onClick={load}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {loading?<Skeleton/>:actions.length===0?<Empty icon="📋" text="No admin actions recorded"/>:
      <div className="ap-action-log">
        {actions.map(a=>(
          <div key={a.id} className="ap-action-item">
            <div className="ap-action-icon">{ACTION_ICONS[a.action_type]||'⚡'}</div>
            <div style={{flex:1}}>
              <div className="ap-action-desc">{a.description}</div>
              <div style={{display:'flex',gap:'8px',marginTop:'3px',flexWrap:'wrap'}}>
                <span className="ap-action-admin">{a.admin?.username||a.admin}</span>
                {a.target_user&&<span className="ap-td-muted">→ {a.target_user?.username||a.target_user}</span>}
                <span className="ap-badge ap-badge--muted">{a.action_type?.replace(/_/g,' ')}</span>
              </div>
            </div>
            <div className="ap-action-time">{fmtDate(a.created_at)}</div>
          </div>
        ))}
      </div>
    }
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 7 — System Health
// ══════════════════════════════════════════════════════════════════
function HealthTab(){
  const [health,   setHealth]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try{ const r = await api.health(); setHealth(r.data); }
    catch(e){ setError(errMsg(e)); } finally{ setLoading(false); }
  }, []);

  useEffect(() => { load(); }, []);

  const overall = health?.status;
  const statusColor = { healthy:'green', degraded:'gold', unhealthy:'red' };

  return <div className="ap-tab-content">
    <div className="ap-tab-header">
      <div><h2 className="ap-tab-title">System Health</h2><p className="ap-tab-sub">Real-time service status</p></div>
      <button className="ap-btn ap-btn--ghost ap-btn--sm" onClick={load}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>
    {error&&<div className="ap-error">{error}</div>}
    {loading?<Skeleton/>:health&&<>
      <div style={{display:'flex',alignItems:'center',gap:'12px',marginBottom:'1.5rem'}}>
        <div className={`ap-health-indicator ap-health-indicator--${overall}`} style={{width:'16px',height:'16px'}}/>
        <span className={`ap-badge ap-badge--${statusColor[overall]||'muted'}`} style={{fontSize:'.8rem',padding:'4px 12px'}}>{overall?.toUpperCase()}</span>
        <span className="ap-td-muted" style={{fontSize:'.78rem'}}>{fmtDate(health.timestamp)}</span>
      </div>
      <div className="ap-health-grid">
        {Object.entries(health.services||{}).map(([name,status])=>(
          <div key={name} className="ap-health-card">
            <div className={`ap-health-indicator ap-health-indicator--${status}`}/>
            <div>
              <div className="ap-health-name">{name}</div>
              <div className="ap-health-status">{status}</div>
            </div>
          </div>
        ))}
      </div>
    </>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════
const TABS = [
  { id:'dashboard',   label:'Dashboard',    icon:<Icon.BarChart2 size={15}/> },
  { id:'settings',    label:'Settings',     icon:<Icon.Settings size={15}/> },
  { id:'notifications',label:'Notifications',icon:<Icon.Bell size={15}/> },
  { id:'contents',    label:'Site Contents',icon:<Icon.FileText size={15}/> },
  { id:'reports',     label:'Reports',      icon:<Icon.PieChart size={15}/> },
  { id:'actions',     label:'Action Log',   icon:<Icon.List size={15}/> },
  { id:'health',      label:'Health',       icon:<Icon.Activity size={15}/> },
];

export default function AdminPanel(){
  const [activeTab, setActiveTab] = useState('dashboard');
  return <div className="ap-root">
    <div className="ap-page-header">
      <div className="ap-page-header-inner">
        <div className="ap-page-title-wrap">
          <span className="ap-page-icon">⚙️</span>
          <div>
            <h1 className="ap-page-title">ADMIN PANEL</h1>
            <p className="ap-page-sub">System configuration, monitoring and management</p>
          </div>
        </div>
        <div className="ap-header-status">
          <div className="ap-status-dot"/>
          <span className="ap-status-txt">SYSTEM ONLINE</span>
        </div>
      </div>
      <div className="ap-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={`ap-tab${activeTab===t.id?' ap-tab--active':''}`} onClick={()=>setActiveTab(t.id)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>
    </div>
    <div className="ap-content">
      {activeTab==='dashboard'     && <DashboardTab/>}
      {activeTab==='settings'      && <SettingsTab/>}
      {activeTab==='notifications' && <NotificationsTab/>}
      {activeTab==='contents'      && <ContentsTab/>}
      {activeTab==='reports'       && <ReportsTab/>}
      {activeTab==='actions'       && <ActionLogTab/>}
      {activeTab==='health'        && <HealthTab/>}
    </div>
  </div>;
}
