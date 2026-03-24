// src/pages/KYCPage.jsx  ── 100% COMPLETE CRUD
import React, { useState, useEffect, useRef, useCallback } from 'react';
import client from '../api/client';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

const THEMES = [
  { name:"OCEAN COMMAND",   p:"#00d4ff", bg:"#010810", bgC:"#020c18", bgP:"#030f1e", b:"#00d4ff22", bs:"#00d4ff55", t:"#cce8ff", tm:"#4a7a99", g:"#00d4ff40", gr:"linear-gradient(135deg,#00d4ff15,#0099cc08)", sl:"#00d4ff08" },
  { name:"EMERALD PROTOCOL",p:"#00ff88", bg:"#010a05", bgC:"#020f07", bgP:"#031208", b:"#00ff8822", bs:"#00ff8855", t:"#ccffe8", tm:"#5a9970", g:"#00ff8840", gr:"linear-gradient(135deg,#00ff8815,#00cc6a08)", sl:"#00ff8808" },
  { name:"CRIMSON FORCE",   p:"#ff2244", bg:"#0a0102", bgC:"#120204", bgP:"#180306", b:"#ff224422", bs:"#ff224455", t:"#ffcccc", tm:"#994455", g:"#ff224440", gr:"linear-gradient(135deg,#ff224415,#cc003308)", sl:"#ff224408" },
  { name:"GOLDEN INTEL",    p:"#ffcc00", bg:"#0a0800", bgC:"#120e00", bgP:"#181200", b:"#ffcc0022", bs:"#ffcc0055", t:"#fff5cc", tm:"#997744", g:"#ffcc0040", gr:"linear-gradient(135deg,#ffcc0015,#cc990008)", sl:"#ffcc0008" },
  { name:"VIOLET CIPHER",   p:"#bb44ff", bg:"#060008", bgC:"#0a000f", bgP:"#0e0015", b:"#bb44ff22", bs:"#bb44ff55", t:"#f0ccff", tm:"#7744aa", g:"#bb44ff40", gr:"linear-gradient(135deg,#bb44ff15,#8822cc08)", sl:"#bb44ff08" },
];

const Icon = ({ d, size=14, stroke=2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"><path d={d}/></svg>
);
const IC = {
  shield:  "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  check:   "M20 6L9 17l-5-5",
  x:       "M18 6L6 18 M6 6l12 12",
  clock:   "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
  alert:   "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
  eye:     "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  search:  "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  refresh: "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  file:    "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6",
  upload:  "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
  trash:   "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
  reset:   "M1 4v6h6 M23 20v-6h-6 M20.49 9A9 9 0 0 0 5.64 5.64L1 10 M23 14l-4.64 4.36A9 9 0 0 1 3.51 15",
  note:    "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  img:     "M21 3H3v18h18V3z M8.5 8.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M21 15l-5-5L5 20",
  chevL:   "M15 18l-6-6 6-6",
  chevR:   "M9 18l6-6-6-6",
  sq:      "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  sqOk:    "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  approve: "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3",
  reject:  "M10 15l-3-3m0 0l3-3m-3 3h8 M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0",
  edit:    "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  down:    "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  log:     "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M16 13H8 M16 17H8 M10 9H8",
  stats:   "M18 20V10 M12 20V4 M6 20v-6",
  risk:    "M12 9v4 M12 17h.01 M5.07 19H19a2 2 0 0 0 1.75-2.96l-7-12a2 2 0 0 0-3.5 0l-7 12A2 2 0 0 0 5.07 19z",
};

const SC = {
  verified:      { c:"#00ff88", l:"VERIFIED" },
  pending:       { c:"#ffcc00", l:"PENDING" },
  rejected:      { c:"#ff2244", l:"REJECTED" },
  not_submitted: { c:"#667788", l:"NOT SUBMITTED" },
  expired:       { c:"#ff6600", l:"EXPIRED" },
};

const imgSrc = p => p ? (p.startsWith('http') ? p : `http://127.0.0.1:8000${p}`) : null;
const riskC  = s => s > 60 ? '#ff2244' : s > 30 ? '#ffcc00' : '#00ff88';
const fmtD   = d => d ? d.slice(0,16).replace('T',' ') : '—';

const Spin = () => <span style={{ display:'inline-block',width:12,height:12,border:'2px solid currentColor',borderTopColor:'transparent',borderRadius:'50%',animation:'kspin 1s linear infinite' }}/>;

function useToast() {
  const [list, setList] = useState([]);
  const add = useCallback((msg, type='ok') => {
    const id = Date.now();
    setList(p => [...p, { id, msg, type }]);
    setTimeout(() => setList(p => p.filter(t => t.id !== id)), 3400);
  }, []);
  return { list, add };
}

const Toasts = ({ list }) => (
  <div style={{ position:'fixed',bottom:20,right:20,zIndex:9999,display:'flex',flexDirection:'column',gap:8 }}>
    {list.map(t => {
      const c = t.type==='err'?'#ff2244':t.type==='warn'?'#ffcc00':'#00ff88';
      return <div key={t.id} style={{ padding:'10px 16px',borderRadius:8,background:`${c}18`,border:`1px solid ${c}44`,color:c,fontSize:12,fontFamily:"'Courier New',monospace",backdropFilter:'blur(8px)',animation:'kfadeUp .3s ease',display:'flex',alignItems:'center',gap:8,maxWidth:320 }}>{t.type==='err'?'✗':t.type==='warn'?'⚠':'✓'} {t.msg}</div>;
    })}
  </div>
);

const Badge = ({ status }) => {
  const s = SC[status] || SC.not_submitted;
  return <span style={{ display:'inline-flex',alignItems:'center',gap:5,color:s.c,background:`${s.c}15`,border:`1px solid ${s.c}44`,borderRadius:20,padding:'3px 9px',fontSize:10,fontWeight:700,fontFamily:"'Courier New',monospace",letterSpacing:'.08em',whiteSpace:'nowrap' }}><span style={{ width:5,height:5,borderRadius:'50%',background:s.c,display:'inline-block' }}/>{s.l}</span>;
};

const SK = ({ w='100%', h=12 }) => <div style={{ width:w,height:h,borderRadius:4,background:'linear-gradient(90deg,#0d2137 25%,#1a3a5c44 50%,#0d2137 75%)',backgroundSize:'200% 100%',animation:'kshimmer 1.5s infinite' }}/>;

const StatCard = ({ label, value, icon, color, loading, t, onClick, active }) => (
  <div onClick={onClick} style={{ background:active?`${color}14`:t.bgC,border:`1px solid ${active?color+'44':color+'33'}`,borderTop:`2px solid ${color}`,borderRadius:10,padding:'16px 18px',position:'relative',overflow:'hidden',cursor:onClick?'pointer':'default',transition:'all .2s',boxShadow:active?`0 0 20px ${color}20`:'none' }}>
    <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:8 }}>
      <span style={{ color }}><Icon d={icon} size={13}/></span>
      <span style={{ color:t.tm,fontSize:10,fontWeight:700,letterSpacing:'.1em',fontFamily:"'Courier New',monospace" }}>{label}</span>
    </div>
    {loading ? <SK h={24} w={60}/> : <div style={{ fontSize:26,fontWeight:900,color,fontFamily:"'Courier New',monospace",textShadow:`0 0 20px ${color}60` }}>{value??'—'}</div>}
    <div style={{ position:'absolute',top:-15,right:-15,width:60,height:60,borderRadius:'50%',background:color,opacity:.06,filter:'blur(10px)' }}/>
  </div>
);

const ABtn = ({ icon, label, color, onClick, loading, small=false, disabled=false }) => (
  <button onClick={onClick} disabled={loading||disabled}
    style={{ background:`${color}16`,border:`1px solid ${color}33`,borderRadius:6,padding:small?'5px 9px':'8px 14px',color,fontSize:10,fontWeight:700,cursor:(loading||disabled)?'not-allowed':'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',gap:5,transition:'all .2s',opacity:(loading||disabled)?.6:1,whiteSpace:'nowrap' }}
    onMouseEnter={e=>{ if(!loading&&!disabled) e.currentTarget.style.background=`${color}2c`; }}
    onMouseLeave={e=>e.currentTarget.style.background=`${color}16`}>
    {loading?<Spin/>:<Icon d={icon} size={11}/>} {label}
  </button>
);

const Confirm = ({ title='CONFIRM', msg, onOk, onNo, loading, okLabel='DELETE', okColor='#ff2244', t }) => (
  <div style={{ position:'fixed',inset:0,zIndex:1002,background:'#000b',backdropFilter:'blur(6px)',display:'flex',alignItems:'center',justifyContent:'center' }}>
    <div style={{ background:t.bgC,border:`1px solid ${okColor}44`,borderRadius:12,padding:24,width:360,maxWidth:'94vw',animation:'kfadeUp .2s ease' }}>
      <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:14 }}>
        <div style={{ width:34,height:34,borderRadius:9,background:`${okColor}20`,display:'flex',alignItems:'center',justifyContent:'center' }}><Icon d={IC.alert} size={16}/></div>
        <span style={{ fontSize:13,fontWeight:700,color:t.t,fontFamily:"'Courier New',monospace" }}>{title}</span>
      </div>
      <p style={{ fontSize:12,color:'#aab',marginBottom:20,lineHeight:1.7,fontFamily:"'Courier New',monospace" }}>{msg}</p>
      <div style={{ display:'flex',gap:10 }}>
        <button onClick={onNo} style={{ flex:1,background:t.b,border:`1px solid ${t.bs}`,borderRadius:8,padding:10,color:t.tm,fontSize:11,cursor:'pointer',fontFamily:"'Courier New',monospace" }}>CANCEL</button>
        <button onClick={onOk} disabled={loading} style={{ flex:1,background:`${okColor}20`,border:`1px solid ${okColor}55`,borderRadius:8,padding:10,color:okColor,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',justifyContent:'center',gap:6 }}>
          {loading?<Spin/>:null} {okLabel}
        </button>
      </div>
    </div>
  </div>
);

const FileUp = ({ label, name, value, existingUrl, onChange, t }) => {
  const ref = useRef();
  const preview = value ? URL.createObjectURL(value) : imgSrc(existingUrl);
  return (
    <div>
      <div style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:5 }}>{label}</div>
      <div onClick={()=>ref.current.click()} style={{ border:`2px dashed ${value?t.bs:t.b}`,borderRadius:8,padding:'10px 8px',cursor:'pointer',textAlign:'center',background:value?`${t.p}08`:t.bgP,transition:'all .2s',minHeight:80,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center' }}
        onMouseEnter={e=>e.currentTarget.style.borderColor=t.bs}
        onMouseLeave={e=>e.currentTarget.style.borderColor=value?t.bs:t.b}>
        {preview
          ? <img src={preview} alt={label} style={{ maxHeight:70,maxWidth:'100%',borderRadius:6,objectFit:'cover' }}/>
          : <><div style={{ color:t.tm }}><Icon d={IC.upload} size={16}/></div><div style={{ fontSize:9,color:t.tm,fontFamily:"'Courier New',monospace",marginTop:3 }}>UPLOAD</div></>}
        <input ref={ref} type="file" accept="image/*" style={{ display:'none' }} onChange={e=>onChange(name,e.target.files[0])}/>
      </div>
    </div>
  );
};

const mkINP = t => ({ width:'100%',background:t.bgP,border:`1px solid ${t.b}`,borderRadius:8,padding:'9px 12px',color:t.t,fontSize:12,outline:'none',boxSizing:'border-box',fontFamily:"'Courier New',monospace",resize:'vertical' });
const LBL = ({ label, t }) => <div style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:5 }}>{label}</div>;
const SEC = ({ title, t, children }) => (
  <div style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:10,padding:'15px 17px',marginBottom:14 }}>
    <div style={{ fontSize:10,fontWeight:700,color:t.p,letterSpacing:'.12em',fontFamily:"'Courier New',monospace",marginBottom:13,display:'flex',alignItems:'center',gap:8 }}>
      <div style={{ width:3,height:12,background:t.p,borderRadius:2 }}/>{title}
    </div>
    {children}
  </div>
);

// ─── KYC SUBMIT FORM (USER) ───────────────────────────────────────────────────
const KYCForm = ({ existing, onDone, toast, t }) => {
  const [form, setForm] = useState({
    full_name:existing?.full_name||'', date_of_birth:existing?.date_of_birth||'',
    phone_number:existing?.phone_number||'', payment_number:existing?.payment_number||'',
    payment_method:existing?.payment_method||'bkash',
    address_line:existing?.address_line||'', city:existing?.city||'',
    country:existing?.country||'Bangladesh',
    document_type:existing?.document_type||'nid', document_number:existing?.document_number||'',
  });
  const [files, setFiles] = useState({ document_front:null,document_back:null,selfie_photo:null });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const INP = mkINP(t);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));
  const inp = (k,ph,type='text') => <input type={type} value={form[k]} placeholder={ph} onChange={e=>set(k,e.target.value)} style={INP} onFocus={e=>e.target.style.borderColor=t.bs} onBlur={e=>e.target.style.borderColor=t.b}/>;
  const sel = (k,opts) => <select value={form[k]} onChange={e=>set(k,e.target.value)} style={INP}>{opts.map(o=><option key={o.v} value={o.v}>{o.l}</option>)}</select>;

  const submit = async () => {
    if (!form.full_name||!form.phone_number||!form.payment_number) { toast('Name, phone & payment দাও','err'); return; }
    setSaving(true);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k,v])=>fd.append(k,v));
      Object.entries(files).forEach(([k,v])=>{ if(v) fd.append(k,v); });
      await client.post('/kyc/submit/', fd, { headers:{'Content-Type':'multipart/form-data'} });
      toast(existing?'KYC updated ✓':'KYC submitted ✓'); onDone();
    } catch(e) {
      const d = e?.response?.data;
      toast(d?.errors?Object.values(d.errors).flat().join(', '):d?.error||'Submit failed','err');
    } finally { setSaving(false); }
  };

  const doDelete = async () => {
    setDeleting(true);
    try { await client.delete('/kyc/submit/'); toast('KYC deleted'); onDone(); }
    catch { toast('Delete failed','err'); }
    finally { setDeleting(false); setConfirmDel(false); }
  };

  return (
    <div style={{ animation:'kfadeUp .3s ease',marginBottom:16 }}>
      <SEC title="PERSONAL INFO" t={t}>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12 }}>
          <div><LBL label="FULL NAME *" t={t}/>{inp('full_name','Legal full name')}</div>
          <div><LBL label="DATE OF BIRTH" t={t}/>{inp('date_of_birth','','date')}</div>
        </div>
      </SEC>
      <SEC title="CONTACT & PAYMENT" t={t}>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12 }}>
          <div><LBL label="PHONE *" t={t}/>{inp('phone_number','01XXXXXXXXX')}</div>
          <div><LBL label="METHOD" t={t}/>{sel('payment_method',[{v:'bkash',l:'bKash'},{v:'nagad',l:'Nagad'},{v:'rocket',l:'Rocket'}])}</div>
          <div style={{ gridColumn:'1/-1' }}><LBL label="PAYMENT NUMBER *" t={t}/>{inp('payment_number','01XXXXXXXXX')}</div>
        </div>
      </SEC>
      <SEC title="ADDRESS" t={t}>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12 }}>
          <div style={{ gridColumn:'1/-1' }}><LBL label="ADDRESS" t={t}/>{inp('address_line','Street, Area')}</div>
          <div><LBL label="CITY" t={t}/>{inp('city','City')}</div>
          <div><LBL label="COUNTRY" t={t}/>{inp('country','Country')}</div>
        </div>
      </SEC>
      <SEC title="IDENTITY DOCUMENT" t={t}>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:14 }}>
          <div><LBL label="TYPE" t={t}/>{sel('document_type',[{v:'nid',l:'National ID'},{v:'passport',l:'Passport'},{v:'driving_license',l:'Driving License'}])}</div>
          <div><LBL label="NUMBER" t={t}/>{inp('document_number','Doc number')}</div>
        </div>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:12 }}>
          <FileUp label="FRONT *"  name="document_front" value={files.document_front} existingUrl={existing?.document_front} onChange={(n,f)=>setFiles(p=>({...p,[n]:f}))} t={t}/>
          <FileUp label="BACK"     name="document_back"  value={files.document_back}  existingUrl={existing?.document_back}  onChange={(n,f)=>setFiles(p=>({...p,[n]:f}))} t={t}/>
          <FileUp label="SELFIE *" name="selfie_photo"   value={files.selfie_photo}   existingUrl={existing?.selfie_photo}   onChange={(n,f)=>setFiles(p=>({...p,[n]:f}))} t={t}/>
        </div>
      </SEC>
      <div style={{ display:'flex',gap:10 }}>
        <button onClick={submit} disabled={saving} style={{ flex:1,background:t.gr,border:`1px solid ${t.bs}`,borderRadius:10,padding:13,color:t.p,fontSize:12,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',justifyContent:'center',gap:10 }}>
          {saving?<Spin/>:<Icon d={IC.upload} size={14}/>} {saving?'SUBMITTING…':existing?'UPDATE & RESUBMIT':'SUBMIT KYC'}
        </button>
        {existing && (
          <button onClick={()=>setConfirmDel(true)} style={{ background:'#ff224416',border:'1px solid #ff224433',borderRadius:10,padding:'13px 18px',color:'#ff2244',fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',gap:6 }}>
            <Icon d={IC.trash} size={12}/> DELETE
          </button>
        )}
      </div>
      {confirmDel && <Confirm title="DELETE KYC" msg={`"${existing?.full_name}" এর KYC সম্পূর্ণ মুছে যাবে।`} onOk={doDelete} onNo={()=>setConfirmDel(false)} loading={deleting} okLabel="DELETE" okColor="#ff2244" t={t}/>}
    </div>
  );
};

// ─── ADMIN EDIT MODAL ─────────────────────────────────────────────────────────
const EditModal = ({ kyc, onClose, onRefresh, toast, t }) => {
  const [form, setForm] = useState({
    full_name:kyc.full_name||'', date_of_birth:kyc.date_of_birth||'',
    phone_number:kyc.phone_number||'', payment_number:kyc.payment_number||'',
    payment_method:kyc.payment_method||'bkash',
    address_line:kyc.address_line||'', city:kyc.city||'', country:kyc.country||'Bangladesh',
    document_type:kyc.document_type||'nid', document_number:kyc.document_number||'',
    admin_notes:kyc.admin_notes||'',
  });
  const [saving, setSaving] = useState(false);
  const INP = mkINP(t);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));
  const inp = (k,ph,type='text') => <input type={type} value={form[k]} placeholder={ph} onChange={e=>set(k,e.target.value)} style={INP} onFocus={e=>e.target.style.borderColor=t.bs} onBlur={e=>e.target.style.borderColor=t.b}/>;
  const sel = (k,opts) => <select value={form[k]} onChange={e=>set(k,e.target.value)} style={INP}>{opts.map(o=><option key={o.v} value={o.v}>{o.l}</option>)}</select>;

  const save = async () => {
    setSaving(true);
    try {
      await client.patch(`/kyc/admin/review/${kyc.id}/`, form);
      toast('KYC updated ✓'); onRefresh(); onClose();
    } catch(e) { toast(e?.response?.data?.error||'Update failed','err'); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ position:'fixed',inset:0,zIndex:1001,background:'#000c',backdropFilter:'blur(8px)',display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:t.bgC,border:`1px solid ${t.bs}`,borderRadius:14,padding:26,width:620,maxWidth:'96vw',maxHeight:'90vh',overflowY:'auto',boxShadow:`0 24px 80px ${t.g}`,animation:'kfadeUp .3s ease' }}>
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20 }}>
          <div style={{ display:'flex',alignItems:'center',gap:10 }}>
            <span style={{ color:t.p }}><Icon d={IC.edit} size={18}/></span>
            <div>
              <div style={{ fontSize:14,fontWeight:800,color:t.t,fontFamily:"'Courier New',monospace" }}>EDIT KYC #{kyc.id}</div>
              <div style={{ fontSize:11,color:t.tm }}>{kyc.full_name}</div>
            </div>
          </div>
          <button onClick={onClose} style={{ background:'none',border:'none',cursor:'pointer',color:t.tm }}><Icon d={IC.x} size={18}/></button>
        </div>
        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12 }}>
          <div><LBL label="FULL NAME" t={t}/>{inp('full_name','Full name')}</div>
          <div><LBL label="DATE OF BIRTH" t={t}/>{inp('date_of_birth','','date')}</div>
          <div><LBL label="PHONE" t={t}/>{inp('phone_number','01XXXXXXXXX')}</div>
          <div><LBL label="PAYMENT NUMBER" t={t}/>{inp('payment_number','01XXXXXXXXX')}</div>
          <div><LBL label="PAYMENT METHOD" t={t}/>{sel('payment_method',[{v:'bkash',l:'bKash'},{v:'nagad',l:'Nagad'},{v:'rocket',l:'Rocket'}])}</div>
          <div><LBL label="DOCUMENT TYPE" t={t}/>{sel('document_type',[{v:'nid',l:'National ID'},{v:'passport',l:'Passport'},{v:'driving_license',l:'Driving License'}])}</div>
          <div><LBL label="DOCUMENT NUMBER" t={t}/>{inp('document_number','Doc number')}</div>
          <div><LBL label="CITY" t={t}/>{inp('city','City')}</div>
          <div style={{ gridColumn:'1/-1' }}><LBL label="ADDRESS" t={t}/>{inp('address_line','Address')}</div>
          <div style={{ gridColumn:'1/-1' }}>
            <LBL label="ADMIN NOTES" t={t}/>
            <textarea value={form.admin_notes} onChange={e=>set('admin_notes',e.target.value)} rows={3} placeholder="Internal notes…" style={{ ...INP,resize:'vertical' }} onFocus={e=>e.target.style.borderColor=t.bs} onBlur={e=>e.target.style.borderColor=t.b}/>
          </div>
        </div>
        <div style={{ display:'flex',gap:10 }}>
          <button onClick={onClose} style={{ flex:1,background:t.b,border:`1px solid ${t.bs}`,borderRadius:8,padding:11,color:t.tm,fontSize:11,cursor:'pointer',fontFamily:"'Courier New',monospace" }}>CANCEL</button>
          <button onClick={save} disabled={saving} style={{ flex:2,background:`${t.p}16`,border:`1px solid ${t.bs}`,borderRadius:8,padding:11,color:t.p,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',justifyContent:'center',gap:8 }}>
            {saving?<Spin/>:<Icon d={IC.check} size={12}/>} {saving?'SAVING…':'SAVE CHANGES'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── REVIEW MODAL (ADMIN) ─────────────────────────────────────────────────────
const ReviewModal = ({ kyc:kycProp, onClose, onRefresh, toast, t }) => {
  const [kyc, setKyc]   = useState(kycProp);
  const [tab, setTab]   = useState('info');
  const [action, setAction] = useState('verified');
  const [reason, setReason] = useState('');
  const [notes, setNotes]   = useState(kycProp.admin_notes||'');
  const [newNote, setNewNote] = useState('');
  const [logs, setLogs] = useState([]);
  const [saving, setSaving]     = useState(false);
  const [noting, setNoting]     = useState(false);
  const [resetting, setResetting] = useState(false);
  const [deleting, setDeleting]   = useState(false);
  const [confirmDel, setConfirmDel]     = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [imgZoom, setImgZoom] = useState(null);
  const [showEdit, setShowEdit] = useState(false);
  const INP = mkINP(t);

  useEffect(() => {
    if (tab==='logs') {
      client.get(`/kyc/admin/logs/${kyc.id}/`).then(r=>setLogs(Array.isArray(r.data)?r.data:[])).catch(()=>setLogs([]));
    }
  }, [tab, kyc.id]);

  const doReview = async () => {
    if (action==='rejected'&&!reason.trim()) { toast('Rejection reason দাও','err'); return; }
    setSaving(true);
    try {
      await client.post(`/kyc/admin/review/${kyc.id}/`, { status:action,rejection_reason:reason,admin_notes:notes });
      toast(action==='verified'?'KYC Approved ✓':action==='rejected'?'KYC Rejected':'Updated');
      setKyc(p=>({...p,status:action,rejection_reason:reason,admin_notes:notes}));
      onRefresh();
    } catch(e) { toast(e?.response?.data?.error||'Failed','err'); }
    finally { setSaving(false); }
  };

  const doNote = async () => {
    if (!newNote.trim()) return;
    setNoting(true);
    try {
      await client.post(`/kyc/admin/add-note/${kyc.id}/`, { note:newNote });
      toast('Note added ✓'); setNewNote('');
      client.get(`/kyc/admin/logs/${kyc.id}/`).then(r=>setLogs(Array.isArray(r.data)?r.data:[]));
    } catch { toast('Note failed','err'); }
    finally { setNoting(false); }
  };

  const doReset = async () => {
    setResetting(true); setConfirmReset(false);
    try { await client.post(`/kyc/admin/reset/${kyc.id}/`); toast('KYC Reset ✓'); onRefresh(); onClose(); }
    catch { toast('Reset failed','err'); }
    finally { setResetting(false); }
  };

  const doDelete = async () => {
    setDeleting(true);
    try { await client.delete(`/kyc/admin/delete/${kyc.id}/`); toast('KYC Deleted'); onRefresh(); onClose(); }
    catch { toast('Delete failed','err'); }
    finally { setDeleting(false); setConfirmDel(false); }
  };

  const TABS = [{k:'info',l:'INFO',ic:IC.shield},{k:'docs',l:'DOCUMENTS',ic:IC.img},{k:'review',l:'REVIEW',ic:IC.approve},{k:'logs',l:'LOGS',ic:IC.log}];

  return (
    <div style={{ position:'fixed',inset:0,zIndex:1000,background:'#000c',backdropFilter:'blur(8px)',display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:t.bgC,border:`1px solid ${t.bs}`,borderRadius:14,padding:26,width:720,maxWidth:'96vw',maxHeight:'92vh',overflowY:'auto',boxShadow:`0 24px 80px ${t.g}`,animation:'kfadeUp .3s ease' }}>

        {/* Header */}
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:18,flexWrap:'wrap',gap:10 }}>
          <div style={{ display:'flex',alignItems:'center',gap:10,flexWrap:'wrap' }}>
            <div style={{ width:7,height:7,borderRadius:'50%',background:t.p,animation:'kpulse 1.5s infinite',boxShadow:`0 0 8px ${t.p}` }}/>
            <span style={{ fontSize:15,fontWeight:800,color:t.t,fontFamily:"'Courier New',monospace" }}>{kyc.full_name||'N/A'}</span>
            <Badge status={kyc.status}/>
            {kyc.is_duplicate&&<span style={{ background:'#ff224420',border:'1px solid #ff224444',borderRadius:4,padding:'2px 8px',color:'#ff2244',fontSize:9,fontFamily:"'Courier New',monospace" }}>⚠ DUPLICATE</span>}
          </div>
          <div style={{ display:'flex',gap:6 }}>
            <ABtn icon={IC.edit}  label="EDIT"   color={t.p}     onClick={()=>setShowEdit(true)}         small/>
            <ABtn icon={IC.reset} label="RESET"  color="#ffcc00" onClick={()=>setConfirmReset(true)} loading={resetting} small/>
            <ABtn icon={IC.trash} label="DELETE" color="#ff2244" onClick={()=>setConfirmDel(true)}        small/>
            <button onClick={onClose} style={{ background:'none',border:'none',cursor:'pointer',color:t.tm,padding:4 }}><Icon d={IC.x} size={18}/></button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex',borderBottom:`1px solid ${t.b}`,marginBottom:18 }}>
          {TABS.map(tb=>(
            <button key={tb.k} onClick={()=>setTab(tb.k)} style={{ background:'none',border:'none',borderBottom:`2px solid ${tab===tb.k?t.p:'transparent'}`,padding:'8px 16px',color:tab===tb.k?t.p:t.tm,fontSize:10,cursor:'pointer',fontFamily:"'Courier New',monospace",fontWeight:700,letterSpacing:'.08em',marginBottom:-1,transition:'all .2s',display:'flex',alignItems:'center',gap:5 }}>
              <Icon d={tb.ic} size={11}/> {tb.l}
            </button>
          ))}
        </div>

        {/* ── INFO TAB ── */}
        {tab==='info'&&(
          <div style={{ animation:'kfadeUp .2s ease' }}>
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:14 }}>
              {[
                {l:'FULL NAME',v:kyc.full_name},{l:'DATE OF BIRTH',v:kyc.date_of_birth},
                {l:'PHONE',v:kyc.phone_number},{l:'PAYMENT',v:`${kyc.payment_number||'—'} (${(kyc.payment_method||'').toUpperCase()})`},
                {l:'DOCUMENT TYPE',v:(kyc.document_type||'—').replace(/_/g,' ').toUpperCase()},{l:'DOCUMENT NUMBER',v:kyc.document_number},
                {l:'CITY',v:kyc.city},{l:'COUNTRY',v:kyc.country},
                {l:'SUBMITTED',v:fmtD(kyc.created_at)},{l:'REVIEWED',v:fmtD(kyc.reviewed_at)},
                ...(kyc.rejection_reason?[{l:'REJECTION REASON',v:kyc.rejection_reason,span:true,warn:true}]:[]),
              ].filter(r=>r.v).map(r=>(
                <div key={r.l} style={{ background:t.bgP,borderRadius:8,padding:'9px 12px',border:`1px solid ${t.b}`,gridColumn:r.span?'1/-1':'auto' }}>
                  <div style={{ fontSize:9,color:r.warn?'#ff2244':t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:3 }}>{r.l}</div>
                  <div style={{ fontSize:12,color:r.warn?'#ff8899':t.t,fontWeight:600 }}>{r.v||'—'}</div>
                </div>
              ))}
            </div>
            {/* Verification checks */}
            <div style={{ display:'flex',gap:8,flexWrap:'wrap',marginBottom:12 }}>
              {[{l:'NAME',v:kyc.is_name_verified},{l:'PHONE',v:kyc.is_phone_verified},{l:'PAYMENT',v:kyc.is_payment_verified},{l:'DOCUMENT',v:!!kyc.document_front},{l:'SELFIE',v:!!kyc.selfie_photo}].map(s=>(
                <div key={s.l} style={{ background:t.bgP,border:`1px solid ${s.v?'#00ff8833':t.b}`,borderRadius:8,padding:'7px 12px',textAlign:'center' }}>
                  <div style={{ fontSize:9,color:t.tm,fontFamily:"'Courier New',monospace",marginBottom:3 }}>{s.l}</div>
                  <div style={{ fontSize:14,fontWeight:800,color:s.v?'#00ff88':'#334455',fontFamily:"'Courier New',monospace" }}>{s.v?'✓':'—'}</div>
                </div>
              ))}
            </div>
            {/* Risk */}
            <div style={{ padding:'12px 16px',background:`${riskC(kyc.risk_score||0)}12`,border:`1px solid ${riskC(kyc.risk_score||0)}33`,borderRadius:8,marginBottom:10 }}>
              <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8 }}>
                <span style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace" }}>RISK SCORE</span>
                <span style={{ fontSize:16,fontWeight:900,color:riskC(kyc.risk_score||0),fontFamily:"'Courier New',monospace" }}>{kyc.risk_score||0}/100</span>
              </div>
              <div style={{ height:5,background:t.bgP,borderRadius:3,overflow:'hidden' }}>
                <div style={{ width:`${kyc.risk_score||0}%`,height:'100%',background:riskC(kyc.risk_score||0),borderRadius:3 }}/>
              </div>
            </div>
            {kyc.risk_factors?.length>0&&(
              <div style={{ padding:'10px 14px',background:'#ff224410',border:'1px solid #ff224433',borderRadius:8,marginBottom:10 }}>
                <div style={{ fontSize:9,color:'#ff2244',letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:6 }}>⚠ RISK FACTORS</div>
                {kyc.risk_factors.map((f,i)=><div key={i} style={{ fontSize:11,color:'#ff6677',marginBottom:2 }}>• {f}</div>)}
              </div>
            )}
            {kyc.admin_notes&&(
              <div style={{ padding:'10px 14px',background:'#ffcc0010',border:'1px solid #ffcc0033',borderRadius:8 }}>
                <div style={{ fontSize:9,color:'#ffcc00',letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:4 }}>ADMIN NOTES</div>
                <div style={{ fontSize:12,color:'#ffe8aa',whiteSpace:'pre-line' }}>{kyc.admin_notes}</div>
              </div>
            )}
          </div>
        )}

        {/* ── DOCS TAB ── */}
        {tab==='docs'&&(
          <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:14,animation:'kfadeUp .2s ease' }}>
            {[{l:'DOCUMENT FRONT',url:imgSrc(kyc.document_front)},{l:'DOCUMENT BACK',url:imgSrc(kyc.document_back)},{l:'SELFIE PHOTO',url:imgSrc(kyc.selfie_photo)}].map(img=>(
              <div key={img.l}>
                <div style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:7 }}>{img.l}</div>
                {img.url
                  ? <div onClick={()=>setImgZoom(img.url)} style={{ cursor:'zoom-in',borderRadius:10,overflow:'hidden',border:`1px solid ${t.b}`,height:180 }}><img src={img.url} alt={img.l} style={{ width:'100%',height:'100%',objectFit:'cover' }}/></div>
                  : <div style={{ height:180,borderRadius:10,border:`2px dashed ${t.b}`,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',color:t.tm }}><Icon d={IC.img} size={28}/><div style={{ fontSize:9,marginTop:8,fontFamily:"'Courier New',monospace" }}>NOT UPLOADED</div></div>}
              </div>
            ))}
          </div>
        )}

        {/* ── REVIEW TAB ── */}
        {tab==='review'&&(
          <div style={{ animation:'kfadeUp .2s ease' }}>
            <div style={{ display:'flex',gap:8,marginBottom:16 }}>
              {[{k:'verified',l:'✓ APPROVE',c:'#00ff88'},{k:'rejected',l:'✗ REJECT',c:'#ff2244'},{k:'pending',l:'⏳ PENDING',c:'#ffcc00'}].map(a=>(
                <button key={a.k} onClick={()=>setAction(a.k)} style={{ flex:1,background:action===a.k?`${a.c}20`:'transparent',border:`1px solid ${action===a.k?a.c+'55':t.b}`,borderRadius:8,padding:10,color:action===a.k?a.c:t.tm,fontSize:11,fontWeight:action===a.k?700:400,cursor:'pointer',fontFamily:"'Courier New',monospace",transition:'all .2s' }}>
                  {a.l}
                </button>
              ))}
            </div>
            {action==='rejected'&&(
              <div style={{ marginBottom:12 }}>
                <div style={{ fontSize:10,color:'#ff2244',letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:5 }}>REJECTION REASON *</div>
                <textarea value={reason} onChange={e=>setReason(e.target.value)} rows={2} placeholder="Reason…" style={{ ...INP,borderColor:'#ff224433' }} onFocus={e=>e.target.style.borderColor='#ff224466'} onBlur={e=>e.target.style.borderColor='#ff224433'}/>
              </div>
            )}
            <div style={{ marginBottom:14 }}>
              <div style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:5 }}>ADMIN NOTES</div>
              <textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} placeholder="Internal notes…" style={INP} onFocus={e=>e.target.style.borderColor=t.bs} onBlur={e=>e.target.style.borderColor=t.b}/>
            </div>
            <div style={{ display:'flex',gap:10,marginBottom:20 }}>
              <button onClick={onClose} style={{ flex:1,background:t.b,border:`1px solid ${t.bs}`,borderRadius:8,padding:11,color:t.tm,fontSize:11,cursor:'pointer',fontFamily:"'Courier New',monospace" }}>CANCEL</button>
              <button onClick={doReview} disabled={saving||(action==='rejected'&&!reason.trim())} style={{ flex:2,background:action==='verified'?'#00ff8820':action==='rejected'?'#ff224420':'#ffcc0020',border:`1px solid ${action==='verified'?'#00ff8855':action==='rejected'?'#ff224455':'#ffcc0055'}`,borderRadius:8,padding:11,color:action==='verified'?'#00ff88':action==='rejected'?'#ff2244':'#ffcc00',fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',justifyContent:'center',gap:8 }}>
                {saving?<Spin/>:<Icon d={IC.check} size={12}/>} {saving?'SAVING…':'SUBMIT REVIEW'}
              </button>
            </div>
            <div style={{ paddingTop:14,borderTop:`1px solid ${t.b}` }}>
              <div style={{ fontSize:10,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",marginBottom:7 }}>ADD QUICK NOTE</div>
              <div style={{ display:'flex',gap:8 }}>
                <input value={newNote} onChange={e=>setNewNote(e.target.value)} onKeyDown={e=>e.key==='Enter'&&doNote()} placeholder="Note… (Enter)" style={{ ...INP,flex:1,resize:'none' }} onFocus={e=>e.target.style.borderColor=t.bs} onBlur={e=>e.target.style.borderColor=t.b}/>
                <button onClick={doNote} disabled={noting||!newNote.trim()} style={{ background:`${t.p}16`,border:`1px solid ${t.bs}`,borderRadius:8,padding:'9px 14px',color:t.p,fontSize:10,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'flex',alignItems:'center',gap:5 }}>
                  {noting?<Spin/>:<Icon d={IC.note} size={11}/>} ADD
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── LOGS TAB ── */}
        {tab==='logs'&&(
          <div style={{ animation:'kfadeUp .2s ease' }}>
            {logs.length===0
              ? <div style={{ textAlign:'center',padding:40,color:t.tm,fontFamily:"'Courier New',monospace",fontSize:11 }}>NO AUDIT LOGS YET</div>
              : logs.map((l,i)=>{
                const lc=l.action==='submitted'?t.p:l.action==='approved'?'#00ff88':l.action==='rejected'?'#ff2244':'#ffcc00';
                return (
                  <div key={i} style={{ display:'flex',gap:12,padding:'10px 0',borderBottom:`1px solid ${t.b}` }}>
                    <div style={{ width:7,height:7,borderRadius:'50%',background:lc,marginTop:5,flexShrink:0,boxShadow:`0 0 6px ${lc}` }}/>
                    <div style={{ flex:1 }}>
                      <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:2 }}>
                        <span style={{ fontSize:11,fontWeight:700,color:lc,fontFamily:"'Courier New',monospace" }}>{(l.action||'').toUpperCase()}</span>
                        {l.performed_by__username&&<span style={{ fontSize:10,color:t.p,fontFamily:"'Courier New',monospace" }}>by {l.performed_by__username}</span>}
                      </div>
                      {l.details&&<div style={{ fontSize:11,color:t.tm }}>{l.details}</div>}
                    </div>
                    <span style={{ fontSize:10,color:t.tm,fontFamily:"'Courier New',monospace",whiteSpace:'nowrap' }}>{fmtD(l.created_at)}</span>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {imgZoom&&<div onClick={()=>setImgZoom(null)} style={{ position:'fixed',inset:0,zIndex:1001,background:'#000e',display:'flex',alignItems:'center',justifyContent:'center',cursor:'zoom-out' }}><img src={imgZoom} alt="doc" style={{ maxWidth:'90vw',maxHeight:'90vh',borderRadius:12 }}/></div>}
      {showEdit&&<EditModal kyc={kyc} onClose={()=>setShowEdit(false)} onRefresh={()=>{ onRefresh(); client.get(`/kyc/admin/review/${kyc.id}/`).then(r=>setKyc(r.data)).catch(()=>{}); }} toast={toast} t={t}/>}
      {confirmReset&&<Confirm title="RESET KYC" msg={`"${kyc.full_name}" এর status reset হয়ে pending হবে।`} onOk={doReset} onNo={()=>setConfirmReset(false)} loading={resetting} okLabel="RESET" okColor="#ffcc00" t={t}/>}
      {confirmDel&&<Confirm title="DELETE KYC" msg={`"${kyc.full_name}" এর সমস্ত KYC data চিরতরে মুছে যাবে।`} onOk={doDelete} onNo={()=>setConfirmDel(false)} loading={deleting} okLabel="DELETE" okColor="#ff2244" t={t}/>}
    </div>
  );
};

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function KYCPage() {
  const [themeIdx, setThemeIdx] = useState(0);
  // progress handled via DOM ref (no re-render)
  const progRef = useRef(null);
  const t = THEMES[themeIdx];

  useEffect(()=>{
    let ticks=0;
    progRef.current=setInterval(()=>{
      ticks++;
      // Use ref for progress to avoid re-render every 100ms
      const newProg = Math.min(100,(ticks/600)*100);
      if(progRef._bar) progRef._bar.style.width = newProg + '%';
      if(ticks>=600){
        ticks=0;
        if(progRef._bar) progRef._bar.style.width = '0%';
        setThemeIdx(i=>(i+1)%THEMES.length);
      }
    },100);
    return ()=>clearInterval(progRef.current);
  },[]);

  const [isAdmin, setIsAdmin]           = useState(false);
  const [profileReady, setProfileReady] = useState(false);
  const [userKyc, setUserKyc]           = useState(null);
  const [userLogs, setUserLogs]         = useState([]);
  const [allKyc, setAllKyc]             = useState([]);
  const [kycList, setKycList]           = useState([]);
  const [stats, setStats]               = useState(null);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [search, setSearch]             = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortField, setSortField]       = useState('created_at');
  const [sortDir, setSortDir]           = useState('desc');
  const [page, setPage]                 = useState(1);
  const [totalPages, setTotalPages]     = useState(1);
  const [selected, setSelected]         = useState([]);
  const [bulkAction, setBulkAction]     = useState('verified');
  const [bulking, setBulking]           = useState(false);
  const [modal, setModal]               = useState(null);
  const openModal = useCallback((kyc) => {
    setModal(kyc);
  }, []);
  const [showForm, setShowForm]         = useState(false);
  const [clock, setClock]               = useState('');
  const PAGE = 15;
  const { list:toasts, add:toast } = useToast();

  useEffect(()=>{ const tick=()=>setClock(new Date().toUTCString().slice(17,25)+' UTC'); tick(); const id=setInterval(tick,1000); return ()=>clearInterval(id); },[]);

  useEffect(()=>{
    let found=false;
    try { const u=JSON.parse(localStorage.getItem('user')||'{}'); if(u?.is_staff||u?.is_superuser){setIsAdmin(true);setProfileReady(true);found=true;} } catch{}
    if(!found){
      try { const tok=localStorage.getItem('adminAccessToken')||localStorage.getItem('access')||localStorage.getItem('token'); if(tok){const p=JSON.parse(atob(tok.split('.')[1]));if(p?.is_staff||p?.is_superuser){setIsAdmin(true);setProfileReady(true);found=true;}} } catch{}
    }
    if(!found){ client.get('/profile/').then(r=>{if(r.data?.is_staff||r.data?.is_superuser)setIsAdmin(true);}).catch(()=>{}).finally(()=>setProfileReady(true)); }
  },[]);

  const fetchUser = useCallback(async()=>{
    try {
      const [s,l]=await Promise.all([client.get('/kyc/submit/'),client.get('/kyc/logs/')]);
      setUserKyc(s.data?.status==='not_submitted'?null:s.data);
      setUserLogs(Array.isArray(l.data)?l.data:[]);
    } catch{}
  },[]);

  const fetchAdmin = useCallback(async(silent=false)=>{
    if(!isAdmin) return;
    if(!silent) setLoading(true); else setRefreshing(true);
    try {
      let statsData=null;
      try { const r=await client.get('/kyc/admin/stats/'); statsData=r.data; } catch{}
      const lr=await client.get('/kyc/admin/list/');
      const all=Array.isArray(lr.data)?lr.data:Array.isArray(lr.data?.results)?lr.data.results:[];
      setAllKyc(all);
      if(!statsData){
        statsData={
          total:all.length, pending:all.filter(k=>k.status==='pending').length,
          verified:all.filter(k=>k.status==='verified').length, rejected:all.filter(k=>k.status==='rejected').length,
          high_risk:all.filter(k=>(k.risk_score||0)>60).length, duplicates:all.filter(k=>k.is_duplicate).length,
          submitted_today:all.filter(k=>k.created_at?.slice(0,10)===new Date().toISOString().slice(0,10)).length,
        };
      }
      setStats(statsData);
    } catch { toast('Load failed','err'); }
    finally { setLoading(false); setRefreshing(false); }
  },[isAdmin]);

  useEffect(()=>{ if(profileReady){fetchUser();if(isAdmin)fetchAdmin();} },[profileReady,isAdmin]);

  // client-side filter + sort + paginate
  useEffect(()=>{
    let list=[...allKyc];
    if(statusFilter) list=list.filter(k=>k.status===statusFilter);
    if(search){const q=search.toLowerCase();list=list.filter(k=>k.full_name?.toLowerCase().includes(q)||k.phone_number?.includes(q)||k.document_number?.includes(q)||String(k.id).includes(q));}
    list.sort((a,b)=>{
      let va=a[sortField],vb=b[sortField];
      if(typeof va==='string'){va=va.toLowerCase();vb=(vb||'').toLowerCase();}
      if(va==null)return 1;if(vb==null)return -1;
      return sortDir==='asc'?(va>vb?1:-1):(va<vb?1:-1);
    });
    const tot=Math.ceil(list.length/PAGE)||1;
    setTotalPages(tot);
    const cp=Math.min(page,tot);
    setKycList(list.slice((cp-1)*PAGE,cp*PAGE));
  },[allKyc,search,statusFilter,sortField,sortDir,page]);

  const toggleSort=field=>{if(sortField===field)setSortDir(d=>d==='asc'?'desc':'asc');else{setSortField(field);setSortDir('desc');}};
  const toggleSel=id=>setSelected(p=>p.includes(id)?p.filter(x=>x!==id):[...p,id]);
  const toggleAll=()=>setSelected(selected.length===kycList.length&&kycList.length>0?[]:kycList.map(k=>k.id));

  const doBulk=async()=>{
    if(!selected.length){toast('কমপক্ষে একটি select করো','warn');return;}
    setBulking(true);
    try {
      await client.post('/kyc/admin/bulk-action/',{ids:selected,action:bulkAction});
      toast(`${selected.length} records → ${bulkAction}`);
    } catch {
      let done=0;
      for(const id of selected){try{await client.post(`/kyc/admin/review/${id}/`,{status:bulkAction});done++;}catch{}}
      if(done)toast(`${done} records updated`);
    }
    setSelected([]); fetchAdmin(true); setBulking(false);
  };

  const exportCSV=()=>{
    const rows=['ID,Name,Status,Risk,DocType,DocNo,Phone,City,Created'].concat(allKyc.map(k=>`${k.id},"${k.full_name||''}",${k.status},${k.risk_score||0},"${k.document_type||''}","${k.document_number||''}","${k.phone_number||''}","${k.city||''}","${(k.created_at||'').slice(0,10)}"`));
    const a=document.createElement('a');
    a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(rows.join('\n'));
    a.download=`kyc_${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); toast('CSV exported');
  };

  if(!profileReady) return (
    <div style={{ minHeight:'100vh',background:t.bg,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ color:t.p,fontSize:12,fontFamily:"'Courier New',monospace",animation:'kpulse 1.5s infinite' }}>LOADING SYSTEM…</div>
    </div>
  );

  const STH=({field,label,w})=>(
    <th onClick={()=>toggleSort(field)} style={{ padding:'10px 14px',fontSize:9,color:sortField===field?t.p:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",fontWeight:700,textAlign:'left',borderBottom:`1px solid ${t.b}`,whiteSpace:'nowrap',width:w,cursor:'pointer',userSelect:'none' }}>
      {label} {sortField===field?(sortDir==='asc'?'↑':'↓'):''}
    </th>
  );
  const TH=({children,w})=><th style={{ padding:'10px 14px',fontSize:9,color:t.tm,letterSpacing:'.1em',fontFamily:"'Courier New',monospace",fontWeight:700,textAlign:'left',borderBottom:`1px solid ${t.b}`,whiteSpace:'nowrap',width:w }}>{children}</th>;
  const TD=({children,style:st={}})=><td style={{ padding:'10px 14px',fontSize:11,color:t.t,fontFamily:"'Courier New',monospace",borderBottom:`1px solid ${t.b}18`,...st }}>{children}</td>;

  return (
    <div style={{ minHeight:'100vh',background:t.bg,color:t.t,fontFamily:"'Segoe UI',sans-serif",transition:'all .8s ease' }}>
      <style>{`
        @keyframes kfadeUp  { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes kshimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes kpulse   { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes kspin    { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        *{ box-sizing:border-box; }
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-thumb{background:${t.bs};border-radius:4px}
        .krow:hover td{background:${t.bgP}!important}
        select option{background:${t.bg}}

      `}</style>

      {/* Scanline */}
      <div style={{ position:'fixed',inset:0,backgroundImage:`repeating-linear-gradient(0deg,${t.sl} 0,${t.sl} 1px,transparent 1px,transparent 4px)`,pointerEvents:'none',zIndex:0 }}/>

      {/* Top bar */}
      <div style={{ background:t.bgC,borderBottom:`1px solid ${t.b}`,padding:'8px 24px',display:'flex',alignItems:'center',justifyContent:'space-between',position:'sticky',top:0,zIndex:10,backdropFilter:'blur(12px)' }}>
        <div style={{ display:'flex',alignItems:'center',gap:14 }}>
          <div style={{ width:6,height:6,borderRadius:'50%',background:t.p,animation:'kpulse 1.5s infinite',boxShadow:`0 0 8px ${t.p}` }}/>
          <span style={{ color:t.p,fontSize:10,fontWeight:700,letterSpacing:'.15em',fontFamily:"'Courier New',monospace" }}>{t.name}</span>
          <span style={{ color:t.tm,fontSize:10,fontFamily:"'Courier New',monospace" }}>• KYC SYSTEM</span>
        </div>
        <div style={{ display:'flex',alignItems:'center',gap:16 }}>
          <div style={{ display:'flex',alignItems:'center',gap:8 }}>
            <span style={{ color:t.tm,fontSize:9,fontFamily:"'Courier New',monospace" }}>NEXT THEME</span>
            <div style={{ width:80,height:3,background:t.b,borderRadius:2 }}><div ref={el=>progRef._bar=el} style={{ width:'0%',height:'100%',background:t.p,borderRadius:2 }}/></div>
          </div>
          <span style={{ color:t.tm,fontSize:10,fontFamily:"'Courier New',monospace" }}>{clock}</span>
          <span style={{ color:t.p,fontSize:10,fontWeight:700,fontFamily:"'Courier New',monospace",background:`${t.p}15`,padding:'3px 10px',borderRadius:4,border:`1px solid ${t.bs}` }}>{isAdmin?'ADMIN ACCESS':'USER VIEW'}</span>
        </div>
      </div>

      <div style={{ padding:'24px',position:'relative',zIndex:2 }}>

        {/* Page header */}
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:24,flexWrap:'wrap',gap:12 }}>
          <div style={{ display:'flex',alignItems:'center',gap:16 }}>
            <div style={{ width:50,height:50,borderRadius:12,background:t.gr,border:`1px solid ${t.bs}`,display:'flex',alignItems:'center',justifyContent:'center',boxShadow:`0 0 28px ${t.g}` }}>
              <span style={{ color:t.p }}><Icon d={IC.shield} size={24}/></span>
            </div>
            <div>
              <div style={{ fontSize:22,fontWeight:900,letterSpacing:'.08em',fontFamily:"'Courier New',monospace",color:t.p,textShadow:`0 0 20px ${t.g}` }}>KYC CONTROL CENTER</div>
              <div style={{ color:t.tm,fontSize:11,fontFamily:"'Courier New',monospace" }}>
                {isAdmin?`${stats?.total??'—'} TOTAL · ${stats?.pending??'—'} PENDING · ${stats?.verified??'—'} VERIFIED`:`STATUS: ${(userKyc?.status||'NOT SUBMITTED').toUpperCase()}`}
              </div>
            </div>
          </div>
          <div style={{ display:'flex',gap:8 }}>
            <ABtn icon={IC.refresh} label="REFRESH" color={t.p} onClick={()=>{fetchUser();fetchAdmin(true);}} loading={refreshing}/>
            {!isAdmin&&<ABtn icon={IC.upload} label={showForm?'HIDE FORM':userKyc?'EDIT/RESUBMIT':'SUBMIT KYC'} color="#00ff88" onClick={()=>setShowForm(v=>!v)}/>}
            {isAdmin&&<ABtn icon={IC.down} label="EXPORT CSV" color={t.p} onClick={exportCSV}/>}
          </div>
        </div>

        {/* ════ USER VIEW ════ */}
        {!isAdmin&&(
          <>
            <div style={{ background:`linear-gradient(135deg,${SC[userKyc?.status||'not_submitted']?.c||'#667788'}12,${t.bgC})`,border:`1px solid ${SC[userKyc?.status||'not_submitted']?.c||'#667788'}33`,borderRadius:12,padding:'20px 22px',marginBottom:20,animation:'kfadeUp .4s ease' }}>
              <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:14 }}>
                <div>
                  <div style={{ fontSize:9,color:t.tm,letterSpacing:'.15em',fontFamily:"'Courier New',monospace",marginBottom:10 }}>YOUR VERIFICATION STATUS</div>
                  <Badge status={userKyc?.status||'not_submitted'}/>
                  {userKyc?.rejection_reason&&<div style={{ marginTop:10,fontSize:12,color:'#ff8899',fontFamily:"'Courier New',monospace" }}><span style={{ color:'#ff2244',fontWeight:700 }}>Reason: </span>{userKyc.rejection_reason}</div>}
                </div>
                {userKyc&&(
                  <div style={{ display:'flex',gap:10,flexWrap:'wrap' }}>
                    {[{l:'NAME',v:userKyc.is_name_verified},{l:'PHONE',v:userKyc.is_phone_verified},{l:'PAYMENT',v:userKyc.is_payment_verified},{l:'DOCUMENT',v:!!userKyc.document_front}].map(s=>(
                      <div key={s.l} style={{ background:t.bgP,borderRadius:8,padding:'8px 13px',textAlign:'center',border:`1px solid ${s.v?'#00ff8833':t.b}` }}>
                        <div style={{ fontSize:9,color:t.tm,fontFamily:"'Courier New',monospace",marginBottom:4 }}>{s.l}</div>
                        <div style={{ fontSize:16,fontWeight:800,color:s.v?'#00ff88':'#334455',fontFamily:"'Courier New',monospace" }}>{s.v?'✓':'—'}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {showForm&&<KYCForm existing={userKyc} onDone={()=>{setShowForm(false);fetchUser();}} toast={toast} t={t}/>}
            {userLogs.length>0&&(
              <div style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:10,padding:'16px 18px' }}>
                <div style={{ fontSize:10,fontWeight:700,color:t.tm,fontFamily:"'Courier New',monospace",letterSpacing:'.1em',marginBottom:12 }}>VERIFICATION HISTORY</div>
                {userLogs.map((l,i)=>(
                  <div key={i} style={{ display:'flex',alignItems:'center',gap:10,padding:'7px 0',borderBottom:`1px solid ${t.b}` }}>
                    <div style={{ width:6,height:6,borderRadius:'50%',background:t.p,flexShrink:0 }}/>
                    <span style={{ fontSize:11,fontWeight:700,color:t.t,fontFamily:"'Courier New',monospace" }}>{(l.action||'').toUpperCase()}</span>
                    {l.details&&<span style={{ fontSize:11,color:t.tm }}>{l.details}</span>}
                    <span style={{ marginLeft:'auto',fontSize:10,color:t.tm,fontFamily:"'Courier New',monospace" }}>{fmtD(l.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ════ ADMIN VIEW ════ */}
        {isAdmin&&(
          <>
            {/* Stats — clickable filter */}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(130px,1fr))',gap:12,marginBottom:22 }}>
              <StatCard label="TOTAL"      value={stats?.total}           icon={IC.shield}  color={t.p}      loading={loading&&!stats} t={t} onClick={()=>{setStatusFilter('');setPage(1);}}             active={statusFilter===''}/>
              <StatCard label="PENDING"    value={stats?.pending}         icon={IC.clock}   color="#ffcc00"  loading={loading&&!stats} t={t} onClick={()=>{setStatusFilter('pending');setPage(1);}}      active={statusFilter==='pending'}/>
              <StatCard label="VERIFIED"   value={stats?.verified}        icon={IC.approve} color="#00ff88"  loading={loading&&!stats} t={t} onClick={()=>{setStatusFilter('verified');setPage(1);}}     active={statusFilter==='verified'}/>
              <StatCard label="REJECTED"   value={stats?.rejected}        icon={IC.reject}  color="#ff2244"  loading={loading&&!stats} t={t} onClick={()=>{setStatusFilter('rejected');setPage(1);}}     active={statusFilter==='rejected'}/>
              <StatCard label="HIGH RISK"  value={stats?.high_risk}       icon={IC.risk}    color="#ff6600"  loading={loading&&!stats} t={t}/>
              <StatCard label="DUPLICATES" value={stats?.duplicates}      icon={IC.alert}   color="#bb44ff"  loading={loading&&!stats} t={t}/>
              <StatCard label="TODAY"      value={stats?.submitted_today} icon={IC.stats}   color={t.p}      loading={loading&&!stats} t={t}/>
            </div>

            {/* Filters */}
            <div style={{ display:'flex',gap:10,marginBottom:14,flexWrap:'wrap',alignItems:'center' }}>
              <div style={{ display:'flex',alignItems:'center',gap:8,background:t.bgC,border:`1px solid ${t.b}`,borderRadius:8,padding:'8px 14px',flex:1,minWidth:200,maxWidth:360 }}>
                <span style={{ color:t.tm,flexShrink:0 }}><Icon d={IC.search} size={12}/></span>
                <input placeholder="Search name, phone, doc, ID…" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} style={{ background:'none',border:'none',outline:'none',color:t.t,fontSize:11,width:'100%',fontFamily:"'Courier New',monospace" }}/>
                {search&&<button onClick={()=>setSearch('')} style={{ background:'none',border:'none',color:t.tm,cursor:'pointer',fontSize:14 }}>✕</button>}
              </div>
              {[{v:'',l:'ALL'},{v:'pending',l:'PENDING'},{v:'verified',l:'VERIFIED'},{v:'rejected',l:'REJECTED'},{v:'not_submitted',l:'NOT SUBMITTED'},{v:'expired',l:'EXPIRED'}].map(f=>(
                <button key={f.v} onClick={()=>{setStatusFilter(f.v);setPage(1);}} style={{ background:statusFilter===f.v?`${t.p}20`:'transparent',border:`1px solid ${statusFilter===f.v?t.p:t.b}`,borderRadius:20,padding:'7px 12px',color:statusFilter===f.v?t.p:t.tm,fontSize:10,cursor:'pointer',fontFamily:"'Courier New',monospace",fontWeight:statusFilter===f.v?700:400,transition:'all .2s',whiteSpace:'nowrap' }}>{f.l}</button>
              ))}
              <span style={{ marginLeft:'auto',color:t.tm,fontSize:11,fontFamily:"'Courier New',monospace",whiteSpace:'nowrap' }}><span style={{ color:t.p,fontWeight:700 }}>{kycList.length}</span>/{allKyc.length} RECORDS</span>
            </div>

            {/* Bulk action bar */}
            {selected.length>0&&(
              <div style={{ display:'flex',alignItems:'center',gap:12,padding:'10px 14px',background:`${t.p}10`,border:`1px solid ${t.bs}`,borderRadius:8,marginBottom:12,animation:'kfadeUp .2s ease',flexWrap:'wrap' }}>
                <span style={{ fontSize:11,color:t.p,fontFamily:"'Courier New',monospace",fontWeight:700 }}>{selected.length} SELECTED</span>
                <select value={bulkAction} onChange={e=>setBulkAction(e.target.value)} style={{ background:t.bgP,border:`1px solid ${t.b}`,borderRadius:6,padding:'5px 10px',color:t.t,fontSize:11,outline:'none',fontFamily:"'Courier New',monospace" }}>
                  <option value="verified">Approve All</option>
                  <option value="rejected">Reject All</option>
                  <option value="pending">Set Pending</option>
                </select>
                <ABtn icon={IC.check} label="APPLY BULK" color={t.p} onClick={doBulk} loading={bulking}/>
                <button onClick={()=>setSelected([])} style={{ marginLeft:'auto',background:'none',border:'none',color:t.tm,cursor:'pointer' }}><Icon d={IC.x} size={14}/></button>
              </div>
            )}

            {/* Table */}
            <div style={{ overflowX:'auto',borderRadius:12,border:`1px solid ${t.b}`,animation:'kfadeUp .3s ease' }}>
              <table style={{ width:'100%',borderCollapse:'collapse',background:t.bgC }}>
                <thead>
                  <tr style={{ background:t.bgP }}>
                    <TH w={36}><div onClick={toggleAll} style={{ cursor:'pointer',color:t.tm }}><Icon d={selected.length===kycList.length&&kycList.length>0?IC.sqOk:IC.sq} size={13}/></div></TH>
                    <STH field="full_name"     label="NAME / ID"/>
                    <STH field="phone_number"  label="PHONE"/>
                    <STH field="document_type" label="DOCUMENT"/>
                    <STH field="status"        label="STATUS"/>
                    <STH field="risk_score"    label="RISK" w={90}/>
                    <STH field="created_at"    label="DATE"/>
                    <TH>ACTIONS</TH>
                  </tr>
                </thead>
                <tbody>
                  {loading
                    ? Array(8).fill(0).map((_,i)=><tr key={i}>{Array(8).fill(0).map((_,j)=><td key={j} style={{ padding:'12px 14px' }}><SK/></td>)}</tr>)
                    : kycList.length===0
                      ? <tr><td colSpan={8} style={{ padding:'60px',textAlign:'center',color:t.tm,fontFamily:"'Courier New',monospace" }}><div style={{ fontSize:36,marginBottom:12 }}>🔒</div>NO RECORDS FOUND</td></tr>
                      : kycList.map(k=>(
                        <tr key={k.id} className="krow" style={{ background:selected.includes(k.id)?`${t.p}08`:'transparent',cursor:'pointer' }}>
                          <TD><div onClick={e=>{e.stopPropagation();toggleSel(k.id);}} style={{ cursor:'pointer',color:selected.includes(k.id)?t.p:t.tm }}><Icon d={selected.includes(k.id)?IC.sqOk:IC.sq} size={13}/></div></TD>
                          <TD>
                            <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                              <div style={{ width:32,height:32,borderRadius:8,background:`${t.p}22`,border:`1px solid ${t.bs}`,display:'flex',alignItems:'center',justifyContent:'center',fontSize:12,fontWeight:800,color:t.p,flexShrink:0 }}>{(k.full_name||'?')[0].toUpperCase()}</div>
                              <div>
                                <div style={{ color:t.p,fontWeight:700 }}>{k.full_name||'—'}</div>
                                <div style={{ color:t.tm,fontSize:9 }}>ID:{k.id}{k.is_duplicate&&<span style={{ color:'#ff2244',marginLeft:6 }}>⚠DUPE</span>}</div>
                              </div>
                            </div>
                          </TD>
                          <TD style={{ color:t.tm }}>{k.phone_number||'—'}</TD>
                          <TD>
                            <div style={{ color:'#bb44ff',fontSize:10 }}>{(k.document_type||'—').replace(/_/g,' ').toUpperCase()}</div>
                            {k.document_number&&<div style={{ color:t.tm,fontSize:9 }}>#{k.document_number}</div>}
                          </TD>
                          <TD><Badge status={k.status}/></TD>
                          <TD>
                            <div style={{ display:'flex',alignItems:'center',gap:6 }}>
                              <div style={{ width:50,height:4,background:t.bgP,borderRadius:2,overflow:'hidden' }}><div style={{ width:`${k.risk_score||0}%`,height:'100%',background:riskC(k.risk_score||0),borderRadius:2 }}/></div>
                              <span style={{ color:riskC(k.risk_score||0),fontWeight:700,fontSize:11,minWidth:24 }}>{k.risk_score||0}</span>
                            </div>
                          </TD>
                          <TD style={{ color:t.tm,fontSize:10 }}>{(k.created_at||'').slice(0,10)}</TD>
                          <TD>
                            <button
                              onClick={()=>openModal(k)}
                              style={{ background:`${t.p}22`,border:`1px solid ${t.bs}`,borderRadius:6,padding:'7px 14px',color:t.p,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:"'Courier New',monospace",display:'inline-flex',alignItems:'center',gap:5,outline:'none',userSelect:'none' }}>
                              <Icon d={IC.eye} size={11}/> REVIEW
                            </button>
                          </TD>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages>1&&(
              <div style={{ display:'flex',alignItems:'center',justifyContent:'center',gap:6,marginTop:16,flexWrap:'wrap' }}>
                <button onClick={()=>setPage(1)} disabled={page===1} style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:6,padding:'7px 10px',color:page===1?t.b:t.tm,cursor:page===1?'not-allowed':'pointer',fontFamily:"'Courier New',monospace",fontSize:11 }}>«</button>
                <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1} style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:6,padding:'7px 10px',color:page===1?t.b:t.tm,cursor:page===1?'not-allowed':'pointer' }}><Icon d={IC.chevL} size={13}/></button>
                {Array.from({length:totalPages},(_,i)=>i+1).filter(p=>p===1||p===totalPages||Math.abs(p-page)<=1).reduce((acc,p,i,arr)=>{ if(i>0&&arr[i-1]!==p-1)acc.push('…'); acc.push(p); return acc; },[]).map((p,i)=>
                  p==='…'?<span key={`e${i}`} style={{ color:t.tm,padding:'0 4px' }}>…</span>
                  :<button key={p} onClick={()=>setPage(p)} style={{ background:page===p?`${t.p}20`:t.bgC,border:`1px solid ${page===p?t.p:t.b}`,borderRadius:6,padding:'7px 11px',color:page===p?t.p:t.tm,cursor:'pointer',fontFamily:"'Courier New',monospace",fontSize:11,fontWeight:page===p?700:400,minWidth:34 }}>{p}</button>
                )}
                <button onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages} style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:6,padding:'7px 10px',color:page===totalPages?t.b:t.tm,cursor:page===totalPages?'not-allowed':'pointer' }}><Icon d={IC.chevR} size={13}/></button>
                <button onClick={()=>setPage(totalPages)} disabled={page===totalPages} style={{ background:t.bgC,border:`1px solid ${t.b}`,borderRadius:6,padding:'7px 10px',color:page===totalPages?t.b:t.tm,cursor:page===totalPages?'not-allowed':'pointer',fontFamily:"'Courier New',monospace",fontSize:11 }}>»</button>
                <span style={{ color:t.tm,fontSize:10,fontFamily:"'Courier New',monospace",marginLeft:4 }}>PAGE {page}/{totalPages}</span>
              </div>
            )}

            {/* Theme selector */}
            <div style={{ display:'flex',justifyContent:'center',gap:8,marginTop:24 }}>
              {THEMES.map((th,i)=>(
                <button key={i} onClick={()=>{setThemeIdx(i);if(progRef._bar)progRef._bar.style.width='0%';}} title={th.name} style={{ width:28,height:6,borderRadius:3,background:i===themeIdx?th.p:`${th.p}44`,border:'none',cursor:'pointer',boxShadow:i===themeIdx?`0 0 8px ${th.p}`:'none',transition:'all .3s' }}/>
              ))}
            </div>
          </>
        )}
      </div>

      {modal&&<ReviewModal kyc={modal} onClose={()=>setModal(null)} onRefresh={()=>{fetchAdmin(true);fetchUser();}} toast={toast} t={t}/>}
      <Toasts list={toasts}/>
    </div>
  );
}