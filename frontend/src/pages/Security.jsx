// src/pages/Security.jsx  — Full CRUD
import { useState } from 'react';
import * as Icon from 'react-feather';
import {
  useSecurityDashboard, useSecurityLogs, useDevices,
  useUserBans, useIPBlacklist, useSessions, useAuditTrail,
} from '../hooks/useSecurity';
import securityAPI from '../api/endpoints/security';
import '../styles/Security.css';

// ── Helpers ────────────────────────────────────────────────
const errMsg = e => {
  const d = e?.response?.data;
  if (!d) return e?.message || 'Error';
  if (typeof d === 'string') return d;
  if (d.detail) return d.detail;
  return Object.entries(d).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
};
const fmt  = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
const arr  = d => Array.isArray(d) ? d : (d?.results ?? []);
const SEV  = { critical:'r', high:'o', medium:'g', low:'n' };
const THLV = { critical:'r', confirmed_attacker:'r', high:'o', medium:'g', low:'n' };

// ── Shared UI ──────────────────────────────────────────────
const Skel = () => <div className="sc-skel">{[1,2,3,4,5].map(i=><div key={i} className="sc-skel-row"/>)}</div>;
const Empty = ({icon,txt}) => <div className="sc-empty"><div className="sc-empty-ico">{icon}</div><p className="sc-empty-txt">{txt}</p></div>;
const Fld = ({label,children}) => <div className="sc-field"><label className="sc-lbl">{label}</label>{children}</div>;
const KV  = ({k,v}) => <div className="kv"><span className="kv-k">{k}</span><span className="kv-v">{v??'—'}</span></div>;

function Modal({title,onClose,wide,children}){
  return <div className="modal-bg" onClick={e=>e.target===e.currentTarget&&onClose()}>
    <div className={`modal${wide?' wide':''}`}>
      <div className="modal-hdr">
        <h3 className="modal-title">{title}</h3>
        <button className="modal-close" onClick={onClose}><Icon.X size={18}/></button>
      </div>
      <div className="modal-body">{children}</div>
    </div>
  </div>;
}

function Confirm({title,text,onConfirm,onCancel,saving,btnLabel='Delete',btnClass='r'}){
  return <div className="sc-form">
    <div className="danger-box">
      <p className="danger-box-title">{title}</p>
      <p className="danger-box-text">{text}</p>
    </div>
    <div className="sc-form-foot">
      <button className="btn ghost" onClick={onCancel}>Cancel</button>
      <button className={`btn ${btnClass}`} onClick={onConfirm} disabled={saving}>{saving?'Please wait…':btnLabel}</button>
    </div>
  </div>;
}

function RiskBar({score}){
  const p = Math.min(Number(score)||0,100);
  const c = p>=80?'crit':p>=60?'high':p>=40?'med':'low';
  return <div className="risk-wrap">
    <div className="risk-bar"><div className={`risk-fill rf-${c}`} style={{width:`${p}%`}}/></div>
    <span className="risk-num">{p}</span>
  </div>;
}
function SevBadge({v}){ return <span className={`badge ${SEV[v]||'muted'}`}>{v||'—'}</span>; }
function ThreatBadge({v}){ return <div className="tdot-wrap"><div className={`tdot ${v}`}/><span className={`badge ${THLV[v]||'muted'}`}>{v?.replace(/_/g,' ')||'—'}</span></div>; }

// ══════════════════════════════════════════════════════════
// TAB 1 — Dashboard
// ══════════════════════════════════════════════════════════
function DashboardTab(){
  const {dashboard,loading,error,refetch,totalThreats,threatsBlocked,threatsPending,highRiskUsers,criticalRiskUsers} = useSecurityDashboard();
  if(loading) return <Skel/>;
  if(error)   return <div className="sc-alert">{error}</div>;
  const d=dashboard||{}, s=d.summary||{}, r=d.risk_analysis||{};
  return <div className="sc-pane">
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">Security Overview</h2><p className="sc-pane-sub">Real-time threat intelligence</p></div>
      <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>
    <div className="sc-grid">
      {[
        {ico:'⚠️',val:totalThreats,    lbl:'Total Threats',  cls:'r'},
        {ico:'🛡️',val:threatsBlocked,  lbl:'Blocked',        cls:'n'},
        {ico:'🕐',val:threatsPending,  lbl:'Pending',        cls:'o'},
        {ico:'👤',val:highRiskUsers,   lbl:'High Risk Users',cls:'g'},
        {ico:'💀',val:criticalRiskUsers,lbl:'Critical Risk', cls:'r'},
        {ico:'📊',val:s.total_users||'—',lbl:'Total Users',  cls:'c'},
      ].map((x,i)=>(
        <div key={i} className={`sc-card ${x.cls}`}>
          <div className="sc-card-ico">{x.ico}</div>
          <div className="sc-card-val">{x.val}</div>
          <div className="sc-card-lbl">{x.lbl}</div>
        </div>
      ))}
    </div>
    {/* Risk breakdown */}
    {r && Object.keys(r).length>0 && (
      <div className="detail-box">
        <div style={{fontFamily:'var(--fh)',fontSize:'.72rem',fontWeight:700,letterSpacing:'.1em',color:'var(--sm)',marginBottom:'12px',textTransform:'uppercase'}}>Risk Analysis</div>
        <div className="kv-grid">
          {Object.entries(r).map(([k,v])=><KV key={k} k={k.replace(/_/g,' ')} v={String(v)}/>)}
        </div>
      </div>
    )}
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 2 — Security Logs (Read + Resolve)
// ══════════════════════════════════════════════════════════
function LogsTab(){
  const {logs,loading,error,setParams,refetch} = useSecurityLogs();
  const [sevF,setSevF]   = useState('');
  const [typeF,setTypeF] = useState('');
  const [detail,setDetail] = useState(null);
  const [resolveModal,setResolveModal] = useState(null);
  const [resolveNote,setResolveNote]   = useState('');
  const [saving,setSaving] = useState(false);
  const [msg,setMsg]       = useState('');

  const applyF = (s,t) => setParams({...(s&&{severity:s}),...(t&&{security_type:t})});

  const handleResolve = async () => {
    setSaving(true); setMsg('');
    try {
      await securityAPI.resolveLog(resolveModal.id,{resolution_note:resolveNote});
      setMsg('Resolved!'); setResolveModal(null); setResolveNote('');
      refetch();
    } catch(e){ setMsg(errMsg(e)); }
    finally{ setSaving(false); }
  };

  const list = arr(logs);
  return <div className="sc-pane">
    <div className="sc-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(110px,1fr))'}}>
      {[
        {val:list.filter(l=>l.severity==='critical').length,lbl:'Critical',cls:'r'},
        {val:list.filter(l=>l.severity==='high').length,lbl:'High',cls:'o'},
        {val:list.filter(l=>l.severity==='medium').length,lbl:'Medium',cls:'g'},
        {val:list.length,lbl:'Total',cls:'c'},
      ].map((x,i)=><div key={i} className={`sc-card ${x.cls}`}><div className="sc-card-val">{x.val}</div><div className="sc-card-lbl">{x.lbl}</div></div>)}
    </div>
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">Security Logs</h2><p className="sc-pane-sub">All security events</p></div>
      <div className="sc-acts">
        <select className="sc-fsel" value={sevF} onChange={e=>{setSevF(e.target.value);applyF(e.target.value,typeF);}}>
          <option value="">All Severity</option>
          {['low','medium','high','critical'].map(s=><option key={s}>{s}</option>)}
        </select>
        <select className="sc-fsel" value={typeF} onChange={e=>{setTypeF(e.target.value);applyF(sevF,e.target.value);}}>
          <option value="">All Types</option>
          {['login','logout','failed_login','password_change','permission_denied','access_denied','success'].map(t=><option key={t}>{t}</option>)}
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
      </div>
    </div>
    {msg&&<div className="sc-success">{msg}</div>}
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="📋" txt="No logs"/>:
      <div className="sc-tbl-wrap"><table className="sc-tbl">
        <thead><tr><th>Time</th><th>Type</th><th>Severity</th><th>IP</th><th>User</th><th>Description</th><th>Actions</th></tr></thead>
        <tbody>{list.map((l,i)=>(
          <tr key={l.id||i} className={`row-${l.severity}`}>
            <td className="td-m">{fmt(l.created_at)}</td>
            <td><span className="badge c">{l.security_type||l.event_type||'—'}</span></td>
            <td><SevBadge v={l.severity}/></td>
            <td className="td-mo">{l.ip_address||'—'}</td>
            <td className="td-b">{l.user?.username||l.user||'—'}</td>
            <td className="td-m" style={{maxWidth:'160px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{l.description||'—'}</td>
            <td><div className="sc-row-acts">
              <button className="ibtn c" onClick={()=>setDetail(l)}><Icon.Eye size={13}/></button>
              {!l.resolved&&<button className="ibtn n" onClick={()=>{setResolveModal(l);setResolveNote('');}}><Icon.CheckCircle size={13}/> Resolve</button>}
              {l.resolved&&<span className="badge n">Resolved</span>}
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }
    {detail&&<Modal title="Log Detail" onClose={()=>setDetail(null)}>
      <div className="kv-grid">
        <KV k="ID" v={detail.id}/><KV k="Type" v={detail.security_type}/><KV k="Severity" v={detail.severity}/>
        <KV k="IP" v={detail.ip_address}/><KV k="User" v={detail.user?.username||detail.user}/>
        <KV k="Risk Score" v={detail.risk_score}/><KV k="Response ms" v={detail.response_time_ms}/>
        <KV k="Resolved" v={detail.resolved?'Yes':'No'}/><KV k="Time" v={fmt(detail.created_at)}/>
      </div>
      {detail.description&&<div className="detail-box" style={{marginTop:'12px'}}>
        <div className="kv-k" style={{marginBottom:'4px'}}>Description</div>
        <div style={{fontSize:'.82rem'}}>{detail.description}</div>
      </div>}
      {detail.action_taken&&<div className="detail-box">
        <div className="kv-k" style={{marginBottom:'4px'}}>Action Taken</div>
        <div style={{fontSize:'.82rem'}}>{detail.action_taken}</div>
      </div>}
    </Modal>}
    {resolveModal&&<Modal title="Resolve Log" onClose={()=>setResolveModal(null)}>
      <div className="sc-form">
        <div className="detail-box"><div className="kv-grid">
          <KV k="Event" v={resolveModal.security_type}/><KV k="Severity" v={resolveModal.severity}/>
          <KV k="IP" v={resolveModal.ip_address}/>
        </div></div>
        <Fld label="Resolution Note">
          <textarea className="sc-ta" rows={3} value={resolveNote} onChange={e=>setResolveNote(e.target.value)} placeholder="What action was taken?"/>
        </Fld>
        {msg&&<div className="sc-alert">{msg}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={()=>setResolveModal(null)}>Cancel</button>
          <button className="btn n" onClick={handleResolve} disabled={saving}>{saving?'Saving…':'Mark Resolved'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 3 — Devices (Full CRUD)
// ══════════════════════════════════════════════════════════
function DevicesTab(){
  const {devices,loading,error,refetch,suspiciousCount,rootedCount,emulatorCount} = useDevices();
  const [modal,  setModal]  = useState(null); // 'detail'|'edit'|'blacklist'|'whitelist'|'delete'
  const [sel,    setSel]    = useState(null);
  const [form,   setForm]   = useState({});
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [msg,    setMsg]    = useState('');

  const open = (m,d) => { setSel(d); setModal(m); setErr(''); setReason(''); if(m==='edit') setForm({risk_score:d.risk_score,trust_level:d.trust_level,is_trusted:d.is_trusted}); };
  const close = () => { setModal(null); setSel(null); };

  const handleEdit = async () => {
    setSaving(true); setErr('');
    try { await securityAPI.updateDevice(sel.id,form); setMsg('Device updated'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleBlacklist = async () => {
    setSaving(true); setErr('');
    try { await securityAPI.blacklistDevice(sel.id,{reason}); setMsg('Device blacklisted'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleWhitelist = async () => {
    setSaving(true); setErr('');
    try { await securityAPI.whitelistDevice(sel.id,{reason}); setMsg('Device whitelisted'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleToggleTrust = async (d) => {
    try { await securityAPI.toggleTrust(d.id,{is_trusted:!d.is_trusted}); refetch(); }
    catch(e){ alert(errMsg(e)); }
  };
  const handleDelete = async () => {
    setSaving(true); setErr('');
    try { await securityAPI.deleteDevice(sel.id); setMsg('Device deleted'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const list = arr(devices);
  return <div className="sc-pane">
    <div className="sc-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[{val:list.length,lbl:'Total',cls:'c'},{val:suspiciousCount,lbl:'Suspicious',cls:'o'},{val:rootedCount,lbl:'Rooted',cls:'r'},{val:emulatorCount,lbl:'Emulators',cls:'g'}]
        .map((x,i)=><div key={i} className={`sc-card ${x.cls}`}><div className="sc-card-val">{x.val}</div><div className="sc-card-lbl">{x.lbl}</div></div>)}
    </div>
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">Devices</h2><p className="sc-pane-sub">Device tracking and security management</p></div>
      <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
    </div>
    {msg&&<div className="sc-success">{msg}</div>}
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="📱" txt="No devices"/>:
      <div className="sc-tbl-wrap"><table className="sc-tbl">
        <thead><tr><th>Device</th><th>OS</th><th>User</th><th>Risk</th><th>Flags</th><th>Last Seen</th><th>Actions</th></tr></thead>
        <tbody>{list.map((d,i)=>(
          <tr key={d.id||i}>
            <td><div className="td-b">{d.device_model||'Unknown'}</div><div className="td-mo">{String(d.device_id||'').slice(0,14)||'—'}</div></td>
            <td className="td-m">{d.android_version||d.os_version||'—'}</td>
            <td className="td-b">{d.user?.username||d.user||'—'}</td>
            <td style={{minWidth:'110px'}}><RiskBar score={d.risk_score}/></td>
            <td><div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>
              {d.is_rooted&&<span className="badge r">Rooted</span>}
              {d.is_emulator&&<span className="badge o">Emulator</span>}
              {d.is_vpn&&<span className="badge p">VPN</span>}
              {d.is_trusted&&<span className="badge n">Trusted</span>}
              {!d.is_rooted&&!d.is_emulator&&!d.is_vpn&&<span className="badge muted">Clean</span>}
            </div></td>
            <td className="td-m">{fmt(d.last_activity||d.updated_at)}</td>
            <td><div className="sc-row-acts">
              <button className="ibtn c"   onClick={()=>open('detail',d)}><Icon.Eye size={13}/></button>
              <button className="ibtn g"   onClick={()=>open('edit',d)}><Icon.Edit2 size={13}/></button>
              {d.is_trusted
                ? <button className="ibtn o" onClick={()=>handleToggleTrust(d)} title="Remove trust"><Icon.ShieldOff size={13}/></button>
                : <button className="ibtn n" onClick={()=>handleToggleTrust(d)} title="Trust"><Icon.Shield size={13}/></button>
              }
              <button className="ibtn r"   onClick={()=>open('blacklist',d)}><Icon.X size={13}/> Block</button>
              <button className="ibtn p"   onClick={()=>open('whitelist',d)}><Icon.CheckCircle size={13}/> Allow</button>
              <button className="ibtn r"   onClick={()=>open('delete',d)}><Icon.Trash2 size={13}/></button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {modal==='detail'&&sel&&<Modal title="Device Detail" onClose={close}>
      <div className="kv-grid">
        {['device_model','device_brand','android_version','app_version','last_ip','risk_score','trust_level'].map(k=>(
          <KV key={k} k={k.replace(/_/g,' ')} v={sel[k]}/>
        ))}
        <KV k="Rooted"   v={sel.is_rooted?'Yes':'No'}/>
        <KV k="Emulator" v={sel.is_emulator?'Yes':'No'}/>
        <KV k="VPN"      v={sel.is_vpn?'Yes':'No'}/>
        <KV k="Trusted"  v={sel.is_trusted?'Yes':'No'}/>
      </div>
      <div style={{marginTop:'12px'}}><RiskBar score={sel.risk_score}/></div>
    </Modal>}

    {modal==='edit'&&sel&&<Modal title="Edit Device" onClose={close}>
      <div className="sc-form">
        <div className="sc-form-row">
          <Fld label="Risk Score (0-100)">
            <input className="sc-input" type="number" min="0" max="100" value={form.risk_score||0}
              onChange={e=>setForm(f=>({...f,risk_score:Number(e.target.value)}))}/>
          </Fld>
          <Fld label="Trust Level">
            <select className="sc-sel" value={form.trust_level||1} onChange={e=>setForm(f=>({...f,trust_level:Number(e.target.value)}))}>
              <option value={1}>Low Trust</option>
              <option value={2}>Medium Trust</option>
              <option value={3}>High Trust</option>
            </select>
          </Fld>
        </div>
        <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
          <input type="checkbox" checked={form.is_trusted||false} onChange={e=>setForm(f=>({...f,is_trusted:e.target.checked}))}
            style={{accentColor:'var(--sn)',width:'15px',height:'15px'}}/>
          Mark as Trusted
        </label>
        {err&&<div className="sc-err">{err}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn c" onClick={handleEdit} disabled={saving}>{saving?'Saving…':'Save Changes'}</button>
        </div>
      </div>
    </Modal>}

    {modal==='blacklist'&&sel&&<Modal title="Blacklist Device" onClose={close}>
      <div className="sc-form">
        <div className="detail-box"><div className="kv-grid">
          <KV k="Device" v={sel.device_model}/><KV k="User" v={sel.user?.username||sel.user}/>
        </div></div>
        <Fld label="Reason">
          <textarea className="sc-ta" rows={3} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Reason for blacklisting..."/>
        </Fld>
        {err&&<div className="sc-err">{err}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn r" onClick={handleBlacklist} disabled={saving}>{saving?'Blocking…':'Blacklist Device'}</button>
        </div>
      </div>
    </Modal>}

    {modal==='whitelist'&&sel&&<Modal title="Whitelist Device" onClose={close}>
      <div className="sc-form">
        <div className="detail-box"><div className="kv-grid">
          <KV k="Device" v={sel.device_model}/><KV k="User" v={sel.user?.username||sel.user}/>
        </div></div>
        <Fld label="Reason">
          <textarea className="sc-ta" rows={2} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Reason for whitelisting..."/>
        </Fld>
        {err&&<div className="sc-err">{err}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn n" onClick={handleWhitelist} disabled={saving}>{saving?'Saving…':'Whitelist Device'}</button>
        </div>
      </div>
    </Modal>}

    {modal==='delete'&&sel&&<Modal title="Delete Device" onClose={close}>
      <Confirm title="Delete this device?" text={`This will permanently delete device "${sel.device_model}" (${sel.user?.username||'—'}). This action cannot be undone.`}
        onConfirm={handleDelete} onCancel={close} saving={saving} btnLabel="Delete Device"/>
      {err&&<div className="sc-err" style={{marginTop:'8px'}}>{err}</div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 4 — User Bans (Full CRUD)
// ══════════════════════════════════════════════════════════
function BansTab(){
  const {bans,loading,banning,error,refetch,banUser,unbanUser,permanentBans,temporaryBans} = useUserBans({});
  const [modal,  setModal]  = useState(null); // 'create'|'edit'|'delete'
  const [sel,    setSel]    = useState(null);
  const [form,   setForm]   = useState({user:'',reason:'',is_permanent:false,banned_until:''});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [msg,    setMsg]    = useState('');
  const F = (k,v) => setForm(f=>({...f,[k]:v}));

  const handleCreate = async () => {
    if(!form.user||!form.reason){setErr('User and reason required');return;}
    setErr('');
    try{ await banUser(form); setMsg('User banned'); setModal(null); setForm({user:'',reason:'',is_permanent:false,banned_until:''}); }
    catch(e){ setErr(errMsg(e)); }
  };
  const handleEdit = async () => {
    setSaving(true); setErr('');
    try{ await securityAPI.updateBan(sel.id,form); setMsg('Ban updated'); setModal(null); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleDelete = async () => {
    setSaving(true); setErr('');
    try{ await securityAPI.deleteBan(sel.id); setMsg('Ban deleted'); setModal(null); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleUnban = async ban => {
    const r = prompt('Reason for unbanning:','');
    if(r===null) return;
    try{ await unbanUser(ban.id,r); setMsg('User unbanned'); }
    catch(e){ alert(errMsg(e)); }
  };

  const list = arr(bans);
  return <div className="sc-pane">
    <div className="sc-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[{val:list.length,lbl:'Active Bans',cls:'r'},{val:permanentBans,lbl:'Permanent',cls:'o'},{val:temporaryBans,lbl:'Temporary',cls:'g'}]
        .map((x,i)=><div key={i} className={`sc-card ${x.cls}`}><div className="sc-card-val">{x.val}</div><div className="sc-card-lbl">{x.lbl}</div></div>)}
    </div>
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">User Bans</h2><p className="sc-pane-sub">Manage banned users</p></div>
      <div className="sc-acts">
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
        <button className="btn r" onClick={()=>{setModal('create');setErr('');setForm({user:'',reason:'',is_permanent:false,banned_until:''})}}>
          <Icon.UserX size={14}/> Ban User
        </button>
      </div>
    </div>
    {msg&&<div className="sc-success">{msg}</div>}
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="✅" txt="No bans found"/>:
      <div className="sc-tbl-wrap"><table className="sc-tbl">
        <thead><tr><th>User</th><th>Reason</th><th>Type</th><th>Banned At</th><th>Until</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{list.map((b,i)=>(
          <tr key={b.id||i}>
            <td className="td-b">{b.user?.username||b.user||'—'}</td>
            <td className="td-m" style={{maxWidth:'160px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{b.reason}</td>
            <td><span className={`badge ${b.is_permanent?'r':'o'}`}>{b.is_permanent?'Permanent':'Temporary'}</span></td>
            <td className="td-m">{fmt(b.banned_at)}</td>
            <td className="td-m">{b.is_permanent?'Forever':fmt(b.banned_until)}</td>
            <td><span className={`badge ${b.is_active_ban?'r':'muted'}`}>{b.is_active_ban?'Active':'Inactive'}</span></td>
            <td><div className="sc-row-acts">
              <button className="ibtn g" onClick={()=>{setSel(b);setForm({reason:b.reason,is_permanent:b.is_permanent,banned_until:b.banned_until?.slice(0,16)||''});setModal('edit');setErr('');}}>
                <Icon.Edit2 size={13}/>
              </button>
              {b.is_active_ban&&<button className="ibtn n" onClick={()=>handleUnban(b)}><Icon.UserCheck size={13}/> Unban</button>}
              <button className="ibtn r" onClick={()=>{setSel(b);setModal('delete');setErr('');}}><Icon.Trash2 size={13}/></button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {(modal==='create'||modal==='edit')&&<Modal title={modal==='create'?'Ban User':'Edit Ban'} onClose={()=>setModal(null)}>
      <div className="sc-form">
        {modal==='create'&&<Fld label="User ID / Username *">
          <input className="sc-input" value={form.user} onChange={e=>F('user',e.target.value)} placeholder="User ID or username"/>
        </Fld>}
        <Fld label="Reason *">
          <textarea className="sc-ta" rows={3} value={form.reason} onChange={e=>F('reason',e.target.value)} placeholder="Reason for ban..."/>
        </Fld>
        <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
          <input type="checkbox" checked={form.is_permanent||false} onChange={e=>F('is_permanent',e.target.checked)}
            style={{accentColor:'var(--sr)',width:'15px',height:'15px'}}/>
          Permanent Ban
        </label>
        {!form.is_permanent&&<Fld label="Ban Until">
          <input className="sc-input" type="datetime-local" value={form.banned_until||''} onChange={e=>F('banned_until',e.target.value)}/>
        </Fld>}
        {err&&<div className="sc-err">{err}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="btn r" onClick={modal==='create'?handleCreate:handleEdit} disabled={banning||saving}>
            {(banning||saving)?'Saving…':(modal==='create'?'Ban User':'Save Changes')}
          </button>
        </div>
      </div>
    </Modal>}

    {modal==='delete'&&sel&&<Modal title="Delete Ban Record" onClose={()=>setModal(null)}>
      <Confirm title="Delete this ban record?" text={`Delete ban for "${sel.user?.username||sel.user}"? This permanently removes the ban record.`}
        onConfirm={handleDelete} onCancel={()=>setModal(null)} saving={saving} btnLabel="Delete Ban"/>
      {err&&<div className="sc-err" style={{marginTop:'8px'}}>{err}</div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 5 — IP Blacklist (Full CRUD)
// ══════════════════════════════════════════════════════════
const THREAT_LEVELS = ['low','medium','high','critical','confirmed_attacker'];
const THREAT_TYPES  = ['brute_force','ddos','scanning','spam','malware','phishing','credential_stuffing','api_abuse','web_scraping','suspicious_pattern','manual_block','other'];

function IPBlacklistTab(){
  const {ips,loading,error,refetch,blockIP,unblockIP,criticalIPs} = useIPBlacklist({});
  const [modal,  setModal]  = useState(null);
  const [sel,    setSel]    = useState(null);
  const [form,   setForm]   = useState({ip_address:'',reason:'',threat_level:'medium',threat_type:'manual_block',is_permanent:false});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [msg,    setMsg]    = useState('');
  const F = (k,v) => setForm(f=>({...f,[k]:v}));

  const handleCreate = async () => {
    if(!form.ip_address){setErr('IP address required');return;}
    setSaving(true); setErr('');
    try{ await blockIP(form); setMsg('IP blocked'); setModal(null); setForm({ip_address:'',reason:'',threat_level:'medium',threat_type:'manual_block',is_permanent:false}); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleEdit = async () => {
    setSaving(true); setErr('');
    try{ await securityAPI.updateBlock(sel.id,form); setMsg('Entry updated'); setModal(null); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleUnblock = async ip => {
    const r = prompt('Reason for unblocking:','');
    if(r===null) return;
    try{ await unblockIP(ip.id,r); setMsg('IP unblocked'); }
    catch(e){ alert(errMsg(e)); }
  };
  const handleDelete = async () => {
    setSaving(true); setErr('');
    try{ await securityAPI.deleteBlock(sel.id); setMsg('Entry deleted'); setModal(null); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const list = arr(ips);
  return <div className="sc-pane">
    <div className="sc-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[{val:list.length,lbl:'Blocked IPs',cls:'r'},{val:criticalIPs.length,lbl:'Critical',cls:'o'},{val:list.filter(x=>x.is_permanent).length,lbl:'Permanent',cls:'p'}]
        .map((x,i)=><div key={i} className={`sc-card ${x.cls}`}><div className="sc-card-val">{x.val}</div><div className="sc-card-lbl">{x.lbl}</div></div>)}
    </div>
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">IP Blacklist</h2><p className="sc-pane-sub">Blocked IPs and threat intelligence</p></div>
      <div className="sc-acts">
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
        <button className="btn r" onClick={()=>{setModal('create');setErr('');}}><Icon.Shield size={14}/> Block IP</button>
      </div>
    </div>
    {msg&&<div className="sc-success">{msg}</div>}
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="🛡️" txt="No blocked IPs"/>:
      <div className="sc-tbl-wrap"><table className="sc-tbl">
        <thead><tr><th>IP Address</th><th>Threat Level</th><th>Threat Type</th><th>Reason</th><th>Blocked</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{list.map((ip,i)=>(
          <tr key={ip.id||i}>
            <td className="td-mo">{ip.ip_address}</td>
            <td><ThreatBadge v={ip.threat_level}/></td>
            <td><span className="badge muted">{ip.threat_type?.replace(/_/g,' ')||'—'}</span></td>
            <td className="td-m" style={{maxWidth:'150px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{ip.reason}</td>
            <td className="td-m">{fmt(ip.first_seen||ip.created_at)}</td>
            <td><span className={`badge ${ip.is_active?'r':'muted'}`}>{ip.is_active?'Active':'Inactive'}</span></td>
            <td><div className="sc-row-acts">
              <button className="ibtn c" onClick={()=>{setSel(ip);setModal('detail');}}><Icon.Eye size={13}/></button>
              <button className="ibtn g" onClick={()=>{setSel(ip);setForm({ip_address:ip.ip_address,reason:ip.reason||'',threat_level:ip.threat_level||'medium',threat_type:ip.threat_type||'manual_block',is_permanent:ip.is_permanent||false});setModal('edit');setErr('');}}><Icon.Edit2 size={13}/></button>
              {ip.is_active&&<button className="ibtn n" onClick={()=>handleUnblock(ip)}><Icon.Unlock size={13}/> Unblock</button>}
              <button className="ibtn r" onClick={()=>{setSel(ip);setModal('delete');setErr('');}}><Icon.Trash2 size={13}/></button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {modal==='detail'&&sel&&<Modal title="IP Detail" onClose={()=>setModal(null)}>
      <div className="kv-grid">
        <KV k="IP" v={sel.ip_address}/><KV k="Threat Level" v={sel.threat_level}/><KV k="Threat Type" v={sel.threat_type}/>
        <KV k="Detection" v={sel.detection_method}/><KV k="Active" v={sel.is_active?'Yes':'No'}/>
        <KV k="Permanent" v={sel.is_permanent?'Yes':'No'}/><KV k="Until" v={fmt(sel.blocked_until)}/>
        <KV k="First Seen" v={fmt(sel.first_seen||sel.created_at)}/>
      </div>
      {sel.reason&&<div className="detail-box" style={{marginTop:'12px'}}>
        <div className="kv-k" style={{marginBottom:'4px'}}>Reason</div>
        <div style={{fontSize:'.82rem'}}>{sel.reason}</div>
      </div>}
    </Modal>}

    {(modal==='create'||modal==='edit')&&<Modal title={modal==='create'?'Block IP Address':'Edit IP Block'} onClose={()=>setModal(null)}>
      <div className="sc-form">
        <Fld label="IP Address *">
          <input className="sc-input" value={form.ip_address} onChange={e=>F('ip_address',e.target.value)}
            placeholder="e.g. 192.168.1.1" disabled={modal==='edit'}/>
        </Fld>
        <div className="sc-form-row">
          <Fld label="Threat Level">
            <select className="sc-sel" value={form.threat_level} onChange={e=>F('threat_level',e.target.value)}>
              {THREAT_LEVELS.map(t=><option key={t}>{t}</option>)}
            </select>
          </Fld>
          <Fld label="Threat Type">
            <select className="sc-sel" value={form.threat_type} onChange={e=>F('threat_type',e.target.value)}>
              {THREAT_TYPES.map(t=><option key={t}>{t}</option>)}
            </select>
          </Fld>
        </div>
        <Fld label="Reason">
          <textarea className="sc-ta" rows={2} value={form.reason} onChange={e=>F('reason',e.target.value)} placeholder="Reason..."/>
        </Fld>
        <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
          <input type="checkbox" checked={form.is_permanent||false} onChange={e=>F('is_permanent',e.target.checked)}
            style={{accentColor:'var(--sr)',width:'15px',height:'15px'}}/>
          Permanent Block
        </label>
        {err&&<div className="sc-err">{err}</div>}
        <div className="sc-form-foot">
          <button className="btn ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="btn r" onClick={modal==='create'?handleCreate:handleEdit} disabled={saving}>
            {saving?'Saving…':(modal==='create'?'Block IP':'Save Changes')}
          </button>
        </div>
      </div>
    </Modal>}

    {modal==='delete'&&sel&&<Modal title="Delete Entry" onClose={()=>setModal(null)}>
      <Confirm title="Delete this IP block?" text={`Permanently delete block for "${sel.ip_address}"?`}
        onConfirm={handleDelete} onCancel={()=>setModal(null)} saving={saving} btnLabel="Delete Entry"/>
      {err&&<div className="sc-err" style={{marginTop:'8px'}}>{err}</div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 6 — Sessions
// ══════════════════════════════════════════════════════════
function SessionsTab(){
  const {sessions,loading,error,refetch,terminateSession,compromisedSessions} = useSessions();
  const [msg,setMsg] = useState('');

  const handleTerminate = async s => {
    const r = prompt('Reason for termination:','Security concern');
    if(r===null) return;
    try{ await terminateSession(s.id,r); setMsg('Session terminated'); }
    catch(e){ alert(errMsg(e)); }
  };

  const list = arr(sessions);
  return <div className="sc-pane">
    <div className="sc-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[{val:list.length,lbl:'Active',cls:'c'},{val:compromisedSessions.length,lbl:'Compromised',cls:'r'}]
        .map((x,i)=><div key={i} className={`sc-card ${x.cls}`}><div className="sc-card-val">{x.val}</div><div className="sc-card-lbl">{x.lbl}</div></div>)}
    </div>
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">Active Sessions</h2><p className="sc-pane-sub">Monitor and terminate live sessions</p></div>
      <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
    </div>
    {msg&&<div className="sc-success">{msg}</div>}
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="🔐" txt="No active sessions"/>:
      <div className="sess-list">{list.map((s,i)=>(
        <div key={s.id||i} className={`sess-card${s.is_compromised?' compromised':''}`}>
          <div style={{flex:1}}>
            <div className="td-b">{s.user?.username||s.user||'Unknown User'}</div>
            <div className="sess-meta">
              <span className="badge c">{s.login_method||'password'}</span>
              {s.is_compromised&&<span className="badge r">Compromised</span>}
              {s.force_logout&&<span className="badge o">Force Logout</span>}
              <span className="td-mo" style={{fontSize:'.75rem'}}>{s.ip_address}</span>
              <span className="td-m">{fmt(s.last_activity)}</span>
            </div>
            <div style={{fontSize:'.72rem',color:'var(--sm)',marginTop:'4px'}}>Expires: {fmt(s.expires_at)}</div>
          </div>
          <button className="ibtn r" onClick={()=>handleTerminate(s)}><Icon.XCircle size={13}/> Terminate</button>
        </div>
      ))}</div>
    }
  </div>;
}

// ══════════════════════════════════════════════════════════
// TAB 7 — Audit Trail
// ══════════════════════════════════════════════════════════
const ACT_ICON = {create:'➕',read:'👁',update:'✏️',delete:'🗑️',login:'🔑',logout:'🚪',export:'📤',import:'📥',approve:'✅',reject:'❌',other:'⚡'};

function AuditTab(){
  const {logs,loading,error,setParams,refetch} = useAuditTrail();
  const [actionF,setActionF] = useState('');
  const [detail, setDetail]  = useState(null);
  const list = arr(logs);
  return <div className="sc-pane">
    <div className="sc-pane-hdr">
      <div><h2 className="sc-pane-title">Audit Trail</h2><p className="sc-pane-sub">Complete log of all system actions</p></div>
      <div className="sc-acts">
        <select className="sc-fsel" value={actionF} onChange={e=>{setActionF(e.target.value);setParams(e.target.value?{action_type:e.target.value}:{});}}>
          <option value="">All Actions</option>
          {Object.keys(ACT_ICON).map(a=><option key={a}>{a}</option>)}
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
      </div>
    </div>
    {error&&<div className="sc-alert">{error}</div>}
    {loading?<Skel/>:list.length===0?<Empty icon="📋" txt="No audit logs"/>:
      <div className="sc-tbl-wrap"><table className="sc-tbl">
        <thead><tr><th>Time</th><th>Action</th><th>Model</th><th>Object</th><th>User</th><th>IP</th><th>Status</th><th></th></tr></thead>
        <tbody>{list.map((l,i)=>(
          <tr key={l.id||i}>
            <td className="td-m">{fmt(l.created_at)}</td>
            <td><span style={{marginRight:'5px'}}>{ACT_ICON[l.action_type]||'⚡'}</span><span className="badge c">{l.action_type}</span></td>
            <td className="td-b">{l.model_name||'—'}</td>
            <td className="td-mo">{l.object_repr||String(l.object_id||'').slice(0,12)||'—'}</td>
            <td className="td-b">{l.user?.username||l.user||'—'}</td>
            <td className="td-mo">{l.ip_address||'—'}</td>
            <td>{l.status_code&&<span className={`badge ${l.status_code<300?'n':l.status_code<400?'c':'r'}`}>{l.status_code}</span>}</td>
            <td><button className="ibtn c" onClick={()=>setDetail(l)}><Icon.Eye size={13}/></button></td>
          </tr>
        ))}</tbody>
      </table></div>
    }
    {detail&&<Modal title="Audit Detail" onClose={()=>setDetail(null)} wide>
      <div className="kv-grid">
        <KV k="Action"  v={detail.action_type}/><KV k="Model"  v={detail.model_name}/>
        <KV k="Object"  v={detail.object_repr||detail.object_id}/><KV k="User" v={detail.user?.username||detail.user}/>
        <KV k="IP"      v={detail.ip_address}/><KV k="Method" v={detail.request_method}/>
        <KV k="Path"    v={detail.request_path}/><KV k="Status" v={detail.status_code}/>
        <KV k="Time"    v={fmt(detail.created_at)}/>
      </div>
      {detail.changed_fields?.length>0&&<div className="detail-box" style={{marginTop:'12px'}}>
        <div className="kv-k" style={{marginBottom:'6px'}}>Changed Fields</div>
        <div style={{display:'flex',gap:'5px',flexWrap:'wrap'}}>
          {detail.changed_fields.map(f=><span key={f} className="badge o">{f}</span>)}
        </div>
      </div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════
// Main
// ══════════════════════════════════════════════════════════
const TABS = [
  {id:'dashboard', label:'Dashboard',    icon:<Icon.Shield size={15}/>},
  {id:'logs',      label:'Logs',         icon:<Icon.AlertTriangle size={15}/>},
  {id:'devices',   label:'Devices',      icon:<Icon.Smartphone size={15}/>},
  {id:'bans',      label:'User Bans',    icon:<Icon.UserX size={15}/>},
  {id:'ips',       label:'IP Blacklist', icon:<Icon.Lock size={15}/>},
  {id:'sessions',  label:'Sessions',     icon:<Icon.Activity size={15}/>},
  {id:'audit',     label:'Audit Trail',  icon:<Icon.List size={15}/>},
];

export default function Security(){
  const [tab, setTab] = useState('dashboard');
  return <div className="sc-root">
    <div className="sc-hdr">
      <div className="sc-hdr-inner">
        <div className="sc-title-wrap">
          <span className="sc-icon">🔒</span>
          <div>
            <h1 className="sc-title">SECURITY CENTER</h1>
            <p className="sc-sub">Threat detection, device control, bans and audit trail</p>
          </div>
        </div>
        <div className="sc-live">
          <div className="sc-live-dot"/>
          <span className="sc-live-txt">MONITORING ACTIVE</span>
        </div>
      </div>
      <div className="sc-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={`sc-tab${tab===t.id?' active':''}`} onClick={()=>setTab(t.id)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>
    </div>
    <div className="sc-body">
      {tab==='dashboard' && <DashboardTab/>}
      {tab==='logs'      && <LogsTab/>}
      {tab==='devices'   && <DevicesTab/>}
      {tab==='bans'      && <BansTab/>}
      {tab==='ips'       && <IPBlacklistTab/>}
      {tab==='sessions'  && <SessionsTab/>}
      {tab==='audit'     && <AuditTab/>}
    </div>
  </div>;
}
