// src/pages/Wallet.jsx
// ✅ REAL API connected — views.py এর সব endpoints
// 🔄 Fallback mock data — API fail হলে দেখাবে, real data আসলে replace হবে
// CSS: ../styles/wallet.css

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import '../styles/wallet.css';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ════════════════════════════════════════════════════════════════════════════
// ✅ BASE URL — আপনার urls.py এর wallet prefix
// যদি /api/wallet/ না হয় তাহলে শুধু এই লাইন change করুন
// ════════════════════════════════════════════════════════════════════════════
const BASE = '/api/wallet';

// ✅ Auth token — localStorage থেকে নেয়
const authH = () => ({
  'Authorization': `Bearer ${
    localStorage.getItem('adminAccessToken') ||
    localStorage.getItem('access_token')     ||
    localStorage.getItem('auth_token')       || ''
  }`,
  'Content-Type': 'application/json',
});

// ════════════════════════════════════════════════════════════════════════════
// ✅ REAL API ENDPOINTS — urls.py এর actual paths
// ════════════════════════════════════════════════════════════════════════════
const API = {
  // WalletSummaryAPIView → path('summary/', ...)
  summary:            ()      => fetch(`${BASE}/summary/`,                               { headers: authH() }),

  // WalletViewSet → router.register(r'wallets', ...)
  wallets:            ()      => fetch(`${BASE}/wallets/`,                               { headers: authH() }),
  lockWallet:         (id, d) => fetch(`${BASE}/wallets/${id}/lock/`,                    { method:'POST',   headers:authH(), body:JSON.stringify(d) }),
  unlockWallet:       (id)    => fetch(`${BASE}/wallets/${id}/unlock/`,                  { method:'POST',   headers:authH() }),
  freezeBalance:      (id, d) => fetch(`${BASE}/wallets/${id}/freeze_balance/`,          { method:'POST',   headers:authH(), body:JSON.stringify(d) }),
  unfreezeBalance:    (id, d) => fetch(`${BASE}/wallets/${id}/unfreeze_balance/`,        { method:'POST',   headers:authH(), body:JSON.stringify(d) }),

  // TransactionHistoryView → path('transactions/', ...) from api_views.py
  // WalletTransactionViewSet CRUD → router.register(r'transactions', ...)
  transactions:       ()      => fetch(`${BASE}/transactions/?page_size=50&ordering=-created_at`, { headers: authH() }),
  // Transaction actions → ViewSet এ আছে (same router prefix)
  approveTransaction: (id)    => fetch(`${BASE}/transactions/${id}/approve/`,            { method:'POST',   headers:authH() }),
  rejectTransaction:  (id, d) => fetch(`${BASE}/transactions/${id}/reject/`,             { method:'POST',   headers:authH(), body:JSON.stringify(d) }),
  reverseTransaction: (id, d) => fetch(`${BASE}/transactions/${id}/reverse/`,            { method:'POST',   headers:authH(), body:JSON.stringify(d) }),

  // WithdrawalHistoryView → path('withdrawals/', ...) from api_views.py  (list)
  // WithdrawalViewSet CRUD → router.register(r'withdrawals-crud', ...)   (actions)
  withdrawals:        ()      => fetch(`${BASE}/withdrawals/?ordering=-created_at`,      { headers: authH() }),
  processWithdrawal:  (id)    => fetch(`${BASE}/withdrawals-crud/${id}/process/`,        { method:'POST',   headers:authH() }),
  completeWithdrawal: (id, d) => fetch(`${BASE}/withdrawals-crud/${id}/complete/`,       { method:'POST',   headers:authH(), body:JSON.stringify(d) }),
  rejectWithdrawal:   (id, d) => fetch(`${BASE}/withdrawals-crud/${id}/reject/`,         { method:'POST',   headers:authH(), body:JSON.stringify(d) }),

  // PaymentMethodsView → path('payment-methods/', ...)  from api_views.py  (list/create)
  // UserPaymentMethodViewSet → router.register(r'payment-methods-crud', ...)  (update/delete/actions)
  paymentMethods:     ()      => fetch(`${BASE}/payment-methods/`,                       { headers: authH() }),
  createPayMethod:    (d)     => fetch(`${BASE}/payment-methods/`,                       { method:'POST',   headers:authH(), body:JSON.stringify(d) }),
  updatePayMethod:    (id, d) => fetch(`${BASE}/payment-methods-crud/${id}/`,            { method:'PATCH',  headers:authH(), body:JSON.stringify(d) }),
  deletePayMethod:    (id)    => fetch(`${BASE}/payment-methods-crud/${id}/`,            { method:'DELETE', headers:authH() }),
  setPrimaryMethod:   (id)    => fetch(`${BASE}/payment-methods-crud/${id}/set_primary/`,{ method:'POST',   headers:authH() }),
  verifyPayMethod:    (id)    => fetch(`${BASE}/payment-methods-crud/${id}/verify/`,     { method:'POST',   headers:authH() }),

  // WalletWebhookLogViewSet → router.register(r'webhooks', ...)
  webhookLogs:        ()      => fetch(`${BASE}/webhooks/`,                              { headers: authH() }),

  // BulkWalletOperationAPIView → path('bulk-operations/', ...)
  bulkOperation:      (d)     => fetch(`${BASE}/bulk-operations/`,                       { method:'POST', headers:authH(), body:JSON.stringify(d) }),

  // Task APIViews → path('tasks/', include(task_urlpatterns))
  expireBonuses:      ()      => fetch(`${BASE}/tasks/expire-bonus/`,                    { method:'POST', headers:authH() }),
  autoProcessWd:      (d)     => fetch(`${BASE}/tasks/process-withdrawals/`,             { method:'POST', headers:authH(), body:JSON.stringify(d) }),
  cleanupLogs:        (d)     => fetch(`${BASE}/tasks/cleanup-logs/`,                    { method:'POST', headers:authH(), body:JSON.stringify(d) }),
  generateReport:     (d)     => fetch(`${BASE}/tasks/generate-report/`,                 { method:'POST', headers:authH(), body:JSON.stringify(d) }),
  syncPayments:       ()      => fetch(`${BASE}/tasks/sync-payments/`,                   { method:'POST', headers:authH() }),

  // User action APIViews → path('user/', include(user_task_urlpatterns))
  requestWithdrawal:  (d)     => fetch(`${BASE}/user/withdraw/request/`,                 { method:'POST', headers:authH(), body:JSON.stringify(d) }),
  addFunds:           (d)     => fetch(`${BASE}/add-money/`,                             { method:'POST', headers:authH(), body:JSON.stringify(d) }),
};

// ════════════════════════════════════════════════════════════════════════════
// ✅ SAFE FETCH — network error handle করে
// ════════════════════════════════════════════════════════════════════════════
async function sf(fn) {
  try {
    const r = await fn();
    if (r.status === 204) return { ok:true, success:true }; // DELETE success
    const text = await r.text();
    if (!r.ok) { console.warn(`[Wallet] ${r.status}:`, text.slice(0,200)); return null; }
    try { return JSON.parse(text); } catch { return null; }
  } catch(e) { console.warn('[Wallet] Network:', e.message); return null; }
}

// API response থেকে array বের করে
// handles: [...] | {results} | {success,data:[]} | {success,data:{withdrawals:[]}} | any named array
const toList = (r) => {
  if (!r) return null;
  if (Array.isArray(r)) return r;
  if (Array.isArray(r.results)) return r.results;
  if (r.data) {
    if (Array.isArray(r.data)) return r.data;
    if (Array.isArray(r.data?.results)) return r.data.results;
    // { success, data: { withdrawals: [...], pagination: {} } }
    const firstArr = Object.values(r.data).find(v => Array.isArray(v));
    if (firstArr) return firstArr;
  }
  return null;
};

// ════════════════════════════════════════════════════════════════════════════
// 🔄 MOCK / FALLBACK DATA
// এগুলো শুধু API offline বা empty হলে দেখাবে
// Real API data আসলে এগুলো automatically replace হয়ে যাবে
// ════════════════════════════════════════════════════════════════════════════

// 🔄 MOCK: WalletSummaryAPIView এর response structure
// Real data: /api/wallet/summary/ থেকে আসবে
const MOCK_SUMMARY = {
  total_balance:      48720.50,   // 🔄 mock
  balance_change_pct: 12.4,       // 🔄 mock — last 30d vs previous 30d
  mining_speed:       3.2,        // 🔄 mock — MH/s
  mining_gauge_pct:   0.68,       // 🔄 mock — 0.0 to 1.0
  mining_bars:        [4,6,5,8,6,9,7,10,8,11,9,10], // 🔄 mock — bar chart heights
  monthly_growth: [               // 🔄 mock — last 6 months income/expense
    { month:'Oct', income:4200, expense:1800 },
    { month:'Nov', income:5100, expense:2200 },
    { month:'Dec', income:4800, expense:1900 },
    { month:'Jan', income:6200, expense:2400 },
    { month:'Feb', income:5800, expense:2100 },
    { month:'Mar', income:7400, expense:2600 },
  ],
  currency_breakdown: { USD:32400.50, BTC:8120.00, USDT:5600.00, BDT:2600.00 }, // 🔄 mock
  withdrawal_counts:  { pending:3, processing:1, completed:24 }, // 🔄 mock
  investment_packages: [], // 🔄 mock
  user: { name:'Admin User', avatar:'', plan:'Pro' }, // 🔄 mock
};

// 🔄 MOCK: WalletViewSet list response
// Real data: /api/wallet/wallets/ থেকে আসবে
const MOCK_WALLETS = [
  { id:1, user:1, currency:'USD', current_balance:'32400.50', available_balance:'28000.00',
    pending_balance:'4400.50', frozen_balance:'0.00', bonus_balance:'200.00',
    total_earned:'85000.00', total_withdrawn:'52599.50', status:'active', is_locked:false },
  { id:2, user:1, currency:'BTC', current_balance:'8120.00',  available_balance:'8120.00',
    pending_balance:'0.00',    frozen_balance:'0.00', bonus_balance:'0.00',
    total_earned:'12000.00', total_withdrawn:'3880.00', status:'active', is_locked:false },
];

// 🔄 MOCK: WalletTransactionViewSet list response
// Real data: /api/wallet/transactions/ থেকে আসবে
const MOCK_TRANSACTIONS = [
  { id:1, transaction_id:'TXN-001', type:'earning',     amount:'520.00',  status:'approved', description:'Weekly earning reward', created_at: new Date(Date.now()-3600000).toISOString() },
  { id:2, transaction_id:'TXN-002', type:'withdrawal',  amount:'-200.00', status:'pending',  description:'Withdrawal to bKash',   created_at: new Date(Date.now()-7200000).toISOString() },
  { id:3, transaction_id:'TXN-003', type:'bonus',       amount:'100.00',  status:'approved', description:'Referral bonus',        created_at: new Date(Date.now()-86400000).toISOString() },
  { id:4, transaction_id:'TXN-004', type:'admin_credit',amount:'1500.00', status:'approved', description:'Admin top-up',          created_at: new Date(Date.now()-172800000).toISOString() },
];

// 🔄 MOCK: WithdrawalViewSet list response
// Real data: /api/wallet/withdrawals/ থেকে আসবে
const MOCK_WITHDRAWALS = [
  { id:1, withdrawal_id:'WD-001', amount:'500.00',  fee:'10.00', net_amount:'490.00',  status:'pending',    created_at: new Date(Date.now()-3600000).toISOString() },
  { id:2, withdrawal_id:'WD-002', amount:'1200.00', fee:'24.00', net_amount:'1176.00', status:'processing', created_at: new Date(Date.now()-86400000).toISOString() },
  { id:3, withdrawal_id:'WD-003', amount:'300.00',  fee:'6.00',  net_amount:'294.00',  status:'completed',  created_at: new Date(Date.now()-172800000).toISOString() },
];

// 🔄 MOCK: UserPaymentMethodViewSet list response
// Real data: /api/wallet/payment-methods/ থেকে আসবে
const MOCK_METHODS = [
  { id:1, method_type:'bank_transfer', method_type_display:'Bank Transfer', account_name:'John Doe', account_number:'****4521',      is_primary:true,  is_verified:true  },
  { id:2, method_type:'bkash',         method_type_display:'bKash',         account_name:'John',     account_number:'01712345678',   is_primary:false, is_verified:false },
];

// ════════════════════════════════════════════════════════════════════════════
// CONFIG
// ════════════════════════════════════════════════════════════════════════════
const CURR_CFG = {
  USD:{color:'#10b981',glow:'#10b98140'}, EUR:{color:'#6366f1',glow:'#6366f140'},
  BTC:{color:'#f59e0b',glow:'#f59e0b40'}, USDT:{color:'#06b6d4',glow:'#06b6d440'},
  BDT:{color:'#8b5cf6',glow:'#8b5cf640'}, default:{color:'#94a3b8',glow:'#94a3b840'},
};
const TX_CFG = {
  earning:{icon:'↑',color:'#10b981'}, reward:{icon:'★',color:'#f59e0b'},
  referral:{icon:'◎',color:'#6366f1'}, bonus:{icon:'✦',color:'#f59e0b'},
  withdrawal:{icon:'↓',color:'#ef4444'}, withdrawal_fee:{icon:'↓',color:'#ef4444'},
  admin_credit:{icon:'⊕',color:'#10b981'}, admin_debit:{icon:'⊖',color:'#ef4444'},
  reversal:{icon:'↺',color:'#6366f1'}, default:{icon:'•',color:'#94a3b8'},
};
const NAV = [
  {id:'dashboard',icon:'⬡',label:'Dashboard'},    {id:'wallets',icon:'◈',label:'Wallets'},
  {id:'transactions',icon:'⇄',label:'Transactions'},{id:'withdrawals',icon:'⬇',label:'Withdrawals'},
  {id:'methods',icon:'▣',label:'Payment Methods'},  {id:'admin',icon:'⚙',label:'Admin Panel'},
  {id:'webhooks',icon:'⚡',label:'Webhooks'},
];

// ════════════════════════════════════════════════════════════════════════════
// HELPERS
// ════════════════════════════════════════════════════════════════════════════
const fmt = (n,d=2) => Number(n||0).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const ago = (d) => {
  if (!d) return '—';
  const s = (Date.now()-new Date(d))/1000;
  if (s<60) return `${~~s}s ago`; if (s<3600) return `${~~(s/60)}m ago`;
  if (s<86400) return `${~~(s/3600)}h ago`; return `${~~(s/86400)}d ago`;
};
const sc = (s) => ({approved:'#10b981',completed:'#10b981',active:'#10b981',pending:'#f59e0b',processing:'#6366f1',rejected:'#ef4444',failed:'#ef4444',locked:'#ef4444'}[(s||'').toLowerCase()]||'#94a3b8');

// ════════════════════════════════════════════════════════════════════════════
// SMALL COMPONENTS
// ════════════════════════════════════════════════════════════════════════════
const Skel = ({w='100%',h=16,r=8}) => <div className="wl-skel" style={{width:w,height:h,borderRadius:r}}/>;

function Toasts({list}) {
  return <div className="wl-toasts">{list.map(t=>(
    <div key={t.id} className={`wl-toast wl-toast--${t.type}`}>
      <span className="wl-toast__icon">{t.type==='success'?'✓':t.type==='error'?'✕':t.type==='loading'?'↻':'ℹ'}</span>
      {t.msg}
    </div>
  ))}</div>;
}

function Modal({title,icon,onClose,children,wide}) {
  return (
    <div className="wl-overlay" onClick={onClose}>
      <div className={`wl-modal wl-glass${wide?' wl-modal--wide':''}`} onClick={e=>e.stopPropagation()}>
        <div className="wl-modal__hdr">
          <div className="wl-modal__hdr-left">
            {icon&&<div className="wl-modal__icon">{icon}</div>}
            <h3 className="wl-modal__title">{title}</h3>
          </div>
          <button className="wl-icon-btn" onClick={onClose}>✕</button>
        </div>
        <div className="wl-modal__body">{children}</div>
      </div>
    </div>
  );
}

function Field({label,field,form,setForm,type='text',options,placeholder,required}) {
  return (
    <div className="wl-field">
      <label className="wl-field__lbl">{label}{required&&<span className="wl-req">*</span>}</label>
      {options
        ? <select className="wl-field__input wl-field__select" value={form[field]||''} onChange={e=>setForm(p=>({...p,[field]:e.target.value}))}>
            {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        : <input type={type} className="wl-field__input" value={form[field]||''} placeholder={placeholder}
            onChange={e=>setForm(p=>({...p,[field]:e.target.value}))}/>
      }
    </div>
  );
}

const ChartTip = ({active,payload,label}) => {
  if (!active||!payload?.length) return null;
  return <div className="wl-chart-tip"><div className="wl-chart-tip__label">{label}</div>
    {payload.map((p,i)=><div key={i} className="wl-chart-tip__row" style={{color:p.color}}>{p.name}: ${p.value?.toLocaleString()}</div>)}
  </div>;
};

// ════════════════════════════════════════════════════════════════════════════
// MODALS
// ════════════════════════════════════════════════════════════════════════════

// ✅ POST /api/wallet/request-withdrawal/
function WithdrawModal({methods,onClose,toast,onSuccess}) {
  const [form,setForm] = useState({amount:'',payment_method_id:'',note:''});
  const [saving,setSaving] = useState(false);
  const fee = form.amount?(Number(form.amount)*0.02).toFixed(2):'0.00';
  const net = form.amount?(Number(form.amount)*0.98).toFixed(2):'0.00';
  const handle = async () => {
    if (!form.amount||Number(form.amount)<=0){toast('Enter valid amount','error');return;}
    if (!form.payment_method_id){toast('Select payment method','error');return;}
    setSaving(true);
    const r = await sf(()=>API.requestWithdrawal({amount:form.amount,payment_method_id:Number(form.payment_method_id),note:form.note}));
    setSaving(false);
    if (r?.success||r?.data){toast('Withdrawal submitted!','success');onSuccess();onClose();}
    else toast(r?.error||'Failed','error');
  };
  return (
    <Modal title="Request Withdrawal" icon="↓" onClose={onClose}>
      <div className="wl-form-grid">
        <Field label="Amount (USD)" field="amount" form={form} setForm={setForm} type="number" placeholder="0.00" required/>
        <Field label="Payment Method" field="payment_method_id" form={form} setForm={setForm}
          options={[{value:'',label:'Select method…'},...methods.map(m=>({value:m.id,label:`${m.method_type_display||m.method_type} — ${m.account_number||''}`}))]} required/>
        <Field label="Note (optional)" field="note" form={form} setForm={setForm} placeholder="Any note…"/>
        {Number(form.amount)>0&&<div className="wl-fee-box">Fee: <strong>${fee}</strong> (2%) → You receive: <strong>${net}</strong></div>}
        <div className="wl-modal__footer">
          <button className="wl-btn wl-btn--danger" onClick={handle} disabled={saving}>{saving&&<span className="wl-spin">↻</span>} {saving?'Submitting…':'Submit Request'}</button>
          <button className="wl-btn wl-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ✅ POST /api/wallet/add-funds/
function AddFundsModal({onClose,toast,onSuccess}) {
  const [form,setForm] = useState({amount:''});
  const [saving,setSaving] = useState(false);
  const handle = async () => {
    if (!form.amount||Number(form.amount)<=0){toast('Enter valid amount','error');return;}
    setSaving(true);
    const r = await sf(()=>API.addFunds({amount:form.amount}));
    setSaving(false);
    if (r?.success||r?.new_balance!==undefined){toast(`$${form.amount} added!`,'success');onSuccess();onClose();}
    else toast(r?.error||'Failed','error');
  };
  return (
    <Modal title="Add Funds" icon="⊕" onClose={onClose}>
      <div className="wl-form-grid">
        <Field label="Amount (USD)" field="amount" form={form} setForm={setForm} type="number" placeholder="0.00" required/>
        <div className="wl-modal__footer">
          <button className="wl-btn wl-btn--primary" onClick={handle} disabled={saving}>{saving&&<span className="wl-spin">↻</span>} {saving?'Processing…':'Add Funds'}</button>
          <button className="wl-btn wl-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ✅ POST/PATCH /api/wallet/payment-methods/
function PayMethodModal({method,onClose,toast,onSuccess,userId}) {
  const isEdit = !!method;
  const [form,setForm] = useState(isEdit?{method_type:method.method_type||'bank_transfer',account_name:method.account_name||'',account_number:method.account_number||'',bank_name:method.bank_name||'',routing_number:method.routing_number||''}:{method_type:'bank_transfer',account_name:'',account_number:'',bank_name:'',routing_number:''});
  const [saving,setSaving] = useState(false);
  const handle = async () => {
    if (!form.account_name||!form.account_number){toast('Fill required fields','error');return;}
    setSaving(true);
    const r = isEdit?await sf(()=>API.updatePayMethod(method.id,form)):await sf(()=>API.createPayMethod({...form,user:userId}));
    setSaving(false);
    if (r?.id||r?.success){toast(isEdit?'Updated!':'Added!','success');onSuccess();onClose();}
    else toast('Failed','error');
  };
  return (
    <Modal title={isEdit?'Edit Method':'Add Payment Method'} icon="▣" onClose={onClose} wide>
      <div className="wl-form-grid">
        <div className="wl-form-row">
          <Field label="Method Type" field="method_type" form={form} setForm={setForm}
            options={[{value:'bank_transfer',label:'Bank Transfer'},{value:'bkash',label:'bKash'},{value:'nagad',label:'Nagad'},{value:'rocket',label:'Rocket'},{value:'paypal',label:'PayPal'},{value:'crypto',label:'Crypto'}]}/>
          <Field label="Account Name *" field="account_name" form={form} setForm={setForm} placeholder="Full name" required/>
        </div>
        <div className="wl-form-row">
          <Field label="Account Number *" field="account_number" form={form} setForm={setForm} placeholder="Account/wallet number" required/>
          <Field label="Bank Name" field="bank_name" form={form} setForm={setForm} placeholder="Optional"/>
        </div>
        <Field label="Routing Number" field="routing_number" form={form} setForm={setForm} placeholder="Optional"/>
        <div className="wl-modal__footer">
          <button className="wl-btn wl-btn--primary" onClick={handle} disabled={saving}>{saving&&<span className="wl-spin">↻</span>} {saving?'Saving…':(isEdit?'Update':'Add')}</button>
          <button className="wl-btn wl-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ✅ POST /api/wallet/wallets/{id}/lock|unlock|freeze_balance|unfreeze_balance/
function WalletActionModal({wallet,action,onClose,toast,onSuccess}) {
  const [form,setForm] = useState({amount:'',reason:''});
  const [saving,setSaving] = useState(false);
  const handle = async () => {
    setSaving(true);
    let r;
    if (action==='lock')     r = await sf(()=>API.lockWallet(wallet.id,{reason:form.reason||'Locked by admin'}));
    if (action==='unlock')   r = await sf(()=>API.unlockWallet(wallet.id));
    if (action==='freeze')   r = await sf(()=>API.freezeBalance(wallet.id,{amount:form.amount,reason:form.reason}));
    if (action==='unfreeze') r = await sf(()=>API.unfreezeBalance(wallet.id,{amount:form.amount,reason:form.reason}));
    setSaving(false);
    if (r?.success){toast(`Wallet ${action}ed!`,'success');onSuccess();onClose();}
    else toast(r?.error||`${action} failed`,'error');
  };
  const labels={lock:'Lock Wallet',unlock:'Unlock Wallet',freeze:'Freeze Balance',unfreeze:'Unfreeze Balance'};
  const icons={lock:'🔒',unlock:'🔓',freeze:'❄',unfreeze:'♨'};
  return (
    <Modal title={labels[action]} icon={icons[action]} onClose={onClose}>
      <div className="wl-form-grid">
        <div className="wl-fee-box" style={{background:'rgba(99,102,241,.08)',borderColor:'rgba(99,102,241,.25)',color:'#a5b4fc'}}>
          Wallet: <strong>{wallet.currency}</strong> — Balance: <strong>${fmt(wallet.current_balance)}</strong>
        </div>
        {(action==='freeze'||action==='unfreeze')&&<Field label="Amount" field="amount" form={form} setForm={setForm} type="number" placeholder="0.00" required/>}
        <Field label="Reason" field="reason" form={form} setForm={setForm} placeholder="Reason…"/>
        <div className="wl-modal__footer">
          <button className="wl-btn wl-btn--primary" onClick={handle} disabled={saving}>{saving&&<span className="wl-spin">↻</span>} {saving?'Processing…':labels[action]}</button>
          <button className="wl-btn wl-btn--ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Modal>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ══ MAIN COMPONENT ══════════════════════════════════════════════════════════
// ════════════════════════════════════════════════════════════════════════════
export default function Wallet() {
  const [tab,         setTab]         = useState('dashboard');
  const [loading,     setLoading]     = useState(false);
  const [apiOnline,   setApiOnline]   = useState(false);
  const [toasts,      setToasts]      = useState([]);
  const [modal,       setModal]       = useState(null);
  const [actionLoad,  setActionLoad]  = useState({});
  const [miningActive,setMiningActive]= useState(false);

  // ✅ REAL DATA STATE
  // Initial value = mock data (দেখাবে যতক্ষণ API load না হয়)
  // fetchAll() call হলে real API data দিয়ে replace হবে
  const [summary,      setSummary]      = useState(MOCK_SUMMARY);      // 🔄→✅ /api/wallet/summary/
  const [wallets,      setWallets]      = useState(MOCK_WALLETS);      // 🔄→✅ /api/wallet/wallets/
  const [transactions, setTransactions] = useState(MOCK_TRANSACTIONS); // 🔄→✅ /api/wallet/transactions/
  const [withdrawals,  setWithdrawals]  = useState(MOCK_WITHDRAWALS);  // 🔄→✅ /api/wallet/withdrawals/
  const [methods,      setMethods]      = useState(MOCK_METHODS);      // 🔄→✅ /api/wallet/payment-methods/
  const [webhooks,     setWebhooks]     = useState([]);                 // ✅ /api/wallet/webhook-logs/

  const setAL = (k,v) => setActionLoad(p=>({...p,[k]:v}));

  // TOAST
  const toast = useCallback((msg,type='success') => {
    const id = Date.now();
    setToasts(p=>[...p,{id,msg,type}]);
    if (type!=='loading') setTimeout(()=>setToasts(p=>p.filter(t=>t.id!==id)),3500);
  },[]);

  // ✅ FETCH ALL — সব API একসাথে call করে real data load করে
  const fetchAll = useCallback(async (showLoader=false) => {
    if (showLoader) setLoading(true);

    const [sumR, wR, txR, wdR, mR, whR] = await Promise.all([
      sf(API.summary),        // → setSummary
      sf(API.wallets),        // → setWallets
      sf(API.transactions),   // → setTransactions
      sf(API.withdrawals),    // → setWithdrawals
      sf(API.paymentMethods), // → setMethods
      sf(API.webhookLogs),    // → setWebhooks
    ]);

    let ok = false;

    // ✅ Summary: total_balance, monthly_growth, mining_*, currency_breakdown, user
    if (sumR && !sumR.error) {
      setSummary(sumR); // 🔄 mock replace হলো real data দিয়ে
      ok = true;
    }

    // ✅ Wallets: currency, current_balance, available_balance, status, is_locked…
    const wList = toList(wR);
    if (wList) { setWallets(wList.length ? wList : MOCK_WALLETS); ok = true; }

    // ✅ Transactions: transaction_id, type, amount, status, description…
    const txList = toList(txR);
    if (txList) { setTransactions(txList.length ? txList : MOCK_TRANSACTIONS); ok = true; }

    // ✅ Withdrawals: withdrawal_id, amount, fee, net_amount, status…
    const wdList = toList(wdR);
    if (wdList) { setWithdrawals(wdList.length ? wdList : MOCK_WITHDRAWALS); ok = true; }

    // ✅ Payment Methods: method_type, account_name, account_number, is_primary…
    const mList = toList(mR);
    if (mList) { setMethods(mList.length ? mList : MOCK_METHODS); ok = true; }

    // ✅ Webhooks: webhook_type, event_type, is_processed, processing_error…
    const whList = toList(whR);
    if (whList) { setWebhooks(whList); ok = true; }

    setApiOnline(ok);
    if (showLoader) setLoading(false);
  }, []);

  useEffect(() => { fetchAll(true); }, [fetchAll]);

  // DERIVED
  const currBreakdown = useMemo(() => {
    // ✅ wallet list থেকে currency group করি
    if (wallets !== MOCK_WALLETS && wallets.length) {
      const m = {};
      wallets.forEach(w => { m[w.currency] = (m[w.currency]||0) + Number(w.current_balance||0); });
      return Object.entries(m).map(([n,a])=>({name:n,amount:a,...(CURR_CFG[n]||CURR_CFG.default)}));
    }
    // 🔄 fallback: summary.currency_breakdown (mock বা real summary)
    if (summary.currency_breakdown)
      return Object.entries(summary.currency_breakdown).map(([n,a])=>({name:n,amount:a,...(CURR_CFG[n]||CURR_CFG.default)}));
    return [];
  }, [wallets, summary]);

  const recentTx = useMemo(()=>transactions.slice(0,5).map(tx=>{
    const c=TX_CFG[(tx.type||'').toLowerCase()]||TX_CFG.default;
    const a=Number(tx.amount||0);
    return{...tx,icon:c.icon,color:c.color,fmtAmt:a>=0?`+$${fmt(Math.abs(a))}`:`-$${fmt(Math.abs(a))}`,timeAgo:ago(tx.created_at)};
  }),[transactions]);

  const wdCounts = useMemo(()=>({
    pending:    withdrawals.filter(w=>w.status==='pending').length,
    processing: withdrawals.filter(w=>w.status==='processing').length,
    completed:  withdrawals.filter(w=>w.status==='completed').length,
  }),[withdrawals]);

  // ✅ ACTIONS
  const handleTxApprove  = async(tx) => { setAL(`ta_${tx.id}`,true); const r=await sf(()=>API.approveTransaction(tx.id));  setAL(`ta_${tx.id}`,false); r?.success?toast('Approved!','success')&&fetchAll():toast(r?.error||'Failed','error'); if(r?.success)fetchAll(); };
  const handleTxReject   = async(tx) => { setAL(`tr_${tx.id}`,true); const r=await sf(()=>API.rejectTransaction(tx.id,{reason:'Rejected by admin'}));  setAL(`tr_${tx.id}`,false); if(r?.success){toast('Rejected','success');fetchAll();}else toast(r?.error||'Failed','error'); };
  const handleTxReverse  = async(tx) => { setAL(`tv_${tx.id}`,true); const r=await sf(()=>API.reverseTransaction(tx.id,{reason:'Reversed by admin'})); setAL(`tv_${tx.id}`,false); if(r?.success){toast('Reversed!','success');fetchAll();}else toast(r?.error||'Failed','error'); };
  const handleWdProcess  = async(wd) => { setAL(`wp_${wd.id}`,true); const r=await sf(()=>API.processWithdrawal(wd.id));   setAL(`wp_${wd.id}`,false); if(r?.success){toast('Processing!','success');fetchAll();}else toast(r?.error||'Failed','error'); };
  const handleWdComplete = async(wd) => { setAL(`wc_${wd.id}`,true); const r=await sf(()=>API.completeWithdrawal(wd.id,{}));setAL(`wc_${wd.id}`,false);if(r?.success){toast('Completed!','success');fetchAll();}else toast(r?.error||'Failed','error'); };
  const handleWdReject   = async(wd) => { setAL(`wr_${wd.id}`,true); const r=await sf(()=>API.rejectWithdrawal(wd.id,{reason:'Rejected'}));setAL(`wr_${wd.id}`,false);if(r?.success){toast('Rejected & refunded','success');fetchAll();}else toast(r?.error||'Failed','error'); };
  const handleSetPrimary   = async(m) => { const r=await sf(()=>API.setPrimaryMethod(m.id));   if(r?.success){toast('Set as primary!','success');fetchAll();}else toast('Failed','error'); };
  const handleVerifyMethod = async(m) => { const r=await sf(()=>API.verifyPayMethod(m.id));    if(r?.success){toast('Verified!','success');fetchAll();}else toast('Failed','error'); };
  const handleDeleteMethod = async(m) => { const r=await sf(()=>API.deletePayMethod(m.id));    if(r?.ok){setMethods(p=>p.filter(x=>x.id!==m.id));toast('Deleted','success');}else toast('Failed','error'); };
  const handleExpireBonuses  = async()  => { const r=await sf(API.expireBonuses);             r?.success?toast(r.message,'success'):toast('Failed','error'); };
  const handleSyncPayments   = async()  => { const r=await sf(API.syncPayments);              r?.success?toast('Synced!','success'):toast('Failed','error'); };
  const handleGenerateReport = async(t) => { const r=await sf(()=>API.generateReport({report_type:t})); r?.success?toast(`${t} report generated!`,'success'):toast('Failed','error'); };
  const handleCleanupLogs    = async()  => { const r=await sf(()=>API.cleanupLogs({days:30}));r?.success?toast(r.message,'success'):toast('Failed','error'); };
  const handleAutoProcess    = async()  => { const r=await sf(()=>API.autoProcessWd({hours:24}));r?.success?toast(r.message,'success'):toast('Failed','error'); };
  const handleBulkLock   = async() => { const ids=wallets.map(w=>w.user||w.id); const r=await sf(()=>API.bulkOperation({operation:'lock',  user_ids:ids,reason:'Bulk lock'}));   r?.success?toast(r.message,'success'):toast('Failed','error'); };
  const handleBulkUnlock = async() => { const ids=wallets.map(w=>w.user||w.id); const r=await sf(()=>API.bulkOperation({operation:'unlock',user_ids:ids})); r?.success?toast(r.message,'success'):toast('Failed','error'); };

  return (
    <div className="wl-root">
      <div className="wl-bg">
        <PageEndpointPanel pageKey="Wallet" title="Wallet Endpoints" />
        <div className="wl-orb wl-orb--1"/><div className="wl-orb wl-orb--2"/><div className="wl-orb wl-orb--3"/>
        <div className="wl-grid-overlay"/>
      </div>

      <div className="wl-layout">
        {/* SIDEBAR */}
        <aside className="wl-sidebar wl-glass">
          <div className="wl-sidebar__brand">
            <div className="wl-brand-orb">◈</div>
            <div><div className="wl-brand-name">GLOBAL<span>WALLET</span></div><div className="wl-brand-sub">Financial Terminal v2</div></div>
          </div>
          <div className={`wl-api-chip ${apiOnline?'green':'amber'}`}>
            <span className={`wl-dot ${apiOnline?'green':'amber'}`}/>{apiOnline?'API Connected':'Offline Mode'}
          </div>
          <nav className="wl-nav">
            {NAV.map(n=>(
              <button key={n.id} className={`wl-nav-item${tab===n.id?' active':''}`} onClick={()=>setTab(n.id)}>
                <span className="wl-nav-item__icon">{n.icon}</span>
                <span className="wl-nav-item__label">{n.label}</span>
                {tab===n.id&&<span className="wl-nav-item__pill"/>}
              </button>
            ))}
          </nav>
          <div className="wl-sidebar__footer">
            <div className="wl-user-chip wl-glass-inner">
              <div className="wl-user-avatar">{(summary.user?.name||'U')[0]}</div>
              <div><div className="wl-user-name">{summary.user?.name||'User'}</div><div className="wl-user-plan">{summary.user?.plan||'Member'}</div></div>
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <div className="wl-main">
          <header className="wl-topbar wl-glass">
            <div className="wl-topbar__left">
              <div className="wl-topbar__title">{NAV.find(n=>n.id===tab)?.label}</div>
              <div className="wl-topbar__sub">{loading&&<><span className="wl-spin">↻</span> Syncing…</>}</div>
            </div>
            <div className="wl-topbar__right">
              <button className="wl-btn wl-btn--ghost wl-btn--sm" onClick={()=>fetchAll(true)}><span className={loading?'wl-spin':''}>↻</span> Refresh</button>
              <button className="wl-btn wl-btn--primary wl-btn--sm" onClick={()=>setModal({type:'addFunds'})}>⊕ Add Funds</button>
              <button className="wl-btn wl-btn--danger  wl-btn--sm" onClick={()=>setModal({type:'withdraw'})}>↓ Withdraw</button>
            </div>
          </header>

          {/* ── DASHBOARD ── */}
          {tab==='dashboard'&&(
            <div className="wl-dash-grid">
              {/* Balance */}
              <div className="wl-card wl-glass wl-card--balance">
                <div className="wl-card__eyebrow"><span>GLOBAL BALANCE</span><span className="wl-live-chip">◉ LIVE</span></div>
                {loading?<Skel h={44} w="60%" r={8}/>:<div className="wl-balance-val">${fmt(summary.total_balance||0)}</div>}
                <div className={`wl-balance-change ${(summary.balance_change_pct||0)>=0?'up':'down'}`}>
                  {(summary.balance_change_pct||0)>=0?'▲':'▼'} {Math.abs(summary.balance_change_pct||0).toFixed(1)}% this month
                </div>
                <div className="wl-curr-chips">
                  {loading?[1,2,3,4].map(i=><Skel key={i} w={80} h={44} r={10}/>):
                    currBreakdown.map(c=>(
                      <div key={c.name} className="wl-curr-chip" style={{'--c':c.color}}>
                        <div className="wl-curr-chip__name">{c.name}</div>
                        <div className="wl-curr-chip__val">${fmt(c.amount)}</div>
                      </div>
                    ))
                  }
                </div>
                <div className="wl-card-actions">
                  <button className="wl-btn wl-btn--primary wl-btn--sm" onClick={()=>setModal({type:'withdraw'})}>↓ Withdraw</button>
                  <button className="wl-btn wl-btn--ghost   wl-btn--sm" onClick={()=>setModal({type:'addFunds'})}>⊕ Add Funds</button>
                </div>
              </div>

              {/* Mining */}
              <div className="wl-card wl-glass wl-card--mining">
                <div className="wl-card__eyebrow"><span>ACTIVE MINING</span></div>
                <div className="wl-gauge-wrap">
                  <div className="wl-gauge-glow" style={{background:`conic-gradient(#10b981 ${(summary.mining_gauge_pct||0)*100}%,transparent 0%)`}}/>
                  <svg width="110" height="110" className="wl-gauge-svg" style={{transform:'rotate(-90deg)'}}>
                    <circle cx="55" cy="55" r="44" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="10"/>
                    <circle cx="55" cy="55" r="44" fill="none" stroke="#10b981" strokeWidth="10"
                      strokeDasharray={`${2*Math.PI*44*(summary.mining_gauge_pct||0)} ${2*Math.PI*44}`}
                      strokeLinecap="round" style={{transition:'stroke-dasharray 1s ease'}}/>
                  </svg>
                  <div className="wl-gauge-center"><div className="wl-gauge-val">{summary.mining_speed||0}</div><div className="wl-gauge-unit">MH/s</div></div>
                </div>
                <div className="wl-mining-bars">
                  {(summary.mining_bars||[4,6,5,8,6,9,7,10,8,11,9,10]).map((h,i,a)=>(
                    <div key={i} className={`wl-bar${i===a.length-1?' active':''}`} style={{height:h*3+'px'}}/>
                  ))}
                </div>
                <button className={`wl-btn wl-btn--sm ${miningActive?'wl-btn--danger':'wl-btn--green'}`} onClick={()=>setMiningActive(p=>!p)}>
                  {miningActive?'⏹ Stop':'▶ Start'} Mining
                </button>
              </div>

              {/* Chart */}
              <div className="wl-card wl-glass wl-card--chart">
                <div className="wl-card__eyebrow"><span>MONTHLY GROWTH</span></div>
                {loading?<Skel h={170} r={8}/>:(summary.monthly_growth||[]).length>0?(
                  <ResponsiveContainer width="100%" height={170}>
                    <AreaChart data={summary.monthly_growth} margin={{top:6,right:6,bottom:0,left:-22}}>
                      <defs>
                        <linearGradient id="wlI" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10b981" stopOpacity={.35}/><stop offset="95%" stopColor="#10b981" stopOpacity={0}/></linearGradient>
                        <linearGradient id="wlE" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366f1" stopOpacity={.35}/><stop offset="95%" stopColor="#6366f1" stopOpacity={0}/></linearGradient>
                      </defs>
                      <XAxis dataKey="month" tick={{fill:'#64748b',fontSize:10}} axisLine={false} tickLine={false}/>
                      <YAxis tick={{fill:'#64748b',fontSize:9}} axisLine={false} tickLine={false}/>
                      <Tooltip content={<ChartTip/>}/>
                      <Legend iconType="circle" iconSize={7} wrapperStyle={{fontSize:10,color:'#94a3b8'}}/>
                      <Area type="monotone" dataKey="income"  name="Income"  stroke="#10b981" fill="url(#wlI)" strokeWidth={2} dot={{r:3,fill:'#10b981'}}/>
                      <Area type="monotone" dataKey="expense" name="Expense" stroke="#6366f1" fill="url(#wlE)" strokeWidth={2} dot={{r:3,fill:'#6366f1'}}/>
                    </AreaChart>
                  </ResponsiveContainer>
                ):<div className="wl-empty">No data</div>}
              </div>

              {/* Recent Transactions */}
              <div className="wl-card wl-glass wl-card--txlist">
                <div className="wl-card__eyebrow"><span>RECENT TRANSACTIONS</span><button className="wl-link" onClick={()=>setTab('transactions')}>View all →</button></div>
                {loading?[1,2,3,4].map(i=><Skel key={i} h={44} r={8}/>):
                  recentTx.map((tx,i)=>(
                    <div key={i} className="wl-tx-row">
                      <div className="wl-tx-icon" style={{'--c':tx.color}}>{tx.icon}</div>
                      <div className="wl-tx-info">
                        <div className="wl-tx-label">{tx.description||tx.type}</div>
                        <div className="wl-tx-meta"><span className="wl-badge" style={{'--c':sc(tx.status)}}>{tx.status}</span><span>{tx.timeAgo}</span></div>
                      </div>
                      <div className="wl-tx-amt" style={{color:tx.color}}>{tx.fmtAmt}</div>
                    </div>
                  ))
                }
              </div>

              {/* Withdrawal Counts */}
              <div className="wl-card wl-glass wl-card--wd">
                <div className="wl-card__eyebrow"><span>WITHDRAWALS</span><button className="wl-link" onClick={()=>setTab('withdrawals')}>View all →</button></div>
                <div className="wl-wd-stats">
                  {[{label:'Pending',count:wdCounts.pending,color:'#f59e0b'},{label:'Processing',count:wdCounts.processing,color:'#6366f1'},{label:'Completed',count:wdCounts.completed,color:'#10b981'}].map(s=>(
                    <div key={s.label} className="wl-wd-stat wl-glass-inner" style={{'--c':s.color}} onClick={()=>setTab('withdrawals')}>
                      <div className="wl-wd-stat__count">{s.count}</div>
                      <div className="wl-wd-stat__label">{s.label}</div>
                    </div>
                  ))}
                </div>
                <button className="wl-btn wl-btn--danger wl-btn--full" onClick={()=>setModal({type:'withdraw'})}>↓ New Withdrawal</button>
              </div>
            </div>
          )}

          {/* ── WALLETS ── */}
          {tab==='wallets'&&(
            <div className="wl-panel wl-glass">
              <div className="wl-panel__hdr"><div className="wl-panel__title">◈ Wallets</div><span className="wl-count-chip">{wallets.length}</span></div>
              <div className="wl-table-wrap">
                <table className="wl-table">
                  <thead><tr><th>Currency</th><th>Balance</th><th>Available</th><th>Pending</th><th>Frozen</th><th>Bonus</th><th>Status</th><th>Actions</th></tr></thead>
                  <tbody>
                    {wallets.map(w=>(
                      <tr key={w.id} className="wl-row">
                        <td><div className="wl-curr-tag" style={{'--c':(CURR_CFG[w.currency]||CURR_CFG.default).color}}>{w.currency}</div></td>
                        <td className="wl-td-val">${fmt(w.current_balance)}</td>
                        <td className="wl-td-sub">${fmt(w.available_balance)}</td>
                        <td className="wl-td-sub">${fmt(w.pending_balance)}</td>
                        <td className="wl-td-sub">${fmt(w.frozen_balance)}</td>
                        <td className="wl-td-sub">${fmt(w.bonus_balance)}</td>
                        <td><span className="wl-badge" style={{'--c':w.is_locked?'#ef4444':sc(w.status)}}>{w.is_locked?'LOCKED':(w.status||'active').toUpperCase()}</span></td>
                        <td>
                          <div className="wl-action-grp">
                            {w.is_locked
                              ?<button className="wl-act-btn wl-act-btn--green" title="Unlock"   onClick={()=>setModal({type:'walletAction',wallet:w,action:'unlock'})}>🔓</button>
                              :<button className="wl-act-btn" title="Lock"                        onClick={()=>setModal({type:'walletAction',wallet:w,action:'lock'})}>🔒</button>
                            }
                            <button className="wl-act-btn" title="Freeze"   onClick={()=>setModal({type:'walletAction',wallet:w,action:'freeze'})}>❄</button>
                            <button className="wl-act-btn" title="Unfreeze" onClick={()=>setModal({type:'walletAction',wallet:w,action:'unfreeze'})}>♨</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!wallets.length&&<div className="wl-empty">No wallets found</div>}
              </div>
            </div>
          )}

          {/* ── TRANSACTIONS ── */}
          {tab==='transactions'&&(
            <div className="wl-panel wl-glass">
              <div className="wl-panel__hdr"><div className="wl-panel__title">⇄ Transactions</div><span className="wl-count-chip">{transactions.length}</span></div>
              <div className="wl-table-wrap">
                <table className="wl-table">
                  <thead><tr><th>ID</th><th>Type</th><th>Amount</th><th>Description</th><th>Status</th><th>Date</th><th>Admin Actions</th></tr></thead>
                  <tbody>
                    {transactions.map(tx=>{
                      const c=TX_CFG[(tx.type||'').toLowerCase()]||TX_CFG.default;
                      const a=Number(tx.amount||0);
                      return(
                        <tr key={tx.id} className="wl-row">
                          <td className="wl-td-mono">{tx.transaction_id||`#${tx.id}`}</td>
                          <td><span className="wl-type-tag" style={{'--c':c.color}}>{c.icon} {(tx.type||'—').toUpperCase()}</span></td>
                          <td className="wl-td-val" style={{color:a>=0?'#10b981':'#ef4444'}}>{a>=0?'+':''}{fmt(a)}</td>
                          <td className="wl-td-sub">{tx.description||'—'}</td>
                          <td><span className="wl-badge" style={{'--c':sc(tx.status)}}>{(tx.status||'').toUpperCase()}</span></td>
                          <td className="wl-td-sub">{ago(tx.created_at)}</td>
                          <td>
                            <div className="wl-action-grp">
                              {tx.status==='pending'&&<>
                                <button className="wl-act-btn wl-act-btn--green" title="Approve" disabled={actionLoad[`ta_${tx.id}`]} onClick={()=>handleTxApprove(tx)}>{actionLoad[`ta_${tx.id}`]?<span className="wl-spin">↻</span>:'✓'}</button>
                                <button className="wl-act-btn wl-act-btn--red"   title="Reject"  disabled={actionLoad[`tr_${tx.id}`]} onClick={()=>handleTxReject(tx)}>{actionLoad[`tr_${tx.id}`]?<span className="wl-spin">↻</span>:'✕'}</button>
                              </>}
                              {tx.status==='approved'&&<button className="wl-act-btn" title="Reverse" disabled={actionLoad[`tv_${tx.id}`]} onClick={()=>handleTxReverse(tx)}>{actionLoad[`tv_${tx.id}`]?<span className="wl-spin">↻</span>:'↺'}</button>}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {!transactions.length&&<div className="wl-empty">No transactions</div>}
              </div>
            </div>
          )}

          {/* ── WITHDRAWALS ── */}
          {tab==='withdrawals'&&(
            <div className="wl-panel wl-glass">
              <div className="wl-panel__hdr">
                <div className="wl-panel__title">⬇ Withdrawals</div>
                <div className="wl-panel__meta"><span className="wl-count-chip">{withdrawals.length}</span><button className="wl-btn wl-btn--danger wl-btn--sm" onClick={()=>setModal({type:'withdraw'})}>+ New</button></div>
              </div>
              <div className="wl-table-wrap">
                <table className="wl-table">
                  <thead><tr><th>ID</th><th>Amount</th><th>Fee</th><th>Net</th><th>Status</th><th>Date</th><th>Admin Actions</th></tr></thead>
                  <tbody>
                    {withdrawals.map(wd=>(
                      <tr key={wd.id} className="wl-row">
                        <td className="wl-td-mono">{wd.withdrawal_id||`#${wd.id}`}</td>
                        <td className="wl-td-val">${fmt(wd.amount)}</td>
                        <td className="wl-td-sub">${fmt(wd.fee)}</td>
                        <td className="wl-td-sub" style={{color:'#10b981'}}>${fmt(wd.net_amount)}</td>
                        <td><span className="wl-badge" style={{'--c':sc(wd.status)}}>{(wd.status||'').toUpperCase()}</span></td>
                        <td className="wl-td-sub">{ago(wd.created_at)}</td>
                        <td>
                          <div className="wl-action-grp">
                            {wd.status==='pending'&&<>
                              <button className="wl-act-btn wl-act-btn--green" title="Process"  disabled={actionLoad[`wp_${wd.id}`]} onClick={()=>handleWdProcess(wd)}>{actionLoad[`wp_${wd.id}`]?<span className="wl-spin">↻</span>:'▶'}</button>
                              <button className="wl-act-btn wl-act-btn--red"   title="Reject"   disabled={actionLoad[`wr_${wd.id}`]} onClick={()=>handleWdReject(wd)}>{actionLoad[`wr_${wd.id}`]?<span className="wl-spin">↻</span>:'✕'}</button>
                            </>}
                            {wd.status==='processing'&&<button className="wl-act-btn wl-act-btn--green" title="Complete" disabled={actionLoad[`wc_${wd.id}`]} onClick={()=>handleWdComplete(wd)}>{actionLoad[`wc_${wd.id}`]?<span className="wl-spin">↻</span>:'✓'}</button>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!withdrawals.length&&<div className="wl-empty">No withdrawals</div>}
              </div>
            </div>
          )}

          {/* ── PAYMENT METHODS ── */}
          {tab==='methods'&&(
            <div className="wl-panel wl-glass">
              <div className="wl-panel__hdr"><div className="wl-panel__title">▣ Payment Methods</div><button className="wl-btn wl-btn--primary wl-btn--sm" onClick={()=>setModal({type:'addMethod'})}>+ Add</button></div>
              <div className="wl-methods-grid">
                {methods.map(m=>(
                  <div key={m.id} className={`wl-method-card wl-glass-inner${m.is_primary?' primary':''}`}>
                    <div className="wl-method-card__hdr">
                      <div><div className="wl-method-card__type">{m.method_type_display||m.method_type}</div><div className="wl-method-card__name">{m.account_name}</div><div className="wl-method-card__num">{m.account_number}</div></div>
                      <div className="wl-method-card__badges">{m.is_primary&&<span className="wl-badge" style={{'--c':'#f59e0b'}}>PRIMARY</span>}{m.is_verified&&<span className="wl-badge" style={{'--c':'#10b981'}}>VERIFIED</span>}</div>
                    </div>
                    <div className="wl-action-grp" style={{marginTop:12}}>
                      <button className="wl-act-btn wl-act-btn--edit"  title="Edit"        onClick={()=>setModal({type:'editMethod',method:m})}>✎</button>
                      {!m.is_primary  &&<button className="wl-act-btn" title="Set Primary" onClick={()=>handleSetPrimary(m)}>★</button>}
                      {!m.is_verified &&<button className="wl-act-btn wl-act-btn--green" title="Verify" onClick={()=>handleVerifyMethod(m)}>✓</button>}
                      <button className="wl-act-btn wl-act-btn--red" title="Delete" onClick={()=>handleDeleteMethod(m)}>✕</button>
                    </div>
                  </div>
                ))}
                {!methods.length&&<div className="wl-empty">No payment methods</div>}
              </div>
            </div>
          )}

          {/* ── ADMIN ── */}
          {tab==='admin'&&(
            <div className="wl-admin-grid">
              <div className="wl-panel wl-glass">
                <div className="wl-panel__hdr"><div className="wl-panel__title">⚙ Admin Operations</div></div>
                <div className="wl-admin-ops">
                  {[
                    {label:'Expire Bonuses',  icon:'⏰',fn:handleExpireBonuses,            color:'#f59e0b',desc:'Expire all overdue bonus balances'},
                    {label:'Sync Payments',   icon:'⟳', fn:handleSyncPayments,             color:'#6366f1',desc:'Sync with payment gateways'},
                    {label:'Auto-Process WDs',icon:'▶', fn:handleAutoProcess,              color:'#10b981',desc:'Auto-process pending withdrawals (24h+)'},
                    {label:'Cleanup Logs',    icon:'🗑', fn:handleCleanupLogs,              color:'#ef4444',desc:'Delete processed webhook logs (30d+)'},
                    {label:'Daily Report',    icon:'📊',fn:()=>handleGenerateReport('daily'),  color:'#06b6d4',desc:'Generate daily financial report'},
                    {label:'Monthly Report',  icon:'📈',fn:()=>handleGenerateReport('monthly'),color:'#8b5cf6',desc:'Generate monthly financial report'},
                  ].map(op=>(
                    <div key={op.label} className="wl-admin-op wl-glass-inner" style={{'--c':op.color}}>
                      <div className="wl-admin-op__icon">{op.icon}</div>
                      <div className="wl-admin-op__info"><div className="wl-admin-op__label">{op.label}</div><div className="wl-admin-op__desc">{op.desc}</div></div>
                      <button className="wl-btn wl-btn--ghost wl-btn--sm" onClick={op.fn} style={{borderColor:op.color+'44',color:op.color}}>Run</button>
                    </div>
                  ))}
                </div>
              </div>
              <div className="wl-panel wl-glass">
                <div className="wl-panel__hdr"><div className="wl-panel__title">⚡ Bulk Operations</div></div>
                <div style={{padding:'20px'}}>
                  <div className="wl-fee-box" style={{marginBottom:16}}>Affects ALL wallets. Use with caution.</div>
                  <div style={{display:'flex',gap:10}}>
                    <button className="wl-btn wl-btn--danger" onClick={handleBulkLock}>🔒 Lock All</button>
                    <button className="wl-btn wl-btn--green"  onClick={handleBulkUnlock}>🔓 Unlock All</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── WEBHOOKS ── */}
          {tab==='webhooks'&&(
            <div className="wl-panel wl-glass">
              <div className="wl-panel__hdr"><div className="wl-panel__title">⚡ Webhook Logs</div><span className="wl-count-chip">{webhooks.length}</span></div>
              <div className="wl-table-wrap">
                <table className="wl-table">
                  <thead><tr><th>Type</th><th>Event</th><th>Processed</th><th>Received</th><th>Error</th></tr></thead>
                  <tbody>
                    {webhooks.map((wh,i)=>(
                      <tr key={i} className="wl-row">
                        <td><span className="wl-type-tag" style={{'--c':'#6366f1'}}>{wh.webhook_type||'—'}</span></td>
                        <td className="wl-td-sub">{wh.event_type||'—'}</td>
                        <td><span className="wl-badge" style={{'--c':wh.is_processed?'#10b981':'#f59e0b'}}>{wh.is_processed?'YES':'NO'}</span></td>
                        <td className="wl-td-sub">{ago(wh.received_at)}</td>
                        <td className="wl-td-sub" style={{color:'#ef4444'}}>{wh.processing_error||'—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!webhooks.length&&<div className="wl-empty">No webhook logs</div>}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* MODALS */}
      {modal?.type==='withdraw'     &&<WithdrawModal    methods={methods} onClose={()=>setModal(null)} toast={toast} onSuccess={fetchAll}/>}
      {modal?.type==='addFunds'     &&<AddFundsModal                      onClose={()=>setModal(null)} toast={toast} onSuccess={fetchAll}/>}
      {modal?.type==='addMethod'    &&<PayMethodModal   method={null}     onClose={()=>setModal(null)} toast={toast} onSuccess={fetchAll} userId={summary?.user?.id}/>}
      {modal?.type==='editMethod'   &&<PayMethodModal   method={modal.method} onClose={()=>setModal(null)} toast={toast} onSuccess={fetchAll} userId={summary?.user?.id}/>}
      {modal?.type==='walletAction' &&<WalletActionModal wallet={modal.wallet} action={modal.action} onClose={()=>setModal(null)} toast={toast} onSuccess={fetchAll}/>}

      <Toasts list={toasts}/>
    </div>
  );
}



// // src/pages/Wallet.jsx
// import React, { useState, useCallback } from 'react';
// import {
//   useWallets, useWalletDashboardStats,
//   useTransactions, useWithdrawalRequests,
// } from '../hooks/useWallet';
// import walletAPI from '../api/endpoints/wallet';
// import {
//   LayoutDashboard, Wallet as WalletIcon, ArrowLeftRight, TrendingUp,
//   Pickaxe, ArrowDownCircle, ClipboardList, CreditCard, Webhook,
//   FileBarChart, Settings, HeadphonesIcon, ChevronRight, Search,
//   Globe, Bell, Puzzle, Users, ChevronDown, Send, DollarSign,
//   Star, CheckCircle, AlertCircle, ArrowUpRight, ArrowDownLeft,
//   RotateCcw, Trophy, Loader2, RefreshCw, Activity, X, Check,
// } from 'lucide-react';
// import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

// // ─── Constants ────────────────────────────────────────────────────────────────
// const navItems = [
//   { icon: LayoutDashboard, label: 'Dashboard',      hasArrow: false },
//   { icon: WalletIcon,      label: 'Wallets',         hasArrow: true  },
//   { icon: ArrowLeftRight,  label: 'Transactions',    hasArrow: true  },
//   { icon: TrendingUp,      label: 'Investments',     hasArrow: true  },
//   { icon: Pickaxe,         label: 'Mining',          hasArrow: true  },
//   { icon: ArrowDownCircle, label: 'Withdrawals',     hasArrow: true  },
//   { icon: ClipboardList,   label: 'Requests',        hasArrow: true  },
//   { icon: CreditCard,      label: 'Payment Methods', hasArrow: false },
//   { icon: Webhook,         label: 'Webhooks',        hasArrow: false },
//   { icon: FileBarChart,    label: 'Reports',         hasArrow: false },
//   { icon: Settings,        label: 'Settings',        hasArrow: false },
// ];

// const CURRENCY_CONFIG = {
//   USD:  { color: '#d8210d', bg: '#d8210d22' },
//   EUR:  { color: '#3498db', bg: '#0d93ec22' },
//   BTC:  { color: '#1246f3', bg: '#f107ab22' },
//   USDT: { color: '#2ecc71', bg: '#2ecc7122' },
//   USST: { color: '#2ecc71', bg: '#2ecc7122' },
//   BDT:  { color: '#d8210d', bg: '#9ae70c22' }, 
// };

// const PACKAGE_CONFIG = [
//   { name: 'Bronze',   color: '#cd7f32', glow: '#cd7f3266', border: '#cd7f32' },
//   { name: 'Silver',   color: '#c0c0c0', glow: '#c0c0c066', border: '#3498db' },
//   { name: 'Gold',     color: '#ffd700', glow: '#ffd70066', border: '#2ecc71' },
//   { name: 'Platinum', color: '#e056fd', glow: '#e056fd66', border: '#9b59b6' },
// ];

// const TX_ICON_MAP = {
//   earning:       { icon: CheckCircle,   color: '#2ecc71' },
//   reward:        { icon: Trophy,        color: '#f39c12' },
//   referral:      { icon: Users,         color: '#3498db' },
//   bonus:         { icon: Star,          color: '#f39c12' },
//   withdrawal:    { icon: ArrowDownLeft, color: '#e74c3c' },
//   withdrawal_fee:{ icon: ArrowDownLeft, color: '#e74c3c' },
//   admin_credit:  { icon: ArrowUpRight,  color: '#2ecc71' },
//   admin_debit:   { icon: ArrowDownLeft, color: '#e74c3c' },
//   reversal:      { icon: RotateCcw,     color: '#3498db' },
//   default:       { icon: ArrowUpRight,  color: '#7f8c8d' },
// };

// // ─── Toast ────────────────────────────────────────────────────────────────────
// const Toast = ({ msg, type, onClose }) => (
//   <div style={{
//     position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
//     background: type === 'success' ? '#1a4a2a' : type === 'error' ? '#4a1a1a' : '#1a2a4a',
//     border: `1px solid ${type === 'success' ? '#2ecc71' : type === 'error' ? '#e74c3c' : '#3498db'}44`,
//     borderRadius: 10, padding: '12px 18px',
//     display: 'flex', alignItems: 'center', gap: 10,
//     color: '#fff', fontSize: 13, fontWeight: 500,
//     boxShadow: '0 8px 32px #00000066',
//     animation: 'fadeUp .3s ease both',
//     maxWidth: 340,
//   }}>
//     {type === 'success' && <Check style={{ width: 16, height: 16, color: '#2ecc71', flexShrink: 0 }} />}
//     {type === 'error'   && <AlertCircle style={{ width: 16, height: 16, color: '#e74c3c', flexShrink: 0 }} />}
//     {type === 'loading' && <Loader2 style={{ width: 16, height: 16, color: '#3498db', flexShrink: 0, animation: 'spin 1s linear infinite' }} />}
//     <span style={{ flex: 1 }}>{msg}</span>
//     <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#aaa', cursor: 'pointer', padding: 0 }}>
//       <X style={{ width: 14, height: 14 }} />
//     </button>
//   </div>
// );

// // ─── Withdrawal Modal ─────────────────────────────────────────────────────────
// const WithdrawalModal = ({ wallets, onClose, onSuccess, showToast }) => {
//   const [form, setForm]     = useState({ amount: '', payment_method_id: '', note: '' });
//   const [methods, setMethods] = useState([]);
//   const [loading, setLoading] = useState(false);
//   const [methodsLoading, setMethodsLoading] = useState(true);

//   React.useEffect(() => {
//     walletAPI.getPaymentMethods()
//       .then(r => setMethods(r.data?.results ?? r.data ?? []))
//       .catch(() => setMethods([]))
//       .finally(() => setMethodsLoading(false));
//   }, []);

//   const handleSubmit = async () => {
//     if (!form.amount || Number(form.amount) <= 0) {
//       showToast('Please enter a valid amount', 'error'); return;
//     }
//     if (!form.payment_method_id) {
//       showToast('Please select a payment method', 'error'); return;
//     }
//     setLoading(true);
//     try {
//       await walletAPI.requestWithdrawal({
//         amount: form.amount,
//         payment_method_id: form.payment_method_id,
//         note: form.note,
//       });
//       showToast('Withdrawal request submitted!', 'success');
//       onSuccess();
//       onClose();
//     } catch (err) {
//       showToast(err?.response?.data?.error || 'Withdrawal failed', 'error');
//     } finally {
//       setLoading(false);
//     }
//   };

//   const inputStyle = {
//     width: '100%', background: '#060d18', border: '1px solid #1e3a5f',
//     borderRadius: 8, padding: '10px 14px', color: '#fff',
//     fontSize: 12, outline: 'none', boxSizing: 'border-box',
//     transition: 'border-color .2s',
//   };

//   return (
//     <div style={{
//       position: 'fixed', inset: 0, zIndex: 1000, background: '#000a',
//       display: 'flex', alignItems: 'center', justifyContent: 'center',
//       backdropFilter: 'blur(6px)',
//     }}>
//       <div style={{
//         background: 'linear-gradient(135deg, #0d1b2a, #0a1628)',
//         border: '1px solid #1e3a5f', borderRadius: 14,
//         padding: 28, width: 400, maxWidth: '92vw',
//         animation: 'fadeUp .3s ease both',
//         boxShadow: '0 24px 80px #00000088',
//       }}>
//         <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
//           <div style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>Request Withdrawal</div>
//           <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7f8c8d' }}>
//             <X style={{ width: 18, height: 18 }} />
//           </button>
//         </div>

//         {/* Amount */}
//         <div style={{ marginBottom: 12 }}>
//           <div style={{ fontSize: 11, color: '#7f8c8d', marginBottom: 5, letterSpacing: 1 }}>AMOUNT (USD)</div>
//           <input
//             type="number" placeholder="0.00" value={form.amount}
//             onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
//             style={inputStyle}
//             onFocus={e => e.target.style.borderColor = '#2ecc7166'}
//             onBlur={e => e.target.style.borderColor = '#1e3a5f'}
//           />
//         </div>

//         {/* Payment Method */}
//         <div style={{ marginBottom: 12 }}>
//           <div style={{ fontSize: 11, color: '#7f8c8d', marginBottom: 5, letterSpacing: 1 }}>PAYMENT METHOD</div>
//           {methodsLoading ? (
//             <div style={{ ...inputStyle, color: '#7f8c8d' }}>Loading methods…</div>
//           ) : methods.length === 0 ? (
//             <div style={{ ...inputStyle, color: '#e74c3c', fontSize: 11 }}>
//               No payment methods found. Add one in Payment Methods.
//             </div>
//           ) : (
//             <select
//               value={form.payment_method_id}
//               onChange={e => setForm(f => ({ ...f, payment_method_id: e.target.value }))}
//               style={{ ...inputStyle, cursor: 'pointer' }}
//             >
//               <option value="" style={{ background: '#0d1b2a' }}>Select method…</option>
//               {methods.map(m => (
//                 <option key={m.id} value={m.id} style={{ background: '#0d1b2a' }}>
//                   {m.method_type_display || m.method_type} — {m.account_name || m.account_number || ''}
//                 </option>
//               ))}
//             </select>
//           )}
//         </div>

//         {/* Note */}
//         <div style={{ marginBottom: 20 }}>
//           <div style={{ fontSize: 11, color: '#7f8c8d', marginBottom: 5, letterSpacing: 1 }}>NOTE (optional)</div>
//           <input
//             type="text" placeholder="Any note…" value={form.note}
//             onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
//             style={inputStyle}
//             onFocus={e => e.target.style.borderColor = '#2ecc7166'}
//             onBlur={e => e.target.style.borderColor = '#1e3a5f'}
//           />
//         </div>

//         {/* Fee note */}
//         {form.amount && Number(form.amount) > 0 && (
//           <div style={{
//             background: '#f39c1214', border: '1px solid #f39c1233',
//             borderRadius: 8, padding: '8px 12px', marginBottom: 16, fontSize: 11, color: '#f39c12',
//           }}>
//             Fee: ${(Number(form.amount) * 0.02).toFixed(2)} (2%) →
//             You receive: ${(Number(form.amount) * 0.98).toFixed(2)}
//           </div>
//         )}

//         <div style={{ display: 'flex', gap: 10 }}>
//           <button onClick={onClose} style={{
//             flex: 1, background: 'none', border: '1px solid #1e3a5f',
//             borderRadius: 8, padding: '11px', color: '#7f8c8d',
//             fontSize: 13, cursor: 'pointer',
//           }}>Cancel</button>
//           <button onClick={handleSubmit} disabled={loading} style={{
//             flex: 2, background: 'linear-gradient(135deg, #e74c3c, #c0392b)',
//             border: 'none', borderRadius: 8, padding: '11px',
//             color: '#fff', fontWeight: 700, fontSize: 13,
//             cursor: loading ? 'not-allowed' : 'pointer',
//             display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
//             boxShadow: '0 4px 16px #e74c3c44', opacity: loading ? .7 : 1,
//           }}>
//             {loading && <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />}
//             {loading ? 'Submitting…' : 'Submit Request'}
//           </button>
//         </div>
//       </div>
//     </div>
//   );
// };

// // ─── Skeleton ─────────────────────────────────────────────────────────────────
// const Skeleton = ({ w = '100%', h = 16, radius = 6, style = {} }) => (
//   <div style={{
//     width: w, height: h, borderRadius: radius,
//     background: 'linear-gradient(90deg,#1e3a5f33 25%,#1e3a5f66 50%,#1e3a5f33 75%)',
//     backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite', ...style,
//   }} />
// );

// const CustomTooltip = ({ active, payload, label }) => {
//   if (!active || !payload?.length) return null;
//   return (
//     <div style={{ background:'#0d1b2a', border:'1px solid #1e3a5f', borderRadius:8, padding:'8px 14px' }}>
//       <p style={{ color:'#aaa', fontSize:11, marginBottom:4 }}>{label}</p>
//       {payload.map((p, i) => (
//         <p key={i} style={{ color:p.color, fontSize:12, margin:0, fontWeight:600 }}>
//           {p.name}: ${p.value?.toLocaleString()}
//         </p>
//       ))}
//     </div>
//   );
// };

// const PulseDot = ({ color = '#2ecc71' }) => (
//   <span style={{ position:'relative', display:'inline-flex', width:10, height:10 }}>
//     <span style={{ position:'absolute', inset:0, borderRadius:'50%', background:color, opacity:.4, animation:'ping 1.5s cubic-bezier(0,0,.2,1) infinite' }} />
//     <span style={{ width:8, height:8, borderRadius:'50%', background:color, margin:'auto' }} />
//   </span>
// );

// // ─── MAIN ─────────────────────────────────────────────────────────────────────
// export default function Wallet() {
//   const [activeNav, setActiveNav]         = useState('Dashboard');
//   const [miningActive, setMiningActive]   = useState(false);
//   const [miningLoading, setMiningLoading] = useState(false);
//   const [transferForm, setTransferForm]   = useState({ recipient:'', amount:'', currency:'USD' });
//   const [transferLoading, setTransferLoading] = useState(false);
//   const [showWithdrawModal, setShowWithdrawModal] = useState(false);
//   const [toast, setToast]                 = useState(null);

//   // ── Hooks ─────────────────────────────────────────────────────────────────
//   const { wallets,       loading: wLoading                          } = useWallets();
//   const { stats,         loading: sLoading, error: sError, refetch: refetchStats } = useWalletDashboardStats();
//   const { transactions:  txList, loading: txLoading, error: txError, refetch: refetchTx } = useTransactions();
//   const { requests,      loading: rLoading, error: rError,  refetch: refetchReq  } = useWithdrawalRequests({ status: '' });

//   const isLoadingAny = wLoading || sLoading || txLoading || rLoading;

//   // ── Toast helper ──────────────────────────────────────────────────────────
//   const showToast = useCallback((msg, type = 'success') => {
//     setToast({ msg, type });
//     if (type !== 'loading') setTimeout(() => setToast(null), 3500);
//   }, []);

//   // ── Refetch all ───────────────────────────────────────────────────────────
//   const refetchAll = useCallback(() => {
//     refetchStats(); refetchTx(); refetchReq();
//   }, [refetchStats, refetchTx, refetchReq]);

//   // ── Derived data ──────────────────────────────────────────────────────────
//   const totalBalance    = stats?.total_balance       ?? 0;
//   const balanceChange   = stats?.balance_change_pct  ?? 0;
//   const miningSpeed     = stats?.mining_speed        ?? 0;
//   const miningGaugeVal  = stats?.mining_gauge_pct    ?? 0;
//   const monthlyData     = stats?.monthly_growth      ?? [];
//   const miningBars      = stats?.mining_bars         ?? [4,7,5,8,6,9,7,10,8,11,9,8];

//   const currencyBreakdown = React.useMemo(() => {
//     if (Array.isArray(wallets) && wallets.length > 0) {

//     // Duplicate currency merge করো
//       const merged = {};
//       wallets.forEach(w => {
//         const bal = Number(w.current_balance ?? w.balance ?? 0);
//         if (merged[w.currency]) {
//           merged[w.currency].rawAmount += bal;
//          } else {
//           merged[w.currency] = {
//              name: w.currency,
//           rawAmount: bal,
//           ...(CURRENCY_CONFIG[w.currency] || { color:'#7f8c8d', bg:'#7f8c8d22' }),
//         };
//       }
//     });
//     return Object.values(merged).map(item => ({
//       ...item,
//       amount: item.rawAmount.toLocaleString(),
//     }));
//   }
//   if (stats?.currency_breakdown)
//     return Object.entries(stats.currency_breakdown).map(([name, amount]) => ({
//       name, amount: Number(amount).toLocaleString(),
//       ...(CURRENCY_CONFIG[name] || { color:'#7f8c8d', bg:'#7f8c8d22' }),
//     }));
//   return [];
// }, [wallets, stats]);

//   const packages = React.useMemo(() =>
//     (stats?.investment_packages ?? []).map((pkg, i) => ({
//       ...pkg, ...(PACKAGE_CONFIG[i] || PACKAGE_CONFIG[3]),
//     })), [stats]);

//   function timeAgo(d) {
//     const s = (Date.now() - new Date(d)) / 1000;
//     if (s < 60)   return `${Math.floor(s)}s ago`;
//     if (s < 3600) return `${Math.floor(s/60)} min ago`;
//     if (s < 86400)return `${Math.floor(s/3600)} hr ago`;
//     return `${Math.floor(s/86400)}d ago`;
//   }

//   const recentTx = React.useMemo(() => {
//     if (!Array.isArray(txList)) return [];
//     return txList.slice(0,4).map(tx => {
//       const cfg = TX_ICON_MAP[(tx.type||'').toLowerCase()] || TX_ICON_MAP.default;
//       const amt = Number(tx.amount ?? 0);
//       return {
//         icon:   cfg.icon,
//         label:  tx.description || tx.transaction_type_display || tx.type || 'Transaction',
//         amount: amt >= 0 ? `+$${Math.abs(amt).toLocaleString()}` : `-$${Math.abs(amt).toLocaleString()}`,
//         time:   tx.created_at ? timeAgo(tx.created_at) : '—',
//         color:  cfg.color,
//         id:     tx.transaction_id || tx.id,
//       };
//     });
//   }, [txList]);

//   const recentActivity = React.useMemo(() => {
//     if (!Array.isArray(txList)) return [];
//     return txList.slice(0,3).map(tx => {
//       const cfg = TX_ICON_MAP[(tx.type||'').toLowerCase()] || TX_ICON_MAP.default;
//       const amt = Number(tx.amount ?? 0);
//       return {
//         icon: cfg.icon, label: tx.description || tx.type || 'Transaction',
//         sub:  amt >= 0 ? `+$${Math.abs(amt).toLocaleString()}` : `-$${Math.abs(amt).toLocaleString()}`,
//         status: tx.status === 'approved' || tx.status === 'completed' ? 'Approved' : null,
//         statusColor:'#2ecc71', bg: cfg.color+'22', iconColor: cfg.color,
//       };
//     });
//   }, [txList]);

//   const pendingCount    = Array.isArray(requests) ? requests.filter(r=>r.status==='pending').length    : 0;
//   const processingCount = Array.isArray(requests) ? requests.filter(r=>r.status==='processing').length : 0;
//   const completedCount  = Array.isArray(requests) ? requests.filter(r=>r.status==='completed').length  : 0;

//   // ── ACTION: Quick Transfer ────────────────────────────────────────────────
//   const handleTransfer = async () => {
//     if (!transferForm.recipient.trim()) { showToast('Enter recipient address', 'error'); return; }
//     if (!transferForm.amount || Number(transferForm.amount) <= 0) { showToast('Enter valid amount', 'error'); return; }
//     setTransferLoading(true);
//     showToast('Processing transfer…', 'loading');
//     try {
//       await walletAPI.quickTransfer({
//         recipient: transferForm.recipient,
//         amount:    transferForm.amount,
//         currency:  transferForm.currency,
//       });
//       setToast(null);
//       showToast(`$${transferForm.amount} sent successfully!`, 'success');
//       setTransferForm({ recipient:'', amount:'', currency:'USD' });
//       refetchAll();
//     } catch (err) {
//       setToast(null);
//       showToast(err?.response?.data?.error || 'Transfer failed', 'error');
//     } finally {
//       setTransferLoading(false);
//     }
//   };

//   // ── ACTION: Mining Toggle ─────────────────────────────────────────────────
//   const handleMiningToggle = async () => {
//     setMiningLoading(true);
//     try {
//       if (miningActive) {
//         await walletAPI.stopMining();
//         setMiningActive(false);
//         showToast('Mining stopped', 'success');
//       } else {
//         await walletAPI.startMining();
//         setMiningActive(true);
//         showToast('Mining started!', 'success');
//       }
//       refetchStats();
//     } catch (err) {
//       showToast(err?.response?.data?.error || 'Mining action failed', 'error');
//     } finally {
//       setMiningLoading(false);
//     }
//   };

//   // ── Shared styles ─────────────────────────────────────────────────────────
//   const cardStyle = {
//     background: 'linear-gradient(135deg,#0d1b2a,#0a1628)',
//     border: '1px solid #1e3a5f', borderRadius: 14, padding: 18,
//   };

//   const inputStyle = {
//     background:'#060d18', border:'1px solid #1e3a5f', borderRadius:8,
//     padding:'10px 12px', marginBottom:8,
//     display:'flex', alignItems:'center', gap:8,
//   };

//   return (
//     <div style={{ display:'flex', height:'100vh', background:'#060d18', fontFamily:"'Segoe UI',sans-serif", overflow:'hidden', color:'#fff' }}>
//       <style>{`
//         @keyframes pulse   {0%,100%{opacity:1}50%{opacity:.4}}
//         @keyframes ping    {75%,100%{transform:scale(1.8);opacity:0}}
//         @keyframes shimmer {0%{background-position:200% 0}100%{background-position:-200% 0}}
//         @keyframes spin    {from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
//         @keyframes fadeUp  {from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
//         @keyframes glow    {0%,100%{box-shadow:0 0 12px #2ecc7166}50%{box-shadow:0 0 24px #2ecc71aa}}
//         ::-webkit-scrollbar{width:4px}
//         ::-webkit-scrollbar-track{background:#060d18}
//         ::-webkit-scrollbar-thumb{background:#1e3a5f;border-radius:2px}
//         .nav-item:hover{background:#1e3a5f22!important}
//         .pkg-card:hover{transform:translateY(-3px)!important;filter:brightness(1.08)}
//         .tx-row:hover{background:#1e3a5f18!important;border-radius:8px}
//         .btn-hover:hover{opacity:.85;transform:translateY(-1px)}
//         .content-grid{animation:fadeUp .4s ease both}
//       `}</style>

//       {/* ── SIDEBAR ─────────────────────────────────────────────────────────── */}
//       <aside style={{
//         width:220, background:'linear-gradient(180deg,#0a1628 0%,#060d18 100%)',
//         borderRight:'1px solid #1e3a5f', display:'flex', flexDirection:'column',
//         flexShrink:0, overflowY:'auto',
//       }}>
//         <div style={{ padding:'20px 16px 12px', display:'flex', alignItems:'center', gap:10 }}>
//           <div style={{ width:36, height:36, borderRadius:8, background:'linear-gradient(135deg,#1a6cf0,#0a3d8f)', display:'flex', alignItems:'center', justifyContent:'center', boxShadow:'0 0 16px #1a6cf077', animation:'glow 3s ease infinite' }}>
//             <Globe style={{ width:18, height:18, color:'#fff' }} />
//           </div>
//           <div>
//             <span style={{ fontWeight:800, fontSize:13, color:'#fff', letterSpacing:1 }}>GLOBAL </span>
//             <span style={{ fontWeight:800, fontSize:13, color:'#1a6cf0', letterSpacing:1 }}>WALLET</span>
//             <div style={{ fontSize:9, color:'#aaa', letterSpacing:2 }}>HUB</div>
//           </div>
//         </div>

//         {isLoadingAny && (
//           <div style={{ display:'flex', alignItems:'center', gap:6, padding:'4px 16px 8px', fontSize:10, color:'#1a6cf0' }}>
//             <Loader2 style={{ width:10, height:10, animation:'spin 1s linear infinite' }} />
//             Syncing data…
//           </div>
//         )}

//         <nav style={{ flex:1, padding:'8px 0' }}>
//           {navItems.map(({ icon: Icon, label, hasArrow }) => (
//             <div key={label} className="nav-item" onClick={() => setActiveNav(label)} style={{
//               display:'flex', alignItems:'center', justifyContent:'space-between',
//               padding:'10px 16px', cursor:'pointer', borderRadius:8, margin:'1px 8px',
//               background: activeNav===label ? 'linear-gradient(90deg,#1a6cf022,#1a6cf011)' : 'transparent',
//               borderLeft: activeNav===label ? '3px solid #2ecc71' : '3px solid transparent',
//               transition:'all 0.2s',
//             }}>
//               <div style={{ display:'flex', alignItems:'center', gap:10 }}>
//                 <Icon style={{ width:16, height:16, color: activeNav===label ? '#2ecc71' : '#7f8c8d' }} />
//                 <span style={{ fontSize:13, color: activeNav===label ? '#fff' : '#95a5a6', fontWeight: activeNav===label ? 600 : 400 }}>{label}</span>
//               </div>
//               {hasArrow && <ChevronRight style={{ width:12, height:12, color:'#7f8c8d' }} />}
//             </div>
//           ))}
//         </nav>

//         <div style={{ margin:12, padding:'12px 14px', borderRadius:10, background:'linear-gradient(135deg,#0a3d8f22,#1a6cf011)', border:'1px solid #1e3a5f' }}>
//           <div style={{ display:'flex', alignItems:'center', gap:8 }}>
//             <div style={{ width:32, height:32, borderRadius:'50%', background:'#1a6cf022', display:'flex', alignItems:'center', justifyContent:'center' }}>
//               <HeadphonesIcon style={{ width:14, height:14, color:'#1a6cf0' }} />
//             </div>
//             <div>
//               <div style={{ fontSize:12, fontWeight:600, color:'#fff' }}>Live Support</div>
//               <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:10, color:'#2ecc71' }}>
//                 <PulseDot color="#2ecc71" /> 24/7 Online
//               </div>
//             </div>
//           </div>
//         </div>
//       </aside>

//       {/* ── MAIN ────────────────────────────────────────────────────────────── */}
//       <main style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden' }}>

//         {/* Top Bar */}
//         <header style={{ height:56, background:'#0a1628', borderBottom:'1px solid #1e3a5f', display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 20px', flexShrink:0 }}>
//           <div style={{ display:'flex', alignItems:'center', gap:8, background:'#060d18', border:'1px solid #1e3a5f', borderRadius:20, padding:'6px 14px', width:240 }}>
//             <Search style={{ width:14, height:14, color:'#7f8c8d' }} />
//             <input placeholder="Search Transactions…" style={{ background:'none', border:'none', outline:'none', color:'#aaa', fontSize:12, width:'100%' }} />
//           </div>
//           <div style={{ display:'flex', alignItems:'center', gap:14 }}>
//             <button onClick={refetchAll} className="btn-hover" style={{ background:'none', border:'1px solid #1e3a5f', borderRadius:8, padding:'5px 8px', cursor:'pointer', display:'flex', alignItems:'center', gap:4, transition:'all .2s' }}>
//               <RefreshCw style={{ width:13, height:13, color: isLoadingAny ? '#1a6cf0' : '#7f8c8d', animation: isLoadingAny ? 'spin 1s linear infinite' : 'none' }} />
//             </button>
//             <div style={{ width:32, height:24, borderRadius:4, overflow:'hidden', background:'linear-gradient(180deg,#e74c3c 33%,#fff 33% 66%,#e74c3c 66%)', border:'1px solid #1e3a5f' }} />
//             <Bell style={{ width:18, height:18, color:'#7f8c8d', cursor:'pointer' }} />
//             <div style={{ position:'relative' }}>
//               <Puzzle style={{ width:18, height:18, color:'#7f8c8d', cursor:'pointer' }} />
//               <div style={{ position:'absolute', top:-4, right:-4, width:8, height:8, borderRadius:'50%', background:'#e74c3c' }} />
//             </div>
//             <Users style={{ width:18, height:18, color:'#7f8c8d', cursor:'pointer' }} />
//             <div style={{ width:1, height:20, background:'#1e3a5f' }} />
//             <div style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
//               <img src={stats?.user?.avatar || 'https://i.pravatar.cc/32'} alt="avatar" style={{ width:32, height:32, borderRadius:'50%', border:'2px solid #1a6cf0' }} />
//               <div>
//                 <div style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{stats?.user?.name || 'User'}</div>
//                 <div style={{ fontSize:10, color:'#f39c12' }}>● {stats?.user?.plan || 'Member'}</div>
//               </div>
//               <ChevronDown style={{ width:12, height:12, color:'#7f8c8d' }} />
//             </div>
//           </div>
//         </header>

//         {/* Error Banner */}
//         {(sError || txError || rError) && (
//           <div style={{ background:'#e74c3c22', border:'1px solid #e74c3c44', padding:'8px 20px', fontSize:12, color:'#e74c3c', display:'flex', alignItems:'center', gap:8 }}>
//             <AlertCircle style={{ width:14, height:14 }} />
//             {sError || txError || rError}
//           </div>
//         )}

//         {/* Content Grid */}
//         <div className="content-grid" style={{ flex:1, overflowY:'auto', padding:16, display:'grid', gap:14, gridTemplateColumns:'1fr 1fr 1fr', gridTemplateRows:'auto auto auto' }}>

//           {/* ── Global Balance ──────────────────────────────────────────────── */}
//           <div style={{ ...cardStyle, gridColumn:'1', position:'relative', overflow:'hidden' }}>
//             <div style={{ position:'absolute', top:-40, right:-40, width:140, height:140, borderRadius:'50%', background:'#1a6cf011', filter:'blur(24px)', pointerEvents:'none' }} />
//             <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 }}>
//               <div style={{ fontSize:11, color:'#7f8c8d', letterSpacing:2 }}>GLOBAL BALANCE</div>
//               <div style={{ fontSize:10, padding:'2px 8px', borderRadius:20, background:'#2ecc7122', color:'#2ecc71', border:'1px solid #2ecc7144' }}>
//                 <Activity style={{ width:9, height:9, display:'inline', marginRight:3 }} />LIVE
//               </div>
//             </div>
//             {sLoading ? (
//               <><Skeleton h={36} w="70%" radius={8} style={{ marginBottom:8 }} /><Skeleton h={14} w="40%" radius={6} style={{ marginBottom:14 }} /></>
//             ) : (
//               <>
//                 <div style={{ fontSize:32, fontWeight:800, color:'#fff', letterSpacing:-1 }}>
//                   ${totalBalance.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
//                 </div>
//                 <div style={{ fontSize:13, color: balanceChange>=0 ? '#2ecc71':'#e74c3c', marginBottom:14 }}>
//                   {balanceChange>=0?'▲':'▼'} {Math.abs(balanceChange).toFixed(1)}%
//                 </div>
//               </>
//             )}
//             <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
//               {wLoading
//                 ? [1,2,3,4].map(i=><Skeleton key={i} w={60} h={44} radius={8} />)
//                 : currencyBreakdown.map(c=>(
//                     <div key={c.name} style={{ background:c.bg, border:`1px solid ${c.color}44`, borderRadius:8, padding:'6px 10px', flex:1, minWidth:60 }}>
//                       <div style={{ fontSize:10, color:c.color, fontWeight:700 }}>{c.name}</div>
//                       <div style={{ fontSize:12, color:'#fff', fontWeight:600 }}>{c.amount}</div>
//                     </div>
//                   ))
//               }
//             </div>
//           </div>

//           {/* ── Active Mining ───────────────────────────────────────────────── */}
//           <div style={{ ...cardStyle, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
//             <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', width:'100%', marginBottom:12 }}>
//               <button style={{ background:'none', border:'none', color:'#7f8c8d', cursor:'pointer', fontSize:16 }}>‹</button>
//               <div style={{ fontSize:11, color:'#7f8c8d', letterSpacing:2 }}>ACTIVE MINING</div>
//               <button style={{ background:'none', border:'none', color:'#7f8c8d', cursor:'pointer', fontSize:16 }}>›</button>
//             </div>
//             {sLoading ? <Skeleton w={100} h={100} radius="50%" style={{ marginBottom:10 }} /> : (
//               <div style={{ position:'relative', width:100, height:100, marginBottom:10 }}>
//                 <div style={{ position:'absolute', inset:-6, borderRadius:'50%', background:`conic-gradient(#2ecc71 ${miningGaugeVal*100}%,transparent 0%)`, filter:'blur(6px)', opacity:.4 }} />
//                 <svg width="100" height="100" style={{ transform:'rotate(-90deg)', position:'relative', zIndex:1 }}>
//                   <circle cx="50" cy="50" r="40" fill="none" stroke="#1e3a5f" strokeWidth="8" />
//                   <circle cx="50" cy="50" r="40" fill="none" stroke="#2ecc71" strokeWidth="8"
//                     strokeDasharray={`${2*Math.PI*40*miningGaugeVal} ${2*Math.PI*40}`}
//                     strokeLinecap="round" style={{ transition:'stroke-dasharray 1s ease' }} />
//                 </svg>
//                 <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
//                   <div style={{ fontSize:16, fontWeight:800, color:'#fff' }}>{miningSpeed || '0'}</div>
//                   <div style={{ fontSize:9, color:'#2ecc71' }}>MH/s</div>
//                 </div>
//               </div>
//             )}
//             <div style={{ display:'flex', alignItems:'flex-end', gap:3, height:32, marginBottom:12 }}>
//               {miningBars.map((h,i)=>(
//                 <div key={i} style={{ width:6, height:h*2.5, background: i===miningBars.length-1?'#2ecc71':'#1e3a5f', borderRadius:2, transition:'height .5s ease' }} />
//               ))}
//             </div>
//             {/* ✅ FUNCTIONAL Mining Toggle Button */}
//             <button onClick={handleMiningToggle} disabled={miningLoading} className="btn-hover" style={{
//               background: miningActive ? 'linear-gradient(135deg,#e74c3c,#c0392b)' : 'linear-gradient(135deg,#27ae60,#1e8449)',
//               border:'none', borderRadius:20, padding:'8px 24px',
//               color:'#fff', fontWeight:600, fontSize:13, cursor: miningLoading ? 'not-allowed' : 'pointer',
//               boxShadow: miningActive ? '0 0 12px #e74c3c66':'0 0 12px #2ecc7166',
//               transition:'all .25s', display:'flex', alignItems:'center', gap:8,
//               opacity: miningLoading ? .7 : 1,
//             }}>
//               {miningLoading && <Loader2 style={{ width:13, height:13, animation:'spin 1s linear infinite' }} />}
//               {miningActive ? '⏹ Stop Mining' : '▶ Start Mining'}
//             </button>
//           </div>

//           {/* ── Quick Transfer ──────────────────────────────────────────────── */}
//           <div style={cardStyle}>
//             <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:16, display:'flex', alignItems:'center', gap:8 }}>
//               <Send style={{ width:15, height:15, color:'#1a6cf0' }} /> Quick Transfer
//             </div>
//             {/* Recipient */}
//             <div style={inputStyle}>
//               <Send style={{ width:14, height:14, color:'#7f8c8d', flexShrink:0 }} />
//               <input placeholder="Recipient address…" value={transferForm.recipient}
//                 onChange={e=>setTransferForm(f=>({...f,recipient:e.target.value}))}
//                 style={{ background:'none', border:'none', outline:'none', color:'#fff', fontSize:12, flex:1 }} />
//             </div>
//             {/* Amount */}
//             <div style={inputStyle}>
//               <DollarSign style={{ width:14, height:14, color:'#7f8c8d', flexShrink:0 }} />
//               <input type="number" placeholder="0.00" value={transferForm.amount}
//                 onChange={e=>setTransferForm(f=>({...f,amount:e.target.value}))}
//                 style={{ background:'none', border:'none', outline:'none', color:'#fff', fontSize:12, flex:1 }} />
//             </div>
//             {/* Currency */}
//             <div style={inputStyle}>
//               <WalletIcon style={{ width:14, height:14, color:'#7f8c8d', flexShrink:0 }} />
//               <select value={transferForm.currency} onChange={e=>setTransferForm(f=>({...f,currency:e.target.value}))}
//                 style={{ background:'none', border:'none', outline:'none', color:'#fff', fontSize:12, flex:1, cursor:'pointer' }}>
//                 {(currencyBreakdown.length > 0 ? currencyBreakdown : [{name:'USD'},{name:'EUR'},{name:'BTC'}])
//                   .map(c=><option key={c.name} value={c.name} style={{ background:'#0d1b2a' }}>{c.name}</option>)}
//               </select>
//               <ChevronDown style={{ width:12, height:12, color:'#7f8c8d' }} />
//             </div>
//             {/* ✅ FUNCTIONAL Transfer Button */}
//             <button onClick={handleTransfer} disabled={transferLoading} className="btn-hover" style={{
//               width:'100%', background:'linear-gradient(135deg,#1a6cf0,#0a3d8f)',
//               border:'none', borderRadius:8, padding:'12px', color:'#fff',
//               fontWeight:700, fontSize:14, cursor: transferLoading?'not-allowed':'pointer', marginTop:4,
//               boxShadow:'0 4px 20px #1a6cf044', transition:'all .2s',
//               display:'flex', alignItems:'center', justifyContent:'center', gap:8,
//               opacity: transferLoading ? .7 : 1,
//             }}>
//               {transferLoading && <Loader2 style={{ width:14, height:14, animation:'spin 1s linear infinite' }} />}
//               {transferLoading ? 'Sending…' : 'Transfer'}
//             </button>
//           </div>

//           {/* ── Investment Packages ─────────────────────────────────────────── */}
//           <div style={{ ...cardStyle, gridColumn:'1 / 3' }}>
//             <div style={{ fontSize:13, color:'#7f8c8d', textAlign:'center', letterSpacing:3, marginBottom:14 }}>● INVESTMENT PACKAGES ●</div>
//             {sLoading ? (
//               <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
//                 {[1,2,3,4].map(i=><Skeleton key={i} h={130} radius={12} />)}
//               </div>
//             ) : packages.length > 0 ? (
//               <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
//                 {packages.map(p=>(
//                   <div key={p.name} className="pkg-card" style={{
//                     background:`linear-gradient(135deg,${p.color}11,${p.color}06)`,
//                     border:`1px solid ${p.border}44`, borderRadius:12, padding:'14px 12px',
//                     textAlign:'center', cursor:'pointer', transition:'all 0.25s',
//                     boxShadow:`0 4px 20px ${p.glow}`,
//                   }}>
//                     <div style={{ fontSize:14, fontWeight:700, color:p.color }}>{p.name}</div>
//                     <div style={{ fontSize:20, fontWeight:800, color:'#fff', margin:'6px 0' }}>{p.price||p.min_amount}</div>
//                     <div style={{ fontSize:12, color:p.color, fontWeight:600 }}>{p.rate||p.monthly_return} / Month</div>
//                     <div style={{ width:44, height:44, borderRadius:10, margin:'10px auto 0', background:`${p.color}22`, display:'flex', alignItems:'center', justifyContent:'center', border:`1px solid ${p.color}44` }}>
//                       <Trophy style={{ width:20, height:20, color:p.color }} />
//                     </div>
//                   </div>
//                 ))}
//               </div>
//             ) : (
//               <div style={{ textAlign:'center', color:'#7f8c8d', fontSize:12, padding:'20px 0' }}>No packages available</div>
//             )}
//           </div>

//           {/* ── Wallet Transactions + Withdrawals (spans rows 2-3) ──────────── */}
//           <div style={{ ...cardStyle, gridColumn:'3', gridRow:'2 / 4', display:'flex', flexDirection:'column' }}>
//             <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:14 }}>Wallet Transactions</div>
//             <div style={{ flex:1 }}>
//               {txLoading
//                 ? [1,2,3,4].map(i=>(
//                     <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 0', borderBottom:'1px solid #1e3a5f22' }}>
//                       <Skeleton w={32} h={32} radius={8} />
//                       <div style={{ flex:1 }}><Skeleton h={12} w="60%" radius={4} style={{ marginBottom:6 }} /><Skeleton h={10} w="40%" radius={4} /></div>
//                       <Skeleton h={14} w={50} radius={4} />
//                     </div>
//                   ))
//                 : recentTx.map((tx,i)=>{
//                     const Icon = tx.icon;
//                     return (
//                       <div key={i} className="tx-row" style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 6px', borderBottom:'1px solid #1e3a5f22', cursor:'pointer', transition:'all .2s' }}>
//                         <div style={{ display:'flex', alignItems:'center', gap:10 }}>
//                           <div style={{ width:32, height:32, borderRadius:8, background:`${tx.color}22`, display:'flex', alignItems:'center', justifyContent:'center' }}>
//                             <Icon style={{ width:14, height:14, color:tx.color }} />
//                           </div>
//                           <div>
//                             <div style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{tx.label}</div>
//                             <div style={{ fontSize:10, color:'#7f8c8d' }}>{tx.time}</div>
//                           </div>
//                         </div>
//                         <div style={{ display:'flex', alignItems:'center', gap:6 }}>
//                           <span style={{ fontSize:13, fontWeight:700, color:tx.color }}>{tx.amount}</span>
//                           <ChevronRight style={{ width:12, height:12, color:tx.color }} />
//                         </div>
//                       </div>
//                     );
//                   })
//               }
//             </div>

//             <button className="btn-hover" onClick={() => setActiveNav('Transactions')} style={{
//               background:'none', border:'1px solid #1e3a5f', borderRadius:8,
//               color:'#7f8c8d', fontSize:12, padding:'8px', cursor:'pointer',
//               marginTop:10, transition:'all 0.2s',
//             }}>View All</button>

//             {/* Withdrawal Requests */}
//             <div style={{ marginTop:16 }}>
//               <div style={{ fontSize:13, fontWeight:700, color:'#fff', marginBottom:10 }}>Withdrawal Requests</div>
//               {rLoading
//                 ? [1,2,3].map(i=><Skeleton key={i} h={36} radius={8} style={{ marginBottom:6 }} />)
//                 : [
//                     { icon:Star,        label:'Pending',    count:pendingCount,    color:'#f39c12', bg:'#f39c1222' },
//                     { icon:AlertCircle, label:'Processing', count:processingCount, color:'#3498db', bg:'#3498db22' },
//                     { icon:CheckCircle, label:'Completed',  count:completedCount,  color:'#2ecc71', bg:'#2ecc7122' },
//                   ].map(item=>{
//                     const Icon = item.icon;
//                     return (
//                       <div key={item.label} className="btn-hover" onClick={()=>setActiveNav('Withdrawals')} style={{
//                         display:'flex', alignItems:'center', justifyContent:'space-between',
//                         padding:'8px 10px', borderRadius:8, marginBottom:6,
//                         background:item.bg, cursor:'pointer', transition:'all .2s',
//                       }}>
//                         <div style={{ display:'flex', alignItems:'center', gap:8 }}>
//                           <Icon style={{ width:14, height:14, color:item.color }} />
//                           <span style={{ fontSize:12, color:'#fff' }}>{item.label}</span>
//                         </div>
//                         <div style={{ display:'flex', alignItems:'center', gap:6 }}>
//                           <span style={{ fontSize:14, fontWeight:800, color:item.color }}>{item.count}</span>
//                           <div style={{ width:20, height:20, borderRadius:4, background:item.color, display:'flex', alignItems:'center', justifyContent:'center' }}>
//                             <ChevronRight style={{ width:10, height:10, color:'#fff' }} />
//                           </div>
//                         </div>
//                       </div>
//                     );
//                   })
//               }
//               {/* ✅ FUNCTIONAL Withdrawal Request Button */}
//               <button className="btn-hover" onClick={()=>setShowWithdrawModal(true)} style={{
//                 width:'100%', background:'linear-gradient(135deg,#e74c3c,#c0392b)',
//                 border:'none', borderRadius:8, padding:'10px',
//                 color:'#fff', fontWeight:700, fontSize:12, cursor:'pointer',
//                 marginTop:6, boxShadow:'0 4px 12px #e74c3c44', transition:'all .2s',
//               }}>Request Withdrawal</button>
//             </div>
//           </div>

//           {/* ── Recent Activity ─────────────────────────────────────────────── */}
//           <div style={cardStyle}>
//             <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:14 }}>Recent Activity</div>
//             {txLoading
//               ? [1,2,3].map(i=>(
//                   <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 0' }}>
//                     <Skeleton w={36} h={36} radius={10} />
//                     <div style={{ flex:1 }}><Skeleton h={12} w="55%" radius={4} style={{ marginBottom:6 }} /><Skeleton h={10} w="35%" radius={4} /></div>
//                   </div>
//                 ))
//               : recentActivity.map((a,i)=>{
//                   const Icon = a.icon;
//                   return (
//                     <div key={i} className="tx-row" style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 6px', borderBottom: i<recentActivity.length-1?'1px solid #1e3a5f22':'none', transition:'all .2s' }}>
//                       <div style={{ width:36, height:36, borderRadius:10, background:a.bg, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
//                         <Icon style={{ width:16, height:16, color:a.iconColor }} />
//                       </div>
//                       <div style={{ flex:1 }}>
//                         <div style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{a.label}</div>
//                         <div style={{ fontSize:13, fontWeight:700, color:'#fff' }}>{a.sub}</div>
//                       </div>
//                       {a.status && (
//                         <div style={{ display:'flex', alignItems:'center', gap:4 }}>
//                           <CheckCircle style={{ width:12, height:12, color:a.statusColor }} />
//                           <span style={{ fontSize:11, color:a.statusColor, fontWeight:600 }}>{a.status}</span>
//                         </div>
//                       )}
//                     </div>
//                   );
//                 })
//             }
//           </div>

//           {/* ── Monthly Growth ──────────────────────────────────────────────── */}
//           <div style={cardStyle}>
//             <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:14 }}>Monthly Growth</div>
//             {sLoading ? <Skeleton h={160} radius={8} />
//               : monthlyData.length > 0 ? (
//                 <ResponsiveContainer width="100%" height={160}>
//                   <AreaChart data={monthlyData} margin={{ top:4, right:8, bottom:0, left:-20 }}>
//                     <defs>
//                       <linearGradient id="incomeGrad" x1="0" y1="0" x2="0" y2="1">
//                         <stop offset="5%"  stopColor="#2ecc71" stopOpacity={0.3} />
//                         <stop offset="95%" stopColor="#2ecc71" stopOpacity={0} />
//                       </linearGradient>
//                       <linearGradient id="expenseGrad" x1="0" y1="0" x2="0" y2="1">
//                         <stop offset="5%"  stopColor="#f39c12" stopOpacity={0.3} />
//                         <stop offset="95%" stopColor="#f39c12" stopOpacity={0} />
//                       </linearGradient>
//                     </defs>
//                     <XAxis dataKey="month" tick={{ fill:'#7f8c8d', fontSize:10 }} axisLine={false} tickLine={false} />
//                     <YAxis tick={{ fill:'#7f8c8d', fontSize:9 }} axisLine={false} tickLine={false} />
//                     <Tooltip content={<CustomTooltip />} />
//                     <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize:10, color:'#aaa' }} />
//                     <Area type="monotone" dataKey="income"  stroke="#2ecc71" fill="url(#incomeGrad)"  strokeWidth={2} dot={{ r:3, fill:'#2ecc71' }} name="Income" />
//                     <Area type="monotone" dataKey="expense" stroke="#f39c12" fill="url(#expenseGrad)" strokeWidth={2} dot={{ r:3, fill:'#f39c12' }} name="Expense" />
//                   </AreaChart>
//                 </ResponsiveContainer>
//               ) : (
//                 <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center', color:'#7f8c8d', fontSize:12 }}>No growth data available</div>
//               )
//             }
//           </div>

//         </div>
//       </main>

//       {/* ── Withdrawal Modal ─────────────────────────────────────────────────── */}
//       {showWithdrawModal && (
//         <WithdrawalModal
//           wallets={wallets}
//           onClose={()=>setShowWithdrawModal(false)}
//           onSuccess={refetchAll}
//           showToast={showToast}
//         />
//       )}

//       {/* ── Toast ────────────────────────────────────────────────────────────── */}
//       {toast && <Toast msg={toast.msg} type={toast.type} onClose={()=>setToast(null)} />}
//     </div>
//   );
// }