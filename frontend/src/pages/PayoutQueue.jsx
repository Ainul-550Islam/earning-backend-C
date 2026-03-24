// src/pages/PayoutQueue.jsx
// Payout Queue — Full Featured: Add Items, Retry, Fee Calc, Priorities
import { useState, useCallback } from 'react';
import * as Icon from 'react-feather';
import { useBatches, usePayoutItems, useLogs, usePriorities } from '../hooks/usePayoutQueue';
import { batchApi, itemApi } from '../api/endpoints/PayoutQueue';
import '../styles/PayoutQueue.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

const GATEWAYS   = ['bkash','nagad','rocket','upay','bank'];
const PRIORITIES = ['LOW','NORMAL','HIGH','CRITICAL'];
const BATCH_STATUS = ['PENDING','PROCESSING','COMPLETED','PARTIALLY_COMPLETED','FAILED','CANCELLED','ON_HOLD'];
const ITEM_STATUS  = ['QUEUED','PROCESSING','SUCCESS','FAILED','CANCELLED','SKIPPED'];
const FEE_RATES  = { bkash:0.015, nagad:0.01, rocket:0.018, upay:0.012, bank:0.005 };
const GICONS     = { bkash:'\ud83d\udc97', nagad:'\ud83d\udfe0', rocket:'\ud83d\udfe3', upay:'\ud83d\udd35', bank:'\ud83c\udfe6' };
const SCOLOR     = { PENDING:'gold',PROCESSING:'cyan',COMPLETED:'green',PARTIALLY_COMPLETED:'gold',FAILED:'red',CANCELLED:'muted',ON_HOLD:'pink',QUEUED:'gold',SUCCESS:'green',SKIPPED:'muted',LOW:'muted',NORMAL:'cyan',HIGH:'gold',CRITICAL:'red' };

const fmtDate   = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '\u2014';
const fmtAmt    = a => a != null ? `\u09f3${Number(a).toLocaleString('en-BD',{minimumFractionDigits:2})}` : '\u2014';
const calcFee   = (a,g) => (Number(a)||0)*(FEE_RATES[g]||0);
const errMsg    = e => e?.response?.data ? JSON.stringify(e.response.data) : (e.message||'Error');

function Badge({value}){ const c=SCOLOR[value]||'muted'; return <span className={`pq-badge pq-badge--${c}`}>{value?.replace(/_/g,' ')}</span>; }
function Stat({label,value,color='cyan'}){ return <div className={`pq-stat pq-stat--${color}`}><div className="pq-stat-value">{value}</div><div className="pq-stat-label">{label}</div></div>; }
function Skeleton(){ return <div className="pq-loading">{[1,2,3,4].map(i=><div key={i} className="pq-loading-row"/>)}</div>; }
function Empty({icon,text,onAdd}){ return <div className="pq-empty"><div className="pq-empty-icon">{icon}</div><p className="pq-empty-text">{text}</p>{onAdd&&<button className="pq-btn pq-btn--cyan" onClick={onAdd}>+ Create First</button>}</div>; }
function Modal({title,onClose,children,wide}){ return <div className="pq-modal-bg" onClick={e=>e.target===e.currentTarget&&onClose()}><div className={`pq-modal${wide?' pq-modal--wide':''}`}><div className="pq-modal-header"><h3 className="pq-modal-title">{title}</h3><button className="pq-modal-close" onClick={onClose}><Icon.X size={18}/></button></div><div className="pq-modal-body">{children}</div></div></div>; }
function Field({label,children}){ return <div className="pq-field"><label className="pq-field-label">{label}</label>{children}</div>; }

function FeeCalc({gateway}){
  const [amt,setAmt]=useState('');
  const fee=calcFee(amt,gateway); const net=(Number(amt)||0)-fee; const rate=((FEE_RATES[gateway]||0)*100).toFixed(1);
  return <div className="pq-fee-calc">
    <div className="pq-fee-title">\ud83d\udcb0 Fee Preview ({GICONS[gateway]} {gateway} \u00b7 {rate}%)</div>
    <input className="pq-input pq-input--sm" type="number" placeholder="Enter gross amount (BDT)" value={amt} onChange={e=>setAmt(e.target.value)}/>
    {amt&&<div className="pq-fee-result"><span>Gross: <b>{fmtAmt(amt)}</b></span><span>Fee: <b className="pq-red">{fmtAmt(fee)}</b></span><span>Net: <b className="pq-green">{fmtAmt(net)}</b></span></div>}
  </div>;
}

function ItemRows({items,setItems,gateway}){
  const add = ()=>setItems(p=>[...p,{user_id:'',account_number:'',gross_amount:'',note:''}]);
  const rem = i=>setItems(p=>p.filter((_,x)=>x!==i));
  const upd = (i,f,v)=>setItems(p=>p.map((r,x)=>x===i?{...r,[f]:v}:r));
  return <div className="pq-items-section">
    <div className="pq-items-header"><span className="pq-field-label">Payout Items</span><button type="button" className="pq-btn pq-btn--ghost pq-btn--sm" onClick={add}>+ Add Row</button></div>
    {gateway&&<FeeCalc gateway={gateway}/>}
    <div className="pq-items-table">
      <div className="pq-items-thead"><span>User ID</span><span>Account No.</span><span>Gross (BDT)</span><span>Note</span><span></span></div>
      {items.map((it,i)=><div key={i} className="pq-items-row">
        <input className="pq-input pq-input--sm" placeholder="User ID" value={it.user_id} onChange={e=>upd(i,'user_id',e.target.value)}/>
        <input className="pq-input pq-input--sm" placeholder="01XXXXXXXXX" value={it.account_number} onChange={e=>upd(i,'account_number',e.target.value)}/>
        <input className="pq-input pq-input--sm" type="number" placeholder="500" value={it.gross_amount} onChange={e=>upd(i,'gross_amount',e.target.value)}/>
        <input className="pq-input pq-input--sm" placeholder="Optional" value={it.note} onChange={e=>upd(i,'note',e.target.value)}/>
        <button type="button" className="pq-icon-btn pq-icon-btn--red" onClick={()=>rem(i)} disabled={items.length===1}><Icon.Minus size={12}/></button>
      </div>)}
    </div>
  </div>;
}

function BatchesTab({onSelectBatch}){
  const {batches,loading,error,createBatch,cancelBatch,processBatch}=useBatches();
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [items,setItems]=useState([{user_id:'',account_number:'',gross_amount:'',note:''}]);
  const [saving,setSaving]=useState(false);
  const [err,setErr]=useState('');
  const [filter,setFilter]=useState('');
  const [statsData,setStatsData]=useState(null);
  const [addTarget,setAddTarget]=useState(null);

  const openCreate=()=>{setForm({name:'',gateway:'bkash',priority:'NORMAL',note:''});setItems([{user_id:'',account_number:'',gross_amount:'',note:''}]);setModal('create');setErr('');};
  const openAddItems=b=>{setAddTarget(b);setItems([{user_id:'',account_number:'',gross_amount:'',note:''}]);setModal('addItems');setErr('');};

  const handleSave=async()=>{
    if(!form.name?.trim()){setErr('Batch name required');return;}
    setSaving(true);setErr('');
    try{
      const vi=items.filter(it=>it.user_id&&it.account_number&&it.gross_amount);
      await createBatch({...form,items:vi.map(it=>({...it,user_id:Number(it.user_id),gross_amount:String(it.gross_amount)}))});
      setModal(null);
    }catch(e){setErr(errMsg(e));}finally{setSaving(false);}
  };

  const handleAddItems=async()=>{
    const vi=items.filter(it=>it.user_id&&it.account_number&&it.gross_amount);
    if(!vi.length){setErr('Add at least one valid item');return;}
    setSaving(true);setErr('');
    try{
      await batchApi.addItems(addTarget.id,{items:vi.map(it=>({...it,user_id:Number(it.user_id),gross_amount:String(it.gross_amount)}))});
      setModal(null);
    }catch(e){setErr(errMsg(e));}finally{setSaving(false);}
  };

  const handleProcess=async(b,async_=false)=>{if(!confirm(`${async_?'Queue':'Process'} "${b.name}"?`))return;try{await processBatch(b.id,async_);}catch(e){alert(e.message);}};
  const handleCancel=async b=>{if(!confirm(`Cancel "${b.name}"?`))return;try{await cancelBatch(b.id);}catch(e){alert(e.message);}};
  const handleStats=async b=>{try{const r=await batchApi.statistics(b.id);setStatsData({batch:b,stats:r.data});setModal('stats');}catch(e){alert(e.message);}};

  const filtered=filter?batches.filter(b=>b.status===filter):batches;
  const totalAmt=batches.reduce((s,b)=>s+Number(b.total_amount||0),0);

  return <div className="pq-tab-content">
    <div className="pq-stats-row">
      <Stat label="Total Batches" value={batches.length} color="cyan"/>
      <Stat label="Pending" value={batches.filter(b=>b.status==='PENDING').length} color="gold"/>
      <Stat label="Processing" value={batches.filter(b=>b.status==='PROCESSING').length} color="pink"/>
      <Stat label="Total Amount" value={fmtAmt(totalAmt)} color="green"/>
    </div>
    <div className="pq-tab-header">
      <div><h2 className="pq-tab-title">Payout Batches</h2><p className="pq-tab-sub">Create and manage payout batches across payment gateways</p></div>
      <div className="pq-header-actions">
        <select className="pq-select pq-select--sm" value={filter} onChange={e=>setFilter(e.target.value)}>
          <option value="">All Status</option>{BATCH_STATUS.map(s=><option key={s}>{s}</option>)}
        </select>
        <button className="pq-btn pq-btn--cyan" onClick={openCreate}><Icon.Plus size={14}/> New Batch</button>
      </div>
    </div>
    {error&&<div className="pq-error">{error}</div>}
    {loading?<Skeleton/>:filtered.length===0?<Empty icon="\ud83d\udce6" text="No batches found" onAdd={openCreate}/>:
      <div className="pq-table-wrap"><table className="pq-table">
        <thead><tr><th>Batch</th><th>Gateway</th><th>Priority</th><th>Status</th><th>Items</th><th>Total</th><th>Net</th><th>Scheduled</th><th>Actions</th></tr></thead>
        <tbody>{filtered.map(b=><tr key={b.id} className="pq-table-row">
          <td><button className="pq-link" onClick={()=>onSelectBatch(b)}>{b.name}</button>{b.error_summary&&<div className="pq-row-error">{b.error_summary.slice(0,60)}</div>}</td>
          <td><span className="pq-gateway">{GICONS[b.gateway]||'\ud83d\udcb3'} {b.gateway}</span></td>
          <td><Badge value={b.priority}/></td>
          <td><Badge value={b.status}/></td>
          <td><span className="pq-count">{b.item_count}{b.success_count>0&&<span className="pq-count--green"> \u00b7{b.success_count}\u2713</span>}{b.failure_count>0&&<span className="pq-count--red"> \u00b7{b.failure_count}\u2717</span>}</span></td>
          <td className="pq-amount">{fmtAmt(b.total_amount)}</td>
          <td className="pq-amount pq-amount--net">{fmtAmt(b.net_amount)}</td>
          <td className="pq-muted">{fmtDate(b.scheduled_at)}</td>
          <td><div className="pq-actions">
            {b.status==='PENDING'&&<>
              <button className="pq-icon-btn pq-icon-btn--cyan" title="Add Items" onClick={()=>openAddItems(b)}><Icon.PlusCircle size={13}/></button>
              <button className="pq-icon-btn pq-icon-btn--green" title="Process now" onClick={()=>handleProcess(b)}><Icon.Play size={13}/></button>
              <button className="pq-icon-btn" title="Queue async" onClick={()=>handleProcess(b,true)}><Icon.Clock size={13}/></button>
            </>}
            <button className="pq-icon-btn" title="Statistics" onClick={()=>handleStats(b)}><Icon.BarChart2 size={13}/></button>
            {['PENDING','ON_HOLD'].includes(b.status)&&<button className="pq-icon-btn pq-icon-btn--red" title="Cancel" onClick={()=>handleCancel(b)}><Icon.XCircle size={13}/></button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>
    }
    {modal==='create'&&<Modal title="New Payout Batch" onClose={()=>setModal(null)} wide>
      <div className="pq-form">
        <Field label="Batch Name *"><input className="pq-input" placeholder="e.g. March Week 1 Payouts" value={form.name||''} onChange={e=>setForm(f=>({...f,name:e.target.value}))}/></Field>
        <div className="pq-form-row">
          <Field label="Gateway"><select className="pq-select" value={form.gateway||''} onChange={e=>setForm(f=>({...f,gateway:e.target.value}))}>{GATEWAYS.map(g=><option key={g}>{g}</option>)}</select></Field>
          <Field label="Priority"><select className="pq-select" value={form.priority||''} onChange={e=>setForm(f=>({...f,priority:e.target.value}))}>{PRIORITIES.map(p=><option key={p}>{p}</option>)}</select></Field>
          <Field label="Scheduled At"><input className="pq-input" type="datetime-local" value={form.scheduled_at||''} onChange={e=>setForm(f=>({...f,scheduled_at:e.target.value}))}/></Field>
        </div>
        <Field label="Note"><textarea className="pq-textarea" rows={2} value={form.note||''} onChange={e=>setForm(f=>({...f,note:e.target.value}))}/></Field>
        <ItemRows items={items} setItems={setItems} gateway={form.gateway}/>
        {err&&<div className="pq-form-error">{err}</div>}
        <div className="pq-form-actions">
          <button className="pq-btn pq-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="pq-btn pq-btn--cyan" onClick={handleSave} disabled={saving}>{saving?'Creating\u2026':'Create Batch'}</button>
        </div>
      </div>
    </Modal>}
    {modal==='addItems'&&addTarget&&<Modal title={`Add Items \u2014 ${addTarget.name}`} onClose={()=>setModal(null)} wide>
      <div className="pq-form">
        <div className="pq-batch-info"><span>{GICONS[addTarget.gateway]} {addTarget.gateway}</span><Badge value={addTarget.status}/><span className="pq-muted">{addTarget.item_count} existing items</span></div>
        <ItemRows items={items} setItems={setItems} gateway={addTarget.gateway}/>
        {err&&<div className="pq-form-error">{err}</div>}
        <div className="pq-form-actions">
          <button className="pq-btn pq-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="pq-btn pq-btn--cyan" onClick={handleAddItems} disabled={saving}>{saving?'Adding\u2026':'Add Items'}</button>
        </div>
      </div>
    </Modal>}
    {modal==='stats'&&statsData&&<Modal title={`Statistics \u2014 ${statsData.batch.name}`} onClose={()=>setModal(null)}>
      <pre className="pq-stats-pre">{JSON.stringify(statsData.stats,null,2)}</pre>
    </Modal>}
  </div>;
}

function ItemsTab({selectedBatch,onClearBatch}){
  const {items,loading,error,cancelItem}=usePayoutItems(selectedBatch?.id);
  const [filter,setFilter]=useState('');
  const filtered=filter?items.filter(i=>i.status===filter):items;
  const totalNet=items.reduce((s,i)=>s+Number(i.net_amount||0),0);

  return <div className="pq-tab-content">
    {selectedBatch&&<div className="pq-batch-banner"><span>\ud83d\udce6 Batch: <strong>{selectedBatch.name}</strong> <Badge value={selectedBatch.status}/></span><button className="pq-btn pq-btn--ghost pq-btn--sm" onClick={onClearBatch}>Show All</button></div>}
    <div className="pq-stats-row">
      <Stat label="Total" value={items.length} color="cyan"/>
      <Stat label="Success" value={items.filter(i=>i.status==='SUCCESS').length} color="green"/>
      <Stat label="Failed" value={items.filter(i=>i.status==='FAILED').length} color="red"/>
      <Stat label="Net Paid" value={fmtAmt(totalNet)} color="gold"/>
    </div>
    <div className="pq-tab-header">
      <div><h2 className="pq-tab-title">Payout Items</h2><p className="pq-tab-sub">Individual disbursements \u2014 cancel queued items</p></div>
      <select className="pq-select pq-select--sm" value={filter} onChange={e=>setFilter(e.target.value)}>
        <option value="">All Status</option>{ITEM_STATUS.map(s=><option key={s}>{s}</option>)}
      </select>
    </div>
    {error&&<div className="pq-error">{error}</div>}
    {loading?<Skeleton/>:filtered.length===0?<Empty icon="\ud83d\udcb8" text="No payout items found"/>:
      <div className="pq-table-wrap"><table className="pq-table">
        <thead><tr><th>User</th><th>Gateway</th><th>Account</th><th>Gross</th><th>Fee</th><th>Net</th><th>Status</th><th>Retry</th><th>Error</th><th>Processed</th><th>Actions</th></tr></thead>
        <tbody>{filtered.map(item=><tr key={item.id} className="pq-table-row">
          <td><span className="pq-user-name">{item.user?.username||item.user}</span>{item.internal_reference&&<div className="pq-ref">{item.internal_reference.slice(0,12)}\u2026</div>}</td>
          <td><span className="pq-gateway">{GICONS[item.gateway]||'\ud83d\udcb3'} {item.gateway}</span></td>
          <td><code className="pq-code">{item.account_number}</code></td>
          <td className="pq-amount">{fmtAmt(item.gross_amount)}</td>
          <td className="pq-amount pq-amount--fee">{fmtAmt(item.fee_amount)}</td>
          <td className="pq-amount pq-amount--net">{fmtAmt(item.net_amount)}</td>
          <td><Badge value={item.status}/></td>
          <td className="pq-muted">{item.retry_count>0&&`${item.retry_count}\u00d7`}{item.next_retry_at&&<div className="pq-retry-at">next: {fmtDate(item.next_retry_at)}</div>}</td>
          <td>{item.error_code&&<span className="pq-error-code">{item.error_code}</span>}{item.error_message&&<button className="pq-icon-btn" title={item.error_message} onClick={()=>alert(item.error_message)}><Icon.AlertCircle size={13}/></button>}</td>
          <td className="pq-muted">{fmtDate(item.processed_at)}</td>
          <td><div className="pq-actions">
            {item.can_retry&&<button className="pq-icon-btn pq-icon-btn--gold" title="Can retry via batch reprocess"><Icon.RefreshCw size={13}/></button>}
            {['QUEUED','FAILED'].includes(item.status)&&<button className="pq-icon-btn pq-icon-btn--red" title="Cancel" onClick={()=>{if(confirm('Cancel?'))cancelItem(item.id);}}><Icon.XCircle size={13}/></button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>
    }
  </div>;
}

function LogsTab(){
  const {logs,loading,error}=useLogs();
  return <div className="pq-tab-content">
    <div className="pq-tab-header"><div><h2 className="pq-tab-title">Process Logs</h2><p className="pq-tab-sub">Bulk processing audit trail</p></div></div>
    {error&&<div className="pq-error">{error}</div>}
    {loading?<Skeleton/>:logs.length===0?<Empty icon="\ud83d\udccb" text="No logs yet"/>:
      <div className="pq-table-wrap"><table className="pq-table">
        <thead><tr><th>Batch</th><th>Status</th><th>Attempted</th><th>Succeeded</th><th>Failed</th><th>Skipped</th><th>Amount</th><th>Duration</th><th>Time</th></tr></thead>
        <tbody>{logs.map(l=><tr key={l.id} className="pq-table-row">
          <td className="pq-muted pq-monospace">{(l.batch||'\u2014').toString().slice(0,8)}\u2026</td>
          <td><Badge value={l.status||'UNKNOWN'}/></td>
          <td className="pq-muted">{l.items_attempted??'\u2014'}</td>
          <td className="pq-count--green">{l.items_succeeded??'\u2014'}</td>
          <td className="pq-count--red">{l.items_failed??'\u2014'}</td>
          <td className="pq-muted">{l.items_skipped??'\u2014'}</td>
          <td className="pq-amount">{fmtAmt(l.total_amount_processed)}</td>
          <td className="pq-muted">{l.duration_ms?`${l.duration_ms}ms`:'\u2014'}</td>
          <td className="pq-muted">{fmtDate(l.created_at)}</td>
        </tr>)}</tbody>
      </table></div>
    }
  </div>;
}

function PrioritiesTab(){
  const {priorities,loading,error}=usePriorities();
  return <div className="pq-tab-content">
    <div className="pq-tab-header"><div><h2 className="pq-tab-title">Withdrawal Priorities</h2><p className="pq-tab-sub">User-level priority overrides for payout order</p></div></div>
    {error&&<div className="pq-error">{error}</div>}
    {loading?<Skeleton/>:priorities.length===0?<Empty icon="\u26a1" text="No priority overrides"/>:
      <div className="pq-table-wrap"><table className="pq-table">
        <thead><tr><th>User</th><th>Priority</th><th>Previous</th><th>Reason</th><th>Note</th><th>Expires</th><th>Active</th></tr></thead>
        <tbody>{priorities.map(p=><tr key={p.id} className="pq-table-row">
          <td className="pq-user-name">{p.user}</td>
          <td><Badge value={p.priority}/></td>
          <td><Badge value={p.previous_priority}/></td>
          <td className="pq-muted">{p.reason_display||p.reason}</td>
          <td className="pq-muted">{p.reason_note||'\u2014'}</td>
          <td className="pq-muted">{fmtDate(p.expires_at)}</td>
          <td><span className={`pq-active-dot${p.is_active?' pq-active-dot--on':''}`}/></td>
        </tr>)}</tbody>
      </table></div>
    }
  </div>;
}

const TABS=[
  {id:'batches',    label:'Batches',      icon:<Icon.Package size={15}/>},
  {id:'items',      label:'Payout Items', icon:<Icon.DollarSign size={15}/>},
  {id:'logs',       label:'Process Logs', icon:<Icon.FileText size={15}/>},
  {id:'priorities', label:'Priorities',   icon:<Icon.Zap size={15}/>},
];

export default function PayoutQueue(){
  const [activeTab,setActiveTab]=useState('batches');
  const [selectedBatch,setSelectedBatch]=useState(null);
  const handleSelect=b=>{setSelectedBatch(b);setActiveTab('items');};
  return <div className="pq-root">
    <div className="pq-page-header">
      <div className="pq-page-header-inner">
        <div className="pq-page-title-wrap">
          <span className="pq-page-icon">\ud83d\udcb8</span>
          <div><h1 className="pq-page-title">PAYOUT QUEUE</h1><p className="pq-page-sub">Manage payout batches, track disbursements and monitor processing logs</p></div>
        </div>
      </div>
      <div className="pq-tabs">
        {TABS.map(t=><button key={t.id} className={`pq-tab${activeTab===t.id?' pq-tab--active':''}`} onClick={()=>setActiveTab(t.id)}>
          {t.icon} {t.label}
          {t.id==='items'&&selectedBatch&&<span className="pq-tab-badge">{selectedBatch.name.slice(0,10)}\u2026</span>}
        </button>)}
      </div>
    </div>
    <div className="pq-content">
      {activeTab==='batches'    &&<BatchesTab    onSelectBatch={handleSelect}/>}
      {activeTab==='items'      &&<ItemsTab      selectedBatch={selectedBatch} onClearBatch={()=>setSelectedBatch(null)}/>}
      {activeTab==='logs'       &&<LogsTab/>}
      {activeTab==='priorities' &&<PrioritiesTab/>}
    </div>
  </div>;
}
