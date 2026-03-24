// src/pages/Offerwall.jsx — All-in-One: Providers + Offers + Categories + Conversions
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LayoutGrid, Plus, RefreshCw, Search, Trash2, Edit3,
  ToggleLeft, ToggleRight, Settings, ExternalLink,
  TrendingUp, CheckCircle, Clock, Zap, Activity,
  BarChart2, Users, DollarSign, Loader2, Save,
  Database, Globe, Shield, Star, Tag, List,
  ChevronDown, ChevronUp, Filter, Eye, AlertCircle,
  Package, Award, Layers, RotateCcw, X
} from 'lucide-react';
import client from '../api/client';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── Design Tokens ────────────────────────────────────────────────
const C = {
  bg:       '#020912',
  bg2:      '#050e1a',
  bg3:      '#071526',
  panel:    '#0a1c2e',
  border:   'rgba(0,180,255,0.12)',
  border2:  'rgba(0,180,255,0.22)',
  text:     '#c8dff0',
  textDim:  '#4a7a9b',
  cyan:     '#00c8ff',
  green:    '#00e87a',
  amber:    '#ffc300',
  red:      '#ff3d71',
  purple:   '#a855f7',
  pink:     '#ec4899',
};

const TAB_DEFS = [
  { key: 'providers',   label: 'Providers',   icon: Database },
  { key: 'offers',      label: 'Offers',      icon: Package },
  { key: 'categories',  label: 'Categories',  icon: Tag },
  { key: 'conversions', label: 'Conversions', icon: Award },
];

const PROVIDER_TYPES = [
  { value: 'tapjoy',    label: 'Tapjoy' },
  { value: 'adgem',     label: 'AdGem' },
  { value: 'adgate',    label: 'AdGate Media' },
  { value: 'offerwall', label: 'OfferToro' },
  { value: 'persona',   label: 'Persona.ly' },
  { value: 'cpx',       label: 'CPX Research' },
  { value: 'bitlabs',   label: 'BitLabs' },
  { value: 'pollfish',  label: 'Pollfish' },
  { value: 'custom',    label: 'Custom Provider' },
];

const OFFER_TYPES = [
  { value: 'app_install', label: 'App Install' },
  { value: 'signup',      label: 'Sign Up' },
  { value: 'survey',      label: 'Survey' },
  { value: 'video',       label: 'Watch Video' },
  { value: 'game',        label: 'Play Game' },
  { value: 'trial',       label: 'Free Trial' },
  { value: 'purchase',    label: 'Make Purchase' },
  { value: 'other',       label: 'Other' },
];

const PLATFORMS = [
  { value: 'all',     label: 'All Platforms' },
  { value: 'android', label: 'Android' },
  { value: 'ios',     label: 'iOS' },
  { value: 'web',     label: 'Web' },
  { value: 'mobile',  label: 'Mobile' },
  { value: 'desktop', label: 'Desktop' },
];

// ─── Utilities ────────────────────────────────────────────────────
function useToast() {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((msg, type = 'success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, msg, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500);
  }, []);
  return { toasts, push };
}

// ─── Components ───────────────────────────────────────────────────
const ToastContainer = ({ toasts }) => (
  <div style={{ position:'fixed', bottom:24, right:24, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
    {toasts.map(t => (
      <div key={t.id} style={{
        padding:'11px 18px', borderRadius:8, fontSize:12,
        fontFamily:"'Courier New', monospace", letterSpacing:0.5,
        background: t.type==='error'?`${C.red}18`:t.type==='warning'?`${C.amber}18`:`${C.green}18`,
        border:`1px solid ${t.type==='error'?C.red:t.type==='warning'?C.amber:C.green}44`,
        color: t.type==='error'?C.red:t.type==='warning'?C.amber:C.green,
        boxShadow:'0 8px 24px rgba(0,0,0,0.5)',
        display:'flex', alignItems:'center', gap:8,
      }}>
        {t.type==='error'?'✗':t.type==='warning'?'⚠':'✓'} {t.msg}
      </div>
    ))}
  </div>
);

const Spinner = ({ size=16 }) => (
  <Loader2 size={size} style={{ animation:'spin 1s linear infinite' }} />
);

const Skeleton = ({ h=14, w='100%', radius=6 }) => (
  <div style={{ height:h, width:w, borderRadius:radius, background:`linear-gradient(90deg,${C.bg3} 25%,${C.panel} 50%,${C.bg3} 75%)`, backgroundSize:'200% 100%', animation:'shimmer 1.6s infinite' }}/>
);

const Badge = ({ label, color=C.cyan }) => (
  <span style={{ fontSize:10, fontWeight:700, letterSpacing:1.2, color, background:`${color}18`, border:`1px solid ${color}40`, borderRadius:4, padding:'2px 8px' }}>
    {label}
  </span>
);

const Btn = ({ children, onClick, color=C.cyan, outline=false, sm=false, disabled=false, style={} }) => (
  <button onClick={onClick} disabled={disabled} style={{
    display:'inline-flex', alignItems:'center', gap:6,
    padding: sm ? '5px 12px' : '8px 16px',
    fontSize: sm ? 11 : 12, fontWeight:600, letterSpacing:0.8,
    borderRadius:7, cursor:disabled?'not-allowed':'pointer',
    background: outline ? 'transparent' : `${color}22`,
    border:`1px solid ${color}${outline?'60':'40'}`,
    color, opacity:disabled?0.5:1,
    transition:'all .15s',
    ...style
  }}>{children}</button>
);

const StatCard = ({ label, value, icon:Icon, color, loading }) => (
  <div style={{ flex:'1 1 140px', background:C.panel, border:`1px solid ${color}20`, borderRadius:10, padding:'14px 18px' }}>
    <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8 }}>
      <Icon size={14} color={color} />
      <span style={{ fontSize:10, color:C.textDim, letterSpacing:1, textTransform:'uppercase' }}>{label}</span>
    </div>
    {loading ? <Skeleton h={22} w={60}/> :
      <div style={{ fontSize:22, fontWeight:700, color, fontFamily:"'Courier New', monospace" }}>{value}</div>
    }
  </div>
);

// ─── Modal ────────────────────────────────────────────────────────
const Modal = ({ title, onClose, children, width=520 }) => (
  <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }} onClick={onClose}>
    <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,${C.bg2},${C.bg3})`, border:`1px solid ${C.border2}`, borderRadius:14, padding:28, width:'100%', maxWidth:width, maxHeight:'88vh', overflowY:'auto' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:22 }}>
        <span style={{ fontSize:14, fontWeight:700, color:C.cyan, letterSpacing:1.5 }}>{title}</span>
        <button onClick={onClose} style={{ background:'none', border:'none', color:C.red, cursor:'pointer', padding:4 }}><X size={18}/></button>
      </div>
      {children}
    </div>
  </div>
);

const Field = ({ label, children }) => (
  <div style={{ marginBottom:14 }}>
    <label style={{ display:'block', fontSize:10, color:C.textDim, letterSpacing:1, marginBottom:5, textTransform:'uppercase' }}>{label}</label>
    {children}
  </div>
);

const inputStyle = {
  width:'100%', background:`${C.bg}cc`, border:`1px solid ${C.border2}`,
  borderRadius:7, padding:'9px 12px', color:C.text, fontSize:12,
  outline:'none', boxSizing:'border-box',
};

const SelectInput = ({ value, onChange, options, placeholder='Select...' }) => (
  <select value={value||''} onChange={e=>onChange(e.target.value)} style={inputStyle}>
    <option value=''>{placeholder}</option>
    {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

const ConfirmModal = ({ msg, onConfirm, onClose, loading }) => (
  <Modal title="CONFIRM DELETE" onClose={onClose} width={380}>
    <div style={{ textAlign:'center' }}>
      <div style={{ fontSize:32, marginBottom:12 }}>⚠️</div>
      <div style={{ color:C.text, fontSize:13, marginBottom:24 }}>{msg}</div>
      <div style={{ display:'flex', gap:10 }}>
        <Btn onClick={onConfirm} color={C.red} disabled={loading} style={{ flex:1, justifyContent:'center' }}>
          {loading ? <Spinner/> : 'DELETE'}
        </Btn>
        <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
      </div>
    </div>
  </Modal>
);

// ─── PROVIDERS TAB ────────────────────────────────────────────────
function ProviderModal({ provider, onClose, onSaved, toast }) {
  const isEdit = !!provider;
  const [form, setForm] = useState({
    name: provider?.name || '',
    provider_type: provider?.provider_type || '',
    status: provider?.status || 'active',
    api_key: provider?.api_key || '',
    api_secret: provider?.api_secret || '',
    app_id: provider?.app_id || '',
    publisher_id: provider?.publisher_id || '',
    api_base_url: provider?.api_base_url || '',
    revenue_share: provider?.revenue_share || '70.00',
    notes: provider?.notes || '',
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const save = async () => {
    if (!form.name.trim() || !form.provider_type) return toast('Name and type required', 'error');
    setSaving(true);
    try {
      if (isEdit) {
        await client.patch(`/offers/providers/${provider.id}/`, form);
        toast('Provider updated!');
      } else {
        await client.post('/offers/providers/', form);
        toast('Provider created!');
      }
      onSaved();
    } catch(e) {
      toast(e?.response?.data?.detail || 'Failed to save', 'error');
    } finally { setSaving(false); }
  };

  return (
    <Modal title={isEdit ? '✏ EDIT PROVIDER' : '✦ NEW PROVIDER'} onClose={onClose}>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
        <Field label="Provider Name">
          <input style={inputStyle} value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. My Provider"/>
        </Field>
        <Field label="Type">
          <SelectInput value={form.provider_type} onChange={v=>set('provider_type',v)} options={PROVIDER_TYPES}/>
        </Field>
        <Field label="Status">
          <SelectInput value={form.status} onChange={v=>set('status',v)} options={[
            {value:'active',label:'Active'},{value:'inactive',label:'Inactive'},
            {value:'testing',label:'Testing'},{value:'suspended',label:'Suspended'},
          ]}/>
        </Field>
        <Field label="Revenue Share (%)">
          <input style={inputStyle} type="number" value={form.revenue_share} onChange={e=>set('revenue_share',e.target.value)}/>
        </Field>
        <Field label="API Key">
          <input style={inputStyle} value={form.api_key} onChange={e=>set('api_key',e.target.value)} placeholder="API Key"/>
        </Field>
        <Field label="API Secret">
          <input style={inputStyle} type="password" value={form.api_secret} onChange={e=>set('api_secret',e.target.value)} placeholder="API Secret"/>
        </Field>
        <Field label="App ID">
          <input style={inputStyle} value={form.app_id} onChange={e=>set('app_id',e.target.value)} placeholder="App ID"/>
        </Field>
        <Field label="Publisher ID">
          <input style={inputStyle} value={form.publisher_id} onChange={e=>set('publisher_id',e.target.value)} placeholder="Publisher ID"/>
        </Field>
      </div>
      <Field label="API Base URL">
        <input style={inputStyle} value={form.api_base_url} onChange={e=>set('api_base_url',e.target.value)} placeholder="https://api.provider.com"/>
      </Field>
      <Field label="Notes">
        <textarea style={{...inputStyle,resize:'vertical'}} rows={2} value={form.notes} onChange={e=>set('notes',e.target.value)}/>
      </Field>
      <div style={{ display:'flex', gap:10, marginTop:8 }}>
        <Btn onClick={save} disabled={saving} style={{ flex:1, justifyContent:'center' }}>
          {saving ? <Spinner/> : <><Save size={13}/> SAVE</>}
        </Btn>
        <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
      </div>
    </Modal>
  );
}

function ProvidersTab({ toast }) {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilter] = useState('all');
  const [modal, setModal] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [syncing, setSyncing] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, sRes] = await Promise.allSettled([
        client.get('/offers/providers/'),
        client.get('/offers/offers/stats/'),
      ]);
      if (pRes.status==='fulfilled') { const d=pRes.value.data; setProviders(d?.results??d??[]); }
      if (sRes.status==='fulfilled') setStats(sRes.value.data);
    } catch { toast('Failed to load','error'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleToggle = async (p) => {
    const next = p.status==='active'?'inactive':'active';
    setProviders(ps=>ps.map(x=>x.id===p.id?{...x,status:next}:x));
    try { await client.patch(`/offers/providers/${p.id}/`,{status:next}); toast(`${p.name} ${next}`); }
    catch { setProviders(ps=>ps.map(x=>x.id===p.id?{...x,status:p.status}:x)); toast('Failed','error'); }
  };

  const handleSync = async (id) => {
    setSyncing(id);
    try {
      const res = await client.post(`/offers/providers/${id}/sync/`);
      toast(`Synced — ${res.data?.synced??res.data?.created??0} offers`);
      fetchAll();
    } catch(e) {
      toast(e?.response?.data?.error||e?.response?.data?.detail||'Sync failed','error');
    } finally { setSyncing(null); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await client.delete(`/offers/providers/${deleteTarget.id}/`);
      setProviders(ps=>ps.filter(x=>x.id!==deleteTarget.id));
      toast(`"${deleteTarget.name}" deleted`);
      setDeleteTarget(null);
    } catch { toast('Delete failed','error'); }
    finally { setDeleting(false); }
  };

  const filtered = providers.filter(p => {
    const ms = p.name?.toLowerCase().includes(search.toLowerCase()) || p.provider_type?.toLowerCase().includes(search.toLowerCase());
    const mf = filterStatus==='all' || p.status===filterStatus;
    return ms && mf;
  });

  const activeCount = providers.filter(p=>p.status==='active').length;

  return (
    <div>
      {modal && <ProviderModal provider={modal==='create'?null:modal} onClose={()=>setModal(null)} onSaved={()=>{setModal(null);fetchAll();}} toast={toast}/>}
      {deleteTarget && <ConfirmModal msg={`Delete "${deleteTarget.name}"?`} onConfirm={handleDelete} onClose={()=>setDeleteTarget(null)} loading={deleting}/>}

      {/* Stats */}
      <div style={{ display:'flex', gap:10, flexWrap:'wrap', marginBottom:20 }}>
        <StatCard label="Total Providers" value={providers.length} icon={Database} color={C.cyan} loading={loading}/>
        <StatCard label="Active" value={activeCount} icon={CheckCircle} color={C.green} loading={loading}/>
        <StatCard label="Total Offers" value={stats?.total_offers??0} icon={Package} color={C.amber} loading={loading}/>
        <StatCard label="Conversions" value={stats?.total_conversions??0} icon={Award} color={C.purple} loading={loading}/>
        <StatCard label="Total Revenue" value={`$${Number(stats?.total_revenue||0).toFixed(2)}`} icon={DollarSign} color={C.pink} loading={loading}/>
      </div>

      {/* Toolbar */}
      <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:16, flexWrap:'wrap' }}>
        <div style={{ flex:1, minWidth:200, display:'flex', alignItems:'center', gap:8, background:C.panel, border:`1px solid ${C.border}`, borderRadius:8, padding:'8px 12px' }}>
          <Search size={13} color={C.textDim}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search providers..." style={{ background:'none', border:'none', color:C.text, fontSize:12, outline:'none', flex:1 }}/>
        </div>
        {['all','active','inactive','testing','suspended'].map(s=>(
          <button key={s} onClick={()=>setFilter(s)} style={{ padding:'7px 14px', borderRadius:7, fontSize:11, fontWeight:600, letterSpacing:0.8, cursor:'pointer', background:filterStatus===s?`${C.cyan}22`:'transparent', border:`1px solid ${filterStatus===s?C.cyan:C.border}`, color:filterStatus===s?C.cyan:C.textDim }}>
            {s.toUpperCase()}
          </button>
        ))}
        <Btn onClick={fetchAll} outline sm><RefreshCw size={13}/> Refresh</Btn>
        <Btn onClick={()=>setModal('create')} sm><Plus size={13}/> Add Provider</Btn>
      </div>

      {/* Provider Cards */}
      {loading ? (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(320px,1fr))', gap:14 }}>
          {[1,2,3].map(i=><div key={i} style={{ background:C.panel, borderRadius:12, padding:20 }}><Skeleton h={120}/></div>)}
        </div>
      ) : filtered.length===0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.textDim }}>No providers found</div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(320px,1fr))', gap:14 }}>
          {filtered.map(p=>{
            const isActive = p.status==='active';
            const accent = isActive?C.green:p.status==='suspended'?C.red:p.status==='testing'?C.amber:C.textDim;
            return (
              <div key={p.id} style={{ background:C.panel, border:`1px solid ${accent}20`, borderRadius:12, padding:18, borderTop:`2px solid ${accent}60`, transition:'border-color .2s' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:14 }}>
                  <div>
                    <div style={{ fontSize:14, fontWeight:700, color:C.text, marginBottom:3 }}>{p.name}</div>
                    <div style={{ fontSize:11, color:C.textDim }}>{p.provider_type_display||p.provider_type}</div>
                  </div>
                  <Badge label={p.status?.toUpperCase()} color={accent}/>
                </div>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8, marginBottom:14 }}>
                  {[
                    {label:'OFFERS', val:p.total_offers||0, c:C.amber},
                    {label:'CONVERSIONS', val:p.total_conversions||0, c:C.purple},
                    {label:'REV SHARE', val:`${p.revenue_share}%`, c:C.cyan},
                  ].map(s=>(
                    <div key={s.label} style={{ background:`${C.bg}88`, borderRadius:7, padding:'8px 10px', textAlign:'center' }}>
                      <div style={{ fontSize:9, color:C.textDim, letterSpacing:1, marginBottom:3 }}>{s.label}</div>
                      <div style={{ fontSize:15, fontWeight:700, color:s.c, fontFamily:"'Courier New',monospace" }}>{s.val}</div>
                    </div>
                  ))}
                </div>
                <div style={{ display:'flex', gap:6, padding:'10px 0 0', borderTop:`1px solid ${C.border}` }}>
                  <Btn onClick={()=>handleToggle(p)} color={isActive?C.red:C.green} sm>
                    {isActive?<ToggleRight size={13}/>:<ToggleLeft size={13}/>}
                    {isActive?'Disable':'Enable'}
                  </Btn>
                  <Btn onClick={()=>handleSync(p.id)} color={C.amber} sm disabled={syncing===p.id}>
                    {syncing===p.id?<Spinner size={12}/>:<RotateCcw size={12}/>} Sync
                  </Btn>
                  <Btn onClick={()=>setModal(p)} color={C.cyan} sm><Edit3 size={12}/> Edit</Btn>
                  <Btn onClick={()=>setDeleteTarget(p)} color={C.red} outline sm><Trash2 size={12}/></Btn>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── OFFERS TAB ───────────────────────────────────────────────────
function OfferModal({ offer, providers, categories, onClose, onSaved, toast }) {
  const isEdit = !!offer;
  const [form, setForm] = useState({
    title: offer?.title||'',
    description: offer?.description||'',
    short_description: offer?.short_description||'',
    provider: offer?.provider?.id||offer?.provider||'',
    category: offer?.category?.id||offer?.category||'',
    offer_type: offer?.offer_type||'',
    platform: offer?.platform||'all',
    payout: offer?.payout||'',
    reward_amount: offer?.reward_amount||'',
    reward_currency: offer?.reward_currency||'Points',
    difficulty: offer?.difficulty||'medium',
    estimated_time_minutes: offer?.estimated_time_minutes||5,
    status: offer?.status||'active',
    is_featured: offer?.is_featured||false,
    is_trending: offer?.is_trending||false,
    click_url: offer?.click_url||'https://example.com/click',
    external_offer_id: offer?.external_offer_id||`manual-${Date.now()}`,
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const save = async () => {
    if (!form.title||!form.provider||!form.offer_type) return toast('Title, provider and type required','error');
    setSaving(true);
    try {
      if (isEdit) { await client.patch(`/offers/offers/${offer.id}/`,form); toast('Offer updated!'); }
      else { await client.post('/offers/offers/',form); toast('Offer created!'); }
      onSaved();
    } catch(e) { toast(e?.response?.data?.detail||JSON.stringify(e?.response?.data)||'Failed','error'); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={isEdit?'✏ EDIT OFFER':'✦ NEW OFFER'} onClose={onClose} width={600}>
      <Field label="Title">
        <input style={inputStyle} value={form.title} onChange={e=>set('title',e.target.value)} placeholder="Offer title"/>
      </Field>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
        <Field label="Provider">
          <SelectInput value={form.provider} onChange={v=>set('provider',v)} options={providers.map(p=>({value:p.id,label:p.name}))}/>
        </Field>
        <Field label="Category">
          <SelectInput value={form.category} onChange={v=>set('category',v)} options={categories.map(c=>({value:c.id,label:c.name}))} placeholder="No category"/>
        </Field>
        <Field label="Offer Type">
          <SelectInput value={form.offer_type} onChange={v=>set('offer_type',v)} options={OFFER_TYPES}/>
        </Field>
        <Field label="Platform">
          <SelectInput value={form.platform} onChange={v=>set('platform',v)} options={PLATFORMS}/>
        </Field>
        <Field label="Payout (USD)">
          <input style={inputStyle} type="number" step="0.01" value={form.payout} onChange={e=>set('payout',e.target.value)} placeholder="0.00"/>
        </Field>
        <Field label="Reward Amount">
          <input style={inputStyle} type="number" step="0.01" value={form.reward_amount} onChange={e=>set('reward_amount',e.target.value)} placeholder="0.00"/>
        </Field>
        <Field label="Difficulty">
          <SelectInput value={form.difficulty} onChange={v=>set('difficulty',v)} options={[{value:'easy',label:'Easy'},{value:'medium',label:'Medium'},{value:'hard',label:'Hard'}]}/>
        </Field>
        <Field label="Est. Time (mins)">
          <input style={inputStyle} type="number" value={form.estimated_time_minutes} onChange={e=>set('estimated_time_minutes',Number(e.target.value))}/>
        </Field>
        <Field label="Status">
          <SelectInput value={form.status} onChange={v=>set('status',v)} options={[{value:'active',label:'Active'},{value:'paused',label:'Paused'},{value:'disabled',label:'Disabled'}]}/>
        </Field>
        <Field label="Reward Currency">
          <input style={inputStyle} value={form.reward_currency} onChange={e=>set('reward_currency',e.target.value)} placeholder="Points"/>
        </Field>
      </div>
      <Field label="Description">
        <textarea style={{...inputStyle,resize:'vertical'}} rows={2} value={form.description} onChange={e=>set('description',e.target.value)}/>
      </Field>
      <Field label="Click URL">
        <input style={inputStyle} value={form.click_url} onChange={e=>set('click_url',e.target.value)} placeholder="https://..."/>
      </Field>
      <div style={{ display:'flex', gap:16, marginBottom:14 }}>
        {[['is_featured','Featured',C.amber],['is_trending','Trending',C.purple]].map(([k,l,c])=>(
          <label key={k} style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', fontSize:12, color:C.text }}>
            <input type="checkbox" checked={form[k]} onChange={e=>set(k,e.target.checked)} style={{ accentColor:c }}/>
            <span style={{ color:c }}>{l}</span>
          </label>
        ))}
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <Btn onClick={save} disabled={saving} style={{ flex:1, justifyContent:'center' }}>
          {saving?<Spinner/>:<><Save size={13}/> SAVE</>}
        </Btn>
        <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
      </div>
    </Modal>
  );
}

function OffersTab({ toast }) {
  const [offers, setOffers] = useState([]);
  const [providers, setProviders] = useState([]);
  const [categories, setCategories] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [modal, setModal] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [oRes,pRes,cRes,sRes] = await Promise.allSettled([
        client.get('/offers/offers/',{params:{page_size:50}}),
        client.get('/offers/providers/'),
        client.get('/offers/categories/'),
        client.get('/offers/offers/stats/'),
      ]);
      if (oRes.status==='fulfilled'){const d=oRes.value.data;setOffers(d?.results??d??[]);}
      if (pRes.status==='fulfilled'){const d=pRes.value.data;setProviders(d?.results??d??[]);}
      if (cRes.status==='fulfilled'){const d=cRes.value.data;setCategories(d?.results??d??[]);}
      if (sRes.status==='fulfilled') setStats(sRes.value.data);
    } catch{ toast('Failed to load offers','error'); }
    finally { setLoading(false); }
  },[]);

  useEffect(()=>{fetchAll();},[fetchAll]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await client.delete(`/offers/offers/${deleteTarget.id}/`);
      setOffers(os=>os.filter(o=>o.id!==deleteTarget.id));
      toast(`"${deleteTarget.title}" deleted`);
      setDeleteTarget(null);
    } catch { toast('Delete failed','error'); }
    finally { setDeleting(false); }
  };

  const toggleFeatured = async (offer) => {
    try {
      const res = await client.patch(`/offers/offers/${offer.id}/toggle_featured/`);
      setOffers(os=>os.map(o=>o.id===offer.id?{...o,is_featured:res.data.is_featured}:o));
      toast(`${offer.title} ${res.data.is_featured?'featured':'unfeatured'}`);
    } catch { toast('Failed','error'); }
  };

  const filtered = offers.filter(o => {
    const ms = o.title?.toLowerCase().includes(search.toLowerCase());
    const mt = !filterType || o.offer_type===filterType;
    const mst = !filterStatus || o.status===filterStatus;
    return ms && mt && mst;
  });

  const diffColor = d => d==='easy'?C.green:d==='hard'?C.red:C.amber;
  const statusColor = s => s==='active'?C.green:s==='paused'?C.amber:C.red;

  return (
    <div>
      {modal && <OfferModal offer={modal==='create'?null:modal} providers={providers} categories={categories} onClose={()=>setModal(null)} onSaved={()=>{setModal(null);fetchAll();}} toast={toast}/>}
      {deleteTarget && <ConfirmModal msg={`Delete "${deleteTarget.title}"?`} onConfirm={handleDelete} onClose={()=>setDeleteTarget(null)} loading={deleting}/>}

      {/* Stats */}
      <div style={{ display:'flex', gap:10, flexWrap:'wrap', marginBottom:20 }}>
        <StatCard label="Total Offers" value={stats?.total_offers??offers.length} icon={Package} color={C.cyan} loading={loading}/>
        <StatCard label="Active" value={stats?.active_offers??offers.filter(o=>o.status==='active').length} icon={CheckCircle} color={C.green} loading={loading}/>
        <StatCard label="Featured" value={stats?.featured_offers??offers.filter(o=>o.is_featured).length} icon={Star} color={C.amber} loading={loading}/>
        <StatCard label="Total Clicks" value={stats?.total_clicks??0} icon={Activity} color={C.purple} loading={loading}/>
        <StatCard label="Total Revenue" value={`$${Number(stats?.total_revenue||0).toFixed(0)}`} icon={DollarSign} color={C.pink} loading={loading}/>
      </div>

      {/* Toolbar */}
      <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:16, flexWrap:'wrap' }}>
        <div style={{ flex:1, minWidth:200, display:'flex', alignItems:'center', gap:8, background:C.panel, border:`1px solid ${C.border}`, borderRadius:8, padding:'8px 12px' }}>
          <Search size={13} color={C.textDim}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search offers..." style={{ background:'none', border:'none', color:C.text, fontSize:12, outline:'none', flex:1 }}/>
        </div>
        <SelectInput value={filterType} onChange={setFilterType} options={OFFER_TYPES} placeholder="All types"/>
        <SelectInput value={filterStatus} onChange={setFilterStatus} options={[{value:'active',label:'Active'},{value:'paused',label:'Paused'},{value:'expired',label:'Expired'}]} placeholder="All status"/>
        <Btn onClick={fetchAll} outline sm><RefreshCw size={13}/></Btn>
        <Btn onClick={()=>setModal('create')} sm><Plus size={13}/> Add Offer</Btn>
      </div>

      {/* Offers Table */}
      {loading ? <Skeleton h={300}/> : filtered.length===0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.textDim }}>No offers found</div>
      ) : (
        <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, overflow:'hidden' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead>
              <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                {['Title','Type','Provider','Platform','Reward','Difficulty','Status','Featured','Actions'].map(h=>(
                  <th key={h} style={{ padding:'11px 14px', textAlign:'left', color:C.textDim, fontWeight:600, fontSize:10, letterSpacing:1, whiteSpace:'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((o,i)=>(
                <tr key={o.id} style={{ borderBottom:`1px solid ${C.border}`, background:i%2===0?'transparent':`${C.bg}44` }}>
                  <td style={{ padding:'10px 14px', color:C.text, maxWidth:200 }}>
                    <div style={{ fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{o.title}</div>
                    <div style={{ fontSize:10, color:C.textDim, marginTop:2 }}>{o.provider_name||''}</div>
                  </td>
                  <td style={{ padding:'10px 14px' }}><Badge label={o.offer_type_display||o.offer_type} color={C.cyan}/></td>
                  <td style={{ padding:'10px 14px', color:C.textDim, fontSize:11 }}>{o.provider_name||'—'}</td>
                  <td style={{ padding:'10px 14px' }}><Badge label={o.platform} color={C.purple}/></td>
                  <td style={{ padding:'10px 14px', color:C.green, fontFamily:"'Courier New',monospace", fontWeight:700 }}>
                    {Number(o.reward_amount||0).toFixed(2)} <span style={{ fontSize:10, color:C.textDim }}>{o.reward_currency}</span>
                  </td>
                  <td style={{ padding:'10px 14px' }}><Badge label={o.difficulty||'—'} color={diffColor(o.difficulty)}/></td>
                  <td style={{ padding:'10px 14px' }}><Badge label={o.status} color={statusColor(o.status)}/></td>
                  <td style={{ padding:'10px 14px', textAlign:'center' }}>
                    <button onClick={()=>toggleFeatured(o)} style={{ background:'none', border:'none', cursor:'pointer', color:o.is_featured?C.amber:C.textDim }}>
                      <Star size={14} fill={o.is_featured?C.amber:'none'}/>
                    </button>
                  </td>
                  <td style={{ padding:'10px 14px' }}>
                    <div style={{ display:'flex', gap:6 }}>
                      <Btn onClick={()=>setModal(o)} color={C.cyan} sm><Edit3 size={11}/></Btn>
                      <Btn onClick={()=>setDeleteTarget(o)} color={C.red} outline sm><Trash2 size={11}/></Btn>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── CATEGORIES TAB ───────────────────────────────────────────────
function CategoriesTab({ toast }) {
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const res = await client.get('/offers/categories/');
      const d = res.data; setCats(d?.results??d??[]);
    } catch { toast('Failed to load categories','error'); }
    finally { setLoading(false); }
  },[]);

  useEffect(()=>{fetchAll();},[fetchAll]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await client.delete(`/offers/categories/${deleteTarget.id}/`);
      setCats(cs=>cs.filter(c=>c.id!==deleteTarget.id));
      toast('Category deleted'); setDeleteTarget(null);
    } catch { toast('Delete failed','error'); }
    finally { setDeleting(false); }
  };

  return (
    <div>
      {modal && <CategoryModal cat={modal==='create'?null:modal} onClose={()=>setModal(null)} onSaved={()=>{setModal(null);fetchAll();}} toast={toast}/>}
      {deleteTarget && <ConfirmModal msg={`Delete "${deleteTarget.name}"?`} onConfirm={handleDelete} onClose={()=>setDeleteTarget(null)} loading={deleting}/>}

      <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:16 }}>
        <Btn onClick={()=>setModal('create')}><Plus size={13}/> Add Category</Btn>
      </div>

      {loading ? <Skeleton h={200}/> : cats.length===0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.textDim }}>No categories found</div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))', gap:12 }}>
          {cats.map(c=>(
            <div key={c.id} style={{ background:C.panel, border:`1px solid ${c.color||C.border}30`, borderRadius:10, padding:16, borderLeft:`3px solid ${c.color||C.cyan}` }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                <div style={{ fontSize:14, fontWeight:700, color:C.text }}>{c.name}</div>
                <Badge label={c.is_active?'ACTIVE':'OFF'} color={c.is_active?C.green:C.textDim}/>
              </div>
              <div style={{ fontSize:11, color:C.textDim, marginBottom:10 }}>{c.description||'No description'}</div>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <span style={{ fontSize:11, color:C.textDim }}>{c.offer_count||0} offers</span>
                <div style={{ display:'flex', gap:6 }}>
                  <Btn onClick={()=>setModal(c)} color={C.cyan} sm><Edit3 size={11}/></Btn>
                  <Btn onClick={()=>setDeleteTarget(c)} color={C.red} outline sm><Trash2 size={11}/></Btn>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CategoryModal({ cat, onClose, onSaved, toast }) {
  const isEdit = !!cat;
  const [form, setForm] = useState({
    name: cat?.name||'',
    slug: cat?.slug||'',
    description: cat?.description||'',
    icon: cat?.icon||'',
    color: cat?.color||'#3B82F6',
    display_order: cat?.display_order||0,
    is_featured: cat?.is_featured||false,
    is_active: cat?.is_active!==undefined ? cat.is_active : true,
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const save = async () => {
    if (!form.name.trim()) return toast('Name required','error');
    if (!form.slug.trim()) form.slug = form.name.toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'');
    setSaving(true);
    try {
      if (isEdit) { await client.patch(`/offers/categories/${cat.id}/`,form); toast('Category updated!'); }
      else { await client.post('/offers/categories/',form); toast('Category created!'); }
      onSaved();
    } catch(e) { toast(e?.response?.data?.detail||'Failed','error'); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={isEdit?'✏ EDIT CATEGORY':'✦ NEW CATEGORY'} onClose={onClose} width={440}>
      <Field label="Name"><input style={inputStyle} value={form.name} onChange={e=>{set('name',e.target.value);if(!isEdit)set('slug',e.target.value.toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,''));}} placeholder="Category name"/></Field>
      <Field label="Slug"><input style={inputStyle} value={form.slug} onChange={e=>set('slug',e.target.value)} placeholder="category-slug"/></Field>
      <Field label="Description"><textarea style={{...inputStyle,resize:'vertical'}} rows={2} value={form.description} onChange={e=>set('description',e.target.value)}/></Field>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
        <Field label="Color"><input type="color" value={form.color} onChange={e=>set('color',e.target.value)} style={{ height:36, width:'100%', borderRadius:7, border:`1px solid ${C.border2}`, background:'none', cursor:'pointer' }}/></Field>
        <Field label="Display Order"><input style={inputStyle} type="number" value={form.display_order} onChange={e=>set('display_order',Number(e.target.value))}/></Field>
      </div>
      <div style={{ display:'flex', gap:16, marginBottom:14 }}>
        {[['is_active','Active',C.green],['is_featured','Featured',C.amber]].map(([k,l,c])=>(
          <label key={k} style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', fontSize:12, color:C.text }}>
            <input type="checkbox" checked={form[k]} onChange={e=>set(k,e.target.checked)} style={{ accentColor:c }}/><span style={{ color:c }}>{l}</span>
          </label>
        ))}
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <Btn onClick={save} disabled={saving} style={{ flex:1, justifyContent:'center' }}>{saving?<Spinner/>:<><Save size={13}/> SAVE</>}</Btn>
        <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
      </div>
    </Modal>
  );
}

// ─── CONVERSIONS TAB ──────────────────────────────────────────────
function ConversionsTab({ toast }) {
  const [convs, setConvs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [selected, setSelected] = useState([]);
  const [acting, setActing] = useState(null);
  const [rejectModal, setRejectModal] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes,sRes] = await Promise.allSettled([
        client.get('/offers/conversions/',{params:{page_size:50,...(filterStatus&&{status:filterStatus})}}),
        client.get('/offers/conversions/stats/'),
      ]);
      if (cRes.status==='fulfilled'){const d=cRes.value.data;setConvs(d?.results??d??[]);}
      if (sRes.status==='fulfilled') setStats(sRes.value.data);
    } catch { toast('Failed to load conversions','error'); }
    finally { setLoading(false); }
  },[filterStatus]);

  useEffect(()=>{fetchAll();},[fetchAll]);

  const approve = async (id) => {
    setActing(id);
    try {
      await client.post(`/offers/conversions/${id}/approve/`);
      toast('Conversion approved!'); fetchAll();
    } catch(e) { toast(e?.response?.data?.error||'Failed','error'); }
    finally { setActing(null); }
  };

  const reject = async () => {
    if (!rejectModal) return;
    setActing(rejectModal);
    try {
      await client.post(`/offers/conversions/${rejectModal}/reject/`,{reason:rejectReason});
      toast('Conversion rejected'); setRejectModal(null); setRejectReason(''); fetchAll();
    } catch(e) { toast(e?.response?.data?.error||'Failed','error'); }
    finally { setActing(null); }
  };

  const bulkApprove = async () => {
    if (!selected.length) return;
    try {
      await client.post('/offers/conversions/bulk_approve/',{ids:selected});
      toast(`${selected.length} approved!`); setSelected([]); fetchAll();
    } catch(e) { toast(e?.response?.data?.error||'Failed','error'); }
  };

  const statusColor = s => ({pending:C.amber,approved:C.green,rejected:C.red,chargeback:C.purple,reversed:C.textDim}[s]||C.textDim);

  return (
    <div>
      {rejectModal && (
        <Modal title="REJECT CONVERSION" onClose={()=>setRejectModal(null)} width={400}>
          <Field label="Rejection Reason">
            <textarea style={{...inputStyle,resize:'vertical'}} rows={3} value={rejectReason} onChange={e=>setRejectReason(e.target.value)} placeholder="Reason for rejection..."/>
          </Field>
          <div style={{ display:'flex', gap:10 }}>
            <Btn onClick={reject} color={C.red} disabled={!!acting} style={{ flex:1, justifyContent:'center' }}>{acting?<Spinner/>:'REJECT'}</Btn>
            <Btn onClick={()=>setRejectModal(null)} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
          </div>
        </Modal>
      )}

      {/* Stats */}
      <div style={{ display:'flex', gap:10, flexWrap:'wrap', marginBottom:20 }}>
        <StatCard label="Total" value={stats?.total||convs.length} icon={List} color={C.cyan} loading={loading}/>
        <StatCard label="Pending" value={stats?.pending||convs.filter(c=>c.status==='pending').length} icon={Clock} color={C.amber} loading={loading}/>
        <StatCard label="Approved" value={stats?.approved||convs.filter(c=>c.status==='approved').length} icon={CheckCircle} color={C.green} loading={loading}/>
        <StatCard label="Rejected" value={stats?.rejected||convs.filter(c=>c.status==='rejected').length} icon={AlertCircle} color={C.red} loading={loading}/>
        <StatCard label="Total Payout" value={`$${Number(stats?.total_payout||0).toFixed(2)}`} icon={DollarSign} color={C.pink} loading={loading}/>
      </div>

      {/* Toolbar */}
      <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:16, flexWrap:'wrap' }}>
        {['','pending','approved','rejected','chargeback'].map(s=>(
          <button key={s} onClick={()=>setFilterStatus(s)} style={{ padding:'7px 14px', borderRadius:7, fontSize:11, fontWeight:600, letterSpacing:0.8, cursor:'pointer', background:filterStatus===s?`${C.cyan}22`:'transparent', border:`1px solid ${filterStatus===s?C.cyan:C.border}`, color:filterStatus===s?C.cyan:C.textDim }}>
            {s?s.toUpperCase():'ALL'}
          </button>
        ))}
        <Btn onClick={fetchAll} outline sm><RefreshCw size={13}/></Btn>
        {selected.length>0 && <Btn onClick={bulkApprove} color={C.green} sm><CheckCircle size={13}/> Approve ({selected.length})</Btn>}
      </div>

      {/* Table */}
      {loading ? <Skeleton h={300}/> : convs.length===0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.textDim }}>No conversions found</div>
      ) : (
        <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, overflow:'hidden' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead>
              <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                <th style={{ padding:'11px 14px', width:36 }}>
                  <input type="checkbox" onChange={e=>setSelected(e.target.checked?convs.filter(c=>c.status==='pending').map(c=>c.id):[])} style={{ accentColor:C.cyan }}/>
                </th>
                {['Offer','User','Reward','Status','Date','Actions'].map(h=>(
                  <th key={h} style={{ padding:'11px 14px', textAlign:'left', color:C.textDim, fontWeight:600, fontSize:10, letterSpacing:1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {convs.map((c,i)=>(
                <tr key={c.id} style={{ borderBottom:`1px solid ${C.border}`, background:i%2===0?'transparent':`${C.bg}44` }}>
                  <td style={{ padding:'10px 14px' }}>
                    {c.status==='pending' && <input type="checkbox" checked={selected.includes(c.id)} onChange={e=>setSelected(p=>e.target.checked?[...p,c.id]:p.filter(x=>x!==c.id))} style={{ accentColor:C.cyan }}/>}
                  </td>
                  <td style={{ padding:'10px 14px', color:C.text, maxWidth:180 }}>
                    <div style={{ fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{c.offer_title||'—'}</div>
                  </td>
                  <td style={{ padding:'10px 14px', color:C.textDim, fontSize:11 }}>{c.user_name||'—'}</td>
                  <td style={{ padding:'10px 14px', color:C.green, fontFamily:"'Courier New',monospace", fontWeight:700 }}>
                    {Number(c.reward_amount||0).toFixed(4)} <span style={{ fontSize:10, color:C.textDim }}>{c.reward_currency}</span>
                  </td>
                  <td style={{ padding:'10px 14px' }}><Badge label={c.status} color={statusColor(c.status)}/></td>
                  <td style={{ padding:'10px 14px', color:C.textDim, fontSize:11 }}>
                    {c.converted_at ? new Date(c.converted_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding:'10px 14px' }}>
                    {c.status==='pending' && (
                      <div style={{ display:'flex', gap:6 }}>
                        <Btn onClick={()=>approve(c.id)} color={C.green} sm disabled={acting===c.id}>
                          {acting===c.id?<Spinner size={11}/>:<CheckCircle size={11}/>} OK
                        </Btn>
                        <Btn onClick={()=>setRejectModal(c.id)} color={C.red} outline sm><X size={11}/></Btn>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── MAIN ─────────────────────────────────────────────────────────
export default function Offerwall() {
  const [activeTab, setActiveTab] = useState('providers');
  const { toasts, push: toast } = useToast();

  return (
    <div style={{ minHeight:'100vh', background:`linear-gradient(135deg,${C.bg} 0%,${C.bg2} 50%,${C.bg} 100%)`, color:C.text, fontFamily:"'Segoe UI',sans-serif" }}>
      <style>{`
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
        @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        *{box-sizing:border-box;}
        select option{background:#0a1c2e;color:#c8dff0;}
      `}</style>

      <ToastContainer toasts={toasts}/>
        <PageEndpointPanel pageKey="Offerwall" title="Offerwall Endpoints" />

      {/* Header */}
      <div style={{ padding:'24px 32px 0', borderBottom:`1px solid ${C.border}`, background:`${C.bg2}88` }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
          <div>
            <div style={{ fontSize:22, fontWeight:800, color:C.text, letterSpacing:2 }}>
              <span style={{ color:C.cyan }}>OFFERWALL</span> MANAGER
            </div>
            <div style={{ fontSize:11, color:C.textDim, letterSpacing:1, marginTop:2 }}>
              Providers · Offers · Categories · Conversions
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex', gap:2 }}>
          {TAB_DEFS.map(t=>{
            const Icon = t.icon;
            const active = activeTab===t.key;
            return (
              <button key={t.key} onClick={()=>setActiveTab(t.key)} style={{
                display:'flex', alignItems:'center', gap:7,
                padding:'10px 20px', fontSize:12, fontWeight:600, letterSpacing:0.8,
                cursor:'pointer', border:'none', borderRadius:'8px 8px 0 0',
                background: active?C.panel:'transparent',
                color: active?C.cyan:C.textDim,
                borderBottom: active?`2px solid ${C.cyan}`:'2px solid transparent',
                transition:'all .15s',
              }}>
                <Icon size={14}/> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div style={{ padding:'28px 32px', animation:'fadeUp .25s ease' }} key={activeTab}>
        {activeTab==='providers'   && <ProvidersTab   toast={toast}/>}
        {activeTab==='offers'      && <OffersTab      toast={toast}/>}
        {activeTab==='categories'  && <CategoriesTab  toast={toast}/>}
        {activeTab==='conversions' && <ConversionsTab toast={toast}/>}
      </div>
    </div>
  );
}