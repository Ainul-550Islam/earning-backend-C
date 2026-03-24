import { useState, useEffect, useRef, useCallback } from "react";
import client from "../api/client";
import {
  Activity, CheckCircle, XCircle, RefreshCw, Plus, Edit3, Trash2,
  Eye, RotateCcw, Copy, ChevronRight, Globe, Clock, Search,
  ToggleLeft, ToggleRight, X, Save, Terminal, Wifi, WifiOff,
  BarChart3, Key, AlertCircle, AlertTriangle, Shield
} from "lucide-react";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

const C = {
  cyan:"#00f5ff",purple:"#b400ff",pink:"#ff003c",green:"#00ff88",
  yellow:"#ffe600",orange:"#ff7b00",blue:"#0066ff",teal:"#00ffcc",
  bg:"#03060f",bgCard:"rgba(6,14,30,0.92)",border:"rgba(0,245,255,0.15)",
  text:"#cce8f4",textDim:"#3d6070",
};

const CSS=`
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&family=Exo+2:wght@300;400;600&display=swap');
@keyframes pb-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@keyframes pb-pulse{0%,100%{opacity:1;box-shadow:0 0 8px currentColor}50%{opacity:.4;box-shadow:0 0 2px currentColor}}
@keyframes pb-scan{0%{transform:translateY(-100vh)}100%{transform:translateY(100vh)}}
@keyframes pb-slide{from{transform:translateX(30px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes pb-pop{0%{transform:scale(.85);opacity:0}100%{transform:scale(1);opacity:1}}
*{scrollbar-width:thin;scrollbar-color:#00f5ff18 transparent}
*::-webkit-scrollbar{width:3px}
*::-webkit-scrollbar-thumb{background:linear-gradient(#00f5ff40,#bf00ff40);border-radius:2px}
.pb3d{transform-style:preserve-3d;transition:transform .4s cubic-bezier(.175,.885,.32,1.275),box-shadow .4s}
.pb3d:hover{transform:perspective(600px) rotateX(-4deg) rotateY(4deg) translateY(-5px) scale(1.02)}
.pb-row:hover td{background:rgba(0,245,255,0.04)!important}
.pb-btn{transition:all .2s cubic-bezier(.175,.885,.32,1.275)!important}
.pb-btn:hover{transform:scale(1.05) translateY(-1px)!important}
`;

const extractList=d=>Array.isArray(d)?d:(d?.results||d?.data||[]);

const STATUS_CFG={
  rewarded:{color:C.green,icon:CheckCircle},rejected:{color:C.pink,icon:XCircle},
  duplicate:{color:C.orange,icon:Copy},failed:{color:C.pink,icon:AlertTriangle},
  received:{color:C.cyan,icon:Activity},processing:{color:C.yellow,icon:RefreshCw},
  validated:{color:C.teal,icon:Shield},pending_review:{color:C.yellow,icon:Clock},
};

const StatusPill=({s})=>{
  const cfg=STATUS_CFG[s]||{color:C.textDim,icon:Activity};
  const Icon=cfg.icon;
  return <span style={{display:"inline-flex",alignItems:"center",gap:5,padding:"3px 10px",borderRadius:20,background:`${cfg.color}15`,border:`1px solid ${cfg.color}50`,color:cfg.color,fontSize:10,letterSpacing:1,textTransform:"uppercase",fontFamily:"'Exo 2',sans-serif",fontWeight:600}}><Icon size={9}/>{s}</span>;
};

const PulseDot=({color=C.green,size=7})=><span style={{display:"inline-block",width:size,height:size,borderRadius:"50%",background:color,boxShadow:`0 0 8px ${color}`,animation:"pb-pulse 2s infinite"}}/>;

const Toast=({t})=>{
  if(!t) return null;
  const cols={success:C.green,error:C.pink,info:C.cyan,warning:C.yellow};
  const c=cols[t.type]||C.cyan;
  return <div style={{position:"fixed",bottom:28,right:28,zIndex:9999,animation:"pb-slide .35s ease",background:"linear-gradient(135deg,rgba(5,12,24,.98),rgba(10,24,48,.98))",border:`1px solid ${c}60`,borderRadius:8,padding:"14px 22px",boxShadow:`0 0 30px ${c}30,0 8px 32px rgba(0,0,0,.6)`,display:"flex",alignItems:"center",gap:10,fontFamily:"'Exo 2',sans-serif"}}>
    <span style={{fontSize:13,color:c,fontWeight:600}}>{t.type==="success"?"✓":t.type==="error"?"✗":"ℹ"} {t.message}</span>
  </div>;
};

const Confirm=({open,label,onConfirm,onCancel})=>{
  if(!open) return null;
  return <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.88)",backdropFilter:"blur(6px)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center"}} onClick={onCancel}>
    <div style={{background:"linear-gradient(135deg,rgba(6,14,30,.99),rgba(12,6,24,.99))",border:`1px solid ${C.pink}50`,borderRadius:12,padding:28,maxWidth:420,width:"90%",boxShadow:`0 0 60px ${C.pink}20`,animation:"pb-pop .3s ease"}} onClick={e=>e.stopPropagation()}>
      <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:16}}><span style={{fontSize:22}}>⚠️</span><span style={{fontFamily:"'Orbitron',monospace",fontSize:13,color:C.pink,letterSpacing:2}}>CONFIRM DELETE</span></div>
      <p style={{fontSize:13,color:C.text,marginBottom:24,fontFamily:"'Exo 2',sans-serif",lineHeight:1.6}}>Delete <strong style={{color:C.pink}}>"{label}"</strong>? This cannot be undone.</p>
      <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
        <button className="pb-btn" style={B(C.textDim)} onClick={onCancel}>CANCEL</button>
        <button className="pb-btn" style={B(C.pink,true)} onClick={onConfirm}><Trash2 size={12}/>DELETE</button>
      </div>
    </div>
  </div>;
};

const B=(c,solid=false)=>({display:"inline-flex",alignItems:"center",gap:6,padding:"8px 16px",borderRadius:6,cursor:"pointer",fontSize:11,letterSpacing:1.5,fontFamily:"'Orbitron',monospace",fontWeight:600,border:"none",textTransform:"uppercase",transition:"all .2s",background:solid?`linear-gradient(135deg,${c}30,${c}15)`:"transparent",border:`1px solid ${c}${solid?"90":"40"}`,color:c,boxShadow:solid?`0 0 12px ${c}20`:"none"});

const iS={background:"rgba(0,245,255,0.04)",border:`1px solid ${C.border}`,borderRadius:6,color:C.text,fontSize:12,padding:"9px 14px",outline:"none",fontFamily:"'Exo 2',sans-serif",width:"100%",boxSizing:"border-box"};
const lS={fontSize:9,letterSpacing:2.5,color:C.textDim,textTransform:"uppercase",display:"block",marginBottom:6,marginTop:16,fontFamily:"'Orbitron',monospace"};

const CrudModal=({open,title,color=C.cyan,onClose,onSave,saving,children})=>{
  if(!open) return null;
  return <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.9)",backdropFilter:"blur(8px)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center"}} onClick={onClose}>
    <div style={{background:"linear-gradient(160deg,rgba(6,14,30,.99) 0%,rgba(10,6,28,.99) 100%)",border:`1px solid ${color}40`,borderRadius:14,width:"94%",maxWidth:620,maxHeight:"88vh",overflow:"auto",boxShadow:`0 0 60px ${color}20,0 30px 60px rgba(0,0,0,.8)`,padding:"28px 28px 20px",animation:"pb-pop .3s ease"}} onClick={e=>e.stopPropagation()}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:24}}>
        <div style={{fontFamily:"'Orbitron',monospace",fontSize:13,letterSpacing:3,color,textTransform:"uppercase"}}>{title}</div>
        <button style={{background:"none",border:"none",color:C.textDim,cursor:"pointer"}} onClick={onClose}><X size={18}/></button>
      </div>
      {children}
      <div style={{display:"flex",gap:10,justifyContent:"flex-end",marginTop:28,paddingTop:16,borderTop:`1px solid ${C.border}`}}>
        <button className="pb-btn" style={B(C.textDim)} onClick={onClose}>CANCEL</button>
        <button className="pb-btn" style={B(color,true)} onClick={onSave} disabled={saving}><Save size={12}/>{saving?"SAVING...":"SAVE CONFIG"}</button>
      </div>
    </div>
  </div>;
};

const LogModal=({log,onClose,onRetry})=>{
  if(!log) return null;
  const cfg=STATUS_CFG[log.status]||{color:C.cyan};
  return <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.9)",backdropFilter:"blur(8px)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center"}} onClick={onClose}>
    <div style={{background:"linear-gradient(160deg,rgba(6,14,30,.99),rgba(10,6,28,.99))",border:`1px solid ${cfg.color}40`,borderRadius:14,width:"94%",maxWidth:680,maxHeight:"88vh",overflow:"auto",boxShadow:`0 0 60px ${cfg.color}20`,padding:28,animation:"pb-pop .3s ease"}} onClick={e=>e.stopPropagation()}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:22}}>
        <div style={{fontFamily:"'Orbitron',monospace",fontSize:13,letterSpacing:3,color:cfg.color}}>POSTBACK LOG DETAIL</div>
        <button style={{background:"none",border:"none",color:C.textDim,cursor:"pointer"}} onClick={onClose}><X size={18}/></button>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10,marginBottom:18}}>
        {[["Status",<StatusPill s={log.status}/>],["Network",log.network_name||"—"],["Lead ID",log.lead_id||"—"],["Offer ID",log.offer_id||"—"],["Points",`${log.points_awarded||0} pts`],["Source IP",log.source_ip||"—"],["Received",log.received_at?new Date(log.received_at).toLocaleString():"—"],["Retry Count",log.retry_count||0]].map(([k,v],i)=>(
          <div key={i} style={{background:"rgba(0,245,255,0.04)",border:`1px solid ${C.border}`,borderRadius:8,padding:"10px 14px"}}>
            <div style={{fontSize:9,color:C.textDim,letterSpacing:2,marginBottom:5,fontFamily:"'Orbitron',monospace"}}>{k}</div>
            <div style={{fontSize:12,color:C.text,fontFamily:"'Exo 2',sans-serif"}}>{v}</div>
          </div>
        ))}
      </div>
      {log.rejection_reason&&<div style={{background:"rgba(255,0,60,.08)",border:`1px solid ${C.pink}30`,borderRadius:8,padding:"12px 16px",marginBottom:14}}>
        <div style={{fontSize:9,color:C.pink,letterSpacing:2,marginBottom:6,fontFamily:"'Orbitron',monospace"}}>REJECTION REASON</div>
        <div style={{fontSize:12,color:C.text,fontFamily:"'Exo 2',sans-serif"}}>{log.rejection_reason}</div>
      </div>}
      {log.raw_payload&&<div style={{background:"rgba(180,0,255,.06)",border:`1px solid ${C.purple}25`,borderRadius:8,padding:"12px 16px",marginBottom:18}}>
        <div style={{fontSize:9,color:C.purple,letterSpacing:2,marginBottom:8,fontFamily:"'Orbitron',monospace"}}>RAW PAYLOAD</div>
        <pre style={{fontSize:10,color:C.textDim,overflowX:"auto",margin:0,maxHeight:100}}>{JSON.stringify(log.raw_payload,null,2)}</pre>
      </div>}
      <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
        {(log.status==="failed"||log.status==="rejected")&&<button className="pb-btn" style={B(C.yellow,true)} onClick={()=>onRetry(log.id)}><RotateCcw size={12}/>RETRY</button>}
        <button className="pb-btn" style={B(C.textDim)} onClick={onClose}>CLOSE</button>
      </div>
    </div>
  </div>;
};

export default function PostbackPage(){
  const[tab,setTab]=useState("dashboard");
  const[networks,setNetworks]=useState([]);
  const[logs,setLogs]=useState([]);
  const[duplicates,setDuplicates]=useState([]);
  const[dashboard,setDashboard]=useState(null);
  const[loading,setLoading]=useState(true);
  const[toast,setToast]=useState(null);
  const[netModal,setNetModal]=useState(null);
  const[logDetail,setLogDetail]=useState(null);
  const[confirmDel,setConfirmDel]=useState(null);
  const[saving,setSaving]=useState(false);
  const[logFilter,setLogFilter]=useState("all");
  const[logSearch,setLogSearch]=useState("");
  const timerRef=useRef(null);
  const defForm={name:"",network_key:"",network_type:"cpa",status:"active",secret_key:"",signature_algorithm:"hmac_sha256",default_reward_points:10,rate_limit_per_minute:60,dedup_window:"1d",require_nonce:false,contact_email:"",notes:"",ip_whitelist:[],field_mapping:{},required_fields:[],reward_rules:{}};
  const[form,setForm]=useState(defForm);

  const showToast=useCallback((msg,type="success")=>{setToast({message:msg,type});clearTimeout(timerRef.current);timerRef.current=setTimeout(()=>setToast(null),3500);},[]);

  const fetchAll=useCallback(async()=>{
    setLoading(true);
    try{
      const[nR,lR,dR,dashR]=await Promise.allSettled([
        client.get("postback/networks/",{params:{page_size:50}}),
        client.get("postback/logs/",{params:{page_size:50}}),
        client.get("postback/duplicates/",{params:{page_size:50}}),
        client.get("postback/admin/dashboard/"),
      ]);
      if(nR.status==="fulfilled")setNetworks(extractList(nR.value.data));
      if(lR.status==="fulfilled")setLogs(extractList(lR.value.data));
      if(dR.status==="fulfilled")setDuplicates(extractList(dR.value.data));
      if(dashR.status==="fulfilled")setDashboard(dashR.value.data);
    }catch{}finally{setLoading(false);}
  },[]);

  useEffect(()=>{fetchAll();if(!document.getElementById("pb-css")){const s=document.createElement("style");s.id="pb-css";s.textContent=CSS;document.head.appendChild(s);}},[]);

  const openCreate=()=>{setForm(defForm);setNetModal({mode:"create"});};
  const openEdit=n=>{setForm({name:n.name||"",network_key:n.network_key||"",network_type:n.network_type||"cpa",status:n.status||"active",secret_key:n.secret_key||"",signature_algorithm:n.signature_algorithm||"hmac_sha256",default_reward_points:n.default_reward_points||10,rate_limit_per_minute:n.rate_limit_per_minute||60,dedup_window:n.dedup_window||"1d",require_nonce:!!n.require_nonce,contact_email:n.contact_email||"",notes:n.notes||"",ip_whitelist:n.ip_whitelist||[],field_mapping:n.field_mapping||{},required_fields:n.required_fields||[],reward_rules:n.reward_rules||{}});setNetModal({mode:"edit",data:n});};

  const handleSave=async()=>{
    if(!form.name||!form.network_key){showToast("Name & Key required","error");return;}
    setSaving(true);
    try{
      if(netModal.mode==="create"){const r=await client.post("postback/networks/",form);setNetworks(p=>[r.data,...p]);showToast("Network created!","success");}
      else{const r=await client.patch(`postback/networks/${netModal.data.id}/`,form);setNetworks(p=>p.map(n=>n.id===netModal.data.id?r.data:n));showToast("Updated!","success");}
      setNetModal(null);
    }catch(e){showToast(e?.response?.data?.detail||"Save failed","error");}
    finally{setSaving(false);}
  };

  const handleDelete=async()=>{
    try{await client.delete(`postback/networks/${confirmDel.id}/`);setNetworks(p=>p.filter(n=>n.id!==confirmDel.id));showToast("Deleted","success");}
    catch{showToast("Delete failed","error");}
    setConfirmDel(null);
  };

  const handleToggle=async n=>{
    try{await client.post(`postback/networks/${n.id}/${n.status==="active"?"deactivate":"activate"}/`);setNetworks(p=>p.map(x=>x.id===n.id?{...x,status:n.status==="active"?"inactive":"active"}:x));showToast(`${n.status==="active"?"Deactivated":"Activated"}!`,"success");}
    catch{showToast("Toggle failed","error");}
  };

  const handleRetry=async id=>{
    try{await client.post(`postback/logs/${id}/retry/`);showToast("Retry queued!","success");setLogDetail(null);fetchAll();}
    catch(e){showToast(e?.response?.data?.detail||"Retry failed","error");}
  };

  const viewLog=async log=>{
    try{const r=await client.get(`postback/logs/${log.id}/`);setLogDetail(r.data);}
    catch{setLogDetail(log);}
  };

  const filteredLogs=logs.filter(l=>{
    const ms=logFilter==="all"||l.status===logFilter;
    const mq=!logSearch||l.lead_id?.includes(logSearch)||l.offer_id?.includes(logSearch)||(l.network_name||"").toLowerCase().includes(logSearch.toLowerCase());
    return ms&&mq;
  });

  const dash=dashboard?.summary||{};
  const activeNets=networks.filter(n=>n.status==="active").length;

  // ─── 3D Stat Card ───────────────────────────────────────────────
  const SC=({label,value,color,Icon,accent})=>(
    <div className="pb3d" style={{background:`linear-gradient(145deg,rgba(6,14,30,.97),rgba(${accent},0.97))`,border:`1px solid ${color}30`,borderRadius:14,padding:"22px 20px 18px",boxShadow:`0 0 0 1px ${color}12,0 0 28px ${color}10,0 10px 40px rgba(0,0,0,.7),inset 0 1px 0 ${color}18`,position:"relative",overflow:"hidden",cursor:"default"}}>
      <div style={{position:"absolute",top:0,right:0,width:50,height:50,background:`linear-gradient(225deg,${color}22,transparent)`,borderRadius:"0 14px 0 50px"}}/>
      <div style={{position:"absolute",top:0,left:"15%",right:"15%",height:1,background:`linear-gradient(90deg,transparent,${color}70,transparent)`}}/>
      <div style={{position:"absolute",bottom:-20,right:-20,width:80,height:80,background:`radial-gradient(circle,${color}10,transparent)`,borderRadius:"50%"}}/>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
        <div style={{fontSize:36,fontWeight:900,color,fontFamily:"'Orbitron',monospace",lineHeight:1,textShadow:`0 0 24px ${color}80`}}>{value??0}</div>
        <div style={{width:44,height:44,borderRadius:11,background:`${color}12`,border:`1px solid ${color}28`,display:"flex",alignItems:"center",justifyContent:"center",boxShadow:`0 0 14px ${color}18,inset 0 0 10px ${color}06`}}><Icon size={19} color={color}/></div>
      </div>
      <div style={{fontSize:9,color:`${color}80`,letterSpacing:2.5,textTransform:"uppercase",fontFamily:"'Orbitron',monospace"}}>{label}</div>
    </div>
  );

  // ─── Section Card ────────────────────────────────────────────────
  const Card=({color=C.cyan,icon:Icon,title,actions,children})=>(
    <div style={{background:"linear-gradient(160deg,rgba(6,14,30,.97) 0%,rgba(10,6,28,.97) 100%)",border:`1px solid ${color}22`,borderRadius:14,boxShadow:`0 0 0 1px ${color}08,0 0 30px ${color}06,0 10px 40px rgba(0,0,0,.5)`,overflow:"hidden"}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"16px 22px",borderBottom:`1px solid ${color}15`,background:`linear-gradient(90deg,${color}08,transparent)`}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          {Icon&&<div style={{width:30,height:30,borderRadius:7,background:`${color}15`,border:`1px solid ${color}28`,display:"flex",alignItems:"center",justifyContent:"center"}}><Icon size={14} color={color}/></div>}
          <span style={{fontFamily:"'Orbitron',monospace",fontSize:11,letterSpacing:2.5,textTransform:"uppercase",color}}>{title}</span>
        </div>
        {actions&&<div style={{display:"flex",gap:8,alignItems:"center"}}>{actions}</div>}
      </div>
      {children}
    </div>
  );

  const TH=({c})=><th style={{fontSize:8,letterSpacing:2.5,color:C.textDim,padding:"10px 18px",textAlign:"left",borderBottom:`1px solid ${C.border}`,textTransform:"uppercase",fontFamily:"'Orbitron',monospace",fontWeight:400}}>{c}</th>;
  const TD=({v,s={}})=><td style={{padding:"12px 18px",fontSize:12,borderBottom:"1px solid rgba(0,245,255,0.05)",verticalAlign:"middle",fontFamily:"'Exo 2',sans-serif",color:C.text,...s}}>{v}</td>;
  const bdg=(c,t)=><span style={{display:"inline-flex",alignItems:"center",gap:4,padding:"3px 10px",borderRadius:20,background:`${c}15`,border:`1px solid ${c}45`,color:c,fontSize:10,letterSpacing:1,textTransform:"uppercase",fontFamily:"'Exo 2',sans-serif",fontWeight:600}}>{t}</span>;

  const TABS=[{id:"dashboard",l:"Dashboard",I:BarChart3,c:C.cyan},{id:"networks",l:"Networks",I:Globe,c:C.purple},{id:"logs",l:"Postback Logs",I:Terminal,c:C.orange},{id:"duplicates",l:"Duplicates",I:Copy,c:C.yellow}];

  return(
    <div style={{minHeight:"100vh",background:`radial-gradient(ellipse at 20% 10%,rgba(0,100,255,0.07) 0%,transparent 50%),radial-gradient(ellipse at 80% 80%,rgba(180,0,255,0.07) 0%,transparent 50%),${C.bg}`,fontFamily:"'Share Tech Mono',monospace",color:C.text,position:"relative",overflow:"hidden"}}>
      <div style={{position:"fixed",inset:0,zIndex:0,pointerEvents:"none",backgroundImage:`linear-gradient(rgba(0,245,255,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(0,245,255,0.025) 1px,transparent 1px)`,backgroundSize:"50px 50px"}}/>
      <div style={{position:"fixed",top:0,left:0,right:0,height:"2px",zIndex:100,pointerEvents:"none",background:`linear-gradient(transparent,${C.cyan}12,transparent)`,animation:"pb-scan 10s linear infinite"}}/>
      <Toast t={toast}/>

      <div style={{position:"relative",zIndex:1,padding:"28px 32px",maxWidth:1600,margin:"0 auto"}}>

        {/* HEADER */}
        <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:32}}>
          <div>
            <div style={{fontSize:9,color:C.textDim,letterSpacing:4,fontFamily:"'Orbitron',monospace",marginBottom:6}}>CONTROL CENTER // NETWORK OPERATIONS</div>
            <div style={{fontSize:28,fontFamily:"'Orbitron',monospace",fontWeight:900,letterSpacing:4,background:`linear-gradient(135deg,${C.cyan} 0%,${C.teal} 50%,${C.purple} 100%)`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",filter:`drop-shadow(0 0 20px ${C.cyan}60)`}}>POSTBACK CONTROL</div>
            <div style={{display:"flex",alignItems:"center",gap:6,marginTop:8,fontSize:10,color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>
              <PulseDot color={C.green} size={6}/>
              <span style={{color:C.cyan}}>◈ NEXUS</span><ChevronRight size={10}/><span>Postback Management</span>
            </div>
          </div>
          <div style={{display:"flex",gap:10}}>
            <button className="pb-btn" style={B(C.cyan)} onClick={fetchAll}><RefreshCw size={13}/>SYNC</button>
            <button className="pb-btn" style={{...B(C.green,true),boxShadow:`0 0 20px ${C.green}30`}} onClick={openCreate}><Plus size={13}/>NEW NETWORK</button>
          </div>
        </div>

        {/* STAT GRID */}
        <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14,marginBottom:28}}>
          <SC label="Total (24H)"     value={dash.total??logs.length}                                color={C.cyan}   Icon={Activity}    accent="0,30,40"/>
          <SC label="Rewarded"        value={dash.rewarded??logs.filter(l=>l.status==="rewarded").length}  color={C.green}  Icon={CheckCircle} accent="0,40,20"/>
          <SC label="Rejected"        value={dash.rejected??logs.filter(l=>l.status==="rejected").length}  color={C.pink}   Icon={XCircle}     accent="40,0,20"/>
          <SC label="Duplicate"       value={dash.duplicate??logs.filter(l=>l.status==="duplicate").length} color={C.orange} Icon={Copy}        accent="40,20,0"/>
          <SC label="Failed"          value={dash.failed??logs.filter(l=>l.status==="failed").length}      color={C.pink}   Icon={AlertTriangle}accent="35,0,15"/>
          <SC label="Pending Review"  value={dash.pending??logs.filter(l=>l.status==="pending_review").length} color={C.yellow} Icon={Clock}    accent="40,36,0"/>
          <SC label="Active Networks" value={dashboard?.active_networks??activeNets}                        color={C.purple} Icon={Wifi}        accent="30,0,50"/>
          <SC label="Total Networks"  value={networks.length}                                               color={C.blue}   Icon={Globe}       accent="0,10,40"/>
        </div>

        {/* TABS */}
        <div style={{display:"flex",gap:2,marginBottom:24,background:"rgba(0,245,255,0.04)",borderRadius:12,padding:4,border:`1px solid ${C.border}`,width:"fit-content"}}>
          {TABS.map(t=>{
            const active=tab===t.id;
            return <button key={t.id} onClick={()=>setTab(t.id)} style={{display:"flex",alignItems:"center",gap:7,padding:"10px 20px",borderRadius:9,fontSize:11,letterSpacing:1.5,fontFamily:"'Orbitron',monospace",fontWeight:600,border:"none",cursor:"pointer",transition:"all .25s",background:active?`linear-gradient(135deg,${t.c}25,${t.c}10)`:"transparent",color:active?t.c:C.textDim,boxShadow:active?`0 0 16px ${t.c}25,inset 0 1px 0 ${t.c}30`:"none"}}>
              <t.I size={13}/>{t.l.toUpperCase()}
            </button>;
          })}
        </div>

        {/* DASHBOARD */}
        {tab==="dashboard"&&(
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
            <Card color={C.cyan} icon={Globe} title="Per-Network Stats (24H)">
              <table style={{width:"100%",borderCollapse:"collapse"}}>
                <thead><tr>{["Network","Total","Rewarded","Rejected","Success Rate"].map(h=><TH key={h} c={h}/>)}</tr></thead>
                <tbody>
                  {(dashboard?.per_network||[]).length===0
                    ?<tr><td colSpan={5} style={{padding:"32px",textAlign:"center",color:C.textDim,fontSize:11,fontFamily:"'Exo 2',sans-serif"}}>No data yet — postbacks will appear here</td></tr>
                    :(dashboard?.per_network||[]).map((n,i)=>{
                      const rate=n.total>0?Math.round((n.rewarded/n.total)*100):0;
                      return <tr key={i} className="pb-row">
                        <TD v={<span style={{color:C.cyan,fontWeight:600}}>{n.network__name||"—"}</span>}/>
                        <TD v={n.total} s={{color:C.text,fontFamily:"'Orbitron',monospace"}}/>
                        <TD v={n.rewarded} s={{color:C.green,fontFamily:"'Orbitron',monospace"}}/>
                        <TD v={n.rejected} s={{color:C.pink,fontFamily:"'Orbitron',monospace"}}/>
                        <TD v={<div style={{display:"flex",alignItems:"center",gap:8}}>
                          <div style={{flex:1,height:4,background:"rgba(0,245,255,0.1)",borderRadius:2}}>
                            <div style={{height:"100%",width:`${rate}%`,borderRadius:2,background:`linear-gradient(90deg,${C.green},${C.teal})`,boxShadow:`0 0 6px ${C.green}`,transition:"width .6s ease"}}/>
                          </div>
                          <span style={{fontSize:10,color:C.green,fontFamily:"'Orbitron',monospace",minWidth:32}}>{rate}%</span>
                        </div>}/>
                      </tr>;
                    })}
                </tbody>
              </table>
            </Card>

            <Card color={C.purple} icon={Activity} title="Recent Activity"
              actions={<button className="pb-btn" style={B(C.purple)} onClick={()=>setTab("logs")}><Eye size={11}/>ALL LOGS</button>}>
              {logs.slice(0,7).map((l,i)=>(
                <div key={l.id} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"12px 22px",borderBottom:"1px solid rgba(0,245,255,0.05)",cursor:"pointer",transition:"background .15s"}}
                  onMouseEnter={e=>e.currentTarget.style.background="rgba(180,0,255,0.06)"}
                  onMouseLeave={e=>e.currentTarget.style.background="transparent"}
                  onClick={()=>viewLog(l)}>
                  <div style={{display:"flex",alignItems:"center",gap:12}}>
                    <div style={{width:30,height:30,borderRadius:7,background:`${C.purple}15`,border:`1px solid ${C.purple}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,color:C.purple,fontFamily:"'Orbitron',monospace",fontWeight:700}}>{i+1}</div>
                    <div>
                      <div style={{fontSize:12,color:C.text,fontFamily:"'Exo 2',sans-serif"}}>
                        <span style={{color:C.purple}}>{l.network_name||"Network"}</span>
                        <span style={{color:C.textDim,margin:"0 6px"}}>·</span>
                        <span style={{fontFamily:"monospace",fontSize:10}}>{l.lead_id?.slice(0,18)||"—"}</span>
                      </div>
                      <div style={{fontSize:10,color:C.textDim,marginTop:2,fontFamily:"'Exo 2',sans-serif"}}>{l.received_at?new Date(l.received_at).toLocaleString():"—"}</div>
                    </div>
                  </div>
                  <StatusPill s={l.status}/>
                </div>
              ))}
              {logs.length===0&&<div style={{padding:"32px",textAlign:"center",color:C.textDim,fontSize:11,fontFamily:"'Exo 2',sans-serif"}}>No postback logs yet</div>}
            </Card>

            <div style={{gridColumn:"span 2"}}>
              <Card color={C.green} icon={Wifi} title="Active Network Status">
                <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:14,padding:20}}>
                  {networks.map(n=>{
                    const isA=n.status==="active";const nc=isA?C.green:C.textDim;
                    return <div key={n.id} className="pb3d" style={{background:`linear-gradient(145deg,rgba(6,14,30,.96),rgba(${isA?"0,40,20":"10,10,15"},0.96))`,border:`1px solid ${nc}28`,borderRadius:12,padding:18,boxShadow:`0 0 0 1px ${nc}08,0 0 20px ${nc}06,0 4px 20px rgba(0,0,0,.5)`,position:"relative",overflow:"hidden"}}>
                      <div style={{position:"absolute",top:0,left:0,right:0,height:1,background:`linear-gradient(90deg,transparent,${nc}60,transparent)`}}/>
                      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
                        <span style={{fontFamily:"'Exo 2',sans-serif",fontSize:13,fontWeight:600,color:C.text}}>{n.name}</span>
                        <PulseDot color={nc}/>
                      </div>
                      <div style={{fontSize:10,color:C.textDim,fontFamily:"'Exo 2',sans-serif",marginBottom:12}}>
                        <span style={{color:`${C.purple}cc`}}>{n.network_type?.toUpperCase()}</span> · <span style={{fontFamily:"monospace"}}>{n.network_key}</span>
                      </div>
                      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                        {bdg(nc,n.status)}
                        <span style={{fontSize:11,color:C.yellow,fontFamily:"'Orbitron',monospace"}}>{n.default_reward_points}pts</span>
                      </div>
                    </div>;
                  })}
                  {networks.length===0&&<div style={{gridColumn:"span 3",padding:"24px",textAlign:"center",color:C.textDim,fontSize:11,fontFamily:"'Exo 2',sans-serif"}}>No networks configured yet</div>}
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* NETWORKS */}
        {tab==="networks"&&(
          <Card color={C.purple} icon={Globe} title="Network Configurations"
            actions={<>{bdg(C.green,`Active: ${activeNets}`)}{bdg(C.textDim,`Total: ${networks.length}`)}<button className="pb-btn" style={B(C.purple,true)} onClick={openCreate}><Plus size={12}/>NEW NETWORK</button></>}>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr>{["Network","Key","Type","Algorithm","Reward","Rate Limit","Status","Actions"].map(h=><TH key={h} c={h}/>)}</tr></thead>
              <tbody>
                {loading?<tr><td colSpan={8} style={{padding:"32px",textAlign:"center",color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>Loading...</td></tr>
                :networks.length===0?<tr><td colSpan={8} style={{padding:"32px",textAlign:"center",color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>No networks — add one to get started</td></tr>
                :networks.map(n=>(
                  <tr key={n.id} className="pb-row">
                    <TD v={<div style={{display:"flex",alignItems:"center",gap:10}}><PulseDot color={n.status==="active"?C.green:C.textDim}/><div><div style={{color:C.text,fontWeight:600,fontFamily:"'Exo 2',sans-serif"}}>{n.name}</div>{n.contact_email&&<div style={{fontSize:10,color:C.textDim}}>{n.contact_email}</div>}</div></div>}/>
                    <TD v={<span style={{fontFamily:"monospace",fontSize:11,color:C.cyan}}>{n.network_key}</span>}/>
                    <TD v={bdg(C.purple,n.network_type)}/>
                    <TD v={<span style={{fontSize:10,color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>{n.signature_algorithm}</span>}/>
                    <TD v={n.default_reward_points} s={{color:C.yellow,fontFamily:"'Orbitron',monospace"}}/>
                    <TD v={`${n.rate_limit_per_minute}/min`} s={{fontSize:11,color:C.textDim}}/>
                    <TD v={bdg(n.status==="active"?C.green:C.textDim,n.status)}/>
                    <TD v={<div style={{display:"flex",gap:6}}>
                      <button className="pb-btn" style={{background:"none",border:`1px solid ${n.status==="active"?C.orange:C.green}40`,borderRadius:6,padding:"6px 10px",cursor:"pointer",color:n.status==="active"?C.orange:C.green,display:"flex",alignItems:"center",gap:4,fontSize:10,fontFamily:"'Orbitron',monospace"}} onClick={()=>handleToggle(n)}>{n.status==="active"?<WifiOff size={11}/>:<Wifi size={11}/>}{n.status==="active"?"OFF":"ON"}</button>
                      <button className="pb-btn" style={{background:"none",border:`1px solid ${C.purple}40`,borderRadius:6,padding:"6px 8px",cursor:"pointer",color:C.purple,display:"flex"}} onClick={()=>openEdit(n)}><Edit3 size={13}/></button>
                      <button className="pb-btn" style={{background:"none",border:`1px solid ${C.pink}40`,borderRadius:6,padding:"6px 8px",cursor:"pointer",color:C.pink,display:"flex"}} onClick={()=>setConfirmDel(n)}><Trash2 size={13}/></button>
                    </div>}/>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {/* LOGS */}
        {tab==="logs"&&(
          <Card color={C.orange} icon={Terminal} title="Postback Logs"
            actions={<>{bdg(C.orange,`Total: ${logs.length}`)}<button className="pb-btn" style={B(C.orange)} onClick={fetchAll}><RefreshCw size={12}/>REFRESH</button></>}>
            <div style={{display:"flex",gap:10,padding:"14px 22px",borderBottom:`1px solid ${C.border}`}}>
              <div style={{position:"relative",flex:1}}>
                <Search size={13} color={C.textDim} style={{position:"absolute",left:12,top:"50%",transform:"translateY(-50%)"}}/>
                <input style={{...iS,paddingLeft:36}} placeholder="Search lead ID, offer, network..." value={logSearch} onChange={e=>setLogSearch(e.target.value)}/>
              </div>
              <select style={{...iS,width:190}} value={logFilter} onChange={e=>setLogFilter(e.target.value)}>
                <option value="all">ALL STATUS</option>
                {["received","processing","rewarded","rejected","duplicate","failed","pending_review"].map(s=><option key={s} value={s}>{s.toUpperCase()}</option>)}
              </select>
            </div>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr>{["Network","Lead ID","Offer","Points","Status","Source IP","Time","Actions"].map(h=><TH key={h} c={h}/>)}</tr></thead>
              <tbody>
                {filteredLogs.length===0
                  ?<tr><td colSpan={8} style={{padding:"32px",textAlign:"center",color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>No logs found</td></tr>
                  :filteredLogs.slice(0,25).map(l=>(
                    <tr key={l.id} className="pb-row">
                      <TD v={<span style={{color:C.cyan,fontWeight:600}}>{l.network_name||"—"}</span>}/>
                      <TD v={<span style={{fontFamily:"monospace",fontSize:10,color:C.textDim}}>{l.lead_id?.slice(0,20)||"—"}</span>}/>
                      <TD v={<span style={{color:C.purple}}>{l.offer_id||"—"}</span>}/>
                      <TD v={l.points_awarded||0} s={{color:C.yellow,fontFamily:"'Orbitron',monospace"}}/>
                      <TD v={<StatusPill s={l.status}/>}/>
                      <TD v={l.source_ip||"—"} s={{fontSize:10,color:C.textDim}}/>
                      <TD v={l.received_at?new Date(l.received_at).toLocaleString():"—"} s={{fontSize:10,color:C.textDim}}/>
                      <TD v={<div style={{display:"flex",gap:6}}>
                        <button className="pb-btn" style={{background:"none",border:`1px solid ${C.cyan}35`,borderRadius:6,padding:"5px 8px",cursor:"pointer",color:C.cyan,display:"flex"}} onClick={()=>viewLog(l)} title="View"><Eye size={13}/></button>
                        {(l.status==="failed"||l.status==="rejected")&&<button className="pb-btn" style={{background:"none",border:`1px solid ${C.yellow}35`,borderRadius:6,padding:"5px 8px",cursor:"pointer",color:C.yellow,display:"flex"}} onClick={()=>handleRetry(l.id)} title="Retry"><RotateCcw size={13}/></button>}
                      </div>}/>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Card>
        )}

        {/* DUPLICATES */}
        {tab==="duplicates"&&(
          <Card color={C.yellow} icon={Copy} title="Duplicate Lead Registry"
            actions={bdg(C.yellow,`Total: ${duplicates.length}`)}>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr>{["Lead ID","Network","First Seen","Actions"].map(h=><TH key={h} c={h}/>)}</tr></thead>
              <tbody>
                {duplicates.length===0
                  ?<tr><td colSpan={4} style={{padding:"32px",textAlign:"center",color:C.textDim,fontFamily:"'Exo 2',sans-serif"}}>No duplicate entries</td></tr>
                  :duplicates.map(d=>(
                    <tr key={d.id} className="pb-row">
                      <TD v={<span style={{fontFamily:"monospace",color:C.yellow}}>{d.lead_id||"—"}</span>}/>
                      <TD v={<span style={{color:C.cyan}}>{d.network_name||d.network||"—"}</span>}/>
                      <TD v={d.first_seen_at?new Date(d.first_seen_at).toLocaleString():"—"} s={{fontSize:10,color:C.textDim}}/>
                      <TD v={<button className="pb-btn" style={B(C.pink)} onClick={async()=>{try{await client.delete(`postback/duplicates/${d.id}/`);setDuplicates(p=>p.filter(x=>x.id!==d.id));showToast("Cleared","success");}catch{showToast("Failed","error");}}}><Trash2 size={11}/>CLEAR</button>}/>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {/* MODALS */}
      <CrudModal open={!!netModal} title={netModal?.mode==="create"?"NEW NETWORK CONFIG":"EDIT NETWORK"} color={C.cyan} onClose={()=>setNetModal(null)} onSave={handleSave} saving={saving}>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
          <div><label style={lS}>Network Name *</label><input style={iS} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="e.g. Adgate Media"/></div>
          <div><label style={lS}>Network Key *</label><input style={iS} value={form.network_key} onChange={e=>setForm({...form,network_key:e.target.value})} placeholder="e.g. adgate_001"/></div>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
          <div><label style={lS}>Network Type</label><select style={iS} value={form.network_type} onChange={e=>setForm({...form,network_type:e.target.value})}>{["cpa","cpl","cpi","affiliate","direct","internal"].map(t=><option key={t} value={t}>{t.toUpperCase()}</option>)}</select></div>
          <div><label style={lS}>Status</label><select style={iS} value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>{["active","inactive","testing"].map(s=><option key={s} value={s}>{s.toUpperCase()}</option>)}</select></div>
        </div>
        <label style={lS}>Secret Key</label><input style={iS} value={form.secret_key} onChange={e=>setForm({...form,secret_key:e.target.value})} placeholder="HMAC secret key"/>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
          <div><label style={lS}>Signature Algorithm</label><select style={iS} value={form.signature_algorithm} onChange={e=>setForm({...form,signature_algorithm:e.target.value})}>{["hmac_sha256","hmac_sha512","md5","none"].map(a=><option key={a} value={a}>{a}</option>)}</select></div>
          <div><label style={lS}>Dedup Window</label><select style={iS} value={form.dedup_window} onChange={e=>setForm({...form,dedup_window:e.target.value})}>{[["1h","1 Hour"],["1d","1 Day"],["7d","7 Days"],["30d","30 Days"],["forever","Forever"]].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
          <div><label style={lS}>Default Reward Points</label><input style={iS} type="number" value={form.default_reward_points} onChange={e=>setForm({...form,default_reward_points:parseInt(e.target.value)||0})}/></div>
          <div><label style={lS}>Rate Limit (per min)</label><input style={iS} type="number" value={form.rate_limit_per_minute} onChange={e=>setForm({...form,rate_limit_per_minute:parseInt(e.target.value)||60})}/></div>
        </div>
        <label style={lS}>Contact Email</label><input style={iS} type="email" value={form.contact_email} onChange={e=>setForm({...form,contact_email:e.target.value})} placeholder="network@example.com"/>
        <label style={lS}>Notes</label><textarea style={{...iS,minHeight:72,resize:"vertical"}} value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})} placeholder="Internal notes..."/>
        <div style={{marginTop:16}}><label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontFamily:"'Exo 2',sans-serif",fontSize:12}}><input type="checkbox" checked={form.require_nonce} onChange={e=>setForm({...form,require_nonce:e.target.checked})}/><Key size={12} color={C.cyan}/>Require Nonce</label></div>
      </CrudModal>

      <LogModal log={logDetail} onClose={()=>setLogDetail(null)} onRetry={handleRetry}/>
      <Confirm open={!!confirmDel} label={confirmDel?.name} onConfirm={handleDelete} onCancel={()=>setConfirmDel(null)}/>
    </div>
  );
}