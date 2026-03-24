// src/pages/AutoMod.jsx — Full Auto-Moderation Admin Page
// Tabs: Dashboard | Review Queue | Submissions | Rules | Bots | Scans

import { useState, useEffect } from 'react';
import * as Icon from 'react-feather';
import { useRules, useSubmissions, useBots, useDashboard, errMsg } from '../hooks/useAutoMod';
import '../styles/AutoMod.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ── Constants ──────────────────────────────────────────────────────
const SUB_TYPES    = ['task_proof','user_content','profile','report','comment','media'];
const MOD_STATUS   = ['pending','scanning','auto_approved','auto_rejected','human_review','human_approved','human_rejected','escalated','expired'];
const RISK_LEVELS  = ['low','medium','high','critical'];
const RULE_ACTIONS = ['approve','reject','flag','escalate','request_proof','notify_admin'];
const OPERATORS    = ['eq','neq','contains','not_contains','regex','gt','lt','gte','lte','in','not_in'];
const SCAN_TYPES   = ['image','text','ocr','combined'];
const BOT_STATUS   = ['idle','running','paused','error','disabled'];
const FLAG_REASONS = ['spam','fake_proof','inappropriate','duplicate','policy_violation','suspicious_pattern','low_quality','other'];

const STATUS_COLORS = {
  pending:'gold', scanning:'cyan', auto_approved:'green', auto_rejected:'red',
  human_review:'orange', human_approved:'green', human_rejected:'red',
  escalated:'purple', expired:'muted',
  low:'green', medium:'gold', high:'orange', critical:'red',
  idle:'muted', running:'green', paused:'gold', error:'red', disabled:'muted',
  approve:'green', reject:'red', flag:'orange', escalate:'purple',
  request_proof:'cyan', notify_admin:'blue',
};

const fmtDate   = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
const fmtConf   = v => v != null ? `${(v*100).toFixed(0)}%` : '—';
const riskColor = r => ({'low':'green','medium':'gold','high':'orange','critical':'red'}[r]||'muted');

// ── Shared UI ──────────────────────────────────────────────────────
function Badge({value}){ const c=STATUS_COLORS[value]||'muted'; return <span className={`am-badge am-badge--${c}`}>{String(value).replace(/_/g,' ')}</span>; }
function Stat({label,value,color='orange'}){ return <div className={`am-stat am-stat--${color}`}><div className="am-stat-value">{value??'—'}</div><div className="am-stat-label">{label}</div></div>; }
function Skeleton(){ return <div className="am-loading">{[1,2,3,4,5].map(i=><div key={i} className="am-loading-row"/>)}</div>; }
function Empty({icon,text,onAdd}){ return <div className="am-empty"><div className="am-empty-icon">{icon}</div><p className="am-empty-txt">{text}</p>{onAdd&&<button className="am-btn am-btn--orange" onClick={onAdd}>+ Create First</button>}</div>; }
function KV({k,v}){ return <div className="am-kv"><span className="am-kv-k">{k}</span><span className="am-kv-v">{v||'—'}</span></div>; }

function Modal({title,onClose,children,wide,lg}){
  return <div className="am-modal-bg" onClick={e=>e.target===e.currentTarget&&onClose()}>
    <div className={`am-modal${wide?' am-modal--wide':''}${lg?' am-modal--lg':''}`}>
      <div className="am-modal-hdr">
        <h3 className="am-modal-title">{title}</h3>
        <button className="am-modal-close" onClick={onClose}><Icon.X size={18}/></button>
      </div>
      <div className="am-modal-body">{children}</div>
    </div>
  </div>;
}

function Field({label,children}){ return <div className="am-field"><label className="am-field-lbl">{label}</label>{children}</div>; }

function ConfBar({value}){
  return <div className="am-conf">
    <div className="am-conf-bar"><div className="am-conf-fill" style={{width:`${(value||0)*100}%`}}/></div>
    <span className="am-conf-val">{fmtConf(value)}</span>
  </div>;
}

function BotPulse({status}){
  return <span className={`am-pulse am-pulse--${status}`}/>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 1 — Dashboard
// ══════════════════════════════════════════════════════════════════
function DashboardTab(){
  const { data, loading, error, refetch } = useDashboard();

  if(loading) return <Skeleton/>;
  if(error)   return <div className="am-error">{error}</div>;
  if(!data)   return <Empty icon="📊" text="No dashboard data"/>;

  // Backend returns: { submissions: {pending,human_review,escalated,auto_approved,auto_rejected,high_risk}, rules:{}, bots:{} }
  const s = data.submissions || data.submission_stats || data;
  const pending   = s.pending        ?? 0;
  const reviewing = s.human_review   ?? 0;
  const approved  = s.auto_approved  ?? 0;
  const rejected  = s.auto_rejected  ?? 0;
  const escalated = s.escalated      ?? 0;
  const highRisk  = s.high_risk      ?? 0;
  const total     = pending + reviewing + approved + rejected + escalated + (data.submissions?.scanning ?? 0);

  return <div className="am-tab-content">
    <div className="am-tab-header">
      <div><h2 className="am-tab-title">Moderation Overview</h2><p className="am-tab-sub">Real-time moderation system status</p></div>
      <button className="am-btn am-btn--ghost am-btn--sm" onClick={refetch}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>

    <div className="am-stats-row">
      <Stat label="Total"        value={total}     color="orange"/>
      <Stat label="Pending"      value={pending}   color="gold"/>
      <Stat label="In Review"    value={reviewing} color="cyan"/>
      <Stat label="Auto-Approved"value={approved}  color="green"/>
      <Stat label="Auto-Rejected"value={rejected}  color="red"/>
      <Stat label="Escalated"    value={escalated} color="purple"/>
      <Stat label="High Risk"    value={highRisk}  color="red"/>
    </div>

    {(data.rules || data.rule_stats)&&<div className="am-dash-grid">
      <div className="am-dash-card">
        <div className="am-dash-card-title">⚡ Rules</div>
        <div className="am-kv-grid">
          <KV k="Total Rules"  v={(data.rules || data.rule_stats)?.total}/>
          <KV k="Active Rules" v={(data.rules || data.rule_stats)?.active}/>
          <KV k="Triggered 24h" v={(data.rules || data.rule_stats)?.triggered_today ?? '—'}/>
        </div>
      </div>
      <div className="am-dash-card">
        <div className="am-dash-card-title">🤖 Bots</div>
        <div className="am-kv-grid">
          <KV k="Total"   v={(data.bots || data.bot_stats)?.total ?? '—'}/>
          <KV k="Running" v={(data.bots || data.bot_stats)?.running ?? 0}/>
          <KV k="Errors"  v={(data.bots || data.bot_stats)?.error ?? 0}/>
        </div>
      </div>
      <div className="am-dash-card">
        <div className="am-dash-card-title">🔍 AI Scans</div>
        <div className="am-kv-grid">
          <KV k="Total Scans" v={data.scan_stats?.total}/>
          <KV k="Flagged"     v={data.scan_stats?.flagged}/>
          <KV k="Avg Conf"    v={data.scan_stats?.avg_confidence ? fmtConf(data.scan_stats.avg_confidence) : '—'}/>
        </div>
      </div>
    </div>}

    {/* Risk breakdown */}
    {data.risk_breakdown&&<div className="am-dash-card" style={{marginTop:'1rem'}}>
      <div className="am-dash-card-title">📊 Risk Level Breakdown</div>
      {RISK_LEVELS.map(r=>{
        const count = data.risk_breakdown[r]||0;
        const pct   = total>0?(count/total):0;
        return <div key={r} style={{marginBottom:'8px'}}>
          <div style={{display:'flex',justifyContent:'space-between',fontSize:'.78rem',marginBottom:'3px'}}>
            <Badge value={r}/><span style={{color:'var(--am-muted)'}}>{count}</span>
          </div>
          <div className="am-risk-bar-wrap"><div className={`am-risk-bar am-risk-bar--${r}`} style={{width:`${pct*100}%`}}/></div>
        </div>;
      })}
    </div>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 2 — Review Queue
// ══════════════════════════════════════════════════════════════════
function QueueTab(){
  const { queue, loading, error, fetchQueue, reviewSubmission, rescanSubmission } = useSubmissions();
  const [modal,   setModal]   = useState(null);
  const [target,  setTarget]  = useState(null);
  const [form,    setForm]    = useState({});
  const [saving,  setSaving]  = useState(false);
  const [err,     setErr]     = useState('');

  useEffect(()=>{ fetchQueue(); },[]);

  const F = (k,v)=>setForm(f=>({...f,[k]:v}));

  const openReview = t=>{ setTarget(t); setForm({decision:'approve',note:'',escalate_to_user_id:''}); setModal('review'); setErr(''); };

  const handleReview = async()=>{
    if(!form.decision) return;
    setSaving(true); setErr('');
    try{ await reviewSubmission(target.id, form.decision, form.note, form.escalate_to_user_id||null); setModal(null); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleRescan = async(id)=>{
    try{ await rescanSubmission(id,'combined'); fetchQueue(); }
    catch(e){ alert(errMsg(e)); }
  };

  if(loading) return <Skeleton/>;

  return <div className="am-tab-content">
    <div className="am-tab-header">
      <div><h2 className="am-tab-title">Review Queue</h2><p className="am-tab-sub">Submissions awaiting human review — highest risk first</p></div>
      <button className="am-btn am-btn--ghost am-btn--sm" onClick={fetchQueue}><Icon.RefreshCw size={13}/> Refresh</button>
    </div>
    {error&&<div className="am-error">{error}</div>}
    {queue.length===0
      ? <Empty icon="✅" text="Queue is empty — all caught up!"/>
      : <div className="am-queue-list">
          {queue.map(s=>(
            <div key={s.id} className={`am-queue-card am-queue-card--${s.risk_level}`}>
              <div className="am-queue-card-top">
                <div>
                  <div className="am-queue-card-id">{s.id?.slice(0,8)}…</div>
                  <div style={{fontSize:'.82rem',fontWeight:600,marginTop:'3px'}}>{s.submitter?.username||s.submitted_by||'Unknown User'}</div>
                </div>
                <Badge value={s.risk_level}/>
              </div>
              <div className="am-queue-card-meta">
                <Badge value={s.submission_type}/>
                <Badge value={s.status}/>
                {s.ai_confidence!=null&&<span style={{fontSize:'.75rem',color:'var(--am-muted)'}}>AI: {fmtConf(s.ai_confidence)}</span>}
                <span style={{fontSize:'.72rem',color:'var(--am-muted)'}}>{fmtDate(s.created_at)}</span>
              </div>
              {s.text_content&&<div className="am-queue-card-text">{s.text_content}</div>}
              {s.flag_reasons?.length>0&&<div style={{marginBottom:'8px',display:'flex',gap:'5px',flexWrap:'wrap'}}>
                {s.flag_reasons.map(r=><Badge key={r} value={r}/>)}
              </div>}
              <ConfBar value={s.ai_confidence}/>
              <div className="am-queue-card-acts">
                <button className="am-icon-btn am-icon-btn--green"  onClick={()=>openReview(s)}><Icon.CheckCircle size={13}/> Review</button>
                <button className="am-icon-btn am-icon-btn--cyan"   onClick={()=>handleRescan(s.id)}><Icon.RefreshCw size={13}/> Rescan</button>
              </div>
            </div>
          ))}
        </div>
    }

    {modal==='review'&&target&&<Modal title="Human Review Decision" onClose={()=>setModal(null)}>
      <div className="am-form">
        <div className="am-detail-section">
          <div className="am-kv-grid">
            <KV k="Type"       v={target.submission_type}/>
            <KV k="Risk"       v={target.risk_level}/>
            <KV k="AI Conf"    v={fmtConf(target.ai_confidence)}/>
            <KV k="Submitted"  v={fmtDate(target.created_at)}/>
          </div>
        </div>
        <Field label="Decision *">
          <select className="am-select" value={form.decision} onChange={e=>F('decision',e.target.value)}>
            <option value="approve">✅ Approve</option>
            <option value="reject">❌ Reject</option>
            <option value="escalate">🔺 Escalate</option>
            <option value="request_proof">📎 Request Proof</option>
          </select>
        </Field>
        {form.decision==='escalate'&&(
          <Field label="Escalate To User ID (required)">
            <input className="am-input" placeholder="Staff user UUID" value={form.escalate_to_user_id||''} onChange={e=>F('escalate_to_user_id',e.target.value)}/>
          </Field>
        )}
        <Field label="Note (optional)">
          <textarea className="am-textarea" rows={3} placeholder="Reviewer note..." value={form.note} onChange={e=>F('note',e.target.value)}/>
        </Field>
        {err&&<div className="am-form-error">{err}</div>}
        <div className="am-form-actions">
          <button className="am-btn am-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className={`am-btn ${form.decision==='approve'?'am-btn--green':'am-btn--red'}`} onClick={handleReview} disabled={saving}>
            {saving?'Submitting…':'Submit Decision'}
          </button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 3 — All Submissions
// ══════════════════════════════════════════════════════════════════
function SubmissionsTab(){
  const [statusF, setStatusF] = useState('');
  const [typeF,   setTypeF]   = useState('');
  const [riskF,   setRiskF]   = useState('');
  const { submissions, loading, error, reviewSubmission, rescanSubmission, bulkAction } = useSubmissions(
    Object.fromEntries(Object.entries({status:statusF,submission_type:typeF,risk_level:riskF}).filter(([,v])=>v))
  );

  const [selected,   setSelected]   = useState([]);
  const [bulkModal,  setBulkModal]  = useState(false);
  const [bulkDec,    setBulkDec]    = useState('approve');
  const [bulkNote,   setBulkNote]   = useState('');
  const [bulkSaving, setBulkSaving] = useState(false);
  const [err,        setErr]        = useState('');

  const toggleSel = id => setSelected(p => p.includes(id)?p.filter(x=>x!==id):[...p,id]);
  const toggleAll = () => setSelected(p => p.length===submissions.length?[]:submissions.map(s=>s.id));

  const handleBulk = async()=>{
    if(!selected.length) return;
    setBulkSaving(true); setErr('');
    try{ await bulkAction(selected, bulkDec, bulkNote); setSelected([]); setBulkModal(false); }
    catch(e){ setErr(errMsg(e)); } finally{ setBulkSaving(false); }
  };

  const pending   = submissions.filter(s=>s.status==='pending').length;
  const review    = submissions.filter(s=>s.status==='human_review').length;
  const escalated = submissions.filter(s=>s.status==='escalated').length;

  return <div className="am-tab-content">
    <div className="am-stats-row">
      <Stat label="Total"    value={submissions.length} color="orange"/>
      <Stat label="Pending"  value={pending}            color="gold"/>
      <Stat label="In Review"value={review}             color="cyan"/>
      <Stat label="Escalated"value={escalated}          color="purple"/>
    </div>
    <div className="am-tab-header">
      <div><h2 className="am-tab-title">All Submissions</h2><p className="am-tab-sub">Full submission log with filter and bulk actions</p></div>
      <div className="am-header-acts">
        <select className="am-select" value={statusF} onChange={e=>setStatusF(e.target.value)} style={{width:'auto'}}>
          <option value="">All Status</option>{MOD_STATUS.map(s=><option key={s}>{s}</option>)}
        </select>
        <select className="am-select" value={typeF} onChange={e=>setTypeF(e.target.value)} style={{width:'auto'}}>
          <option value="">All Types</option>{SUB_TYPES.map(t=><option key={t}>{t}</option>)}
        </select>
        <select className="am-select" value={riskF} onChange={e=>setRiskF(e.target.value)} style={{width:'auto'}}>
          <option value="">All Risk</option>{RISK_LEVELS.map(r=><option key={r}>{r}</option>)}
        </select>
      </div>
    </div>

    {selected.length>0&&<div className="am-bulk-bar">
      <span className="am-bulk-count">{selected.length} selected</span>
      <button className="am-icon-btn am-icon-btn--orange" onClick={()=>setBulkModal(true)}><Icon.Zap size={13}/> Bulk Action</button>
      <button className="am-icon-btn" onClick={()=>setSelected([])}><Icon.X size={13}/> Clear</button>
    </div>}

    {error&&<div className="am-error">{error}</div>}
    {loading?<Skeleton/>:submissions.length===0
      ?<Empty icon="📋" text="No submissions found"/>
      :<div className="am-table-wrap"><table className="am-table">
        <thead><tr>
          <th><input type="checkbox" checked={selected.length===submissions.length&&submissions.length>0} onChange={toggleAll}/></th>
          <th>ID</th><th>User</th><th>Type</th><th>Status</th><th>Risk</th><th>AI Conf</th><th>Submitted</th><th>Actions</th>
        </tr></thead>
        <tbody>{submissions.map(s=>(
          <tr key={s.id}>
            <td><input type="checkbox" checked={selected.includes(s.id)} onChange={()=>toggleSel(s.id)}/></td>
            <td><code className="am-td-code">{s.id?.slice(0,8)}…</code></td>
            <td className="am-td-user">{s.submitter?.username||s.submitted_by||'—'}</td>
            <td><Badge value={s.submission_type}/></td>
            <td><Badge value={s.status}/></td>
            <td><Badge value={s.risk_level}/></td>
            <td style={{minWidth:'100px'}}><ConfBar value={s.ai_confidence}/></td>
            <td className="am-td-muted">{fmtDate(s.created_at)}</td>
            <td><div className="am-actions">
              {['pending','human_review','escalated'].includes(s.status)&&(
                <button className="am-icon-btn am-icon-btn--green" onClick={async()=>{
                  try{ await reviewSubmission(s.id,'approve',''); }catch(e){ alert(errMsg(e)); }
                }} title="Quick Approve"><Icon.Check size={13}/></button>
              )}
              {['pending','human_review'].includes(s.status)&&(
                <button className="am-icon-btn am-icon-btn--red" onClick={async()=>{
                  try{ await reviewSubmission(s.id,'reject',''); }catch(e){ alert(errMsg(e)); }
                }} title="Quick Reject"><Icon.X size={13}/></button>
              )}
              <button className="am-icon-btn am-icon-btn--cyan" onClick={async()=>{
                try{ await rescanSubmission(s.id); }catch(e){ alert(errMsg(e)); }
              }} title="Rescan"><Icon.RefreshCw size={13}/></button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    }

    {bulkModal&&<Modal title={`Bulk Action — ${selected.length} submissions`} onClose={()=>setBulkModal(false)}>
      <div className="am-form">
        <Field label="Action *">
          <select className="am-select" value={bulkDec} onChange={e=>setBulkDec(e.target.value)}>
            <option value="approve">✅ Approve All</option>
            <option value="reject">❌ Reject All</option>
            <option value="escalate">🔺 Escalate All</option>
          </select>
        </Field>
        <Field label="Note (optional)">
          <textarea className="am-textarea" rows={2} value={bulkNote} onChange={e=>setBulkNote(e.target.value)} placeholder="Bulk action reason..."/>
        </Field>
        {err&&<div className="am-form-error">{err}</div>}
        <div className="am-form-actions">
          <button className="am-btn am-btn--ghost" onClick={()=>setBulkModal(false)}>Cancel</button>
          <button className="am-btn am-btn--orange" onClick={handleBulk} disabled={bulkSaving}>{bulkSaving?'Processing…':'Apply to All'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 4 — Rules
// ══════════════════════════════════════════════════════════════════
function RulesTab(){
  const { rules, loading, error, createRule, updateRule, deleteRule, toggleRule } = useRules();
  const [modal,  setModal]  = useState(null);
  const [target, setTarget] = useState(null);
  const [form,   setForm]   = useState({});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [condsText, setCondsText] = useState('[]');

  const F = (k,v)=>setForm(f=>({...f,[k]:v}));

  const openCreate = ()=>{
    setTarget(null);
    setForm({name:'',description:'',submission_type:'task_proof',priority:50,action:'flag',confidence_threshold:0.8,is_active:true});
    setCondsText('[\n  {\n    "field": "text_length",\n    "operator": "gt",\n    "value": 10\n  }\n]');
    setModal('form'); setErr('');
  };
  const openEdit = t=>{
    setTarget(t);
    setForm({...t});
    setCondsText(JSON.stringify(t.conditions||[], null, 2));
    setModal('form'); setErr('');
  };

  const handleSave = async()=>{
    setSaving(true); setErr('');
    try{
      let conds;
      try{ conds = JSON.parse(condsText); }
      catch{ throw new Error('Conditions JSON is invalid'); }
      const payload = { ...form, conditions: conds };
      if(target) await updateRule(target.id, payload);
      else       await createRule(payload);
      setModal(null);
    }catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleDelete = async t=>{
    if(t.is_system){ alert('System rules cannot be deleted.'); return; }
    if(!confirm(`Delete rule "${t.name}"?`)) return;
    try{ await deleteRule(t.id); }catch(e){ alert(errMsg(e)); }
  };

  const active = rules.filter(r=>r.is_active).length;

  return <div className="am-tab-content">
    <div className="am-stats-row">
      <Stat label="Total Rules"  value={rules.length} color="orange"/>
      <Stat label="Active"       value={active}       color="green"/>
      <Stat label="Inactive"     value={rules.length-active} color="red"/>
    </div>
    <div className="am-tab-header">
      <div><h2 className="am-tab-title">Auto-Approval Rules</h2><p className="am-tab-sub">Configure rules that auto-approve, reject or escalate submissions</p></div>
      <button className="am-btn am-btn--orange" onClick={openCreate}><Icon.Plus size={14}/> New Rule</button>
    </div>
    {error&&<div className="am-error">{error}</div>}
    {loading?<Skeleton/>:rules.length===0
      ?<Empty icon="⚡" text="No rules configured" onAdd={openCreate}/>
      :<div className="am-rule-card-list">
          {rules.map(r=>(
            <div key={r.id} className={`am-rule-card${!r.is_active?' am-rule-card--off':''}`}>
              <div style={{flex:1}}>
                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px'}}>
                  <div className="am-rule-card-name">{r.name}</div>
                  {r.is_system&&<span className="am-badge am-badge--muted">SYSTEM</span>}
                </div>
                <div className="am-rule-card-meta">
                  <Badge value={r.submission_type}/>
                  <Badge value={r.action}/>
                  <span className="am-badge am-badge--muted">Pri: {r.priority}</span>
                  <span className="am-badge am-badge--muted">Conf ≥ {fmtConf(r.confidence_threshold)}</span>
                  {r.condition_count>0&&<span className="am-badge am-badge--muted">{r.condition_count} condition{r.condition_count!==1?'s':''}</span>}
                </div>
                {r.description&&<div className="am-rule-card-desc">{r.description}</div>}
              </div>
              <div className="am-actions" style={{flexShrink:0}}>
                <label className="am-toggle" title={r.is_active?'Disable':'Enable'} onClick={()=>toggleRule(r.id)}>
                  <input type="checkbox" checked={!!r.is_active} readOnly/>
                  <span className="am-toggle-slider"/>
                </label>
                <button className="am-icon-btn" onClick={()=>openEdit(r)} title="Edit"><Icon.Edit2 size={13}/></button>
                {!r.is_system&&<button className="am-icon-btn am-icon-btn--red" onClick={()=>handleDelete(r)} title="Delete"><Icon.Trash2 size={13}/></button>}
              </div>
            </div>
          ))}
        </div>
    }

    {modal==='form'&&<Modal title={target?`Edit Rule — ${target.name}`:'New Auto-Approval Rule'} onClose={()=>setModal(null)} wide>
      <div className="am-form">
        <div className="am-form-row">
          <Field label="Name *"><input className="am-input" placeholder="Rule name" value={form.name||''} onChange={e=>F('name',e.target.value)}/></Field>
          <Field label="Priority (1=highest)"><input className="am-input" type="number" min="1" max="100" value={form.priority??50} onChange={e=>F('priority',Number(e.target.value))}/></Field>
        </div>
        <div className="am-form-row">
          <Field label="Submission Type">
            <select className="am-select" value={form.submission_type||'task_proof'} onChange={e=>F('submission_type',e.target.value)}>
              {SUB_TYPES.map(t=><option key={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Action">
            <select className="am-select" value={form.action||'flag'} onChange={e=>F('action',e.target.value)}>
              {RULE_ACTIONS.map(a=><option key={a}>{a}</option>)}
            </select>
          </Field>
          <Field label="Confidence Threshold">
            <input className="am-input" type="number" min="0" max="1" step="0.05" value={form.confidence_threshold??0.8} onChange={e=>F('confidence_threshold',Number(e.target.value))}/>
          </Field>
        </div>
        <Field label="Description">
          <input className="am-input" placeholder="Optional description" value={form.description||''} onChange={e=>F('description',e.target.value)}/>
        </Field>
        <Field label="Conditions (JSON array)">
          <textarea className="am-textarea" rows={8} value={condsText} onChange={e=>setCondsText(e.target.value)}/>
        </Field>
        <label style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'.85rem',cursor:'pointer'}}>
          <input type="checkbox" checked={!!form.is_active} onChange={e=>F('is_active',e.target.checked)} style={{accentColor:'var(--am-green)',width:'15px',height:'15px'}}/>
          Active (rule will be evaluated)
        </label>
        {err&&<div className="am-form-error">{err}</div>}
        <div className="am-form-actions">
          <button className="am-btn am-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="am-btn am-btn--orange" onClick={handleSave} disabled={saving}>{saving?'Saving…':target?'Update Rule':'Create Rule'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 5 — Bots
// ══════════════════════════════════════════════════════════════════
function BotsTab(){
  const { bots, loading, error, createBot, updateBot, deleteBot, startBot, stopBot, getBotHealth } = useBots();
  const [modal,  setModal]  = useState(null);
  const [target, setTarget] = useState(null);
  const [form,   setForm]   = useState({});
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const [health, setHealth] = useState(null);

  const F = (k,v)=>setForm(f=>({...f,[k]:v}));

  const openCreate = ()=>{ setTarget(null); setForm({name:'',description:'',submission_type:'task_proof',config:{max_batch_size:50,process_interval:60,auto_escalate:true,notify_on_error:true}}); setModal('form'); setErr(''); };
  const openEdit   = t=>{ setTarget(t); setForm({...t}); setModal('form'); setErr(''); };

  const openHealth = async t=>{
    setTarget(t); setHealth(null); setModal('health');
    try{ const h = await getBotHealth(t.id); setHealth(h); }
    catch(e){ setHealth({error:errMsg(e)}); }
  };

  const handleSave = async()=>{
    setSaving(true); setErr('');
    try{
      if(!form.name?.trim()) throw new Error('Name required');
      if(target) await updateBot(target.id, form);
      else       await createBot(form);
      setModal(null);
    }catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  const handleStart = async id=>{ try{ await startBot(id); }catch(e){ alert(errMsg(e)); }};
  const handleStop  = async id=>{ try{ await stopBot(id);  }catch(e){ alert(errMsg(e)); }};
  const handleDelete= async t=>{ if(!confirm(`Delete bot "${t.name}"?`)) return; try{ await deleteBot(t.id); }catch(e){ alert(errMsg(e)); }};

  const running = bots.filter(b=>b.status==='running').length;
  const errBots = bots.filter(b=>b.status==='error').length;

  return <div className="am-tab-content">
    <div className="am-stats-row">
      <Stat label="Total Bots" value={bots.length} color="orange"/>
      <Stat label="Running"    value={running}      color="green"/>
      <Stat label="Errors"     value={errBots}      color="red"/>
    </div>
    <div className="am-tab-header">
      <div><h2 className="am-tab-title">Task Bots</h2><p className="am-tab-sub">Autonomous bots that process moderation queues on a schedule</p></div>
      <button className="am-btn am-btn--orange" onClick={openCreate}><Icon.Plus size={14}/> New Bot</button>
    </div>
    {error&&<div className="am-error">{error}</div>}
    {loading?<Skeleton/>:bots.length===0
      ?<Empty icon="🤖" text="No bots configured" onAdd={openCreate}/>
      :<div className="am-bot-grid">
          {bots.map(b=>(
            <div key={b.id} className="am-bot-card">
              <div className="am-bot-card-top">
                <div>
                  <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
                    <BotPulse status={b.status}/>
                    <div className="am-bot-card-name">{b.name}</div>
                  </div>
                  <div className="am-bot-card-desc">{b.description||b.submission_type}</div>
                </div>
                <Badge value={b.status}/>
              </div>
              <div className="am-bot-stats">
                <div className="am-bot-stat"><div className="am-bot-stat-v" style={{color:'var(--am-cyan)'}}>{b.total_processed||0}</div><div className="am-bot-stat-l">Processed</div></div>
                <div className="am-bot-stat"><div className="am-bot-stat-v" style={{color:'var(--am-green)'}}>{b.total_approved||0}</div><div className="am-bot-stat-l">Approved</div></div>
                <div className="am-bot-stat"><div className="am-bot-stat-v" style={{color:'var(--am-red)'}}>{b.total_rejected||0}</div><div className="am-bot-stat-l">Rejected</div></div>
                <div className="am-bot-stat"><div className="am-bot-stat-v" style={{color:'var(--am-purple)'}}>{b.total_escalated||0}</div><div className="am-bot-stat-l">Escalated</div></div>
              </div>
              <div className="am-bot-acts">
                {b.status!=='running'&&<button className="am-icon-btn am-icon-btn--green" onClick={()=>handleStart(b.id)}><Icon.Play size={13}/> Start</button>}
                {b.status==='running'&&<button className="am-icon-btn am-icon-btn--orange" onClick={()=>handleStop(b.id)}><Icon.Square size={13}/> Stop</button>}
                <button className="am-icon-btn am-icon-btn--cyan" onClick={()=>openHealth(b)}><Icon.Activity size={13}/> Health</button>
                <button className="am-icon-btn" onClick={()=>openEdit(b)}><Icon.Edit2 size={13}/></button>
                <button className="am-icon-btn am-icon-btn--red" onClick={()=>handleDelete(b)}><Icon.Trash2 size={13}/></button>
              </div>
            </div>
          ))}
        </div>
    }

    {modal==='form'&&<Modal title={target?`Edit Bot — ${target.name}`:'New Task Bot'} onClose={()=>setModal(null)}>
      <div className="am-form">
        <Field label="Name *"><input className="am-input" placeholder="e.g. Task Proof Scanner" value={form.name||''} onChange={e=>F('name',e.target.value)}/></Field>
        <Field label="Description"><input className="am-input" placeholder="What this bot does" value={form.description||''} onChange={e=>F('description',e.target.value)}/></Field>
        <Field label="Target Submission Type">
          <select className="am-select" value={form.submission_type||'task_proof'} onChange={e=>F('submission_type',e.target.value)}>
            {SUB_TYPES.map(t=><option key={t}>{t}</option>)}
          </select>
        </Field>
        {err&&<div className="am-form-error">{err}</div>}
        <div className="am-form-actions">
          <button className="am-btn am-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="am-btn am-btn--orange" onClick={handleSave} disabled={saving}>{saving?'Saving…':target?'Update Bot':'Create Bot'}</button>
        </div>
      </div>
    </Modal>}

    {modal==='health'&&target&&<Modal title={`Bot Health — ${target.name}`} onClose={()=>setModal(null)}>
      {!health
        ? <div style={{textAlign:'center',padding:'2rem',color:'var(--am-muted)'}}>Loading health data…</div>
        : health.error
          ? <div className="am-form-error">{health.error}</div>
          : <div className="am-kv-grid">
              {Object.entries(health).map(([k,v])=><KV key={k} k={k.replace(/_/g,' ')} v={String(v)}/>)}
            </div>
      }
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════
const TABS = [
  { id:'dashboard',   label:'Dashboard',    icon:<Icon.BarChart2 size={15}/> },
  { id:'queue',       label:'Review Queue', icon:<Icon.AlertTriangle size={15}/>, alert:true },
  { id:'submissions', label:'Submissions',  icon:<Icon.FileText size={15}/> },
  { id:'rules',       label:'Rules',        icon:<Icon.Zap size={15}/> },
  { id:'bots',        label:'Bots',         icon:<Icon.Cpu size={15}/> },
];

export default function AutoMod(){
  const [activeTab, setActiveTab] = useState('dashboard');
  return <div className="am-root">
    <div className="am-page-header">
      <div className="am-page-header-inner">
        <div className="am-page-title-wrap">
          <span className="am-page-icon">🛡️</span>
          <div>
            <h1 className="am-page-title">AUTO-MODERATION</h1>
            <p className="am-page-sub">AI-powered content moderation — rules, bots, queue and scan results</p>
          </div>
        </div>
      </div>
      <div className="am-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={`am-tab${activeTab===t.id?' am-tab--active':''}`} onClick={()=>setActiveTab(t.id)}>
            {t.icon} {t.label}
            {t.alert&&<span className="am-tab-badge am-tab-badge--red">!</span>}
          </button>
        ))}
      </div>
    </div>
    <div className="am-content">
      {activeTab==='dashboard'   && <DashboardTab/>}
      {activeTab==='queue'       && <QueueTab/>}
      {activeTab==='submissions' && <SubmissionsTab/>}
      {activeTab==='rules'       && <RulesTab/>}
      {activeTab==='bots'        && <BotsTab/>}
    </div>
  </div>;
}
