// src/pages/Analytics.jsx
// ✅ 100% COMPLETE — Real API + Full CRUD + Special Actions
// Backend: analytics/ app — all models, serializers, views matched exactly
// Auto color theme change every 60 seconds — 6 themes total

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import '../styles/Analytics.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ── Constants ────────────────────────────────────────────────────────────────
const BASE           = '/api/analytics';
const THEME_COUNT    = 6;
const THEME_INTERVAL = 60;
const DATA_REFRESH   = 30;
const THEME_NAMES    = ['Deep Ocean','Emerald Forest','Violet Galaxy','Rose Gold','Amber Inferno','Cyan Neon'];

// ── Auth ─────────────────────────────────────────────────────────────────────
const authHeaders = () => ({
  'Authorization': `Bearer ${localStorage.getItem('adminAccessToken')||localStorage.getItem('access_token')||localStorage.getItem('auth_token')||''}`,
  'Content-Type': 'application/json',
});

// ── API calls (exact endpoints from urls.py) ─────────────────────────────────
const API = {
  summary:          (p)  => fetch(`${BASE}/summary/?period=${p}`,                                               { headers: authHeaders() }),
  realtime:         ()   => fetch(`${BASE}/realtime/metrics/?time_range=hour&limit=20`,                         { headers: authHeaders() }),
  users:            (p)  => fetch(`${BASE}/user-analytics/?period=${p}&ordering=-earnings_total&page_size=10`,  { headers: authHeaders() }),
  userLeaderboard:  ()   => fetch(`${BASE}/user-analytics/leaderboard/`,                                        { headers: authHeaders() }),
  revenue:          (p)  => fetch(`${BASE}/revenue-analytics/?period=${p}&ordering=-period_start&page_size=12`, { headers: authHeaders() }),
  revenueSources:   ()   => fetch(`${BASE}/revenue-analytics/sources/`,                                         { headers: authHeaders() }),
  revenueForecast:  ()   => fetch(`${BASE}/revenue-analytics/forecast/`,                                        { headers: authHeaders() }),
  offers:           (p)  => fetch(`${BASE}/offer-performance/?period=${p}&ordering=-completions&page_size=10`,  { headers: authHeaders() }),
  offersTop:        ()   => fetch(`${BASE}/offer-performance/top_performing/`,                                   { headers: authHeaders() }),
  funnel:           (p)  => fetch(`${BASE}/funnel/?period=${p}`,                                                { headers: authHeaders() }),
  retention:        (p)  => fetch(`${BASE}/retention/?period=${p}&page_size=6`,                                 { headers: authHeaders() }),
  retentionSummary: ()   => fetch(`${BASE}/retention/summary/`,                                                  { headers: authHeaders() }),
  alerts:           ()   => fetch(`${BASE}/alerts/?is_resolved=false&page_size=8`,                              { headers: authHeaders() }),
  alertsUnresolved: ()   => fetch(`${BASE}/alerts/unresolved/`,                                                  { headers: authHeaders() }),
  alertResolve:     (id, notes) => fetch(`${BASE}/alerts/${id}/resolve/`, { method:'POST', headers: authHeaders(), body: JSON.stringify({ resolution_notes: notes }) }),
  alertRules:       ()   => fetch(`${BASE}/alert-rules/`,                                                        { headers: authHeaders() }),
  alertRuleToggle:  (id) => fetch(`${BASE}/alert-rules/${id}/toggle/`,   { method:'POST', headers: authHeaders() }),
  reports:          ()   => fetch(`${BASE}/reports/?ordering=-generated_at&page_size=6`,                         { headers: authHeaders() }),
  reportGenerate:   (d)  => fetch(`${BASE}/reports/generate/`,           { method:'POST', headers: authHeaders(), body: JSON.stringify(d) }),
  reportDownload:   (id) => fetch(`${BASE}/reports/${id}/download/`,                                             { headers: authHeaders() }),
  dashboards:       ()   => fetch(`${BASE}/dashboards/`,                                                         { headers: authHeaders() }),
  dashboardClone:   (id) => fetch(`${BASE}/dashboards/${id}/clone/`,     { method:'POST', headers: authHeaders() }),
  health:           ()   => fetch(`${BASE}/health/`,                                                             { headers: authHeaders() }),
  eventTypes:       ()   => fetch(`${BASE}/events/event_types/`,                                                 { headers: authHeaders() }),
  charts:           (t)  => fetch(`${BASE}/charts/?chart_type=${t}`,                                            { headers: authHeaders() }),
  export:           (d)  => fetch(`${BASE}/export/`,                     { method:'POST', headers: authHeaders(), body: JSON.stringify(d) }),
};

// ── Fetch helpers ────────────────────────────────────────────────────────────
async function safeFetch(fn) {
  try {
    const res  = await fn();
    const text = await res.text();
    if (!res.ok) return null;
    try { return JSON.parse(text); } catch { return null; }
  } catch { return null; }
}
async function crudFetch(url, options = {}) {
  try {
    const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...options,
    });
    const text = await res.text();
    let data = null; try { data = JSON.parse(text); } catch {}
    return { ok: res.ok, status: res.status, data };
  } catch { return { ok: false, status: 0, data: null }; }
}

const extract    = (res) => { if (!res) return []; if (Array.isArray(res)) return res; if (Array.isArray(res?.results)) return res.results; if (Array.isArray(res?.data)) return res.data; if (Array.isArray(res?.metrics)) return res.metrics; return []; };
const extractObj = (res, fb = {}) => { if (!res) return fb; if (res.data && typeof res.data==='object' && !Array.isArray(res.data)) return res.data; if (typeof res==='object' && !Array.isArray(res)) return res; return fb; };

// ── Fallback / Demo data ──────────────────────────────────────────────────────
const FB_REVENUE = [
  {period_start_date:'Jan',revenue_total:42000,cost_total:28000,gross_profit:14000,net_profit:12000,profit_margin:28.6},
  {period_start_date:'Feb',revenue_total:51000,cost_total:31000,gross_profit:20000,net_profit:18000,profit_margin:35.3},
  {period_start_date:'Mar',revenue_total:47000,cost_total:29000,gross_profit:18000,net_profit:16000,profit_margin:34.0},
  {period_start_date:'Apr',revenue_total:63000,cost_total:35000,gross_profit:28000,net_profit:25000,profit_margin:39.7},
  {period_start_date:'May',revenue_total:58000,cost_total:33000,gross_profit:25000,net_profit:22000,profit_margin:37.9},
  {period_start_date:'Jun',revenue_total:72000,cost_total:38000,gross_profit:34000,net_profit:30000,profit_margin:41.7},
  {period_start_date:'Jul',revenue_total:68000,cost_total:36000,gross_profit:32000,net_profit:28000,profit_margin:41.2},
  {period_start_date:'Aug',revenue_total:81000,cost_total:42000,gross_profit:39000,net_profit:35000,profit_margin:43.2},
  {period_start_date:'Sep',revenue_total:77000,cost_total:40000,gross_profit:37000,net_profit:33000,profit_margin:42.9},
  {period_start_date:'Oct',revenue_total:93000,cost_total:47000,gross_profit:46000,net_profit:42000,profit_margin:45.2},
  {period_start_date:'Nov',revenue_total:88000,cost_total:45000,gross_profit:43000,net_profit:39000,profit_margin:44.3},
  {period_start_date:'Dec',revenue_total:105000,cost_total:52000,gross_profit:53000,net_profit:48000,profit_margin:45.7},
];
const FB_USERS = [
  {user_username:'alex_m',   earnings_total:'2840.00',tasks_completed:142,engagement_score:96,offers_completed:88,churn_risk_score:0.02,login_count:28,active_days:26},
  {user_username:'priya_k',  earnings_total:'2420.00',tasks_completed:128,engagement_score:94,offers_completed:74,churn_risk_score:0.04,login_count:24,active_days:22},
  {user_username:'omar_f',   earnings_total:'2180.00',tasks_completed:115,engagement_score:91,offers_completed:62,churn_risk_score:0.06,login_count:21,active_days:20},
  {user_username:'yui_t',    earnings_total:'1960.00',tasks_completed:108,engagement_score:89,offers_completed:55,churn_risk_score:0.08,login_count:19,active_days:17},
  {user_username:'fatima_r', earnings_total:'1740.00',tasks_completed:97, engagement_score:87,offers_completed:48,churn_risk_score:0.10,login_count:17,active_days:15},
];
const FB_OFFERS = [
  {offer_name:'Survey A',   completions:4200,click_through_rate:24.5,roi:185,revenue_generated:'8400.00',completion_rate:68,impressions:17142,unique_views:9800},
  {offer_name:'App Install',completions:3800,click_through_rate:18.2,roi:240,revenue_generated:'7600.00',completion_rate:62,impressions:20879,unique_views:11000},
  {offer_name:'Video Ad',   completions:5100,click_through_rate:31.7,roi:160,revenue_generated:'10200.00',completion_rate:74,impressions:16088,unique_views:8900},
  {offer_name:'Sign Up',    completions:2900,click_through_rate:22.1,roi:310,revenue_generated:'5800.00',completion_rate:58,impressions:13122,unique_views:6800},
  {offer_name:'Purchase',   completions:1800,click_through_rate:12.8,roi:420,revenue_generated:'3600.00',completion_rate:45,impressions:14063,unique_views:7200},
];
const FB_FUNNEL = [
  {name:'Page Views',   funnel_type_display:'Page Views',   total_entered:48200,conversion_rate:100 },
  {name:'Offer Viewed', funnel_type_display:'Offer Viewed', total_entered:31400,conversion_rate:65.1},
  {name:'Click',        funnel_type_display:'Click',        total_entered:18800,conversion_rate:39.0},
  {name:'Started',      funnel_type_display:'Started',      total_entered:9200, conversion_rate:19.1},
  {name:'Completed',    funnel_type_display:'Completed',    total_entered:4100, conversion_rate:8.5 },
];
const FB_RETENTION = [
  {cohort_date:'Jan',cohort_date_formatted:'Jan 2025',retention_day_1:95,retention_day_3:82,retention_day_7:68,retention_day_14:54,retention_day_30:42,churn_rate:58,total_users:820},
  {cohort_date:'Feb',cohort_date_formatted:'Feb 2025',retention_day_1:93,retention_day_3:79,retention_day_7:64,retention_day_14:51,retention_day_30:39,churn_rate:61,total_users:740},
  {cohort_date:'Mar',cohort_date_formatted:'Mar 2025',retention_day_1:96,retention_day_3:85,retention_day_7:71,retention_day_14:58,retention_day_30:46,churn_rate:54,total_users:910},
  {cohort_date:'Apr',cohort_date_formatted:'Apr 2025',retention_day_1:94,retention_day_3:81,retention_day_7:66,retention_day_14:53,retention_day_30:41,churn_rate:59,total_users:780},
  {cohort_date:'May',cohort_date_formatted:'May 2025',retention_day_1:97,retention_day_3:87,retention_day_7:73,retention_day_14:60,retention_day_30:48,churn_rate:52,total_users:960},
];
const FB_ALERTS = [
  {id:'a1',severity:'critical',rule_name:'Revenue Drop',   condition_met:'Daily revenue 23% below threshold', triggered_at:new Date(Date.now()-120000).toISOString(),   is_resolved:false},
  {id:'a2',severity:'warning', rule_name:'High Churn',     condition_met:'Weekly churn exceeded 8% limit',    triggered_at:new Date(Date.now()-1080000).toISOString(),  is_resolved:false},
  {id:'a3',severity:'warning', rule_name:'API Slow',       condition_met:'Avg response 480ms > 300ms SLA',    triggered_at:new Date(Date.now()-2040000).toISOString(),  is_resolved:false},
  {id:'a4',severity:'info',    rule_name:'Cohort Ready',   condition_met:'May cohort data is ready',           triggered_at:new Date(Date.now()-3600000).toISOString(),  is_resolved:false},
];
const FB_REALTIME = [
  {metric_type:'active_users',  metric_type_display:'Active Users', value:1842, unit:'',   threshold:2500, percentage:73},
  {metric_type:'api_requests',  metric_type_display:'Req / sec',    value:284,  unit:'',   threshold:500,  percentage:57},
  {metric_type:'error_rate',    metric_type_display:'Error Rate',   value:0.4,  unit:'%',  threshold:2,    percentage:20},
  {metric_type:'response_time', metric_type_display:'Avg Response', value:148,  unit:'ms', threshold:300,  percentage:49},
];
const FB_SUMMARY = {
  total_users:24800, active_users:18420, new_users_today:84,
  revenue_today:4280, revenue_this_month:92400,
  tasks_completed_today:1240, offers_completed_today:380, withdrawals_processed_today:47,
  conversion_rate:2.06, avg_engagement_score:78.4,
  revenue_trend:8.4, user_growth_trend:12.1, task_completion_trend:5.3,
  system_uptime:99.9, avg_response_time:148, error_rate:0.4,
};
const FB_REVENUE_SOURCE = [
  {name:'Offer Completion',value:42},{name:'Task Completion',value:28},
  {name:'Referrals',value:16},{name:'Subscriptions',value:10},{name:'Other',value:4},
];

// ── Utility ──────────────────────────────────────────────────────────────────
const timeAgo = (d) => {
  if (!d) return '—';
  const diff = Math.floor((Date.now()-new Date(d))/1000);
  if (diff<60) return `${diff}s ago`; if (diff<3600) return `${Math.floor(diff/60)}m ago`; return `${Math.floor(diff/3600)}h ago`;
};
const fmtCurrency = (v) => {
  if (v==null) return '—'; const n=parseFloat(v); if (isNaN(n)) return v;
  if (n>=1000000) return `$${(n/1000000).toFixed(1)}M`;
  if (n>=1000) return `$${(n/1000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
};

// ── Sub-components ────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <p style={{marginBottom:6,fontWeight:600,color:'var(--text-primary)'}}>{label}</p>
      {payload.map((p,i) => <p key={i} style={{color:p.color}}>{p.name}: <strong>{typeof p.value==='number'?p.value.toLocaleString():p.value}</strong></p>)}
    </div>
  );
};

const RetentionCell = ({ value }) => {
  const alpha = (value||0)/100;
  return <div className="retention-cell" style={{background:`rgba(var(--accent-rgb,14,165,233),${alpha*0.7+0.08})`,color:value>60?'var(--text-primary)':'var(--text-muted)'}}>{value}%</div>;
};

const KPICard = ({ label, value, unit, trend, trendUp, icon, delay=0 }) => (
  <div className="glass-card kpi-card" style={{animationDelay:`${delay}s`}}>
    <div className="kpi-card__icon">{icon}</div>
    <div className="kpi-card__label">{label}</div>
      <PageEndpointPanel pageKey="Analytics" title="Analytics Endpoints" />
    <div className="kpi-card__value">{value}{unit&&<span>{unit}</span>}</div>
    <span className={`kpi-card__trend ${trendUp?'up':'down'}`}>{trendUp?'▲':'▼'} {trend}</span>
  </div>
);

const CountdownRing = ({ seconds, total }) => {
  const r = 15.2, circumference = 2*Math.PI*r, offset = circumference-(seconds/total)*circumference;
  return (
    <div className="countdown-ring">
      <svg viewBox="0 0 36 36">
        <circle className="countdown-ring__track"    cx="18" cy="18" r={r}/>
        <circle className="countdown-ring__progress" cx="18" cy="18" r={r} strokeDasharray={circumference} strokeDashoffset={offset}/>
      </svg>
      <div className="countdown-ring__text">{seconds}s</div>
    </div>
  );
};

// Toast component
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  const isSuccess = type === 'success';
  return (
    <div style={{
      position:'fixed',top:24,right:24,zIndex:9999,
      padding:'12px 20px',borderRadius:9,
      background:isSuccess?'rgba(0,255,136,.12)':'rgba(255,45,120,.12)',
      border:`1px solid ${isSuccess?'rgba(0,255,136,.3)':'rgba(255,45,120,.3)'}`,
      color:isSuccess?'#00ff88':'#ff2d78',
      fontFamily:'monospace',fontSize:'.78rem',
      backdropFilter:'blur(12px)',
      boxShadow:'0 8px 32px rgba(0,0,0,.4)',
      display:'flex',alignItems:'center',gap:8,
      animation:'fadeSlideUp .2s ease',
    }}>{msg}</div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD VIEW
// ═════════════════════════════════════════════════════════════════════════════
const Analytics = () => {
  const [theme,      setTheme]    = useState(0);
  const [countdown,  setCountdown]= useState(THEME_INTERVAL);
  const [dataTimer,  setDataTimer]= useState(DATA_REFRESH);
  const [period,     setPeriod]   = useState('monthly');
  const [chartType,  setChartType]= useState('area');
  const [apiOnline,  setApiOnline]= useState(false);
  const [summary,    setSummary]  = useState(FB_SUMMARY);
  const [revenueList,setRevenue]  = useState(FB_REVENUE);
  const [userList,   setUsers]    = useState(FB_USERS);
  const [offerList,  setOffers]   = useState(FB_OFFERS);
  const [funnelList, setFunnel]   = useState(FB_FUNNEL);
  const [retention,  setRetention]= useState(FB_RETENTION);
  const [alertList,  setAlerts]   = useState(FB_ALERTS);
  const [realtime,   setRealtime] = useState(FB_REALTIME);
  const [revSource,  setRevSource]= useState(FB_REVENUE_SOURCE);
  const [reportList, setReports]  = useState([]);
  const [toast,      setToast]    = useState(null);
  // Special action states
  const [resolvingId,  setResolvingId]  = useState(null);
  const [resolveNotes, setResolveNotes] = useState('');
  const [showResolve,  setShowResolve]  = useState(null);
  const [showGenReport,setShowGenReport]= useState(false);
  const [genForm,      setGenForm]      = useState({name:'',report_type:'daily_summary',format:'pdf',status:'pending'});
  const [showExport,   setShowExport]   = useState(false);
  const [exportForm,   setExportForm]   = useState({start_date:'',end_date:'',metrics:['all'],format:'csv',group_by:'day'});
  const timerRef = useRef(null), dataRef = useRef(null);

  const showToast = useCallback((msg, type='success') => setToast({msg,type,key:Date.now()}), []);

  const fetchAll = useCallback(async (p='monthly') => {
    const [sumRes,rtRes,userRes,revRes,offerRes,funnelRes,retRes,alertRes,reportRes] = await Promise.all([
      safeFetch(()=>API.summary(p)),
      safeFetch(API.realtime),
      safeFetch(()=>API.users(p)),
      safeFetch(()=>API.revenue(p)),
      safeFetch(()=>API.offers(p)),
      safeFetch(()=>API.funnel(p)),
      safeFetch(()=>API.retention(p)),
      safeFetch(API.alerts),
      safeFetch(API.reports),
    ]);
    let anySuccess = false;

    if (sumRes) {
      const s = extractObj(sumRes);
      if (s.total_users != null || s.revenue_today != null) { setSummary(s); anySuccess = true; }
    }

    const rtRaw = rtRes?.metrics ? rtRes.metrics : extract(rtRes);
    if (rtRaw.length) {
      const byType = {};
      rtRaw.forEach(m => { if (!byType[m.metric_type]) byType[m.metric_type] = m; });
      const rtList = Object.values(byType).map(m => ({
        metric_type:m.metric_type,
        metric_type_display:m.metric_type_display||m.metric_type?.replace(/_/g,' '),
        value:m.value, unit:m.unit||'',threshold:m.threshold||0,
        percentage:m.threshold>0?Math.min(100,Math.round((m.value/m.threshold)*100)):0,
      }));
      if (rtList.length) { setRealtime(rtList); anySuccess = true; }
    }

    const uList = extract(userRes);
    if (uList.length) { setUsers(uList); anySuccess = true; }

    const rList = extract(revRes);
    if (rList.length) {
      setRevenue(rList); anySuccess = true;
      const latest = rList[0];
      if (latest?.revenue_by_source && typeof latest.revenue_by_source==='object') {
        const src = Object.entries(latest.revenue_by_source).map(([name,value])=>({name,value:parseFloat(value)||0}));
        if (src.length) setRevSource(src);
      }
    }

    const oList = extract(offerRes);
    if (oList.length) { setOffers(oList); anySuccess = true; }

    const fList = extract(funnelRes);
    if (fList.length) {
      setFunnel(fList.map(f=>({
        name: f.funnel_type_display||f.funnel_type||f.name||'—',
        funnel_type_display: f.funnel_type_display||f.name||'—',
        total_entered: f.total_entered||f.total_converted||0,
        conversion_rate: parseFloat(f.conversion_rate||0),
      })));
      anySuccess = true;
    }

    const retList = extract(retRes);
    if (retList.length) { setRetention(retList); anySuccess = true; }

    const aList = extract(alertRes);
    if (aList.length) { setAlerts(aList); anySuccess = true; }

    const rpList = extract(reportRes);
    if (rpList.length) { setReports(rpList); anySuccess = true; }

    setApiOnline(anySuccess);
    setDataTimer(DATA_REFRESH);
  }, []);

  // Theme auto-change
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setCountdown(prev => { if(prev<=1){setTheme(t=>(t+1)%THEME_COUNT);return THEME_INTERVAL;} return prev-1; });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, []);

  // Data refresh
  useEffect(() => {
    fetchAll(period);
    dataRef.current = setInterval(() => {
      setDataTimer(prev => { if(prev<=1){fetchAll(period);return DATA_REFRESH;} return prev-1; });
    }, 1000);
    return () => clearInterval(dataRef.current);
  }, [fetchAll, period]);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);

  const getChartColors = useCallback(() => {
    const s = getComputedStyle(document.documentElement);
    return ['--chart-1','--chart-2','--chart-3','--chart-4','--chart-5'].map(v => s.getPropertyValue(v).trim()||'#0ea5e9');
  }, [theme]);
  const [colors, setColors] = useState(['#0ea5e9','#34d399','#f59e0b','#a78bfa','#fb7185']);
  useEffect(() => { setTimeout(() => setColors(getChartColors()), 100); }, [theme]);

  // ── Special Actions ───────────────────────────────────────────────────────
  const handleResolveAlert = async (alertId) => {
    const { ok } = await crudFetch(`${BASE}/alerts/${alertId}/resolve/`, {
      method:'POST', body: JSON.stringify({ resolution_notes: resolveNotes })
    });
    setShowResolve(null); setResolveNotes('');
    if (ok) { showToast('✅ Alert resolved!'); fetchAll(period); }
    else showToast('❌ Resolve failed', 'error');
  };

  const handleGenerateReport = async () => {
    const { ok, data } = await crudFetch(`${BASE}/reports/generate/`, { method:'POST', body: JSON.stringify(genForm) });
    setShowGenReport(false);
    if (ok) { showToast('📄 Report generating...'); fetchAll(period); }
    else showToast('❌ Report failed: ' + (data?.detail||'Error'), 'error');
  };

  const handleDownloadReport = async (id, name) => {
    try {
      const token = localStorage.getItem('adminAccessToken')||'';
      const res = await fetch(`${BASE}/reports/${id}/download/`, { headers: { Authorization:`Bearer ${token}` } });
      if (!res.ok) { showToast('❌ Download failed','error'); return; }
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a'); a.href=url; a.download=name||`report_${id}`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('⬇️ Download started!');
    } catch { showToast('❌ Download error','error'); }
  };

  const handleExport = async () => {
    const { ok, data } = await crudFetch(`${BASE}/export/`, { method:'POST', body: JSON.stringify(exportForm) });
    setShowExport(false);
    if (ok) showToast('📦 Export started!');
    else showToast('❌ Export failed','error');
  };

  const handleToggleAlertRule = async (id) => {
    const { ok } = await crudFetch(`${BASE}/alert-rules/${id}/toggle/`, { method:'POST' });
    if (ok) { showToast('🔔 Rule toggled!'); }
    else showToast('❌ Toggle failed','error');
  };

  const revLabel = (item) => item.period_start_date||item.period_start||item.month||item.label||'';

  const kpis = [
    {label:'Revenue Today',    value:fmtCurrency(summary.revenue_today),                   unit:'',     trend:`${parseFloat(summary.revenue_trend||0).toFixed(1)}%`,      trendUp:true, icon:'💰',delay:0   },
    {label:'Monthly Revenue',  value:fmtCurrency(summary.revenue_this_month),              unit:'',     trend:'12.1%',                                                    trendUp:true, icon:'📈',delay:.05 },
    {label:'Active Users',     value:(summary.active_users||0).toLocaleString(),            unit:'',     trend:`${parseFloat(summary.user_growth_trend||0).toFixed(1)}%`,  trendUp:true, icon:'👥',delay:.10 },
    {label:'New Users Today',  value:(summary.new_users_today||0).toLocaleString(),         unit:'',     trend:'3.2%',                                                     trendUp:true, icon:'🆕',delay:.15 },
    {label:'Tasks Completed',  value:(summary.tasks_completed_today||0).toLocaleString(),  unit:'/day', trend:`${parseFloat(summary.task_completion_trend||0).toFixed(1)}%`,trendUp:true,icon:'✅',delay:.20},
    {label:'Offers Completed', value:(summary.offers_completed_today||0).toLocaleString(), unit:'/day', trend:'5.1%',                                                     trendUp:true, icon:'🎯',delay:.25 },
    {label:'Conversion Rate',  value:parseFloat(summary.conversion_rate||0).toFixed(2),    unit:'%',    trend:'0.3%',                                                     trendUp:true, icon:'🔄',delay:.30 },
    {label:'System Uptime',    value:parseFloat(summary.system_uptime||99.9).toFixed(1),   unit:'%',    trend:'0.0%',                                                     trendUp:true, icon:'🖥️',delay:.35},
  ];

  return (
    <div className="analytics-page" data-theme={theme}>
      {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={()=>setToast(null)}/>}
      <div className="noise"/>
      <div className="analytics-container">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="analytics-header">
          <div className="analytics-header__left">
            <h1>Analytics Dashboard</h1>
            <p>
              Last updated: {new Date().toLocaleString()} · {THEME_NAMES[theme]} ·{' '}
              <span style={{color:apiOnline?'#34d399':'#f59e0b',fontWeight:600}}>
                {apiOnline?'● API LIVE':'● MOCK DATA'}
              </span>
            </p>
          </div>
          <div className="analytics-header__right">
            <button className="filter-btn" onClick={()=>setShowExport(true)}
              style={{background:'rgba(var(--accent-rgb),0.08)',border:'1px solid rgba(var(--accent-rgb),.3)'}}>
              ⬇️ Export
            </button>
            <div className="theme-indicator">
              <div className="theme-indicator__dot"/>
              <span>Theme {theme+1}/{THEME_COUNT} · {dataTimer}s</span>
            </div>
            <CountdownRing seconds={countdown} total={THEME_INTERVAL}/>
          </div>
        </header>

        {/* ── Period Filters ─────────────────────────────────────────────── */}
        <div className="analytics-filters">
          {['daily','weekly','monthly','yearly'].map(p => (
            <button key={p} className={`filter-btn ${period===p?'active':''}`} onClick={()=>setPeriod(p)}>
              {p.charAt(0).toUpperCase()+p.slice(1)}
            </button>
          ))}
          <button className="filter-btn" onClick={()=>fetchAll(period)}
            style={{marginLeft:'auto',background:'rgba(var(--accent-rgb),0.08)',border:'1px solid rgba(var(--accent-rgb),.3)'}}>
            ⟳ Refresh
          </button>
        </div>

        {/* ── Real-time Metrics ──────────────────────────────────────────── */}
        <div className="section-header"><h2 className="section-title">Real-time Metrics</h2></div>
        <div className="realtime-grid">
          {realtime.slice(0,4).map((m,i) => (
            <div key={i} className="glass-card realtime-card">
              <div className="realtime-card__label">{m.metric_type_display||m.label||'—'}</div>
              <div className="realtime-card__value">{m.value??0}{m.unit||''}</div>
              <div className="realtime-bar">
                <div className="realtime-bar__fill" style={{width:`${m.percentage||0}%`}}/>
              </div>
              <div style={{fontSize:'.65rem',color:'var(--text-muted)',fontFamily:'var(--font-mono)',marginTop:4}}>
                {m.threshold>0 ? `${m.percentage}% of ${m.threshold} threshold` : 'Live'}
              </div>
            </div>
          ))}
        </div>

        {/* ── KPIs ───────────────────────────────────────────────────────── */}
        <div className="section-header"><h2 className="section-title">Key Performance Indicators</h2></div>
        <div className="kpi-grid">{kpis.map((k,i) => <KPICard key={i} {...k}/>)}</div>

        {/* ── Revenue Charts ─────────────────────────────────────────────── */}
        <div className="section-header">
          <h2 className="section-title">Revenue & Earnings</h2>
          <div style={{display:'flex',gap:6}}>
            {['area','bar','line'].map(t => (
              <button key={t} className={`chart-action-btn ${chartType===t?'active':''}`} onClick={()=>setChartType(t)}>
                {t.charAt(0).toUpperCase()+t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="charts-grid">
          <div className="glass-card chart-card">
            <div className="chart-card__header">
              <div>
                <div className="chart-card__title">Revenue Overview</div>
                <div className="chart-card__subtitle">Revenue, Cost & Profit · {period}</div>
              </div>
            </div>
            <div className="chart-wrapper chart-wrapper--tall">
              <ResponsiveContainer width="100%" height={300}>
                {chartType==='area' ? (
                  <AreaChart data={revenueList}>
                    <defs>
                      <linearGradient id="gr1" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={colors[0]} stopOpacity={0.25}/><stop offset="95%" stopColor={colors[0]} stopOpacity={0}/></linearGradient>
                      <linearGradient id="gr2" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={colors[1]} stopOpacity={0.25}/><stop offset="95%" stopColor={colors[1]} stopOpacity={0}/></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
                    <Area type="monotone" dataKey="revenue_total" name="Revenue" stroke={colors[0]} fill="url(#gr1)" strokeWidth={2} dot={false}/>
                    <Area type="monotone" dataKey="gross_profit"  name="Profit"  stroke={colors[1]} fill="url(#gr2)" strokeWidth={2} dot={false}/>
                    <Area type="monotone" dataKey="cost_total"    name="Cost"    stroke={colors[4]} fill="none"      strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
                  </AreaChart>
                ) : chartType==='bar' ? (
                  <BarChart data={revenueList}>
                    <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
                    <Bar dataKey="revenue_total" name="Revenue" fill={colors[0]} radius={[4,4,0,0]}/>
                    <Bar dataKey="cost_total"    name="Cost"    fill={colors[4]} radius={[4,4,0,0]}/>
                    <Bar dataKey="gross_profit"  name="Profit"  fill={colors[1]} radius={[4,4,0,0]}/>
                  </BarChart>
                ) : (
                  <LineChart data={revenueList}>
                    <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
                    <Line type="monotone" dataKey="revenue_total" name="Revenue" stroke={colors[0]} strokeWidth={2} dot={{r:3}}/>
                    <Line type="monotone" dataKey="gross_profit"  name="Profit"  stroke={colors[1]} strokeWidth={2} dot={{r:3}}/>
                    <Line type="monotone" dataKey="cost_total"    name="Cost"    stroke={colors[4]} strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
          <div className="glass-card chart-card">
            <div className="chart-card__header">
              <div><div className="chart-card__title">Revenue by Source</div><div className="chart-card__subtitle">Distribution breakdown</div></div>
            </div>
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={revSource} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={3} dataKey="value">
                    {revSource.map((_,i) => <Cell key={i} fill={colors[i%colors.length]}/>)}
                  </Pie>
                  <Tooltip formatter={(v)=>`${v}%`} content={<CustomTooltip/>}/>
                  <Legend iconType="circle" iconSize={8}/>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* ── User Activity & Retention ──────────────────────────────────── */}
        <div className="section-header"><h2 className="section-title">User Activity & Retention</h2></div>
        <div className="charts-grid">
          <div className="glass-card chart-card">
            <div className="chart-card__header">
              <div><div className="chart-card__title">User Activity</div><div className="chart-card__subtitle">Tasks, Offers & Engagement</div></div>
            </div>
            <div className="chart-wrapper chart-wrapper--tall">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={userList.slice(0,7)}>
                  <CartesianGrid strokeDasharray="3 3"/>
                  <XAxis dataKey="user_username"/>
                  <YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
                  <Bar dataKey="tasks_completed"  name="Tasks"      fill={colors[0]} radius={[3,3,0,0]}/>
                  <Bar dataKey="offers_completed" name="Offers"     fill={colors[1]} radius={[3,3,0,0]}/>
                  <Bar dataKey="engagement_score" name="Engagement" fill={colors[2]} radius={[3,3,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="glass-card chart-card">
            <div className="chart-card__header">
              <div><div className="chart-card__title">Retention Cohorts</div><div className="chart-card__subtitle">Day 1 → Day 30</div></div>
            </div>
            <div style={{overflowX:'auto',paddingBottom:4}}>
              <table className="retention-table">
                <thead>
                  <tr>
                    <th style={{textAlign:'left',paddingLeft:16}}>Cohort</th>
                    <th>D1</th><th>D3</th><th>D7</th><th>D14</th><th>D30</th>
                  </tr>
                </thead>
                <tbody>
                  {retention.slice(0,6).map((row,i) => (
                    <tr key={i}>
                      <td style={{fontFamily:'var(--font-mono)',fontSize:'0.75rem',color:'var(--text-muted)',paddingLeft:16}}>
                        {row.cohort_date_formatted||row.cohort_date||`Cohort ${i+1}`}
                      </td>
                      {[row.retention_day_1||0, row.retention_day_3||0, row.retention_day_7||0, row.retention_day_14||0, row.retention_day_30||0]
                        .map((v,j) => <td key={j}><RetentionCell value={parseFloat(v||0)}/></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ── Offer Performance ──────────────────────────────────────────── */}
        <div className="section-header"><h2 className="section-title">Offer Performance</h2></div>
        <div className="charts-grid-3">
          <div className="glass-card chart-card" style={{gridColumn:'span 2'}}>
            <div className="chart-card__header">
              <div><div className="chart-card__title">Top Offers by Completions</div><div className="chart-card__subtitle">Completions · CTR · ROI</div></div>
            </div>
            <div className="chart-wrapper chart-wrapper--tall">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={offerList.slice(0,6)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" horizontal={false}/>
                  <XAxis type="number"/>
                  <YAxis dataKey="offer_name" type="category" width={90}/>
                  <Tooltip content={<CustomTooltip/>}/><Legend/>
                  <Bar dataKey="completions"        name="Completions" fill={colors[0]} radius={[0,4,4,0]}/>
                  <Bar dataKey="click_through_rate" name="CTR %"       fill={colors[2]} radius={[0,4,4,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="glass-card chart-card">
            <div className="chart-card__header">
              <div><div className="chart-card__title">Conversion Funnel</div><div className="chart-card__subtitle">Offer completion flow</div></div>
            </div>
            <div className="funnel-container" style={{marginTop:8}}>
              {funnelList.map((step,i) => (
                <div key={i} className="funnel-step">
                  <div className="funnel-step__label">
                    <span className="funnel-step__name">{step.name||step.funnel_type_display||'—'}</span>
                    <span className="funnel-step__count">{(step.total_entered||0).toLocaleString()}</span>
                    <span className="funnel-step__pct">{parseFloat(step.conversion_rate||0).toFixed(1)}%</span>
                  </div>
                  <div className="funnel-bar">
                    <div className="funnel-bar__fill" style={{width:`${Math.min(100,parseFloat(step.conversion_rate||0))}%`}}/>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Bottom Row ─────────────────────────────────────────────────── */}
        <div className="charts-grid">
          {/* Top Earners table */}
          <div className="glass-card table-card">
            <div className="table-card__header">
              <div><div className="chart-card__title">Top Earners</div><div className="chart-card__subtitle">Leaderboard · {period}</div></div>
            </div>
            <table className="analytics-table">
              <thead><tr><th>#</th><th>User</th><th>Earnings</th><th>Tasks</th><th>Engagement</th><th>Churn Risk</th></tr></thead>
              <tbody>
                {userList.slice(0,5).map((u,i) => (
                  <tr key={u.id||i}>
                    <td style={{fontFamily:'var(--font-mono)',color:'var(--text-muted)'}}>{i===0?'🥇':i===1?'🥈':i===2?'🥉':i+1}</td>
                    <td style={{fontFamily:'var(--font-mono)',fontWeight:600}}>@{u.user_username||u.username||'—'}</td>
                    <td style={{color:'var(--accent-2)',fontWeight:600}}>{fmtCurrency(u.earnings_total)}</td>
                    <td>{u.tasks_completed||0}</td>
                    <td><span className={`badge ${(u.engagement_score||0)>=90?'badge--success':'badge--info'}`}>{parseFloat(u.engagement_score||0).toFixed(0)}/100</span></td>
                    <td><span className={`badge ${(u.churn_risk_score||0)<0.05?'badge--success':(u.churn_risk_score||0)<0.15?'badge--warn':'badge--danger'}`}>{((u.churn_risk_score||0)*100).toFixed(0)}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Active Alerts with Resolve action */}
          <div className="glass-card" style={{display:'flex',flexDirection:'column'}}>
            <div className="table-card__header">
              <div>
                <div className="chart-card__title">Active Alerts</div>
                <div className="chart-card__subtitle">{alertList.length} unresolved</div>
              </div>
              <span className="badge badge--danger">{alertList.filter(a=>a.severity==='critical').length} Critical</span>
            </div>
            <div className="alerts-list">
              {alertList.slice(0,5).map((alert,i) => (
                <div key={alert.id||i} className="alert-item">
                  <div className={`alert-item__icon alert-item__icon--${alert.severity||'info'}`}>
                    {alert.severity==='critical'?'🚨':alert.severity==='warning'?'⚠️':'💡'}
                  </div>
                  <div className="alert-item__content">
                    <div className="alert-item__title">{alert.rule_name||alert.title||'—'}</div>
                    <div className="alert-item__desc">{alert.condition_met||alert.message||'—'}</div>
                  </div>
                  <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:4,flexShrink:0}}>
                    <div className="alert-item__time">{timeAgo(alert.triggered_at||alert.created_at)}</div>
                    {/* ✅ resolve action from AlertHistoryViewSet */}
                    {!alert.is_resolved && (
                      <button onClick={()=>setShowResolve(alert)}
                        style={{padding:'2px 8px',borderRadius:4,border:'1px solid rgba(52,211,153,.3)',background:'rgba(52,211,153,.06)',color:'#34d399',fontSize:'.62rem',cursor:'pointer'}}>
                        ✓ Resolve
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Reports Section with Generate + Download ───────────────────── */}
        <div className="section-header">
          <h2 className="section-title">Reports</h2>
          {/* ✅ generate action from ReportViewSet */}
          <button className="filter-btn" onClick={()=>setShowGenReport(true)}
            style={{background:'rgba(var(--accent-rgb),0.08)',border:'1px solid rgba(var(--accent-rgb),.3)'}}>
            ＋ Generate Report
          </button>
        </div>
        <div className="glass-card table-card">
          <table className="analytics-table">
            <thead><tr><th>Name</th><th>Type</th><th>Format</th><th>Status</th><th>Generated</th><th>Action</th></tr></thead>
            <tbody>
              {(reportList.length ? reportList : []).slice(0,6).map((r,i) => (
                <tr key={r.id||i}>
                  <td style={{fontWeight:600}}>{r.name||'—'}</td>
                  <td><span className="badge badge--info">{(r.report_type_display||r.report_type||'—').replace(/_/g,' ')}</span></td>
                  <td style={{fontFamily:'var(--font-mono)',fontSize:'.72rem',textTransform:'uppercase'}}>{r.format||'—'}</td>
                  <td><span className={`badge ${r.status==='completed'?'badge--success':r.status==='failed'?'badge--danger':'badge--warn'}`}>{r.status||'—'}</span></td>
                  <td style={{color:'var(--text-muted)',fontSize:'.72rem'}}>{timeAgo(r.generated_at)}</td>
                  <td>
                    {/* ✅ download action from ReportViewSet */}
                    {r.status==='completed' && (
                      <button onClick={()=>handleDownloadReport(r.id, r.name)}
                        style={{padding:'4px 10px',borderRadius:5,border:'1px solid rgba(var(--accent-rgb),.3)',background:'rgba(var(--accent-rgb),.06)',color:'var(--accent-2)',fontSize:'.68rem',cursor:'pointer'}}>
                        ⬇️ Download
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {reportList.length === 0 && (
                <tr><td colSpan={6} style={{textAlign:'center',color:'var(--text-muted)',padding:'24px',fontSize:'.8rem'}}>No reports yet — click "Generate Report" to create one</td></tr>
              )}
            </tbody>
          </table>
        </div>

      </div>{/* /analytics-container */}

      {/* ── Resolve Alert Modal ─────────────────────────────────────────── */}
      {showResolve && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(52,211,153,.3)',borderRadius:16,padding:28,width:'100%',maxWidth:420,boxShadow:'0 0 40px rgba(52,211,153,.1)'}}>
            <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'.9rem',fontWeight:800,color:'#e8e0ff',marginBottom:8}}>✓ Resolve Alert</div>
            <div style={{fontSize:'.8rem',color:'rgba(180,160,255,.7)',marginBottom:16}}>{showResolve.rule_name} — {showResolve.condition_met}</div>
            <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:'rgba(52,211,153,.7)',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>Resolution Notes</label>
            <textarea value={resolveNotes} onChange={e=>setResolveNotes(e.target.value)} rows={3}
              placeholder="Describe how this was resolved..."
              style={{width:'100%',padding:'9px 12px',background:'rgba(255,255,255,.03)',border:'1px solid rgba(52,211,153,.25)',borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box',resize:'vertical'}}
            />
            <div style={{display:'flex',gap:10,marginTop:16}}>
              <button onClick={()=>{setShowResolve(null);setResolveNotes('');}} style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>Cancel</button>
              <button onClick={()=>handleResolveAlert(showResolve.id)} style={{flex:2,padding:'10px',borderRadius:9,border:'none',background:'linear-gradient(135deg,#34d399bb,#34d399)',color:'#000',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',fontWeight:700,cursor:'pointer'}}>Mark Resolved</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Generate Report Modal ───────────────────────────────────────── */}
      {showGenReport && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(var(--accent-rgb,14,165,233),.35)',borderRadius:16,padding:28,width:'100%',maxWidth:480,boxShadow:'0 0 60px rgba(var(--accent-rgb,14,165,233),.1)'}}>
            <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff',marginBottom:20}}>📄 Generate Report</div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
              {[
                {name:'name',label:'Report Name',type:'text'},
                {name:'report_type',label:'Type',type:'select',opts:['daily_summary','weekly_analytics','monthly_earnings','user_activity','revenue_report','offer_performance','referral_report','custom']},
                {name:'format',label:'Format',type:'select',opts:['pdf','excel','csv','html','json']},
                {name:'status',label:'Status',type:'select',opts:['pending','processing','completed']},
              ].map(f => (
                <div key={f.name}>
                  <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:'rgba(14,165,233,.7)',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>{f.label}</label>
                  {f.type==='select'
                    ? <select value={genForm[f.name]||''} onChange={e=>setGenForm(p=>({...p,[f.name]:e.target.value}))} style={{width:'100%',padding:'9px 12px',background:'rgba(8,5,30,.95)',border:'1px solid rgba(14,165,233,.3)',borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box'}}>
                        {f.opts.map(o=><option key={o} value={o}>{o}</option>)}
                      </select>
                    : <input type="text" value={genForm[f.name]||''} onChange={e=>setGenForm(p=>({...p,[f.name]:e.target.value}))} placeholder={f.label}
                        style={{width:'100%',padding:'9px 12px',background:'rgba(255,255,255,.03)',border:'1px solid rgba(14,165,233,.3)',borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box'}}/>
                  }
                </div>
              ))}
            </div>
            <div style={{display:'flex',gap:10,marginTop:20}}>
              <button onClick={()=>setShowGenReport(false)} style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>Cancel</button>
              <button onClick={handleGenerateReport} style={{flex:2,padding:'10px',borderRadius:9,border:'none',background:'linear-gradient(135deg,rgba(14,165,233,.7),#0ea5e9)',color:'#000',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',fontWeight:700,cursor:'pointer'}}>Generate</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Export Modal ────────────────────────────────────────────────── */}
      {showExport && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(139,92,246,.35)',borderRadius:16,padding:28,width:'100%',maxWidth:480,boxShadow:'0 0 60px rgba(139,92,246,.1)'}}>
            <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff',marginBottom:20}}>📦 Export Analytics</div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
              {[
                {name:'start_date',label:'Start Date',type:'date'},
                {name:'end_date',label:'End Date',type:'date'},
                {name:'format',label:'Format',type:'select',opts:['csv','excel','json']},
                {name:'group_by',label:'Group By',type:'select',opts:['day','week','month']},
              ].map(f => (
                <div key={f.name}>
                  <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:'rgba(139,92,246,.7)',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>{f.label}</label>
                  {f.type==='select'
                    ? <select value={exportForm[f.name]||''} onChange={e=>setExportForm(p=>({...p,[f.name]:e.target.value}))} style={{width:'100%',padding:'9px 12px',background:'rgba(8,5,30,.95)',border:'1px solid rgba(139,92,246,.3)',borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box'}}>
                        {f.opts.map(o=><option key={o} value={o}>{o}</option>)}
                      </select>
                    : <input type={f.type} value={exportForm[f.name]||''} onChange={e=>setExportForm(p=>({...p,[f.name]:e.target.value}))}
                        style={{width:'100%',padding:'9px 12px',background:'rgba(255,255,255,.03)',border:'1px solid rgba(139,92,246,.3)',borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box'}}/>
                  }
                </div>
              ))}
            </div>
            <div style={{marginTop:12}}>
              <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:'rgba(139,92,246,.7)',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>Metrics</label>
              <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                {['all','user_activity','revenue','offer_performance','retention','funnel'].map(m => (
                  <button key={m} onClick={()=>{
                    if (m==='all') { setExportForm(p=>({...p,metrics:['all']})); return; }
                    setExportForm(p => {
                      const cur = p.metrics.filter(x=>x!=='all');
                      return {...p, metrics: cur.includes(m) ? cur.filter(x=>x!==m) : [...cur,m]};
                    });
                  }} style={{padding:'4px 10px',borderRadius:5,fontSize:'.68rem',fontFamily:'monospace',cursor:'pointer',
                    background:exportForm.metrics.includes(m)?'rgba(139,92,246,.15)':'transparent',
                    border:`1px solid rgba(139,92,246,${exportForm.metrics.includes(m)?'.5':'.2'})`,
                    color:exportForm.metrics.includes(m)?'#a78bfa':'rgba(180,160,255,.4)'}}>
                    {m}
                  </button>
                ))}
              </div>
            </div>
            <div style={{display:'flex',gap:10,marginTop:20}}>
              <button onClick={()=>setShowExport(false)} style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>Cancel</button>
              <button onClick={handleExport} style={{flex:2,padding:'10px',borderRadius:9,border:'none',background:'linear-gradient(135deg,rgba(139,92,246,.7),#8b5cf6)',color:'#fff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',fontWeight:700,cursor:'pointer'}}>Export Data</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// CRUD MANAGEMENT — all 10 modules
// ═════════════════════════════════════════════════════════════════════════════

const CRUD_SECTIONS = [
  {
    key:'events', label:'Analytics Events', icon:'⚡', color:'#00f3ff',
    endpoint:'/api/analytics/events/',
    // AnalyticsEventSerializer exact fields
    columns:['event_type','user_username','ip_address','device_type','country','value','formatted_time'],
    // extra actions from AnalyticsEventViewSet
    extraActions:[
      {label:'Event Types',  endpoint:'/api/analytics/events/event_types/', method:'GET'},
    ],
    fields:[
      {name:'event_type', label:'Event Type', type:'select', options:['user_signup','user_login','task_completed','offer_viewed','offer_completed','withdrawal_requested','withdrawal_processed','referral_joined','wallet_deposit','wallet_withdrawal','page_view','button_click','api_call','error_occurred','notification_sent','email_opened','push_received']},
      {name:'ip_address',  label:'IP Address',  type:'text'},
      {name:'device_type', label:'Device',      type:'select', options:['desktop','mobile','tablet']},
      {name:'country',     label:'Country',     type:'text'},
      {name:'city',        label:'City',        type:'text'},
      {name:'value',       label:'Value ($)',   type:'number'},
      {name:'duration',    label:'Duration (s)',type:'number'},
      {name:'session_id',  label:'Session ID',  type:'text'},
    ],
  },
  {
    key:'user-analytics', label:'User Analytics', icon:'👤', color:'#b44fff',
    endpoint:'/api/analytics/user-analytics/',
    // UserAnalyticsSerializer exact fields
    columns:['user_username','period','login_count','tasks_completed','offers_completed','earnings_total','engagement_score'],
    extraActions:[
      {label:'Leaderboard',    endpoint:'/api/analytics/user-analytics/leaderboard/',     method:'GET'},
      {label:'Retention Curve',endpoint:'/api/analytics/user-analytics/retention_curve/', method:'GET'},
      {label:'My Analytics',   endpoint:'/api/analytics/user-analytics/my_analytics/',    method:'GET'},
    ],
    fields:[
      {name:'period',                  label:'Period',              type:'select', options:['daily','weekly','monthly','yearly']},
      {name:'login_count',             label:'Login Count',         type:'number'},
      {name:'active_days',             label:'Active Days',         type:'number'},
      {name:'tasks_completed',         label:'Tasks Done',          type:'number'},
      {name:'tasks_attempted',         label:'Tasks Attempted',     type:'number'},
      {name:'offers_viewed',           label:'Offers Viewed',       type:'number'},
      {name:'offers_completed',        label:'Offers Completed',    type:'number'},
      {name:'earnings_total',          label:'Total Earnings ($)',  type:'number'},
      {name:'earnings_from_tasks',     label:'Task Earnings ($)',   type:'number'},
      {name:'earnings_from_offers',    label:'Offer Earnings ($)',  type:'number'},
      {name:'earnings_from_referrals', label:'Referral Earn ($)',   type:'number'},
      {name:'referrals_sent',          label:'Referrals Sent',      type:'number'},
      {name:'referrals_joined',        label:'Referrals Joined',    type:'number'},
      {name:'withdrawals_requested',   label:'Withdrawal Requests', type:'number'},
      {name:'withdrawals_amount',      label:'Withdrawal Amt ($)',  type:'number'},
      {name:'churn_risk_score',        label:'Churn Risk (0-1)',    type:'number'},
      {name:'is_retained',             label:'Is Retained',         type:'select', options:['true','false']},
    ],
  },
  {
    key:'revenue-analytics', label:'Revenue Analytics', icon:'💰', color:'#ffd700',
    endpoint:'/api/analytics/revenue-analytics/',
    // RevenueAnalyticsSerializer exact fields
    columns:['period','period_start_date','revenue_total','cost_total','gross_profit','net_profit','profit_margin'],
    extraActions:[
      {label:'Summary',  endpoint:'/api/analytics/revenue-analytics/summary/',  method:'GET'},
      {label:'Sources',  endpoint:'/api/analytics/revenue-analytics/sources/',  method:'GET'},
      {label:'Forecast', endpoint:'/api/analytics/revenue-analytics/forecast/', method:'GET'},
    ],
    fields:[
      {name:'period',              label:'Period',              type:'select', options:['daily','weekly','monthly','yearly']},
      {name:'revenue_total',       label:'Total Revenue ($)',   type:'number'},
      {name:'cost_total',          label:'Total Cost ($)',      type:'number'},
      {name:'gross_profit',        label:'Gross Profit ($)',    type:'number'},
      {name:'active_users',        label:'Active Users',        type:'number'},
      {name:'paying_users',        label:'Paying Users',        type:'number'},
      {name:'total_withdrawals',   label:'Total Withdrawals ($)',type:'number'},
      {name:'withdrawal_requests', label:'Withdrawal Requests', type:'number'},
      {name:'platform_fee_earned', label:'Platform Fee ($)',    type:'number'},
      {name:'tax_deducted',        label:'Tax Deducted ($)',    type:'number'},
    ],
  },
  {
    key:'offer-performance', label:'Offer Performance', icon:'🎯', color:'#ff8c00',
    endpoint:'/api/analytics/offer-performance/',
    // OfferPerformanceAnalyticsSerializer exact fields
    columns:['offer_name','period','impressions','completions','completion_rate','roi','revenue_generated'],
    extraActions:[
      {label:'Top Performing', endpoint:'/api/analytics/offer-performance/top_performing/', method:'GET'},
      {label:'Comparison',     endpoint:'/api/analytics/offer-performance/comparison/',     method:'GET'},
    ],
    fields:[
      {name:'period',              label:'Period',              type:'select', options:['daily','weekly','monthly','yearly']},
      {name:'impressions',         label:'Impressions',         type:'number'},
      {name:'unique_views',        label:'Unique Views',        type:'number'},
      {name:'clicks',              label:'Clicks',              type:'number'},
      {name:'completions',         label:'Completions',         type:'number'},
      {name:'completion_rate',     label:'Completion Rate %',   type:'number'},
      {name:'revenue_generated',   label:'Revenue ($)',         type:'number'},
      {name:'cost_per_completion', label:'Cost/Completion ($)', type:'number'},
      {name:'roi',                 label:'ROI %',               type:'number'},
      {name:'unique_users_completed',label:'Unique Users',      type:'number'},
      {name:'avg_completion_time', label:'Avg Time (sec)',       type:'number'},
    ],
  },
  {
    key:'funnel', label:'Funnel Analytics', icon:'🔻', color:'#00ff88',
    endpoint:'/api/analytics/funnel/',
    // FunnelAnalyticsSerializer exact fields
    columns:['funnel_type_display','period','total_entered','total_converted','conversion_rate','avg_time_to_convert'],
    extraActions:[
      {label:'By Type', endpoint:'/api/analytics/funnel/by_type/?funnel_type=offer_completion', method:'GET'},
    ],
    fields:[
      {name:'funnel_type',            label:'Funnel Type',   type:'select', options:['user_signup','offer_completion','withdrawal','referral','premium_upgrade']},
      {name:'period',                 label:'Period',        type:'select', options:['daily','weekly','monthly','yearly']},
      {name:'total_entered',          label:'Total Entered', type:'number'},
      {name:'total_converted',        label:'Total Converted',type:'number'},
      {name:'conversion_rate',        label:'Conv. Rate %',  type:'number'},
      {name:'avg_time_to_convert',    label:'Avg Time (sec)',type:'number'},
      {name:'median_time_to_convert', label:'Median Time',   type:'number'},
    ],
  },
  {
    key:'retention', label:'Retention Analytics', icon:'🔄', color:'#ff2d78',
    endpoint:'/api/analytics/retention/',
    // RetentionAnalyticsSerializer exact fields
    columns:['cohort_type','cohort_date_formatted','total_users','retention_day_1','retention_day_7','retention_day_30','churn_rate'],
    extraActions:[
      {label:'Summary', endpoint:'/api/analytics/retention/summary/', method:'GET'},
    ],
    fields:[
      {name:'cohort_type',     label:'Cohort Type',   type:'select', options:['daily','weekly','monthly']},
      {name:'cohort_date',     label:'Cohort Date',   type:'date'},
      {name:'total_users',     label:'Total Users',   type:'number'},
      {name:'retention_day_1', label:'Day 1 %',       type:'number'},
      {name:'retention_day_3', label:'Day 3 %',       type:'number'},
      {name:'retention_day_7', label:'Day 7 %',       type:'number'},
      {name:'retention_day_14',label:'Day 14 %',      type:'number'},
      {name:'retention_day_30',label:'Day 30 %',      type:'number'},
      {name:'retention_day_60',label:'Day 60 %',      type:'number'},
      {name:'retention_day_90',label:'Day 90 %',      type:'number'},
      {name:'churned_users',   label:'Churned Users', type:'number'},
      {name:'churn_rate',      label:'Churn Rate %',  type:'number'},
      {name:'ltv',             label:'LTV ($)',        type:'number'},
    ],
  },
  {
    key:'dashboards', label:'Dashboards', icon:'📊', color:'#4d79ff',
    endpoint:'/api/analytics/dashboards/',
    // DashboardSerializer exact fields
    columns:['name','dashboard_type_display','is_public','refresh_interval','created_by_username','created_at_formatted'],
    extraActions:[
      // dashboard clone action — handled per-row
    ],
    fields:[
      {name:'name',              label:'Name',          type:'text'},
      {name:'dashboard_type',    label:'Type',          type:'select', options:['admin','user','realtime','financial','marketing']},
      {name:'description',       label:'Description',   type:'text'},
      {name:'is_public',         label:'Public',        type:'select', options:['true','false']},
      {name:'refresh_interval',  label:'Refresh (sec)', type:'number'},
      {name:'default_time_range',label:'Default Range', type:'select', options:['last_7_days','last_30_days','last_90_days','this_month','this_year']},
    ],
    rowActions:[
      {label:'Clone', icon:'📋', action:'clone', endpoint:(id)=>`/api/analytics/dashboards/${id}/clone/`, method:'POST', color:'#4d79ff'},
    ],
  },
  {
    key:'reports', label:'Reports', icon:'📄', color:'#00f3ff',
    endpoint:'/api/analytics/reports/',
    // ReportSerializer exact fields
    columns:['name','report_type_display','format','status','generated_by_username','generated_at_formatted'],
    extraActions:[
      {label:'Generate', endpoint:'/api/analytics/reports/generate/', method:'POST', payload:{name:'Quick Report',report_type:'daily_summary',format:'json'}},
    ],
    fields:[
      {name:'name',        label:'Report Name', type:'text'},
      {name:'report_type', label:'Type',        type:'select', options:['daily_summary','weekly_analytics','monthly_earnings','user_activity','revenue_report','offer_performance','referral_report','custom']},
      {name:'format',      label:'Format',      type:'select', options:['pdf','excel','csv','html','json']},
      {name:'status',      label:'Status',      type:'select', options:['pending','processing','completed','failed']},
    ],
    rowActions:[
      {label:'Download', icon:'⬇️', action:'download', endpoint:(id)=>`/api/analytics/reports/${id}/download/`, method:'GET', color:'#00f3ff', condition:(row)=>row.status==='completed'},
    ],
  },
  {
    key:'alert-rules', label:'Alert Rules', icon:'🔔', color:'#ffd700',
    endpoint:'/api/analytics/alert-rules/',
    // AlertRuleSerializer exact fields
    columns:['name','metric_type_display','condition_display','threshold_value','severity','is_active'],
    fields:[
      {name:'name',            label:'Rule Name',    type:'text'},
      {name:'description',     label:'Description',  type:'text'},
      {name:'alert_type',      label:'Alert Type',   type:'select', options:['threshold','anomaly','pattern']},
      {name:'metric_type',     label:'Metric',       type:'select', options:['active_users','concurrent_tasks','revenue_per_minute','api_requests','error_rate','response_time','queue_size','server_load']},
      {name:'condition',       label:'Condition',    type:'select', options:['greater_than','less_than','equal_to','not_equal','in_range','out_of_range']},
      {name:'threshold_value', label:'Threshold',    type:'number'},
      {name:'time_window',     label:'Window (sec)', type:'number'},
      {name:'severity',        label:'Severity',     type:'select', options:['info','warning','error','critical']},
      {name:'is_active',       label:'Active',       type:'select', options:['true','false']},
      {name:'notify_email',    label:'Email Notify', type:'select', options:['true','false']},
      {name:'notify_slack',    label:'Slack Notify', type:'select', options:['true','false']},
      {name:'cooldown_period', label:'Cooldown (sec)',type:'number'},
    ],
    // toggle action from AlertRuleViewSet
    rowActions:[
      {label:'Toggle', icon:'⚡', action:'toggle', endpoint:(id)=>`/api/analytics/alert-rules/${id}/toggle/`, method:'POST', color:'#ffd700'},
    ],
  },
  {
    key:'alerts', label:'Alert History', icon:'🚨', color:'#ff2d78',
    endpoint:'/api/analytics/alerts/',
    // AlertHistorySerializer exact fields
    columns:['rule_name','severity_display','metric_value','is_resolved','triggered_at_formatted','resolved_at_formatted'],
    extraActions:[
      {label:'Unresolved', endpoint:'/api/analytics/alerts/unresolved/', method:'GET'},
    ],
    fields:[
      {name:'metric_value',     label:'Metric Value', type:'number'},
      {name:'is_resolved',      label:'Resolved',     type:'select', options:['true','false']},
      {name:'resolution_notes', label:'Notes',        type:'text'},
    ],
    // resolve action from AlertHistoryViewSet
    rowActions:[
      {label:'Resolve', icon:'✓', action:'resolve', endpoint:(id)=>`/api/analytics/alerts/${id}/resolve/`, method:'POST', color:'#34d399', condition:(row)=>!row.is_resolved},
    ],
  },
];

// Cell formatter
function cFmtCell(val, col) {
  if (val === null || val === undefined) return React.createElement('span',{style:{color:'rgba(180,160,255,.3)'}},'—');
  if (typeof val==='boolean' || val==='true' || val==='false') {
    const t = val===true||val==='true';
    return React.createElement('span',{style:{padding:'2px 8px',borderRadius:4,background:t?'rgba(0,255,136,.1)':'rgba(255,45,120,.1)',color:t?'#00ff88':'#ff2d78',fontSize:'.64rem',fontFamily:'monospace',border:`1px solid ${t?'rgba(0,255,136,.25)':'rgba(255,45,120,.25)'}`}},t?'✓ Yes':'✗ No');
  }
  if (col?.includes('_at')||col?.includes('date')||col?.includes('time')||col?.endsWith('_formatted')) {
    if (!val||val==='—') return React.createElement('span',{style:{color:'rgba(180,160,255,.3)'}},'—');
    try { return React.createElement('span',{style:{fontFamily:'monospace',fontSize:'.7rem',color:'rgba(180,160,255,.6)'}},new Date(val).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})); }
    catch { return React.createElement('span',{style:{fontFamily:'monospace',fontSize:'.7rem',color:'rgba(180,160,255,.6)'}},String(val)); }
  }
  const BADGE_COLORS={
    daily:'#00f3ff',weekly:'#b44fff',monthly:'#ffd700',yearly:'#ff8c00',
    desktop:'#00f3ff',mobile:'#00ff88',tablet:'#b44fff',
    admin:'#b44fff',user:'#00f3ff',realtime:'#00ff88',financial:'#ffd700',marketing:'#ff8c00',
    completed:'#00ff88',pending:'#ffd700',processing:'#00f3ff',failed:'#ff2d78',
    pdf:'#ff2d78',excel:'#00ff88',csv:'#ffd700',html:'#00f3ff',json:'#b44fff',
    info:'#00f3ff',warning:'#ffd700',error:'#ff8c00',critical:'#ff2d78',
    user_signup:'#00ff88',user_login:'#00f3ff',task_completed:'#ffd700',offer_completed:'#ff8c00',
    threshold:'#ffd700',anomaly:'#ff8c00',pattern:'#b44fff',
    low:'#00ff88',medium:'#ffd700',high:'#ff8c00',elite:'#ff2d78',
  };
  if (['period','event_type','device_type','report_type','dashboard_type','status','metric_type','alert_type','severity','format','cohort_type'].includes(col)||col?.endsWith('_display')) {
    const c=BADGE_COLORS[val]||'#b44fff';
    return React.createElement('span',{style:{padding:'2px 9px',borderRadius:4,background:`${c}18`,color:c,border:`1px solid ${c}30`,fontSize:'.63rem',fontFamily:'monospace'}},val);
  }
  if (col?.includes('revenue')||col?.includes('earning')||col?.includes('profit')||col?.includes('ltv')||col?.includes('amount')||col?.includes('withdrawal')||col?.includes('fee')) {
    return React.createElement('span',{style:{color:'#ffd700',fontFamily:'monospace',fontSize:'.75rem'}},`$${parseFloat(val||0).toFixed(2)}`);
  }
  if (col?.includes('rate')||col?.includes('retention_day')||col?.includes('margin')||col?.includes('churn')||col?.includes('roi')||col?.includes('conversion')) {
    return React.createElement('span',{style:{color:'#00ff88',fontFamily:'monospace',fontSize:'.75rem'}},`${parseFloat(val||0).toFixed(1)}%`);
  }
  const s=String(val);
  return React.createElement('span',{style:{fontSize:'.78rem'}},s.length>35?s.slice(0,35)+'…':s);
}

// Extra Action Results Modal
function ActionResultModal({ result, title, onClose }) {
  return (
    <div style={{position:'fixed',inset:0,zIndex:1100,background:'rgba(0,0,0,.85)',backdropFilter:'blur(12px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
      <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(0,243,255,.3)',borderRadius:16,padding:24,width:'100%',maxWidth:680,maxHeight:'80vh',overflowY:'auto',boxShadow:'0 0 60px rgba(0,243,255,.1)'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
          <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'.85rem',fontWeight:800,color:'#e8e0ff'}}>{title}</div>
          <button onClick={onClose} style={{background:'transparent',border:'none',color:'rgba(180,160,255,.5)',cursor:'pointer',fontSize:'1.2rem'}}>✕</button>
        </div>
        <pre style={{fontFamily:'monospace',fontSize:'.72rem',color:'rgba(180,160,255,.8)',whiteSpace:'pre-wrap',wordBreak:'break-all',background:'rgba(0,0,0,.3)',padding:16,borderRadius:8,border:'1px solid rgba(100,60,220,.15)'}}>
          {JSON.stringify(result, null, 2)}
        </pre>
      </div>
    </div>
  );
}

// CRUD Table component
function CrudTable({ section, onToast }) {
  const [rows,      setRows]     = useState([]);
  const [loading,   setLoading]  = useState(true);
  const [showForm,  setShowForm] = useState(false);
  const [editRow,   setEditRow]  = useState(null);
  const [delRow,    setDelRow]   = useState(null);
  const [detRow,    setDetRow]   = useState(null);
  const [form,      setForm]     = useState({});
  const [saving,    setSaving]   = useState(false);
  const [search,    setSearch]   = useState('');
  const [page,      setPage]     = useState(1);
  const [errMsg,    setErrMsg]   = useState('');
  const [actionRes, setActionRes]= useState(null);
  const [actionTitle,setActionTitle]=useState('');
  const PG = 10;

  const load = useCallback(async () => {
    setLoading(true);
    const { ok, data } = await crudFetch(`${section.endpoint}?ordering=-id&page_size=100`);
    if (ok && data) setRows(Array.isArray(data)?data:(data?.results||[]));
    setLoading(false);
  }, [section.endpoint]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true); setErrMsg('');
    const payload = { ...form };
    Object.keys(payload).forEach(k => {
      if (payload[k]==='true')  payload[k]=true;
      if (payload[k]==='false') payload[k]=false;
      if (payload[k]==='')      delete payload[k];
    });
    const url = editRow ? `${section.endpoint}${editRow.id}/` : section.endpoint;
    const { ok, data } = await crudFetch(url, { method:editRow?'PUT':'POST', body:JSON.stringify(payload) });
    setSaving(false);
    if (ok) { onToast(`✅ ${editRow?'Updated':'Created'} successfully!`,'success'); setShowForm(false); load(); }
    else {
      const msg = data ? (typeof data==='string'?data:Object.entries(data).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(', '):v}`).join(' | ')) : 'Save failed.';
      setErrMsg(msg);
    }
  };

  const handleDelete = async () => {
    const { ok } = await crudFetch(`${section.endpoint}${delRow.id}/`,{method:'DELETE'});
    setDelRow(null);
    if (ok) { onToast('🗑️ Deleted!','success'); load(); }
    else onToast('❌ Delete failed.','error');
  };

  const handleExtraAction = async (action) => {
    const { ok, data } = await crudFetch(action.endpoint, {
      method: action.method,
      body: action.payload ? JSON.stringify(action.payload) : undefined,
    });
    if (ok) { setActionTitle(action.label); setActionRes(data); }
    else onToast(`❌ ${action.label} failed`,'error');
  };

  const handleRowAction = async (rowAction, row) => {
    if (rowAction.condition && !rowAction.condition(row)) return;
    const url = rowAction.endpoint(row.id);
    const { ok, data } = await crudFetch(url, { method: rowAction.method });
    if (ok) {
      onToast(`✅ ${rowAction.label} done!`,'success');
      if (rowAction.action==='download' && data) {
        const blob = new Blob([JSON.stringify(data)],{type:'application/json'});
        const a = document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`${row.name||row.id}.json`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
      } else { setActionTitle(rowAction.label); setActionRes(data); }
      load();
    } else onToast(`❌ ${rowAction.label} failed`,'error');
  };

  const filtered  = rows.filter(r=>!search||JSON.stringify(r).toLowerCase().includes(search.toLowerCase()));
  const paginated = filtered.slice((page-1)*PG,page*PG);
  const totalPages= Math.ceil(filtered.length/PG);
  const C = section.color;
  const inputStyle = {width:'100%',padding:'9px 12px',background:'rgba(255,255,255,.03)',border:`1px solid ${C}30`,borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none',boxSizing:'border-box'};

  return (
    <>
    {actionRes && <ActionResultModal result={actionRes} title={actionTitle} onClose={()=>setActionRes(null)}/>}

    <div style={{background:'rgba(6,4,22,.9)',border:`1px solid ${C}25`,borderRadius:14,overflow:'hidden',boxShadow:`0 0 40px ${C}08,0 8px 32px rgba(0,0,0,.5)`,position:'relative'}}>
      <div style={{position:'absolute',top:0,left:0,right:0,height:2,background:`linear-gradient(90deg,transparent,${C},transparent)`}}/>

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px 20px',borderBottom:`1px solid ${C}15`,background:`${C}04`,flexWrap:'wrap',gap:10}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <span style={{fontSize:'1.1rem'}}>{section.icon}</span>
          <span style={{fontFamily:"'Orbitron',sans-serif",fontSize:'.72rem',fontWeight:800,letterSpacing:'.12em',color:'#e8e0ff'}}>{section.label}</span>
          <span style={{padding:'3px 10px',borderRadius:50,background:`${C}12`,color:C,border:`1px solid ${C}25`,fontFamily:'monospace',fontSize:'.62rem'}}>{filtered.length} records</span>
        </div>
        <div style={{display:'flex',gap:6,alignItems:'center',flexWrap:'wrap'}}>
          {/* Extra actions from ViewSet */}
          {section.extraActions?.map(a => (
            <button key={a.label} onClick={()=>handleExtraAction(a)}
              style={{padding:'6px 12px',borderRadius:7,border:`1px solid ${C}30`,background:`${C}08`,color:C,cursor:'pointer',fontFamily:'monospace',fontSize:'.62rem',letterSpacing:'.05em'}}>
              ⚡ {a.label}
            </button>
          ))}
          <input placeholder="🔍 Search..." value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}
            style={{padding:'7px 12px',background:'rgba(255,255,255,.04)',border:`1px solid ${C}20`,borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.75rem',outline:'none',width:150}}/>
          <button onClick={load} style={{padding:'8px 12px',borderRadius:8,border:`1px solid ${C}30`,background:'transparent',color:C,cursor:'pointer',fontSize:'.75rem'}}>⟳</button>
          <button onClick={()=>{setEditRow(null);setForm({});setErrMsg('');setShowForm(true);}}
            style={{padding:'8px 16px',borderRadius:8,border:`1px solid ${C}`,background:`${C}12`,color:C,fontFamily:"'Orbitron',sans-serif",fontSize:'.62rem',fontWeight:700,cursor:'pointer',letterSpacing:'.08em',boxShadow:`0 0 12px ${C}20`}}>
            + Add New
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{padding:48,textAlign:'center',color:'rgba(180,160,255,.3)',fontFamily:'monospace',fontSize:'.75rem',letterSpacing:'.1em'}}>⟳ Loading...</div>
      ) : paginated.length===0 ? (
        <div style={{padding:56,textAlign:'center'}}>
          <div style={{fontSize:'2rem',marginBottom:10,opacity:.3}}>{section.icon}</div>
          <div style={{color:'rgba(180,160,255,.3)',fontFamily:'monospace',fontSize:'.75rem',letterSpacing:'.08em'}}>{search?'No results found':`No ${section.label} yet`}</div>
          {!search&&<div style={{color:'rgba(180,160,255,.2)',fontSize:'.68rem',marginTop:6}}>Click "+ Add New" to create the first record</div>}
        </div>
      ) : (
        <div style={{overflowX:'auto'}}>
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead>
              <tr style={{background:'rgba(0,0,0,.2)'}}>
                <th style={{padding:'10px 16px',textAlign:'left',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.12em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`,whiteSpace:'nowrap'}}>#</th>
                {section.columns.map(col => (
                  <th key={col} style={{padding:'10px 14px',textAlign:'left',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.1em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`,whiteSpace:'nowrap'}}>
                    {col.replace(/_display$/,'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
                  </th>
                ))}
                <th style={{padding:'10px 14px',textAlign:'right',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.1em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`,whiteSpace:'nowrap'}}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((row,i) => (
                <tr key={row.id||i}
                  onMouseEnter={e=>e.currentTarget.style.background=`${C}05`}
                  onMouseLeave={e=>e.currentTarget.style.background='transparent'}
                  style={{transition:'background .15s'}}>
                  <td style={{padding:'11px 16px',color:'rgba(180,160,255,.25)',fontFamily:'monospace',fontSize:'.65rem',borderBottom:`1px solid rgba(100,60,220,.05)`}}>{(page-1)*PG+i+1}</td>
                  {section.columns.map(col => (
                    <td key={col} style={{padding:'11px 14px',borderBottom:`1px solid rgba(100,60,220,.05)`,verticalAlign:'middle'}}>
                      {cFmtCell(row[col],col)}
                    </td>
                  ))}
                  <td style={{padding:'11px 14px',textAlign:'right',borderBottom:`1px solid rgba(100,60,220,.05)`}}>
                    <div style={{display:'flex',gap:4,justifyContent:'flex-end',flexWrap:'wrap'}}>
                      {/* Row-level special actions */}
                      {section.rowActions?.map(ra => {
                        const disabled = ra.condition && !ra.condition(row);
                        return !disabled && (
                          <button key={ra.action} onClick={()=>handleRowAction(ra,row)}
                            style={{padding:'5px 10px',borderRadius:6,border:`1px solid ${ra.color}30`,background:`${ra.color}06`,color:ra.color,fontSize:'.7rem',cursor:'pointer'}}>
                            {ra.icon} {ra.label}
                          </button>
                        );
                      })}
                      <button onClick={()=>setDetRow(row)} style={{padding:'5px 10px',borderRadius:6,border:'1px solid rgba(180,160,255,.2)',background:'rgba(180,160,255,.05)',color:'rgba(180,160,255,.6)',fontSize:'.7rem',cursor:'pointer'}}>👁️</button>
                      <button onClick={()=>{setEditRow(row);setForm({...row});setErrMsg('');setShowForm(true);}} style={{padding:'5px 10px',borderRadius:6,border:'1px solid rgba(0,243,255,.3)',background:'rgba(0,243,255,.06)',color:'#00f3ff',fontSize:'.7rem',cursor:'pointer'}}>✏️</button>
                      <button onClick={()=>setDelRow(row)} style={{padding:'5px 10px',borderRadius:6,border:'1px solid rgba(255,45,120,.3)',background:'rgba(255,45,120,.06)',color:'#ff2d78',fontSize:'.7rem',cursor:'pointer'}}>🗑️</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages>1 && (
        <div style={{display:'flex',alignItems:'center',justifyContent:'flex-end',gap:6,padding:'12px 18px',borderTop:`1px solid ${C}10`}}>
          <span style={{fontFamily:'monospace',fontSize:'.62rem',color:'rgba(180,160,255,.35)',marginRight:8}}>{(page-1)*PG+1}–{Math.min(page*PG,filtered.length)} of {filtered.length}</span>
          <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1} style={{width:28,height:28,borderRadius:6,border:`1px solid ${C}25`,background:'transparent',color:page===1?'rgba(180,160,255,.2)':C,cursor:page===1?'default':'pointer',fontSize:'.8rem'}}>‹</button>
          {Array.from({length:Math.min(totalPages,6)},(_,i)=>i+1).map(p=>(
            <button key={p} onClick={()=>setPage(p)} style={{width:28,height:28,borderRadius:6,border:`1px solid ${page===p?C:C+'25'}`,background:page===p?`${C}15`:'transparent',color:page===p?C:'rgba(180,160,255,.4)',fontFamily:'monospace',fontSize:'.68rem',cursor:'pointer'}}>{p}</button>
          ))}
          <button onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages} style={{width:28,height:28,borderRadius:6,border:`1px solid ${C}25`,background:'transparent',color:page===totalPages?'rgba(180,160,255,.2)':C,cursor:page===totalPages?'default':'pointer',fontSize:'.8rem'}}>›</button>
        </div>
      )}

      {/* Detail Modal */}
      {detRow && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:`1px solid ${C}35`,borderRadius:16,padding:28,width:'100%',maxWidth:640,maxHeight:'85vh',overflowY:'auto',boxShadow:`0 0 60px ${C}15`}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}>
              <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'.9rem',fontWeight:800,color:'#e8e0ff'}}>{section.icon} Record Detail</div>
              <button onClick={()=>setDetRow(null)} style={{background:'transparent',border:'none',color:'rgba(180,160,255,.5)',cursor:'pointer',fontSize:'1.2rem'}}>✕</button>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:10}}>
              {Object.entries(detRow).filter(([k])=>!k.startsWith('_')).map(([k,v])=>(
                <div key={k} style={{padding:'8px 12px',background:'rgba(255,255,255,.02)',borderRadius:8,border:`1px solid ${C}15`}}>
                  <div style={{fontFamily:'monospace',fontSize:'.58rem',color:`${C}70`,letterSpacing:'.1em',textTransform:'uppercase',marginBottom:4}}>{k.replace(/_/g,' ')}</div>
                  <div style={{fontSize:'.78rem',color:'#e8e0ff',wordBreak:'break-all'}}>{cFmtCell(v,k)}</div>
                </div>
              ))}
            </div>
            <div style={{marginTop:16,display:'flex',justifyContent:'flex-end',gap:8}}>
              <button onClick={()=>{setDetRow(null);setEditRow(detRow);setForm({...detRow});setShowForm(true);}} style={{padding:'8px 20px',borderRadius:8,border:`1px solid ${C}`,background:`${C}12`,color:C,cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>✏️ Edit</button>
              <button onClick={()=>setDetRow(null)} style={{padding:'8px 20px',borderRadius:8,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showForm && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:`1px solid ${C}35`,borderRadius:16,padding:30,width:'100%',maxWidth:560,maxHeight:'85vh',overflowY:'auto',boxShadow:`0 0 60px ${C}15,0 40px 80px rgba(0,0,0,.7)`}}>
            <div style={{position:'relative',marginBottom:24}}>
              <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff'}}>{editRow?`✏️ Edit ${section.label}`:`➕ New ${section.label}`}</div>
              <div style={{position:'absolute',bottom:-8,left:0,right:0,height:1,background:`linear-gradient(90deg,${C},transparent)`}}/>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
              {section.fields.map(f => (
                <div key={f.name} style={f.name==='description'||f.name==='resolution_notes'||f.name==='notes'?{gridColumn:'span 2'}:{}}>
                  <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:`${C}90`,letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>{f.label}</label>
                  {f.type==='select'
                    ? <select value={form[f.name]??''} onChange={e=>setForm(p=>({...p,[f.name]:e.target.value}))} style={{...inputStyle,background:'rgba(8,5,30,.95)'}}>
                        <option value="">— Select —</option>
                        {f.options.map(o=><option key={o} value={o}>{o}</option>)}
                      </select>
                    : <input type={f.type||'text'} placeholder={f.label} value={form[f.name]??''} onChange={e=>setForm(p=>({...p,[f.name]:e.target.value}))} style={inputStyle}/>
                  }
                </div>
              ))}
            </div>
            {errMsg && <div style={{marginTop:12,padding:'8px 12px',borderRadius:8,background:'rgba(255,45,120,.08)',border:'1px solid rgba(255,45,120,.25)',color:'#ff2d78',fontFamily:'monospace',fontSize:'.72rem'}}>{errMsg}</div>}
            <div style={{display:'flex',gap:10,marginTop:24}}>
              <button onClick={()=>{setShowForm(false);setErrMsg('');}} style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',cursor:'pointer'}}>Cancel</button>
              <button onClick={handleSave} disabled={saving} style={{flex:2,padding:'10px',borderRadius:9,border:'none',background:`linear-gradient(135deg,${C}bb,${C})`,color:'#000',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',fontWeight:700,cursor:'pointer',boxShadow:`0 4px 20px ${C}40`,opacity:saving?.6:1}}>
                {saving?'Saving...':(editRow?'Update Record':'Create Record')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {delRow && (
        <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(255,45,120,.35)',borderRadius:16,padding:28,width:'100%',maxWidth:380,boxShadow:'0 0 40px rgba(255,45,120,.1)'}}>
            <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff',marginBottom:12}}>⚠️ Confirm Delete</div>
            <p style={{fontSize:'.82rem',color:'rgba(180,160,255,.7)',marginBottom:20,lineHeight:1.6}}>
              Delete record <strong style={{color:'#ff2d78'}}>#{String(delRow.id).slice(0,8)}</strong>? This cannot be undone.
            </p>
            <div style={{display:'flex',gap:10}}>
              <button onClick={()=>setDelRow(null)} style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer',fontFamily:"'Exo 2',sans-serif"}}>Cancel</button>
              <button onClick={handleDelete} style={{flex:1,padding:'10px',borderRadius:9,border:'none',background:'linear-gradient(135deg,#ff2d78bb,#ff2d78)',color:'#000',fontWeight:700,cursor:'pointer',fontFamily:"'Exo 2',sans-serif",boxShadow:'0 4px 20px rgba(255,45,120,.4)'}}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
    </>
  );
}

// Management page
function AnalyticsManagement() {
  const [active,  setActive] = useState('events');
  const [toast,   setToast]  = useState(null);
  const showToast = useCallback((msg,type)=>setToast({msg,type,key:Date.now()}),[]);
  const section = CRUD_SECTIONS.find(s=>s.key===active);

  return (
    <div style={{minHeight:'100vh',background:'#04020f',padding:'24px',fontFamily:"'Exo 2',sans-serif",color:'#e8e0ff'}}>
      {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={()=>setToast(null)}/>}
      <div style={{marginBottom:24}}>
        <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1.3rem',fontWeight:900,background:'linear-gradient(135deg,#00f3ff,#b44fff)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',letterSpacing:'.05em',marginBottom:4}}>
          ⚙️ Analytics Management
        </div>
        <div style={{fontSize:'.7rem',color:'rgba(180,160,255,.4)',fontFamily:'monospace',letterSpacing:'.1em'}}>
          FULL CRUD · {CRUD_SECTIONS.length} MODULES · SPECIAL ACTIONS · REAL API
        </div>
      </div>
      <div style={{display:'flex',gap:8,marginBottom:24,flexWrap:'wrap'}}>
        {CRUD_SECTIONS.map(s => (
          <button key={s.key} onClick={()=>setActive(s.key)}
            style={{padding:'8px 14px',borderRadius:9,border:`1px solid ${active===s.key?s.color:'rgba(100,60,220,.18)'}`,background:active===s.key?`${s.color}15`:'rgba(6,4,22,.8)',color:active===s.key?s.color:'rgba(180,160,255,.4)',fontFamily:"'Orbitron',sans-serif",fontSize:'.6rem',fontWeight:700,letterSpacing:'.08em',cursor:'pointer',transition:'all .2s',boxShadow:active===s.key?`0 0 16px ${s.color}20`:'none'}}>
            {s.icon} {s.label}
          </button>
        ))}
      </div>
      {section && <CrudTable key={active} section={section} onToast={showToast}/>}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// ROOT — Tab wrapper
// ═════════════════════════════════════════════════════════════════════════════
const AnalyticsWithManagement = () => {
  const [view, setView] = useState('dashboard');
  return (
    <div style={{minHeight:'100vh',background:'#04020f'}}>
      <div style={{display:'flex',gap:0,background:'rgba(6,4,22,.97)',borderBottom:'1px solid rgba(100,60,220,.2)',backdropFilter:'blur(20px)',position:'sticky',top:0,zIndex:200,padding:'0 20px'}}>
        {[
          {key:'dashboard',  label:'📊 Analytics Dashboard', color:'#00f3ff'},
          {key:'management', label:'⚙️ Management · CRUD',   color:'#b44fff'},
        ].map(t => (
          <button key={t.key} onClick={()=>setView(t.key)}
            style={{padding:'14px 22px',border:'none',borderBottom:`2px solid ${view===t.key?t.color:'transparent'}`,background:'transparent',color:view===t.key?t.color:'rgba(180,160,255,.4)',fontFamily:"'Orbitron',sans-serif",fontSize:'.65rem',fontWeight:700,letterSpacing:'.1em',cursor:'pointer',transition:'all .25s'}}>
            {t.label}
          </button>
        ))}
      </div>
      {view==='dashboard'  && <Analytics/>}
      {view==='management' && <AnalyticsManagement/>}
    </div>
  );
};

export default AnalyticsWithManagement;


// // src/pages/Analytics.jsx
// // Ultra Professional Analytics Dashboard
// // ✅ 100% REAL API — /api/analytics/ endpoints
// // Auto color theme change every 60 seconds — 6 themes total

// import React, { useState, useEffect, useCallback, useRef } from 'react';
// import {
//   LineChart, Line, AreaChart, Area, BarChart, Bar,
//   PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
//   Tooltip, Legend, ResponsiveContainer,
// } from 'recharts';
// import '../styles/Analytics.css';

// const BASE           = '/api/analytics';
// const THEME_COUNT    = 6;
// const THEME_INTERVAL = 60;
// const DATA_REFRESH   = 30;
// const THEME_NAMES = ['Deep Ocean','Emerald Forest','Violet Galaxy','Rose Gold','Amber Inferno','Cyan Neon'];

// const authHeaders = () => ({
//   'Authorization': `Bearer ${localStorage.getItem('adminAccessToken')||localStorage.getItem('access_token')||localStorage.getItem('auth_token')||''}`,
//   'Content-Type': 'application/json',
// });

// const API = {
//   summary:   (p) => fetch(`${BASE}/summary/?period=${p}`,                                          { headers: authHeaders() }),
//   realtime:  ()  => fetch(`${BASE}/realtime/metrics/`,                                             { headers: authHeaders() }),
//   users:     (p) => fetch(`${BASE}/user-analytics/?period=${p}&ordering=-earnings_total&page_size=10`, { headers: authHeaders() }),
//   revenue:   (p) => fetch(`${BASE}/revenue-analytics/?period=${p}&ordering=-period_start&page_size=12`, { headers: authHeaders() }),
//   offers:    (p) => fetch(`${BASE}/offer-performance/?period=${p}&ordering=-completions&page_size=10`, { headers: authHeaders() }),
//   funnel:    (p) => fetch(`${BASE}/funnel/?period=${p}`,                                           { headers: authHeaders() }),
//   retention: (p) => fetch(`${BASE}/retention/?period=${p}&page_size=6`,                           { headers: authHeaders() }),
//   alerts:    ()  => fetch(`${BASE}/alerts/?is_resolved=false&page_size=8`,                         { headers: authHeaders() }),
// };

// async function safeFetch(fn) {
//   try {
//     const res  = await fn();
//     const text = await res.text();
//     if (!res.ok) return null;
//     try { return JSON.parse(text); } catch { return null; }
//   } catch { return null; }
// }
// const extract    = (res) => { if (!res) return []; if (Array.isArray(res)) return res; if (Array.isArray(res.results)) return res.results; if (Array.isArray(res.data)) return res.data; return []; };
// const extractObj = (res, fb = {}) => { if (!res) return fb; if (res.data && typeof res.data==='object' && !Array.isArray(res.data)) return res.data; if (typeof res==='object' && !Array.isArray(res)) return res; return fb; };

// const FB_REVENUE = [
//   {period_start_date:'Jan',revenue_total:42000,cost_total:28000,gross_profit:14000,net_profit:12000},
//   {period_start_date:'Feb',revenue_total:51000,cost_total:31000,gross_profit:20000,net_profit:18000},
//   {period_start_date:'Mar',revenue_total:47000,cost_total:29000,gross_profit:18000,net_profit:16000},
//   {period_start_date:'Apr',revenue_total:63000,cost_total:35000,gross_profit:28000,net_profit:25000},
//   {period_start_date:'May',revenue_total:58000,cost_total:33000,gross_profit:25000,net_profit:22000},
//   {period_start_date:'Jun',revenue_total:72000,cost_total:38000,gross_profit:34000,net_profit:30000},
//   {period_start_date:'Jul',revenue_total:68000,cost_total:36000,gross_profit:32000,net_profit:28000},
//   {period_start_date:'Aug',revenue_total:81000,cost_total:42000,gross_profit:39000,net_profit:35000},
//   {period_start_date:'Sep',revenue_total:77000,cost_total:40000,gross_profit:37000,net_profit:33000},
//   {period_start_date:'Oct',revenue_total:93000,cost_total:47000,gross_profit:46000,net_profit:42000},
//   {period_start_date:'Nov',revenue_total:88000,cost_total:45000,gross_profit:43000,net_profit:39000},
//   {period_start_date:'Dec',revenue_total:105000,cost_total:52000,gross_profit:53000,net_profit:48000},
// ];
// const FB_USERS = [
//   {user_username:'alex_m',   earnings_total:'2840.00',tasks_completed:142,engagement_score:96,offers_completed:88,churn_risk_score:0.02},
//   {user_username:'priya_k',  earnings_total:'2420.00',tasks_completed:128,engagement_score:94,offers_completed:74,churn_risk_score:0.04},
//   {user_username:'omar_f',   earnings_total:'2180.00',tasks_completed:115,engagement_score:91,offers_completed:62,churn_risk_score:0.06},
//   {user_username:'yui_t',    earnings_total:'1960.00',tasks_completed:108,engagement_score:89,offers_completed:55,churn_risk_score:0.08},
//   {user_username:'fatima_r', earnings_total:'1740.00',tasks_completed:97, engagement_score:87,offers_completed:48,churn_risk_score:0.10},
// ];
// const FB_OFFERS = [
//   {offer_name:'Survey A',   completions:4200,click_through_rate:24.5,roi:185,revenue_generated:'8400.00',completion_rate:68},
//   {offer_name:'App Install',completions:3800,click_through_rate:18.2,roi:240,revenue_generated:'7600.00',completion_rate:62},
//   {offer_name:'Video Ad',   completions:5100,click_through_rate:31.7,roi:160,revenue_generated:'10200.00',completion_rate:74},
//   {offer_name:'Sign Up',    completions:2900,click_through_rate:22.1,roi:310,revenue_generated:'5800.00',completion_rate:58},
//   {offer_name:'Purchase',   completions:1800,click_through_rate:12.8,roi:420,revenue_generated:'3600.00',completion_rate:45},
// ];
// const FB_FUNNEL = [
//   {name:'Page Views',  entry_count:48200,conversion_rate:100 },
//   {name:'Offer Viewed',entry_count:31400,conversion_rate:65.1},
//   {name:'Click',       entry_count:18800,conversion_rate:39.0},
//   {name:'Started',     entry_count:9200, conversion_rate:19.1},
//   {name:'Completed',   entry_count:4100, conversion_rate:8.5 },
// ];
// const FB_RETENTION = [
//   {cohort_label:'Jan',day_1:95,day_3:82,day_7:68,day_14:54,day_30:42},
//   {cohort_label:'Feb',day_1:93,day_3:79,day_7:64,day_14:51,day_30:39},
//   {cohort_label:'Mar',day_1:96,day_3:85,day_7:71,day_14:58,day_30:46},
//   {cohort_label:'Apr',day_1:94,day_3:81,day_7:66,day_14:53,day_30:41},
//   {cohort_label:'May',day_1:97,day_3:87,day_7:73,day_14:60,day_30:48},
// ];
// const FB_ALERTS = [
//   {id:1,severity:'critical',title:'Revenue Drop Detected',message:'Daily revenue 23% below threshold',created_at:new Date(Date.now()-120000).toISOString()},
//   {id:2,severity:'warning', title:'High Churn Rate',      message:'Weekly churn exceeded 8% limit',  created_at:new Date(Date.now()-1080000).toISOString()},
//   {id:3,severity:'warning', title:'API Response Slow',    message:'Avg response 480ms > 300ms SLA',  created_at:new Date(Date.now()-2040000).toISOString()},
//   {id:4,severity:'info',    title:'New Cohort Report',    message:'May cohort data is ready',        created_at:new Date(Date.now()-3600000).toISOString()},
// ];
// const FB_REALTIME = [
//   {metric_name:'Active Users', metric_value:1842,unit:'',  threshold:2500,percentage:73},
//   {metric_name:'Req / sec',    metric_value:284, unit:'',  threshold:500, percentage:57},
//   {metric_name:'Error Rate',   metric_value:0.4, unit:'%', threshold:2,   percentage:4 },
//   {metric_name:'Avg Response', metric_value:148, unit:'ms',threshold:300, percentage:30},
// ];
// const FB_SUMMARY = {total_revenue:'847000.00',total_users:24800,active_users:18420,offer_completions:18420,avg_engagement:78.4,total_withdrawals:'312000.00',churn_rate:4.2,referrals_joined:3841,error_rate:0.4};
// const FB_REVENUE_SOURCE = [{name:'Offer Completion',value:42},{name:'Task Completion',value:28},{name:'Referrals',value:16},{name:'Subscriptions',value:10},{name:'Other',value:4}];

// const CustomTooltip = ({ active, payload, label }) => {
//   if (!active || !payload?.length) return null;
//   return (
//     <div className="custom-tooltip">
//       <p style={{marginBottom:6,fontWeight:600,color:'var(--text-primary)'}}>{label}</p>
//       {payload.map((p,i) => <p key={i} style={{color:p.color}}>{p.name}: <strong>{typeof p.value==='number'?p.value.toLocaleString():p.value}</strong></p>)}
//     </div>
//   );
// };

// const RetentionCell = ({ value }) => {
//   const alpha = (value||0)/100;
//   return <div className="retention-cell" style={{background:`rgba(var(--accent-rgb,14,165,233),${alpha*0.7+0.08})`,color:value>60?'var(--text-primary)':'var(--text-muted)'}}>{value}%</div>;
// };

// const KPICard = ({ label, value, unit, trend, trendUp, icon, delay=0 }) => (
//   <div className="glass-card kpi-card" style={{animationDelay:`${delay}s`}}>
//     <div className="kpi-card__icon">{icon}</div>
//     <div className="kpi-card__label">{label}</div>
//     <div className="kpi-card__value">{value}{unit&&<span>{unit}</span>}</div>
//     <span className={`kpi-card__trend ${trendUp?'up':'down'}`}>{trendUp?'▲':'▼'} {trend}</span>
//   </div>
// );

// const CountdownRing = ({ seconds, total }) => {
//   const r = 15.2, circumference = 2*Math.PI*r, offset = circumference-(seconds/total)*circumference;
//   return (
//     <div className="countdown-ring">
//       <svg viewBox="0 0 36 36">
//         <circle className="countdown-ring__track"    cx="18" cy="18" r={r}/>
//         <circle className="countdown-ring__progress" cx="18" cy="18" r={r} strokeDasharray={circumference} strokeDashoffset={offset}/>
//       </svg>
//       <div className="countdown-ring__text">{seconds}s</div>
//     </div>
//   );
// };

// const timeAgo = (d) => {
//   if (!d) return '—';
//   const diff = Math.floor((Date.now()-new Date(d))/1000);
//   if (diff<60) return `${diff}s ago`; if (diff<3600) return `${Math.floor(diff/60)}m ago`; return `${Math.floor(diff/3600)}h ago`;
// };
// const fmtCurrency = (v) => { if (v==null) return '—'; const n=parseFloat(v); if (isNaN(n)) return v; if (n>=1000000) return `$${(n/1000000).toFixed(1)}M`; if (n>=1000) return `$${(n/1000).toFixed(1)}K`; return `$${n.toFixed(2)}`; };

// const Analytics = () => {
//   const [theme,      setTheme]    = useState(0);
//   const [countdown,  setCountdown]= useState(THEME_INTERVAL);
//   const [dataTimer,  setDataTimer]= useState(DATA_REFRESH);
//   const [period,     setPeriod]   = useState('monthly');
//   const [chartType,  setChartType]= useState('area');
//   const [apiOnline,  setApiOnline]= useState(false);
//   const [summary,    setSummary]  = useState(FB_SUMMARY);
//   const [revenueList,setRevenue]  = useState(FB_REVENUE);
//   const [userList,   setUsers]    = useState(FB_USERS);
//   const [offerList,  setOffers]   = useState(FB_OFFERS);
//   const [funnelList, setFunnel]   = useState(FB_FUNNEL);
//   const [retention,  setRetention]= useState(FB_RETENTION);
//   const [alertList,  setAlerts]   = useState(FB_ALERTS);
//   const [realtime,   setRealtime] = useState(FB_REALTIME);
//   const [revSource,  setRevSource]= useState(FB_REVENUE_SOURCE);
//   const timerRef = useRef(null), dataRef = useRef(null);

//   const fetchAll = useCallback(async (p='monthly') => {
//     const [sumRes,rtRes,userRes,revRes,offerRes,funnelRes,retRes,alertRes] = await Promise.all([
//       safeFetch(()=>API.summary(p)), safeFetch(API.realtime), safeFetch(()=>API.users(p)),
//       safeFetch(()=>API.revenue(p)), safeFetch(()=>API.offers(p)), safeFetch(()=>API.funnel(p)),
//       safeFetch(()=>API.retention(p)), safeFetch(API.alerts),
//     ]);
//     let anySuccess=false;
//     if (sumRes) { const s=extractObj(sumRes); if (s.total_revenue!=null||s.total_users!=null){setSummary(s);anySuccess=true;} }
//     const rtList=extract(rtRes); if (rtList.length){setRealtime(rtList);anySuccess=true;}
//     const uList=extract(userRes); if (uList.length){setUsers(uList);anySuccess=true;}
//     const rList=extract(revRes);
//     if (rList.length){
//       setRevenue(rList); anySuccess=true;
//       const latest=rList[0];
//       if (latest?.revenue_by_source&&typeof latest.revenue_by_source==='object'){
//         const src=Object.entries(latest.revenue_by_source).map(([name,value])=>({name,value:parseFloat(value)||0}));
//         if (src.length) setRevSource(src);
//       }
//     }
//     const oList=extract(offerRes); if (oList.length){setOffers(oList);anySuccess=true;}
//     const fList=extract(funnelRes);
//     if (fList.length){setFunnel(fList.map(f=>({name:f.name||f.funnel_type_display||f.funnel_type||'—',entry_count:f.entry_count||f.total_entries||0,conversion_rate:f.conversion_rate||f.overall_conversion_rate||0})));anySuccess=true;}
//     const retList=extract(retRes); if (retList.length){setRetention(retList);anySuccess=true;}
//     const aList=extract(alertRes); if (aList.length){setAlerts(aList);anySuccess=true;}
//     setApiOnline(anySuccess); setDataTimer(DATA_REFRESH);
//   },[]);

//   useEffect(()=>{ timerRef.current=setInterval(()=>{ setCountdown(prev=>{ if(prev<=1){setTheme(t=>(t+1)%THEME_COUNT);return THEME_INTERVAL;} return prev-1; }); },1000); return ()=>clearInterval(timerRef.current); },[]);
//   useEffect(()=>{ fetchAll(period); dataRef.current=setInterval(()=>{ setDataTimer(prev=>{ if(prev<=1){fetchAll(period);return DATA_REFRESH;} return prev-1; }); },1000); return ()=>clearInterval(dataRef.current); },[fetchAll,period]);
//   useEffect(()=>{ document.documentElement.setAttribute('data-theme',theme); },[theme]);

//   const getChartColors=useCallback(()=>{const s=getComputedStyle(document.documentElement);return[s.getPropertyValue('--chart-1').trim()||'#0ea5e9',s.getPropertyValue('--chart-2').trim()||'#34d399',s.getPropertyValue('--chart-3').trim()||'#f59e0b',s.getPropertyValue('--chart-4').trim()||'#a78bfa',s.getPropertyValue('--chart-5').trim()||'#fb7185'];},[theme]);
//   const [colors,setColors]=useState(['#0ea5e9','#34d399','#f59e0b','#a78bfa','#fb7185']);
//   useEffect(()=>{setTimeout(()=>setColors(getChartColors()),100);},[theme]);

//   const kpis=[
//     {label:'Total Revenue',    value:fmtCurrency(summary.total_revenue),                                              unit:'',     trend:'18.4%',trendUp:true, icon:'💰',delay:0   },
//     {label:'Active Users',     value:(summary.active_users||summary.total_users||0).toLocaleString(),                 unit:'',     trend:'12.1%',trendUp:true, icon:'👥',delay:.05 },
//     {label:'Offer Completions',value:(summary.offer_completions||0).toLocaleString(),                                 unit:'',     trend:'9.7%', trendUp:true, icon:'✅',delay:.10 },
//     {label:'Avg Engagement',   value:parseFloat(summary.avg_engagement||0).toFixed(1),                               unit:'/100', trend:'3.2%', trendUp:true, icon:'📊',delay:.15 },
//     {label:'Withdrawals',      value:fmtCurrency(summary.total_withdrawals),                                          unit:'',     trend:'7.8%', trendUp:true, icon:'💸',delay:.20 },
//     {label:'Churn Rate',       value:parseFloat(summary.churn_rate||0).toFixed(1),                                   unit:'%',    trend:'1.1%', trendUp:false,icon:'📉',delay:.25 },
//     {label:'Referrals Joined', value:(summary.referrals_joined||0).toLocaleString(),                                  unit:'',     trend:'22.5%',trendUp:true, icon:'🔗',delay:.30 },
//     {label:'Error Rate',       value:parseFloat(summary.error_rate||0).toFixed(1),                                   unit:'%',    trend:'0.1%', trendUp:false,icon:'⚠️',delay:.35 },
//   ];
//   const revLabel=(item)=>item.period_start_date||item.period_start||item.month||item.label||'';

//   return (
//     <div className="analytics-page" data-theme={theme}>
//       <div className="noise"/>
//       <div className="analytics-container">
//         <header className="analytics-header">
//           <div className="analytics-header__left">
//             <h1>Analytics Dashboard</h1>
//             <p>Last updated: {new Date().toLocaleString()} · {THEME_NAMES[theme]} · <span style={{color:apiOnline?'#34d399':'#f59e0b',fontWeight:600}}>{apiOnline?'● API LIVE':'● MOCK DATA'}</span></p>
//           </div>
//           <div className="analytics-header__right">
//             <div className="theme-indicator"><div className="theme-indicator__dot"/><span>Theme {theme+1}/{THEME_COUNT} · Refresh {dataTimer}s</span></div>
//             <CountdownRing seconds={countdown} total={THEME_INTERVAL}/>
//           </div>
//         </header>

//         <div className="analytics-filters">
//           {['daily','weekly','monthly','yearly'].map(p=>(
//             <button key={p} className={`filter-btn ${period===p?'active':''}`} onClick={()=>setPeriod(p)}>{p.charAt(0).toUpperCase()+p.slice(1)}</button>
//           ))}
//         </div>

//         <div className="section-header"><h2 className="section-title">Real-time Metrics</h2></div>
//         <div className="realtime-grid">
//           {realtime.slice(0,4).map((m,i)=>(
//             <div key={i} className="glass-card realtime-card">
//               <div className="realtime-card__label">{m.metric_name||m.label||'—'}</div>
//               <div className="realtime-card__value">{m.metric_value??m.value??0}{m.unit||''}</div>
//               <div className="realtime-bar"><div className="realtime-bar__fill" style={{width:`${m.percentage||m.pct||0}%`}}/></div>
//             </div>
//           ))}
//         </div>

//         <div className="section-header"><h2 className="section-title">Key Performance Indicators</h2></div>
//         <div className="kpi-grid">{kpis.map((k,i)=><KPICard key={i} {...k}/>)}</div>

//         <div className="section-header">
//           <h2 className="section-title">Revenue & Earnings</h2>
//           <div style={{display:'flex',gap:6}}>
//             {['area','bar','line'].map(t=><button key={t} className={`chart-action-btn ${chartType===t?'active':''}`} onClick={()=>setChartType(t)}>{t.charAt(0).toUpperCase()+t.slice(1)}</button>)}
//           </div>
//         </div>
//         <div className="charts-grid">
//           <div className="glass-card chart-card">
//             <div className="chart-card__header"><div><div className="chart-card__title">Revenue Overview</div><div className="chart-card__subtitle">Revenue, Cost & Profit · {period}</div></div></div>
//             <div className="chart-wrapper chart-wrapper--tall">
//               <ResponsiveContainer width="100%" height={300}>
//                 {chartType==='area'?(
//                   <AreaChart data={revenueList}>
//                     <defs>
//                       <linearGradient id="gr1" x1="0" y1="0" x2="0" y2="1"><stop offset="5%"  stopColor={colors[0]} stopOpacity={0.25}/><stop offset="95%" stopColor={colors[0]} stopOpacity={0}/></linearGradient>
//                       <linearGradient id="gr2" x1="0" y1="0" x2="0" y2="1"><stop offset="5%"  stopColor={colors[1]} stopOpacity={0.25}/><stop offset="95%" stopColor={colors[1]} stopOpacity={0}/></linearGradient>
//                     </defs>
//                     <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
//                     <Area type="monotone" dataKey="revenue_total" name="Revenue" stroke={colors[0]} fill="url(#gr1)" strokeWidth={2} dot={false}/>
//                     <Area type="monotone" dataKey="gross_profit"  name="Profit"  stroke={colors[1]} fill="url(#gr2)" strokeWidth={2} dot={false}/>
//                     <Area type="monotone" dataKey="cost_total"    name="Cost"    stroke={colors[4]} fill="none"      strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
//                   </AreaChart>
//                 ):chartType==='bar'?(
//                   <BarChart data={revenueList}>
//                     <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
//                     <Bar dataKey="revenue_total" name="Revenue" fill={colors[0]} radius={[4,4,0,0]}/><Bar dataKey="cost_total" name="Cost" fill={colors[4]} radius={[4,4,0,0]}/><Bar dataKey="gross_profit" name="Profit" fill={colors[1]} radius={[4,4,0,0]}/>
//                   </BarChart>
//                 ):(
//                   <LineChart data={revenueList}>
//                     <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={revLabel} tickFormatter={revLabel}/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
//                     <Line type="monotone" dataKey="revenue_total" name="Revenue" stroke={colors[0]} strokeWidth={2} dot={{r:3}}/><Line type="monotone" dataKey="gross_profit" name="Profit" stroke={colors[1]} strokeWidth={2} dot={{r:3}}/><Line type="monotone" dataKey="cost_total" name="Cost" stroke={colors[4]} strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
//                   </LineChart>
//                 )}
//               </ResponsiveContainer>
//             </div>
//           </div>
//           <div className="glass-card chart-card">
//             <div className="chart-card__header"><div><div className="chart-card__title">Revenue by Source</div><div className="chart-card__subtitle">Distribution breakdown</div></div></div>
//             <div className="chart-wrapper">
//               <ResponsiveContainer width="100%" height={300}>
//                 <PieChart>
//                   <Pie data={revSource} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={3} dataKey="value">
//                     {revSource.map((_,i)=><Cell key={i} fill={colors[i%colors.length]}/>)}
//                   </Pie>
//                   <Tooltip formatter={(v)=>`${v}%`} content={<CustomTooltip/>}/><Legend iconType="circle" iconSize={8}/>
//                 </PieChart>
//               </ResponsiveContainer>
//             </div>
//           </div>
//         </div>

//         <div className="section-header"><h2 className="section-title">User Activity & Retention</h2></div>
//         <div className="charts-grid">
//           <div className="glass-card chart-card">
//             <div className="chart-card__header"><div><div className="chart-card__title">User Activity</div><div className="chart-card__subtitle">Tasks, Offers & Engagement</div></div></div>
//             <div className="chart-wrapper chart-wrapper--tall">
//               <ResponsiveContainer width="100%" height={300}>
//                 <BarChart data={userList.slice(0,7)}>
//                   <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="user_username"/><YAxis/><Tooltip content={<CustomTooltip/>}/><Legend/>
//                   <Bar dataKey="tasks_completed"  name="Tasks"      fill={colors[0]} radius={[3,3,0,0]}/>
//                   <Bar dataKey="offers_completed" name="Offers"     fill={colors[1]} radius={[3,3,0,0]}/>
//                   <Bar dataKey="engagement_score" name="Engagement" fill={colors[2]} radius={[3,3,0,0]}/>
//                 </BarChart>
//               </ResponsiveContainer>
//             </div>
//           </div>
//           <div className="glass-card chart-card">
//             <div className="chart-card__header"><div><div className="chart-card__title">Retention Cohorts</div><div className="chart-card__subtitle">Day 1 → Day 30</div></div></div>
//             <div style={{overflowX:'auto',paddingBottom:4}}>
//               <table className="retention-table">
//                 <thead><tr><th style={{textAlign:'left',paddingLeft:16}}>Cohort</th><th>D1</th><th>D3</th><th>D7</th><th>D14</th><th>D30</th></tr></thead>
//                 <tbody>
//                   {retention.slice(0,6).map((row,i)=>(
//                     <tr key={i}>
//                       <td style={{fontFamily:'var(--font-mono)',fontSize:'0.75rem',color:'var(--text-muted)',paddingLeft:16}}>{row.cohort_label||row.cohort||`Cohort ${i+1}`}</td>
//                       {[row.day_1||row.d1,row.day_3||row.d3,row.day_7||row.d7,row.day_14||row.d14,row.day_30||row.d30].map((v,j)=><td key={j}><RetentionCell value={v||0}/></td>)}
//                     </tr>
//                   ))}
//                 </tbody>
//               </table>
//             </div>
//           </div>
//         </div>

//         <div className="section-header"><h2 className="section-title">Offer Performance</h2></div>
//         <div className="charts-grid-3">
//           <div className="glass-card chart-card" style={{gridColumn:'span 2'}}>
//             <div className="chart-card__header"><div><div className="chart-card__title">Top Offers by Completions</div><div className="chart-card__subtitle">Completions · CTR · ROI</div></div></div>
//             <div className="chart-wrapper chart-wrapper--tall">
//               <ResponsiveContainer width="100%" height={300}>
//                 <BarChart data={offerList.slice(0,6)} layout="vertical">
//                   <CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number"/><YAxis dataKey="offer_name" type="category" width={90}/><Tooltip content={<CustomTooltip/>}/><Legend/>
//                   <Bar dataKey="completions"        name="Completions" fill={colors[0]} radius={[0,4,4,0]}/>
//                   <Bar dataKey="click_through_rate" name="CTR %"       fill={colors[2]} radius={[0,4,4,0]}/>
//                 </BarChart>
//               </ResponsiveContainer>
//             </div>
//           </div>
//           <div className="glass-card chart-card">
//             <div className="chart-card__header"><div><div className="chart-card__title">Conversion Funnel</div><div className="chart-card__subtitle">Offer completion flow</div></div></div>
//             <div className="funnel-container" style={{marginTop:8}}>
//               {funnelList.map((step,i)=>(
//                 <div key={i} className="funnel-step">
//                   <div className="funnel-step__label">
//                     <span className="funnel-step__name">{step.name||step.funnel_type_display||'—'}</span>
//                     <span className="funnel-step__count">{(step.entry_count||step.total_entries||0).toLocaleString()}</span>
//                     <span className="funnel-step__pct">{parseFloat(step.conversion_rate||0).toFixed(1)}%</span>
//                   </div>
//                   <div className="funnel-bar"><div className="funnel-bar__fill" style={{width:`${Math.min(100,parseFloat(step.conversion_rate||0))}%`}}/></div>
//                 </div>
//               ))}
//             </div>
//           </div>
//         </div>

//         <div className="charts-grid">
//           <div className="glass-card table-card">
//             <div className="table-card__header"><div><div className="chart-card__title">Top Earners</div><div className="chart-card__subtitle">Leaderboard · {period}</div></div></div>
//             <table className="analytics-table">
//               <thead><tr><th>#</th><th>User</th><th>Earnings</th><th>Tasks</th><th>Engagement</th></tr></thead>
//               <tbody>
//                 {userList.slice(0,5).map((u,i)=>(
//                   <tr key={u.id||i}>
//                     <td style={{fontFamily:'var(--font-mono)',color:'var(--text-muted)'}}>{i===0?'🥇':i===1?'🥈':i===2?'🥉':i+1}</td>
//                     <td style={{fontFamily:'var(--font-mono)',fontWeight:600}}>@{u.user_username||u.username||'—'}</td>
//                     <td style={{color:'var(--accent-2)',fontWeight:600}}>{fmtCurrency(u.earnings_total)}</td>
//                     <td>{u.tasks_completed||0}</td>
//                     <td><span className={`badge ${(u.engagement_score||0)>=90?'badge--success':'badge--info'}`}>{parseFloat(u.engagement_score||0).toFixed(0)}/100</span></td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>
//           </div>
//           <div className="glass-card" style={{display:'flex',flexDirection:'column'}}>
//             <div className="table-card__header">
//               <div><div className="chart-card__title">Active Alerts</div><div className="chart-card__subtitle">{alertList.length} unresolved</div></div>
//               <span className="badge badge--danger">{alertList.filter(a=>(a.severity||a.level||'')==='critical').length} Critical</span>
//             </div>
//             <div className="alerts-list">
//               {alertList.slice(0,5).map((alert,i)=>(
//                 <div key={alert.id||i} className="alert-item">
//                   <div className={`alert-item__icon alert-item__icon--${alert.severity||alert.level||'info'}`}>{(alert.severity||alert.level)==='critical'?'🚨':(alert.severity||alert.level)==='warning'?'⚠️':'💡'}</div>
//                   <div className="alert-item__content">
//                     <div className="alert-item__title">{alert.title||alert.rule_name||'—'}</div>
//                     <div className="alert-item__desc">{alert.message||alert.description||'—'}</div>
//                   </div>
//                   <div className="alert-item__time">{timeAgo(alert.created_at)}</div>
//                 </div>
//               ))}
//             </div>
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// };

// // ═══════════════════════════════════════════════════════════════
// // CRUD MANAGEMENT — Analytics Management Full CRUD
// // ═══════════════════════════════════════════════════════════════

// async function crudFetch(url, options = {}) {
//   try {
//     const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
//     const res = await fetch(url, {
//       headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
//       ...options,
//     });
//     const text = await res.text();
//     let data = null;
//     try { data = JSON.parse(text); } catch {}
//     return { ok: res.ok, data };
//   } catch { return { ok: false, data: null }; }
// }

// const CRUD_SECTIONS = [
//   {
//     key: 'events', label: 'Analytics Events', icon: '⚡', color: '#00f3ff',
//     endpoint: '/api/analytics/events/',
//     columns: ['event_type','ip_address','device_type','country','value','event_time'],
//     fields: [
//       { name:'event_type', label:'Event Type', type:'select', options:['page_view','click','task_completed','offer_completed','login','logout','withdrawal_requested','referral_clicked'] },
//       { name:'ip_address', label:'IP Address', type:'text' },
//       { name:'device_type', label:'Device', type:'select', options:['desktop','mobile','tablet'] },
//       { name:'country', label:'Country', type:'text' },
//       { name:'value', label:'Value', type:'number' },
//     ],
//   },
//   {
//     key: 'user-analytics', label: 'User Analytics', icon: '👤', color: '#b44fff',
//     endpoint: '/api/analytics/user-analytics/',
//     columns: ['user_username','period','login_count','tasks_completed','earnings_total','engagement_score'],
//     fields: [
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly','yearly'] },
//       { name:'login_count', label:'Login Count', type:'number' },
//       { name:'tasks_completed', label:'Tasks Done', type:'number' },
//       { name:'earnings_total', label:'Earnings', type:'number' },
//     ],
//   },
//   {
//     key: 'revenue-analytics', label: 'Revenue Analytics', icon: '💰', color: '#ffd700',
//     endpoint: '/api/analytics/revenue-analytics/',
//     columns: ['period','period_start_date','revenue_total','cost_total','gross_profit','net_profit'],
//     fields: [
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly','yearly'] },
//       { name:'revenue_total', label:'Total Revenue', type:'number' },
//       { name:'revenue_ads', label:'Ads Revenue', type:'number' },
//       { name:'revenue_tasks', label:'Tasks Revenue', type:'number' },
//       { name:'gross_profit', label:'Gross Profit', type:'number' },
//     ],
//   },
//   {
//     key: 'offer-performance', label: 'Offer Performance', icon: '🎯', color: '#ff8c00',
//     endpoint: '/api/analytics/offer-performance/',
//     columns: ['period','period_start_date','total_offers','completed_offers','completion_rate','total_revenue'],
//     fields: [
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly'] },
//       { name:'total_offers', label:'Total Offers', type:'number' },
//       { name:'completed_offers', label:'Completed', type:'number' },
//       { name:'total_revenue', label:'Revenue', type:'number' },
//     ],
//   },
//   {
//     key: 'funnel', label: 'Funnel Analytics', icon: '🔻', color: '#00ff88',
//     endpoint: '/api/analytics/funnel/',
//     columns: ['funnel_name','period','step_1_count','step_2_count','step_3_count','conversion_rate'],
//     fields: [
//       { name:'funnel_name', label:'Funnel Name', type:'text' },
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly'] },
//       { name:'step_1_count', label:'Step 1', type:'number' },
//       { name:'step_2_count', label:'Step 2', type:'number' },
//       { name:'step_3_count', label:'Step 3', type:'number' },
//     ],
//   },
//   {
//     key: 'retention', label: 'Retention Analytics', icon: '🔄', color: '#ff2d78',
//     endpoint: '/api/analytics/retention/',
//     columns: ['period','cohort_date','cohort_size','day_1_retention','day_7_retention','day_30_retention'],
//     fields: [
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly'] },
//       { name:'cohort_size', label:'Cohort Size', type:'number' },
//       { name:'day_1_retention', label:'Day 1 %', type:'number' },
//       { name:'day_7_retention', label:'Day 7 %', type:'number' },
//       { name:'day_30_retention', label:'Day 30 %', type:'number' },
//     ],
//   },
//   {
//     key: 'dashboards', label: 'Dashboards', icon: '📊', color: '#4d79ff',
//     endpoint: '/api/analytics/dashboards/',
//     columns: ['name','dashboard_type','is_public','is_default','created_at'],
//     fields: [
//       { name:'name', label:'Name', type:'text' },
//       { name:'dashboard_type', label:'Type', type:'select', options:['admin','user','public'] },
//       { name:'description', label:'Description', type:'text' },
//       { name:'is_public', label:'Is Public', type:'select', options:['true','false'] },
//       { name:'is_default', label:'Is Default', type:'select', options:['true','false'] },
//     ],
//   },
//   {
//     key: 'reports', label: 'Reports', icon: '📄', color: '#00f3ff',
//     endpoint: '/api/analytics/reports/',
//     columns: ['name','report_type','status','period','created_at'],
//     fields: [
//       { name:'name', label:'Report Name', type:'text' },
//       { name:'report_type', label:'Type', type:'select', options:['revenue','users','tasks','offers','comprehensive'] },
//       { name:'period', label:'Period', type:'select', options:['daily','weekly','monthly','yearly'] },
//     ],
//   },
//   {
//     key: 'alert-rules', label: 'Alert Rules', icon: '🔔', color: '#ffd700',
//     endpoint: '/api/analytics/alert-rules/',
//     columns: ['name','metric','operator','threshold','is_active','created_at'],
//     fields: [
//       { name:'name', label:'Rule Name', type:'text' },
//       { name:'metric', label:'Metric', type:'select', options:['revenue','users','tasks','errors','response_time'] },
//       { name:'operator', label:'Operator', type:'select', options:['gt','lt','gte','lte','eq'] },
//       { name:'threshold', label:'Threshold', type:'number' },
//       { name:'is_active', label:'Active', type:'select', options:['true','false'] },
//     ],
//   },
//   {
//     key: 'alerts', label: 'Alert Histories', icon: '🚨', color: '#ff2d78',
//     endpoint: '/api/analytics/alerts/',
//     columns: ['metric_value','triggered_at','is_resolved','resolved_at'],
//     fields: [
//       { name:'metric_value', label:'Metric Value', type:'number' },
//       { name:'is_resolved', label:'Resolved', type:'select', options:['true','false'] },
//     ],
//   },
// ];

// function cFmtCell(val, col) {
//   if (val === null || val === undefined) return React.createElement('span', {style:{color:'rgba(180,160,255,.3)'}}, '—');
//   if (typeof val === 'boolean' || val === 'true' || val === 'false') {
//     const t = val === true || val === 'true';
//     return React.createElement('span', {style:{padding:'2px 8px',borderRadius:4,background:t?'rgba(0,255,136,.1)':'rgba(255,45,120,.1)',color:t?'#00ff88':'#ff2d78',fontSize:'.64rem',fontFamily:'monospace',border:`1px solid ${t?'rgba(0,255,136,.25)':'rgba(255,45,120,.25)'}`}}, t?'✓ Yes':'✗ No');
//   }
//   if (col?.includes('_at')||col?.includes('date')||col?.includes('time')) {
//     try { return React.createElement('span',{style:{fontFamily:'monospace',fontSize:'.7rem',color:'rgba(180,160,255,.6)'}}, new Date(val).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})); }
//     catch { return String(val); }
//   }
//   const BADGE_COLORS = {daily:'#00f3ff',weekly:'#b44fff',monthly:'#ffd700',yearly:'#ff8c00',desktop:'#00f3ff',mobile:'#00ff88',tablet:'#b44fff',active:'#00ff88',pending:'#ffd700',failed:'#ff2d78',page_view:'#4d79ff',click:'#00f3ff',login:'#00ff88',logout:'#ff2d78',admin:'#b44fff',user:'#00f3ff',public:'#00ff88'};
//   if (['period','event_type','device_type','report_type','dashboard_type','status','metric','operator'].includes(col)) {
//     const c = BADGE_COLORS[val] || '#b44fff';
//     return React.createElement('span',{style:{padding:'2px 9px',borderRadius:4,background:`${c}18`,color:c,border:`1px solid ${c}30`,fontSize:'.63rem',fontFamily:'monospace'}}, val);
//   }
//   if (col?.includes('revenue')||col?.includes('earning')||col?.includes('profit')||col?.includes('total_revenue')) {
//     return React.createElement('span',{style:{color:'#ffd700',fontFamily:'monospace',fontSize:'.75rem'}}, `$${parseFloat(val||0).toFixed(2)}`);
//   }
//   if (col?.includes('rate')||col?.includes('retention')) {
//     return React.createElement('span',{style:{color:'#00ff88',fontFamily:'monospace',fontSize:'.75rem'}}, `${parseFloat(val||0).toFixed(1)}%`);
//   }
//   const s = String(val);
//   return React.createElement('span',{style:{fontSize:'.78rem'}}, s.length>35?s.slice(0,35)+'…':s);
// }

// function CrudMgmtToast({ msg, type, onClose }) {
//   useEffect(() => { const t = setTimeout(onClose, 3000); return () => clearTimeout(t); }, [onClose]);
//   return React.createElement('div', {
//     style:{position:'fixed',top:24,right:24,zIndex:9999,padding:'12px 20px',borderRadius:9,
//       background:type==='success'?'rgba(0,255,136,.12)':'rgba(255,45,120,.12)',
//       border:`1px solid ${type==='success'?'rgba(0,255,136,.3)':'rgba(255,45,120,.3)'}`,
//       color:type==='success'?'#00ff88':'#ff2d78',
//       fontFamily:'monospace',fontSize:'.78rem',backdropFilter:'blur(12px)',
//       boxShadow:'0 8px 32px rgba(0,0,0,.4)',
//     }
//   }, msg);
// }

// function CrudTable({ section, onToast }) {
//   const [rows,     setRows]     = useState([]);
//   const [loading,  setLoading]  = useState(true);
//   const [showForm, setShowForm] = useState(false);
//   const [editRow,  setEditRow]  = useState(null);
//   const [delRow,   setDelRow]   = useState(null);
//   const [form,     setForm]     = useState({});
//   const [saving,   setSaving]   = useState(false);
//   const [search,   setSearch]   = useState('');
//   const [page,     setPage]     = useState(1);
//   const PG = 10;

//   const load = useCallback(async () => {
//     setLoading(true);
//     const { ok, data } = await crudFetch(`${section.endpoint}?ordering=-id&page_size=100`);
//     if (ok && data) setRows(Array.isArray(data) ? data : (data?.results || []));
//     setLoading(false);
//   }, [section.endpoint]);

//   useEffect(() => { load(); }, [load]);

//   const handleSave = async () => {
//     setSaving(true);
//     const payload = { ...form };
//     Object.keys(payload).forEach(k => {
//       if (payload[k] === 'true') payload[k] = true;
//       if (payload[k] === 'false') payload[k] = false;
//       if (payload[k] === '') delete payload[k];
//     });
//     const url = editRow ? `${section.endpoint}${editRow.id}/` : section.endpoint;
//     const { ok } = await crudFetch(url, { method: editRow ? 'PUT' : 'POST', body: JSON.stringify(payload) });
//     setSaving(false);
//     if (ok) { onToast(`✅ ${editRow ? 'Updated' : 'Created'}!`, 'success'); setShowForm(false); load(); }
//     else onToast('❌ Save failed. Check required fields.', 'error');
//   };

//   const handleDelete = async () => {
//     const { ok } = await crudFetch(`${section.endpoint}${delRow.id}/`, { method: 'DELETE' });
//     setDelRow(null);
//     if (ok) { onToast('🗑️ Deleted!', 'success'); load(); }
//     else onToast('❌ Delete failed.', 'error');
//   };

//   const filtered = rows.filter(r => !search || JSON.stringify(r).toLowerCase().includes(search.toLowerCase()));
//   const paginated = filtered.slice((page - 1) * PG, page * PG);
//   const totalPages = Math.ceil(filtered.length / PG);
//   const C = section.color;

//   return (
//     <div style={{background:'rgba(6,4,22,.9)',border:`1px solid ${C}25`,borderRadius:14,overflow:'hidden',boxShadow:`0 0 40px ${C}08, 0 8px 32px rgba(0,0,0,.5)`,position:'relative'}}>
//       {/* Top accent line */}
//       <div style={{position:'absolute',top:0,left:0,right:0,height:2,background:`linear-gradient(90deg,transparent,${C},transparent)`}}/>

//       {/* Header */}
//       <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px 20px',borderBottom:`1px solid ${C}15`,background:`${C}04`}}>
//         <div style={{display:'flex',alignItems:'center',gap:10}}>
//           <span style={{fontSize:'1.1rem'}}>{section.icon}</span>
//           <span style={{fontFamily:"'Orbitron',sans-serif",fontSize:'.72rem',fontWeight:800,letterSpacing:'.12em',color:'#e8e0ff'}}>{section.label}</span>
//           <span style={{padding:'3px 10px',borderRadius:50,background:`${C}12`,color:C,border:`1px solid ${C}25`,fontFamily:'monospace',fontSize:'.62rem'}}>{filtered.length} records</span>
//         </div>
//         <div style={{display:'flex',gap:8,alignItems:'center'}}>
//           <input
//             placeholder="🔍 Search..."
//             value={search}
//             onChange={e=>{setSearch(e.target.value);setPage(1);}}
//             style={{padding:'7px 12px',background:'rgba(255,255,255,.04)',border:`1px solid ${C}20`,borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.75rem',outline:'none',width:160,transition:'all .2s'}}
//           />
//           <button
//             onClick={()=>{setEditRow(null);setForm({});setShowForm(true);}}
//             style={{padding:'8px 16px',borderRadius:8,border:`1px solid ${C}`,background:`${C}12`,color:C,fontFamily:"'Orbitron',sans-serif",fontSize:'.62rem',fontWeight:700,cursor:'pointer',letterSpacing:'.08em',transition:'all .2s',boxShadow:`0 0 12px ${C}20`}}
//           >+ Add New</button>
//         </div>
//       </div>

//       {/* Table */}
//       {loading ? (
//         <div style={{padding:48,textAlign:'center',color:'rgba(180,160,255,.3)',fontFamily:'monospace',fontSize:'.75rem',letterSpacing:'.1em'}}>
//           ⟳ Loading...
//         </div>
//       ) : paginated.length === 0 ? (
//         <div style={{padding:56,textAlign:'center'}}>
//           <div style={{fontSize:'2rem',marginBottom:10,opacity:.3}}>{section.icon}</div>
//           <div style={{color:'rgba(180,160,255,.3)',fontFamily:'monospace',fontSize:'.75rem',letterSpacing:'.08em'}}>
//             {search ? 'No results found' : `No ${section.label} yet`}
//           </div>
//           {!search && <div style={{color:'rgba(180,160,255,.2)',fontSize:'.68rem',marginTop:6}}>Click "+ Add New" to create the first record</div>}
//         </div>
//       ) : (
//         <div style={{overflowX:'auto'}}>
//           <table style={{width:'100%',borderCollapse:'collapse'}}>
//             <thead>
//               <tr style={{background:'rgba(0,0,0,.2)'}}>
//                 <th style={{padding:'10px 16px',textAlign:'left',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.12em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`,whiteSpace:'nowrap'}}>#</th>
//                 {section.columns.map(col => (
//                   <th key={col} style={{padding:'10px 14px',textAlign:'left',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.1em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`,whiteSpace:'nowrap'}}>
//                     {col.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
//                   </th>
//                 ))}
//                 <th style={{padding:'10px 14px',textAlign:'right',fontFamily:'monospace',fontSize:'.6rem',color:`${C}80`,letterSpacing:'.1em',textTransform:'uppercase',borderBottom:`1px solid ${C}12`}}>Actions</th>
//               </tr>
//             </thead>
//             <tbody>
//               {paginated.map((row, i) => (
//                 <tr key={row.id||i}
//                   onMouseEnter={e=>e.currentTarget.style.background=`${C}05`}
//                   onMouseLeave={e=>e.currentTarget.style.background='transparent'}
//                   style={{transition:'background .15s',cursor:'default'}}
//                 >
//                   <td style={{padding:'11px 16px',color:'rgba(180,160,255,.25)',fontFamily:'monospace',fontSize:'.65rem',borderBottom:`1px solid rgba(100,60,220,.05)`}}>{(page-1)*PG+i+1}</td>
//                   {section.columns.map(col => (
//                     <td key={col} style={{padding:'11px 14px',borderBottom:`1px solid rgba(100,60,220,.05)`,verticalAlign:'middle'}}>
//                       {cFmtCell(row[col], col)}
//                     </td>
//                   ))}
//                   <td style={{padding:'11px 14px',textAlign:'right',borderBottom:`1px solid rgba(100,60,220,.05)`}}>
//                     <button
//                       onClick={()=>{setEditRow(row);setForm({...row});setShowForm(true);}}
//                       style={{padding:'5px 11px',borderRadius:6,border:'1px solid rgba(0,243,255,.3)',background:'rgba(0,243,255,.06)',color:'#00f3ff',fontSize:'.7rem',cursor:'pointer',marginRight:5,transition:'all .2s'}}
//                     >✏️ Edit</button>
//                     <button
//                       onClick={()=>setDelRow(row)}
//                       style={{padding:'5px 11px',borderRadius:6,border:'1px solid rgba(255,45,120,.3)',background:'rgba(255,45,120,.06)',color:'#ff2d78',fontSize:'.7rem',cursor:'pointer',transition:'all .2s'}}
//                     >🗑️ Del</button>
//                   </td>
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         </div>
//       )}

//       {/* Pagination */}
//       {totalPages > 1 && (
//         <div style={{display:'flex',alignItems:'center',justifyContent:'flex-end',gap:6,padding:'12px 18px',borderTop:`1px solid ${C}10`}}>
//           <span style={{fontFamily:'monospace',fontSize:'.62rem',color:'rgba(180,160,255,.35)',marginRight:8}}>
//             {(page-1)*PG+1}–{Math.min(page*PG,filtered.length)} of {filtered.length}
//           </span>
//           <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1}
//             style={{width:28,height:28,borderRadius:6,border:`1px solid ${C}25`,background:'transparent',color:page===1?'rgba(180,160,255,.2)':C,cursor:page===1?'default':'pointer',fontSize:'.8rem'}}>‹</button>
//           {Array.from({length:Math.min(totalPages,6)},(_,i)=>i+1).map(p=>(
//             <button key={p} onClick={()=>setPage(p)}
//               style={{width:28,height:28,borderRadius:6,border:`1px solid ${page===p?C:C+'25'}`,background:page===p?`${C}15`:'transparent',color:page===p?C:'rgba(180,160,255,.4)',fontFamily:'monospace',fontSize:'.68rem',cursor:'pointer'}}
//             >{p}</button>
//           ))}
//           <button onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages}
//             style={{width:28,height:28,borderRadius:6,border:`1px solid ${C}25`,background:'transparent',color:page===totalPages?'rgba(180,160,255,.2)':C,cursor:page===totalPages?'default':'pointer',fontSize:'.8rem'}}>›</button>
//         </div>
//       )}

//       {/* Add/Edit Modal */}
//       {showForm && (
//         <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
//           <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:`1px solid ${C}35`,borderRadius:16,padding:30,width:'100%',maxWidth:540,maxHeight:'85vh',overflowY:'auto',boxShadow:`0 0 60px ${C}15,0 40px 80px rgba(0,0,0,.7)`}}>
//             <div style={{position:'relative',marginBottom:24}}>
//               <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff'}}>
//                 {editRow?`✏️ Edit ${section.label}`:`➕ New ${section.label}`}
//               </div>
//               <div style={{position:'absolute',bottom:-8,left:0,right:0,height:1,background:`linear-gradient(90deg,${C},transparent)`}}/>
//             </div>
//             <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
//               {section.fields.map(f => (
//                 <div key={f.name}>
//                   <label style={{display:'block',fontFamily:'monospace',fontSize:'.6rem',color:`${C}90`,letterSpacing:'.1em',textTransform:'uppercase',marginBottom:6}}>{f.label}</label>
//                   {f.type==='select' ? (
//                     <select
//                       value={form[f.name]??''}
//                       onChange={e=>setForm(p=>({...p,[f.name]:e.target.value}))}
//                       style={{width:'100%',padding:'9px 12px',background:'rgba(8,5,30,.95)',border:`1px solid ${C}30`,borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none'}}
//                     >
//                       <option value="">— Select —</option>
//                       {f.options.map(o=><option key={o} value={o}>{o}</option>)}
//                     </select>
//                   ) : (
//                     <input
//                       type={f.type} placeholder={f.label}
//                       value={form[f.name]??''}
//                       onChange={e=>setForm(p=>({...p,[f.name]:e.target.value}))}
//                       style={{width:'100%',padding:'9px 12px',background:'rgba(255,255,255,.03)',border:`1px solid ${C}30`,borderRadius:8,color:'#e8e0ff',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',outline:'none'}}
//                     />
//                   )}
//                 </div>
//               ))}
//             </div>
//             <div style={{display:'flex',gap:10,marginTop:24}}>
//               <button onClick={()=>setShowForm(false)}
//                 style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',cursor:'pointer'}}>Cancel</button>
//               <button onClick={handleSave} disabled={saving}
//                 style={{flex:2,padding:'10px',borderRadius:9,border:'none',background:`linear-gradient(135deg,${C}bb,${C})`,color:'#000',fontFamily:"'Exo 2',sans-serif",fontSize:'.83rem',fontWeight:700,cursor:'pointer',boxShadow:`0 4px 20px ${C}40`}}>
//                 {saving?'Saving...':(editRow?'Update':'Create')}
//               </button>
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Delete Confirm */}
//       {delRow && (
//         <div style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.8)',backdropFilter:'blur(10px)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
//           <div style={{background:'linear-gradient(135deg,#080520,#0a0628)',border:'1px solid rgba(255,45,120,.35)',borderRadius:16,padding:28,width:'100%',maxWidth:380,boxShadow:'0 0 40px rgba(255,45,120,.1),0 40px 80px rgba(0,0,0,.7)'}}>
//             <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1rem',fontWeight:800,color:'#e8e0ff',marginBottom:12}}>⚠️ Confirm Delete</div>
//             <p style={{fontSize:'.82rem',color:'rgba(180,160,255,.7)',marginBottom:20,lineHeight:1.6}}>
//               Delete record <strong style={{color:'#ff2d78'}}>#{delRow.id}</strong>? This action cannot be undone.
//             </p>
//             <div style={{display:'flex',gap:10}}>
//               <button onClick={()=>setDelRow(null)}
//                 style={{flex:1,padding:'10px',borderRadius:9,border:'1px solid rgba(100,60,220,.3)',background:'transparent',color:'rgba(180,160,255,.5)',cursor:'pointer'}}>Cancel</button>
//               <button onClick={handleDelete}
//                 style={{flex:1,padding:'10px',borderRadius:9,border:'none',background:'linear-gradient(135deg,#ff2d78bb,#ff2d78)',color:'#000',fontWeight:700,cursor:'pointer',boxShadow:'0 4px 20px rgba(255,45,120,.4)'}}>Delete</button>
//             </div>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// }

// function AnalyticsManagement() {
//   const [active, setActive] = useState('events');
//   const [toast,  setToast]  = useState(null);
//   const showToast = useCallback((msg, type) => setToast({ msg, type, key: Date.now() }), []);
//   const section = CRUD_SECTIONS.find(s => s.key === active);

//   return (
//     <div style={{minHeight:'100vh',background:'#04020f',padding:'24px',fontFamily:"'Exo 2',sans-serif",color:'#e8e0ff'}}>
//       {toast && <CrudMgmtToast key={toast.key} msg={toast.msg} type={toast.type} onClose={()=>setToast(null)}/>}

//       {/* Header */}
//       <div style={{marginBottom:24}}>
//         <div style={{fontFamily:"'Orbitron',sans-serif",fontSize:'1.3rem',fontWeight:900,background:'linear-gradient(135deg,#00f3ff,#b44fff)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',letterSpacing:'.05em',marginBottom:4}}>
//           ⚙️ Analytics Management
//         </div>
//         <div style={{fontSize:'.7rem',color:'rgba(180,160,255,.4)',fontFamily:'monospace',letterSpacing:'.1em'}}>
//           FULL CRUD · {CRUD_SECTIONS.length} MODULES · REAL API
//         </div>
//       </div>

//       {/* Section Tabs */}
//       <div style={{display:'flex',gap:8,marginBottom:24,flexWrap:'wrap'}}>
//         {CRUD_SECTIONS.map(s => (
//           <button key={s.key}
//             onClick={()=>setActive(s.key)}
//             style={{
//               padding:'8px 14px',borderRadius:9,
//               border:`1px solid ${active===s.key?s.color:'rgba(100,60,220,.18)'}`,
//               background:active===s.key?`${s.color}15`:'rgba(6,4,22,.8)',
//               color:active===s.key?s.color:'rgba(180,160,255,.4)',
//               fontFamily:"'Orbitron',sans-serif",fontSize:'.6rem',fontWeight:700,
//               letterSpacing:'.08em',cursor:'pointer',transition:'all .2s',
//               boxShadow:active===s.key?`0 0 16px ${s.color}20`:'none',
//             }}
//           >{s.icon} {s.label}</button>
//         ))}
//       </div>

//       {/* Active Table */}
//       {section && <CrudTable key={active} section={section} onToast={showToast}/>}
//     </div>
//   );
// }

// // ─── Default Export: Tab Wrapper ──────────────────────────────────────────────
// const AnalyticsWithManagement = () => {
//   const [view, setView] = useState('dashboard');
//   return (
//     <div style={{minHeight:'100vh',background:'#04020f'}}>
//       {/* Tab Bar */}
//       <div style={{display:'flex',gap:0,background:'rgba(6,4,22,.97)',borderBottom:'1px solid rgba(100,60,220,.2)',backdropFilter:'blur(20px)',position:'sticky',top:0,zIndex:200,padding:'0 20px'}}>
//         {[
//           {key:'dashboard', label:'📊 Analytics Dashboard', color:'#00f3ff'},
//           {key:'management',label:'⚙️ Management · CRUD',   color:'#b44fff'},
//         ].map(t=>(
//           <button key={t.key} onClick={()=>setView(t.key)}
//             style={{padding:'14px 22px',border:'none',borderBottom:`2px solid ${view===t.key?t.color:'transparent'}`,background:'transparent',color:view===t.key?t.color:'rgba(180,160,255,.4)',fontFamily:"'Orbitron',sans-serif",fontSize:'.65rem',fontWeight:700,letterSpacing:'.1em',cursor:'pointer',transition:'all .25s'}}
//           >{t.label}</button>
//         ))}
//       </div>
//       {view==='dashboard'  && <Analytics/>}
//       {view==='management' && <AnalyticsManagement/>}
//     </div>
//   );
// };

// export default AnalyticsWithManagement;


