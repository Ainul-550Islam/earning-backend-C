// src/pages/AdminDisputes.jsx
// Admin: Review and resolve worker disputes
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
    padding:sm?'5px 12px':'8px 16px', fontSize:sm?11:12, fontWeight:600, letterSpacing:0.8,
    borderRadius:7, cursor:disabled?'not-allowed':'pointer',
    background:outline?'transparent':`${color}22`, border:`1px solid ${color}${outline?'60':'40'}`,
    color, opacity:disabled?0.5:1 }}>{children}</button>
);

function ResolveModal({ dispute, onClose, onResolve, loading }) {
  const [decision, setDecision] = useState('');
  const [note, setNote]         = useState('');

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.8)', zIndex:9000, display:'flex', alignItems:'center', justifyContent:'center' }} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{ background:`linear-gradient(135deg,${C.bg2},#0d0a20)`, border:`1px solid ${C.purple}44`, borderRadius:14, padding:28, width:480 }}>
        <div style={{ fontSize:14, fontWeight:700, color:C.purple, marginBottom:4 }}>⚖ RESOLVE DISPUTE</div>
        <div style={{ fontSize:12, color:C.dim, marginBottom:16 }}>
          Worker: <span style={{ color:C.text }}>{dispute?.worker}</span>
        </div>

        <div style={{ background:`${C.bg}88`, border:`1px solid ${C.border}`, borderRadius:8, padding:'12px 14px', marginBottom:16 }}>
          <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:6 }}>WORKER'S REASON</div>
          <div style={{ fontSize:12, color:C.text }}>{dispute?.reason}</div>
          {dispute?.evidence_url && (
            <a href={dispute.evidence_url} target="_blank" rel="noreferrer" style={{ fontSize:11, color:C.cyan, marginTop:6, display:'block' }}>
              View Evidence →
            </a>
          )}
        </div>

        <div style={{ display:'flex', gap:10, marginBottom:14 }}>
          {[
            { val:'approved', label:'Approve — Pay Worker', color:C.green },
            { val:'rejected', label:'Reject — Deny Dispute', color:C.red },
          ].map(d => (
            <button key={d.val} onClick={() => setDecision(d.val)} style={{
              flex:1, padding:'10px 0', borderRadius:8, fontSize:12, fontWeight:600, cursor:'pointer',
              background:decision===d.val?`${d.color}22`:'transparent',
              border:`1px solid ${decision===d.val?d.color:C.border}`,
              color:decision===d.val?d.color:C.dim
            }}>{d.label}</button>
          ))}
        </div>

        <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:5 }}>ADMIN NOTE (optional)</div>
        <textarea value={note} onChange={e=>setNote(e.target.value)} rows={2}
          style={{ ...inp, resize:'vertical', marginBottom:16 }} placeholder="Reason for your decision..."/>

        <div style={{ display:'flex', gap:10 }}>
          <Btn onClick={() => decision && onResolve(decision, note)} color={decision==='approved'?C.green:C.red}
            disabled={!decision || loading} style={{ flex:1, justifyContent:'center' }}>
            {loading ? '...' : 'CONFIRM DECISION'}
          </Btn>
          <Btn onClick={onClose} outline style={{ flex:1, justifyContent:'center' }}>CANCEL</Btn>
        </div>
      </div>
    </div>
  );
}

export default function AdminDisputes() {
  const [disputes, setDisputes]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [filterStatus, setFilter] = useState('open');
  const [resolveTarget, setResolveTarget] = useState(null);
  const [acting, setActing]       = useState(null);
  const { toasts, push: toast }   = useToast();

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = { ordering: '-created_at', page_size: 50, ...(filterStatus ? { status: filterStatus } : {}) };
      const res = await client.get('/promotions/disputes/', { params });
      setDisputes(res.data?.results ?? res.data ?? []);
    } catch { toast('Failed to load disputes', 'error'); }
    finally { setLoading(false); }
  }, [filterStatus]);

  useEffect(() => { fetch(); }, [fetch]);

  const resolve = async (decision, note) => {
    if (!resolveTarget) return;
    setActing(resolveTarget.id);
    try {
      await client.post(`/promotions/disputes/${resolveTarget.id}/resolve/`, { decision, admin_note: note });
      toast(decision === 'approved' ? 'Dispute approved — worker paid!' : 'Dispute rejected');
      setResolveTarget(null);
      fetch();
    } catch(e) { toast(e?.response?.data?.detail ?? 'Resolve failed', 'error'); }
    finally { setActing(null); }
  };

  const deleteDispute = async (id) => {
    if (!window.confirm('Delete this dispute permanently?')) return;
    try {
      await client.delete(`/promotions/disputes/${id}/`);
      setDisputes(p => p.filter(d => d.id !== id));
      toast('Dispute deleted');
    } catch(e) { toast(e?.response?.data?.detail ?? 'Delete failed', 'error'); }
  };

  const markUnderReview = async (id) => {
    try {
      await client.patch(`/promotions/disputes/${id}/`, { status: 'under_review' });
      setDisputes(p => p.map(d => d.id === id ? {...d, status:'under_review'} : d));
      toast('Marked as Under Review');
    } catch(e) { toast(e?.response?.data?.detail ?? 'Update failed', 'error'); }
  };

  const statusColor = s => ({
    open:'#ffc300', under_review:'#00c8ff',
    resolved_approved:'#00e87a', resolved_rejected:'#ff3d71'
  }[s] ?? C.dim);

  const statusLabel = s => ({
    open:'OPEN', under_review:'REVIEWING',
    resolved_approved:'APPROVED', resolved_rejected:'REJECTED'
  }[s] ?? s?.toUpperCase());

  return (
    <div style={{ minHeight:'100vh', background:`linear-gradient(135deg,${C.bg},${C.bg2})`, color:C.text, fontFamily:"'Segoe UI',sans-serif", padding:'28px 32px' }}>
      <style>{`@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}} *{box-sizing:border-box}`}</style>

      {/* Toast */}
      <div style={{ position:'fixed', bottom:24, right:24, zIndex:9999, display:'flex', flexDirection:'column', gap:8 }}>
        {toasts.map(t => (
          <div key={t.id} style={{ padding:'11px 18px', borderRadius:8, fontSize:12, fontFamily:"'Courier New',monospace",
            background:t.type==='error'?`${C.red}18`:`${C.green}18`,
            border:`1px solid ${t.type==='error'?C.red:C.green}44`,
            color:t.type==='error'?C.red:C.green }}>
            {t.type==='error'?'✗':'✓'} {t.msg}
          </div>
        ))}
      </div>

      {resolveTarget && <ResolveModal dispute={resolveTarget} onClose={() => setResolveTarget(null)} onResolve={resolve} loading={!!acting}/>}

      <div style={{ marginBottom:24 }}>
        <div style={{ fontSize:22, fontWeight:800, letterSpacing:2, color:C.text }}>
          <span style={{ color:C.purple }}>DISPUTE</span> REVIEW
        </div>
        <div style={{ fontSize:11, color:C.dim, letterSpacing:1 }}>Worker appeals on rejected submissions</div>
      </div>

      {/* Stats */}
      <div style={{ display:'flex', gap:12, marginBottom:24 }}>
        {[
          { label:'Open', color:C.amber, filter:'open' },
          { label:'Under Review', color:C.cyan, filter:'under_review' },
          { label:'Approved', color:C.green, filter:'resolved_approved' },
          { label:'Rejected', color:C.red, filter:'resolved_rejected' },
        ].map(s => (
          <div key={s.label} onClick={() => setFilter(s.filter)} style={{ flex:1, background:C.panel, border:`1px solid ${s.color}${filterStatus===s.filter?'60':'20'}`, borderRadius:10, padding:'14px 18px', cursor:'pointer' }}>
            <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:6 }}>{s.label}</div>
            <div style={{ fontSize:20, fontWeight:700, color:s.color, fontFamily:"'Courier New',monospace" }}>
              {disputes.filter(d => d.status === s.filter).length}
            </div>
          </div>
        ))}
      </div>

      {/* Filter + refresh */}
      <div style={{ display:'flex', gap:8, marginBottom:16, alignItems:'center' }}>
        {[{val:'open',label:'Open'},{val:'under_review',label:'Reviewing'},{val:'',label:'All'}].map(f => (
          <button key={f.val} onClick={() => setFilter(f.val)} style={{
            padding:'7px 14px', borderRadius:7, fontSize:11, fontWeight:600, cursor:'pointer',
            background:filterStatus===f.val?`${C.purple}22`:'transparent',
            border:`1px solid ${filterStatus===f.val?C.purple:C.border}`,
            color:filterStatus===f.val?C.purple:C.dim
          }}>{f.label}</button>
        ))}
        <Btn onClick={fetch} outline sm>↺</Btn>
      </div>

      {/* List */}
      {loading ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.dim }}>Loading...</div>
      ) : disputes.length === 0 ? (
        <div style={{ textAlign:'center', padding:'60px 0', color:C.dim }}>No disputes found</div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
          {disputes.map(d => {
            const sc = statusColor(d.status);
            return (
              <div key={d.id} style={{ background:C.panel, border:`1px solid ${sc}22`, borderRadius:12, padding:'18px 22px', borderLeft:`3px solid ${sc}`, animation:'fadeUp .2s ease' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
                  <div>
                    <div style={{ fontSize:13, fontWeight:700, color:C.text, marginBottom:3 }}>
                      Submission #{d.submission}
                    </div>
                    <div style={{ fontSize:11, color:C.dim }}>
                      Filed: {d.created_at ? new Date(d.created_at).toLocaleString() : '—'}
                    </div>
                  </div>
                  <Badge label={statusLabel(d.status)} color={sc}/>
                </div>

                <div style={{ background:`${C.bg}88`, border:`1px solid ${C.border}`, borderRadius:8, padding:'10px 14px', marginBottom:12 }}>
                  <div style={{ fontSize:10, color:C.dim, letterSpacing:1, marginBottom:4 }}>WORKER'S REASON</div>
                  <div style={{ fontSize:12, color:C.text }}>{d.reason}</div>
                  {d.evidence_url && (
                    <a href={d.evidence_url} target="_blank" rel="noreferrer" style={{ fontSize:11, color:C.cyan, marginTop:6, display:'block' }}>View Evidence →</a>
                  )}
                </div>

                {d.admin_note && (
                  <div style={{ fontSize:11, color:C.dim, marginBottom:12 }}>
                    Admin note: <span style={{ color:C.text }}>{d.admin_note}</span>
                  </div>
                )}

                <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                  {(d.status === 'open' || d.status === 'under_review') && (
                    <Btn onClick={() => setResolveTarget(d)} color={C.purple} disabled={acting===d.id}>
                      ⚖ Resolve Dispute
                    </Btn>
                  )}
                  {d.status === 'open' && (
                    <Btn onClick={() => markUnderReview(d.id)} color={C.cyan} outline sm>
                      👁 Mark Reviewing
                    </Btn>
                  )}
                  <Btn onClick={() => deleteDispute(d.id)} color={C.red} outline sm>
                    🗑 Delete
                  </Btn>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}