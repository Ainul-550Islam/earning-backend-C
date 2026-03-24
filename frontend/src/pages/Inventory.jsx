// src/pages/Inventory.jsx  — Full Inventory Admin Page
// Tabs: Items | User Inventory | Redemption Codes
// Features: CRUD items, restock, adjust stock, award, bulk codes, void, revoke

import { useState } from 'react';
import * as Icon from 'react-feather';
import { useItems, useUserInventory, useCodes } from '../hooks/useInventory';
import '../styles/Inventory.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ── Constants ──────────────────────────────────────────────────────
const ITEM_TYPES   = ['digital','physical','voucher','experience','subscription','points','nft'];
const ITEM_STATUS  = ['draft','active','paused','out_of_stock','discontinued','archived'];
const INV_STATUS   = ['pending','delivered','claimed','expired','revoked','failed','refunded'];
const CODE_STATUS  = ['available','reserved','redeemed','expired','voided','failed'];
const DELIVERY     = ['email','sms','in_app','manual','api','physical_shipment'];
const UNLIMITED    = -1;

const TYPE_ICONS = { digital:'💾', physical:'📦', voucher:'🎟️', experience:'🎭', subscription:'🔄', points:'⭐', nft:'🖼️' };
const STATUS_COLORS = {
  active:'green', draft:'muted', paused:'gold', out_of_stock:'red', discontinued:'muted', archived:'muted',
  pending:'gold', delivered:'cyan', claimed:'green', expired:'muted', revoked:'red', failed:'red', refunded:'purple',
  available:'green', reserved:'gold', redeemed:'cyan', voided:'muted',
};

const fmtDate = d => d ? new Date(d).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
const errMsg  = e => {
  if (!e) return 'Unknown error';
  const d = e?.response?.data;
  if (!d) return e.message||'Error';
  if (typeof d==='string') return d;
  if (d.detail) return d.detail;
  if (d.error)  return d.error;
  return Object.entries(d).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ');
};

function stockLabel(s) {
  if (s===UNLIMITED) return {label:'Unlimited',cls:'inv-item-stock--inf'};
  if (s<=0)   return {label:'Out of Stock',cls:'inv-item-stock--oos'};
  if (s<=10)  return {label:`Low: ${s}`,cls:'inv-item-stock--low'};
  return {label:`${s} in stock`,cls:'inv-item-stock--ok'};
}

// ── Shared UI ──────────────────────────────────────────────────────
function Badge({value}){ const c=STATUS_COLORS[value]||'muted'; return <span className={`inv-badge inv-badge--${c}`}>{value?.replace(/_/g,' ')}</span>; }
function Stat({label,value,color='green'}){ return <div className={`inv-stat inv-stat--${color}`}><div className="inv-stat-value">{value}</div><div className="inv-stat-label">{label}</div></div>; }
function Skeleton(){ return <div className="inv-loading">{[1,2,3,4].map(i=><div key={i} className="inv-loading-row"/>)}</div>; }
function CardSkeleton(){ return <div className="inv-loading-cards">{[1,2,3,4,5,6].map(i=><div key={i} className="inv-loading-card"/>)}</div>; }
function Empty({icon,text,onAdd}){ return <div className="inv-empty"><div className="inv-empty-icon">{icon}</div><p className="inv-empty-txt">{text}</p>{onAdd&&<button className="inv-btn inv-btn--green" onClick={onAdd}>+ Create First</button>}</div>; }

function Modal({title,onClose,children,wide,lg}){
  return <div className="inv-modal-bg" onClick={e=>e.target===e.currentTarget&&onClose()}>
    <div className={`inv-modal${wide?' inv-modal--wide':''}${lg?' inv-modal--lg':''}`}>
      <div className="inv-modal-hdr">
        <h3 className="inv-modal-title">{title}</h3>
        <button className="inv-modal-close" onClick={onClose}><Icon.X size={18}/></button>
      </div>
      <div className="inv-modal-body">{children}</div>
    </div>
  </div>;
}

function Field({label,children}){ return <div className="inv-field"><label className="inv-field-lbl">{label}</label>{children}</div>; }

function KV({k,v}){ return <div className="inv-kv"><span className="inv-kv-k">{k}</span><span className="inv-kv-v">{v||'—'}</span></div>; }

// ══════════════════════════════════════════════════════════════════
// TAB 1 — Reward Items
// ══════════════════════════════════════════════════════════════════
function ItemsTab(){
  const { items, loading, error, createItem, updateItem, deleteItem,
          restockItem, adjustStock, getStockHistory,
          bulkImportCodes, generateCodes, awardItem } = useItems();

  const [modal,     setModal]   = useState(null); // null|'create'|'edit'|'restock'|'adjust'|'codes'|'generate'|'award'|'history'
  const [target,    setTarget]  = useState(null);
  const [form,      setForm]    = useState({});
  const [saving,    setSaving]  = useState(false);
  const [err,       setErr]     = useState('');
  const [history,   setHistory] = useState([]);
  const [filter,    setFilter]  = useState('');
  const [typeFilter,setType]    = useState('');
  const [viewMode,  setViewMode]= useState('grid'); // 'grid'|'table'

  const F = (k,v)=>setForm(f=>({...f,[k]:v}));

  const openCreate = ()=>{setForm({name:'',item_type:'digital',status:'draft',points_cost:0,cash_value:'0.00',max_per_user:1,delivery_method:'email',current_stock:0,is_featured:false,is_transferable:false,requires_shipping_address:false,tags:[],description:''});setModal('create');setErr('');};
  const openEdit   = t=>{setTarget(t);setForm({...t,tags:t.tags||[]});setModal('edit');setErr('');};
  const openRestock= t=>{setTarget(t);setForm({qty:1,note:''});setModal('restock');setErr('');};
  const openAdjust = t=>{setTarget(t);setForm({qty:0,reason:''});setModal('adjust');setErr('');};
  const openCodes  = t=>{setTarget(t);setForm({codes_text:''});setModal('codes');setErr('');};
  // ✅ FIXED BUG 6: was {count:10, prefix:''} — GenerateCodesSerializer has no prefix field
  // GenerateCodesSerializer fields: count, batch_id, expires_at
  const openGen    = t=>{setTarget(t);setForm({count:10,batch_id:'',expires_at:''});setModal('generate');setErr('');};
  const openAward  = t=>{setTarget(t);setForm({user_id:'',qty:1,note:''});setModal('award');setErr('');};
  const openHistory= async t=>{
    setTarget(t); setModal('history'); setHistory([]);
    try{ const h=await getStockHistory(t.slug); setHistory(h); }
    catch(e){ setHistory([]); }
  };

  const run = async(fn)=>{ setSaving(true); setErr(''); try{ await fn(); setModal(null); }catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }};

  const handleSave = ()=> run(async()=>{
    if(!form.name?.trim()) throw new Error('Name required');
    if(modal==='create') await createItem(form);
    else await updateItem(target.slug, form);
  });
  const handleRestock  = ()=>run(()=>restockItem(target.slug, Number(form.qty), form.note));
  const handleAdjust   = ()=>run(()=>adjustStock(target.slug, Number(form.delta), form.note));
  const handleCodes    = ()=>run(async()=>{
    const codes = form.codes_text.split('\n').map(c=>c.trim()).filter(Boolean);
    if(!codes.length) throw new Error('Enter at least one code');
    await bulkImportCodes(target.slug, codes);
  });
  // ✅ FIXED BUG 6: added batch_id to generateCodes call
  const handleGenerate = ()=>run(()=>generateCodes(target.slug, Number(form.count), { batch_id: form.batch_id||undefined, expires_at: form.expires_at||undefined }));
  const handleAward    = ()=>run(async()=>{
    if(!form.user_id) throw new Error('User ID required');
    // ✅ FIXED BUG 1: removed target.id — viewset injects item_id from slug
    await awardItem(target.slug, form.user_id, { delivery_method: form.delivery_method||'email', expires_at: form.expires_at||undefined });
  });
  const handleDelete   = async t=>{ if(!confirm(`Delete "${t.name}"? This cannot be undone.`)) return; try{ await deleteItem(t.slug); }catch(e){ alert(errMsg(e)); }};

  const displayed = items.filter(i=>{
    if(filter   && i.status    !==filter)    return false;
    if(typeFilter && i.item_type!==typeFilter) return false;
    return true;
  });

  const active   = items.filter(i=>i.status==='active').length;
  const oos      = items.filter(i=>i.current_stock===0&&i.current_stock!==UNLIMITED).length;
  const featured = items.filter(i=>i.is_featured).length;

  return <div className="inv-tab-content">
    <div className="inv-stats-row">
      <Stat label="Total Items"   value={items.length}         color="green"/>
      <Stat label="Active"        value={active}               color="cyan"/>
      <Stat label="Out of Stock"  value={oos}                  color="red"/>
      <Stat label="Featured"      value={featured}             color="gold"/>
    </div>

    <div className="inv-tab-header">
      <div><h2 className="inv-tab-title">Reward Items</h2><p className="inv-tab-sub">Manage redeemable rewards — digital, physical, vouchers and more</p></div>
      <div className="inv-header-acts">
        <select className="inv-select inv-input--sm" value={filter} onChange={e=>setFilter(e.target.value)} style={{width:'auto'}}>
          <option value="">All Status</option>{ITEM_STATUS.map(s=><option key={s}>{s}</option>)}
        </select>
        <select className="inv-select inv-input--sm" value={typeFilter} onChange={e=>setType(e.target.value)} style={{width:'auto'}}>
          <option value="">All Types</option>{ITEM_TYPES.map(t=><option key={t}>{t}</option>)}
        </select>
        <button className="inv-icon-btn" title="Grid" onClick={()=>setViewMode('grid')}><Icon.Grid size={14}/></button>
        <button className="inv-icon-btn" title="Table" onClick={()=>setViewMode('table')}><Icon.List size={14}/></button>
        <button className="inv-btn inv-btn--green" onClick={openCreate}><Icon.Plus size={14}/> New Item</button>
      </div>
    </div>

    {error&&<div className="inv-error">{error}</div>}
    {loading ? (viewMode==='grid'?<CardSkeleton/>:<Skeleton/>) : displayed.length===0
      ? <Empty icon="🎁" text="No items found" onAdd={openCreate}/>
      : viewMode==='grid'
        ? <div className="inv-items-grid">{displayed.map(item=>{
            const stk=stockLabel(item.current_stock);
            return <div key={item.id} className={`inv-item-card${item.current_stock===0&&item.current_stock!==UNLIMITED?' inv-item-card--oos':''}${item.status==='draft'?' inv-item-card--draft':''}`}>
              {item.thumbnail_url||item.image_url
                ? <img className="inv-item-thumb" src={item.thumbnail_url||item.image_url} alt={item.name} onError={e=>e.target.style.display='none'}/>
                : <div className="inv-item-thumb-placeholder">{TYPE_ICONS[item.item_type]||'🎁'}</div>
              }
              <div className="inv-item-body">
                <div className="inv-item-top">
                  <div><div className="inv-item-name">{item.name}</div><div className="inv-item-slug">{item.slug}</div></div>
                  <Badge value={item.status}/>
                </div>
                <div className="inv-item-meta">
                  <Badge value={item.item_type}/>
                  {item.is_featured&&<span className="inv-badge inv-badge--gold">⭐ Featured</span>}
                  {item.uses_codes&&<span className="inv-badge inv-badge--purple">🔑 Codes</span>}
                </div>
                <div className={`inv-item-stock ${stk.cls}`}>{stk.label}</div>
                {item.current_stock!==UNLIMITED&&item.current_stock>0&&(
                  <div className="inv-stock-bar-wrap">
                    <div className={`inv-stock-bar ${stk.cls.replace('stock','stock-bar')}`} style={{width:`${Math.min(100,(item.current_stock/100)*100)}%`}}/>
                  </div>
                )}
                {item.points_cost>0&&<div className="inv-item-cost">⭐ {item.points_cost} pts</div>}
                <div className="inv-item-acts">
                  <button className="inv-icon-btn inv-icon-btn--green"  title="Restock"        onClick={()=>openRestock(item)}><Icon.PlusCircle size={12}/> Restock</button>
                  <button className="inv-icon-btn inv-icon-btn--gold"   title="Adjust Stock"   onClick={()=>openAdjust(item)}><Icon.Sliders size={12}/></button>
                  {item.uses_codes&&<>
                    <button className="inv-icon-btn inv-icon-btn--purple" title="Import Codes"  onClick={()=>openCodes(item)}><Icon.Upload size={12}/></button>
                    <button className="inv-icon-btn inv-icon-btn--purple" title="Generate Codes" onClick={()=>openGen(item)}><Icon.Zap size={12}/></button>
                  </>}
                  <button className="inv-icon-btn inv-icon-btn--cyan"   title="Award to User"  onClick={()=>openAward(item)}><Icon.Gift size={12}/></button>
                  <button className="inv-icon-btn"                       title="Stock History"  onClick={()=>openHistory(item)}><Icon.Clock size={12}/></button>
                  <button className="inv-icon-btn"                       title="Edit"           onClick={()=>openEdit(item)}><Icon.Edit2 size={12}/></button>
                  <button className="inv-icon-btn inv-icon-btn--red"    title="Delete"         onClick={()=>handleDelete(item)}><Icon.Trash2 size={12}/></button>
                </div>
              </div>
            </div>;
          })}</div>
        : <div className="inv-table-wrap"><table className="inv-table">
            <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Stock</th><th>Points</th><th>Value</th><th>Redeemed</th><th>Actions</th></tr></thead>
            <tbody>{displayed.map(item=>{
              const stk=stockLabel(item.current_stock);
              return <tr key={item.id}>
                <td><div style={{fontWeight:600}}>{item.name}</div><div className="inv-td-muted">{item.slug}</div></td>
                <td><Badge value={item.item_type}/></td>
                <td><Badge value={item.status}/></td>
                <td><span className={`inv-item-stock ${stk.cls}`} style={{fontSize:'.8rem'}}>{stk.label}</span></td>
                <td className="inv-td-muted">{item.points_cost||'free'}</td>
                <td className="inv-td-amt">{item.cash_value>0?`৳${item.cash_value}`:'—'}</td>
                <td className="inv-td-muted">{item.total_redeemed}</td>
                <td><div className="inv-actions">
                  <button className="inv-icon-btn inv-icon-btn--green" onClick={()=>openRestock(item)} title="Restock"><Icon.PlusCircle size={13}/></button>
                  <button className="inv-icon-btn inv-icon-btn--gold"  onClick={()=>openAdjust(item)}  title="Adjust"><Icon.Sliders size={13}/></button>
                  {item.uses_codes&&<button className="inv-icon-btn inv-icon-btn--purple" onClick={()=>openCodes(item)} title="Codes"><Icon.Key size={13}/></button>}
                  <button className="inv-icon-btn inv-icon-btn--cyan" onClick={()=>openAward(item)} title="Award"><Icon.Gift size={13}/></button>
                  <button className="inv-icon-btn" onClick={()=>openEdit(item)} title="Edit"><Icon.Edit2 size={13}/></button>
                  <button className="inv-icon-btn inv-icon-btn--red" onClick={()=>handleDelete(item)} title="Delete"><Icon.Trash2 size={13}/></button>
                </div></td>
              </tr>;
            })}</tbody>
          </table></div>
    }

    {/* ── Create / Edit Modal ── */}
    {(modal==='create'||modal==='edit')&&<Modal title={modal==='create'?'New Reward Item':`Edit — ${target?.name}`} onClose={()=>setModal(null)} wide>
      <div className="inv-form">
        <div className="inv-form-row">
          <Field label="Name *"><input className="inv-input" placeholder="e.g. Amazon Gift Card" value={form.name||''} onChange={e=>F('name',e.target.value)}/></Field>
          <Field label="Slug"><input className="inv-input" placeholder="auto-generated if blank" value={form.slug||''} onChange={e=>F('slug',e.target.value)}/></Field>
        </div>
        <div className="inv-form-row">
          <Field label="Type"><select className="inv-select" value={form.item_type||'digital'} onChange={e=>F('item_type',e.target.value)}>{ITEM_TYPES.map(t=><option key={t}>{t}</option>)}</select></Field>
          <Field label="Status"><select className="inv-select" value={form.status||'draft'} onChange={e=>F('status',e.target.value)}>{ITEM_STATUS.map(s=><option key={s}>{s}</option>)}</select></Field>
          <Field label="Delivery"><select className="inv-select" value={form.delivery_method||'email'} onChange={e=>F('delivery_method',e.target.value)}>{DELIVERY.map(d=><option key={d}>{d}</option>)}</select></Field>
        </div>
        <div className="inv-form-row">
          <Field label="Points Cost"><input className="inv-input" type="number" min="0" value={form.points_cost??0} onChange={e=>F('points_cost',Number(e.target.value))}/></Field>
          <Field label="Cash Value (BDT)"><input className="inv-input" type="number" min="0" step="0.01" value={form.cash_value??'0.00'} onChange={e=>F('cash_value',e.target.value)}/></Field>
          <Field label="Stock (-1=unlimited)"><input className="inv-input" type="number" min="-1" value={form.current_stock??0} onChange={e=>F('current_stock',Number(e.target.value))}/></Field>
        </div>
        <div className="inv-form-row">
          <Field label="Max Per User"><input className="inv-input" type="number" min="1" value={form.max_per_user??1} onChange={e=>F('max_per_user',Number(e.target.value))}/></Field>
          <Field label="Sort Order"><input className="inv-input" type="number" min="0" value={form.sort_order??0} onChange={e=>F('sort_order',Number(e.target.value))}/></Field>
        </div>
        <Field label="Description"><textarea className="inv-textarea" rows={3} value={form.description||''} onChange={e=>F('description',e.target.value)}/></Field>
        <Field label="Image URL"><input className="inv-input" placeholder="https://..." value={form.image_url||''} onChange={e=>F('image_url',e.target.value)}/></Field>
        <Field label="Delivery Callback URL (for API method)"><input className="inv-input" placeholder="https://..." value={form.delivery_callback_url||''} onChange={e=>F('delivery_callback_url',e.target.value)}/></Field>
        <div style={{display:'flex',gap:'1.5rem',flexWrap:'wrap'}}>
          <label className="inv-checkbox-row"><input type="checkbox" checked={!!form.is_featured} onChange={e=>F('is_featured',e.target.checked)}/> Featured</label>
          <label className="inv-checkbox-row"><input type="checkbox" checked={!!form.is_transferable} onChange={e=>F('is_transferable',e.target.checked)}/> Transferable</label>
          <label className="inv-checkbox-row"><input type="checkbox" checked={!!form.requires_shipping_address} onChange={e=>F('requires_shipping_address',e.target.checked)}/> Requires Shipping</label>
        </div>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--green" onClick={handleSave} disabled={saving}>{saving?'Saving…':modal==='create'?'Create Item':'Update Item'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Restock Modal ── */}
    {modal==='restock'&&target&&<Modal title={`Restock — ${target.name}`} onClose={()=>setModal(null)}>
      <div className="inv-form">
        <div className="inv-detail-section">
          <div className="inv-kv-grid">
            <KV k="Current Stock" v={target.current_stock===UNLIMITED?'Unlimited':target.current_stock}/>
            <KV k="Total Redeemed" v={target.total_redeemed}/>
          </div>
        </div>
        <Field label="Quantity to Add *"><input className="inv-input" type="number" min="1" value={form.qty||1} onChange={e=>F('qty',e.target.value)}/></Field>
        <Field label="Note"><input className="inv-input" placeholder="e.g. Supplier delivery" value={form.note||''} onChange={e=>F('note',e.target.value)}/></Field>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--green" onClick={handleRestock} disabled={saving}>{saving?'Restocking…':'Restock'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Adjust Stock Modal ── */}
    {modal==='adjust'&&target&&<Modal title={`Adjust Stock — ${target.name}`} onClose={()=>setModal(null)}>
      <div className="inv-form">
        <div className="inv-detail-section">
          <div className="inv-kv-grid"><KV k="Current Stock" v={target.current_stock===UNLIMITED?'Unlimited':target.current_stock}/></div>
        </div>
        <Field label="Delta (+ to add, - to remove) *"><input className="inv-input" type="number" placeholder="-5 or +10" value={form.delta||''} onChange={e=>F('delta',e.target.value)}/></Field>
        <Field label="Note"><input className="inv-input" placeholder="e.g. Damaged goods, audit correction" value={form.note||''} onChange={e=>F('note',e.target.value)}/></Field>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--gold" onClick={handleAdjust} disabled={saving}>{saving?'Adjusting…':'Apply Adjustment'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Bulk Import Codes Modal ── */}
    {modal==='codes'&&target&&<Modal title={`Import Codes — ${target.name}`} onClose={()=>setModal(null)}>
      <div className="inv-form">
        <p style={{fontSize:'.82rem',color:'var(--inv-muted)',margin:'0 0 8px'}}>Paste one code per line. Duplicates are skipped.</p>
        <Field label="Codes (one per line)">
          <textarea className="inv-textarea inv-codes-area" rows={10} placeholder={"CODE-001\nCODE-002\nCODE-003"} value={form.codes_text||''} onChange={e=>F('codes_text',e.target.value)}/>
        </Field>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--purple" onClick={handleCodes} disabled={saving}>{saving?'Importing…':'Import Codes'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Generate Codes Modal ── */}
    {modal==='generate'&&target&&<Modal title={`Generate Codes — ${target.name}`} onClose={()=>setModal(null)}>
      <div className="inv-form">
        {/* ✅ FIXED BUG 6: added batch_id field, removed prefix (not in GenerateCodesSerializer) */}
        <div className="inv-form-row">
          <Field label="Count * (max 10,000)"><input className="inv-input" type="number" min="1" max="10000" value={form.count||10} onChange={e=>F('count',e.target.value)}/></Field>
          <Field label="Batch ID (optional)"><input className="inv-input" placeholder="e.g. batch-2024-q1" value={form.batch_id||''} onChange={e=>F('batch_id',e.target.value)}/></Field>
        </div>
        <Field label="Expires At (optional)"><input className="inv-input" type="datetime-local" value={form.expires_at||''} onChange={e=>F('expires_at',e.target.value)}/></Field>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--purple" onClick={handleGenerate} disabled={saving}>{saving?'Generating…':'Generate'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Award Modal ── */}
    {modal==='award'&&target&&<Modal title={`Award to User — ${target.name}`} onClose={()=>setModal(null)}>
      <div className="inv-form">
        <div className="inv-detail-section">
          <div className="inv-kv-grid">
            <KV k="Item" v={target.name}/>
            <KV k="Item ID" v={target.id?.toString().slice(0,8)+'…'}/>
            <KV k="Stock" v={target.current_stock===UNLIMITED?'Unlimited':target.current_stock}/>
          </div>
        </div>
        <Field label="User ID *"><input className="inv-input" placeholder="User UUID or integer ID" value={form.user_id||''} onChange={e=>F('user_id',e.target.value)}/></Field>
        <div className="inv-form-row">
          <Field label="Delivery Method">
            <select className="inv-select" value={form.delivery_method||'email'} onChange={e=>F('delivery_method',e.target.value)}>
              {DELIVERY.map(d=><option key={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="Expires At (optional)"><input className="inv-input" type="datetime-local" value={form.expires_at||''} onChange={e=>F('expires_at',e.target.value)}/></Field>
        </div>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--cyan" onClick={handleAward} disabled={saving}>{saving?'Awarding…':'Award Item'}</button>
        </div>
      </div>
    </Modal>}

    {/* ── Stock History Modal ── */}
    {modal==='history'&&target&&<Modal title={`Stock History — ${target.name}`} onClose={()=>setModal(null)} wide>
      {history.length===0
        ? <p style={{color:'var(--inv-muted)',textAlign:'center',padding:'2rem'}}>No stock events yet</p>
        : <div className="inv-table-wrap"><table className="inv-table">
            <thead><tr><th>Event</th><th>Qty</th><th>Before</th><th>After</th><th>Note</th><th>By</th><th>Time</th></tr></thead>
            <tbody>{history.map(e=><tr key={e.id}>
              <td><Badge value={e.event_type||e.type||'—'}/></td>
              {/* ✅ FIXED BUG 2: quantity_delta (not quantity) */}
              <td style={{color:Number(e.quantity_delta)>0?'var(--inv-green)':'var(--inv-red)',fontWeight:700}}>{Number(e.quantity_delta)>0?'+':''}{e.quantity_delta}</td>
              <td className="inv-td-muted">{e.stock_before??'—'}</td>
              <td className="inv-td-muted">{e.stock_after??'—'}</td>
              <td className="inv-td-muted">{e.note||e.reason||'—'}</td>
              {/* ✅ FIXED BUG 2: performed_by_username (not created_by) */}
              <td className="inv-td-muted">{e.performed_by_username||'system'}</td>
              <td className="inv-td-muted">{fmtDate(e.created_at)}</td>
            </tr>)}</tbody>
          </table></div>
      }
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 2 — User Inventory
// ══════════════════════════════════════════════════════════════════
function UserInventoryTab(){
  const [statusFilter, setStatusFilter] = useState('');
  const { entries, loading, error, claimEntry, revokeEntry } = useUserInventory(
    statusFilter ? { status: statusFilter } : {}
  );

  const [revokeModal, setRevokeModal] = useState(null);
  const [revokeReason,setRevokeReason]= useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const pending   = entries.filter(e=>e.status==='pending').length;
  const delivered = entries.filter(e=>e.status==='delivered').length;
  const revoked   = entries.filter(e=>e.status==='revoked').length;

  const handleClaim  = async id=>{ try{ await claimEntry(id); }catch(e){ alert(errMsg(e)); }};
  const handleRevoke = async ()=>{
    setSaving(true); setErr('');
    try{ await revokeEntry(revokeModal.id, revokeReason); setRevokeModal(null); }
    catch(e){ setErr(errMsg(e)); } finally{ setSaving(false); }
  };

  return <div className="inv-tab-content">
    <div className="inv-stats-row">
      <Stat label="Total"     value={entries.length} color="green"/>
      <Stat label="Pending"   value={pending}        color="gold"/>
      <Stat label="Delivered" value={delivered}      color="cyan"/>
      <Stat label="Revoked"   value={revoked}        color="red"/>
    </div>
    <div className="inv-tab-header">
      <div><h2 className="inv-tab-title">User Inventory</h2><p className="inv-tab-sub">Track user rewards — claim, revoke and monitor delivery status</p></div>
      <select className="inv-select" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} style={{width:'auto'}}>
        <option value="">All Status</option>{INV_STATUS.map(s=><option key={s}>{s}</option>)}
      </select>
    </div>
    {error&&<div className="inv-error">{error}</div>}
    {loading?<Skeleton/>:entries.length===0
      ?<Empty icon="🎒" text="No inventory entries found"/>
      :<div className="inv-table-wrap"><table className="inv-table">
        <thead><tr><th>User</th><th>Item</th><th>Status</th><th>Delivery</th><th>Code</th><th>Expires</th><th>Awarded</th><th>Actions</th></tr></thead>
        <tbody>{entries.map(e=><tr key={e.id}>
          <td className="inv-td-user">{e.user?.username||e.user}</td>
          <td><div style={{fontWeight:600}}>{e.item?.name||e.item}</div></td>
          <td><Badge value={e.status}/></td>
          <td className="inv-td-muted">{e.delivery_method||'—'}</td>
          {/* ✅ FIXED BUG 3: code_value (not code) — UserInventorySerializer.get_code_value */}
          <td>{e.code_value?<code className="inv-td-code">{e.code_value}</code>:'—'}</td>
          <td className="inv-td-muted">{fmtDate(e.expires_at)}</td>
          <td className="inv-td-muted">{fmtDate(e.created_at)}</td>
          <td><div className="inv-actions">
            {/* ✅ FIXED BUG 4: is_claimable=true for 'delivered' (not 'pending') — model.is_claimable */}
            {e.is_claimable&&<button className="inv-icon-btn inv-icon-btn--green" title="Mark Claimed" onClick={()=>handleClaim(e.id)}><Icon.CheckCircle size={13}/> Claim</button>}
            {!['revoked','refunded','expired'].includes(e.status)&&<button className="inv-icon-btn inv-icon-btn--red" title="Revoke" onClick={()=>{setRevokeModal(e);setRevokeReason('');setErr('');}}><Icon.XCircle size={13}/> Revoke</button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>
    }
    {revokeModal&&<Modal title={`Revoke — ${revokeModal.item?.name||'Item'}`} onClose={()=>setRevokeModal(null)}>
      <div className="inv-form">
        <p style={{fontSize:'.82rem',color:'var(--inv-muted)',margin:'0 0 10px'}}>User: <strong>{revokeModal.user?.username||revokeModal.user}</strong></p>
        <Field label="Reason *"><input className="inv-input" placeholder="e.g. Fraudulent redemption" value={revokeReason} onChange={e=>setRevokeReason(e.target.value)}/></Field>
        {err&&<div className="inv-form-error">{err}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setRevokeModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--danger" onClick={handleRevoke} disabled={saving}>{saving?'Revoking…':'Revoke'}</button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// TAB 3 — Redemption Codes
// ══════════════════════════════════════════════════════════════════
function CodesTab(){
  const [statusFilter, setStatusFilter] = useState('');
  const [batchFilter,  setBatchFilter]  = useState('');
  const { codes, loading, error, voidCode } = useCodes(
    Object.fromEntries(Object.entries({ status: statusFilter, batch_id: batchFilter }).filter(([,v])=>v))
  );

  const [voidModal,  setVoidModal]  = useState(null);
  const [voidReason, setVoidReason] = useState('');
  const [voidSaving, setVoidSaving] = useState(false);
  const [voidErr,    setVoidErr]    = useState('');

  const available = codes.filter(c=>c.status==='available').length;
  const redeemed  = codes.filter(c=>c.status==='redeemed').length;
  const voided    = codes.filter(c=>c.status==='voided').length;
  const expired   = codes.filter(c=>c.status==='expired').length;

  const handleVoid = async ()=>{
    setVoidSaving(true); setVoidErr('');
    try{
      await voidCode(voidModal.id, voidReason||'Voided by admin.');
      setVoidModal(null);
    }catch(e){ setVoidErr(errMsg(e)); } finally{ setVoidSaving(false); }
  };

  return <div className="inv-tab-content">
    <div className="inv-stats-row">
      <Stat label="Total"     value={codes.length} color="green"/>
      <Stat label="Available" value={available}    color="cyan"/>
      <Stat label="Redeemed"  value={redeemed}     color="gold"/>
      <Stat label="Voided"    value={voided}        color="red"/>
      <Stat label="Expired"   value={expired}       color="purple"/>
    </div>
    <div className="inv-tab-header">
      <div><h2 className="inv-tab-title">Redemption Codes</h2><p className="inv-tab-sub">View, filter and void digital codes — filter by status or batch ID</p></div>
      <div className="inv-header-acts">
        <select className="inv-select inv-input--sm" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} style={{width:'auto'}}>
          <option value="">All Status</option>{CODE_STATUS.map(s=><option key={s}>{s}</option>)}
        </select>
        <input className="inv-input inv-input--sm" placeholder="Filter by Batch ID" value={batchFilter} onChange={e=>setBatchFilter(e.target.value)} style={{width:'160px'}}/>
      </div>
    </div>
    {error&&<div className="inv-error">{error}</div>}
    {loading?<Skeleton/>:codes.length===0
      ?<Empty icon="🔑" text="No redemption codes found"/>
      :<div className="inv-table-wrap"><table className="inv-table">
        <thead><tr><th>Code</th><th>Item</th><th>Batch ID</th><th>Status</th><th>Reserved By</th><th>Redeemed By</th><th>Redeemed At</th><th>Expires</th><th>Actions</th></tr></thead>
        <tbody>{codes.map(c=><tr key={c.id}>
          <td><code className={`inv-td-code${c.status==='voided'?' inv-code-void':''}`}>{c.code}</code></td>
          <td className="inv-td-muted">{c.item?.name||c.item||'—'}</td>
          <td className="inv-td-muted">{c.batch_id||'—'}</td>
          <td><Badge value={c.status}/></td>
          <td className="inv-td-muted">{c.reserved_by?.username||c.reserved_by||'—'}</td>
          <td className="inv-td-muted">{c.redeemed_by?.username||c.redeemed_by||'—'}</td>
          <td className="inv-td-muted">{fmtDate(c.redeemed_at)}</td>
          <td className="inv-td-muted">{fmtDate(c.expires_at)}</td>
          <td>
            {c.status==='available'&&(
              <button className="inv-icon-btn inv-icon-btn--red" title="Void"
                onClick={()=>{ setVoidModal(c); setVoidReason(''); setVoidErr(''); }}>
                <Icon.XCircle size={13}/> Void
              </button>
            )}
          </td>
        </tr>)}</tbody>
      </table></div>
    }

    {/* Void Modal with reason */}
    {voidModal&&<Modal title="Void Redemption Code" onClose={()=>setVoidModal(null)}>
      <div className="inv-form">
        <div className="inv-detail-section">
          <div className="inv-kv-grid">
            <KV k="Code"  v={voidModal.code}/>
            <KV k="Item"  v={voidModal.item?.name||voidModal.item||'—'}/>
            <KV k="Status" v={voidModal.status}/>
          </div>
        </div>
        <p style={{fontSize:'.82rem',color:'var(--inv-red)',margin:'0 0 8px'}}>
          ⚠️ Voided codes cannot be reactivated.
        </p>
        <Field label="Reason (optional)">
          <input className="inv-input" placeholder="e.g. Duplicate, fraud prevention"
            value={voidReason} onChange={e=>setVoidReason(e.target.value)}/>
        </Field>
        {voidErr&&<div className="inv-form-error">{voidErr}</div>}
        <div className="inv-form-actions">
          <button className="inv-btn inv-btn--ghost" onClick={()=>setVoidModal(null)}>Cancel</button>
          <button className="inv-btn inv-btn--danger" onClick={handleVoid} disabled={voidSaving}>
            {voidSaving?'Voiding…':'Void Code'}
          </button>
        </div>
      </div>
    </Modal>}
  </div>;
}

// ══════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════
const TABS = [
  { id:'items',     label:'Reward Items',    icon:<Icon.Gift size={15}/> },
  { id:'inventory', label:'User Inventory',  icon:<Icon.Archive size={15}/> },
  { id:'codes',     label:'Redemption Codes',icon:<Icon.Key size={15}/> },
];

export default function Inventory(){
  const [activeTab, setActiveTab] = useState('items');
  return <div className="inv-root">
    <div className="inv-page-header">
      <div className="inv-page-header-inner">
        <div className="inv-page-title-wrap">
          <span className="inv-page-icon">🎁</span>
          <div>
            <h1 className="inv-page-title">INVENTORY</h1>
            <p className="inv-page-sub">Manage reward items, user inventory and redemption codes</p>
          </div>
        </div>
      </div>
      <div className="inv-tabs">
        {TABS.map(t=><button key={t.id} className={`inv-tab${activeTab===t.id?' inv-tab--active':''}`} onClick={()=>setActiveTab(t.id)}>
          {t.icon} {t.label}
        </button>)}
      </div>
    </div>
    <div className="inv-content">
      {activeTab==='items'     && <ItemsTab/>}
      {activeTab==='inventory' && <UserInventoryTab/>}
      {activeTab==='codes'     && <CodesTab/>}
    </div>
  </div>;
}