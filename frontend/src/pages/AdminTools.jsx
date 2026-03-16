// src/pages/AdminTools.jsx
// Admin: Bidding + Reward Policy + Blacklist — all in one
import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';

const C = {
  bg:'#020912', bg2:'#050e1a', panel:'#0a1c2e',
  border:'rgba(0,180,255,0.12)', border2:'rgba(0,180,255,0.22)',
  text:'#c8dff0', dim:'#4a7a9b',
  cyan:'#00c8ff', green:'#00e87a', amber:'#ffc300', red:'#ff3d71', purple:'#a855f7',
};
const inp = { width:'100%', background:`${C.bg}cc`, border:`1px solid ${C.border2}`, borderRadius:7, padding:'9px 12px', color:C.text, fontSize:12, outline:'none', boxSizing:'border-box' };

function useToast() {
  const [toasts, setToasts] = useState([]);
  const push = (msg, type='success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, msg, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500);
  };
  return { toasts, push };
}
const Badge = ({ label, color }) => (
  <span style={{ fontSize:10, fontWeight:700, letterSpacing:1, color, background:`${color}18`, border:`1px solid ${color}40`, borderRadius:4, padding:'2px 8px' }}>{label}</span>
);
const Btn = ({ children, onClick, color=C.cyan, outline=false, sm=false, disabled=false }) => (
  <button onClick={onClick} disabled={disabled} style={{ display:'inline-flex', alignItems:'center', gap:5,
    padding:sm?'5px 12px':'8px 16px', fontSize:sm?11:12, fontWeight:600, borderRadius:7,
    cursor:disabled?'not-allowed':'pointer', background:outline?'transparent':`${color}22`,
    border:`1px solid ${color}${outline?'60':'40'}`, color, opacity:disabled?0.5:1 }}>{children}</button>
);
const Sel = ({ value, onChange, options, placeholder='Select...' }) => (
  <select value={value||''} onChange={e=>onChange(e.target.value)} style={inp}>
    <option value=''>{placeholder}</option>
    {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

// ── Bidding Tab ───────────────────────────────────────────────────
function BiddingTab({ toast }) {
  const [data, setData]   = useState({ stats:{}, bids:[] });
  const [loading, setL]   = useState(true);
  const [acting, setA]    = useState(null);

  const fetch = useCallback(async () => {
    setL(true);
    try {
      const res = await client.get('/promotions/bidding/');
      setData(res.data ?? { stats:{}, bids:[] });
    } catch { toast('Failed to load bids', 'error'); }
    finally { setL(false); }
  },[]);
  useEffect(()=>{fetch();},[fetch]);

  const resolve = async (id, action) => {
    setA(id);
    try {
      await client.post(`/promotions/bidding/${id}/resolve/`, { action });
      toast(`Bid ${action}`); fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? 'Failed', 'error'); }
    finally { setA(null); }
  };

  const { stats, bids } = data;
  return (
    <div>
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        {[
          { label:'Total Bids', val:stats.total_bids??0, color:C.cyan },
          { label:'Active Auctions', val:stats.active_auctions??0, color:C.amber },
          { label:'Won Bids', val:stats.won_bids??0, color:C.green },
          { label:'Avg Bid', val:`$${Number(stats.avg_bid||0).toFixed(2)}`, color:C.purple },
        ].map(s=>(
          <div key={s.label} style={{ flex:'1 1 120px', background:C.panel, border:`1px solid ${s.color}20`, borderRadius:10, padding:'14px 18px' }}>
            <div style={{ fontSize:9, color:C.dim, letterSpacing:1, marginBottom:4 }}>{s.label}</div>
            <div style={{ fontSize:20, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>{s.val}</div>
          </div>
        ))}
      </div>
      <Btn onClick={fetch} outline sm style={{ marginBottom:14 }}>↺ Refresh</Btn>
      {loading ? <div style={{ textAlign:'center', padding:'40px', color:C.dim }}>Loading...</div> : (
        <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, overflow:'hidden' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead><tr style={{ borderBottom:`1px solid ${C.border}` }}>
              {['Campaign','Advertiser','Bid Amount','Auction Type','Status','Actions'].map(h=>(
                <th key={h} style={{ padding:'11px 14px', textAlign:'left', color:C.dim, fontSize:10, letterSpacing:1 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {bids.map((b,i)=>{
                const sc = b.status==='won'?C.green:b.status==='lost'?C.red:b.status==='cancelled'?C.dim:C.amber;
                return (
                  <tr key={b.id} style={{ borderBottom:`1px solid ${C.border}`, background:i%2===0?'transparent':`${C.bg}44` }}>
                    <td style={{ padding:'10px 14px', color:C.text }}>{b.campaign_title?.slice(0,30) ?? `#${b.campaign_id}`}</td>
                    <td style={{ padding:'10px 14px', color:C.dim, fontSize:11 }}>{b.advertiser}</td>
                    <td style={{ padding:'10px 14px', color:C.green, fontFamily:"'Courier New',monospace", fontWeight:700 }}>${b.bid_amount}</td>
                    <td style={{ padding:'10px 14px' }}><Badge label={b.auction_type?.toUpperCase()} color={C.purple}/></td>
                    <td style={{ padding:'10px 14px' }}><Badge label={b.status?.toUpperCase()} color={sc}/></td>
                    <td style={{ padding:'10px 14px' }}>
                      {b.status === 'pending' && (
                        <div style={{ display:'flex', gap:6 }}>
                          <Btn onClick={()=>resolve(b.id,'won')} color={C.green} sm disabled={acting===b.id}>Won</Btn>
                          <Btn onClick={()=>resolve(b.id,'lost')} color={C.red} outline sm disabled={acting===b.id}>Lost</Btn>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {bids.length===0 && <tr><td colSpan={6} style={{ padding:'40px', textAlign:'center', color:C.dim }}>No bids yet</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Reward Policy Tab ─────────────────────────────────────────────
function RewardPolicyTab({ toast }) {
  const [policies, setPolicies] = useState([]);
  const [cats, setCats]         = useState([]);
  const [loading, setL]         = useState(true);
  const [modal, setModal]       = useState(null);
  const [form, setForm]         = useState({ country_code:'', category:'', rate_usd:'', min_payout_usd:'1.00' });
  const [saving, setSaving]     = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const fetch = useCallback(async () => {
    setL(true);
    try {
      const [pRes, cRes] = await Promise.all([
        client.get('/promotions/reward-policies/', { params: { page_size: 100 } }),
        client.get('/promotions/categories/'),
      ]);
      setPolicies(pRes.data?.results ?? pRes.data ?? []);
      setCats(cRes.data?.results ?? cRes.data ?? []);
    } catch { toast('Failed to load', 'error'); }
    finally { setL(false); }
  },[]);
  useEffect(()=>{fetch();},[fetch]);

  const save = async () => {
    if (!form.country_code.match(/^[A-Z]{2}$/)) return toast('Country code must be 2 uppercase letters (e.g. US, BD)', 'error');
    if (!form.category) return toast('Category required', 'error');
    if (!form.rate_usd || Number(form.rate_usd) <= 0) return toast('Rate must be positive', 'error');
    setSaving(true);
    try {
      if (modal?.id) {
        await client.patch(`/promotions/reward-policies/${modal.id}/`, { rate_usd: form.rate_usd, min_payout_usd: form.min_payout_usd });
        toast('Policy updated!');
      } else {
        await client.post('/promotions/reward-policies/', form);
        toast('Policy created!');
      }
      setModal(null); fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? JSON.stringify(e?.response?.data) ?? 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  const del = async (id) => {
    try { await client.delete(`/promotions/reward-policies/${id}/`); toast('Deleted'); fetch(); }
    catch(e) { toast(e?.response?.data?.detail ?? 'Delete failed', 'error'); }
  };

  const COUNTRIES = [
    {value:'US',label:'🇺🇸 USA'},{value:'GB',label:'🇬🇧 UK'},{value:'CA',label:'🇨🇦 Canada'},
    {value:'AU',label:'🇦🇺 Australia'},{value:'DE',label:'🇩🇪 Germany'},{value:'BD',label:'🇧🇩 Bangladesh'},
    {value:'IN',label:'🇮🇳 India'},{value:'PK',label:'🇵🇰 Pakistan'},{value:'NG',label:'🇳🇬 Nigeria'},
    {value:'PH',label:'🇵🇭 Philippines'},{value:'BR',label:'🇧🇷 Brazil'},{value:'ID',label:'🇮🇩 Indonesia'},
  ];

  return (
    <div>
      {modal !== null && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center' }} onClick={()=>setModal(null)}>
          <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,${C.bg2},#0d0a20)`, border:`1px solid ${C.cyan}44`, borderRadius:14, padding:28, width:440 }}>
            <div style={{ fontSize:14, fontWeight:700, color:C.cyan, marginBottom:20 }}>{modal?.id ? '✏ EDIT POLICY' : '✦ NEW POLICY'}</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>COUNTRY</div>
                {modal?.id
                  ? <div style={{ fontSize:12, color:C.text, padding:'9px 12px', background:`${C.bg}cc`, borderRadius:7, border:`1px solid ${C.border2}` }}>{modal.country_code}</div>
                  : <Sel value={form.country_code} onChange={v=>set('country_code',v)} options={COUNTRIES} placeholder="Select country"/>
                }
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>CATEGORY</div>
                {modal?.id
                  ? <div style={{ fontSize:12, color:C.text, padding:'9px 12px', background:`${C.bg}cc`, borderRadius:7, border:`1px solid ${C.border2}` }}>{modal.category}</div>
                  : <Sel value={form.category} onChange={v=>set('category',v)} options={cats.map(c=>({value:c.id,label:c.name}))} placeholder="Select category"/>
                }
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>RATE (USD per task)</div>
                <input style={inp} type="number" step="0.0001" value={form.rate_usd} onChange={e=>set('rate_usd',e.target.value)} placeholder="0.5000"/>
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>MIN PAYOUT (USD)</div>
                <input style={inp} type="number" step="0.01" value={form.min_payout_usd} onChange={e=>set('min_payout_usd',e.target.value)} placeholder="1.00"/>
              </div>
            </div>
            <div style={{ display:'flex', gap:10, marginTop:8 }}>
              <Btn onClick={save} disabled={saving} style={{ flex:1, justifyContent:'center' }}>{saving?'...':'SAVE'}</Btn>
              <Btn onClick={()=>setModal(null)} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
            </div>
          </div>
        </div>
      )}

      <div style={{ display:'flex', justifyContent:'flex-end', gap:8, marginBottom:16 }}>
        <Btn onClick={fetch} outline sm>↺</Btn>
        <Btn onClick={()=>{ setForm({ country_code:'', category:'', rate_usd:'', min_payout_usd:'1.00' }); setModal({}); }}>+ Add Policy</Btn>
      </div>

      {loading ? <div style={{ textAlign:'center', padding:'40px', color:C.dim }}>Loading...</div> : (
        <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, overflow:'hidden' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead><tr style={{ borderBottom:`1px solid ${C.border}` }}>
              {['Country','Category','Rate (USD)','Min Payout','Status','Actions'].map(h=>(
                <th key={h} style={{ padding:'11px 14px', textAlign:'left', color:C.dim, fontSize:10, letterSpacing:1 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {policies.map((p,i)=>(
                <tr key={p.id} style={{ borderBottom:`1px solid ${C.border}`, background:i%2===0?'transparent':`${C.bg}44` }}>
                  <td style={{ padding:'10px 14px', color:C.text, fontWeight:700 }}>{p.country_code}</td>
                  <td style={{ padding:'10px 14px', color:C.dim }}>{p.category}</td>
                  <td style={{ padding:'10px 14px', color:C.green, fontFamily:"'Courier New',monospace", fontWeight:700 }}>${p.rate_usd}</td>
                  <td style={{ padding:'10px 14px', color:C.text, fontFamily:"'Courier New',monospace" }}>${p.min_payout_usd}</td>
                  <td style={{ padding:'10px 14px' }}><Badge label={p.is_active?'ACTIVE':'INACTIVE'} color={p.is_active?C.green:C.dim}/></td>
                  <td style={{ padding:'10px 14px' }}>
                    <div style={{ display:'flex', gap:6 }}>
                      <Btn onClick={()=>{ setForm({ rate_usd:p.rate_usd, min_payout_usd:p.min_payout_usd }); setModal(p); }} color={C.cyan} sm>Edit</Btn>
                      <Btn onClick={()=>del(p.id)} color={C.red} outline sm>Del</Btn>
                    </div>
                  </td>
                </tr>
              ))}
              {policies.length===0 && <tr><td colSpan={6} style={{ padding:'40px', textAlign:'center', color:C.dim }}>No policies yet. Add country rates to control payouts.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Blacklist Tab ─────────────────────────────────────────────────
function BlacklistTab({ toast }) {
  const [list, setList]   = useState([]);
  const [loading, setL]   = useState(true);
  const [modal, setModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm]   = useState({ type:'user', value:'', reason:'', severity:'permanent', expires_at:'' });
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  const fetch = useCallback(async () => {
    setL(true);
    try {
      const res = await client.get('/promotions/blacklist/', { params: { page_size: 100 } });
      setList(res.data?.results ?? res.data ?? []);
    } catch { toast('Failed to load', 'error'); }
    finally { setL(false); }
  },[]);
  useEffect(()=>{fetch();},[fetch]);

  const add = async () => {
    if (!form.value.trim()) return toast('Value required', 'error');
    if (form.reason.trim().length < 5) return toast('Reason must be at least 5 characters', 'error');
    if (form.severity === 'temp_ban' && !form.expires_at) return toast('Expiry date required for temp ban', 'error');
    setSaving(true);
    try {
      await client.post('/promotions/blacklist/', { ...form, value: form.value.trim(), reason: form.reason.trim() });
      toast('Added to blacklist!'); setModal(false); fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? JSON.stringify(e?.response?.data) ?? 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  const remove = async (id, value) => {
    try { await client.delete(`/promotions/blacklist/${id}/`); toast(`Removed: ${value}`); fetch(); }
    catch(e) { toast(e?.response?.data?.detail ?? 'Remove failed', 'error'); }
  };

  const sevColor = s => ({ warn:C.amber, temp_ban:C.purple, permanent:C.red }[s] ?? C.dim);
  const typeColor = t => ({ user:C.cyan, ip:C.amber, device:C.purple, email_domain:C.green, channel_url:C.pink, phone:C.red }[t] ?? C.dim);

  return (
    <div>
      {modal && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center' }} onClick={()=>setModal(false)}>
          <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,${C.bg2},#0d0a20)`, border:`1px solid ${C.red}44`, borderRadius:14, padding:28, width:480 }}>
            <div style={{ fontSize:14, fontWeight:700, color:C.red, marginBottom:20 }}>🚫 ADD TO BLACKLIST</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>TYPE</div>
                <Sel value={form.type} onChange={v=>set('type',v)} options={[
                  {value:'user',label:'User Account'},{value:'ip',label:'IP Address'},
                  {value:'device',label:'Device'},{value:'email_domain',label:'Email Domain'},
                  {value:'channel_url',label:'Channel URL'},{value:'phone',label:'Phone'},
                ]}/>
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>SEVERITY</div>
                <Sel value={form.severity} onChange={v=>set('severity',v)} options={[
                  {value:'warn',label:'Warning Only'},{value:'temp_ban',label:'Temporary Ban'},
                  {value:'permanent',label:'Permanent Ban'},
                ]}/>
              </div>
            </div>
            <div style={{ marginBottom:14 }}>
              <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>VALUE (user ID, IP, domain etc.)</div>
              <input style={inp} value={form.value} onChange={e=>set('value',e.target.value)} placeholder="e.g. 123, 192.168.1.1, spam.com"/>
            </div>
            <div style={{ marginBottom:14 }}>
              <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>REASON (min 5 chars)</div>
              <textarea style={{ ...inp, resize:'vertical' }} rows={2} value={form.reason} onChange={e=>set('reason',e.target.value)} placeholder="Why are you blacklisting this?"/>
            </div>
            {form.severity === 'temp_ban' && (
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>EXPIRES AT</div>
                <input style={inp} type="datetime-local" value={form.expires_at} onChange={e=>set('expires_at',e.target.value)}/>
              </div>
            )}
            <div style={{ display:'flex', gap:10 }}>
              <Btn onClick={add} color={C.red} disabled={saving} style={{ flex:1, justifyContent:'center' }}>{saving?'...':'🚫 BLACKLIST'}</Btn>
              <Btn onClick={()=>setModal(false)} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
            </div>
          </div>
        </div>
      )}

      <div style={{ display:'flex', justifyContent:'flex-end', gap:8, marginBottom:16 }}>
        <Btn onClick={fetch} outline sm>↺</Btn>
        <Btn onClick={()=>{ setForm({ type:'user', value:'', reason:'', severity:'permanent', expires_at:'' }); setModal(true); }} color={C.red}>🚫 Add to Blacklist</Btn>
      </div>

      {loading ? <div style={{ textAlign:'center', padding:'40px', color:C.dim }}>Loading...</div> : (
        <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
          {list.map(b => {
            const sc = sevColor(b.severity);
            return (
              <div key={b.id} style={{ background:C.panel, border:`1px solid ${sc}22`, borderRadius:10, padding:'14px 18px', display:'flex', alignItems:'center', gap:12, borderLeft:`3px solid ${sc}` }}>
                <Badge label={b.type?.toUpperCase().replace('_',' ')} color={typeColor(b.type)}/>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:13, fontWeight:700, color:C.text }}>{b.value}</div>
                  <div style={{ fontSize:11, color:C.dim, marginTop:2 }}>{b.reason}</div>
                  {b.expires_at && <div style={{ fontSize:10, color:C.amber, marginTop:2 }}>Expires: {new Date(b.expires_at).toLocaleDateString()}</div>}
                </div>
                <Badge label={b.severity?.toUpperCase().replace('_',' ')} color={sc}/>
                <Btn onClick={()=>remove(b.id, b.value)} color={C.red} outline sm>Remove</Btn>
              </div>
            );
          })}
          {list.length === 0 && <div style={{ textAlign:'center', padding:'60px', color:C.dim }}>Blacklist is empty</div>}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────
export default function AdminTools() {
  const [tab, setTab] = useState('bidding');
  const { toasts, push: toast } = useToast();

  const TABS = [
    { key:'bidding',       label:'Ad Bidding',    color:'#ffc300' },
    { key:'reward_policy', label:'Reward Rates',  color:'#00e87a' },
    { key:'blacklist',     label:'Blacklist',      color:'#ff3d71' },
  ];

  return (
    <div style={{ minHeight:'100vh', background:`linear-gradient(135deg,${C.bg},${C.bg2})`, color:C.text, fontFamily:"'Segoe UI',sans-serif" }}>
      <style>{`*{box-sizing:border-box} select option{background:#0a1c2e}`}</style>
      <div style={{ position:'fixed', bottom:24, right:24, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
        {toasts.map(t=>(
          <div key={t.id} style={{ padding:'11px 18px', borderRadius:8, fontSize:12, fontFamily:"'Courier New',monospace",
            background:t.type==='error'?`${C.red}18`:`${C.green}18`, border:`1px solid ${t.type==='error'?C.red:C.green}44`,
            color:t.type==='error'?C.red:C.green }}>{t.type==='error'?'✗':'✓'} {t.msg}</div>
        ))}
      </div>

      {/* Header */}
      <div style={{ padding:'24px 32px 0', borderBottom:`1px solid ${C.border}` }}>
        <div style={{ fontSize:22, fontWeight:800, letterSpacing:2, marginBottom:4 }}>
          <span style={{ color:C.amber }}>ADMIN</span> TOOLS
        </div>
        <div style={{ fontSize:11, color:C.dim, letterSpacing:1, marginBottom:20 }}>Bidding · Reward Rates · Blacklist</div>
        <div style={{ display:'flex', gap:2 }}>
          {TABS.map(t=>(
            <button key={t.key} onClick={()=>setTab(t.key)} style={{
              display:'flex', alignItems:'center', gap:7, padding:'10px 20px',
              fontSize:12, fontWeight:600, letterSpacing:0.8, cursor:'pointer',
              border:'none', borderRadius:'8px 8px 0 0',
              background:tab===t.key?C.panel:'transparent',
              color:tab===t.key?t.color:C.dim,
              borderBottom:tab===t.key?`2px solid ${t.color}`:'2px solid transparent'
            }}>{t.label}</button>
          ))}
        </div>
      </div>

      <div style={{ padding:'28px 32px' }}>
        {tab==='bidding'       && <BiddingTab      toast={toast}/>}
        {tab==='reward_policy' && <RewardPolicyTab toast={toast}/>}
        {tab==='blacklist'     && <BlacklistTab    toast={toast}/>}
      </div>
    </div>
  );
}
