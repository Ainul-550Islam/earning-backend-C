import { useState, useEffect, useRef, useCallback } from "react";
import {
  LayoutDashboard, FileText, Image, MessageSquare, Settings,
  HelpCircle, Megaphone, FolderOpen, Globe, Shield, BarChart3,
  Plus, Search, Filter, Eye, Edit3, Trash2, Star, Pin,
  TrendingUp, Users, Zap, RefreshCw, ChevronRight, Tag,
  Calendar, Clock, CheckCircle, AlertCircle, XCircle,
  Upload, Download, Link2, Layers, Database, Activity,
  Bell, BookOpen, Film, Hash, Bookmark, Award, X, Save,
  ToggleLeft, ToggleRight, AlertTriangle
} from "lucide-react";
import {
  useContentPages,
  useContentCategories,
  useBanners,
  useFAQs,
  useComments,
  useSiteAnalytics,
  useFiles,
  useGalleries,
} from "../hooks/useCms";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── Cyberpunk Color System ───────────────────────────────────────
const C = {
  cyan:    "#00f5ff",
  purple:  "#bf00ff",
  pink:    "#ff006e",
  green:   "#00ff88",
  yellow:  "#ffe600",
  orange:  "#ff6b00",
  bg:      "#050b14",
  bgCard:  "rgba(8,20,40,0.85)",
  bgHover: "rgba(0,245,255,0.04)",
  border:  "rgba(0,245,255,0.18)",
  borderP: "rgba(191,0,255,0.22)",
  text:    "#c8e6f0",
  textDim: "#4a7a8a",
};

// ─── Styles ───────────────────────────────────────────────────────
const S = {
  page: { minHeight:"100vh", background:C.bg, fontFamily:"'Share Tech Mono','Courier New',monospace", color:C.text, position:"relative", overflow:"hidden" },
  grid: { position:"fixed",inset:0,zIndex:0,pointerEvents:"none", backgroundImage:`linear-gradient(rgba(0,245,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,245,255,0.03) 1px,transparent 1px)`, backgroundSize:"40px 40px" },
  blob: (color,top,left,size=400)=>({ position:"fixed",top,left,width:size,height:size, background:`radial-gradient(circle,${color}18 0%,transparent 70%)`, borderRadius:"50%",filter:"blur(40px)",pointerEvents:"none",zIndex:0 }),
  sidebar: { width:240,flexShrink:0, background:"rgba(5,12,24,0.95)", borderRight:`1px solid ${C.border}`, backdropFilter:"blur(20px)", position:"sticky",top:0,height:"100vh", display:"flex",flexDirection:"column",zIndex:10 },
  logo: { padding:"20px 20px 16px", borderBottom:`1px solid ${C.border}` },
  logoText: { fontSize:11,letterSpacing:4,color:C.cyan,textTransform:"uppercase",fontWeight:700 },
  logoSub: { fontSize:9,color:C.textDim,letterSpacing:2,marginTop:2 },
  navSection: { padding:"10px 0",flex:1,overflowY:"auto" },
  navLabel: { fontSize:9,letterSpacing:3,color:C.textDim,padding:"8px 20px 4px",textTransform:"uppercase" },
  navItem: (active,color=C.cyan)=>({ display:"flex",alignItems:"center",gap:10, padding:"9px 20px",cursor:"pointer",transition:"all 0.2s", background:active?`${color}10`:"transparent", borderLeft:active?`2px solid ${color}`:"2px solid transparent", color:active?color:C.textDim,fontSize:12 }),
  card: (glowColor=C.cyan)=>({ background:C.bgCard, backdropFilter:"blur(16px)", border:`1px solid ${glowColor}28`, borderRadius:4, boxShadow:`0 0 20px ${glowColor}08,inset 0 1px 0 ${glowColor}15`, position:"relative" }),
  cardHeader: { display:"flex",alignItems:"center",justifyContent:"space-between", padding:"14px 18px", borderBottom:`1px solid ${C.border}` },
  cardTitle: { fontSize:11,letterSpacing:2,textTransform:"uppercase",color:C.cyan },
  statGrid: { display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,padding:"0 0 16px" },
  statCard: (color)=>({ ...((c=color)=>({ background:C.bgCard,backdropFilter:"blur(16px)",border:`1px solid ${c}28`,borderRadius:4,boxShadow:`0 0 20px ${c}08,inset 0 1px 0 ${c}15`,position:"relative" }))(color), padding:"16px",display:"flex",flexDirection:"column",gap:6 }),
  statNum: (color)=>({ fontSize:28,fontWeight:700,color,fontFamily:"'Orbitron',monospace",lineHeight:1 }),
  statLabel: { fontSize:10,color:C.textDim,letterSpacing:2,textTransform:"uppercase" },
  table: { width:"100%",borderCollapse:"collapse" },
  th: { fontSize:9,letterSpacing:2,color:C.textDim,padding:"10px 14px",textAlign:"left",borderBottom:`1px solid ${C.border}`,textTransform:"uppercase" },
  td: { padding:"11px 14px",fontSize:12,borderBottom:`1px solid rgba(0,245,255,0.06)`,verticalAlign:"middle" },
  badge: (color)=>({ display:"inline-flex",alignItems:"center",gap:4,padding:"2px 8px",borderRadius:2, background:`${color}18`,border:`1px solid ${color}40`,color,fontSize:10,letterSpacing:1,textTransform:"uppercase" }),
  btn: (color=C.cyan,variant="outline")=>({ display:"inline-flex",alignItems:"center",gap:6,padding:"7px 14px",borderRadius:2,cursor:"pointer",fontSize:11,letterSpacing:1,transition:"all 0.2s",textTransform:"uppercase",border:"none", ...(variant==="solid"?{background:`${color}20`,border:`1px solid ${color}80`,color}:{background:"transparent",border:`1px solid ${color}40`,color}) }),
  input: { background:"rgba(0,245,255,0.04)",border:`1px solid ${C.border}`,borderRadius:2,color:C.text,fontSize:12,padding:"8px 12px",outline:"none",fontFamily:"inherit",width:"100%",boxSizing:"border-box" },
  tab: (active)=>({ padding:"8px 16px",fontSize:11,cursor:"pointer",letterSpacing:1,textTransform:"uppercase", color:active?C.cyan:C.textDim, borderBottom:active?`2px solid ${C.cyan}`:"2px solid transparent", transition:"all 0.2s",background:"transparent",border:"none",fontFamily:"inherit" }),
  // Modal overlay
  overlay: { position:"fixed",inset:0,background:"rgba(0,0,0,0.8)",backdropFilter:"blur(4px)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center" },
  modal: (color=C.cyan)=>({ background:"rgba(5,12,24,0.97)",border:`1px solid ${color}40`,borderRadius:6,width:"92%",maxWidth:560,maxHeight:"88vh",overflow:"auto", boxShadow:`0 0 40px ${color}20`,padding:24,position:"relative" }),
  modalTitle: (color)=>({ fontSize:13,letterSpacing:3,textTransform:"uppercase",color,marginBottom:20 }),
  label: { fontSize:10,letterSpacing:2,color:C.textDim,textTransform:"uppercase",display:"block",marginBottom:6,marginTop:14 },
  select: { background:"rgba(0,245,255,0.04)",border:`1px solid ${C.border}`,borderRadius:2,color:C.text,fontSize:12,padding:"8px 12px",outline:"none",fontFamily:"inherit",width:"100%",boxSizing:"border-box" },
  textarea: { background:"rgba(0,245,255,0.04)",border:`1px solid ${C.border}`,borderRadius:2,color:C.text,fontSize:12,padding:"8px 12px",outline:"none",fontFamily:"inherit",width:"100%",boxSizing:"border-box",minHeight:80,resize:"vertical" },
};

const STATUS_COLORS = { published:C.green,draft:C.textDim,scheduled:C.yellow,archived:C.orange,expired:C.pink,review:C.purple,approved:C.cyan,active:C.green,inactive:C.textDim,pending:C.yellow,rejected:C.pink };
const StatusBadge = ({status})=><span style={S.badge(STATUS_COLORS[status]||C.textDim)}>{status}</span>;
const PulseDot = ({color=C.green})=><span style={{display:"inline-block",width:6,height:6,borderRadius:"50%",background:color,boxShadow:`0 0 6px ${color}`,animation:"pulse 2s infinite"}}/>;

// ─── Toast ────────────────────────────────────────────────────────
const Toast = ({toast})=>{
  if(!toast) return null;
  const colors={success:C.green,error:C.pink,info:C.cyan,warning:C.yellow};
  const color=colors[toast.type]||C.cyan;
  return (
    <div style={{position:"fixed",bottom:24,right:24,zIndex:9999,
      background:`rgba(5,12,24,0.97)`,border:`1px solid ${color}60`,
      borderRadius:4,padding:"12px 20px",color,fontSize:12,letterSpacing:1,
      boxShadow:`0 0 20px ${color}30`,display:"flex",alignItems:"center",gap:10,
      animation:"slideIn 0.3s ease"}}>
      {toast.type==="success"?<CheckCircle size={14}/>:toast.type==="error"?<XCircle size={14}/>:<AlertCircle size={14}/>}
      {toast.message}
    </div>
  );
};

// ─── Confirm Delete Modal ─────────────────────────────────────────
const ConfirmModal = ({open,label,onConfirm,onCancel})=>{
  if(!open) return null;
  return (
    <div style={S.overlay} onClick={onCancel}>
      <div style={S.modal(C.pink)} onClick={e=>e.stopPropagation()}>
        <div style={{...S.modalTitle(C.pink),display:"flex",alignItems:"center",gap:8}}>
          <AlertTriangle size={16}/> CONFIRM DELETE
        </div>
        <p style={{fontSize:12,color:C.text,marginBottom:20}}>
          Delete <span style={{color:C.pink}}>"{label}"</span>? This cannot be undone.
        </p>
        <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
          <button style={S.btn(C.textDim)} onClick={onCancel}>CANCEL</button>
          <button style={S.btn(C.pink,"solid")} onClick={onConfirm}><Trash2 size={11}/>DELETE</button>
        </div>
      </div>
    </div>
  );
};

// ─── CRUD Modal Base ──────────────────────────────────────────────
const CrudModal = ({open,title,color=C.cyan,onClose,onSave,saving,children})=>{
  if(!open) return null;
  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.modal(color)} onClick={e=>e.stopPropagation()}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20}}>
          <div style={S.modalTitle(color)}>{title}</div>
          <button style={{background:"none",border:"none",color:C.textDim,cursor:"pointer"}} onClick={onClose}><X size={16}/></button>
        </div>
        {children}
        <div style={{display:"flex",gap:10,justifyContent:"flex-end",marginTop:24}}>
          <button style={S.btn(C.textDim)} onClick={onClose}>CANCEL</button>
          <button style={S.btn(color,"solid")} onClick={onSave} disabled={saving}>
            <Save size={11}/>{saving?"SAVING...":"SAVE"}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Stat Card ────────────────────────────────────────────────────
const StatCard = ({label,value,color,icon:Icon,sub})=>(
  <div style={S.statCard(color)}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
      <div>
        <div style={S.statNum(color)}>{value??0}</div>
        <div style={S.statLabel}>{label}</div>
      </div>
      {Icon&&<div style={{width:36,height:36,borderRadius:4,background:`${color}12`,border:`1px solid ${color}30`,display:"flex",alignItems:"center",justifyContent:"center"}}><Icon size={16} color={color}/></div>}
    </div>
    {sub&&<div style={{fontSize:10,color:C.textDim,marginTop:4}}>{sub}</div>}
  </div>
);

// ─── Section ──────────────────────────────────────────────────────
const Section = ({title,icon:Icon,color=C.cyan,children,actions})=>(
  <div style={S.card(color)}>
    <div style={S.cardHeader}>
      <div style={{display:"flex",alignItems:"center",gap:8}}>
        {Icon&&<Icon size={14} color={color}/>}
        <span style={{...S.cardTitle,color}}>{title}</span>
      </div>
      {actions&&<div style={{display:"flex",gap:8}}>{actions}</div>}
    </div>
    <div>{children}</div>
  </div>
);

// ─── Empty ────────────────────────────────────────────────────────
const Empty=({label="NO DATA"})=>(
  <div style={{padding:"40px 0",textAlign:"center",color:C.textDim,fontSize:11,letterSpacing:2}}>
    <div style={{fontSize:24,marginBottom:8,opacity:0.3}}>◈</div>{label}
  </div>
);

// ─── Nav ─────────────────────────────────────────────────────────
const NAV=[
  {id:"overview",label:"Overview",icon:LayoutDashboard,color:C.cyan},
  {id:"div1",label:"CONTENT"},
  {id:"pages",label:"Pages",icon:FileText,color:C.cyan},
  {id:"categories",label:"Categories",icon:FolderOpen,color:C.purple},
  {id:"banners",label:"Banners",icon:Megaphone,color:C.pink},
  {id:"faq",label:"FAQ",icon:HelpCircle,color:C.yellow},
  {id:"div2",label:"MEDIA"},
  {id:"gallery",label:"Gallery",icon:Image,color:C.purple},
  {id:"files",label:"Files",icon:Database,color:C.cyan},
  {id:"div3",label:"ENGAGEMENT"},
  {id:"comments",label:"Comments",icon:MessageSquare,color:C.green},
  {id:"analytics",label:"Analytics",icon:BarChart3,color:C.orange},
  {id:"div4",label:"SYSTEM"},
  {id:"settings",label:"Settings",icon:Settings,color:C.textDim},
];

// ═══════════════════════════════════════════════════════════════════
//  OVERVIEW
// ═══════════════════════════════════════════════════════════════════
const OverviewSection=({setActive})=>{
  const {pages,stats}=useContentPages();
  const {comments}=useComments({is_approved:"false"});
  const {today}=useSiteAnalytics();
  const {banners}=useBanners();

  return(
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div style={S.statGrid}>
        <StatCard label="Total Pages"      value={stats?.total??pages?.length??0} color={C.cyan}   icon={FileText}/>
        <StatCard label="Published"        value={stats?.published??0}             color={C.green}  icon={CheckCircle}/>
        <StatCard label="Pending Comments" value={comments?.length??0}             color={C.yellow} icon={MessageSquare}/>
        <StatCard label="Active Banners"   value={banners?.filter(b=>b.is_active).length??0} color={C.pink} icon={Megaphone}/>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
        <Section title="SYSTEM STATUS" icon={Activity} color={C.cyan}>
          {[{label:"Content Engine",status:"ONLINE",color:C.green},{label:"Banner Service",status:"ONLINE",color:C.green},
            {label:"Cache Layer",status:"ACTIVE",color:C.cyan},{label:"Media CDN",status:"SYNCING",color:C.yellow},
            {label:"Analytics DB",status:"ONLINE",color:C.green}].map(item=>(
            <div key={item.label} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"10px 18px",borderBottom:`1px solid ${C.border}`}}>
              <div style={{display:"flex",alignItems:"center",gap:8}}><PulseDot color={item.color}/><span style={{fontSize:12}}>{item.label}</span></div>
              <span style={S.badge(item.color)}>{item.status}</span>
            </div>
          ))}
        </Section>
        <Section title="QUICK ACTIONS" icon={Zap} color={C.purple}>
          <div style={{padding:"14px 18px",display:"flex",flexDirection:"column",gap:8}}>
            {[{label:"New Page",icon:FileText,color:C.cyan,nav:"pages"},{label:"New Banner",icon:Megaphone,color:C.pink,nav:"banners"},
              {label:"Add FAQ",icon:HelpCircle,color:C.yellow,nav:"faq"},{label:"Moderate Comments",icon:MessageSquare,color:C.green,nav:"comments"},
              {label:"View Analytics",icon:BarChart3,color:C.orange,nav:"analytics"}].map(a=>(
              <button key={a.label} style={{...S.btn(a.color,"solid"),justifyContent:"flex-start"}} onClick={()=>setActive(a.nav)}>
                <a.icon size={12}/>{a.label}
              </button>
            ))}
          </div>
        </Section>
      </div>
      <div style={S.statGrid}>
        <StatCard label="Page Views Today"    value={today?.page_views??0}         color={C.orange} icon={Eye}/>
        <StatCard label="Unique Visitors"     value={today?.unique_visitors??0}     color={C.purple} icon={Users}/>
        <StatCard label="Banner Clicks"       value={today?.banner_clicks??0}       color={C.pink}   icon={Link2}/>
        <StatCard label="Offer Completions"   value={today?.offer_completions??0}   color={C.green}  icon={Award}/>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  PAGES
// ═══════════════════════════════════════════════════════════════════
const PagesSection=({showToast})=>{
  const {pages,stats,loading,fetch,create,update,remove}=useContentPages();
  const {categories}=useContentCategories();
  const [tab,setTab]=useState("all");
  const [modal,setModal]=useState(null); // {mode:"create"|"edit", data:null|{}}
  const [confirmDel,setConfirmDel]=useState(null);
  const [saving,setSaving]=useState(false);
  const [form,setForm]=useState({title:"",slug:"",excerpt:"",status:"draft",page_type:"page",category:"",is_featured:false,is_pinned:false});
  const [search,setSearch]=useState("");

  const filtered=(pages||[]).filter(p=>{
    if(tab==="published") return p.status==="published";
    if(tab==="draft") return p.status==="draft";
    if(tab==="scheduled") return p.status==="scheduled";
    return true;
  }).filter(p=>!search||p.title?.toLowerCase().includes(search.toLowerCase()));

  const openCreate=()=>{ setForm({title:"",slug:"",excerpt:"",status:"draft",page_type:"page",category:"",is_featured:false,is_pinned:false}); setModal({mode:"create"}); };
  const openEdit=(p)=>{ setForm({title:p.title||"",slug:p.slug||"",excerpt:p.excerpt||"",status:p.status||"draft",page_type:p.page_type||"page",category:p.category||"",is_featured:!!p.is_featured,is_pinned:!!p.is_pinned}); setModal({mode:"edit",data:p}); };

  const handleSave=async()=>{
    if(!form.title){showToast("Title is required","error");return;}
    setSaving(true);
    try{
      if(modal.mode==="create"){ await create(form); showToast("Page created!","success"); }
      else{ await update(modal.data.id,form); showToast("Page updated!","success"); }
      setModal(null);
    }catch(e){showToast(e?.response?.data?.detail||"Save failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{ await remove(confirmDel.id); showToast("Page deleted","success"); }
    catch{ showToast("Delete failed","error"); }
    setConfirmDel(null);
  };

  const handleToggleFeatured=async(p)=>{
    try{ await update(p.id,{is_featured:!p.is_featured}); showToast(`${!p.is_featured?"Featured":"Unfeatured"}!`,"success"); }
    catch{ showToast("Failed","error"); }
  };

  return(
    <>
    <Section title="CONTENT PAGES" icon={FileText} color={C.cyan}
      actions={<>
        <div style={{...S.badge(C.cyan),padding:"4px 10px"}}>Total: {stats?.total??pages?.length??0}</div>
        <button style={S.btn(C.cyan,"solid")} onClick={openCreate}><Plus size={12}/>NEW PAGE</button>
      </>}>
      <div style={{display:"flex",borderBottom:`1px solid ${C.border}`,padding:"0 18px"}}>
        {["all","published","draft","scheduled"].map(t=>(
          <button key={t} style={S.tab(tab===t)} onClick={()=>setTab(t)}>{t.toUpperCase()}</button>
        ))}
      </div>
      <div style={{display:"flex",gap:8,padding:"12px 18px",borderBottom:`1px solid ${C.border}`}}>
        <div style={{position:"relative",flex:1}}>
          <Search size={12} color={C.textDim} style={{position:"absolute",left:10,top:"50%",transform:"translateY(-50%)"}}/>
          <input style={{...S.input,paddingLeft:30}} placeholder="SEARCH PAGES..." value={search} onChange={e=>setSearch(e.target.value)}/>
        </div>
        <button style={S.btn(C.cyan)} onClick={()=>fetch()}><RefreshCw size={12}/></button>
      </div>
      <div style={{overflowX:"auto"}}>
        <table style={S.table}>
          <thead><tr>{["TITLE","TYPE","CATEGORY","STATUS","VIEWS","DATE","ACTIONS"].map(h=><th key={h} style={S.th}>{h}</th>)}</tr></thead>
          <tbody>
            {loading?<tr><td colSpan={7}><Empty label="LOADING..."/></td></tr>
            :filtered.length===0?<tr><td colSpan={7}><Empty label="NO PAGES FOUND"/></td></tr>
            :filtered.slice(0,12).map(p=>(
              <tr key={p.id} onMouseEnter={e=>e.currentTarget.style.background=C.bgHover} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                <td style={S.td}>
                  <div style={{display:"flex",alignItems:"center",gap:6}}>
                    {p.is_featured&&<Star size={10} color={C.yellow}/>}
                    {p.is_pinned&&<Pin size={10} color={C.pink}/>}
                    <span>{p.title}</span>
                  </div>
                  <div style={{fontSize:10,color:C.textDim,marginTop:2}}>{p.slug}</div>
                </td>
                <td style={S.td}><span style={S.badge(C.purple)}>{p.page_type}</span></td>
                <td style={{...S.td,fontSize:11,color:C.textDim}}>{p.category_name||"—"}</td>
                <td style={S.td}><StatusBadge status={p.status}/></td>
                <td style={{...S.td,color:C.cyan,fontFamily:"'Orbitron',monospace",fontSize:11}}>{p.view_count?.toLocaleString()??0}</td>
                <td style={{...S.td,fontSize:11,color:C.textDim}}>{p.published_date?new Date(p.published_date).toLocaleDateString():"—"}</td>
                <td style={S.td}>
                  <div style={{display:"flex",gap:6}}>
                    <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>handleToggleFeatured(p)} title="Toggle featured"><Star size={13} color={p.is_featured?C.yellow:C.textDim}/></button>
                    <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>openEdit(p)}><Edit3 size={13} color={C.purple}/></button>
                    <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>setConfirmDel(p)}><Trash2 size={13} color={C.pink}/></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>

    <CrudModal open={!!modal} title={modal?.mode==="create"?"CREATE PAGE":"EDIT PAGE"} color={C.cyan} onClose={()=>setModal(null)} onSave={handleSave} saving={saving}>
      <label style={S.label}>Title *</label>
      <input style={S.input} value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="Page title"/>
      <label style={S.label}>Slug</label>
      <input style={S.input} value={form.slug} onChange={e=>setForm({...form,slug:e.target.value})} placeholder="page-slug"/>
      <label style={S.label}>Excerpt</label>
      <textarea style={S.textarea} value={form.excerpt} onChange={e=>setForm({...form,excerpt:e.target.value})} placeholder="Short description..."/>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginTop:14}}>
        <div>
          <label style={{...S.label,marginTop:0}}>Status</label>
          <select style={S.select} value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>
            {["draft","published","scheduled","archived","review"].map(s=><option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label style={{...S.label,marginTop:0}}>Page Type</label>
          <select style={S.select} value={form.page_type} onChange={e=>setForm({...form,page_type:e.target.value})}>
            {["page","blog","news","tutorial","offer","task"].map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>
      <label style={S.label}>Category</label>
      <select style={S.select} value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>
        <option value="">— None —</option>
        {(categories||[]).map(cat=><option key={cat.id} value={cat.id}>{cat.name}</option>)}
      </select>
      <div style={{display:"flex",gap:20,marginTop:16}}>
        <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:12}}>
          <input type="checkbox" checked={form.is_featured} onChange={e=>setForm({...form,is_featured:e.target.checked})}/>
          <Star size={12} color={C.yellow}/> Featured
        </label>
        <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:12}}>
          <input type="checkbox" checked={form.is_pinned} onChange={e=>setForm({...form,is_pinned:e.target.checked})}/>
          <Pin size={12} color={C.pink}/> Pinned
        </label>
      </div>
    </CrudModal>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.title} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  CATEGORIES
// ═══════════════════════════════════════════════════════════════════
const CategoriesSection=({showToast})=>{
  const {categories,loading,fetch,create,update,remove}=useContentCategories();
  const [modal,setModal]=useState(null);
  const [confirmDel,setConfirmDel]=useState(null);
  const [saving,setSaving]=useState(false);
  const [form,setForm]=useState({name:"",slug:"",description:"",category_type:"general",is_active:true,show_in_menu:true,show_in_app:true});

  const openCreate=()=>{ setForm({name:"",slug:"",description:"",category_type:"general",is_active:true,show_in_menu:true,show_in_app:true}); setModal({mode:"create"}); };
  const openEdit=(c)=>{ setForm({name:c.name||"",slug:c.slug||"",description:c.description||"",category_type:c.category_type||"general",is_active:!!c.is_active,show_in_menu:!!c.show_in_menu,show_in_app:!!c.show_in_app}); setModal({mode:"edit",data:c}); };

  const handleSave=async()=>{
    if(!form.name){showToast("Name required","error");return;}
    setSaving(true);
    try{
      if(modal.mode==="create"){await create(form);showToast("Category created!","success");}
      else{await update(modal.data.id,form);showToast("Category updated!","success");}
      setModal(null);
    }catch(e){showToast(e?.response?.data?.detail||"Failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("Deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="CONTENT TAXONOMY" icon={FolderOpen} color={C.purple}
      actions={<button style={S.btn(C.purple,"solid")} onClick={openCreate}><Plus size={12}/>NEW CATEGORY</button>}>
      <div style={{overflowX:"auto"}}>
        <table style={S.table}>
          <thead><tr>{["NAME","TYPE","CONTENT","VIEWS","MENU","APP","ACTIONS"].map(h=><th key={h} style={S.th}>{h}</th>)}</tr></thead>
          <tbody>
            {loading?<tr><td colSpan={7}><Empty label="LOADING..."/></td></tr>
            :(categories||[]).map(cat=>(
              <tr key={cat.id} onMouseEnter={e=>e.currentTarget.style.background=C.bgHover} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                <td style={S.td}>
                  <div style={{display:"flex",alignItems:"center",gap:8}}><Hash size={11} color={C.purple}/><span>{cat.name}</span></div>
                  <div style={{fontSize:10,color:C.textDim}}>{cat.slug}</div>
                </td>
                <td style={S.td}><span style={S.badge(C.purple)}>{cat.category_type}</span></td>
                <td style={{...S.td,color:C.cyan,fontFamily:"'Orbitron',monospace",fontSize:11}}>{cat.content_count??0}</td>
                <td style={{...S.td,color:C.textDim,fontSize:11}}>{cat.total_views?.toLocaleString()??0}</td>
                <td style={S.td}><PulseDot color={cat.show_in_menu?C.green:C.textDim}/></td>
                <td style={S.td}><PulseDot color={cat.show_in_app?C.green:C.textDim}/></td>
                <td style={S.td}>
                  <div style={{display:"flex",gap:6}}>
                    <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>openEdit(cat)}><Edit3 size={13} color={C.purple}/></button>
                    <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>setConfirmDel(cat)}><Trash2 size={13} color={C.pink}/></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
    <CrudModal open={!!modal} title={modal?.mode==="create"?"NEW CATEGORY":"EDIT CATEGORY"} color={C.purple} onClose={()=>setModal(null)} onSave={handleSave} saving={saving}>
      <label style={S.label}>Name *</label>
      <input style={S.input} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Category name"/>
      <label style={S.label}>Slug</label>
      <input style={S.input} value={form.slug} onChange={e=>setForm({...form,slug:e.target.value})} placeholder="category-slug"/>
      <label style={S.label}>Description</label>
      <textarea style={S.textarea} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
      <label style={S.label}>Type</label>
      <select style={S.select} value={form.category_type} onChange={e=>setForm({...form,category_type:e.target.value})}>
        {["general","blog","news","tutorial","offer","task","faq"].map(t=><option key={t} value={t}>{t}</option>)}
      </select>
      <div style={{display:"flex",gap:20,marginTop:16}}>
        {[{k:"is_active",l:"Active"},{k:"show_in_menu",l:"Show in Menu"},{k:"show_in_app",l:"Show in App"}].map(({k,l})=>(
          <label key={k} style={{display:"flex",alignItems:"center",gap:6,cursor:"pointer",fontSize:11}}>
            <input type="checkbox" checked={form[k]} onChange={e=>setForm({...form,[k]:e.target.checked})}/>{l}
          </label>
        ))}
      </div>
    </CrudModal>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.name} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  BANNERS
// ═══════════════════════════════════════════════════════════════════
const BannersSection=({showToast})=>{
  const {banners,stats,loading,fetch,create,update,remove,toggle}=useBanners();
  const [modal,setModal]=useState(null);
  const [confirmDel,setConfirmDel]=useState(null);
  const [saving,setSaving]=useState(false);
  const [form,setForm]=useState({name:"",title:"",description:"",banner_type:"image",position:"top",link_url:"",is_active:true,priority:0,reward_amount:"",start_date:"",end_date:""});

  const openCreate=()=>{ setForm({name:"",title:"",description:"",banner_type:"image",position:"top",link_url:"",is_active:true,priority:0,reward_amount:""}); setModal({mode:"create"}); };
  const openEdit=(b)=>{ setForm({name:b.name||"",title:b.title||"",description:b.description||"",banner_type:b.banner_type||"image",position:b.position||"top",link_url:b.link_url||"",is_active:!!b.is_active,priority:b.priority||0,reward_amount:b.reward_amount||"",start_date:b.start_date?b.start_date.slice(0,10):"",end_date:b.end_date?b.end_date.slice(0,10):""}); setModal({mode:"edit",data:b}); };

  const handleSave=async()=>{
    if(!form.name){showToast("Name required","error");return;}
    setSaving(true);
    try{
      if(modal.mode==="create"){await create(form);showToast("Banner created!","success");}
      else{await update(modal.data.id,form);showToast("Banner updated!","success");}
      setModal(null);
    }catch(e){showToast(e?.response?.data?.detail||"Failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("Deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="BANNER CONTROL" icon={Megaphone} color={C.pink}
      actions={<>
        {stats&&<div style={{display:"flex",gap:8}}>
          <span style={S.badge(C.green)}>Active: {stats.active}</span>
          <span style={S.badge(C.textDim)}>Total: {stats.total}</span>
        </div>}
        <button style={S.btn(C.pink,"solid")} onClick={openCreate}><Plus size={12}/>NEW BANNER</button>
      </>}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12,padding:18}}>
        {loading?<Empty label="LOADING..."/>
        :(banners||[]).map(b=>(
          <div key={b.id} style={{...S.card(b.is_active?C.pink:C.textDim),padding:14}}>
            <div style={{height:60,borderRadius:2,marginBottom:10,background:`linear-gradient(135deg,${C.pink}15,${C.purple}15)`,border:`1px solid ${C.pink}20`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Megaphone size={20} color={`${C.pink}80`}/>
            </div>
            <div style={{fontSize:12,marginBottom:4,color:C.text}}>{b.name||b.title}</div>
            <div style={{fontSize:10,color:C.textDim,marginBottom:8}}>{b.position} · {b.banner_type}</div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
              <StatusBadge status={b.is_active?"active":"inactive"}/>
              <span style={{fontSize:10,color:C.textDim}}>CTR: <span style={{color:C.cyan}}>{b.click_through_rate?.toFixed(2)??0}%</span></span>
            </div>
            <div style={{display:"flex",gap:6}}>
              <button style={S.btn(b.is_active?C.textDim:C.green)} onClick={()=>toggle(b.id,b.is_active)}>
                {b.is_active?<ToggleRight size={11}/>:<ToggleLeft size={11}/>}{b.is_active?"OFF":"ON"}
              </button>
              <button style={S.btn(C.purple)} onClick={()=>openEdit(b)}><Edit3 size={11}/></button>
              <button style={S.btn(C.pink)} onClick={()=>setConfirmDel(b)}><Trash2 size={11}/></button>
            </div>
          </div>
        ))}
        {!loading&&(!banners||banners.length===0)&&<Empty label="NO BANNERS DEPLOYED"/>}
      </div>
    </Section>
    <CrudModal open={!!modal} title={modal?.mode==="create"?"NEW BANNER":"EDIT BANNER"} color={C.pink} onClose={()=>setModal(null)} onSave={handleSave} saving={saving}>
      <label style={S.label}>Name *</label>
      <input style={S.input} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Banner name"/>
      <label style={S.label}>Title</label>
      <input style={S.input} value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="Display title"/>
      <label style={S.label}>Description</label>
      <textarea style={S.textarea} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginTop:14}}>
        <div>
          <label style={{...S.label,marginTop:0}}>Type</label>
          <select style={S.select} value={form.banner_type} onChange={e=>setForm({...form,banner_type:e.target.value})}>
            {["image","video","html","text"].map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label style={{...S.label,marginTop:0}}>Position</label>
          <select style={S.select} value={form.position} onChange={e=>setForm({...form,position:e.target.value})}>
            {["top","bottom","sidebar","popup","interstitial"].map(p=><option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>
      <label style={S.label}>Link URL</label>
      <input style={S.input} value={form.link_url} onChange={e=>setForm({...form,link_url:e.target.value})} placeholder="https://..."/>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginTop:14}}>
        <div>
          <label style={{...S.label,marginTop:0}}>Start Date</label>
          <input style={S.input} type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/>
        </div>
        <div>
          <label style={{...S.label,marginTop:0}}>End Date</label>
          <input style={S.input} type="date" value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/>
        </div>
      </div>
      <label style={S.label}>Priority</label>
      <input style={S.input} type="number" value={form.priority} onChange={e=>setForm({...form,priority:parseInt(e.target.value)||0})}/>
      <div style={{display:"flex",gap:10,marginTop:16,alignItems:"center"}}>
        <label style={{display:"flex",alignItems:"center",gap:6,cursor:"pointer",fontSize:11}}>
          <input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})}/> Active
        </label>
      </div>
    </CrudModal>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.name} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  FAQ
// ═══════════════════════════════════════════════════════════════════
const FAQSection=({showToast})=>{
  const {faqs,faqCategories,loading,search,create,update,remove}=useFAQs();
  const [modal,setModal]=useState(null);
  const [confirmDel,setConfirmDel]=useState(null);
  const [saving,setSaving]=useState(false);
  const [q,setQ]=useState("");
  const [form,setForm]=useState({question:"",short_answer:"",detailed_answer:"",category:"",priority:0,is_active:true,is_featured:false,show_in_app:true});

  const openCreate=()=>{ setForm({question:"",short_answer:"",detailed_answer:"",category:"",priority:0,is_active:true,is_featured:false,show_in_app:true}); setModal({mode:"create"}); };
  const openEdit=(f)=>{ setForm({question:f.question||"",short_answer:f.short_answer||"",detailed_answer:f.detailed_answer||"",category:f.category||"",priority:f.priority||0,is_active:!!f.is_active,is_featured:!!f.is_featured,show_in_app:!!f.show_in_app}); setModal({mode:"edit",data:f}); };

  const handleSave=async()=>{
    if(!form.question){showToast("Question required","error");return;}
    setSaving(true);
    try{
      if(modal.mode==="create"){await create(form);showToast("FAQ created!","success");}
      else{await update(modal.data.id,form);showToast("FAQ updated!","success");}
      setModal(null);
    }catch(e){showToast(e?.response?.data?.detail||"Failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("Deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="FAQ MATRIX" icon={HelpCircle} color={C.yellow}
      actions={<button style={S.btn(C.yellow,"solid")} onClick={openCreate}><Plus size={12}/>ADD FAQ</button>}>
      <div style={{display:"flex",gap:8,padding:"12px 18px",borderBottom:`1px solid ${C.border}`}}>
        <div style={{position:"relative",flex:1}}>
          <Search size={12} color={C.textDim} style={{position:"absolute",left:10,top:"50%",transform:"translateY(-50%)"}}/>
          <input style={{...S.input,paddingLeft:30}} placeholder="SEARCH FAQ..." value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==="Enter"&&search(q)}/>
        </div>
        <button style={S.btn(C.yellow)} onClick={()=>search(q)}><Search size={12}/>GO</button>
      </div>
      <div>
        {loading?<Empty label="SCANNING DATABASE..."/>
        :(faqs||[]).map((f,i)=>(
          <div key={f.id} style={{padding:"14px 18px",borderBottom:`1px solid ${C.border}`,transition:"background 0.2s"}}
            onMouseEnter={e=>e.currentTarget.style.background=C.bgHover} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
              <div style={{flex:1}}>
                <div style={{fontSize:12,marginBottom:4,color:C.text}}>
                  <span style={{color:C.yellow,marginRight:8,fontFamily:"'Orbitron',monospace",fontSize:10}}>#{String(i+1).padStart(3,"0")}</span>
                  {f.question}
                </div>
                {f.short_answer&&<div style={{fontSize:11,color:C.textDim,lineHeight:1.5}}>{f.short_answer.slice(0,100)}{f.short_answer.length>100?"...":""}</div>}
              </div>
              <div style={{display:"flex",gap:6,marginLeft:12,alignItems:"center"}}>
                {f.is_featured&&<Star size={11} color={C.yellow}/>}
                <StatusBadge status={f.is_active?"active":"inactive"}/>
                <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>openEdit(f)}><Edit3 size={13} color={C.purple}/></button>
                <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>setConfirmDel(f)}><Trash2 size={13} color={C.pink}/></button>
              </div>
            </div>
            <div style={{display:"flex",gap:12,marginTop:8,fontSize:10,color:C.textDim}}>
              <span style={{color:C.cyan}}>{f.category_name||"Uncategorized"}</span>
              <span>👁 {f.view_count??0}</span>
              <span style={{color:C.green}}>✓ {f.helpful_count??0}</span>
              <span style={{color:C.pink}}>✗ {f.not_helpful_count??0}</span>
              <span>Priority: {f.priority??0}</span>
            </div>
          </div>
        ))}
        {!loading&&faqs?.length===0&&<Empty label="NO FAQs FOUND"/>}
      </div>
    </Section>
    <CrudModal open={!!modal} title={modal?.mode==="create"?"NEW FAQ":"EDIT FAQ"} color={C.yellow} onClose={()=>setModal(null)} onSave={handleSave} saving={saving}>
      <label style={S.label}>Question *</label>
      <input style={S.input} value={form.question} onChange={e=>setForm({...form,question:e.target.value})} placeholder="FAQ question"/>
      <label style={S.label}>Short Answer</label>
      <textarea style={S.textarea} value={form.short_answer} onChange={e=>setForm({...form,short_answer:e.target.value})} placeholder="Brief answer..."/>
      <label style={S.label}>Detailed Answer</label>
      <textarea style={{...S.textarea,minHeight:100}} value={form.detailed_answer} onChange={e=>setForm({...form,detailed_answer:e.target.value})} placeholder="Full detailed answer..."/>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginTop:14}}>
        <div>
          <label style={{...S.label,marginTop:0}}>Category</label>
          <select style={S.select} value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>
            <option value="">— None —</option>
            {(faqCategories||[]).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label style={{...S.label,marginTop:0}}>Priority</label>
          <input style={S.input} type="number" value={form.priority} onChange={e=>setForm({...form,priority:parseInt(e.target.value)||0})}/>
        </div>
      </div>
      <div style={{display:"flex",gap:16,marginTop:16}}>
        {[{k:"is_active",l:"Active"},{k:"is_featured",l:"Featured"},{k:"show_in_app",l:"Show in App"}].map(({k,l})=>(
          <label key={k} style={{display:"flex",alignItems:"center",gap:6,cursor:"pointer",fontSize:11}}>
            <input type="checkbox" checked={form[k]} onChange={e=>setForm({...form,[k]:e.target.checked})}/>{l}
          </label>
        ))}
      </div>
    </CrudModal>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.question} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  COMMENTS
// ═══════════════════════════════════════════════════════════════════
const CommentsSection=({showToast})=>{
  const {comments,loading,fetch,fetchPending,approve,flag,remove}=useComments();
  const [confirmDel,setConfirmDel]=useState(null);
  const [filter,setFilter]=useState("all");

  const displayed=(comments||[]).filter(c=>{
    if(filter==="pending") return !c.is_approved;
    if(filter==="flagged") return c.is_flagged;
    if(filter==="approved") return c.is_approved;
    return true;
  });

  const handleApprove=async(id)=>{
    try{await approve(id);showToast("Comment approved!","success");}
    catch{showToast("Failed","error");}
  };
  const handleFlag=async(id)=>{
    try{await flag(id,"spam");showToast("Comment flagged","warning");}
    catch{showToast("Failed","error");}
  };
  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("Deleted","success");}
    catch{showToast("Failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="COMMENT MODERATION" icon={MessageSquare} color={C.green}
      actions={<>
        <span style={S.badge(C.yellow)}>Pending: {(comments||[]).filter(c=>!c.is_approved).length}</span>
        <button style={S.btn(C.yellow)} onClick={fetchPending}><AlertCircle size={12}/>PENDING ONLY</button>
        <button style={S.btn(C.green)} onClick={()=>fetch()}><RefreshCw size={12}/>REFRESH</button>
      </>}>
      <div style={{display:"flex",gap:8,padding:"10px 18px",borderBottom:`1px solid ${C.border}`}}>
        {["all","pending","approved","flagged"].map(f=>(
          <button key={f} style={S.tab(filter===f)} onClick={()=>setFilter(f)}>{f.toUpperCase()}</button>
        ))}
      </div>
      <table style={S.table}>
        <thead><tr>{["USER","COMMENT","RATING","STATUS","DATE","ACTIONS"].map(h=><th key={h} style={S.th}>{h}</th>)}</tr></thead>
        <tbody>
          {loading?<tr><td colSpan={6}><Empty label="LOADING..."/></td></tr>
          :displayed.length===0?<tr><td colSpan={6}><Empty label="NO COMMENTS"/></td></tr>
          :displayed.slice(0,12).map(c=>(
            <tr key={c.id} onMouseEnter={e=>e.currentTarget.style.background=C.bgHover} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
              <td style={S.td}><div style={{fontSize:12,color:C.cyan}}>{c.user_username||c.user_name||"Anonymous"}</div></td>
              <td style={{...S.td,maxWidth:260}}>
                <div style={{fontSize:11,color:C.text,lineHeight:1.4}}>{(c.comment||"").slice(0,80)}{c.comment?.length>80?"...":""}</div>
                {c.is_flagged&&<span style={{...S.badge(C.pink),marginTop:4}}>FLAGGED</span>}
              </td>
              <td style={S.td}>{c.rating?<span style={{color:C.yellow}}>{"★".repeat(c.rating)}{"☆".repeat(5-c.rating)}</span>:"—"}</td>
              <td style={S.td}><StatusBadge status={c.is_approved?"approved":"pending"}/></td>
              <td style={{...S.td,fontSize:11,color:C.textDim}}>{c.created_at?new Date(c.created_at).toLocaleDateString():"—"}</td>
              <td style={S.td}>
                <div style={{display:"flex",gap:6}}>
                  {!c.is_approved&&<button style={S.btn(C.green)} onClick={()=>handleApprove(c.id)}><CheckCircle size={11}/>OK</button>}
                  <button style={S.btn(C.pink)} onClick={()=>handleFlag(c.id)}><XCircle size={11}/>FLAG</button>
                  <button style={{background:"none",border:"none",cursor:"pointer"}} onClick={()=>setConfirmDel(c)}><Trash2 size={13} color={C.pink}/></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
    <ConfirmModal open={!!confirmDel} label={"this comment"} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  FILES
// ═══════════════════════════════════════════════════════════════════
const FilesSection=({showToast})=>{
  const {files,loading,remove,download}=useFiles();
  const [confirmDel,setConfirmDel]=useState(null);
  const FILE_ICONS={pdf:{icon:BookOpen,color:C.pink},document:{icon:FileText,color:C.cyan},image:{icon:Image,color:C.purple},video:{icon:Film,color:C.orange},archive:{icon:Database,color:C.yellow},spreadsheet:{icon:Layers,color:C.green}};

  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("File deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="FILE REPOSITORY" icon={Database} color={C.cyan}
      actions={<button style={S.btn(C.cyan,"solid")}><Upload size={12}/>UPLOAD</button>}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:10,padding:18}}>
        {loading?<Empty label="SCANNING STORAGE..."/>
        :(files||[]).map(f=>{
          const cfg=FILE_ICONS[f.file_type]||{icon:FileText,color:C.textDim};
          return(
            <div key={f.id} style={{...S.card(cfg.color),padding:12,display:"flex",flexDirection:"column",gap:8}}>
              <div style={{display:"flex",alignItems:"center",gap:8}}><cfg.icon size={16} color={cfg.color}/><span style={S.badge(cfg.color)}>{f.file_type}</span></div>
              <div style={{fontSize:11,color:C.text}}>{f.name}</div>
              <div style={{fontSize:10,color:C.textDim}}>{f.file_size_human||`${f.file_size} B`}</div>
              <div style={{display:"flex",gap:6,marginTop:4}}>
                <button style={S.btn(cfg.color)} onClick={()=>download(f.id)}><Download size={10}/>DL</button>
                <button style={S.btn(C.pink)} onClick={()=>setConfirmDel(f)}><Trash2 size={10}/></button>
              </div>
            </div>
          );
        })}
        {!loading&&(!files||files.length===0)&&<Empty label="NO FILES STORED"/>}
      </div>
    </Section>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.name} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  GALLERY
// ═══════════════════════════════════════════════════════════════════
const GallerySection=({showToast})=>{
  const {galleries,loading,create,remove}=useGalleries();
  const [modal,setModal]=useState(null);
  const [confirmDel,setConfirmDel]=useState(null);
  const [saving,setSaving]=useState(false);
  const [form,setForm]=useState({title:"",description:"",is_active:true,is_featured:false});

  const handleSave=async()=>{
    if(!form.title){showToast("Title required","error");return;}
    setSaving(true);
    try{await create(form);showToast("Gallery created!","success");setModal(null);}
    catch(e){showToast(e?.response?.data?.detail||"Failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{await remove(confirmDel.id);showToast("Deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  return(
    <>
    <Section title="IMAGE GALLERY" icon={Image} color={C.purple}
      actions={<button style={S.btn(C.purple,"solid")} onClick={()=>setModal({mode:"create"})}><Plus size={12}/>NEW GALLERY</button>}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12,padding:18}}>
        {loading?<Empty label="LOADING..."/>
        :(galleries||[]).map(g=>(
          <div key={g.id} style={{...S.card(C.purple),padding:14}}>
            <div style={{height:80,borderRadius:2,marginBottom:10,background:`linear-gradient(135deg,${C.purple}15,${C.cyan}15)`,border:`1px solid ${C.purple}20`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Image size={24} color={`${C.purple}80`}/>
            </div>
            <div style={{fontSize:12,color:C.text,marginBottom:4}}>{g.title}</div>
            <div style={{fontSize:10,color:C.textDim,marginBottom:8}}>
              {g.image_count??0} images
              {g.is_featured&&<span style={{...S.badge(C.yellow),marginLeft:6}}>FEATURED</span>}
            </div>
            <div style={{display:"flex",gap:6}}>
              <button style={S.btn(C.pink)} onClick={()=>setConfirmDel(g)}><Trash2 size={11}/>DELETE</button>
            </div>
          </div>
        ))}
        {!loading&&(!galleries||galleries.length===0)&&<Empty label="NO GALLERIES"/>}
      </div>
    </Section>
    <CrudModal open={!!modal} title="NEW GALLERY" color={C.purple} onClose={()=>setModal(null)} onSave={handleSave} saving={saving}>
      <label style={S.label}>Title *</label>
      <input style={S.input} value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="Gallery title"/>
      <label style={S.label}>Description</label>
      <textarea style={S.textarea} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
      <div style={{display:"flex",gap:16,marginTop:16}}>
        <label style={{display:"flex",alignItems:"center",gap:6,cursor:"pointer",fontSize:11}}>
          <input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})}/> Active
        </label>
        <label style={{display:"flex",alignItems:"center",gap:6,cursor:"pointer",fontSize:11}}>
          <input type="checkbox" checked={form.is_featured} onChange={e=>setForm({...form,is_featured:e.target.checked})}/> Featured
        </label>
      </div>
    </CrudModal>
    <ConfirmModal open={!!confirmDel} label={confirmDel?.title} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  ANALYTICS
// ═══════════════════════════════════════════════════════════════════
const AnalyticsSection=()=>{
  const {today,analytics,loading}=useSiteAnalytics();
  const metrics=today?[
    {label:"Page Views",value:today.page_views,color:C.cyan},
    {label:"Unique Visitors",value:today.unique_visitors,color:C.purple},
    {label:"New Users",value:today.new_users,color:C.green},
    {label:"Session Count",value:today.session_count,color:C.orange},
    {label:"Bounce Rate",value:`${today.bounce_rate?.toFixed(1)??0}%`,color:C.yellow},
    {label:"Avg Session",value:`${today.avg_session_duration?.toFixed(0)??0}s`,color:C.pink},
    {label:"Total Earnings",value:`$${today.total_earnings??0}`,color:C.green},
    {label:"Withdrawals",value:`$${today.total_withdrawals??0}`,color:C.pink},
  ]:[];

  return(
    <Section title="ANALYTICS NEXUS" icon={BarChart3} color={C.orange}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,padding:18}}>
        {metrics.map(m=>(
          <div key={m.label} style={{...S.card(m.color),padding:"12px 14px"}}>
            <div style={{fontSize:20,fontFamily:"'Orbitron',monospace",color:m.color}}>{m.value??0}</div>
            <div style={S.statLabel}>{m.label}</div>
          </div>
        ))}
        {!today&&!loading&&<Empty label="AWAITING TELEMETRY DATA"/>}
      </div>
      <div style={{padding:"0 18px 18px"}}>
        <div style={{...S.card(C.orange),padding:14}}>
          <div style={{fontSize:10,color:C.textDim,letterSpacing:2,marginBottom:12}}>ENGAGEMENT DISTRIBUTION</div>
          {[
            {label:"Content Views",val:today?.content_views??0,color:C.cyan,max:1000},
            {label:"Content Shares",val:today?.content_shares??0,color:C.purple,max:500},
            {label:"Banner Clicks",val:today?.banner_clicks??0,color:C.pink,max:300},
            {label:"Comments",val:today?.content_comments??0,color:C.green,max:200},
          ].map(bar=>(
            <div key={bar.label} style={{marginBottom:10}}>
              <div style={{display:"flex",justifyContent:"space-between",fontSize:10,marginBottom:4}}>
                <span style={{color:C.textDim}}>{bar.label}</span>
                <span style={{color:bar.color,fontFamily:"'Orbitron',monospace"}}>{bar.val}</span>
              </div>
              <div style={{height:3,background:`${bar.color}15`,borderRadius:2}}>
                <div style={{height:"100%",borderRadius:2,width:`${Math.min(100,(bar.val/bar.max)*100)}%`,background:`linear-gradient(90deg,${bar.color},${bar.color}80)`,boxShadow:`0 0 6px ${bar.color}`,transition:"width 0.6s ease"}}/>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  SETTINGS placeholder
// ═══════════════════════════════════════════════════════════════════
const SettingsSection=()=>(
  <Section title="SYSTEM SETTINGS" icon={Settings} color={C.textDim}>
    <Empty label="SETTINGS NODE — COMING ONLINE"/>
  </Section>
);

// ═══════════════════════════════════════════════════════════════════
//  MAIN CMS PAGE
// ═══════════════════════════════════════════════════════════════════
export default function CMSPage(){
  const [active,setActive]=useState("overview");
  const [toast,setToast]=useState(null);
  const toastTimer=useRef(null);

  const showToast=useCallback((message,type="success")=>{
    setToast({message,type});
    clearTimeout(toastTimer.current);
    toastTimer.current=setTimeout(()=>setToast(null),3500);
  },[]);

  useEffect(()=>{
    if(!document.getElementById("cms-fonts")){
      const link=document.createElement("link");
      link.id="cms-fonts";link.rel="stylesheet";
      link.href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700&display=swap";
      document.head.appendChild(link);
    }
    if(!document.getElementById("cms-kf")){
      const style=document.createElement("style");
      style.id="cms-kf";
      style.textContent=`
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
        @keyframes scanline{0%{transform:translateY(-100%)}100%{transform:translateY(100vh)}}
        @keyframes flicker{0%,100%{opacity:1}92%{opacity:.9}94%{opacity:1}96%{opacity:.85}98%{opacity:1}}
        @keyframes slideIn{from{transform:translateX(20px);opacity:0}to{transform:translateX(0);opacity:1}}
        *{scrollbar-width:thin;scrollbar-color:#00f5ff20 transparent}
        *::-webkit-scrollbar{width:4px}
        *::-webkit-scrollbar-track{background:transparent}
        *::-webkit-scrollbar-thumb{background:#00f5ff30;border-radius:2px}
      `;
      document.head.appendChild(style);
    }
  },[]);

  const SECTION_MAP={
    overview:    <OverviewSection setActive={setActive}/>,
    pages:       <PagesSection showToast={showToast}/>,
    categories:  <CategoriesSection showToast={showToast}/>,
    banners:     <BannersSection showToast={showToast}/>,
    faq:         <FAQSection showToast={showToast}/>,
    gallery:     <GallerySection showToast={showToast}/>,
    files:       <FilesSection showToast={showToast}/>,
    comments:    <CommentsSection showToast={showToast}/>,
    analytics:   <AnalyticsSection/>,
    settings:    <SettingsSection/>,
  };

  const activeNav=NAV.find(n=>n.id===active);

  return(
    <div style={S.page}>
      <div style={S.grid}/>
      <div style={S.blob(C.cyan,"-10%","-5%",600)}/>
      <div style={S.blob(C.purple,"60%","70%",500)}/>
      <div style={S.blob(C.pink,"30%","-8%",300)}/>
      <div style={{position:"fixed",top:0,left:0,right:0,height:2,zIndex:1000,background:`linear-gradient(transparent,${C.cyan}08,transparent)`,animation:"scanline 8s linear infinite",pointerEvents:"none"}}/>

      <Toast toast={toast}/>
        <PageEndpointPanel pageKey="CMS" title="CMS Endpoints" />

      <div style={{display:"flex",position:"relative",zIndex:1}}>
        {/* SIDEBAR */}
        <aside style={S.sidebar}>
          <div style={S.logo}>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6}}>
              <div style={{width:28,height:28,background:`linear-gradient(135deg,${C.cyan},${C.purple})`,borderRadius:2,display:"flex",alignItems:"center",justifyContent:"center"}}><Layers size={14} color="#000"/></div>
              <div>
                <div style={S.logoText}>CMS NEXUS</div>
                <div style={S.logoSub}>HOLOGRAPHIC CONTROL</div>
              </div>
            </div>
            <div style={{display:"flex",alignItems:"center",gap:6,marginTop:8}}>
              <PulseDot color={C.green}/>
              <span style={{fontSize:10,color:C.textDim}}>ALL SYSTEMS NOMINAL</span>
            </div>
          </div>
          <nav style={S.navSection}>
            {NAV.map(item=>{
              if(item.id.startsWith("div")) return <div key={item.id} style={S.navLabel}>{item.label}</div>;
              const Icon=item.icon;
              const isActive=active===item.id;
              return(
                <div key={item.id} style={S.navItem(isActive,item.color)} onClick={()=>setActive(item.id)}
                  onMouseEnter={e=>{if(!isActive)e.currentTarget.style.color=item.color;}}
                  onMouseLeave={e=>{if(!isActive)e.currentTarget.style.color=C.textDim;}}>
                  <Icon size={13}/><span>{item.label}</span>
                  {isActive&&<ChevronRight size={10} style={{marginLeft:"auto"}}/>}
                </div>
              );
            })}
          </nav>
          <div style={{padding:"12px 20px",borderTop:`1px solid ${C.border}`,fontSize:10,color:C.textDim}}>
            <div style={{marginBottom:4}}>v2.4.1 // CYBERPUNK BUILD</div>
            <div style={{color:C.cyan}}>◈ NEURAL LINK ACTIVE</div>
          </div>
        </aside>

        {/* MAIN */}
        <main style={{flex:1,padding:"24px 28px",overflowY:"auto",minHeight:"100vh"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20}}>
            <div>
              <div style={{fontSize:9,color:C.textDim,letterSpacing:4,textTransform:"uppercase",marginBottom:2}}>CONTROL CENTER //</div>
              <div style={{fontSize:20,fontFamily:"'Orbitron',monospace",color:activeNav?.color||C.cyan,letterSpacing:2,textTransform:"uppercase",textShadow:`0 0 20px ${activeNav?.color||C.cyan}60`}}>
                {activeNav?.label||"OVERVIEW"}
              </div>
            </div>
            <div style={{display:"flex",gap:10,alignItems:"center"}}>
              <button style={S.btn(C.cyan)} onClick={()=>window.location.reload()}><RefreshCw size={12}/>SYNC</button>
            </div>
          </div>
          <div style={{fontSize:10,color:C.textDim,marginBottom:20,letterSpacing:1}}>
            <span style={{color:C.cyan}}>◈ NEXUS</span>
            <ChevronRight size={10} style={{display:"inline",margin:"0 4px"}}/>
            <span>CMS</span>
            <ChevronRight size={10} style={{display:"inline",margin:"0 4px"}}/>
            <span style={{color:C.text}}>{activeNav?.label||"OVERVIEW"}</span>
          </div>
          <div style={{animation:"flicker 0.1s ease"}}>
            {SECTION_MAP[active]||<Empty label={`MODULE ${active.toUpperCase()} — LOADING`}/>}
          </div>
        </main>
      </div>
    </div>
  );
}



// import { useState, useEffect, useRef } from "react";
// import {
//   LayoutDashboard, FileText, Image, MessageSquare, Settings,
//   HelpCircle, Megaphone, FolderOpen, Globe, Shield, BarChart3,
//   Plus, Search, Filter, Eye, Edit3, Trash2, Star, Pin,
//   TrendingUp, Users, Zap, RefreshCw, ChevronRight, Tag,
//   Calendar, Clock, CheckCircle, AlertCircle, XCircle,
//   Upload, Download, Link2, Layers, Database, Activity,
//   Bell, BookOpen, Film, Hash, Bookmark, Award
// } from "lucide-react";
// import {
//   useContentPages,
//   useContentCategories,
//   useBanners,
//   useFAQs,
//   useComments,
//   useSiteAnalytics,
//   useFiles,
// } from "../hooks/useCms";

// // ─── Cyberpunk Color System ───────────────────────────────────────
// const C = {
//   cyan:    "#00f5ff",
//   purple:  "#bf00ff",
//   pink:    "#ff006e",
//   green:   "#00ff88",
//   yellow:  "#ffe600",
//   orange:  "#ff6b00",
//   bg:      "#050b14",
//   bgCard:  "rgba(8,20,40,0.72)",
//   bgHover: "rgba(0,245,255,0.04)",
//   border:  "rgba(0,245,255,0.18)",
//   borderP: "rgba(191,0,255,0.22)",
//   text:    "#c8e6f0",
//   textDim: "#4a7a8a",
// };

// // ─── Inline Styles ─────────────────────────────────────────────────
// const S = {
//   page: {
//     minHeight: "100vh",
//     background: C.bg,
//     fontFamily: "'Share Tech Mono', 'Courier New', monospace",
//     color: C.text,
//     position: "relative",
//     overflow: "hidden",
//   },
//   // Animated grid background
//   grid: {
//     position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none",
//     backgroundImage: `
//       linear-gradient(rgba(0,245,255,0.03) 1px, transparent 1px),
//       linear-gradient(90deg, rgba(0,245,255,0.03) 1px, transparent 1px)
//     `,
//     backgroundSize: "40px 40px",
//   },
//   // Ambient glow blobs
//   blob: (color, top, left, size = 400) => ({
//     position: "fixed", top, left,
//     width: size, height: size,
//     background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`,
//     borderRadius: "50%", filter: "blur(40px)", pointerEvents: "none", zIndex: 0,
//   }),
//   sidebar: {
//     width: 240, flexShrink: 0,
//     background: "rgba(5,12,24,0.9)",
//     borderRight: `1px solid ${C.border}`,
//     backdropFilter: "blur(20px)",
//     position: "sticky", top: 0, height: "100vh",
//     display: "flex", flexDirection: "column",
//     zIndex: 10,
//   },
//   logo: {
//     padding: "24px 20px 20px",
//     borderBottom: `1px solid ${C.border}`,
//   },
//   logoText: {
//     fontSize: 11, letterSpacing: 4, color: C.cyan,
//     textTransform: "uppercase", fontWeight: 700,
//   },
//   logoSub: { fontSize: 9, color: C.textDim, letterSpacing: 2, marginTop: 2 },
//   navSection: { padding: "12px 0", flex: 1, overflowY: "auto" },
//   navLabel: {
//     fontSize: 9, letterSpacing: 3, color: C.textDim,
//     padding: "8px 20px 4px", textTransform: "uppercase",
//   },
//   navItem: (active, color = C.cyan) => ({
//     display: "flex", alignItems: "center", gap: 10,
//     padding: "9px 20px", cursor: "pointer", transition: "all 0.2s",
//     background: active ? `${color}10` : "transparent",
//     borderLeft: active ? `2px solid ${color}` : "2px solid transparent",
//     color: active ? color : C.textDim,
//     fontSize: 12,
//   }),
//   // Glass card
//   card: (glowColor = C.cyan) => ({
//     background: C.bgCard,
//     backdropFilter: "blur(16px)",
//     border: `1px solid ${glowColor}28`,
//     borderRadius: 4,
//     boxShadow: `0 0 20px ${glowColor}08, inset 0 1px 0 ${glowColor}15`,
//     position: "relative",
//   }),
//   cardHeader: {
//     display: "flex", alignItems: "center", justifyContent: "space-between",
//     padding: "14px 18px",
//     borderBottom: `1px solid ${C.border}`,
//   },
//   cardTitle: { fontSize: 11, letterSpacing: 2, textTransform: "uppercase", color: C.cyan },
//   statGrid: {
//     display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
//     padding: "0 0 16px",
//   },
//   statCard: (color) => ({
//     ...S.card(color),
//     padding: "16px",
//     display: "flex", flexDirection: "column", gap: 6,
//   }),
//   statNum: (color) => ({
//     fontSize: 28, fontWeight: 700, color,
//     fontFamily: "'Orbitron', monospace",
//     lineHeight: 1,
//   }),
//   statLabel: { fontSize: 10, color: C.textDim, letterSpacing: 2, textTransform: "uppercase" },
//   statDelta: (up) => ({
//     fontSize: 10, color: up ? C.green : C.pink,
//     display: "flex", alignItems: "center", gap: 3,
//   }),
//   // Table
//   table: { width: "100%", borderCollapse: "collapse" },
//   th: {
//     fontSize: 9, letterSpacing: 2, color: C.textDim,
//     padding: "10px 14px", textAlign: "left",
//     borderBottom: `1px solid ${C.border}`,
//     textTransform: "uppercase",
//   },
//   td: {
//     padding: "11px 14px", fontSize: 12,
//     borderBottom: `1px solid rgba(0,245,255,0.06)`,
//     verticalAlign: "middle",
//   },
//   // Badges
//   badge: (color) => ({
//     display: "inline-flex", alignItems: "center", gap: 4,
//     padding: "2px 8px", borderRadius: 2,
//     background: `${color}18`, border: `1px solid ${color}40`,
//     color: color, fontSize: 10, letterSpacing: 1,
//     textTransform: "uppercase",
//   }),
//   // Buttons
//   btn: (color = C.cyan, variant = "outline") => ({
//     display: "inline-flex", alignItems: "center", gap: 6,
//     padding: "7px 14px", borderRadius: 2, cursor: "pointer",
//     fontSize: 11, letterSpacing: 1, transition: "all 0.2s",
//     textTransform: "uppercase",
//     ...(variant === "solid"
//       ? { background: `${color}20`, border: `1px solid ${color}80`, color }
//       : { background: "transparent", border: `1px solid ${color}40`, color }),
//   }),
//   input: {
//     background: "rgba(0,245,255,0.04)",
//     border: `1px solid ${C.border}`,
//     borderRadius: 2, color: C.text, fontSize: 12,
//     padding: "8px 12px", outline: "none",
//     fontFamily: "inherit",
//   },
//   // Tab
//   tab: (active) => ({
//     padding: "8px 16px", fontSize: 11, cursor: "pointer",
//     letterSpacing: 1, textTransform: "uppercase",
//     color: active ? C.cyan : C.textDim,
//     borderBottom: active ? `2px solid ${C.cyan}` : "2px solid transparent",
//     transition: "all 0.2s", background: "transparent", border: "none",
//     fontFamily: "inherit",
//   }),
// };

// // ─── Nav Config ────────────────────────────────────────────────────
// const NAV = [
//   { id: "overview",    label: "Overview",    icon: LayoutDashboard, color: C.cyan   },
//   { id: "divider1",   label: "CONTENT" },
//   { id: "pages",      label: "Pages",        icon: FileText,        color: C.cyan   },
//   { id: "categories", label: "Categories",   icon: FolderOpen,      color: C.purple },
//   { id: "banners",    label: "Banners",      icon: Megaphone,       color: C.pink   },
//   { id: "faq",        label: "FAQ",          icon: HelpCircle,      color: C.yellow },
//   { id: "divider2",   label: "MEDIA" },
//   { id: "gallery",    label: "Gallery",      icon: Image,           color: C.purple },
//   { id: "files",      label: "Files",        icon: Database,        color: C.cyan   },
//   { id: "divider3",   label: "ENGAGEMENT" },
//   { id: "comments",   label: "Comments",     icon: MessageSquare,   color: C.green  },
//   { id: "analytics",  label: "Analytics",    icon: BarChart3,       color: C.orange },
//   { id: "divider4",   label: "SYSTEM" },
//   { id: "permissions",label: "Permissions",  icon: Shield,          color: C.pink   },
//   { id: "settings",   label: "Settings",     icon: Settings,        color: C.textDim},
// ];

// // ─── Status Badge ──────────────────────────────────────────────────
// const STATUS_COLORS = {
//   published: C.green, draft: C.textDim, scheduled: C.yellow,
//   archived: C.orange, expired: C.pink, review: C.purple,
//   approved: C.cyan, active: C.green, inactive: C.textDim,
//   pending: C.yellow, rejected: C.pink,
// };
// const StatusBadge = ({ status }) => (
//   <span style={S.badge(STATUS_COLORS[status] || C.textDim)}>
//     {status}
//   </span>
// );

// // ─── Neon Pulse dot ────────────────────────────────────────────────
// const PulseDot = ({ color = C.green }) => (
//   <span style={{
//     display: "inline-block", width: 6, height: 6, borderRadius: "50%",
//     background: color, boxShadow: `0 0 6px ${color}`,
//     animation: "pulse 2s infinite",
//   }} />
// );

// // ─── Stat Card ─────────────────────────────────────────────────────
// const StatCard = ({ label, value, color, delta, icon: Icon, sub }) => (
//   <div style={S.statCard(color)}>
//     <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
//       <div>
//         <div style={S.statNum(color)}>{value ?? "—"}</div>
//         <div style={S.statLabel}>{label}</div>
//       </div>
//       {Icon && (
//         <div style={{
//           width: 36, height: 36, borderRadius: 4,
//           background: `${color}12`, border: `1px solid ${color}30`,
//           display: "flex", alignItems: "center", justifyContent: "center",
//         }}>
//           <Icon size={16} color={color} />
//         </div>
//       )}
//     </div>
//     {(delta || sub) && (
//       <div style={S.statDelta(delta >= 0)}>
//         {delta != null && <>{delta >= 0 ? "↑" : "↓"} {Math.abs(delta)}%</>}
//         {sub && <span style={{ color: C.textDim }}>{sub}</span>}
//       </div>
//     )}
//   </div>
// );

// // ─── Section Wrapper ───────────────────────────────────────────────
// const Section = ({ title, icon: Icon, color = C.cyan, children, actions }) => (
//   <div style={S.card(color)}>
//     <div style={S.cardHeader}>
//       <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//         {Icon && <Icon size={14} color={color} />}
//         <span style={{ ...S.cardTitle, color }}>{title}</span>
//       </div>
//       {actions && <div style={{ display: "flex", gap: 8 }}>{actions}</div>}
//     </div>
//     <div>{children}</div>
//   </div>
// );

// // ─── Search + Filter Bar ───────────────────────────────────────────
// const SearchBar = ({ placeholder = "SEARCH..." }) => (
//   <div style={{ display: "flex", gap: 8, padding: "12px 18px", borderBottom: `1px solid ${C.border}` }}>
//     <div style={{ position: "relative", flex: 1 }}>
//       <Search size={12} color={C.textDim} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)" }} />
//       <input style={{ ...S.input, width: "100%", paddingLeft: 30, boxSizing: "border-box" }} placeholder={placeholder} />
//     </div>
//     <button style={S.btn(C.purple)}><Filter size={12} />FILTER</button>
//   </div>
// );

// // ─── Empty State ───────────────────────────────────────────────────
// const Empty = ({ color = C.textDim, label = "NO DATA" }) => (
//   <div style={{ padding: "40px 0", textAlign: "center", color: C.textDim, fontSize: 11, letterSpacing: 2 }}>
//     <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.3 }}>◈</div>
//     {label}
//   </div>
// );

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: OVERVIEW
// // ═══════════════════════════════════════════════════════════════════
// const OverviewSection = () => {
//   const { analytics, today } = useSiteAnalytics();
//   const { pages } = useContentPages({ status: "published" });
//   const { comments } = useComments({ is_approved: false });

//   return (
//     <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
//       {/* Stat row */}
//       <div style={S.statGrid}>
//         <StatCard label="Total Pages"        value={pages?.length ?? 0}            color={C.cyan}   icon={FileText}  delta={12} />
//         <StatCard label="Page Views Today"   value={today?.page_views ?? 0}        color={C.purple} icon={Eye}       delta={5}  />
//         <StatCard label="Pending Comments"   value={comments?.length ?? 0}         color={C.yellow} icon={MessageSquare} />
//         <StatCard label="Active Users"       value={today?.active_users ?? 0}      color={C.green}  icon={Users}     delta={8}  />
//       </div>
//       <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
//         {/* Recent Activity */}
//         <Section title="SYSTEM STATUS" icon={Activity} color={C.cyan}>
//           {[
//             { label: "Content Engine",  status: "ONLINE",  color: C.green  },
//             { label: "Banner Service",  status: "ONLINE",  color: C.green  },
//             { label: "Cache Layer",     status: "ACTIVE",  color: C.cyan   },
//             { label: "Media CDN",       status: "SYNCING", color: C.yellow },
//             { label: "Analytics DB",    status: "ONLINE",  color: C.green  },
//           ].map((item) => (
//             <div key={item.label} style={{
//               display: "flex", justifyContent: "space-between", alignItems: "center",
//               padding: "10px 18px", borderBottom: `1px solid ${C.border}`,
//             }}>
//               <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//                 <PulseDot color={item.color} />
//                 <span style={{ fontSize: 12 }}>{item.label}</span>
//               </div>
//               <span style={{ ...S.badge(item.color) }}>{item.status}</span>
//             </div>
//           ))}
//         </Section>

//         {/* Quick Actions */}
//         <Section title="QUICK ACTIONS" icon={Zap} color={C.purple}>
//           <div style={{ padding: "14px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
//             {[
//               { label: "New Page",       icon: FileText,     color: C.cyan   },
//               { label: "Upload Media",   icon: Upload,       color: C.purple },
//               { label: "New Banner",     icon: Megaphone,    color: C.pink   },
//               { label: "Add FAQ",        icon: HelpCircle,   color: C.yellow },
//               { label: "View Analytics", icon: BarChart3,    color: C.orange },
//             ].map((a) => (
//               <button key={a.label} style={{ ...S.btn(a.color, "solid"), justifyContent: "flex-start" }}>
//                 <a.icon size={12} />
//                 {a.label}
//               </button>
//             ))}
//           </div>
//         </Section>
//       </div>

//       {/* Analytics row */}
//       <div style={S.statGrid}>
//         <StatCard label="Content Views"   value={today?.content_views ?? 0}     color={C.orange} icon={BarChart3} />
//         <StatCard label="Content Shares"  value={today?.content_shares ?? 0}    color={C.purple} icon={Globe}     />
//         <StatCard label="Banner Clicks"   value={today?.banner_clicks ?? 0}     color={C.pink}   icon={Megaphone} />
//         <StatCard label="Offer Completions" value={today?.offer_completions ?? 0} color={C.green} icon={CheckCircle} />
//       </div>
//     </div>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: PAGES
// // ═══════════════════════════════════════════════════════════════════
// const PagesSection = () => {
//   const [tab, setTab] = useState("all");
//   const { pages, loading, fetchPublished, fetchFeatured, createPage } = useContentPages();

//   const tabConfig = [
//     { id: "all",       label: "ALL"       },
//     { id: "published", label: "PUBLISHED" },
//     { id: "draft",     label: "DRAFTS"    },
//     { id: "scheduled", label: "SCHEDULED" },
//   ];

//   return (
//     <Section title="CONTENT PAGES" icon={FileText} color={C.cyan}
//       actions={
//         <button style={S.btn(C.cyan, "solid")}><Plus size={12} />NEW PAGE</button>
//       }
//     >
//       {/* Tabs */}
//       <div style={{ display: "flex", borderBottom: `1px solid ${C.border}`, padding: "0 18px" }}>
//         {tabConfig.map((t) => (
//           <button key={t.id} style={S.tab(tab === t.id)} onClick={() => setTab(t.id)}>{t.label}</button>
//         ))}
//       </div>
//       <SearchBar placeholder="SEARCH PAGES..." />
//       <div style={{ overflowX: "auto" }}>
//         <table style={S.table}>
//           <thead>
//             <tr>
//               {["TITLE","TYPE","CATEGORY","STATUS","VIEWS","DATE","ACTIONS"].map((h) => (
//                 <th key={h} style={S.th}>{h}</th>
//               ))}
//             </tr>
//           </thead>
//           <tbody>
//             {loading ? (
//               <tr><td colSpan={7}><Empty label="LOADING NEURAL CONTENT..." /></td></tr>
//             ) : (pages || []).length === 0 ? (
//               <tr><td colSpan={7}><Empty label="NO PAGES FOUND" /></td></tr>
//             ) : (pages || []).slice(0, 8).map((p) => (
//               <tr key={p.id} style={{ cursor: "pointer" }}
//                 onMouseEnter={(e) => e.currentTarget.style.background = C.bgHover}
//                 onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
//               >
//                 <td style={S.td}>
//                   <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//                     {p.is_featured && <Star size={10} color={C.yellow} />}
//                     {p.is_pinned && <Pin size={10} color={C.pink} />}
//                     <span style={{ color: C.text, fontSize: 12 }}>{p.title}</span>
//                   </div>
//                   <div style={{ fontSize: 10, color: C.textDim, marginTop: 2 }}>{p.slug}</div>
//                 </td>
//                 <td style={S.td}><span style={S.badge(C.purple)}>{p.page_type}</span></td>
//                 <td style={S.td}><span style={{ fontSize: 11, color: C.textDim }}>{p.category?.name || "—"}</span></td>
//                 <td style={S.td}><StatusBadge status={p.status} /></td>
//                 <td style={{ ...S.td, color: C.cyan, fontFamily: "'Orbitron', monospace", fontSize: 11 }}>
//                   {p.view_count?.toLocaleString() ?? 0}
//                 </td>
//                 <td style={{ ...S.td, color: C.textDim, fontSize: 11 }}>
//                   {p.published_date ? new Date(p.published_date).toLocaleDateString() : "—"}
//                 </td>
//                 <td style={S.td}>
//                   <div style={{ display: "flex", gap: 6 }}>
//                     <Eye size={13} color={C.cyan} style={{ cursor: "pointer" }} />
//                     <Edit3 size={13} color={C.purple} style={{ cursor: "pointer" }} />
//                     <Trash2 size={13} color={C.pink} style={{ cursor: "pointer" }} />
//                   </div>
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//       </div>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: BANNERS
// // ═══════════════════════════════════════════════════════════════════
// const BannersSection = () => {
//   const { banners, loading } = useBanners();

//   return (
//     <Section title="BANNER CONTROL" icon={Megaphone} color={C.pink}
//       actions={<button style={S.btn(C.pink, "solid")}><Plus size={12} />NEW BANNER</button>}
//     >
//       <SearchBar placeholder="SEARCH BANNERS..." />
//       <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, padding: 18 }}>
//         {loading ? <Empty label="LOADING..." /> :
//           (banners || []).slice(0, 4).map((b) => (
//             <div key={b.id} style={{
//               ...S.card(C.pink),
//               padding: 14, cursor: "pointer",
//             }}>
//               {/* Banner preview area */}
//               <div style={{
//                 height: 80, borderRadius: 2, marginBottom: 12,
//                 background: `linear-gradient(135deg, ${C.pink}15, ${C.purple}15)`,
//                 border: `1px solid ${C.pink}20`,
//                 display: "flex", alignItems: "center", justifyContent: "center",
//               }}>
//                 <Megaphone size={24} color={`${C.pink}60`} />
//               </div>
//               <div style={{ fontSize: 12, marginBottom: 6 }}>{b.name || b.title}</div>
//               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
//                 <StatusBadge status={b.is_active ? "active" : "inactive"} />
//                 <div style={{ fontSize: 10, color: C.textDim }}>
//                   CTR: <span style={{ color: C.cyan }}>{b.click_through_rate?.toFixed(2) ?? 0}%</span>
//                 </div>
//               </div>
//               <div style={{ display: "flex", gap: 12, marginTop: 10, fontSize: 10, color: C.textDim }}>
//                 <span><Eye size={9} style={{ display: "inline", marginRight: 3 }} />{b.impression_count?.toLocaleString() ?? 0}</span>
//                 <span><Link2 size={9} style={{ display: "inline", marginRight: 3 }} />{b.click_count?.toLocaleString() ?? 0}</span>
//               </div>
//             </div>
//           ))
//         }
//         {(!loading && (!banners || banners.length === 0)) && <Empty label="NO BANNERS DEPLOYED" />}
//       </div>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: FAQ
// // ═══════════════════════════════════════════════════════════════════
// const FAQSection = () => {
//   const { faqs, loading, search } = useFAQs();
//   const [q, setQ] = useState("");

//   return (
//     <Section title="FAQ MATRIX" icon={HelpCircle} color={C.yellow}
//       actions={<button style={S.btn(C.yellow, "solid")}><Plus size={12} />ADD FAQ</button>}
//     >
//       <div style={{ display: "flex", gap: 8, padding: "12px 18px", borderBottom: `1px solid ${C.border}` }}>
//         <div style={{ position: "relative", flex: 1 }}>
//           <Search size={12} color={C.textDim} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)" }} />
//           <input
//             style={{ ...S.input, width: "100%", paddingLeft: 30, boxSizing: "border-box" }}
//             placeholder="SEARCH KNOWLEDGE BASE..."
//             value={q}
//             onChange={(e) => setQ(e.target.value)}
//             onKeyDown={(e) => e.key === "Enter" && search(q)}
//           />
//         </div>
//         <button style={S.btn(C.yellow)} onClick={() => search(q)}>SEARCH</button>
//       </div>
//       <div>
//         {loading ? <Empty label="SCANNING DATABASE..." /> :
//           (faqs || []).slice(0, 8).map((f, i) => (
//             <div key={f.id} style={{
//               padding: "14px 18px",
//               borderBottom: `1px solid ${C.border}`,
//               cursor: "pointer",
//               transition: "background 0.2s",
//             }}
//               onMouseEnter={(e) => e.currentTarget.style.background = C.bgHover}
//               onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
//             >
//               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
//                 <div style={{ flex: 1 }}>
//                   <div style={{ fontSize: 12, marginBottom: 4, color: C.text }}>
//                     <span style={{ color: C.yellow, marginRight: 8, fontFamily: "'Orbitron', monospace", fontSize: 10 }}>
//                       #{String(i + 1).padStart(3, "0")}
//                     </span>
//                     {f.question}
//                   </div>
//                   {f.short_answer && (
//                     <div style={{ fontSize: 11, color: C.textDim, lineHeight: 1.5 }}>
//                       {f.short_answer.slice(0, 100)}...
//                     </div>
//                   )}
//                 </div>
//                 <div style={{ display: "flex", gap: 6, marginLeft: 12 }}>
//                   {f.is_featured && <Star size={11} color={C.yellow} />}
//                   <StatusBadge status={f.is_active ? "active" : "inactive"} />
//                 </div>
//               </div>
//               <div style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 10, color: C.textDim }}>
//                 <span style={{ color: C.cyan }}>{f.category?.name || "Uncategorized"}</span>
//                 <span>👁 {f.view_count ?? 0}</span>
//                 <span style={{ color: C.green }}>✓ {f.helpful_count ?? 0}</span>
//                 <span style={{ color: C.pink }}>✗ {f.not_helpful_count ?? 0}</span>
//               </div>
//             </div>
//           ))
//         }
//       </div>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: COMMENTS
// // ═══════════════════════════════════════════════════════════════════
// const CommentsSection = () => {
//   const { comments, loading, approve, flag, fetchPending } = useComments();

//   return (
//     <Section title="COMMENT MODERATION" icon={MessageSquare} color={C.green}
//       actions={
//         <button style={S.btn(C.yellow)} onClick={fetchPending}>
//           <AlertCircle size={12} />PENDING
//         </button>
//       }
//     >
//       <SearchBar placeholder="SEARCH COMMENTS..." />
//       <table style={S.table}>
//         <thead>
//           <tr>
//             {["USER","COMMENT","RATING","STATUS","DATE","ACTIONS"].map((h) => (
//               <th key={h} style={S.th}>{h}</th>
//             ))}
//           </tr>
//         </thead>
//         <tbody>
//           {loading ? (
//             <tr><td colSpan={6}><Empty label="LOADING TRANSMISSIONS..." /></td></tr>
//           ) : (comments || []).length === 0 ? (
//             <tr><td colSpan={6}><Empty label="NO COMMENTS" /></td></tr>
//           ) : (comments || []).slice(0, 8).map((c) => (
//             <tr key={c.id}
//               onMouseEnter={(e) => e.currentTarget.style.background = C.bgHover}
//               onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
//             >
//               <td style={S.td}>
//                 <div style={{ fontSize: 12, color: C.cyan }}>{c.user?.username || "Anonymous"}</div>
//               </td>
//               <td style={{ ...S.td, maxWidth: 280 }}>
//                 <div style={{ fontSize: 11, color: C.text, lineHeight: 1.4 }}>
//                   {(c.comment || "").slice(0, 80)}{c.comment?.length > 80 ? "..." : ""}
//                 </div>
//                 {c.is_flagged && <span style={{ ...S.badge(C.pink), marginTop: 4 }}>FLAGGED</span>}
//               </td>
//               <td style={S.td}>
//                 {c.rating ? (
//                   <span style={{ color: C.yellow }}>{"★".repeat(c.rating)}{"☆".repeat(5 - c.rating)}</span>
//                 ) : "—"}
//               </td>
//               <td style={S.td}>
//                 <StatusBadge status={c.is_approved ? "approved" : "pending"} />
//               </td>
//               <td style={{ ...S.td, fontSize: 11, color: C.textDim }}>
//                 {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
//               </td>
//               <td style={S.td}>
//                 <div style={{ display: "flex", gap: 6 }}>
//                   {!c.is_approved && (
//                     <button style={S.btn(C.green)} onClick={() => approve(c.id)}>
//                       <CheckCircle size={11} />OK
//                     </button>
//                   )}
//                   <button style={S.btn(C.pink)} onClick={() => flag(c.id, "spam")}>
//                     <XCircle size={11} />FLAG
//                   </button>
//                 </div>
//               </td>
//             </tr>
//           ))}
//         </tbody>
//       </table>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: FILES
// // ═══════════════════════════════════════════════════════════════════
// const FilesSection = () => {
//   const { files, loading, download } = useFiles();

//   const FILE_ICONS = {
//     pdf: { icon: BookOpen, color: C.pink },
//     document: { icon: FileText, color: C.cyan },
//     image: { icon: Image, color: C.purple },
//     video: { icon: Film, color: C.orange },
//     archive: { icon: Database, color: C.yellow },
//     spreadsheet: { icon: Layers, color: C.green },
//   };

//   return (
//     <Section title="FILE REPOSITORY" icon={Database} color={C.cyan}
//       actions={
//         <button style={S.btn(C.cyan, "solid")}><Upload size={12} />UPLOAD</button>
//       }
//     >
//       <SearchBar placeholder="SEARCH FILES..." />
//       <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, padding: 18 }}>
//         {loading ? <Empty label="SCANNING STORAGE..." /> :
//           (files || []).slice(0, 9).map((f) => {
//             const cfg = FILE_ICONS[f.file_type] || { icon: FileText, color: C.textDim };
//             return (
//               <div key={f.id} style={{
//                 ...S.card(cfg.color), padding: 12, cursor: "pointer",
//                 display: "flex", flexDirection: "column", gap: 8,
//               }}>
//                 <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//                   <cfg.icon size={16} color={cfg.color} />
//                   <span style={{ ...S.badge(cfg.color) }}>{f.file_type}</span>
//                 </div>
//                 <div style={{ fontSize: 11, color: C.text }}>{f.name}</div>
//                 <div style={{ fontSize: 10, color: C.textDim }}>
//                   {f.file_size_human || `${f.file_size} B`}
//                 </div>
//                 <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
//                   <button style={S.btn(cfg.color)} onClick={() => download(f.id)}>
//                     <Download size={10} />DL
//                   </button>
//                   <button style={S.btn(C.pink)}><Trash2 size={10} /></button>
//                 </div>
//               </div>
//             );
//           })
//         }
//         {(!loading && (!files || files.length === 0)) && <Empty label="NO FILES STORED" />}
//       </div>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: ANALYTICS
// // ═══════════════════════════════════════════════════════════════════
// const AnalyticsSection = () => {
//   const { today, fetchRange } = useSiteAnalytics();

//   const metrics = today ? [
//     { label: "Page Views",         value: today.page_views,         color: C.cyan   },
//     { label: "Unique Visitors",    value: today.unique_visitors,    color: C.purple },
//     { label: "New Users",          value: today.new_users,          color: C.green  },
//     { label: "Session Count",      value: today.session_count,      color: C.orange },
//     { label: "Bounce Rate",        value: `${today.bounce_rate?.toFixed(1)}%`, color: C.yellow },
//     { label: "Avg Session",        value: `${today.avg_session_duration?.toFixed(0)}s`, color: C.pink },
//     { label: "Total Earnings",     value: `$${today.total_earnings ?? 0}`, color: C.green },
//     { label: "Total Withdrawals",  value: `$${today.total_withdrawals ?? 0}`, color: C.pink },
//   ] : [];

//   return (
//     <Section title="ANALYTICS NEXUS" icon={BarChart3} color={C.orange}>
//       <div style={{ padding: "14px 18px 0", display: "flex", gap: 8 }}>
//         <button style={S.btn(C.orange, "solid")}>TODAY</button>
//         <button style={S.btn(C.orange)}>7D</button>
//         <button style={S.btn(C.orange)}>30D</button>
//         <button style={S.btn(C.orange)}>CUSTOM</button>
//       </div>
//       <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, padding: 18 }}>
//         {metrics.map((m) => (
//           <div key={m.label} style={{ ...S.card(m.color), padding: "12px 14px" }}>
//             <div style={{ fontSize: 18, fontFamily: "'Orbitron', monospace", color: m.color }}>{m.value ?? 0}</div>
//             <div style={S.statLabel}>{m.label}</div>
//           </div>
//         ))}
//         {!today && <Empty label="AWAITING TELEMETRY DATA" />}
//       </div>
//       {/* Mini bar viz */}
//       <div style={{ padding: "0 18px 18px" }}>
//         <div style={{ ...S.card(C.orange), padding: 14 }}>
//           <div style={{ fontSize: 10, color: C.textDim, letterSpacing: 2, marginBottom: 12 }}>
//             ENGAGEMENT DISTRIBUTION
//           </div>
//           {[
//             { label: "Content Views",  val: today?.content_views ?? 0,    color: C.cyan,   max: 1000 },
//             { label: "Content Shares", val: today?.content_shares ?? 0,   color: C.purple, max: 500  },
//             { label: "Banner Clicks",  val: today?.banner_clicks ?? 0,    color: C.pink,   max: 300  },
//             { label: "Comments",       val: today?.content_comments ?? 0, color: C.green,  max: 200  },
//           ].map((bar) => (
//             <div key={bar.label} style={{ marginBottom: 10 }}>
//               <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, marginBottom: 4 }}>
//                 <span style={{ color: C.textDim }}>{bar.label}</span>
//                 <span style={{ color: bar.color, fontFamily: "'Orbitron', monospace" }}>{bar.val}</span>
//               </div>
//               <div style={{ height: 3, background: `${bar.color}15`, borderRadius: 2 }}>
//                 <div style={{
//                   height: "100%", borderRadius: 2,
//                   width: `${Math.min(100, (bar.val / bar.max) * 100)}%`,
//                   background: `linear-gradient(90deg, ${bar.color}, ${bar.color}80)`,
//                   boxShadow: `0 0 6px ${bar.color}`,
//                   transition: "width 0.6s ease",
//                 }} />
//               </div>
//             </div>
//           ))}
//         </div>
//       </div>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  SECTION: CATEGORIES
// // ═══════════════════════════════════════════════════════════════════
// const CategoriesSection = () => {
//   const { categories, loading } = useContentCategories();

//   return (
//     <Section title="CONTENT TAXONOMY" icon={FolderOpen} color={C.purple}
//       actions={<button style={S.btn(C.purple, "solid")}><Plus size={12} />NEW CATEGORY</button>}
//     >
//       <SearchBar placeholder="SEARCH CATEGORIES..." />
//       <table style={S.table}>
//         <thead>
//           <tr>
//             {["NAME","TYPE","CONTENT","VIEWS","MENU","APP","ACTIONS"].map((h) => (
//               <th key={h} style={S.th}>{h}</th>
//             ))}
//           </tr>
//         </thead>
//         <tbody>
//           {loading ? (
//             <tr><td colSpan={7}><Empty label="LOADING TAXONOMY..." /></td></tr>
//           ) : (categories || []).slice(0, 8).map((cat) => (
//             <tr key={cat.id}
//               onMouseEnter={(e) => e.currentTarget.style.background = C.bgHover}
//               onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
//             >
//               <td style={S.td}>
//                 <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
//                   {cat.icon && <Hash size={11} color={C.purple} />}
//                   <span>{cat.name}</span>
//                 </div>
//                 <div style={{ fontSize: 10, color: C.textDim }}>{cat.slug}</div>
//               </td>
//               <td style={S.td}><span style={S.badge(C.purple)}>{cat.category_type}</span></td>
//               <td style={{ ...S.td, color: C.cyan, fontFamily: "'Orbitron', monospace", fontSize: 11 }}>{cat.total_content ?? 0}</td>
//               <td style={{ ...S.td, color: C.textDim, fontSize: 11 }}>{cat.total_views?.toLocaleString() ?? 0}</td>
//               <td style={S.td}><PulseDot color={cat.show_in_menu ? C.green : C.textDim} /></td>
//               <td style={S.td}><PulseDot color={cat.show_in_app ? C.green : C.textDim} /></td>
//               <td style={S.td}>
//                 <div style={{ display: "flex", gap: 6 }}>
//                   <Edit3 size={13} color={C.purple} style={{ cursor: "pointer" }} />
//                   <Trash2 size={13} color={C.pink} style={{ cursor: "pointer" }} />
//                 </div>
//               </td>
//             </tr>
//           ))}
//         </tbody>
//       </table>
//     </Section>
//   );
// };

// // ═══════════════════════════════════════════════════════════════════
// //  MAIN CMS PAGE
// // ═══════════════════════════════════════════════════════════════════
// export default function CMSPage() {
//   const [active, setActive] = useState("overview");

//   // Inject fonts + keyframes
//   useEffect(() => {
//     if (!document.getElementById("cms-fonts")) {
//       const link = document.createElement("link");
//       link.id = "cms-fonts";
//       link.rel = "stylesheet";
//       link.href = "https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700&display=swap";
//       document.head.appendChild(link);
//     }
//     if (!document.getElementById("cms-keyframes")) {
//       const style = document.createElement("style");
//       style.id = "cms-keyframes";
//       style.textContent = `
//         @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.3;} }
//         @keyframes scanline {
//           0% { transform: translateY(-100%); }
//           100% { transform: translateY(100vh); }
//         }
//         @keyframes flicker { 0%,100%{opacity:1} 92%{opacity:.9} 94%{opacity:1} 96%{opacity:.85} 98%{opacity:1} }
//         * { scrollbar-width: thin; scrollbar-color: #00f5ff20 transparent; }
//         *::-webkit-scrollbar { width: 4px; }
//         *::-webkit-scrollbar-track { background: transparent; }
//         *::-webkit-scrollbar-thumb { background: #00f5ff30; border-radius: 2px; }
//         tr:hover td { transition: background 0.15s; }
//       `;
//       document.head.appendChild(style);
//     }
//   }, []);

//   const SECTION_MAP = {
//     overview:    <OverviewSection />,
//     pages:       <PagesSection />,
//     categories:  <CategoriesSection />,
//     banners:     <BannersSection />,
//     faq:         <FAQSection />,
//     gallery:     <div><Section title="IMAGE GALLERY" icon={Image} color={C.purple}><Empty label="GALLERY MODULE — SELECT FROM NAV" /></Section></div>,
//     files:       <FilesSection />,
//     comments:    <CommentsSection />,
//     analytics:   <AnalyticsSection />,
//     permissions: <div><Section title="PERMISSION MATRIX" icon={Shield} color={C.pink}><Empty label="PERMISSION ENGINE — COMING ONLINE" /></Section></div>,
//     settings:    <div><Section title="SYSTEM SETTINGS" icon={Settings} color={C.textDim}><Empty label="SETTINGS NODE — INITIALIZING" /></Section></div>,
//   };

//   return (
//     <div style={S.page}>
//       {/* Background layers */}
//       <div style={S.grid} />
//       <div style={S.blob(C.cyan,   "-10%", "-5%",  600)} />
//       <div style={S.blob(C.purple, "60%",  "70%",  500)} />
//       <div style={S.blob(C.pink,   "30%",  "-8%",  300)} />

//       {/* Scanline effect */}
//       <div style={{
//         position: "fixed", top: 0, left: 0, right: 0, height: 2, zIndex: 1000,
//         background: `linear-gradient(transparent, ${C.cyan}08, transparent)`,
//         animation: "scanline 8s linear infinite", pointerEvents: "none",
//       }} />

//       {/* Layout */}
//       <div style={{ display: "flex", position: "relative", zIndex: 1 }}>

//         {/* ─── Sidebar ─── */}
//         <aside style={S.sidebar}>
//           {/* Logo */}
//           <div style={S.logo}>
//             <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
//               <div style={{
//                 width: 28, height: 28, background: `linear-gradient(135deg, ${C.cyan}, ${C.purple})`,
//                 borderRadius: 2, display: "flex", alignItems: "center", justifyContent: "center",
//               }}>
//                 <Layers size={14} color="#000" />
//               </div>
//               <div>
//                 <div style={S.logoText}>CMS NEXUS</div>
//                 <div style={S.logoSub}>HOLOGRAPHIC CONTROL</div>
//               </div>
//             </div>
//             <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
//               <PulseDot color={C.green} />
//               <span style={{ fontSize: 10, color: C.textDim }}>ALL SYSTEMS NOMINAL</span>
//             </div>
//           </div>

//           {/* Nav */}
//           <nav style={S.navSection}>
//             {NAV.map((item) => {
//               if (item.id.startsWith("divider")) {
//                 return <div key={item.id} style={S.navLabel}>{item.label}</div>;
//               }
//               const Icon = item.icon;
//               const isActive = active === item.id;
//               return (
//                 <div
//                   key={item.id}
//                   style={S.navItem(isActive, item.color)}
//                   onClick={() => setActive(item.id)}
//                   onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.color = item.color; }}
//                   onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.color = C.textDim; }}
//                 >
//                   <Icon size={13} />
//                   <span>{item.label}</span>
//                   {isActive && <ChevronRight size={10} style={{ marginLeft: "auto" }} />}
//                 </div>
//               );
//             })}
//           </nav>

//           {/* Sidebar footer */}
//           <div style={{
//             padding: "12px 20px",
//             borderTop: `1px solid ${C.border}`,
//             fontSize: 10, color: C.textDim,
//           }}>
//             <div style={{ marginBottom: 4 }}>v2.4.1 // CYBERPUNK BUILD</div>
//             <div style={{ color: C.cyan }}>◈ NEURAL LINK ACTIVE</div>
//           </div>
//         </aside>

//         {/* ─── Main Content ─── */}
//         <main style={{ flex: 1, padding: "24px 28px", overflowY: "auto", minHeight: "100vh" }}>
//           {/* Top bar */}
//           <div style={{
//             display: "flex", alignItems: "center", justifyContent: "space-between",
//             marginBottom: 20,
//           }}>
//             <div>
//               <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 4, textTransform: "uppercase", marginBottom: 2 }}>
//                 CONTROL CENTER //
//               </div>
//               <div style={{
//                 fontSize: 20, fontFamily: "'Orbitron', monospace",
//                 color: C.cyan, letterSpacing: 2, textTransform: "uppercase",
//                 textShadow: `0 0 20px ${C.cyan}60`,
//               }}>
//                 {NAV.find((n) => n.id === active)?.label || "OVERVIEW"}
//               </div>
//             </div>
//             <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
//               <button style={S.btn(C.cyan)}>
//                 <RefreshCw size={12} />SYNC
//               </button>
//               <button style={S.btn(C.purple, "solid")}>
//                 <Bell size={12} />
//                 <span style={{
//                   width: 14, height: 14, borderRadius: "50%",
//                   background: C.pink, color: "#fff",
//                   fontSize: 8, display: "inline-flex",
//                   alignItems: "center", justifyContent: "center",
//                 }}>3</span>
//               </button>
//             </div>
//           </div>

//           {/* Breadcrumb */}
//           <div style={{ fontSize: 10, color: C.textDim, marginBottom: 20, letterSpacing: 1 }}>
//             <span style={{ color: C.cyan }}>◈ NEXUS</span>
//             <ChevronRight size={10} style={{ display: "inline", margin: "0 4px" }} />
//             <span>CMS</span>
//             <ChevronRight size={10} style={{ display: "inline", margin: "0 4px" }} />
//             <span style={{ color: C.text }}>{NAV.find((n) => n.id === active)?.label || "OVERVIEW"}</span>
//           </div>

//           {/* Active section */}
//           <div style={{ animation: "flicker 0.1s ease" }}>
//             {SECTION_MAP[active] || <Empty label={`MODULE ${active.toUpperCase()} — LOADING`} />}
//           </div>
//         </main>
//       </div>
//     </div>
//   );
// }