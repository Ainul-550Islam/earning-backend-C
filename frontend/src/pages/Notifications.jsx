// NotificationsPage.jsx — Full CRUD
// API: /api/notifications/

import { useState, useEffect, useCallback } from "react";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── API ──────────────────────────────────────────────────────────────────
const API_BASE = "";
const getToken = () => localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || localStorage.getItem("token") || "";
const apiFetch = async (path, opts = {}) => {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers },
    ...opts,
  });
  if (res.status === 204) return {};
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw e; }
  return res.json();
};

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────
const T = {
  bg: "#060608", surface: "#0d0d12", surface2: "#13131a", surface3: "#1a1a24",
  border: "rgba(255,255,255,0.06)", border2: "rgba(255,255,255,0.1)",
  text: "#e8e8f0", textSub: "#8888a8", textMuted: "#5a5a72",
  accent: "#6c63ff", accentGlow: "rgba(108,99,255,0.25)",
  green: "#00e87a", red: "#ff3d5a", yellow: "#ffcc00", purple: "#c084fc", blue: "#38bdf8",
};

// ─── GLOBAL STYLES ────────────────────────────────────────────────────────
const GS = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');
    *{box-sizing:border-box;margin:0;padding:0;}
    ::-webkit-scrollbar{width:4px;height:4px;}
    ::-webkit-scrollbar-thumb{background:rgba(108,99,255,0.3);border-radius:2px;}
    select option{background:#13131a;color:#e8e8f0;}
    input::placeholder,textarea::placeholder{color:#3a3a52;}
    @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
    @keyframes modalIn{from{opacity:0;transform:scale(0.96)}to{opacity:1;transform:scale(1)}}
    .row-hover:hover{background:rgba(108,99,255,0.04)!important;}
    .btn-hover:hover{opacity:0.85!important;}
    .act-btn:hover{background:rgba(255,255,255,0.07)!important;color:#e8e8f0!important;}
    .pill:hover{border-color:rgba(108,99,255,0.4)!important;}
    .inp:focus{border-color:#6c63ff!important;outline:none;}
  `}</style>
);

// ─── ICONS ────────────────────────────────────────────────────────────────
const IC = {
  bell:"M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  send:"M22 2L11 13 M22 2L15 22 11 13 2 9l20-7z",
  template:"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  campaign:"M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z",
  notice:"M11 21H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h5 M13 3h5a2 2 0 0 1 2 2v5 M13 3l8 8-8 8",
  chart:"M18 20V10 M12 20V4 M6 20v-6",
  check:"M20 6L9 17l-5-5",
  pin:"M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z M12 7v6 M12 16h.01",
  archive:"M21 8v13H3V8 M1 3h22v5H1z M10 12h4",
  trash:"M3 6h18 M19 6l-1 14H6L5 6 M8 6V4h8v2",
  plus:"M12 5v14 M5 12h14",
  edit:"M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  eye:"M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  play:"M5 3l14 9-14 9V3z",
  pause:"M6 4h4v16H6z M14 4h4v16h-4z",
  stop:"M18 6H6v12h12z",
  bolt:"M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  x:"M18 6L6 18 M6 6l12 12",
  copy:"M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
};
const Ico = ({ n, s = 16 }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {(IC[n] || "").split(" M").map((d, i) => <path key={i} d={i === 0 ? d : "M" + d} />)}
  </svg>
);

// ─── SMALL UI COMPONENTS ──────────────────────────────────────────────────
const PC = {
  critical:{color:"#ff3d5a",bg:"rgba(255,61,90,0.12)",label:"CRITICAL"},
  urgent:{color:"#ff8c42",bg:"rgba(255,140,66,0.12)",label:"URGENT"},
  high:{color:"#ffcc00",bg:"rgba(255,204,0,0.12)",label:"HIGH"},
  medium:{color:"#00e87a",bg:"rgba(0,232,122,0.12)",label:"MEDIUM"},
  low:{color:"#5a5a72",bg:"rgba(90,90,114,0.15)",label:"LOW"},
};
const Badge = ({ p }) => { const c = PC[p] || PC.medium; return (
  <span style={{color:c.color,background:c.bg,padding:"2px 7px",borderRadius:3,fontSize:9,fontWeight:700,letterSpacing:"0.1em",fontFamily:"'JetBrains Mono',monospace",border:`1px solid ${c.color}30`}}>{c.label}</span>
);};

const SC = {sent:T.green,delivered:T.blue,read:T.textMuted,failed:T.red,pending:T.yellow,scheduled:T.purple,draft:"#3a3a4a",cancelled:T.red};
const Dot = ({ s }) => <span style={{display:"inline-block",width:6,height:6,borderRadius:"50%",background:SC[s]||T.textMuted,boxShadow:`0 0 5px ${SC[s]||T.textMuted}80`,flexShrink:0}} />;

const IS = {width:"100%",background:T.surface2,border:`1px solid ${T.border2}`,borderRadius:8,padding:"9px 13px",color:T.text,fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif",transition:"border-color 0.2s"};
const Lbl = ({ c }) => <label style={{display:"block",color:T.textMuted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",marginBottom:6,fontFamily:"'JetBrains Mono',monospace"}}>{c}</label>;
const ActBtn = ({ icon, onClick, title, color = T.textMuted }) => (
  <button className="act-btn" onClick={onClick} title={title} style={{background:"none",border:"none",color,cursor:"pointer",padding:"5px 7px",borderRadius:6,transition:"all 0.15s",display:"flex",alignItems:"center"}}>
    <Ico n={icon} s={13} />
  </button>
);
const FormField = ({ label, children }) => <div><Lbl c={label} />{children}</div>;
const TxtIn = ({ value, onChange, placeholder = "" }) => <input className="inp" value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} style={IS} />;
const SelIn = ({ value, onChange, options }) => (
  <select className="inp" value={value} onChange={e=>onChange(e.target.value)} style={IS}>
    {options.map(o => <option key={o} value={o}>{o.replace(/_/g," ")}</option>)}
  </select>
);
const TxtArea = ({ value, onChange, rows = 3 }) => <textarea className="inp" value={value} onChange={e=>onChange(e.target.value)} rows={rows} style={{...IS,resize:"vertical"}} />;

// ─── MODAL ────────────────────────────────────────────────────────────────
const Modal = ({ title, onClose, children, width = 520 }) => (
  <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.78)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center",padding:20}} onClick={onClose}>
    <div style={{background:T.surface,border:`1px solid ${T.border2}`,borderRadius:16,width:"100%",maxWidth:width,maxHeight:"88vh",overflow:"auto",animation:"modalIn 0.2s ease both"}} onClick={e=>e.stopPropagation()}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"18px 22px",borderBottom:`1px solid ${T.border}`}}>
        <h3 style={{color:T.text,fontWeight:800,fontSize:16,fontFamily:"'Syne',sans-serif"}}>{title}</h3>
        <button onClick={onClose} style={{background:"none",border:"none",color:T.textMuted,cursor:"pointer",padding:4}}><Ico n="x" s={16}/></button>
      </div>
      <div style={{padding:22}}>{children}</div>
    </div>
  </div>
);

// ─── CONFIRM ──────────────────────────────────────────────────────────────
const Confirm = ({ message, onConfirm, onCancel }) => (
  <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.82)",zIndex:2000,display:"flex",alignItems:"center",justifyContent:"center"}}>
    <div style={{background:T.surface,border:`1px solid ${T.red}40`,borderRadius:14,padding:28,maxWidth:360,width:"100%",textAlign:"center",animation:"modalIn 0.2s ease"}}>
      <div style={{fontSize:32,marginBottom:12}}>⚠️</div>
      <p style={{color:T.text,fontSize:14,marginBottom:20,fontFamily:"'DM Sans',sans-serif",lineHeight:1.6}}>{message}</p>
      <div style={{display:"flex",gap:10,justifyContent:"center"}}>
        <button onClick={onConfirm} style={{background:T.red,color:"#fff",border:"none",borderRadius:8,padding:"9px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>Delete</button>
        <button onClick={onCancel} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:8,padding:"9px 22px",fontSize:13,cursor:"pointer"}}>Cancel</button>
      </div>
    </div>
  </div>
);

// ─── TOAST ────────────────────────────────────────────────────────────────
const Toast = ({ msg, type = "success" }) => (
  <div style={{position:"fixed",bottom:24,right:24,zIndex:3000,background:type==="success"?`${T.green}18`:`${T.red}18`,border:`1px solid ${type==="success"?T.green:T.red}40`,borderRadius:10,padding:"12px 20px",color:type==="success"?T.green:T.red,fontSize:13,fontFamily:"'DM Sans',sans-serif",animation:"fadeUp 0.3s ease",boxShadow:"0 8px 24px rgba(0,0,0,0.4)"}}>
    {type==="success"?"✓":"✗"} {msg}
  </div>
);
function useToast() {
  const [toast, setToast] = useState(null);
  const show = (msg, type="success") => { setToast({msg,type}); setTimeout(()=>setToast(null),3000); };
  return { toast, show };
}

// ─── DATA HOOKS ───────────────────────────────────────────────────────────
const NOTIF_TYPES = ["general","payment_success","task_completed","security_alert","bonus_added","withdrawal_success","kyc_approved","announcement"];
const PRIORITIES  = ["low","medium","high","urgent","critical"];
const CHANNELS    = ["in_app","push","email","sms","all"];

function useNotifications(params = {}) {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([,v])=>v!==undefined))).toString();
      const [data, cnt] = await Promise.all([
        apiFetch(`/api/notifications/notifications/?${q}`),
        apiFetch(`/api/notifications/notifications/count_unread/`),
      ]);
      setNotifications(data.results || data);
      setUnreadCount(cnt.unread_count || 0);
    } catch { setNotifications([]); } finally { setLoading(false); }
  }, [JSON.stringify(params)]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const markAsRead    = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/mark_read/`,{method:"POST"}); fetchAll(); };
  const markAllAsRead = async ()   => { await apiFetch(`/api/notifications/notifications/mark_all_read/`,{method:"POST"}); fetchAll(); show("All marked as read"); };
  const archiveNotif  = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/archive/`,{method:"POST"}); fetchAll(); show("Archived"); };
  const deleteNotif   = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
  const pinNotif      = async (id,isPinned) => { await apiFetch(`/api/notifications/notifications/${id}/${isPinned?"unpin":"pin"}/`,{method:"POST"}); fetchAll(); };
  const updateNotif   = async (id,data) => { await apiFetch(`/api/notifications/notifications/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Updated"); };

  return { notifications, unreadCount, loading, toast, markAsRead, markAllAsRead, archiveNotif, deleteNotif, pinNotif, updateNotif };
}

function useNotificationStats() {
  const [stats, setStats] = useState({total:0,delivered:0,failed:0,unread:0});
  useEffect(()=>{
    apiFetch(`/api/notifications/notifications/summary/`).then(d=>setStats({total:d.total||0,delivered:d.delivered||0,failed:d.failed||0,unread:d.unread||0})).catch(()=>{});
  },[]);
  return stats;
}

function useTemplates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();
  const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/templates/`).then(d=>setTemplates(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(()=>{ fetchAll(); },[]);
  const create = async (data) => { await apiFetch(`/api/notifications/templates/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Template created"); };
  const update = async (id,data) => { await apiFetch(`/api/notifications/templates/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Template updated"); };
  const remove = async (id) => { await apiFetch(`/api/notifications/templates/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
  const clone  = async (id) => { await apiFetch(`/api/notifications/templates/${id}/clone/`,{method:"POST"}); fetchAll(); show("Cloned"); };
  return { templates, loading, toast, create, update, remove, clone };
}

function useCampaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();
  const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/campaigns/`).then(d=>setCampaigns(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(()=>{ fetchAll(); },[]);
  const create = async (data) => { await apiFetch(`/api/notifications/campaigns/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Campaign created"); };
  const update = async (id,data) => { await apiFetch(`/api/notifications/campaigns/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Campaign updated"); };
  const remove = async (id) => { await apiFetch(`/api/notifications/campaigns/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
  const action = async (id,act) => { await apiFetch(`/api/notifications/campaigns/${id}/user_action/`,{method:"POST",body:JSON.stringify({action:act})}); fetchAll(); show(`Campaign ${act}ed`); };
  return { campaigns, loading, toast, create, update, remove,
    start:(id)=>action(id,"start"), pause:(id)=>action(id,"pause"), cancel:(id)=>action(id,"cancel"),
    active:campaigns.filter(c=>c.status==="running"), draft:campaigns.filter(c=>c.status==="draft") };
}

function useNotices() {
  const [notices, setNotices] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();
  const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/notices/`).then(d=>setNotices(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(()=>{ fetchAll(); },[]);
  const create   = async (data) => { await apiFetch(`/api/notifications/notices/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Notice created"); };
  const update   = async (id,data) => { await apiFetch(`/api/notifications/notices/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Notice updated"); };
  const remove   = async (id) => { await apiFetch(`/api/notifications/notices/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
  const publish  = async (id) => { await apiFetch(`/api/notifications/notices/${id}/publish/`,{method:"POST"}); fetchAll(); show("Published"); };
  const unpublish= async (id) => { await apiFetch(`/api/notifications/notices/${id}/unpublish/`,{method:"POST"}); fetchAll(); show("Unpublished"); };
  const archive  = async (id) => { await apiFetch(`/api/notifications/notices/${id}/archive/`,{method:"POST"}); fetchAll(); show("Archived"); };
  return { notices, loading, toast, create, update, remove, publish, unpublish, archive, published:notices.filter(n=>n.is_published) };
}

function useSend() {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const send = async (data) => {
    setSending(true); setError(null);
    try { return await apiFetch(`/api/notifications/admin/notifications/bulk_create/`,{method:"POST",body:JSON.stringify(data)}); }
    catch(e){ setError(e); throw e; } finally { setSending(false); }
  };
  return { send, sending, error };
}

function useAnalytics() {
  const [analytics, setAnalytics] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(()=>{ apiFetch(`/api/notifications/analytics/`).then(d=>setAnalytics(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); },[]);
  const totalSent = analytics.reduce((s,a)=>s+(a.total_sent||0),0);
  const totalRead = analytics.reduce((s,a)=>s+(a.total_read||0),0);
  const avgDel    = analytics.length?(analytics.reduce((s,a)=>s+(a.delivery_rate||0),0)/analytics.length).toFixed(1):0;
  const avgOpen   = analytics.length?(analytics.reduce((s,a)=>s+(a.open_rate||0),0)/analytics.length).toFixed(1):0;
  return { analytics, loading, totalSent, totalRead, avgDel, avgOpen };
}

// ─── EDIT NOTIFICATION MODAL ──────────────────────────────────────────────
const EditNotifModal = ({ notif, onSave, onClose }) => {
  const [form, setForm] = useState({title:notif?.title||"",message:notif?.message||"",priority:notif?.priority||"medium",notification_type:notif?.notification_type||"general",channel:notif?.channel||"in_app"});
  const [saving, setSaving] = useState(false);
  const set = k => v => setForm(p=>({...p,[k]:v}));
  const handleSave = async () => { setSaving(true); try { await onSave(notif.id,form); onClose(); } finally { setSaving(false); } };
  return (
    <Modal title="Edit Notification" onClose={onClose}>
      <div style={{display:"grid",gap:14}}>
        <FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField>
        <FormField label="Message"><TxtArea value={form.message} onChange={set("message")}/></FormField>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
          <FormField label="Type"><SelIn value={form.notification_type} onChange={set("notification_type")} options={NOTIF_TYPES}/></FormField>
          <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
        </div>
        <FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField>
        <div style={{display:"flex",gap:10,marginTop:6}}>
          <button onClick={handleSave} disabled={saving} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 24px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
            {saving?"Saving…":"Save Changes"}
          </button>
          <button onClick={onClose} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
};

// ─── VIEW NOTIFICATION MODAL ──────────────────────────────────────────────
const ViewNotifModal = ({ notif, onClose }) => (
  <Modal title="Notification Detail" onClose={onClose} width={480}>
    <div style={{display:"grid",gap:16}}>
      <div><Lbl c="Title"/><p style={{color:T.text,fontSize:15,fontWeight:600,fontFamily:"'Syne',sans-serif"}}>{notif.title}</p></div>
      <div><Lbl c="Message"/><p style={{color:T.textSub,fontSize:13,lineHeight:1.7,fontFamily:"'DM Sans',sans-serif"}}>{notif.message}</p></div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14}}>
        {[["Type",notif.notification_type],["Priority",notif.priority],["Channel",notif.channel],["Status",notif.status],["Read",notif.is_read?"Yes":"No"],["Pinned",notif.is_pinned?"Yes":"No"]].map(([k,v])=>(
          <div key={k}><Lbl c={k}/><span style={{color:T.text,fontSize:13,fontFamily:"'JetBrains Mono',monospace"}}>{v}</span></div>
        ))}
      </div>
      <div><Lbl c="Created At"/><span style={{color:T.textSub,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{notif.created_at&&new Date(notif.created_at).toLocaleString()}</span></div>
    </div>
  </Modal>
);

// ─── NOTIFICATION ROW ─────────────────────────────────────────────────────
const NotifRow = ({ n, onRead, onArchive, onPin, onDelete, onEdit, onView }) => (
  <div className="row-hover" style={{display:"grid",gridTemplateColumns:"4px 1fr auto",gap:16,padding:"14px 20px",alignItems:"center",background:n.is_read?"transparent":`linear-gradient(90deg,rgba(108,99,255,0.05),transparent)`,borderBottom:`1px solid ${T.border}`,transition:"background 0.2s",animation:"fadeUp 0.3s ease both"}}>
    <div style={{width:4,height:n.is_read?0:26,borderRadius:2,background:`linear-gradient(180deg,${T.accent},${T.purple})`,transition:"height 0.3s",alignSelf:"center"}}/>
    <div onClick={()=>!n.is_read&&onRead(n.id)} style={{cursor:n.is_read?"default":"pointer"}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
        <span style={{color:n.is_read?T.textSub:T.text,fontSize:13,fontWeight:n.is_read?400:600,fontFamily:"'DM Sans',sans-serif"}}>{n.title}</span>
        <Badge p={n.priority}/>
        {n.is_pinned&&<span style={{color:T.yellow,fontSize:11}}>📌</span>}
      </div>
      <div style={{color:T.textMuted,fontSize:12,marginBottom:5,lineHeight:1.5}}>{n.message?.slice(0,90)}{n.message?.length>90?"…":""}</div>
      <div style={{display:"flex",gap:10,alignItems:"center"}}>
        <Dot s={n.status}/>
        <span style={{color:"#3a3a5a",fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{n.notification_type?.replace(/_/g," ")}</span>
        <span style={{color:"#2a2a3a",fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{n.created_at&&new Date(n.created_at).toLocaleString()}</span>
      </div>
    </div>
    <div style={{display:"flex",gap:2}} onClick={e=>e.stopPropagation()}>
      <ActBtn icon="eye"     onClick={()=>onView(n)}               title="View"    color={T.blue}/>
      <ActBtn icon="edit"    onClick={()=>onEdit(n)}               title="Edit"/>
      <ActBtn icon="pin"     onClick={()=>onPin(n.id,n.is_pinned)} title={n.is_pinned?"Unpin":"Pin"} color={n.is_pinned?T.yellow:T.textMuted}/>
      <ActBtn icon="archive" onClick={()=>onArchive(n.id)}         title="Archive"/>
      <ActBtn icon="trash"   onClick={()=>onDelete(n.id)}          title="Delete"  color={T.red}/>
    </div>
  </div>
);

// ─── SEND PANEL ───────────────────────────────────────────────────────────
const SendPanel = () => {
  const { send, sending, error } = useSend();
  const { toast, show } = useToast();
  const [form, setForm] = useState({title:"",message:"",notification_type:"general",priority:"medium",channel:"in_app",user_ids:""});
  const set = k => v => setForm(p=>({...p,[k]:v}));
  const handleSend = async () => {
    try { await send({...form,user_ids:form.user_ids.split(",").map(s=>parseInt(s.trim())).filter(Boolean)}); show("Sent!"); setForm({title:"",message:"",notification_type:"general",priority:"medium",channel:"in_app",user_ids:""}); } catch {}
  };
  const Btn = ({ label }) => (
    <button onClick={handleSend} disabled={sending||!form.user_ids||!form.title} className="btn-hover"
      style={{marginTop:18,background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"11px 28px",fontWeight:700,fontSize:13,cursor:"pointer",display:"flex",alignItems:"center",gap:8,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 20px ${T.accentGlow}`,opacity:sending||!form.user_ids||!form.title?0.5:1}}>
      <Ico n="send" s={14}/>{label}
    </button>
  );
  return (
    <div style={{maxWidth:560,animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      <div style={{marginBottom:24}}>
        <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em",marginBottom:4}}>Send Notification</h3>
        <p style={{color:T.textMuted,fontSize:12}}>Dispatch to one or more users</p>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <div style={{gridColumn:"span 2"}}><FormField label="User IDs (comma separated)"><TxtIn value={form.user_ids} onChange={set("user_ids")} placeholder="1, 2, 3…"/></FormField></div>
        <div style={{gridColumn:"span 2"}}><FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField></div>
        <div style={{gridColumn:"span 2"}}><FormField label="Message"><TxtArea value={form.message} onChange={set("message")}/></FormField></div>
        <FormField label="Type"><SelIn value={form.notification_type} onChange={set("notification_type")} options={NOTIF_TYPES}/></FormField>
        <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
        <div style={{gridColumn:"span 2"}}><FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField></div>
      </div>
      {error&&<div style={{background:`${T.red}12`,border:`1px solid ${T.red}30`,borderRadius:8,padding:"10px 14px",color:T.red,fontSize:12,marginTop:14}}>{JSON.stringify(error)}</div>}
      <Btn label={sending?"Sending…":"Send Notification"}/>
    </div>
  );
};

// ─── TEMPLATES PANEL ──────────────────────────────────────────────────────
const TemplatesPanel = () => {
  const { templates, loading, toast, create, update, remove, clone } = useTemplates();
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [form, setForm] = useState({name:"",title_en:"",message_en:"",template_type:"general",is_active:true});
  const set = k => v => setForm(p=>({...p,[k]:v}));

  const openCreate = () => { setForm({name:"",title_en:"",message_en:"",template_type:"general",is_active:true}); setModal({mode:"create"}); };
  const openEdit   = t => { setForm({name:t.name,title_en:t.title_en||"",message_en:t.message_en||"",template_type:t.template_type||"general",is_active:t.is_active}); setModal({mode:"edit",id:t.id}); };
  const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

  const PrimaryBtn = ({ label }) => (
    <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>{label}</button>
  );

  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
      {modal&&(
        <Modal title={modal.mode==="create"?"New Template":"Edit Template"} onClose={()=>setModal(null)}>
          <div style={{display:"grid",gap:14}}>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <FormField label="Name"><TxtIn value={form.name} onChange={set("name")}/></FormField>
              <FormField label="Type"><SelIn value={form.template_type} onChange={set("template_type")} options={["general","payment","task","security","announcement","promotion"]}/></FormField>
            </div>
            <FormField label="Title (EN)"><TxtIn value={form.title_en} onChange={set("title_en")}/></FormField>
            <FormField label="Message (EN)"><TxtArea value={form.message_en} onChange={set("message_en")}/></FormField>
            <div style={{display:"flex",alignItems:"center",gap:10}}>
              <input type="checkbox" checked={form.is_active} onChange={e=>set("is_active")(e.target.checked)} style={{accentColor:T.accent,width:16,height:16}}/>
              <span style={{color:T.textSub,fontSize:13}}>Active</span>
            </div>
            <div style={{display:"flex",gap:10,marginTop:4}}>
              <PrimaryBtn label={modal.mode==="create"?"Create":"Save Changes"}/>
              <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <div>
          <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Templates</h3>
          <p style={{color:T.textMuted,fontSize:12,marginTop:2}}>{templates.length} templates</p>
        </div>
        <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
          <Ico n="plus" s={13}/> New Template
        </button>
      </div>

      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : templates.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No templates yet</div>
      : (
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(270px,1fr))",gap:14}}>
          {templates.map((t,i)=>(
            <div key={t.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:18,animation:`fadeUp 0.4s ease ${i*50}ms both`,transition:"border-color 0.2s"}}
              onMouseEnter={e=>e.currentTarget.style.borderColor=T.border2}
              onMouseLeave={e=>e.currentTarget.style.borderColor=T.border}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
                <div>
                  <div style={{color:T.text,fontWeight:600,fontSize:13,marginBottom:3,fontFamily:"'Syne',sans-serif"}}>{t.name}</div>
                  <div style={{color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",letterSpacing:"0.08em"}}>{t.template_type}</div>
                </div>
                <span style={{color:t.is_active?T.green:T.textMuted,background:t.is_active?`${T.green}12`:`${T.textMuted}12`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{t.is_active?"ACTIVE":"INACTIVE"}</span>
              </div>
              <div style={{color:T.textSub,fontSize:12,marginBottom:12,lineHeight:1.6}}>{t.title_en}</div>
              <div style={{display:"flex",alignItems:"center",borderTop:`1px solid ${T.border}`,paddingTop:10}}>
                <span style={{color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{t.usage_count||0} uses</span>
                <div style={{marginLeft:"auto",display:"flex",gap:2}}>
                  <ActBtn icon="copy"  onClick={()=>clone(t.id)}  title="Clone"/>
                  <ActBtn icon="edit"  onClick={()=>openEdit(t)}  title="Edit"/>
                  <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Delete "${t.name}"?`,fn:()=>{remove(t.id);setConfirm(null);}})} title="Delete" color={T.red}/>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── CAMPAIGNS PANEL ──────────────────────────────────────────────────────
const CSC = {draft:T.textMuted,scheduled:T.purple,running:T.green,paused:T.yellow,completed:T.blue,cancelled:T.red,failed:T.red};

const CampaignsPanel = () => {
  const { campaigns, loading, toast, create, update, remove, start, pause, cancel, active, draft } = useCampaigns();
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [form, setForm] = useState({name:"",description:"",campaign_type:"promotional",channel:"in_app"});
  const set = k => v => setForm(p=>({...p,[k]:v}));

  const openCreate = () => { setForm({name:"",description:"",campaign_type:"promotional",channel:"in_app"}); setModal({mode:"create"}); };
  const openEdit   = c => { setForm({name:c.name,description:c.description||"",campaign_type:c.campaign_type||"promotional",channel:c.channel||"in_app"}); setModal({mode:"edit",id:c.id}); };
  const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
      {modal&&(
        <Modal title={modal.mode==="create"?"New Campaign":"Edit Campaign"} onClose={()=>setModal(null)}>
          <div style={{display:"grid",gap:14}}>
            <FormField label="Campaign Name"><TxtIn value={form.name} onChange={set("name")}/></FormField>
            <FormField label="Description"><TxtArea value={form.description} onChange={set("description")} rows={2}/></FormField>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <FormField label="Type"><SelIn value={form.campaign_type} onChange={set("campaign_type")} options={["promotional","transactional","educational","alert","reminder","welcome","re_engagement","birthday","holiday","event"]}/></FormField>
              <FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField>
            </div>
            <div style={{display:"flex",gap:10,marginTop:4}}>
              <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>
                {modal.mode==="create"?"Create":"Save Changes"}
              </button>
              <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Campaigns</h3>
        <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
          <Ico n="plus" s={13}/> New Campaign
        </button>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:14,marginBottom:24}}>
        {[{label:"Running",value:active.length,color:T.green},{label:"Draft",value:draft.length,color:T.textMuted},{label:"Total",value:campaigns.length,color:T.accent}].map(s=>(
          <div key={s.label} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"16px 20px",textAlign:"center",borderTop:`2px solid ${s.color}`}}>
            <div style={{color:s.color,fontSize:28,fontWeight:800,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.03em"}}>{s.value}</div>
            <div style={{color:T.textMuted,fontSize:11,marginTop:2,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",letterSpacing:"0.06em"}}>{s.label}</div>
          </div>
        ))}
      </div>

      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : campaigns.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No campaigns yet</div>
      : (
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {campaigns.map((c,i)=>(
            <div key={c.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"16px 20px",display:"grid",gridTemplateColumns:"1fr auto auto",gap:16,alignItems:"center",animation:`fadeUp 0.4s ease ${i*50}ms both`}}>
              <div>
                <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6}}>
                  <span style={{color:T.text,fontWeight:600,fontSize:14,fontFamily:"'Syne',sans-serif"}}>{c.name}</span>
                  <span style={{color:CSC[c.status]||T.textMuted,background:`${CSC[c.status]||T.textMuted}18`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{c.status}</span>
                </div>
                <div style={{display:"flex",gap:18,color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace",marginBottom:c.total_sent>0?8:0}}>
                  <span>Target <span style={{color:T.textSub}}>{c.target_count?.toLocaleString()||0}</span></span>
                  <span>Sent <span style={{color:T.textSub}}>{c.total_sent?.toLocaleString()||0}</span></span>
                  <span>Delivery <span style={{color:T.green}}>{c.delivery_rate?.toFixed(1)||0}%</span></span>
                </div>
                {c.total_sent>0&&c.target_count>0&&(
                  <div style={{background:T.surface2,borderRadius:3,height:3,overflow:"hidden"}}>
                    <div style={{height:"100%",width:`${Math.min(100,(c.total_sent/c.target_count)*100)}%`,background:`linear-gradient(90deg,${CSC[c.status]||T.accent},${T.purple})`,borderRadius:3}}/>
                  </div>
                )}
              </div>
              <div style={{display:"flex",gap:6}}>
                {c.status==="draft"&&<button onClick={()=>start(c.id)} className="btn-hover" style={{background:`${T.green}15`,color:T.green,border:`1px solid ${T.green}30`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="play" s={11}/> Start</button>}
                {c.status==="running"&&<button onClick={()=>pause(c.id)} className="btn-hover" style={{background:`${T.yellow}15`,color:T.yellow,border:`1px solid ${T.yellow}30`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="pause" s={11}/> Pause</button>}
                {["running","paused","scheduled"].includes(c.status)&&<button onClick={()=>cancel(c.id)} className="btn-hover" style={{background:`${T.red}12`,color:T.red,border:`1px solid ${T.red}20`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="stop" s={11}/> Cancel</button>}
              </div>
              <div style={{display:"flex",gap:2}}>
                <ActBtn icon="edit"  onClick={()=>openEdit(c)} title="Edit"/>
                <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Delete campaign "${c.name}"?`,fn:()=>{remove(c.id);setConfirm(null);}})} title="Delete" color={T.red}/>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── NOTICES PANEL ────────────────────────────────────────────────────────
const TYPE_EMOJI = {announcement:"📢",update:"🔄",maintenance:"🔧",promotion:"🎁",warning:"⚠️",information:"ℹ️",emergency:"🚨",holiday:"🎉",event:"📅",news:"📰"};
const BLANK_NOTICE = {title:"",content:"",notice_type:"announcement",priority:"medium",audience:"all"};

const NoticesPanel = () => {
  const { notices, loading, toast, create, update, remove, publish, unpublish, archive, published } = useNotices();
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [form, setForm] = useState(BLANK_NOTICE);
  const set = k => v => setForm(p=>({...p,[k]:v}));

  const openCreate = () => { setForm(BLANK_NOTICE); setModal({mode:"create"}); };
  const openEdit   = n => { setForm({title:n.title,content:n.content||"",notice_type:n.notice_type||"announcement",priority:n.priority||"medium",audience:n.audience||"all"}); setModal({mode:"edit",id:n.id}); };
  const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
      {modal&&(
        <Modal title={modal.mode==="create"?"New Notice":"Edit Notice"} onClose={()=>setModal(null)}>
          <div style={{display:"grid",gap:14}}>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
              <FormField label="Type"><SelIn value={form.notice_type} onChange={set("notice_type")} options={["announcement","update","maintenance","promotion","warning","information","emergency","holiday","event","news"]}/></FormField>
              <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
              <FormField label="Audience"><SelIn value={form.audience} onChange={set("audience")} options={["all","premium","new","active"]}/></FormField>
            </div>
            <FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField>
            <FormField label="Content"><TxtArea value={form.content} onChange={set("content")} rows={4}/></FormField>
            <div style={{display:"flex",gap:10,marginTop:4}}>
              <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>
                {modal.mode==="create"?"Create Notice":"Save Changes"}
              </button>
              <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <div>
          <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Notices</h3>
          <p style={{color:T.textMuted,fontSize:12,marginTop:2}}><span style={{color:T.green}}>{published.length} live</span> · {notices.length} total</p>
        </div>
        <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
          <Ico n="plus" s={13}/> New Notice
        </button>
      </div>

      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : notices.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No notices yet</div>
      : (
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {notices.map((n,i)=>(
            <div key={n.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderLeft:`3px solid ${n.is_published?T.green:"#2a2a3a"}`,borderRadius:12,padding:"16px 20px",animation:`fadeUp 0.4s ease ${i*50}ms both`}}>
              <div style={{display:"grid",gridTemplateColumns:"40px 1fr auto",gap:16,alignItems:"flex-start"}}>
                <div style={{fontSize:26,lineHeight:1,textAlign:"center"}}>{TYPE_EMOJI[n.notice_type]||"📢"}</div>
                <div>
                  <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:5,flexWrap:"wrap"}}>
                    <span style={{color:T.text,fontWeight:600,fontSize:14,fontFamily:"'Syne',sans-serif"}}>{n.title}</span>
                    <Badge p={n.priority}/>
                  </div>
                  <div style={{color:T.textSub,fontSize:12,lineHeight:1.6,marginBottom:8}}>{n.content?.slice(0,140)}{n.content?.length>140?"…":""}</div>
                  <div style={{display:"flex",gap:14,color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>
                    <span>👁 {n.view_count||0}</span><span>✓ {n.acknowledge_count||0}</span><span>Audience: {n.audience}</span>
                  </div>
                </div>
                <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:8}}>
                  <span style={{color:n.is_published?T.green:T.textMuted,background:n.is_published?`${T.green}12`:`${T.textMuted}12`,padding:"2px 10px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{n.is_published?"PUBLISHED":"DRAFT"}</span>
                  <div style={{display:"flex",gap:2}}>
                    {n.is_published?<ActBtn icon="eye" onClick={()=>unpublish(n.id)} title="Unpublish" color={T.yellow}/>:<ActBtn icon="bolt" onClick={()=>publish(n.id)} title="Publish" color={T.green}/>}
                    <ActBtn icon="edit"    onClick={()=>openEdit(n)}   title="Edit"/>
                    <ActBtn icon="archive" onClick={()=>archive(n.id)} title="Archive"/>
                    <ActBtn icon="trash"   onClick={()=>setConfirm({msg:`Delete "${n.title}"?`,fn:()=>{remove(n.id);setConfirm(null);}})} title="Delete" color={T.red}/>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── ANALYTICS PANEL ──────────────────────────────────────────────────────
const AnalyticsPanel = () => {
  const { analytics, loading, totalSent, totalRead, avgDel, avgOpen } = useAnalytics();
  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14,marginBottom:28}}>
        {[{label:"Total Sent",value:totalSent,icon:"send",color:T.accent},{label:"Total Read",value:totalRead,icon:"eye",color:T.green},{label:"Avg Delivery",value:`${avgDel}%`,icon:"check",color:T.yellow},{label:"Avg Open Rate",value:`${avgOpen}%`,icon:"bell",color:T.purple}].map((c,i)=>(
          <div key={c.label} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:"20px 22px",position:"relative",overflow:"hidden",animation:`fadeUp 0.5s ease ${i*80}ms both`}}>
            <div style={{position:"absolute",top:0,left:0,right:0,height:2,background:`linear-gradient(90deg,transparent,${c.color},transparent)`}}/>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}>
              <div style={{width:28,height:28,borderRadius:8,background:`${c.color}18`,display:"flex",alignItems:"center",justifyContent:"center",color:c.color}}><Ico n={c.icon} s={13}/></div>
              <span style={{color:T.textMuted,fontSize:11,fontWeight:600,letterSpacing:"0.08em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>{c.label}</span>
            </div>
            <div style={{fontSize:30,fontWeight:800,color:T.text,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.03em"}}>{typeof c.value==="number"?c.value.toLocaleString():c.value}</div>
          </div>
        ))}
      </div>
      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : analytics.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No analytics data</div>
      : (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,overflow:"hidden"}}>
          <div style={{padding:"12px 20px",background:T.surface2,borderBottom:`1px solid ${T.border}`,display:"grid",gridTemplateColumns:"110px 80px 80px 90px 80px 80px 80px 80px",color:T.textMuted,fontSize:9,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>
            {["Date","Total","Sent","Delivered","Read","Clicked","Failed","Open%"].map(h=><span key={h}>{h}</span>)}
          </div>
          {analytics.slice(0,20).map((a,i)=>(
            <div key={a.date||a.id} style={{padding:"12px 20px",borderBottom:`1px solid ${T.border}`,display:"grid",gridTemplateColumns:"110px 80px 80px 90px 80px 80px 80px 80px",fontSize:12,animation:`fadeUp 0.3s ease ${i*30}ms both`,fontFamily:"'JetBrains Mono',monospace"}}>
              <span style={{color:T.text}}>{a.date}</span>
              <span style={{color:T.textSub}}>{a.total_notifications?.toLocaleString()}</span>
              <span style={{color:T.accent}}>{a.total_sent?.toLocaleString()}</span>
              <span style={{color:T.green}}>{a.total_delivered?.toLocaleString()}</span>
              <span style={{color:T.purple}}>{a.total_read?.toLocaleString()}</span>
              <span style={{color:T.yellow}}>{a.total_clicked?.toLocaleString()}</span>
              <span style={{color:a.total_failed>0?T.red:T.textMuted}}>{a.total_failed?.toLocaleString()}</span>
              <span style={{color:T.green}}>{a.open_rate?.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


// ─── RULES PANEL (Auto Rules) ─────────────────────────────────────────────
function useRules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();
  const fetchAll = async () => {
    setLoading(true);
    try { const d = await apiFetch(`/api/notifications/rules/`); setRules(d.results||d||[]); }
    catch(_) { setRules([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []);
  const create  = async (data) => { try { await apiFetch(`/api/notifications/rules/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Rule created"); } catch(e) { show(e?.detail||"Error","error"); throw e; } };
  const update  = async (id,data) => { try { await apiFetch(`/api/notifications/rules/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Rule updated"); } catch(e) { show(e?.detail||"Error","error"); throw e; } };
  const remove  = async (id) => { try { await apiFetch(`/api/notifications/rules/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); } catch(e) { show(e?.detail||"Error","error"); } };
  const test    = async (id) => { try { const d = await apiFetch(`/api/notifications/rules/${id}/test/`,{method:"POST"}); show("Test triggered!"); return d; } catch(e) { show(e?.detail||"Test failed","error"); } };
  return { rules, loading, toast, create, update, remove, test, fetchAll };
}

const RULE_BLANK = { name:"", description:"", trigger_type:"event", action_type:"send_notification", target_type:"all_users", is_active:true, is_enabled:true };

const RulesPanel = () => {
  const { rules, loading, toast, create, update, remove, test } = useRules();
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(RULE_BLANK);
  const set = k => v => setForm(p=>({...p,[k]:v}));

  const openCreate = () => { setForm(RULE_BLANK); setModal({mode:"create"}); };
  const openEdit   = r => { setForm({name:r.name||"",description:r.description||"",trigger_type:r.trigger_type||"event",action_type:r.action_type||"send_notification",target_type:r.target_type||"all_users",is_active:!!r.is_active,is_enabled:!!r.is_enabled}); setModal({mode:"edit",id:r.id}); };
  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); }
    catch(_) {} finally { setSaving(false); }
  };

  const TRIGGER_COLOR = { event:"#6c63ff", schedule:"#00e87a", condition:"#ffcc00", webhook:"#38bdf8" };

  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
      {modal&&(
        <Modal title={modal.mode==="create"?"New Auto Rule":"Edit Rule"} onClose={()=>setModal(null)}>
          <div style={{display:"grid",gap:14}}>
            <FormField label="Rule Name *"><TxtIn value={form.name} onChange={set("name")} placeholder="e.g. Welcome new users"/></FormField>
            <FormField label="Description"><TxtArea value={form.description} onChange={set("description")} rows={2}/></FormField>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <FormField label="Trigger Type">
                <SelIn value={form.trigger_type} onChange={set("trigger_type")} options={["event","schedule","condition","webhook"]}/>
              </FormField>
              <FormField label="Action">
                <SelIn value={form.action_type} onChange={set("action_type")} options={["send_notification","update_notification","archive_notification","send_email","call_webhook"]}/>
              </FormField>
            </div>
            <FormField label="Target">
              <SelIn value={form.target_type} onChange={set("target_type")} options={["user","user_group","all_users","dynamic"]}/>
            </FormField>
            <div style={{display:"flex",gap:20}}>
              {[["is_active","Active"],["is_enabled","Enabled"]].map(([k,lbl])=>(
                <label key={k} style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",color:T.textSub,fontSize:13}}>
                  <input type="checkbox" checked={!!form[k]} onChange={e=>set(k)(e.target.checked)} style={{accentColor:T.accent,width:15,height:15}}/>
                  {lbl}
                </label>
              ))}
            </div>
            <div style={{display:"flex",gap:10,marginTop:4}}>
              <button onClick={handleSave} disabled={saving||!form.name.trim()} className="btn-hover"
                style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif",opacity:saving||!form.name.trim()?0.5:1}}>
                {saving?"Saving…":modal.mode==="create"?"Create Rule":"Save Changes"}
              </button>
              <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <div>
          <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Auto Rules</h3>
          <p style={{color:T.textMuted,fontSize:12,marginTop:2}}>{rules.filter(r=>r.is_active).length} active · {rules.length} total</p>
        </div>
        <button onClick={openCreate} className="btn-hover"
          style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
          <Ico n="plus" s={13}/> New Rule
        </button>
      </div>

      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : rules.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}><div style={{fontSize:32,marginBottom:8}}>⚙️</div>No auto rules yet</div>
      : (
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {rules.map((r,i)=>(
            <div key={r.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"16px 20px",display:"grid",gridTemplateColumns:"1fr auto",gap:16,alignItems:"center",animation:`fadeUp 0.4s ease ${i*40}ms both`}}>
              <div>
                <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6,flexWrap:"wrap"}}>
                  <span style={{color:T.text,fontWeight:600,fontSize:14,fontFamily:"'Syne',sans-serif"}}>{r.name}</span>
                  <span style={{color:TRIGGER_COLOR[r.trigger_type]||T.accent,background:`${TRIGGER_COLOR[r.trigger_type]||T.accent}15`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",letterSpacing:"0.08em"}}>{r.trigger_type}</span>
                  {r.is_active&&r.is_enabled
                    ? <span style={{color:T.green,background:`${T.green}12`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace"}}>ACTIVE</span>
                    : <span style={{color:T.textMuted,background:`${T.textMuted}12`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace"}}>INACTIVE</span>}
                </div>
                <div style={{display:"flex",gap:16,color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>
                  <span>Triggered: <span style={{color:T.textSub}}>{(r.trigger_count||0).toLocaleString()}</span></span>
                  <span>Success: <span style={{color:T.green}}>{(r.success_count||0).toLocaleString()}</span></span>
                  <span>Failed: <span style={{color:r.failure_count>0?T.red:T.textMuted}}>{(r.failure_count||0).toLocaleString()}</span></span>
                </div>
              </div>
              <div style={{display:"flex",gap:4}}>
                <button onClick={()=>test(r.id)} className="btn-hover" title="Test Rule"
                  style={{background:`${T.yellow}12`,color:T.yellow,border:`1px solid ${T.yellow}25`,borderRadius:7,padding:"6px 10px",fontSize:11,cursor:"pointer",fontWeight:600,fontFamily:"'Syne',sans-serif"}}>Test</button>
                <ActBtn icon="edit"  onClick={()=>openEdit(r)} title="Edit"/>
                <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Delete rule "${r.name}"?`,fn:()=>{remove(r.id);setConfirm(null);}})} title="Delete" color={T.red}/>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── DEVICES PANEL ────────────────────────────────────────────────────────
function useDevices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, show } = useToast();
  const fetchAll = async () => {
    setLoading(true);
    try { const d = await apiFetch(`/api/notifications/device-tokens/`); setDevices(d.results||d||[]); }
    catch(_) { setDevices([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []);
  const remove     = async (id) => { try { await apiFetch(`/api/notifications/device-tokens/${id}/`,{method:"DELETE"}); fetchAll(); show("Device removed"); } catch(e){ show(e?.detail||"Error","error"); } };
  const deactivate = async (id) => { try { await apiFetch(`/api/notifications/device-tokens/${id}/deactivate/`,{method:"POST"}); fetchAll(); show("Deactivated"); } catch(e){ show(e?.detail||"Error","error"); } };
  return { devices, loading, toast, remove, deactivate, fetchAll };
}

const PLATFORM_ICON = { android_app:"🤖", ios_app:"🍎", web:"🌐", progressive_web_app:"💻", api:"⚙️", windows_app:"🪟", mac_app:"🍎" };
const DEVICE_ICON   = { android:"🤖", ios:"🍎", web:"🌐", desktop:"💻", mobile:"📱", tablet:"📋", unknown:"❓" };

const DevicesPanel = () => {
  const { devices, loading, toast, remove, deactivate, fetchAll } = useDevices();
  const [confirm, setConfirm] = useState(null);
  const [search, setSearch] = useState("");

  const filtered = devices.filter(d =>
    !search || (d.device_model||"").toLowerCase().includes(search.toLowerCase()) ||
    (d.device_name||"").toLowerCase().includes(search.toLowerCase()) ||
    (d.platform||"").includes(search)
  );

  return (
    <div style={{animation:"fadeUp 0.4s ease both"}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
        <div>
          <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Device Tokens</h3>
          <p style={{color:T.textMuted,fontSize:12,marginTop:2}}>{devices.filter(d=>d.is_active).length} active · {devices.length} total</p>
        </div>
        <button onClick={fetchAll} className="btn-hover" style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"8px 16px",fontSize:12,cursor:"pointer",display:"flex",alignItems:"center",gap:6}}>
          ⟳ Refresh
        </button>
      </div>

      <div style={{marginBottom:16}}>
        <input className="inp" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by model, name, platform…"
          style={{...IS,maxWidth:340}}/>
      </div>

      {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
      : filtered.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}><div style={{fontSize:32,marginBottom:8}}>📱</div>No devices found</div>
      : (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,overflow:"hidden"}}>
          <div style={{display:"grid",gridTemplateColumns:"36px 1fr 100px 90px 80px 100px",gap:12,padding:"10px 18px",background:T.surface2,borderBottom:`1px solid ${T.border}`,color:T.textMuted,fontSize:9,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.1em",fontFamily:"'JetBrains Mono',monospace"}}>
            {["","Device","Platform","OS","Status","Actions"].map(h=><span key={h}>{h}</span>)}
          </div>
          {filtered.map((d,i)=>(
            <div key={d.id} style={{display:"grid",gridTemplateColumns:"36px 1fr 100px 90px 80px 100px",gap:12,padding:"13px 18px",borderBottom:`1px solid ${T.border}`,fontSize:12,animation:`fadeUp 0.3s ease ${i*30}ms both`,alignItems:"center"}}>
              <div style={{fontSize:20,textAlign:"center"}}>{DEVICE_ICON[d.device_type]||"📱"}</div>
              <div>
                <div style={{color:T.text,fontWeight:600,fontSize:13}}>{d.device_name||d.device_model||"Unknown Device"}</div>
                <div style={{color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace",marginTop:2}}>{d.token?.slice(0,24)}…</div>
              </div>
              <span style={{color:T.textSub,fontFamily:"'JetBrains Mono',monospace",fontSize:11}}>{PLATFORM_ICON[d.platform]||"🌐"} {d.platform?.replace(/_/g," ")}</span>
              <span style={{color:T.textMuted,fontSize:11}}>{d.os_version||"—"}</span>
              <span style={{color:d.is_active?T.green:T.red,background:d.is_active?`${T.green}12`:`${T.red}12`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace"}}>{d.is_active?"ACTIVE":"OFF"}</span>
              <div style={{display:"flex",gap:2}}>
                {d.is_active&&<ActBtn icon="pause" onClick={()=>deactivate(d.id)} title="Deactivate" color={T.yellow}/>}
                <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Remove this device?`,fn:()=>{remove(d.id);setConfirm(null);}})} title="Remove" color={T.red}/>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── PREFERENCES PANEL ────────────────────────────────────────────────────
function usePreferences() {
  const [prefs, setPrefs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast, show } = useToast();
  useEffect(() => {
    apiFetch(`/api/notifications/preferences/`)
      .then(d => setPrefs(d.results?.[0]||d[0]||d||null))
      .catch(() => setPrefs(null))
      .finally(() => setLoading(false));
  }, []);
  const save = async (data) => {
    setSaving(true);
    try {
      if (prefs?.id) { await apiFetch(`/api/notifications/preferences/${prefs.id}/`,{method:"PATCH",body:JSON.stringify(data)}); }
      else { await apiFetch(`/api/notifications/preferences/`,{method:"POST",body:JSON.stringify(data)}); }
      show("Preferences saved!"); setPrefs(p=>({...p,...data}));
    } catch(e) { show(e?.detail||"Error","error"); throw e; }
    finally { setSaving(false); }
  };
  const reset = async () => {
    if (!prefs?.id) return;
    try { await apiFetch(`/api/notifications/preferences/${prefs.id}/reset/`,{method:"POST"}); show("Reset to defaults"); window.location.reload(); }
    catch(e){ show(e?.detail||"Error","error"); }
  };
  return { prefs, loading, saving, toast, save, reset };
}

const PreferencesPanel = () => {
  const { prefs, loading, saving, toast, save, reset } = usePreferences();
  const [form, setForm] = useState(null);
  const [confirm, setConfirm] = useState(null);

  useEffect(() => {
    if (prefs) setForm({
      enable_in_app: !!prefs.enable_in_app,
      enable_push: !!prefs.enable_push,
      enable_email: !!prefs.enable_email,
      enable_sms: !!prefs.enable_sms,
      enable_telegram: !!prefs.enable_telegram,
      enable_whatsapp: !!prefs.enable_whatsapp,
      enable_browser: !!prefs.enable_browser,
      enable_system_notifications: !!prefs.enable_system_notifications,
      enable_financial_notifications: !!prefs.enable_financial_notifications,
      enable_task_notifications: !!prefs.enable_task_notifications,
      enable_security_notifications: !!prefs.enable_security_notifications,
      enable_marketing_notifications: !!prefs.enable_marketing_notifications,
      enable_social_notifications: !!prefs.enable_social_notifications,
      enable_achievement_notifications: !!prefs.enable_achievement_notifications,
      sound_enabled: !!prefs.sound_enabled,
      vibration_enabled: !!prefs.vibration_enabled,
      quiet_hours_enabled: !!prefs.quiet_hours_enabled,
      do_not_disturb: !!prefs.do_not_disturb,
      max_notifications_per_day: prefs.max_notifications_per_day||50,
    });
  }, [prefs]);

  if (loading) return <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>;

  const toggle = (k) => setForm(p => p ? {...p,[k]:!p[k]} : p);
  const Toggle = ({k, label, desc}) => (
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"12px 0",borderBottom:`1px solid ${T.border}`}}>
      <div>
        <div style={{color:T.text,fontSize:13,fontWeight:500}}>{label}</div>
        {desc&&<div style={{color:T.textMuted,fontSize:11,marginTop:2}}>{desc}</div>}
      </div>
      <div onClick={()=>toggle(k)} style={{width:42,height:24,borderRadius:12,background:form?.[k]?T.accent:T.surface3,cursor:"pointer",transition:"background 0.2s",position:"relative",flexShrink:0,boxShadow:form?.[k]?`0 0 12px ${T.accentGlow}`:""}} >
        <div style={{position:"absolute",top:3,left:form?.[k]?19:3,width:18,height:18,borderRadius:"50%",background:"#fff",transition:"left 0.2s",boxShadow:"0 1px 4px rgba(0,0,0,0.4)"}}/>
      </div>
    </div>
  );

  const Section = ({title, children}) => (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:"20px 22px",marginBottom:16}}>
      <h4 style={{color:T.textSub,fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",marginBottom:14}}>{title}</h4>
      {children}
    </div>
  );

  return (
    <div style={{animation:"fadeUp 0.4s ease both",maxWidth:600}}>
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <div>
          <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Preferences</h3>
          <p style={{color:T.textMuted,fontSize:12,marginTop:2}}>Notification delivery preferences</p>
        </div>
        <div style={{display:"flex",gap:8}}>
          <button onClick={()=>setConfirm({msg:"Reset all preferences to defaults?",fn:()=>{reset();setConfirm(null);}})}
            style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"8px 16px",fontSize:12,cursor:"pointer"}}>Reset</button>
          <button onClick={()=>form&&save(form)} disabled={saving||!form} className="btn-hover"
            style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"8px 20px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"'Syne',sans-serif",opacity:saving||!form?0.6:1}}>
            {saving?"Saving…":"Save"}
          </button>
        </div>
      </div>

      {form && <>
        <Section title="📡 Delivery Channels">
          {[["enable_in_app","In-App","Show inside the app"],["enable_push","Push Notification","Mobile/Desktop push"],["enable_email","Email","Send to email address"],["enable_sms","SMS","Text message"],["enable_telegram","Telegram","Telegram bot"],["enable_whatsapp","WhatsApp","WhatsApp message"],["enable_browser","Browser Push","Web browser notifications"]].map(([k,lbl,desc])=>
            <Toggle key={k} k={k} label={lbl} desc={desc}/>
          )}
        </Section>

        <Section title="🗂️ Notification Types">
          {[["enable_system_notifications","System","Updates, maintenance, announcements"],["enable_financial_notifications","Financial","Payments, withdrawals, wallet"],["enable_task_notifications","Tasks","Task assignments, completions"],["enable_security_notifications","Security","Login alerts, fraud detection"],["enable_marketing_notifications","Marketing","Promotions, offers, discounts"],["enable_social_notifications","Social","Friends, messages, mentions"],["enable_achievement_notifications","Achievements","Badges, levels, contests"]].map(([k,lbl,desc])=>
            <Toggle key={k} k={k} label={lbl} desc={desc}/>
          )}
        </Section>

        <Section title="🔔 Sound & Vibration">
          <Toggle k="sound_enabled" label="Sound" desc="Play notification sound"/>
          <Toggle k="vibration_enabled" label="Vibration" desc="Vibrate on notification"/>
        </Section>

        <Section title="🌙 Do Not Disturb">
          <Toggle k="quiet_hours_enabled" label="Quiet Hours" desc="Silence during set times"/>
          <Toggle k="do_not_disturb" label="Do Not Disturb" desc="Pause all notifications now"/>
          <div style={{paddingTop:14}}>
            <Lbl c="Max per day"/>
            <input type="number" className="inp" value={form.max_notifications_per_day||50}
              onChange={e=>setForm(p=>p?{...p,max_notifications_per_day:parseInt(e.target.value)||50}:p)}
              style={{...IS,maxWidth:160}} min={1} max={500}/>
          </div>
        </Section>
      </>}
    </div>
  );
};

// ─── SEND NOTIFICATION (enhanced) ─────────────────────────────────────────
// useSend, SendPanel already exist above — keep as is
// Enhanced with better validation already + error display

// ─── BULK ACTION HANDLER (Inbox) ─────────────────────────────────────────
function useBulkAction(refetch, show) {
  const bulkAction = async (ids, action) => {
    if (!ids.length) return;
    try {
      await apiFetch(`/api/notifications/notifications/bulk_action/`, {
        method: "POST",
        body: JSON.stringify({ ids, action }),
      });
      refetch();
      show(`${ids.length} notifications ${action}ed`);
    } catch(e) {
      show(e?.detail||`Bulk ${action} failed`, "error");
    }
  };
  const bulkDelete = async (ids) => {
    try {
      await apiFetch(`/api/notifications/notifications/bulk_delete/`, {
        method: "POST",
        body: JSON.stringify({ ids }),
      });
      refetch();
      show(`${ids.length} deleted`);
    } catch(e) { show(e?.detail||"Bulk delete failed","error"); }
  };
  return { bulkAction, bulkDelete };
}

// ─── TABS ─────────────────────────────────────────────────────────────────
const TABS = [
  {id:"inbox",      label:"Inbox",        icon:"bell"},
  {id:"send",       label:"Send",         icon:"send"},
  {id:"templates",  label:"Templates",    icon:"template"},
  {id:"campaigns",  label:"Campaigns",    icon:"campaign"},
  {id:"notices",    label:"Notices",      icon:"notice"},
  {id:"rules",      label:"Auto Rules",   icon:"bolt"},
  {id:"devices",    label:"Devices",      icon:"pin"},
  {id:"preferences",label:"Preferences",  icon:"check"},
  {id:"analytics",  label:"Analytics",    icon:"chart"},
];

// ─── MAIN ─────────────────────────────────────────────────────────────────
export default function NotificationsPage() {
  const [activeTab,  setActiveTab]  = useState("inbox");
  const [filter,     setFilter]     = useState("all");
  const [search,     setSearch]     = useState("");
  const [editModal,  setEditModal]  = useState(null);
  const [viewModal,  setViewModal]  = useState(null);
  const [confirmDel, setConfirmDel] = useState(null);
  const [selected,   setSelected]   = useState([]);

  const fp = filter==="unread"?{is_read:false}:filter==="pinned"?{is_pinned:true}:filter==="archived"?{is_archived:true}:{};
  const { notifications, unreadCount, loading, toast, markAsRead, markAllAsRead, archiveNotif, deleteNotif, pinNotif, updateNotif } = useNotifications(fp);
  const stats = useNotificationStats();
  const { bulkAction, bulkDelete } = useBulkAction(()=>{}, ()=>{});

  // Filtered by search
  const visibleNotifs = notifications.filter(n =>
    !search || n.title?.toLowerCase().includes(search.toLowerCase()) || n.message?.toLowerCase().includes(search.toLowerCase())
  );

  const allSelected = visibleNotifs.length > 0 && selected.length === visibleNotifs.length;
  const toggleSelectAll = () => setSelected(allSelected ? [] : visibleNotifs.map(n=>n.id));
  const toggleSelect = (id) => setSelected(p => p.includes(id) ? p.filter(x=>x!==id) : [...p,id]);

  const handleBulkRead   = async () => { await bulkAction(selected,"read");    setSelected([]); };
  const handleBulkDel    = async () => { await bulkDelete(selected);           setSelected([]); };
  const handleBulkArchive= async () => { await bulkAction(selected,"archive"); setSelected([]); };

  return (
    <>
      <GS/>
        <PageEndpointPanel pageKey="Notifications" title="Notifications Endpoints" />
      {toast&&<Toast msg={toast.msg} type={toast.type}/>}
      {editModal&&<EditNotifModal notif={editModal} onSave={updateNotif} onClose={()=>setEditModal(null)}/>}
      {viewModal&&<ViewNotifModal notif={viewModal} onClose={()=>setViewModal(null)}/>}
      {confirmDel&&(
        <Confirm
          message={typeof confirmDel==="object"&&confirmDel.bulk
            ? `Delete ${confirmDel.ids.length} notifications?`
            : "Delete this notification?"}
          onConfirm={async()=>{
            if (typeof confirmDel==="object"&&confirmDel.bulk) {
              await handleBulkDel();
            } else {
              await deleteNotif(typeof confirmDel==="object"?confirmDel.id:confirmDel);
            }
            setConfirmDel(null);
          }}
          onCancel={()=>setConfirmDel(null)}
        />
      )}

      <div style={{minHeight:"100vh",background:T.bg,color:T.text,fontFamily:"'DM Sans',sans-serif",padding:"28px 32px"}}>

        {/* HEADER */}
        <div style={{marginBottom:28,animation:"fadeUp 0.5s ease both"}}>
          <div style={{display:"flex",alignItems:"flex-start",gap:16,marginBottom:14}}>
            <div style={{width:46,height:46,borderRadius:14,flexShrink:0,background:`linear-gradient(135deg,${T.accent},${T.purple})`,display:"flex",alignItems:"center",justifyContent:"center",boxShadow:`0 8px 24px ${T.accentGlow}`}}>
              <Ico n="bell" s={20}/>
            </div>
            <div style={{flex:1}}>
              <h1 style={{fontSize:24,fontWeight:800,color:T.text,letterSpacing:"-0.03em",margin:0,fontFamily:"'Syne',sans-serif"}}>Notifications</h1>
              <p style={{color:T.textMuted,fontSize:12,margin:"3px 0 0"}}>Manage notifications, campaigns, rules & devices</p>
            </div>
            {unreadCount>0&&(
              <div style={{background:T.red,color:"#fff",borderRadius:20,padding:"4px 12px",fontSize:12,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",boxShadow:`0 4px 12px ${T.red}40`,animation:"pulse 2s ease infinite"}}>
                {unreadCount} unread
              </div>
            )}
          </div>
          {/* STATS BAR */}
          <div style={{display:"flex",gap:24,paddingLeft:62}}>
            {[
              {label:"Total",    value:stats.total,     color:T.textSub},
              {label:"Delivered",value:stats.delivered, color:T.green},
              {label:"Failed",   value:stats.failed,    color:T.red},
              {label:"Unread",   value:stats.unread||unreadCount, color:T.accent},
            ].map(s=>(
              <div key={s.label} style={{display:"flex",alignItems:"flex-end",gap:6}}>
                <span style={{color:s.color,fontWeight:800,fontSize:15,fontFamily:"'Syne',sans-serif"}}>{(s.value||0).toLocaleString()}</span>
                <span style={{color:T.textMuted,fontSize:11,paddingBottom:1,fontFamily:"'JetBrains Mono',monospace"}}>{s.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* TABS */}
        <div style={{display:"flex",gap:2,marginBottom:26,background:T.surface,borderRadius:14,padding:5,border:`1px solid ${T.border}`,flexWrap:"wrap"}}>
          {TABS.map(tab=>(
            <button key={tab.id} onClick={()=>setActiveTab(tab.id)}
              style={{flex:"0 0 auto",display:"flex",alignItems:"center",justifyContent:"center",gap:6,padding:"8px 13px",borderRadius:9,border:"none",cursor:"pointer",fontSize:11,fontWeight:600,transition:"all 0.2s",fontFamily:"'Syne',sans-serif",background:activeTab===tab.id?`linear-gradient(135deg,${T.accent},${T.purple})`:"transparent",color:activeTab===tab.id?"#fff":T.textMuted,boxShadow:activeTab===tab.id?`0 4px 12px ${T.accentGlow}`:"none",whiteSpace:"nowrap"}}>
              <Ico n={tab.icon} s={12}/>
              <span>{tab.label}</span>
              {tab.id==="inbox"&&unreadCount>0&&(
                <span style={{background:activeTab==="inbox"?"rgba(255,255,255,0.25)":T.red,color:"#fff",borderRadius:10,padding:"1px 7px",fontSize:9,fontWeight:800,fontFamily:"'JetBrains Mono',monospace"}}>{unreadCount}</span>
              )}
            </button>
          ))}
        </div>

        {/* ── INBOX TAB ── */}
        {activeTab==="inbox"&&(
          <div style={{animation:"fadeUp 0.4s ease both"}}>
            {/* Filter + Search + Bulk Bar */}
            <div style={{display:"flex",gap:8,marginBottom:14,alignItems:"center",flexWrap:"wrap"}}>
              {[{id:"all",label:"All"},{id:"unread",label:"Unread"},{id:"pinned",label:"Pinned"},{id:"archived",label:"Archived"}].map(f=>(
                <button key={f.id} onClick={()=>{setFilter(f.id);setSelected([]);}} className="pill"
                  style={{background:filter===f.id?`${T.accent}20`:T.surface,color:filter===f.id?T.accent:T.textMuted,border:`1px solid ${filter===f.id?T.accent+"50":T.border}`,borderRadius:20,padding:"5px 15px",fontSize:11,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace",fontWeight:600,letterSpacing:"0.04em",transition:"all 0.2s"}}>
                  {f.label}
                </button>
              ))}
              <input className="inp" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search…"
                style={{...IS,width:200,padding:"5px 12px",fontSize:12}}/>
              {unreadCount>0&&(
                <button onClick={markAllAsRead} className="btn-hover"
                  style={{marginLeft:"auto",background:`${T.green}12`,color:T.green,border:`1px solid ${T.green}30`,borderRadius:8,padding:"6px 14px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",fontWeight:600}}>
                  <Ico n="check" s={12}/> Mark all read
                </button>
              )}
            </div>

            {/* Bulk Actions Bar */}
            {selected.length>0&&(
              <div style={{background:`${T.accent}12`,border:`1px solid ${T.accent}30`,borderRadius:10,padding:"10px 16px",marginBottom:12,display:"flex",alignItems:"center",gap:10,animation:"fadeUp 0.2s ease both"}}>
                <span style={{color:T.accent,fontSize:12,fontWeight:600,fontFamily:"'Syne',sans-serif"}}>{selected.length} selected</span>
                <div style={{marginLeft:"auto",display:"flex",gap:8}}>
                  <button onClick={handleBulkRead}    className="btn-hover" style={{background:`${T.green}12`,color:T.green,border:`1px solid ${T.green}25`,borderRadius:7,padding:"5px 12px",fontSize:11,cursor:"pointer",fontWeight:600}}>Mark Read</button>
                  <button onClick={handleBulkArchive} className="btn-hover" style={{background:`${T.yellow}12`,color:T.yellow,border:`1px solid ${T.yellow}25`,borderRadius:7,padding:"5px 12px",fontSize:11,cursor:"pointer",fontWeight:600}}>Archive</button>
                  <button onClick={()=>setConfirmDel({bulk:true,ids:selected})} className="btn-hover" style={{background:`${T.red}12`,color:T.red,border:`1px solid ${T.red}25`,borderRadius:7,padding:"5px 12px",fontSize:11,cursor:"pointer",fontWeight:600}}>Delete</button>
                  <button onClick={()=>setSelected([])} style={{background:"transparent",color:T.textMuted,border:"none",fontSize:18,cursor:"pointer",lineHeight:1,padding:"0 4px"}}>✕</button>
                </div>
              </div>
            )}

            {/* Notifications List */}
            <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,overflow:"hidden"}}>
              {/* Select All Row */}
              {visibleNotifs.length>0&&(
                <div style={{padding:"8px 18px",borderBottom:`1px solid ${T.border}`,display:"flex",alignItems:"center",gap:10,background:T.surface2}}>
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} style={{accentColor:T.accent,width:14,height:14,cursor:"pointer"}}/>
                  <span style={{color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>Select All ({visibleNotifs.length})</span>
                </div>
              )}

              {loading ? (
                <div style={{padding:64,textAlign:"center",color:T.textMuted,animation:"pulse 1.5s ease infinite",fontSize:13}}>Loading…</div>
              ) : visibleNotifs.length===0 ? (
                <div style={{padding:64,textAlign:"center"}}>
                  <div style={{fontSize:36,marginBottom:12}}>🔔</div>
                  <div style={{color:T.textMuted,fontSize:14}}>{search?"No results found":"No notifications"}</div>
                </div>
              ) : visibleNotifs.map(n=>(
                <div key={n.id} className="row-hover"
                  style={{display:"grid",gridTemplateColumns:"30px 4px 1fr auto",gap:12,padding:"13px 18px",alignItems:"center",background:n.is_read?"transparent":`linear-gradient(90deg,rgba(108,99,255,0.04),transparent)`,borderBottom:`1px solid ${T.border}`,transition:"background 0.2s",animation:"fadeUp 0.3s ease both"}}>

                  {/* Checkbox */}
                  <input type="checkbox" checked={selected.includes(n.id)} onChange={()=>toggleSelect(n.id)}
                    onClick={e=>e.stopPropagation()} style={{accentColor:T.accent,width:14,height:14,cursor:"pointer"}}/>

                  {/* Unread indicator */}
                  <div style={{width:4,height:n.is_read?0:24,borderRadius:2,background:`linear-gradient(180deg,${T.accent},${T.purple})`,transition:"height 0.3s",alignSelf:"center"}}/>

                  {/* Content */}
                  <div onClick={()=>!n.is_read&&markAsRead(n.id)} style={{cursor:n.is_read?"default":"pointer",minWidth:0}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:3,flexWrap:"wrap"}}>
                      <span style={{color:n.is_read?T.textSub:T.text,fontSize:13,fontWeight:n.is_read?400:600,fontFamily:"'DM Sans',sans-serif",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:380}}>{n.title||"(no title)"}</span>
                      <Badge p={n.priority}/>
                      {n.is_pinned&&<span style={{color:T.yellow,fontSize:11}}>📌</span>}
                    </div>
                    <div style={{color:T.textMuted,fontSize:12,marginBottom:4,lineHeight:1.5,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:520}}>{n.message||""}</div>
                    <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
                      <Dot s={n.status}/>
                      <span style={{color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{(n.notification_type||"").replace(/_/g," ")}</span>
                      <span style={{color:"#2a2a3a",fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{n.created_at&&new Date(n.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{display:"flex",gap:2}} onClick={e=>e.stopPropagation()}>
                    <ActBtn icon="eye"     onClick={()=>setViewModal(n)}                    title="View Detail"    color={T.blue}/>
                    <ActBtn icon="edit"    onClick={()=>setEditModal(n)}                    title="Edit"/>
                    <ActBtn icon="pin"     onClick={()=>pinNotif(n.id,n.is_pinned)}         title={n.is_pinned?"Unpin":"Pin"} color={n.is_pinned?T.yellow:T.textMuted}/>
                    <ActBtn icon="archive" onClick={()=>archiveNotif(n.id)}                 title="Archive"/>
                    <ActBtn icon="trash"   onClick={()=>setConfirmDel({id:n.id})}           title="Delete"         color={T.red}/>
                  </div>
                </div>
              ))}
            </div>

            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:10,color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace"}}>
              <span>Showing {visibleNotifs.length} notification{visibleNotifs.length!==1?"s":""}</span>
              {selected.length>0&&<span style={{color:T.accent}}>{selected.length} selected</span>}
            </div>
          </div>
        )}

        {activeTab==="send"        && <SendPanel/>}
        {activeTab==="templates"   && <TemplatesPanel/>}
        {activeTab==="campaigns"   && <CampaignsPanel/>}
        {activeTab==="notices"     && <NoticesPanel/>}
        {activeTab==="rules"       && <RulesPanel/>}
        {activeTab==="devices"     && <DevicesPanel/>}
        {activeTab==="preferences" && <PreferencesPanel/>}
        {activeTab==="analytics"   && <AnalyticsPanel/>}

      </div>
    </>
  );
}



// // NotificationsPage.jsx — Full CRUD
// // API: http://localhost:8000/api/notifications/

// import { useState, useEffect, useCallback } from "react";

// // ─── API ──────────────────────────────────────────────────────────────────
// const API_BASE = "http://localhost:8000";
// const getToken = () => localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || localStorage.getItem("token") || "";
// const apiFetch = async (path, opts = {}) => {
//   const token = getToken();
//   const res = await fetch(`${API_BASE}${path}`, {
//     headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers },
//     ...opts,
//   });
//   if (res.status === 204) return {};
//   if (!res.ok) { const e = await res.json().catch(() => ({})); throw e; }
//   return res.json();
// };

// // ─── DESIGN TOKENS ───────────────────────────────────────────────────────
// const T = {
//   bg: "#060608", surface: "#0d0d12", surface2: "#13131a", surface3: "#1a1a24",
//   border: "rgba(255,255,255,0.06)", border2: "rgba(255,255,255,0.1)",
//   text: "#e8e8f0", textSub: "#8888a8", textMuted: "#5a5a72",
//   accent: "#6c63ff", accentGlow: "rgba(108,99,255,0.25)",
//   green: "#00e87a", red: "#ff3d5a", yellow: "#ffcc00", purple: "#c084fc", blue: "#38bdf8",
// };

// // ─── GLOBAL STYLES ────────────────────────────────────────────────────────
// const GS = () => (
//   <style>{`
//     @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');
//     *{box-sizing:border-box;margin:0;padding:0;}
//     ::-webkit-scrollbar{width:4px;height:4px;}
//     ::-webkit-scrollbar-thumb{background:rgba(108,99,255,0.3);border-radius:2px;}
//     select option{background:#13131a;color:#e8e8f0;}
//     input::placeholder,textarea::placeholder{color:#3a3a52;}
//     @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
//     @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
//     @keyframes modalIn{from{opacity:0;transform:scale(0.96)}to{opacity:1;transform:scale(1)}}
//     .row-hover:hover{background:rgba(108,99,255,0.04)!important;}
//     .btn-hover:hover{opacity:0.85!important;}
//     .act-btn:hover{background:rgba(255,255,255,0.07)!important;color:#e8e8f0!important;}
//     .pill:hover{border-color:rgba(108,99,255,0.4)!important;}
//     .inp:focus{border-color:#6c63ff!important;outline:none;}
//   `}</style>
// );

// // ─── ICONS ────────────────────────────────────────────────────────────────
// const IC = {
//   bell:"M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
//   send:"M22 2L11 13 M22 2L15 22 11 13 2 9l20-7z",
//   template:"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
//   campaign:"M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z",
//   notice:"M11 21H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h5 M13 3h5a2 2 0 0 1 2 2v5 M13 3l8 8-8 8",
//   chart:"M18 20V10 M12 20V4 M6 20v-6",
//   check:"M20 6L9 17l-5-5",
//   pin:"M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z M12 7v6 M12 16h.01",
//   archive:"M21 8v13H3V8 M1 3h22v5H1z M10 12h4",
//   trash:"M3 6h18 M19 6l-1 14H6L5 6 M8 6V4h8v2",
//   plus:"M12 5v14 M5 12h14",
//   edit:"M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
//   eye:"M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
//   play:"M5 3l14 9-14 9V3z",
//   pause:"M6 4h4v16H6z M14 4h4v16h-4z",
//   stop:"M18 6H6v12h12z",
//   bolt:"M13 2L3 14h9l-1 8 10-12h-9l1-8z",
//   x:"M18 6L6 18 M6 6l12 12",
//   copy:"M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
// };
// const Ico = ({ n, s = 16 }) => (
//   <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
//     {(IC[n] || "").split(" M").map((d, i) => <path key={i} d={i === 0 ? d : "M" + d} />)}
//   </svg>
// );

// // ─── SMALL UI COMPONENTS ──────────────────────────────────────────────────
// const PC = {
//   critical:{color:"#ff3d5a",bg:"rgba(255,61,90,0.12)",label:"CRITICAL"},
//   urgent:{color:"#ff8c42",bg:"rgba(255,140,66,0.12)",label:"URGENT"},
//   high:{color:"#ffcc00",bg:"rgba(255,204,0,0.12)",label:"HIGH"},
//   medium:{color:"#00e87a",bg:"rgba(0,232,122,0.12)",label:"MEDIUM"},
//   low:{color:"#5a5a72",bg:"rgba(90,90,114,0.15)",label:"LOW"},
// };
// const Badge = ({ p }) => { const c = PC[p] || PC.medium; return (
//   <span style={{color:c.color,background:c.bg,padding:"2px 7px",borderRadius:3,fontSize:9,fontWeight:700,letterSpacing:"0.1em",fontFamily:"'JetBrains Mono',monospace",border:`1px solid ${c.color}30`}}>{c.label}</span>
// );};

// const SC = {sent:T.green,delivered:T.blue,read:T.textMuted,failed:T.red,pending:T.yellow,scheduled:T.purple,draft:"#3a3a4a",cancelled:T.red};
// const Dot = ({ s }) => <span style={{display:"inline-block",width:6,height:6,borderRadius:"50%",background:SC[s]||T.textMuted,boxShadow:`0 0 5px ${SC[s]||T.textMuted}80`,flexShrink:0}} />;

// const IS = {width:"100%",background:T.surface2,border:`1px solid ${T.border2}`,borderRadius:8,padding:"9px 13px",color:T.text,fontSize:13,outline:"none",boxSizing:"border-box",fontFamily:"'DM Sans',sans-serif",transition:"border-color 0.2s"};
// const Lbl = ({ c }) => <label style={{display:"block",color:T.textMuted,fontSize:10,fontWeight:600,letterSpacing:"0.1em",textTransform:"uppercase",marginBottom:6,fontFamily:"'JetBrains Mono',monospace"}}>{c}</label>;
// const ActBtn = ({ icon, onClick, title, color = T.textMuted }) => (
//   <button className="act-btn" onClick={onClick} title={title} style={{background:"none",border:"none",color,cursor:"pointer",padding:"5px 7px",borderRadius:6,transition:"all 0.15s",display:"flex",alignItems:"center"}}>
//     <Ico n={icon} s={13} />
//   </button>
// );
// const FormField = ({ label, children }) => <div><Lbl c={label} />{children}</div>;
// const TxtIn = ({ value, onChange, placeholder = "" }) => <input className="inp" value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} style={IS} />;
// const SelIn = ({ value, onChange, options }) => (
//   <select className="inp" value={value} onChange={e=>onChange(e.target.value)} style={IS}>
//     {options.map(o => <option key={o} value={o}>{o.replace(/_/g," ")}</option>)}
//   </select>
// );
// const TxtArea = ({ value, onChange, rows = 3 }) => <textarea className="inp" value={value} onChange={e=>onChange(e.target.value)} rows={rows} style={{...IS,resize:"vertical"}} />;

// // ─── MODAL ────────────────────────────────────────────────────────────────
// const Modal = ({ title, onClose, children, width = 520 }) => (
//   <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.78)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center",padding:20}} onClick={onClose}>
//     <div style={{background:T.surface,border:`1px solid ${T.border2}`,borderRadius:16,width:"100%",maxWidth:width,maxHeight:"88vh",overflow:"auto",animation:"modalIn 0.2s ease both"}} onClick={e=>e.stopPropagation()}>
//       <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"18px 22px",borderBottom:`1px solid ${T.border}`}}>
//         <h3 style={{color:T.text,fontWeight:800,fontSize:16,fontFamily:"'Syne',sans-serif"}}>{title}</h3>
//         <button onClick={onClose} style={{background:"none",border:"none",color:T.textMuted,cursor:"pointer",padding:4}}><Ico n="x" s={16}/></button>
//       </div>
//       <div style={{padding:22}}>{children}</div>
//     </div>
//   </div>
// );

// // ─── CONFIRM ──────────────────────────────────────────────────────────────
// const Confirm = ({ message, onConfirm, onCancel }) => (
//   <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.82)",zIndex:2000,display:"flex",alignItems:"center",justifyContent:"center"}}>
//     <div style={{background:T.surface,border:`1px solid ${T.red}40`,borderRadius:14,padding:28,maxWidth:360,width:"100%",textAlign:"center",animation:"modalIn 0.2s ease"}}>
//       <div style={{fontSize:32,marginBottom:12}}>⚠️</div>
//       <p style={{color:T.text,fontSize:14,marginBottom:20,fontFamily:"'DM Sans',sans-serif",lineHeight:1.6}}>{message}</p>
//       <div style={{display:"flex",gap:10,justifyContent:"center"}}>
//         <button onClick={onConfirm} style={{background:T.red,color:"#fff",border:"none",borderRadius:8,padding:"9px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>Delete</button>
//         <button onClick={onCancel} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:8,padding:"9px 22px",fontSize:13,cursor:"pointer"}}>Cancel</button>
//       </div>
//     </div>
//   </div>
// );

// // ─── TOAST ────────────────────────────────────────────────────────────────
// const Toast = ({ msg, type = "success" }) => (
//   <div style={{position:"fixed",bottom:24,right:24,zIndex:3000,background:type==="success"?`${T.green}18`:`${T.red}18`,border:`1px solid ${type==="success"?T.green:T.red}40`,borderRadius:10,padding:"12px 20px",color:type==="success"?T.green:T.red,fontSize:13,fontFamily:"'DM Sans',sans-serif",animation:"fadeUp 0.3s ease",boxShadow:"0 8px 24px rgba(0,0,0,0.4)"}}>
//     {type==="success"?"✓":"✗"} {msg}
//   </div>
// );
// function useToast() {
//   const [toast, setToast] = useState(null);
//   const show = (msg, type="success") => { setToast({msg,type}); setTimeout(()=>setToast(null),3000); };
//   return { toast, show };
// }

// // ─── DATA HOOKS ───────────────────────────────────────────────────────────
// const NOTIF_TYPES = ["general","payment_success","task_completed","security_alert","bonus_added","withdrawal_success","kyc_approved","announcement"];
// const PRIORITIES  = ["low","medium","high","urgent","critical"];
// const CHANNELS    = ["in_app","push","email","sms","all"];

// function useNotifications(params = {}) {
//   const [notifications, setNotifications] = useState([]);
//   const [unreadCount, setUnreadCount] = useState(0);
//   const [loading, setLoading] = useState(true);
//   const { toast, show } = useToast();

//   const fetchAll = useCallback(async () => {
//     setLoading(true);
//     try {
//       const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([,v])=>v!==undefined))).toString();
//       const [data, cnt] = await Promise.all([
//         apiFetch(`/api/notifications/notifications/?${q}`),
//         apiFetch(`/api/notifications/notifications/count_unread/`),
//       ]);
//       setNotifications(data.results || data);
//       setUnreadCount(cnt.unread_count || 0);
//     } catch { setNotifications([]); } finally { setLoading(false); }
//   }, [JSON.stringify(params)]);

//   useEffect(() => { fetchAll(); }, [fetchAll]);

//   const markAsRead    = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/mark_read/`,{method:"POST"}); fetchAll(); };
//   const markAllAsRead = async ()   => { await apiFetch(`/api/notifications/notifications/mark_all_read/`,{method:"POST"}); fetchAll(); show("All marked as read"); };
//   const archiveNotif  = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/archive/`,{method:"POST"}); fetchAll(); show("Archived"); };
//   const deleteNotif   = async (id) => { await apiFetch(`/api/notifications/notifications/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
//   const pinNotif      = async (id,isPinned) => { await apiFetch(`/api/notifications/notifications/${id}/${isPinned?"unpin":"pin"}/`,{method:"POST"}); fetchAll(); };
//   const updateNotif   = async (id,data) => { await apiFetch(`/api/notifications/notifications/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Updated"); };

//   return { notifications, unreadCount, loading, toast, markAsRead, markAllAsRead, archiveNotif, deleteNotif, pinNotif, updateNotif };
// }

// function useNotificationStats() {
//   const [stats, setStats] = useState({total:0,delivered:0,failed:0,unread:0});
//   useEffect(()=>{
//     apiFetch(`/api/notifications/notifications/summary/`).then(d=>setStats({total:d.total||0,delivered:d.delivered||0,failed:d.failed||0,unread:d.unread||0})).catch(()=>{});
//   },[]);
//   return stats;
// }

// function useTemplates() {
//   const [templates, setTemplates] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const { toast, show } = useToast();
//   const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/templates/`).then(d=>setTemplates(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
//   useEffect(()=>{ fetchAll(); },[]);
//   const create = async (data) => { await apiFetch(`/api/notifications/templates/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Template created"); };
//   const update = async (id,data) => { await apiFetch(`/api/notifications/templates/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Template updated"); };
//   const remove = async (id) => { await apiFetch(`/api/notifications/templates/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
//   const clone  = async (id) => { await apiFetch(`/api/notifications/templates/${id}/clone/`,{method:"POST"}); fetchAll(); show("Cloned"); };
//   return { templates, loading, toast, create, update, remove, clone };
// }

// function useCampaigns() {
//   const [campaigns, setCampaigns] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const { toast, show } = useToast();
//   const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/campaigns/`).then(d=>setCampaigns(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
//   useEffect(()=>{ fetchAll(); },[]);
//   const create = async (data) => { await apiFetch(`/api/notifications/campaigns/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Campaign created"); };
//   const update = async (id,data) => { await apiFetch(`/api/notifications/campaigns/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Campaign updated"); };
//   const remove = async (id) => { await apiFetch(`/api/notifications/campaigns/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
//   const action = async (id,act) => { await apiFetch(`/api/notifications/campaigns/${id}/user_action/`,{method:"POST",body:JSON.stringify({action:act})}); fetchAll(); show(`Campaign ${act}ed`); };
//   return { campaigns, loading, toast, create, update, remove,
//     start:(id)=>action(id,"start"), pause:(id)=>action(id,"pause"), cancel:(id)=>action(id,"cancel"),
//     active:campaigns.filter(c=>c.status==="running"), draft:campaigns.filter(c=>c.status==="draft") };
// }

// function useNotices() {
//   const [notices, setNotices] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const { toast, show } = useToast();
//   const fetchAll = async () => { setLoading(true); apiFetch(`/api/notifications/notices/`).then(d=>setNotices(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); };
//   useEffect(()=>{ fetchAll(); },[]);
//   const create   = async (data) => { await apiFetch(`/api/notifications/notices/`,{method:"POST",body:JSON.stringify(data)}); fetchAll(); show("Notice created"); };
//   const update   = async (id,data) => { await apiFetch(`/api/notifications/notices/${id}/`,{method:"PATCH",body:JSON.stringify(data)}); fetchAll(); show("Notice updated"); };
//   const remove   = async (id) => { await apiFetch(`/api/notifications/notices/${id}/`,{method:"DELETE"}); fetchAll(); show("Deleted"); };
//   const publish  = async (id) => { await apiFetch(`/api/notifications/notices/${id}/publish/`,{method:"POST"}); fetchAll(); show("Published"); };
//   const unpublish= async (id) => { await apiFetch(`/api/notifications/notices/${id}/unpublish/`,{method:"POST"}); fetchAll(); show("Unpublished"); };
//   const archive  = async (id) => { await apiFetch(`/api/notifications/notices/${id}/archive/`,{method:"POST"}); fetchAll(); show("Archived"); };
//   return { notices, loading, toast, create, update, remove, publish, unpublish, archive, published:notices.filter(n=>n.is_published) };
// }

// function useSend() {
//   const [sending, setSending] = useState(false);
//   const [error, setError] = useState(null);
//   const send = async (data) => {
//     setSending(true); setError(null);
//     try { return await apiFetch(`/api/notifications/admin/notifications/bulk_create/`,{method:"POST",body:JSON.stringify(data)}); }
//     catch(e){ setError(e); throw e; } finally { setSending(false); }
//   };
//   return { send, sending, error };
// }

// function useAnalytics() {
//   const [analytics, setAnalytics] = useState([]);
//   const [loading, setLoading] = useState(true);
//   useEffect(()=>{ apiFetch(`/api/notifications/analytics/`).then(d=>setAnalytics(d.results||d)).catch(()=>{}).finally(()=>setLoading(false)); },[]);
//   const totalSent = analytics.reduce((s,a)=>s+(a.total_sent||0),0);
//   const totalRead = analytics.reduce((s,a)=>s+(a.total_read||0),0);
//   const avgDel    = analytics.length?(analytics.reduce((s,a)=>s+(a.delivery_rate||0),0)/analytics.length).toFixed(1):0;
//   const avgOpen   = analytics.length?(analytics.reduce((s,a)=>s+(a.open_rate||0),0)/analytics.length).toFixed(1):0;
//   return { analytics, loading, totalSent, totalRead, avgDel, avgOpen };
// }

// // ─── EDIT NOTIFICATION MODAL ──────────────────────────────────────────────
// const EditNotifModal = ({ notif, onSave, onClose }) => {
//   const [form, setForm] = useState({title:notif?.title||"",message:notif?.message||"",priority:notif?.priority||"medium",notification_type:notif?.notification_type||"general",channel:notif?.channel||"in_app"});
//   const [saving, setSaving] = useState(false);
//   const set = k => v => setForm(p=>({...p,[k]:v}));
//   const handleSave = async () => { setSaving(true); try { await onSave(notif.id,form); onClose(); } finally { setSaving(false); } };
//   return (
//     <Modal title="Edit Notification" onClose={onClose}>
//       <div style={{display:"grid",gap:14}}>
//         <FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField>
//         <FormField label="Message"><TxtArea value={form.message} onChange={set("message")}/></FormField>
//         <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
//           <FormField label="Type"><SelIn value={form.notification_type} onChange={set("notification_type")} options={NOTIF_TYPES}/></FormField>
//           <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
//         </div>
//         <FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField>
//         <div style={{display:"flex",gap:10,marginTop:6}}>
//           <button onClick={handleSave} disabled={saving} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 24px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
//             {saving?"Saving…":"Save Changes"}
//           </button>
//           <button onClick={onClose} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
//         </div>
//       </div>
//     </Modal>
//   );
// };

// // ─── VIEW NOTIFICATION MODAL ──────────────────────────────────────────────
// const ViewNotifModal = ({ notif, onClose }) => (
//   <Modal title="Notification Detail" onClose={onClose} width={480}>
//     <div style={{display:"grid",gap:16}}>
//       <div><Lbl c="Title"/><p style={{color:T.text,fontSize:15,fontWeight:600,fontFamily:"'Syne',sans-serif"}}>{notif.title}</p></div>
//       <div><Lbl c="Message"/><p style={{color:T.textSub,fontSize:13,lineHeight:1.7,fontFamily:"'DM Sans',sans-serif"}}>{notif.message}</p></div>
//       <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14}}>
//         {[["Type",notif.notification_type],["Priority",notif.priority],["Channel",notif.channel],["Status",notif.status],["Read",notif.is_read?"Yes":"No"],["Pinned",notif.is_pinned?"Yes":"No"]].map(([k,v])=>(
//           <div key={k}><Lbl c={k}/><span style={{color:T.text,fontSize:13,fontFamily:"'JetBrains Mono',monospace"}}>{v}</span></div>
//         ))}
//       </div>
//       <div><Lbl c="Created At"/><span style={{color:T.textSub,fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}>{notif.created_at&&new Date(notif.created_at).toLocaleString()}</span></div>
//     </div>
//   </Modal>
// );

// // ─── NOTIFICATION ROW ─────────────────────────────────────────────────────
// const NotifRow = ({ n, onRead, onArchive, onPin, onDelete, onEdit, onView }) => (
//   <div className="row-hover" style={{display:"grid",gridTemplateColumns:"4px 1fr auto",gap:16,padding:"14px 20px",alignItems:"center",background:n.is_read?"transparent":`linear-gradient(90deg,rgba(108,99,255,0.05),transparent)`,borderBottom:`1px solid ${T.border}`,transition:"background 0.2s",animation:"fadeUp 0.3s ease both"}}>
//     <div style={{width:4,height:n.is_read?0:26,borderRadius:2,background:`linear-gradient(180deg,${T.accent},${T.purple})`,transition:"height 0.3s",alignSelf:"center"}}/>
//     <div onClick={()=>!n.is_read&&onRead(n.id)} style={{cursor:n.is_read?"default":"pointer"}}>
//       <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
//         <span style={{color:n.is_read?T.textSub:T.text,fontSize:13,fontWeight:n.is_read?400:600,fontFamily:"'DM Sans',sans-serif"}}>{n.title}</span>
//         <Badge p={n.priority}/>
//         {n.is_pinned&&<span style={{color:T.yellow,fontSize:11}}>📌</span>}
//       </div>
//       <div style={{color:T.textMuted,fontSize:12,marginBottom:5,lineHeight:1.5}}>{n.message?.slice(0,90)}{n.message?.length>90?"…":""}</div>
//       <div style={{display:"flex",gap:10,alignItems:"center"}}>
//         <Dot s={n.status}/>
//         <span style={{color:"#3a3a5a",fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{n.notification_type?.replace(/_/g," ")}</span>
//         <span style={{color:"#2a2a3a",fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{n.created_at&&new Date(n.created_at).toLocaleString()}</span>
//       </div>
//     </div>
//     <div style={{display:"flex",gap:2}} onClick={e=>e.stopPropagation()}>
//       <ActBtn icon="eye"     onClick={()=>onView(n)}               title="View"    color={T.blue}/>
//       <ActBtn icon="edit"    onClick={()=>onEdit(n)}               title="Edit"/>
//       <ActBtn icon="pin"     onClick={()=>onPin(n.id,n.is_pinned)} title={n.is_pinned?"Unpin":"Pin"} color={n.is_pinned?T.yellow:T.textMuted}/>
//       <ActBtn icon="archive" onClick={()=>onArchive(n.id)}         title="Archive"/>
//       <ActBtn icon="trash"   onClick={()=>onDelete(n.id)}          title="Delete"  color={T.red}/>
//     </div>
//   </div>
// );

// // ─── SEND PANEL ───────────────────────────────────────────────────────────
// const SendPanel = () => {
//   const { send, sending, error } = useSend();
//   const { toast, show } = useToast();
//   const [form, setForm] = useState({title:"",message:"",notification_type:"general",priority:"medium",channel:"in_app",user_ids:""});
//   const set = k => v => setForm(p=>({...p,[k]:v}));
//   const handleSend = async () => {
//     try { await send({...form,user_ids:form.user_ids.split(",").map(s=>parseInt(s.trim())).filter(Boolean)}); show("Sent!"); setForm({title:"",message:"",notification_type:"general",priority:"medium",channel:"in_app",user_ids:""}); } catch {}
//   };
//   const Btn = ({ label }) => (
//     <button onClick={handleSend} disabled={sending||!form.user_ids||!form.title} className="btn-hover"
//       style={{marginTop:18,background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"11px 28px",fontWeight:700,fontSize:13,cursor:"pointer",display:"flex",alignItems:"center",gap:8,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 20px ${T.accentGlow}`,opacity:sending||!form.user_ids||!form.title?0.5:1}}>
//       <Ico n="send" s={14}/>{label}
//     </button>
//   );
//   return (
//     <div style={{maxWidth:560,animation:"fadeUp 0.4s ease both"}}>
//       {toast&&<Toast msg={toast.msg} type={toast.type}/>}
//       <div style={{marginBottom:24}}>
//         <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em",marginBottom:4}}>Send Notification</h3>
//         <p style={{color:T.textMuted,fontSize:12}}>Dispatch to one or more users</p>
//       </div>
//       <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
//         <div style={{gridColumn:"span 2"}}><FormField label="User IDs (comma separated)"><TxtIn value={form.user_ids} onChange={set("user_ids")} placeholder="1, 2, 3…"/></FormField></div>
//         <div style={{gridColumn:"span 2"}}><FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField></div>
//         <div style={{gridColumn:"span 2"}}><FormField label="Message"><TxtArea value={form.message} onChange={set("message")}/></FormField></div>
//         <FormField label="Type"><SelIn value={form.notification_type} onChange={set("notification_type")} options={NOTIF_TYPES}/></FormField>
//         <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
//         <div style={{gridColumn:"span 2"}}><FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField></div>
//       </div>
//       {error&&<div style={{background:`${T.red}12`,border:`1px solid ${T.red}30`,borderRadius:8,padding:"10px 14px",color:T.red,fontSize:12,marginTop:14}}>{JSON.stringify(error)}</div>}
//       <Btn label={sending?"Sending…":"Send Notification"}/>
//     </div>
//   );
// };

// // ─── TEMPLATES PANEL ──────────────────────────────────────────────────────
// const TemplatesPanel = () => {
//   const { templates, loading, toast, create, update, remove, clone } = useTemplates();
//   const [modal, setModal] = useState(null);
//   const [confirm, setConfirm] = useState(null);
//   const [form, setForm] = useState({name:"",title_en:"",message_en:"",template_type:"general",is_active:true});
//   const set = k => v => setForm(p=>({...p,[k]:v}));

//   const openCreate = () => { setForm({name:"",title_en:"",message_en:"",template_type:"general",is_active:true}); setModal({mode:"create"}); };
//   const openEdit   = t => { setForm({name:t.name,title_en:t.title_en||"",message_en:t.message_en||"",template_type:t.template_type||"general",is_active:t.is_active}); setModal({mode:"edit",id:t.id}); };
//   const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

//   const PrimaryBtn = ({ label }) => (
//     <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>{label}</button>
//   );

//   return (
//     <div style={{animation:"fadeUp 0.4s ease both"}}>
//       {toast&&<Toast msg={toast.msg} type={toast.type}/>}
//       {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
//       {modal&&(
//         <Modal title={modal.mode==="create"?"New Template":"Edit Template"} onClose={()=>setModal(null)}>
//           <div style={{display:"grid",gap:14}}>
//             <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
//               <FormField label="Name"><TxtIn value={form.name} onChange={set("name")}/></FormField>
//               <FormField label="Type"><SelIn value={form.template_type} onChange={set("template_type")} options={["general","payment","task","security","announcement","promotion"]}/></FormField>
//             </div>
//             <FormField label="Title (EN)"><TxtIn value={form.title_en} onChange={set("title_en")}/></FormField>
//             <FormField label="Message (EN)"><TxtArea value={form.message_en} onChange={set("message_en")}/></FormField>
//             <div style={{display:"flex",alignItems:"center",gap:10}}>
//               <input type="checkbox" checked={form.is_active} onChange={e=>set("is_active")(e.target.checked)} style={{accentColor:T.accent,width:16,height:16}}/>
//               <span style={{color:T.textSub,fontSize:13}}>Active</span>
//             </div>
//             <div style={{display:"flex",gap:10,marginTop:4}}>
//               <PrimaryBtn label={modal.mode==="create"?"Create":"Save Changes"}/>
//               <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
//             </div>
//           </div>
//         </Modal>
//       )}

//       <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
//         <div>
//           <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Templates</h3>
//           <p style={{color:T.textMuted,fontSize:12,marginTop:2}}>{templates.length} templates</p>
//         </div>
//         <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
//           <Ico n="plus" s={13}/> New Template
//         </button>
//       </div>

//       {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
//       : templates.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No templates yet</div>
//       : (
//         <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(270px,1fr))",gap:14}}>
//           {templates.map((t,i)=>(
//             <div key={t.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:18,animation:`fadeUp 0.4s ease ${i*50}ms both`,transition:"border-color 0.2s"}}
//               onMouseEnter={e=>e.currentTarget.style.borderColor=T.border2}
//               onMouseLeave={e=>e.currentTarget.style.borderColor=T.border}>
//               <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
//                 <div>
//                   <div style={{color:T.text,fontWeight:600,fontSize:13,marginBottom:3,fontFamily:"'Syne',sans-serif"}}>{t.name}</div>
//                   <div style={{color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",letterSpacing:"0.08em"}}>{t.template_type}</div>
//                 </div>
//                 <span style={{color:t.is_active?T.green:T.textMuted,background:t.is_active?`${T.green}12`:`${T.textMuted}12`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{t.is_active?"ACTIVE":"INACTIVE"}</span>
//               </div>
//               <div style={{color:T.textSub,fontSize:12,marginBottom:12,lineHeight:1.6}}>{t.title_en}</div>
//               <div style={{display:"flex",alignItems:"center",borderTop:`1px solid ${T.border}`,paddingTop:10}}>
//                 <span style={{color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>{t.usage_count||0} uses</span>
//                 <div style={{marginLeft:"auto",display:"flex",gap:2}}>
//                   <ActBtn icon="copy"  onClick={()=>clone(t.id)}  title="Clone"/>
//                   <ActBtn icon="edit"  onClick={()=>openEdit(t)}  title="Edit"/>
//                   <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Delete "${t.name}"?`,fn:()=>{remove(t.id);setConfirm(null);}})} title="Delete" color={T.red}/>
//                 </div>
//               </div>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// };

// // ─── CAMPAIGNS PANEL ──────────────────────────────────────────────────────
// const CSC = {draft:T.textMuted,scheduled:T.purple,running:T.green,paused:T.yellow,completed:T.blue,cancelled:T.red,failed:T.red};

// const CampaignsPanel = () => {
//   const { campaigns, loading, toast, create, update, remove, start, pause, cancel, active, draft } = useCampaigns();
//   const [modal, setModal] = useState(null);
//   const [confirm, setConfirm] = useState(null);
//   const [form, setForm] = useState({name:"",description:"",campaign_type:"promotional",channel:"in_app"});
//   const set = k => v => setForm(p=>({...p,[k]:v}));

//   const openCreate = () => { setForm({name:"",description:"",campaign_type:"promotional",channel:"in_app"}); setModal({mode:"create"}); };
//   const openEdit   = c => { setForm({name:c.name,description:c.description||"",campaign_type:c.campaign_type||"promotional",channel:c.channel||"in_app"}); setModal({mode:"edit",id:c.id}); };
//   const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

//   return (
//     <div style={{animation:"fadeUp 0.4s ease both"}}>
//       {toast&&<Toast msg={toast.msg} type={toast.type}/>}
//       {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
//       {modal&&(
//         <Modal title={modal.mode==="create"?"New Campaign":"Edit Campaign"} onClose={()=>setModal(null)}>
//           <div style={{display:"grid",gap:14}}>
//             <FormField label="Campaign Name"><TxtIn value={form.name} onChange={set("name")}/></FormField>
//             <FormField label="Description"><TxtArea value={form.description} onChange={set("description")} rows={2}/></FormField>
//             <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
//               <FormField label="Type"><SelIn value={form.campaign_type} onChange={set("campaign_type")} options={["promotional","transactional","educational","alert","reminder","welcome","re_engagement","birthday","holiday","event"]}/></FormField>
//               <FormField label="Channel"><SelIn value={form.channel} onChange={set("channel")} options={CHANNELS}/></FormField>
//             </div>
//             <div style={{display:"flex",gap:10,marginTop:4}}>
//               <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>
//                 {modal.mode==="create"?"Create":"Save Changes"}
//               </button>
//               <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
//             </div>
//           </div>
//         </Modal>
//       )}

//       <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
//         <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Campaigns</h3>
//         <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
//           <Ico n="plus" s={13}/> New Campaign
//         </button>
//       </div>

//       <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:14,marginBottom:24}}>
//         {[{label:"Running",value:active.length,color:T.green},{label:"Draft",value:draft.length,color:T.textMuted},{label:"Total",value:campaigns.length,color:T.accent}].map(s=>(
//           <div key={s.label} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"16px 20px",textAlign:"center",borderTop:`2px solid ${s.color}`}}>
//             <div style={{color:s.color,fontSize:28,fontWeight:800,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.03em"}}>{s.value}</div>
//             <div style={{color:T.textMuted,fontSize:11,marginTop:2,fontFamily:"'JetBrains Mono',monospace",textTransform:"uppercase",letterSpacing:"0.06em"}}>{s.label}</div>
//           </div>
//         ))}
//       </div>

//       {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
//       : campaigns.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No campaigns yet</div>
//       : (
//         <div style={{display:"flex",flexDirection:"column",gap:10}}>
//           {campaigns.map((c,i)=>(
//             <div key={c.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"16px 20px",display:"grid",gridTemplateColumns:"1fr auto auto",gap:16,alignItems:"center",animation:`fadeUp 0.4s ease ${i*50}ms both`}}>
//               <div>
//                 <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6}}>
//                   <span style={{color:T.text,fontWeight:600,fontSize:14,fontFamily:"'Syne',sans-serif"}}>{c.name}</span>
//                   <span style={{color:CSC[c.status]||T.textMuted,background:`${CSC[c.status]||T.textMuted}18`,padding:"2px 9px",borderRadius:20,fontSize:9,fontWeight:700,textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{c.status}</span>
//                 </div>
//                 <div style={{display:"flex",gap:18,color:T.textMuted,fontSize:11,fontFamily:"'JetBrains Mono',monospace",marginBottom:c.total_sent>0?8:0}}>
//                   <span>Target <span style={{color:T.textSub}}>{c.target_count?.toLocaleString()||0}</span></span>
//                   <span>Sent <span style={{color:T.textSub}}>{c.total_sent?.toLocaleString()||0}</span></span>
//                   <span>Delivery <span style={{color:T.green}}>{c.delivery_rate?.toFixed(1)||0}%</span></span>
//                 </div>
//                 {c.total_sent>0&&c.target_count>0&&(
//                   <div style={{background:T.surface2,borderRadius:3,height:3,overflow:"hidden"}}>
//                     <div style={{height:"100%",width:`${Math.min(100,(c.total_sent/c.target_count)*100)}%`,background:`linear-gradient(90deg,${CSC[c.status]||T.accent},${T.purple})`,borderRadius:3}}/>
//                   </div>
//                 )}
//               </div>
//               <div style={{display:"flex",gap:6}}>
//                 {c.status==="draft"&&<button onClick={()=>start(c.id)} className="btn-hover" style={{background:`${T.green}15`,color:T.green,border:`1px solid ${T.green}30`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="play" s={11}/> Start</button>}
//                 {c.status==="running"&&<button onClick={()=>pause(c.id)} className="btn-hover" style={{background:`${T.yellow}15`,color:T.yellow,border:`1px solid ${T.yellow}30`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="pause" s={11}/> Pause</button>}
//                 {["running","paused","scheduled"].includes(c.status)&&<button onClick={()=>cancel(c.id)} className="btn-hover" style={{background:`${T.red}12`,color:T.red,border:`1px solid ${T.red}20`,borderRadius:8,padding:"6px 12px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:5,fontWeight:600}}><Ico n="stop" s={11}/> Cancel</button>}
//               </div>
//               <div style={{display:"flex",gap:2}}>
//                 <ActBtn icon="edit"  onClick={()=>openEdit(c)} title="Edit"/>
//                 <ActBtn icon="trash" onClick={()=>setConfirm({msg:`Delete campaign "${c.name}"?`,fn:()=>{remove(c.id);setConfirm(null);}})} title="Delete" color={T.red}/>
//               </div>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// };

// // ─── NOTICES PANEL ────────────────────────────────────────────────────────
// const TYPE_EMOJI = {announcement:"📢",update:"🔄",maintenance:"🔧",promotion:"🎁",warning:"⚠️",information:"ℹ️",emergency:"🚨",holiday:"🎉",event:"📅",news:"📰"};
// const BLANK_NOTICE = {title:"",content:"",notice_type:"announcement",priority:"medium",audience:"all"};

// const NoticesPanel = () => {
//   const { notices, loading, toast, create, update, remove, publish, unpublish, archive, published } = useNotices();
//   const [modal, setModal] = useState(null);
//   const [confirm, setConfirm] = useState(null);
//   const [form, setForm] = useState(BLANK_NOTICE);
//   const set = k => v => setForm(p=>({...p,[k]:v}));

//   const openCreate = () => { setForm(BLANK_NOTICE); setModal({mode:"create"}); };
//   const openEdit   = n => { setForm({title:n.title,content:n.content||"",notice_type:n.notice_type||"announcement",priority:n.priority||"medium",audience:n.audience||"all"}); setModal({mode:"edit",id:n.id}); };
//   const handleSave = async () => { if(modal.mode==="create") await create(form); else await update(modal.id,form); setModal(null); };

//   return (
//     <div style={{animation:"fadeUp 0.4s ease both"}}>
//       {toast&&<Toast msg={toast.msg} type={toast.type}/>}
//       {confirm&&<Confirm message={confirm.msg} onConfirm={confirm.fn} onCancel={()=>setConfirm(null)}/>}
//       {modal&&(
//         <Modal title={modal.mode==="create"?"New Notice":"Edit Notice"} onClose={()=>setModal(null)}>
//           <div style={{display:"grid",gap:14}}>
//             <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
//               <FormField label="Type"><SelIn value={form.notice_type} onChange={set("notice_type")} options={["announcement","update","maintenance","promotion","warning","information","emergency","holiday","event","news"]}/></FormField>
//               <FormField label="Priority"><SelIn value={form.priority} onChange={set("priority")} options={PRIORITIES}/></FormField>
//               <FormField label="Audience"><SelIn value={form.audience} onChange={set("audience")} options={["all","premium","new","active"]}/></FormField>
//             </div>
//             <FormField label="Title"><TxtIn value={form.title} onChange={set("title")}/></FormField>
//             <FormField label="Content"><TxtArea value={form.content} onChange={set("content")} rows={4}/></FormField>
//             <div style={{display:"flex",gap:10,marginTop:4}}>
//               <button onClick={handleSave} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:9,padding:"10px 22px",fontWeight:700,fontSize:13,cursor:"pointer",fontFamily:"'Syne',sans-serif"}}>
//                 {modal.mode==="create"?"Create Notice":"Save Changes"}
//               </button>
//               <button onClick={()=>setModal(null)} style={{background:T.surface2,color:T.textSub,border:`1px solid ${T.border}`,borderRadius:9,padding:"10px 18px",fontSize:13,cursor:"pointer"}}>Cancel</button>
//             </div>
//           </div>
//         </Modal>
//       )}

//       <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
//         <div>
//           <h3 style={{color:T.text,fontWeight:800,fontSize:18,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.02em"}}>Notices</h3>
//           <p style={{color:T.textMuted,fontSize:12,marginTop:2}}><span style={{color:T.green}}>{published.length} live</span> · {notices.length} total</p>
//         </div>
//         <button onClick={openCreate} className="btn-hover" style={{background:`linear-gradient(135deg,${T.accent},${T.purple})`,color:"#fff",border:"none",borderRadius:10,padding:"9px 18px",fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",boxShadow:`0 4px 16px ${T.accentGlow}`}}>
//           <Ico n="plus" s={13}/> New Notice
//         </button>
//       </div>

//       {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
//       : notices.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No notices yet</div>
//       : (
//         <div style={{display:"flex",flexDirection:"column",gap:10}}>
//           {notices.map((n,i)=>(
//             <div key={n.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderLeft:`3px solid ${n.is_published?T.green:"#2a2a3a"}`,borderRadius:12,padding:"16px 20px",animation:`fadeUp 0.4s ease ${i*50}ms both`}}>
//               <div style={{display:"grid",gridTemplateColumns:"40px 1fr auto",gap:16,alignItems:"flex-start"}}>
//                 <div style={{fontSize:26,lineHeight:1,textAlign:"center"}}>{TYPE_EMOJI[n.notice_type]||"📢"}</div>
//                 <div>
//                   <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:5,flexWrap:"wrap"}}>
//                     <span style={{color:T.text,fontWeight:600,fontSize:14,fontFamily:"'Syne',sans-serif"}}>{n.title}</span>
//                     <Badge p={n.priority}/>
//                   </div>
//                   <div style={{color:T.textSub,fontSize:12,lineHeight:1.6,marginBottom:8}}>{n.content?.slice(0,140)}{n.content?.length>140?"…":""}</div>
//                   <div style={{display:"flex",gap:14,color:T.textMuted,fontSize:10,fontFamily:"'JetBrains Mono',monospace"}}>
//                     <span>👁 {n.view_count||0}</span><span>✓ {n.acknowledge_count||0}</span><span>Audience: {n.audience}</span>
//                   </div>
//                 </div>
//                 <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:8}}>
//                   <span style={{color:n.is_published?T.green:T.textMuted,background:n.is_published?`${T.green}12`:`${T.textMuted}12`,padding:"2px 10px",borderRadius:20,fontSize:9,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.08em"}}>{n.is_published?"PUBLISHED":"DRAFT"}</span>
//                   <div style={{display:"flex",gap:2}}>
//                     {n.is_published?<ActBtn icon="eye" onClick={()=>unpublish(n.id)} title="Unpublish" color={T.yellow}/>:<ActBtn icon="bolt" onClick={()=>publish(n.id)} title="Publish" color={T.green}/>}
//                     <ActBtn icon="edit"    onClick={()=>openEdit(n)}   title="Edit"/>
//                     <ActBtn icon="archive" onClick={()=>archive(n.id)} title="Archive"/>
//                     <ActBtn icon="trash"   onClick={()=>setConfirm({msg:`Delete "${n.title}"?`,fn:()=>{remove(n.id);setConfirm(null);}})} title="Delete" color={T.red}/>
//                   </div>
//                 </div>
//               </div>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// };

// // ─── ANALYTICS PANEL ──────────────────────────────────────────────────────
// const AnalyticsPanel = () => {
//   const { analytics, loading, totalSent, totalRead, avgDel, avgOpen } = useAnalytics();
//   return (
//     <div style={{animation:"fadeUp 0.4s ease both"}}>
//       <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14,marginBottom:28}}>
//         {[{label:"Total Sent",value:totalSent,icon:"send",color:T.accent},{label:"Total Read",value:totalRead,icon:"eye",color:T.green},{label:"Avg Delivery",value:`${avgDel}%`,icon:"check",color:T.yellow},{label:"Avg Open Rate",value:`${avgOpen}%`,icon:"bell",color:T.purple}].map((c,i)=>(
//           <div key={c.label} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:"20px 22px",position:"relative",overflow:"hidden",animation:`fadeUp 0.5s ease ${i*80}ms both`}}>
//             <div style={{position:"absolute",top:0,left:0,right:0,height:2,background:`linear-gradient(90deg,transparent,${c.color},transparent)`}}/>
//             <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}>
//               <div style={{width:28,height:28,borderRadius:8,background:`${c.color}18`,display:"flex",alignItems:"center",justifyContent:"center",color:c.color}}><Ico n={c.icon} s={13}/></div>
//               <span style={{color:T.textMuted,fontSize:11,fontWeight:600,letterSpacing:"0.08em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>{c.label}</span>
//             </div>
//             <div style={{fontSize:30,fontWeight:800,color:T.text,fontFamily:"'Syne',sans-serif",letterSpacing:"-0.03em"}}>{typeof c.value==="number"?c.value.toLocaleString():c.value}</div>
//           </div>
//         ))}
//       </div>
//       {loading ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>Loading…</div>
//       : analytics.length===0 ? <div style={{color:T.textMuted,padding:48,textAlign:"center"}}>No analytics data</div>
//       : (
//         <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,overflow:"hidden"}}>
//           <div style={{padding:"12px 20px",background:T.surface2,borderBottom:`1px solid ${T.border}`,display:"grid",gridTemplateColumns:"110px 80px 80px 90px 80px 80px 80px 80px",color:T.textMuted,fontSize:9,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",fontFamily:"'JetBrains Mono',monospace"}}>
//             {["Date","Total","Sent","Delivered","Read","Clicked","Failed","Open%"].map(h=><span key={h}>{h}</span>)}
//           </div>
//           {analytics.slice(0,20).map((a,i)=>(
//             <div key={a.date||a.id} style={{padding:"12px 20px",borderBottom:`1px solid ${T.border}`,display:"grid",gridTemplateColumns:"110px 80px 80px 90px 80px 80px 80px 80px",fontSize:12,animation:`fadeUp 0.3s ease ${i*30}ms both`,fontFamily:"'JetBrains Mono',monospace"}}>
//               <span style={{color:T.text}}>{a.date}</span>
//               <span style={{color:T.textSub}}>{a.total_notifications?.toLocaleString()}</span>
//               <span style={{color:T.accent}}>{a.total_sent?.toLocaleString()}</span>
//               <span style={{color:T.green}}>{a.total_delivered?.toLocaleString()}</span>
//               <span style={{color:T.purple}}>{a.total_read?.toLocaleString()}</span>
//               <span style={{color:T.yellow}}>{a.total_clicked?.toLocaleString()}</span>
//               <span style={{color:a.total_failed>0?T.red:T.textMuted}}>{a.total_failed?.toLocaleString()}</span>
//               <span style={{color:T.green}}>{a.open_rate?.toFixed(1)}%</span>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// };

// // ─── TABS ─────────────────────────────────────────────────────────────────
// const TABS = [
//   {id:"inbox",label:"Inbox",icon:"bell"},
//   {id:"send",label:"Send",icon:"send"},
//   {id:"templates",label:"Templates",icon:"template"},
//   {id:"campaigns",label:"Campaigns",icon:"campaign"},
//   {id:"notices",label:"Notices",icon:"notice"},
//   {id:"analytics",label:"Analytics",icon:"chart"},
// ];

// // ─── MAIN ─────────────────────────────────────────────────────────────────
// export default function NotificationsPage() {
//   const [activeTab, setActiveTab] = useState("inbox");
//   const [filter, setFilter] = useState("all");
//   const [editModal, setEditModal] = useState(null);
//   const [viewModal, setViewModal] = useState(null);
//   const [confirmDel, setConfirmDel] = useState(null);

//   const fp = filter==="unread"?{is_read:false}:filter==="pinned"?{is_pinned:true}:filter==="archived"?{is_archived:true}:{};
//   const { notifications, unreadCount, loading, toast, markAsRead, markAllAsRead, archiveNotif, deleteNotif, pinNotif, updateNotif } = useNotifications(fp);
//   const stats = useNotificationStats();

//   return (
//     <>
//       <GS/>
//       {toast&&<Toast msg={toast.msg} type={toast.type}/>}
//       {editModal&&<EditNotifModal notif={editModal} onSave={updateNotif} onClose={()=>setEditModal(null)}/>}
//       {viewModal&&<ViewNotifModal notif={viewModal} onClose={()=>setViewModal(null)}/>}
//       {confirmDel&&<Confirm message="Delete this notification?" onConfirm={()=>{deleteNotif(confirmDel);setConfirmDel(null);}} onCancel={()=>setConfirmDel(null)}/>}

//       <div style={{minHeight:"100vh",background:T.bg,color:T.text,fontFamily:"'DM Sans',sans-serif",padding:"28px 32px"}}>

//         {/* HEADER */}
//         <div style={{marginBottom:30,animation:"fadeUp 0.5s ease both"}}>
//           <div style={{display:"flex",alignItems:"flex-start",gap:16,marginBottom:16}}>
//             <div style={{width:46,height:46,borderRadius:14,flexShrink:0,background:`linear-gradient(135deg,${T.accent},${T.purple})`,display:"flex",alignItems:"center",justifyContent:"center",boxShadow:`0 8px 24px ${T.accentGlow}`}}><Ico n="bell" s={20}/></div>
//             <div style={{flex:1}}>
//               <h1 style={{fontSize:24,fontWeight:800,color:T.text,letterSpacing:"-0.03em",margin:0,fontFamily:"'Syne',sans-serif"}}>Notifications</h1>
//               <p style={{color:T.textMuted,fontSize:12,margin:"3px 0 0"}}>Manage notifications, campaigns & announcements</p>
//             </div>
//             {unreadCount>0&&<div style={{background:T.red,color:"#fff",borderRadius:20,padding:"4px 12px",fontSize:12,fontWeight:700,fontFamily:"'JetBrains Mono',monospace",boxShadow:`0 4px 12px ${T.red}40`}}>{unreadCount} unread</div>}
//           </div>
//           <div style={{display:"flex",gap:24,paddingLeft:62}}>
//             {[{label:"Total",value:stats.total,color:T.textSub},{label:"Delivered",value:stats.delivered,color:T.green},{label:"Failed",value:stats.failed,color:T.red},{label:"Unread",value:stats.unread,color:T.accent}].map(s=>(
//               <div key={s.label} style={{display:"flex",alignItems:"flex-end",gap:6}}>
//                 <span style={{color:s.color,fontWeight:800,fontSize:15,fontFamily:"'Syne',sans-serif"}}>{s.value?.toLocaleString()||0}</span>
//                 <span style={{color:T.textMuted,fontSize:11,paddingBottom:1,fontFamily:"'JetBrains Mono',monospace"}}>{s.label}</span>
//               </div>
//             ))}
//           </div>
//         </div>

//         {/* TABS */}
//         <div style={{display:"flex",gap:1,marginBottom:28,background:T.surface,borderRadius:12,padding:4,border:`1px solid ${T.border}`}}>
//           {TABS.map(tab=>(
//             <button key={tab.id} onClick={()=>setActiveTab(tab.id)} style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center",gap:7,padding:"9px 10px",borderRadius:9,border:"none",cursor:"pointer",fontSize:12,fontWeight:600,transition:"all 0.2s",fontFamily:"'Syne',sans-serif",background:activeTab===tab.id?`linear-gradient(135deg,${T.accent},${T.purple})`:"transparent",color:activeTab===tab.id?"#fff":T.textMuted,boxShadow:activeTab===tab.id?`0 4px 12px ${T.accentGlow}`:"none"}}>
//               <Ico n={tab.icon} s={13}/>
//               <span style={{whiteSpace:"nowrap"}}>{tab.label}</span>
//               {tab.id==="inbox"&&unreadCount>0&&<span style={{background:activeTab==="inbox"?"rgba(255,255,255,0.25)":T.red,color:"#fff",borderRadius:10,padding:"1px 7px",fontSize:9,fontWeight:800,fontFamily:"'JetBrains Mono',monospace"}}>{unreadCount}</span>}
//             </button>
//           ))}
//         </div>

//         {/* INBOX */}
//         {activeTab==="inbox"&&(
//           <div style={{animation:"fadeUp 0.4s ease both"}}>
//             <div style={{display:"flex",gap:8,marginBottom:16,alignItems:"center"}}>
//               {[{id:"all",label:"All"},{id:"unread",label:"Unread"},{id:"pinned",label:"Pinned"},{id:"archived",label:"Archived"}].map(f=>(
//                 <button key={f.id} onClick={()=>setFilter(f.id)} className="pill" style={{background:filter===f.id?`${T.accent}20`:T.surface,color:filter===f.id?T.accent:T.textMuted,border:`1px solid ${filter===f.id?T.accent+"50":T.border}`,borderRadius:20,padding:"5px 15px",fontSize:11,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace",fontWeight:600,letterSpacing:"0.04em",transition:"all 0.2s"}}>
//                   {f.label}
//                 </button>
//               ))}
//               {unreadCount>0&&<button onClick={markAllAsRead} className="btn-hover" style={{marginLeft:"auto",background:`${T.green}12`,color:T.green,border:`1px solid ${T.green}30`,borderRadius:8,padding:"6px 14px",fontSize:11,cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontFamily:"'Syne',sans-serif",fontWeight:600}}><Ico n="check" s={12}/> Mark all read</button>}
//             </div>
//             <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,overflow:"hidden"}}>
//               {loading ? <div style={{padding:64,textAlign:"center",color:T.textMuted,animation:"pulse 1.5s ease infinite",fontSize:13}}>Loading…</div>
//               : notifications.length===0 ? <div style={{padding:64,textAlign:"center"}}><div style={{fontSize:36,marginBottom:12}}>🔔</div><div style={{color:T.textMuted,fontSize:14}}>No notifications</div></div>
//               : notifications.map(n=>(
//                 <NotifRow key={n.id} n={n}
//                   onRead={markAsRead} onArchive={archiveNotif} onPin={pinNotif}
//                   onDelete={id=>setConfirmDel(id)}
//                   onEdit={n=>setEditModal(n)}
//                   onView={n=>setViewModal(n)}
//                 />
//               ))}
//             </div>
//           </div>
//         )}

//         {activeTab==="send"      && <SendPanel/>}
//         {activeTab==="templates" && <TemplatesPanel/>}
//         {activeTab==="campaigns" && <CampaignsPanel/>}
//         {activeTab==="notices"   && <NoticesPanel/>}
//         {activeTab==="analytics" && <AnalyticsPanel/>}
//       </div>
//     </>
//   );
// }


