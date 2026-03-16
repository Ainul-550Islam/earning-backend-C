// src/pages/RateLimit.jsx
// Tabs: Dashboard | Configs | Logs | User Profiles
// Full CRUD — field names from actual serializers/views
import { useState } from 'react';
import * as Icon from 'react-feather';
import {
  useRateLimitDashboard,
  useConfigs,
  useRateLimitLogs,
  useUserProfiles,
} from '../hooks/useRateLimit';
import rateLimitAPI from '../api/endpoints/rateLimit';
import '../styles/RateLimit.css';

// ── Helpers ───────────────────────────────────────────────────────
const errMsg = e => {
  const d = e?.response?.data;
  if (!d) return e?.message || 'Unknown error';
  if (typeof d === 'string') return d;
  if (d.detail) return d.detail;
  if (d.non_field_errors) return d.non_field_errors.join(', ');
  return Object.entries(d).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
};
const fmt     = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
const fmtDate = d => d ? new Date(d).toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'}) : '—';
const safeArr = d => Array.isArray(d) ? d : (d?.results ?? []);

const STATUS_CLS = { allowed:'n', blocked:'r', exceeded:'o' };
const TYPE_CLS   = { user:'c', ip:'p', endpoint:'g', global:'o', referral:'n', task:'g' };
const RL_TYPES   = ['user','ip','endpoint','global','referral','task'];
const TIME_UNITS = ['second','minute','hour','day'];

// ── Shared UI ─────────────────────────────────────────────────────
const Skel  = () => <div className="rl-skel">{[1,2,3,4,5].map(i=><div key={i} className="rl-skel-row"/>)}</div>;
const Empty = ({icon,txt}) => <div className="rl-empty"><div className="rl-empty-ico">{icon}</div><p className="rl-empty-txt">{txt}</p></div>;
const Fld   = ({label,children}) => <div className="rl-field"><label className="rl-lbl">{label}</label>{children}</div>;
const KV    = ({k,v}) => <div className="kv"><span className="kv-k">{k}</span><span className="kv-v">{v??'—'}</span></div>;

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

function Confirm({title,text,onConfirm,onCancel,saving,btnLabel='Delete',cls='r'}){
  return <div className="rl-form">
    <div className="danger-box"><p className="danger-title">{title}</p><p className="danger-text">{text}</p></div>
    <div className="rl-form-foot">
      <button className="btn ghost" onClick={onCancel}>Cancel</button>
      <button className={`btn ${cls}`} onClick={onConfirm} disabled={saving}>{saving?'Please wait…':btnLabel}</button>
    </div>
  </div>;
}

function HealthBar({score}){
  const p = Math.min(Number(score)||0,100);
  const c = p>=80?'good':p>=60?'ok':p>=40?'bad':'crit';
  return <div className="health-wrap">
    <div className="health-bar"><div className={`health-fill hf-${c}`} style={{width:`${p}%`}}/></div>
    <span className="health-num">{p}%</span>
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 1 — Dashboard
// ══════════════════════════════════════════════════════════════════
function DashboardTab(){
  const [tf,setTf] = useState('24h');
  const {
    loading, error, refetch,
    totalConfigs, activeConfigs, totalRequests,
    blockedRequests, blockRate, userStats, topConfigs, recentBlocked,
  } = useRateLimitDashboard(tf);

  if(loading) return <Skel/>;
  if(error)   return <div className="rl-alert">{error}</div>;

  return <div className="rl-pane">
    <div className="rl-pane-hdr">
      <div><h2 className="rl-pane-title">Rate Limit Overview</h2><p className="rl-pane-sub">System-wide API throttling metrics</p></div>
      <div className="rl-acts">
        <select className="rl-fsel" value={tf} onChange={e=>setTf(e.target.value)}>
          <option value="24h">Last 24h</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option>
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/> Refresh</button>
      </div>
    </div>

    <div className="rl-grid">
      {[
        {ico:'⚙️',val:totalConfigs,                                 lbl:'Total Configs',   cls:'c'},
        {ico:'✅',val:activeConfigs,                                lbl:'Active Configs',   cls:'n'},
        {ico:'📊',val:totalRequests,                               lbl:'Total Requests',   cls:'p'},
        {ico:'🚫',val:blockedRequests,                             lbl:'Blocked',          cls:'r'},
        {ico:'✔️',val:totalRequests-blockedRequests,               lbl:'Allowed',          cls:'n'},
        {ico:'📈',val:`${Number(blockRate).toFixed(1)}%`,          lbl:'Block Rate',       cls:'o'},
        {ico:'👥',val:userStats?.total_users   ||'—',              lbl:'Total Users',      cls:'c'},
        {ico:'⭐',val:userStats?.premium_users ||'—',              lbl:'Premium Users',    cls:'g'},
      ].map((x,i)=>(
        <div key={i} className={`rl-card ${x.cls}`}>
          <div className="rl-card-ico">{x.ico}</div>
          <div className="rl-card-val">{x.val}</div>
          <div className="rl-card-lbl">{x.lbl}</div>
        </div>
      ))}
    </div>

    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
      {topConfigs.length>0&&<div className="detail-box">
        <div className="rl-section-title">Top Configs (by request count)</div>
        {topConfigs.map((c,i)=>(
          <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'7px 0',borderBottom:'1px solid var(--rl-bdr)'}}>
            <span className="td-b" style={{fontSize:'.8rem'}}>{c.config__name||'—'}</span>
            <div style={{display:'flex',gap:'5px'}}>
              <span className="badge c" title="total">{c.count}</span>
              <span className="badge r" title="blocked">{c.blocked}</span>
            </div>
          </div>
        ))}
      </div>}

      {recentBlocked.length>0&&<div className="detail-box">
        <div className="rl-section-title">Recent Blocked Requests</div>
        {recentBlocked.slice(0,8).map((l,i)=>(
          <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'6px 0',borderBottom:'1px solid var(--rl-bdr)'}}>
            <div>
              <span className="td-b" style={{fontSize:'.8rem'}}>{l.user_username||'Anonymous'}</span>
              <span className="td-mo" style={{marginLeft:'8px',fontSize:'.72rem'}}>{l.ip_address}</span>
            </div>
            <span className="td-m">{fmt(l.timestamp)}</span>
          </div>
        ))}
      </div>}
    </div>
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 2 — Configs (Full CRUD + Bulk + Test + Duplicate)
// ══════════════════════════════════════════════════════════════════
const EMPTY_FORM = {
  name:'', rate_limit_type:'endpoint', requests_per_unit:100,
  time_unit:'hour', time_value:1, is_active:true,
  endpoint:'', ip_address:'', task_type:'', offer_wall:'',
};

function ConfigsTab(){
  const {configs,loading,error,setParams,refetch,activeCount,inactiveCount} = useConfigs();
  const [modal,  setModal]  = useState(null);
  const [sel,    setSel]    = useState(null);
  const [form,   setForm]   = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [msg,    setMsg]    = useState('');
  const [typeF,  setTypeF]  = useState('');
  const [activeF,setActiveF]= useState('');
  const [testRes,setTestRes]= useState(null);
  const [bulkSel,setBulkSel]= useState([]);
  const F = (k,v) => setForm(f=>({...f,[k]:v}));

  const open = (m,d=null) => {
    setSel(d); setModal(m); setErr(''); setTestRes(null);
    if(m==='edit'&&d) setForm({
      name:d.name, rate_limit_type:d.rate_limit_type,
      requests_per_unit:d.requests_per_unit, time_unit:d.time_unit,
      time_value:d.time_value, is_active:d.is_active,
      endpoint:d.endpoint||'', ip_address:d.ip_address||'',
      task_type:d.task_type||'', offer_wall:d.offer_wall||'',
    });
    else if(m==='create') setForm(EMPTY_FORM);
  };
  const close = () => { setModal(null); setSel(null); };

  const handleCreate = async () => {
    if(!form.name){setErr('Name is required');return;}
    if(form.rate_limit_type==='endpoint'&&!form.endpoint){setErr('Endpoint is required');return;}
    if(form.rate_limit_type==='ip'&&!form.ip_address){setErr('IP address is required');return;}
    if(form.rate_limit_type==='task'&&!form.task_type){setErr('Task type is required');return;}
    setSaving(true); setErr('');
    try{ await rateLimitAPI.createConfig(form); setMsg(`"${form.name}" created`); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleEdit = async () => {
    setSaving(true); setErr('');
    try{ await rateLimitAPI.updateConfig(sel.id,form); setMsg(`"${form.name}" updated`); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleDelete = async () => {
    setSaving(true); setErr('');
    try{ await rateLimitAPI.deleteConfig(sel.id); setMsg('Config deleted'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleDuplicate = async c => {
    try{ await rateLimitAPI.duplicateConfig(c.id); setMsg(`"${c.name}" duplicated`); refetch(); }
    catch(e){ alert(errMsg(e)); }
  };
  const handleToggle = async c => {
    try{ await rateLimitAPI.updateConfig(c.id,{is_active:!c.is_active}); refetch(); }
    catch(e){ alert(errMsg(e)); }
  };
  const handleTest = async () => {
    setSaving(true); setTestRes(null);
    try{ const res = await rateLimitAPI.testConfig(sel.id,{}); setTestRes(res.data); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleBulk = async action => {
    if(!bulkSel.length) return;
    setSaving(true);
    try{
      await rateLimitAPI.bulkUpdate({configs:bulkSel.map(id=>({id})),action});
      setMsg(`${bulkSel.length} configs ${action}d`); setBulkSel([]); refetch();
    } catch(e){ alert(errMsg(e)); } finally{ setSaving(false); }
  };
  const toggleBulk = id => setBulkSel(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);

  const list = configs
    .filter(c=>!typeF  ||c.rate_limit_type===typeF)
    .filter(c=>!activeF||String(c.is_active)===activeF);

  // Config Form shared for create/edit
  const ConfigForm = () => <>
    <Fld label="Config Name *">
      <input className="rl-input" value={form.name} onChange={e=>F('name',e.target.value)} placeholder="e.g. Login API Rate Limit"/>
    </Fld>
    <div className="rl-form-row">
      <Fld label="Type">
        <select className="rl-sel" value={form.rate_limit_type} onChange={e=>F('rate_limit_type',e.target.value)}>
          {RL_TYPES.map(t=><option key={t}>{t}</option>)}
        </select>
      </Fld>
      <Fld label="Status">
        <select className="rl-sel" value={String(form.is_active)} onChange={e=>F('is_active',e.target.value==='true')}>
          <option value="true">Active</option><option value="false">Inactive</option>
        </select>
      </Fld>
    </div>
    <div className="rl-form-row">
      <Fld label="Requests *">
        <input className="rl-input" type="number" min="1" value={form.requests_per_unit} onChange={e=>F('requests_per_unit',Number(e.target.value))}/>
      </Fld>
      <Fld label="Per">
        <input className="rl-input" type="number" min="1" value={form.time_value} onChange={e=>F('time_value',Number(e.target.value))}/>
      </Fld>
      <Fld label="Unit">
        <select className="rl-sel" value={form.time_unit} onChange={e=>F('time_unit',e.target.value)}>
          {TIME_UNITS.map(t=><option key={t}>{t}</option>)}
        </select>
      </Fld>
    </div>
    {form.rate_limit_type==='endpoint'&&<Fld label="Endpoint *"><input className="rl-input" value={form.endpoint} onChange={e=>F('endpoint',e.target.value)} placeholder="/api/tasks/complete/"/></Fld>}
    {form.rate_limit_type==='ip'      &&<Fld label="IP Address *"><input className="rl-input" value={form.ip_address} onChange={e=>F('ip_address',e.target.value)} placeholder="192.168.1.1"/></Fld>}
    {form.rate_limit_type==='task'    &&<Fld label="Task Type *"><input className="rl-input" value={form.task_type} onChange={e=>F('task_type',e.target.value)} placeholder="e.g. survey"/></Fld>}
    {form.rate_limit_type==='referral'&&<Fld label="Offer Wall"><input className="rl-input" value={form.offer_wall} onChange={e=>F('offer_wall',e.target.value)} placeholder="Offer wall name"/></Fld>}
    <div className="detail-box">
      <p style={{fontSize:'.82rem',color:'var(--rl-text)',margin:0}}>
        Allow <strong style={{color:'var(--rl-cyan)'}}>{form.requests_per_unit}</strong> requests per{' '}
        <strong style={{color:'var(--rl-cyan)'}}>{form.time_value} {form.time_unit}</strong>{' '}
        [{form.rate_limit_type}]
      </p>
    </div>
  </>;

  return <div className="rl-pane">
    <div className="rl-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[{val:configs.length,lbl:'Total',cls:'c'},{val:activeCount,lbl:'Active',cls:'n'},{val:inactiveCount,lbl:'Inactive',cls:'r'}]
        .map((x,i)=><div key={i} className={`rl-card ${x.cls}`}><div className="rl-card-val">{x.val}</div><div className="rl-card-lbl">{x.lbl}</div></div>)}
    </div>

    <div className="rl-pane-hdr">
      <div><h2 className="rl-pane-title">Rate Limit Configs</h2><p className="rl-pane-sub">Create, test and manage all throttling rules</p></div>
      <div className="rl-acts">
        {bulkSel.length>0&&<>
          <span className="badge c">{bulkSel.length} selected</span>
          <button className="btn n sm" onClick={()=>handleBulk('activate')} disabled={saving}>Activate</button>
          <button className="btn r sm" onClick={()=>handleBulk('deactivate')} disabled={saving}>Deactivate</button>
        </>}
        <select className="rl-fsel" value={typeF} onChange={e=>setTypeF(e.target.value)}>
          <option value="">All Types</option>{RL_TYPES.map(t=><option key={t}>{t}</option>)}
        </select>
        <select className="rl-fsel" value={activeF} onChange={e=>setActiveF(e.target.value)}>
          <option value="">All Status</option><option value="true">Active</option><option value="false">Inactive</option>
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
        <button className="btn c" onClick={()=>open('create')}><Icon.Plus size={14}/> New Config</button>
      </div>
    </div>

    {msg  &&<div className="rl-ok">{msg}</div>}
    {error&&<div className="rl-alert">{error}</div>}

    {loading?<Skel/>:list.length===0?<Empty icon="⚙️" txt="No configs"/>:
      <div className="rl-tbl-wrap"><table className="rl-tbl">
        <thead><tr>
          <th style={{width:'32px'}}/>
          <th>Name</th><th>Type</th><th>Limit / Period</th><th>Target</th>
          <th>Hits</th><th>Blocks</th><th>Active</th><th>Updated</th><th>Actions</th>
        </tr></thead>
        <tbody>{list.map((c,i)=>(
          <tr key={c.id||i}>
            <td><input type="checkbox" checked={bulkSel.includes(c.id)} onChange={()=>toggleBulk(c.id)} style={{accentColor:'var(--rl-cyan)',width:'14px',height:'14px'}}/></td>
            <td className="td-b">{c.name}</td>
            <td><span className={`badge ${TYPE_CLS[c.rate_limit_type]||'muted'}`}>{c.rate_limit_type}</span></td>
            <td className="td-b">{c.requests_per_unit} / {c.time_value} {c.time_unit}</td>
            <td className="td-m" style={{maxWidth:'130px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
              {c.endpoint||c.ip_address||c.task_type||c.user_username||c.offer_wall||'Global'}
            </td>
            <td><span className="badge c">{c.hit_count||0}</span></td>
            <td><span className="badge r">{c.block_count||0}</span></td>
            <td>
              <label className="tog">
                <input type="checkbox" checked={!!c.is_active} onChange={()=>handleToggle(c)}/>
                <div className="tog-track"/>
              </label>
            </td>
            <td className="td-m">{fmt(c.updated_at)}</td>
            <td><div className="row-acts">
              <button className="ibtn c" onClick={()=>{setSel(c);setModal('detail');}} title="Detail"><Icon.Eye size={13}/></button>
              <button className="ibtn g" onClick={()=>open('edit',c)} title="Edit"><Icon.Edit2 size={13}/></button>
              <button className="ibtn p" onClick={()=>handleDuplicate(c)} title="Duplicate"><Icon.Copy size={13}/></button>
              <button className="ibtn o" onClick={()=>{setSel(c);setModal('test');setErr('');setTestRes(null);}} title="Test"><Icon.Zap size={13}/></button>
              <button className="ibtn r" onClick={()=>{setSel(c);setModal('delete');setErr('');}} title="Delete"><Icon.Trash2 size={13}/></button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {/* Detail */}
    {modal==='detail'&&sel&&<Modal title="Config Detail" onClose={close}>
      <div className="kv-grid">
        <KV k="Name"       v={sel.name}/><KV k="Type"       v={sel.rate_limit_type}/>
        <KV k="Limit"      v={`${sel.requests_per_unit} per ${sel.time_value} ${sel.time_unit}`}/>
        <KV k="Active"     v={sel.is_active?'Yes':'No'}/><KV k="Hits" v={sel.hit_count}/><KV k="Blocks" v={sel.block_count}/>
        <KV k="Last Hit"   v={fmt(sel.last_hit_at)}/><KV k="Endpoint"   v={sel.endpoint}/>
        <KV k="IP"         v={sel.ip_address}/><KV k="Task Type" v={sel.task_type}/>
        <KV k="Offer Wall" v={sel.offer_wall}/><KV k="User"      v={sel.user_username}/>
        <KV k="Created"    v={fmt(sel.created_at)}/><KV k="Updated" v={fmt(sel.updated_at)}/>
      </div>
      <div style={{marginTop:'14px',display:'flex',gap:'8px'}}>
        <button className="btn c sm" onClick={()=>open('edit',sel)}>Edit</button>
        <button className="btn p sm" onClick={()=>handleDuplicate(sel)}>Duplicate</button>
        <button className="btn o sm" onClick={()=>{setModal('test');setTestRes(null);}}>Test</button>
      </div>
    </Modal>}

    {/* Create / Edit */}
    {(modal==='create'||modal==='edit')&&<Modal title={modal==='create'?'New Rate Limit Config':`Edit: ${sel?.name}`} onClose={close}>
      <div className="rl-form">
        <ConfigForm/>
        {err&&<div className="rl-err">{err}</div>}
        <div className="rl-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn c" onClick={modal==='create'?handleCreate:handleEdit} disabled={saving}>
            {saving?'Saving…':(modal==='create'?'Create Config':'Save Changes')}
          </button>
        </div>
      </div>
    </Modal>}

    {/* Test */}
    {modal==='test'&&sel&&<Modal title={`Test: ${sel.name}`} onClose={close}>
      <div className="rl-form">
        <div className="detail-box"><div className="kv-grid">
          <KV k="Limit" v={`${sel.requests_per_unit} / ${sel.time_value} ${sel.time_unit}`}/>
          <KV k="Type"  v={sel.rate_limit_type}/>
          <KV k="Target" v={sel.endpoint||sel.ip_address||sel.task_type||'global'}/>
        </div></div>
        <button className="btn c" onClick={handleTest} disabled={saving} style={{alignSelf:'flex-start'}}>
          <Icon.Zap size={14}/> {saving?'Testing…':'Run Test'}
        </button>
        {testRes&&<div className="detail-box">
          <div style={{fontFamily:'var(--fh)',fontSize:'.72rem',color:'var(--rl-cyan)',marginBottom:'10px',letterSpacing:'.08em'}}>RESULT</div>
          <div className="kv-grid">
            {Object.entries(testRes).filter(([,v])=>typeof v!=='object').map(([k,v])=><KV key={k} k={k.replace(/_/g,' ')} v={String(v)}/>)}
          </div>
        </div>}
        {err&&<div className="rl-err">{err}</div>}
        <div className="rl-form-foot"><button className="btn ghost" onClick={close}>Close</button></div>
      </div>
    </Modal>}

    {/* Delete */}
    {modal==='delete'&&sel&&<Modal title="Delete Config" onClose={close}>
      <Confirm
        title="Delete this rate limit config?"
        text={`"${sel.name}" will be permanently deleted. All associated logs will lose their config reference.`}
        onConfirm={handleDelete} onCancel={close} saving={saving} btnLabel="Delete Config"
      />
      {err&&<div className="rl-err" style={{marginTop:'8px'}}>{err}</div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 3 — Logs (Read + Filter + Clear old)
// ══════════════════════════════════════════════════════════════════
function LogsTab(){
  const {logs,stats,loading,error,setParams,refetch,blockedCount,allowedCount,exceededCount} = useRateLimitLogs();
  const [statusF, setStatusF] = useState('');
  const [methodF, setMethodF] = useState('');
  const [detail,  setDetail]  = useState(null);
  const [clearing,setClearing]= useState(false);
  const [msg,     setMsg]     = useState('');

  const handleClear = async () => {
    if(!window.confirm('Delete all logs older than 30 days?')) return;
    setClearing(true);
    try{
      const res = await rateLimitAPI.clearOldLogs(30);
      setMsg(`Cleared ${res.data.deleted_count||0} old logs`); refetch();
    } catch(e){ alert(errMsg(e)); } finally{ setClearing(false); }
  };

  const list = logs
    .filter(l=>!statusF||l.status===statusF)
    .filter(l=>!methodF||l.request_method===methodF);

  return <div className="rl-pane">
    <div className="rl-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(110px,1fr))'}}>
      {[
        {val:stats?.total_requests  ||logs.length, lbl:'Total (24h)', cls:'c'},
        {val:stats?.allowed_requests||allowedCount, lbl:'Allowed',    cls:'n'},
        {val:stats?.blocked_requests||blockedCount, lbl:'Blocked',    cls:'r'},
        {val:exceededCount,                         lbl:'Exceeded',   cls:'o'},
        {val:stats?`${Number(stats.block_rate).toFixed(1)}%`:'—',     lbl:'Block Rate',cls:'p'},
      ].map((x,i)=><div key={i} className={`rl-card ${x.cls}`}><div className="rl-card-val">{x.val}</div><div className="rl-card-lbl">{x.lbl}</div></div>)}
    </div>

    <div className="rl-pane-hdr">
      <div><h2 className="rl-pane-title">Rate Limit Logs</h2><p className="rl-pane-sub">All API request and blocking events</p></div>
      <div className="rl-acts">
        <select className="rl-fsel" value={statusF} onChange={e=>{setStatusF(e.target.value);setParams(e.target.value?{status:e.target.value}:{});}}>
          <option value="">All Status</option>{['allowed','blocked','exceeded'].map(s=><option key={s}>{s}</option>)}
        </select>
        <select className="rl-fsel" value={methodF} onChange={e=>setMethodF(e.target.value)}>
          <option value="">All Methods</option>{['GET','POST','PUT','PATCH','DELETE'].map(m=><option key={m}>{m}</option>)}
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
        <button className="btn o sm" onClick={handleClear} disabled={clearing}><Icon.Trash2 size={13}/> {clearing?'Clearing…':'Clear Old'}</button>
      </div>
    </div>

    {msg  &&<div className="rl-ok">{msg}</div>}
    {error&&<div className="rl-alert">{error}</div>}

    {loading?<Skel/>:list.length===0?<Empty icon="📋" txt="No logs found"/>:
      <div className="rl-tbl-wrap"><table className="rl-tbl">
        <thead><tr><th>Time</th><th>User</th><th>IP</th><th>Endpoint</th><th>Method</th><th>Status</th><th>Config</th><th>Suspicion</th><th></th></tr></thead>
        <tbody>{list.map((l,i)=>(
          <tr key={l.id||i}>
            <td className="td-m">{fmt(l.timestamp)}</td>
            <td className="td-b">{l.user_username||'—'}</td>
            <td className="td-mo">{l.ip_address}</td>
            <td className="td-m" style={{maxWidth:'150px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={l.endpoint}>{l.endpoint}</td>
            <td><span className="badge muted">{l.request_method}</span></td>
            <td><span className={`badge ${STATUS_CLS[l.status]||'muted'}`}>{l.status}</span></td>
            <td className="td-m">{l.config_name||'—'}</td>
            <td>
              <div style={{display:'flex',alignItems:'center',gap:'6px'}}>
                <div style={{width:'44px',height:'4px',background:'rgba(255,255,255,.06)',borderRadius:'2px',overflow:'hidden'}}>
                  <div style={{width:`${l.suspicion_score||0}%`,height:'100%',borderRadius:'2px',
                    background:(l.suspicion_score||0)>=70?'var(--rl-red)':(l.suspicion_score||0)>=40?'var(--rl-orange)':'var(--rl-cyan)'}}/>
                </div>
                <span className="td-m">{l.suspicion_score||0}</span>
              </div>
            </td>
            <td><button className="ibtn c" onClick={()=>setDetail(l)}><Icon.Eye size={13}/></button></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {detail&&<Modal title="Log Detail" onClose={()=>setDetail(null)}>
      <div className="kv-grid">
        <KV k="Time"          v={fmt(detail.timestamp)}/><KV k="User"         v={detail.user_username}/>
        <KV k="IP Address"    v={detail.ip_address}/><KV k="Endpoint"         v={detail.endpoint}/>
        <KV k="Method"        v={detail.request_method}/><KV k="Status"       v={detail.status}/>
        <KV k="Req Count"     v={detail.requests_count}/><KV k="Suspicion"    v={detail.suspicion_score}/>
        <KV k="Config"        v={detail.config_name}/><KV k="Task ID"         v={detail.task_id}/>
        <KV k="Offer ID"      v={detail.offer_id}/><KV k="Referral Code"      v={detail.referral_code}/>
        <KV k="Created"       v={fmt(detail.created_at)}/>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 4 — User Profiles (Full CRUD)
// ══════════════════════════════════════════════════════════════════
function ProfilesTab(){
  const {profiles,loading,error,setParams,refetch,premiumCount,suspiciousCount} = useUserProfiles();
  const [modal,    setModal]    = useState(null);
  const [sel,      setSel]      = useState(null);
  const [limForm,  setLimForm]  = useState({custom_daily_limit:'',custom_hourly_limit:''});
  const [premDays, setPremDays] = useState(30);
  const [saving,   setSaving]   = useState(false);
  const [err,      setErr]      = useState('');
  const [msg,      setMsg]      = useState('');
  const [premF,    setPremF]    = useState('');
  const [search,   setSearch]   = useState('');
  const LF = (k,v) => setLimForm(f=>({...f,[k]:v}));

  const close = () => { setModal(null); setSel(null); setErr(''); };

  const handleSetLimits = async () => {
    setSaving(true); setErr('');
    try{
      await rateLimitAPI.setCustomLimits(sel.id,{
        daily_limit:  limForm.custom_daily_limit  ? Number(limForm.custom_daily_limit)  : null,
        hourly_limit: limForm.custom_hourly_limit ? Number(limForm.custom_hourly_limit) : null,
      });
      setMsg(`Limits set for ${sel.username}`); close(); refetch();
    } catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handlePremium = async () => {
    setSaving(true); setErr('');
    try{
      await rateLimitAPI.upgradePremium(sel.id,{duration_days:Number(premDays)});
      setMsg(`${sel.username} upgraded for ${premDays} days`); close(); refetch();
    } catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };
  const handleReset = async p => {
    if(!window.confirm(`Reset all limits for ${p.username}?`)) return;
    try{ await rateLimitAPI.resetLimits(p.id); setMsg(`Reset for ${p.username}`); refetch(); }
    catch(e){ alert(errMsg(e)); }
  };
  const handleDelete = async () => {
    setSaving(true); setErr('');
    try{ await rateLimitAPI.deleteProfile(sel.id); setMsg('Profile deleted'); close(); refetch(); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const list = profiles
    .filter(p=>!premF  ||String(p.is_premium)===premF)
    .filter(p=>!search ||(p.username||'').toLowerCase().includes(search.toLowerCase()));

  return <div className="rl-pane">
    <div className="rl-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))'}}>
      {[
        {val:profiles.length,             lbl:'Total',      cls:'c'},
        {val:premiumCount,                lbl:'Premium',    cls:'g'},
        {val:suspiciousCount,             lbl:'Suspicious', cls:'r'},
        {val:profiles.length-premiumCount,lbl:'Standard',  cls:'p'},
      ].map((x,i)=><div key={i} className={`rl-card ${x.cls}`}><div className="rl-card-val">{x.val}</div><div className="rl-card-lbl">{x.lbl}</div></div>)}
    </div>

    <div className="rl-pane-hdr">
      <div><h2 className="rl-pane-title">User Profiles</h2><p className="rl-pane-sub">Per-user rate limits, premium status and usage</p></div>
      <div className="rl-acts">
        <input className="rl-search" placeholder="Search username…" value={search} onChange={e=>setSearch(e.target.value)}/>
        <select className="rl-fsel" value={premF} onChange={e=>{setPremF(e.target.value);setParams(e.target.value?{is_premium:e.target.value}:{});}}>
          <option value="">All</option><option value="true">Premium</option><option value="false">Standard</option>
        </select>
        <button className="btn ghost sm" onClick={refetch}><Icon.RefreshCw size={13}/></button>
      </div>
    </div>

    {msg  &&<div className="rl-ok">{msg}</div>}
    {error&&<div className="rl-alert">{error}</div>}

    {loading?<Skel/>:list.length===0?<Empty icon="👥" txt="No profiles found"/>:
      <div className="rl-tbl-wrap"><table className="rl-tbl">
        <thead><tr>
          <th>User</th><th>Email</th><th>Status</th>
          <th>Daily</th><th>Hourly</th><th>Total Reqs</th>
          <th>Blocked</th><th>API Health</th><th>Premium Until</th><th>Actions</th>
        </tr></thead>
        <tbody>{list.map((p,i)=>{
          const br = p.total_requests>0?Math.round((p.blocked_requests/p.total_requests)*100):0;
          return <tr key={p.id||i}>
            <td className="td-b">{p.username||'—'}</td>
            <td className="td-m">{p.email||'—'}</td>
            <td>
              <div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>
                {p.is_premium&&<span className="badge g">Premium</span>}
                {(p.suspicion_score||0)>=50&&<span className="badge r">Suspicious</span>}
                {!p.is_premium&&(p.suspicion_score||0)<50&&<span className="badge muted">Standard</span>}
              </div>
            </td>
            <td className="td-b">{p.custom_daily_limit  ||<span className="td-m">Default</span>}</td>
            <td className="td-b">{p.custom_hourly_limit ||<span className="td-m">Default</span>}</td>
            <td><span className="badge c">{p.total_requests||0}</span></td>
            <td>
              <div style={{display:'flex',alignItems:'center',gap:'5px'}}>
                <span className="badge r">{p.blocked_requests||0}</span>
                {br>0&&<span className="td-m">({br}%)</span>}
              </div>
            </td>
            <td style={{minWidth:'100px'}}><HealthBar score={p.api_health_score||100}/></td>
            <td className="td-m">{p.is_premium?fmtDate(p.premium_until)||'Forever':'—'}</td>
            <td><div className="row-acts">
              <button className="ibtn c" onClick={()=>{setSel(p);setModal('detail');}} title="Detail"><Icon.Eye size={13}/></button>
              <button className="ibtn g" onClick={()=>{setSel(p);setLimForm({custom_daily_limit:p.custom_daily_limit||'',custom_hourly_limit:p.custom_hourly_limit||''});setModal('limits');setErr('');}} title="Set Limits"><Icon.Sliders size={13}/></button>
              {!p.is_premium&&<button className="ibtn g" onClick={()=>{setSel(p);setPremDays(30);setModal('premium');setErr('');}} title="Upgrade"><Icon.Star size={13}/></button>}
              <button className="ibtn o" onClick={()=>handleReset(p)} title="Reset"><Icon.RefreshCw size={13}/></button>
              <button className="ibtn r" onClick={()=>{setSel(p);setModal('delete');setErr('');}} title="Delete"><Icon.Trash2 size={13}/></button>
            </div></td>
          </tr>;
        })}</tbody>
      </table></div>
    }

    {/* Detail */}
    {modal==='detail'&&sel&&<Modal title={`Profile: ${sel.username}`} onClose={close}>
      <div className="kv-grid">
        <KV k="Username"     v={sel.username}/><KV k="Email"         v={sel.email}/>
        <KV k="Premium"      v={sel.is_premium?'Yes':'No'}/><KV k="Premium Until" v={fmtDate(sel.premium_until)}/>
        <KV k="Daily Limit"  v={sel.custom_daily_limit||'Default'}/><KV k="Hourly Limit" v={sel.custom_hourly_limit||'Default'}/>
        <KV k="Total Reqs"   v={sel.total_requests}/><KV k="Blocked" v={sel.blocked_requests}/>
        <KV k="Daily Usage"  v={sel.daily_usage}/><KV k="Hourly Usage" v={sel.hourly_usage}/>
        <KV k="Suspicion"    v={sel.suspicion_score}/><KV k="API Health" v={`${sel.api_health_score||100}%`}/>
        <KV k="Last Request" v={fmt(sel.last_request_at)}/><KV k="Created" v={fmt(sel.created_at)}/>
      </div>
      <div style={{marginTop:'14px'}}>
        <div className="rl-section-title" style={{margin:'0 0 8px'}}>API Health Score</div>
        <HealthBar score={sel.api_health_score||100}/>
      </div>
      <div style={{marginTop:'14px',display:'flex',gap:'8px',flexWrap:'wrap'}}>
        <button className="btn c sm" onClick={()=>{setModal('limits');setLimForm({custom_daily_limit:sel.custom_daily_limit||'',custom_hourly_limit:sel.custom_hourly_limit||''});}}>Set Limits</button>
        {!sel.is_premium&&<button className="btn g sm" onClick={()=>{setModal('premium');setPremDays(30);}}>Upgrade Premium</button>}
        <button className="btn o sm" onClick={()=>handleReset(sel)}>Reset Limits</button>
      </div>
    </Modal>}

    {/* Set Limits */}
    {modal==='limits'&&sel&&<Modal title={`Custom Limits: ${sel.username}`} onClose={close}>
      <div className="rl-form">
        <div className="detail-box"><p style={{fontSize:'.82rem',color:'var(--rl-muted)',margin:0}}>Leave empty to use system default limits.</p></div>
        <div className="rl-form-row">
          <Fld label="Daily Limit">
            <input className="rl-input" type="number" min="1" value={limForm.custom_daily_limit} onChange={e=>LF('custom_daily_limit',e.target.value)} placeholder="e.g. 1000"/>
          </Fld>
          <Fld label="Hourly Limit">
            <input className="rl-input" type="number" min="1" value={limForm.custom_hourly_limit} onChange={e=>LF('custom_hourly_limit',e.target.value)} placeholder="e.g. 100"/>
          </Fld>
        </div>
        {err&&<div className="rl-err">{err}</div>}
        <div className="rl-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn c" onClick={handleSetLimits} disabled={saving}>{saving?'Saving…':'Save Limits'}</button>
        </div>
      </div>
    </Modal>}

    {/* Premium */}
    {modal==='premium'&&sel&&<Modal title={`Upgrade: ${sel.username}`} onClose={close}>
      <div className="rl-form">
        <div className="detail-box"><p style={{fontSize:'.82rem',color:'var(--rl-muted)',margin:0}}>Premium users get higher rate limit allowances.</p></div>
        <Fld label="Duration (days)">
          <input className="rl-input" type="number" min="1" value={premDays} onChange={e=>setPremDays(e.target.value)}/>
        </Fld>
        <div className="detail-box">
          <p style={{fontSize:'.8rem',color:'var(--rl-text)',margin:0}}>
            Premium until:{' '}
            <strong style={{color:'var(--rl-gold)'}}>
              {new Date(Date.now()+Number(premDays)*864e5).toLocaleDateString([],{month:'long',day:'numeric',year:'numeric'})}
            </strong>
          </p>
        </div>
        {err&&<div className="rl-err">{err}</div>}
        <div className="rl-form-foot">
          <button className="btn ghost" onClick={close}>Cancel</button>
          <button className="btn g" onClick={handlePremium} disabled={saving}>{saving?'Saving…':'Upgrade to Premium'}</button>
        </div>
      </div>
    </Modal>}

    {/* Delete */}
    {modal==='delete'&&sel&&<Modal title="Delete Profile" onClose={close}>
      <Confirm
        title="Delete this user profile?"
        text={`Permanently delete rate limit profile for "${sel.username}". Custom limits and usage history will be lost.`}
        onConfirm={handleDelete} onCancel={close} saving={saving} btnLabel="Delete Profile"
      />
      {err&&<div className="rl-err" style={{marginTop:'8px'}}>{err}</div>}
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════
const TABS = [
  {id:'dashboard',label:'Dashboard',    icon:<Icon.BarChart2 size={15}/>},
  {id:'configs',  label:'Configs',      icon:<Icon.Settings  size={15}/>},
  {id:'logs',     label:'Logs',         icon:<Icon.FileText  size={15}/>},
  {id:'profiles', label:'User Profiles',icon:<Icon.Users     size={15}/>},
];

export default function RateLimit(){
  const [tab,setTab] = useState('dashboard');
  return <div className="rl-root">
    <div className="rl-hdr">
      <div className="rl-hdr-inner">
        <div className="rl-title-wrap">
          <span className="rl-icon">⏱️</span>
          <div>
            <h1 className="rl-title">RATE LIMIT</h1>
            <p className="rl-sub">API throttling, config management and user profiles</p>
          </div>
        </div>
        <div className="rl-live">
          <div className="rl-live-dot"/>
          <span className="rl-live-txt">ENFORCING</span>
        </div>
      </div>
      <div className="rl-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={`rl-tab${tab===t.id?' active':''}`} onClick={()=>setTab(t.id)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>
    </div>
    <div className="rl-body">
      {tab==='dashboard'&&<DashboardTab/>}
      {tab==='configs'  &&<ConfigsTab/>}
      {tab==='logs'     &&<LogsTab/>}
      {tab==='profiles' &&<ProfilesTab/>}
    </div>
  </div>;
}
