// src/pages/AdminSubmissions.jsx
// Admin: Review worker task submissions — approve / reject
import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';

const C = {
  bg:'#020912', bg2:'#050e1a', panel:'#0a1c2e',
  border:'rgba(0,180,255,0.12)', border2:'rgba(0,180,255,0.22)',
  text:'#c8dff0', dim:'#4a7a9b',
  cyan:'#00c8ff', green:'#00e87a', amber:'#ffc300', red:'#ff3d71', purple:'#a855f7',
};

const inp = { width:'100%', background:`${C.bg}cc`, border:`1px solid ${C.border2}`, borderRadius:7, padding:'9px 12px', color:C.text, fontSize:12, outline:'none', boxSizing:'border-box' };

function Toast({ toasts }) {
  return (
    <div style={{ position:'fixed', bottom:24, right:24, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
      {toasts.map(t => (
        <div key={t.id} style={{ padding:'11px 18px', borderRadius:8, fontSize:12, fontFamily:"'Courier New',monospace",
          background:t.type==='error'?`${C.red}18`:t.type==='warning'?`${C.amber}18`:`${C.green}18`,
          border:`1px solid ${t.type==='error'?C.red:t.type==='warning'?C.amber:C.green}44`,
          color:t.type==='error'?C.red:t.type==='warning'?C.amber:C.green }}>
          {t.type==='error'?'✗':t.type==='warning'?'⚠':'✓'} {t.msg}
        </div>
      ))}
    </div>
  );
}

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
    padding:sm?'5px 12px':'8px 16px', fontSize:sm?11:12, fontWeight:600, letterSpacing:0.8,
    borderRadius:7, cursor:disabled?'not-allowed':'pointer',
    background:outline?'transparent':`${color}22`, border:`1px solid ${color}${outline?'60':'40'}`,
    color, opacity:disabled?0.5:1 }}>{children}</button>
);

function RejectModal({ sub, onClose, onConfirm, loading }) {
  const [note, setNote] = useState('');
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center' }} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,${C.bg2},#0d0a20)`, border:`1px solid ${C.red}44`, borderRadius:14, padding:28, width:440 }}>
        <div style={{ fontSize:14, fontWeight:700, color:C.red, marginBottom:16 }}>✗ REJECT SUBMISSION</div>
        <div style={{ fontSize:12, color:C.dim, marginBottom:12 }}>
          Worker: <span style={{ color:C.text }}>{sub?.worker_username}</span> — Campaign: <span style={{ color:C.text }}>#{sub?.campaign}</span>
        </div>
        <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>REJECTION REASON (required)</div>
        <textarea value={note} onChange={e=>setNote(e.target.value)} rows={3}
          style={{ ...inp, resize:'vertical', marginBottom:16 }} placeholder="Explain why this is rejected..."/>
        <div style={{ display:'flex', gap:10 }}>
          <Btn onClick={() => note.trim().length >= 5 ? onConfirm(note) : null} color={C.red} disabled={loading || note.trim().length < 5}
            style={{ flex:1, justifyContent:'center' }}>
            {loading ? '...' : 'REJECT'}
          </Btn>
          <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
        </div>
        {note.trim().length > 0 && note.trim().length < 5 && (
          <div style={{ fontSize:11, color:C.amber, marginTop:8 }}>Reason must be at least 5 characters</div>
        )}
      </div>
    </div>
  );
}

function ProofViewer({ proofs }) {
  if (!proofs?.length) return <div style={{ color:C.dim, fontSize:11 }}>No proofs submitted</div>;
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
      {proofs.map((p, i) => (
        <div key={i} style={{ background:`${C.bg}88`, border:`1px solid ${C.border}`, borderRadius:7, padding:'10px 14px' }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
            <Badge label={p.proof_type?.toUpperCase()} color={C.cyan}/>
            <span style={{ fontSize:10, color:C.dim }}>Step {p.step}</span>
          </div>
          {p.proof_type === 'screenshot' || p.proof_type === 'video' ? (
            <a href={p.content} target="_blank" rel="noreferrer" style={{ color:C.cyan, fontSize:12, wordBreak:'break-all' }}>
              {p.content}
            </a>
          ) : p.proof_type === 'link' ? (
            <a href={p.content} target="_blank" rel="noreferrer" style={{ color:C.cyan, fontSize:12, wordBreak:'break-all' }}>
              {p.content}
            </a>
          ) : (
            <div style={{ fontSize:12, color:C.text }}>{p.content}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function AdminSubmissions() {
  const [subs, setSubs]             = useState([]);
  const [loading, setLoading]       = useState(true);
  const [filterStatus, setFilter]   = useState('pending');
  const [selected, setSelected]     = useState(null); // expanded row
  const [rejectTarget, setRejectTarget] = useState(null);
  const [acting, setActing]         = useState(null);
  const [stats, setStats]           = useState({ pending:0, approved:0, rejected:0 });
  const { toasts, push: toast }     = useToast();

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = filterStatus ? { status: filterStatus, ordering: '-submitted_at', page_size: 50 } : { ordering: '-submitted_at', page_size: 50 };
      const res = await client.get('/promotions/submissions/', { params });
      const data = res.data?.results ?? res.data ?? [];
      setSubs(data);
      // Stats
      const [p, a, r] = await Promise.all([
        client.get('/promotions/submissions/', { params: { status:'pending', page_size:1 } }),
        client.get('/promotions/submissions/', { params: { status:'approved', page_size:1 } }),
        client.get('/promotions/submissions/', { params: { status:'rejected', page_size:1 } }),
      ]);
      setStats({ pending: p.data?.count??0, approved: a.data?.count??0, rejected: r.data?.count??0 });
    } catch { toast('Failed to load submissions', 'error'); }
    finally { setLoading(false); }
  }, [filterStatus]);

  useEffect(() => { fetch(); }, [fetch]);

  const loadDetail = async (sub) => {
    if (selected?.id === sub.id) { setSelected(null); return; }
    try {
      const res = await client.get(`/promotions/submissions/${sub.id}/`);
      setSelected(res.data);
    } catch { setSelected(sub); }
  };

  const approve = async (id) => {
    setActing(id);
    try {
      await client.post(`/promotions/submissions/${id}/approve/`, { note: '' });
      toast('Submission approved — wallet credited!');
      fetch();
      if (selected?.id === id) setSelected(null);
    } catch(e) { toast(e?.response?.data?.detail ?? 'Approval failed', 'error'); }
    finally { setActing(null); }
  };

  const reject = async (note) => {
    if (!rejectTarget) return;
    setActing(rejectTarget.id);
    try {
      await client.post(`/promotions/submissions/${rejectTarget.id}/reject/`, { note });
      toast('Submission rejected');
      setRejectTarget(null);
      fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? 'Rejection failed', 'error'); }
    finally { setActing(null); }
  };

  const deleteSub = async (id) => {
    if (!window.confirm('Delete this submission permanently?')) return;
    try {
      await client.delete(`/promotions/submissions/${id}/`);
      toast('Submission deleted');
      if (selected?.id === id) setSelected(null);
      fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? 'Delete failed — submissions may be protected', 'error'); }
  };

  const statusColor = s => ({ pending:C.amber, approved:C.green, rejected:C.red, disputed:C.purple, expired:C.dim }[s] ?? C.dim);

  return (
    <div style={{ minHeight:'100vh', background:`linear-gradient(135deg,${C.bg},${C.bg2})`, color:C.text, fontFamily:"'Segoe UI',sans-serif", padding:'28px 32px' }}>
      <style>{`@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}} *{box-sizing:border-box}`}</style>
      <Toast toasts={toasts}/>
      {rejectTarget && <RejectModal sub={rejectTarget} onClose={()=>setRejectTarget(null)} onConfirm={reject} loading={!!acting}/>}

      <div style={{ marginBottom:24 }}>
        <div style={{ fontSize:22, fontWeight:800, letterSpacing:2, color:C.text }}>
          <span style={{ color:C.amber }}>SUBMISSION</span> REVIEW
        </div>
        <div style={{ fontSize:11, color:C.dim, letterSpacing:1 }}>Approve or reject worker task submissions</div>
      </div>

      {/* Stats */}
      <div style={{ display:'flex', gap:12, marginBottom:24, flexWrap:'wrap' }}>
        {[
          { label:'Pending Review', val:stats.pending, color:C.amber },
          { label:'Approved', val:stats.approved, color:C.green },
          { label:'Rejected', val:stats.rejected, color:C.red },
          { label:'Total Shown', val:subs.length, color:C.cyan },
        ].map(s => (
          <div key={s.label} style={{ flex:'1 1 140px', background:C.panel, border:`1px solid ${s.color}20`, borderRadius:10, padding:'14px 18px' }}>
            <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:6 }}>{s.label}</div>
            <div style={{ fontSize:24, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>{s.val}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        {[
          { val:'pending',  label:'Pending' },
          { val:'approved', label:'Approved' },
          { val:'rejected', label:'Rejected' },
          { val:'disputed', label:'Disputed' },
          { val:'',         label:'All' },
        ].map(f => (
          <button key={f.val} onClick={() => setFilter(f.val)} style={{
            padding:'7px 16px', borderRadius:7, fontSize:11, fontWeight:600, letterSpacing:0.8, cursor:'pointer',
            background:filterStatus===f.val?`${C.cyan}22`:'transparent',
            border:`1px solid ${filterStatus===f.val?C.cyan:C.border}`,
            color:filterStatus===f.val?C.cyan:C.dim
          }}>{f.label}</button>
        ))}
        <Btn onClick={fetch} outline sm>↺ Refresh</Btn>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.dim }}>Loading submissions...</div>
      ) : subs.length === 0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.dim }}>No submissions found</div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
          {subs.map(sub => {
            const sc = statusColor(sub.status);
            const isExpanded = selected?.id === sub.id;
            return (
              <div key={sub.id} style={{ background:C.panel, border:`1px solid ${sc}22`, borderRadius:12, overflow:'hidden', borderLeft:`3px solid ${sc}`, animation:'fadeUp .2s ease' }}>
                {/* Row */}
                <div onClick={() => loadDetail(sub)} style={{ display:'flex', alignItems:'center', gap:12, padding:'14px 18px', cursor:'pointer' }}>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13, fontWeight:700, color:C.text, marginBottom:3 }}>
                      {sub.worker_username ?? `Worker #${sub.worker}`}
                    </div>
                    <div style={{ fontSize:11, color:C.dim }}>
                      Campaign #{sub.campaign} · {sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : '—'}
                    </div>
                  </div>
                  <Badge label={sub.status?.toUpperCase()} color={sc}/>
                  <div style={{ textAlign:'right' }}>
                    <div style={{ fontSize:13, fontWeight:700, color:C.green, fontFamily:"'Courier New',monospace" }}>
                      ${Number(sub.reward_usd||0).toFixed(4)}
                    </div>
                    {Number(sub.bonus_usd||0) > 0 && (
                      <div style={{ fontSize:10, color:C.amber }}>+${Number(sub.bonus_usd).toFixed(4)} bonus</div>
                    )}
                  </div>
                  <span style={{ color:C.dim, fontSize:16 }}>{isExpanded ? '▲' : '▼'}</span>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div style={{ padding:'0 18px 18px', borderTop:`1px solid ${C.border}` }}>
                    <div style={{ marginTop:14, marginBottom:14 }}>
                      <div style={{ fontSize:11, color:C.dim, letterSpacing:1, marginBottom:8 }}>SUBMITTED PROOFS</div>
                      <ProofViewer proofs={selected?.proofs}/>
                    </div>
                    {selected?.review_note && (
                      <div style={{ background:`${C.red}10`, border:`1px solid ${C.red}30`, borderRadius:8, padding:'10px 14px', marginBottom:14 }}>
                        <div style={{ fontSize:10, color:C.red, letterSpacing:1, marginBottom:4 }}>REVIEW NOTE</div>
                        <div style={{ fontSize:12, color:C.text }}>{selected.review_note}</div>
                      </div>
                    )}
                    {sub.status === 'pending' && (
                      <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                        <Btn onClick={() => approve(sub.id)} color={C.green} disabled={acting===sub.id}>
                          {acting===sub.id ? '...' : '✓ Approve — Credit Wallet'}
                        </Btn>
                        <Btn onClick={() => setRejectTarget(sub)} color={C.red} outline disabled={acting===sub.id}>
                          ✗ Reject
                        </Btn>
                        <Btn onClick={() => deleteSub(sub.id)} color={C.dim} outline sm disabled={acting===sub.id}>
                          🗑 Delete
                        </Btn>
                      </div>
                    )}
                    {sub.status === 'disputed' && (
                      <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                        <Btn onClick={() => approve(sub.id)} color={C.green} disabled={acting===sub.id}>
                          ✓ Approve Dispute — Credit Wallet
                        </Btn>
                        <Btn onClick={() => setRejectTarget(sub)} color={C.red} outline disabled={acting===sub.id}>
                          ✗ Reject Dispute
                        </Btn>
                        <Btn onClick={() => deleteSub(sub.id)} color={C.dim} outline sm disabled={acting===sub.id}>
                          🗑 Delete
                        </Btn>
                      </div>
                    )}
                    {['approved','rejected','expired'].includes(sub.status) && (
                      <Btn onClick={() => deleteSub(sub.id)} color={C.dim} outline sm>
                        🗑 Delete Submission
                      </Btn>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}