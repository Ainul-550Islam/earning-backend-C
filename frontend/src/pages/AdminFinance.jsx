// src/pages/AdminFinance.jsx
// Admin: Revenue dashboard — commission, transactions, escrow
import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';

const C = {
  bg:'#020912', bg2:'#050e1a', panel:'#0a1c2e',
  border:'rgba(0,180,255,0.12)', border2:'rgba(0,180,255,0.22)',
  text:'#c8dff0', dim:'#4a7a9b',
  cyan:'#00c8ff', green:'#00e87a', amber:'#ffc300', red:'#ff3d71', purple:'#a855f7', pink:'#ec4899',
};

const Badge = ({ label, color }) => (
  <span style={{ fontSize:10, fontWeight:700, letterSpacing:1, color, background:`${color}18`, border:`1px solid ${color}40`, borderRadius:4, padding:'2px 8px' }}>{label}</span>
);

const Btn = ({ children, onClick, color=C.cyan, outline=false, sm=false }) => (
  <button onClick={onClick} style={{ display:'inline-flex', alignItems:'center', gap:5,
    padding:sm?'5px 12px':'8px 16px', fontSize:sm?11:12, fontWeight:600, letterSpacing:0.8,
    borderRadius:7, cursor:'pointer', background:outline?'transparent':`${color}22`,
    border:`1px solid ${color}${outline?'60':'40'}`, color }}>{children}</button>
);

const inp = { width:'100%', background:'#020912cc', border:'1px solid rgba(0,180,255,0.22)', borderRadius:7, padding:'9px 12px', color:'#c8dff0', fontSize:12, outline:'none', boxSizing:'border-box' };

function StatCard({ label, value, sub, color, icon }) {
  return (
    <div style={{ flex:'1 1 160px', background:C.panel, border:`1px solid ${color}20`, borderRadius:12, padding:'18px 20px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
        <span style={{ fontSize:20 }}>{icon}</span>
        <span style={{ fontSize:10, color:C.dim, letterSpacing:1, textTransform:'uppercase' }}>{label}</span>
      </div>
      <div style={{ fontSize:24, fontWeight:700, color, fontFamily:"'Courier New',monospace" }}>{value}</div>
      {sub && <div style={{ fontSize:11, color:C.dim, marginTop:4 }}>{sub}</div>}
    </div>
  );
}

export default function AdminFinance() {
  const [stats, setStats]       = useState(null);
  const [txns, setTxns]         = useState([]);
  const [escrow, setEscrow]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [activeTab, setTab]     = useState('overview');
  const [txnFilter, setTxnFilter] = useState('');
  const [txnModal, setTxnModal] = useState(false);
  const [txnForm, setTxnForm]   = useState({ type:'commission', amount_usd:'', note:'', currency_code:'USD', balance_after:'0' });
  const [saving, setSaving]     = useState(false);
  const setF = (k,v) => setTxnForm(p=>({...p,[k]:v}));

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, overallRes, biddingRes, offerStatsRes] = await Promise.allSettled([
        client.get('/promotions/stats/'),
        client.get('/promotions/analytics/overall/'),
        client.get('/promotions/bidding/'),
        client.get('/offers/offers/stats/'),
      ]);
      const s = statsRes.status==='fulfilled' ? statsRes.value.data : {};
      const o = overallRes.status==='fulfilled' ? overallRes.value.data : {};
      const b = biddingRes.status==='fulfilled' ? biddingRes.value.data?.stats : {};
      const of = offerStatsRes.status==='fulfilled' ? offerStatsRes.value.data : {};
      setStats({ ...s, ...o, bidding: b, offers: of });
    } catch {}

    try {
      const res = await client.get('/promotions/transactions/', { params: { page_size: 50, ordering: '-created_at', ...(txnFilter ? { type: txnFilter } : {}) } });
      setTxns(res.data?.results ?? res.data ?? []);
    } catch {}

    try {
      const res = await client.get('/promotions/escrow/', { params: { page_size: 20 } });
      setEscrow(res.data?.results ?? res.data ?? []);
    } catch {}

    setLoading(false);
  }, [txnFilter]);

  useEffect(() => { fetch(); }, [fetch]);

  const createTxn = async () => {
    if (!txnForm.amount_usd || Number(txnForm.amount_usd) <= 0) return;
    setSaving(true);
    try {
      await client.post('/promotions/transactions/', {
        type:          txnForm.type,
        amount_usd:    Number(txnForm.amount_usd).toFixed(6),
        note:          txnForm.note,
        currency_code: txnForm.currency_code,
        balance_after: Number(txnForm.balance_after).toFixed(6),
      });
      setTxnModal(false);
      setTxnForm({ type:'commission', amount_usd:'', note:'', currency_code:'USD', balance_after:'0' });
      fetch();
    } catch(e) {
      alert(e?.response?.data?.detail ?? JSON.stringify(e?.response?.data) ?? 'Failed');
    }
    setSaving(false);
  };

  const deleteTxn = async (id) => {
    if (!window.confirm('Delete this transaction? This cannot be undone.')) return;
    try {
      await client.delete(`/promotions/transactions/${id}/`);
      setTxns(p => p.filter(t => t.id !== id));
    } catch(e) {
      alert(e?.response?.data?.detail ?? 'Delete failed — transactions may be protected');
    }
  };

  const txnTypeColor = t => ({ reward:C.green, commission:C.amber, bonus:C.cyan, referral:C.purple, penalty:C.red, deposit:C.green, withdrawal:C.red, refund:C.amber }[t] ?? C.dim);

  const TABS = ['overview', 'transactions', 'escrow'];

  return (
    <div style={{ minHeight:'100vh', background:`linear-gradient(135deg,${C.bg},${C.bg2})`, color:C.text, fontFamily:"'Segoe UI',sans-serif" }}>
      <style>{`@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}} *{box-sizing:border-box}`}</style>

      {/* Create Transaction Modal */}
      {txnModal && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center' }} onClick={()=>setTxnModal(false)}>
          <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,#050e1a,#0d0a20)`, border:`1px solid ${C.green}44`, borderRadius:14, padding:28, width:460 }}>
            <div style={{ fontSize:14, fontWeight:700, color:C.green, marginBottom:20 }}>💰 CREATE TRANSACTION</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>TYPE</div>
                <select value={txnForm.type} onChange={e=>setF('type',e.target.value)} style={inp}>
                  {['reward','commission','bonus','referral','penalty','deposit','withdrawal','refund'].map(t=>(
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>AMOUNT (USD)</div>
                <input style={inp} type="number" step="0.000001" value={txnForm.amount_usd} onChange={e=>setF('amount_usd',e.target.value)} placeholder="0.000000"/>
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>CURRENCY</div>
                <input style={inp} value={txnForm.currency_code} onChange={e=>setF('currency_code',e.target.value)} placeholder="USD"/>
              </div>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>BALANCE AFTER</div>
                <input style={inp} type="number" step="0.000001" value={txnForm.balance_after} onChange={e=>setF('balance_after',e.target.value)} placeholder="0.000000"/>
              </div>
            </div>
            <div style={{ marginBottom:14 }}>
              <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>NOTE</div>
              <input style={inp} value={txnForm.note} onChange={e=>setF('note',e.target.value)} placeholder="Transaction note (optional)"/>
            </div>
            <div style={{ display:'flex', gap:10, marginTop:8 }}>
              <Btn onClick={createTxn} color={C.green} disabled={saving} style={{ flex:1, justifyContent:'center' }}>{saving?'...':'CREATE'}</Btn>
              <Btn onClick={()=>setTxnModal(false)} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div style={{ padding:'24px 32px 0', borderBottom:`1px solid ${C.border}` }}>
        <div style={{ fontSize:22, fontWeight:800, letterSpacing:2, marginBottom:4 }}>
          <span style={{ color:C.green }}>FINANCE</span> DASHBOARD
        </div>
        <div style={{ fontSize:11, color:C.dim, letterSpacing:1, marginBottom:20 }}>Revenue · Commission · Escrow · Transactions</div>
        <div style={{ display:'flex', gap:2 }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding:'10px 20px', fontSize:12, fontWeight:600, letterSpacing:0.8, cursor:'pointer',
              border:'none', borderRadius:'8px 8px 0 0', background:activeTab===t?C.panel:'transparent',
              color:activeTab===t?C.green:C.dim, borderBottom:activeTab===t?`2px solid ${C.green}`:'2px solid transparent'
            }}>{t.charAt(0).toUpperCase()+t.slice(1)}</button>
          ))}
        </div>
      </div>

      <div style={{ padding:'28px 32px', animation:'fadeUp .25s ease' }} key={activeTab}>

        {/* OVERVIEW */}
        {activeTab==='overview' && (
          <>
            <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:24 }}>
              <StatCard label="Admin Commission" value={`$${Number(stats?.admin_commission||0).toFixed(2)}`} color={C.amber} icon="💰" sub="Total earned from tasks"/>
              <StatCard label="Total Budget" value={`$${Number(stats?.total_budget||0).toFixed(2)}`} color={C.cyan} icon="📊" sub="Advertiser deposits"/>
              <StatCard label="Total Spent" value={`$${Number(stats?.total_spent||0).toFixed(2)}`} color={C.purple} icon="💸" sub="Paid to workers"/>
              <StatCard label="Offer Revenue" value={`$${Number(stats?.offers?.total_revenue||0).toFixed(2)}`} color={C.green} icon="🎯" sub="Offerwall conversions"/>
              <StatCard label="Active Auctions" value={stats?.bidding?.active_auctions??0} color={C.pink} icon="⚡" sub="Pending bids"/>
              <StatCard label="Avg Bid" value={`$${Number(stats?.bidding?.avg_bid||0).toFixed(2)}`} color={C.amber} icon="🔨" sub="Won bids average"/>
            </div>

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
              <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, padding:'20px 22px' }}>
                <div style={{ fontSize:12, fontWeight:700, color:C.text, marginBottom:16, letterSpacing:1 }}>TASK PERFORMANCE</div>
                {[
                  { label:'Active Campaigns', val:stats?.active_count??0, color:C.green },
                  { label:'Paused Campaigns', val:stats?.paused_count??0, color:C.amber },
                  { label:'Users Engaged', val:stats?.users_engaged??0, color:C.cyan },
                  { label:'Pending Reviews', val:stats?.pending_submissions??0, color:C.amber },
                  { label:'Approved Tasks', val:stats?.approved_submissions??0, color:C.green },
                ].map(s => (
                  <div key={s.label} style={{ display:'flex', justifyContent:'space-between', padding:'8px 0', borderBottom:`1px solid ${C.border}` }}>
                    <span style={{ fontSize:12, color:C.dim }}>{s.label}</span>
                    <span style={{ fontSize:13, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>{s.val}</span>
                  </div>
                ))}
              </div>

              <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, padding:'20px 22px' }}>
                <div style={{ fontSize:12, fontWeight:700, color:C.text, marginBottom:16, letterSpacing:1 }}>OFFERWALL STATS</div>
                {[
                  { label:'Total Offers', val:stats?.offers?.total_offers??0, color:C.cyan },
                  { label:'Active Offers', val:stats?.offers?.active_offers??0, color:C.green },
                  { label:'Total Clicks', val:stats?.offers?.total_clicks??0, color:C.amber },
                  { label:'Total Conversions', val:stats?.offers?.total_conversions??0, color:C.purple },
                  { label:'Total Payout', val:`$${Number(stats?.offers?.total_payout||0).toFixed(2)}`, color:C.red },
                ].map(s => (
                  <div key={s.label} style={{ display:'flex', justifyContent:'space-between', padding:'8px 0', borderBottom:`1px solid ${C.border}` }}>
                    <span style={{ fontSize:12, color:C.dim }}>{s.label}</span>
                    <span style={{ fontSize:13, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>{s.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* TRANSACTIONS */}
        {activeTab==='transactions' && (
          <>
            <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
              {['','reward','commission','bonus','referral','penalty','deposit','withdrawal'].map(t => (
                <button key={t} onClick={() => setTxnFilter(t)} style={{
                  padding:'6px 14px', borderRadius:7, fontSize:11, fontWeight:600, cursor:'pointer',
                  background:txnFilter===t?`${C.cyan}22`:'transparent',
                  border:`1px solid ${txnFilter===t?C.cyan:C.border}`,
                  color:txnFilter===t?C.cyan:C.dim
                }}>{t || 'All'}</button>
              ))}
              <Btn onClick={fetch} outline sm>↺</Btn>
              <Btn onClick={()=>setTxnModal(true)} color={C.green} sm>+ Create Transaction</Btn>
            </div>

            {loading ? <div style={{ textAlign:'center', padding:'40px', color:C.dim }}>Loading...</div> : (
              <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:12, overflow:'hidden' }}>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                  <thead>
                    <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                      {['Type','Amount','User','Campaign','Balance After','Date',''].map(h => (
                        <th key={h} style={{ padding:'11px 14px', textAlign:'left', color:C.dim, fontSize:10, letterSpacing:1 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {txns.map((t,i) => (
                      <tr key={t.id} style={{ borderBottom:`1px solid ${C.border}`, background:i%2===0?'transparent':`${C.bg}44` }}>
                        <td style={{ padding:'10px 14px' }}><Badge label={t.type?.toUpperCase()} color={txnTypeColor(t.type)}/></td>
                        <td style={{ padding:'10px 14px', color:C.green, fontFamily:"'Courier New',monospace", fontWeight:700 }}>
                          ${Number(t.amount_usd||0).toFixed(4)}
                        </td>
                        <td style={{ padding:'10px 14px', color:C.dim, fontSize:11 }}>{t.user ?? '—'}</td>
                        <td style={{ padding:'10px 14px', color:C.dim, fontSize:11 }}>#{t.campaign ?? '—'}</td>
                        <td style={{ padding:'10px 14px', color:C.text, fontFamily:"'Courier New',monospace" }}>
                          ${Number(t.balance_after||0).toFixed(4)}
                        </td>
                        <td style={{ padding:'10px 14px', color:C.dim, fontSize:11 }}>
                          {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding:'10px 14px' }}>
                          <Btn onClick={()=>deleteTxn(t.id)} color={C.red} outline sm>🗑</Btn>
                        </td>
                      </tr>
                    ))}
                    {txns.length === 0 && (
                      <tr><td colSpan={6} style={{ padding:'40px', textAlign:'center', color:C.dim }}>No transactions found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ESCROW */}
        {activeTab==='escrow' && (
          <>
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:16 }}>
              <Btn onClick={fetch} outline sm>↺ Refresh</Btn>
            </div>
            {loading ? <div style={{ textAlign:'center', padding:'40px', color:C.dim }}>Loading...</div> : (
              <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                {escrow.map(e => {
                  const sc = e.status==='locked'?C.amber:e.status==='fully_released'?C.green:e.status==='refunded'?C.red:C.cyan;
                  return (
                    <div key={e.campaign} style={{ background:C.panel, border:`1px solid ${sc}22`, borderRadius:12, padding:'18px 22px', borderLeft:`3px solid ${sc}` }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                        <div>
                          <div style={{ fontSize:13, fontWeight:700, color:C.text }}>Campaign #{e.campaign}</div>
                          <div style={{ fontSize:11, color:C.dim, marginTop:2 }}>Locked: {e.locked_at ? new Date(e.locked_at).toLocaleDateString() : '—'}</div>
                        </div>
                        <Badge label={e.status?.toUpperCase().replace('_',' ')} color={sc}/>
                      </div>
                      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10 }}>
                        {[
                          { label:'Locked', val:`$${Number(e.locked_amount_usd||0).toFixed(2)}`, color:C.amber },
                          { label:'Released', val:`$${Number(e.released_amount_usd||0).toFixed(2)}`, color:C.green },
                          { label:'Remaining', val:`$${Number((e.locked_amount_usd||0)-(e.released_amount_usd||0)).toFixed(2)}`, color:C.cyan },
                        ].map(s => (
                          <div key={s.label} style={{ background:`${C.bg}88`, borderRadius:7, padding:'8px 12px', textAlign:'center' }}>
                            <div style={{ fontSize:9, color:C.dim, marginBottom:3 }}>{s.label}</div>
                            <div style={{ fontSize:15, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>{s.val}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {escrow.length === 0 && <div style={{ textAlign:'center', padding:'60px', color:C.dim }}>No escrow wallets found</div>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}