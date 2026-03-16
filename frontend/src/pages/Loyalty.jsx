// src/pages/Loyalty.jsx
import React, { useState, useEffect, useCallback } from 'react';
import '../styles/loyalty.css';

// ── Auth ───────────────────────────────────────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem('adminAccessToken') || localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

const BASE = '/api/loyalty';

async function safeFetch(url, options = {}) {
  try {
    const res = await fetch(url, { headers: authHeaders(), ...options });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '—';
const fmtTime = (d) => d ? new Date(d).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}) : '—';
const initials = (f, l) => ((f?.[0] || '') + (l?.[0] || '')).toUpperCase() || '?';

function txnType(txn) {
  if (txn.value < 0) return 'spending';
  if (txn.is_discount) return 'discount';
  return 'full';
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3200); return () => clearTimeout(t); }, [onClose]);
  return <div className={`loy-toast ${type}`}>{msg}</div>;
}

// ── Add Customer Modal ─────────────────────────────────────────────────────────
function AddCustomerModal({ onClose, onSaved }) {
  const [form, setForm] = useState({
    code:'', firstname:'', lastname:'', email:'', phone:'', city:'', newsletter: true
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!form.code.trim()) return;
    setSaving(true);
    const res = await safeFetch(`${BASE}/customers/`, {
      method: 'POST',
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (res?.id) { onSaved(res); onClose(); }
  };

  return (
    <div className="loy-modal-overlay" onClick={onClose}>
      <div className="loy-modal" onClick={e => e.stopPropagation()}>
        <div className="loy-modal__title">Add New Customer</div>

        <div className="loy-form-row">
          <div className="loy-form-group">
            <label>Code *</label>
            <input placeholder="CUST001" value={form.code}
              onChange={e => setForm(p=>({...p,code:e.target.value}))}/>
          </div>
          <div className="loy-form-group">
            <label>Phone</label>
            <input placeholder="+1 234 567" value={form.phone}
              onChange={e => setForm(p=>({...p,phone:e.target.value}))}/>
          </div>
        </div>

        <div className="loy-form-row">
          <div className="loy-form-group">
            <label>First Name</label>
            <input placeholder="John" value={form.firstname}
              onChange={e => setForm(p=>({...p,firstname:e.target.value}))}/>
          </div>
          <div className="loy-form-group">
            <label>Last Name</label>
            <input placeholder="Doe" value={form.lastname}
              onChange={e => setForm(p=>({...p,lastname:e.target.value}))}/>
          </div>
        </div>

        <div className="loy-form-group">
          <label>Email</label>
          <input placeholder="john@example.com" value={form.email}
            onChange={e => setForm(p=>({...p,email:e.target.value}))}/>
        </div>

        <div className="loy-form-group">
          <label>City</label>
          <input placeholder="New York" value={form.city}
            onChange={e => setForm(p=>({...p,city:e.target.value}))}/>
        </div>

        <div className="loy-modal__actions">
          <button className="loy-btn-cancel" onClick={onClose}>Cancel</button>
          <button className="loy-btn-submit" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving...' : 'Add Customer'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function LoyaltyPage() {
  const [customers,   setCustomers]   = useState([]);
  const [txns,        setTxns]        = useState([]);
  const [events,      setEvents]      = useState([]);
  const [actionStats, setActionStats] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [search,      setSearch]      = useState('');
  const [showModal,   setShowModal]   = useState(false);
  const [toast,       setToast]       = useState(null);
  const [page,        setPage]        = useState(1);
  const PAGE_SIZE = 8;

  const showToast = useCallback((msg, type='success') =>
    setToast({ msg, type, key: Date.now() }), []);

  // ── Fetch ──────────────────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [custRes, txnRes, evtRes, actRes] = await Promise.all([
      safeFetch(`${BASE}/customers/?ordering=-created_at`),
      safeFetch(`${BASE}/transactions/?ordering=-timestamp`),
      safeFetch(`${BASE}/events/?ordering=-timestamp`),
      safeFetch(`${BASE}/events/by_action/`),
    ]);

    if (Array.isArray(custRes))        setCustomers(custRes);
    else if (custRes?.results)         setCustomers(custRes.results);

    if (Array.isArray(txnRes))         setTxns(txnRes);
    else if (txnRes?.results)          setTxns(txnRes.results);

    if (Array.isArray(evtRes))         setEvents(evtRes);
    else if (evtRes?.results)          setEvents(evtRes.results);

    if (Array.isArray(actRes))         setActionStats(actRes.slice(0,6));

    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Stats ──────────────────────────────────────────────────────────────────
  const totalSpent    = txns.filter(t=>t.value>0).reduce((s,t)=>s+parseFloat(t.value),0);
  const discountCount = txns.filter(t=>t.is_discount).length;
  const nlCount       = customers.filter(c=>c.newsletter).length;

  // ── Filter ─────────────────────────────────────────────────────────────────
  const filtered = customers.filter(c =>
    !search ||
    (c.code||'').toLowerCase().includes(search.toLowerCase()) ||
    (c.firstname||'').toLowerCase().includes(search.toLowerCase()) ||
    (c.lastname||'').toLowerCase().includes(search.toLowerCase()) ||
    (c.email||'').toLowerCase().includes(search.toLowerCase())
  );
  const paginated = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const maxAction = actionStats[0]?.count || 1;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="loy-page">
      <div className="loy-orb loy-orb-1"/>
      <div className="loy-orb loy-orb-2"/>

      {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} onClose={()=>setToast(null)}/>}
      {showModal && (
        <AddCustomerModal
          onClose={() => setShowModal(false)}
          onSaved={(c) => { setCustomers(p=>[c,...p]); showToast('✅ Customer added!'); }}
        />
      )}

      <div className="loy-container">

        {/* ── Header ── */}
        <header className="loy-header">
          <div className="loy-header__left">
            <div className="loy-header__eyebrow">CRM · Loyalty Program</div>
            <div className="loy-header__title">
              Customer <span>Loyalty</span>
            </div>
          </div>
          <div className="loy-header__right">
            <div className="loy-search">
              <span className="loy-search__icon">🔍</span>
              <input
                placeholder="Search customers..."
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1); }}
              />
            </div>
            <button className="loy-add-btn" onClick={() => setShowModal(true)}>
              + Add Customer
            </button>
          </div>
        </header>

        {/* ── Stats ── */}
        <div className="loy-stats">
          {[
            { icon:'👥', label:'Total Customers',    value: customers.length,          sub:'registered'         },
            { icon:'💰', label:'Total Revenue',       value: `$${totalSpent.toFixed(2)}`,sub:'all transactions'  },
            { icon:'🏷️', label:'Discount Txns',       value: discountCount,             sub:'transactions'       },
            { icon:'📧', label:'Newsletter Subs',     value: nlCount,                   sub:'subscribers'        },
          ].map((s,i) => (
            <div className="loy-stat" key={i}>
              <div className="loy-stat__icon">{s.icon}</div>
              <div className="loy-stat__label">{s.label}</div>
              <div className="loy-stat__value">{s.value}</div>
              <div className="loy-stat__sub">{s.sub}</div>
            </div>
          ))}
        </div>

        {/* ── Main Grid ── */}
        <div className="loy-main-grid">

          {/* Customers Table */}
          <div className="loy-card">
            <div className="loy-card__header">
              <div className="loy-card__title">👥 Customers</div>
              <div className="loy-card__badge">{filtered.length} total</div>
            </div>
            <div className="loy-table-wrap">
              {loading ? (
                <div className="loy-empty"><div className="loy-empty__text">Loading...</div></div>
              ) : paginated.length === 0 ? (
                <div className="loy-empty">
                  <div className="loy-empty__icon">👥</div>
                  <div className="loy-empty__text">{search ? 'No results found' : 'No customers yet'}</div>
                  <div className="loy-empty__sub">{!search && 'Add your first customer to get started'}</div>
                </div>
              ) : (
                <table className="loy-table">
                  <thead>
                    <tr>
                      <th>Customer</th>
                      <th>Email</th>
                      <th>City</th>
                      <th>Newsletter</th>
                      <th>Txns</th>
                      <th>Joined</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginated.map(c => (
                      <tr key={c.id}>
                        <td>
                          <div style={{display:'flex',alignItems:'center',gap:10}}>
                            <div className="loy-avatar">{initials(c.firstname,c.lastname)}</div>
                            <div>
                              <div className="cust-name">{c.full_name || `${c.firstname||''} ${c.lastname||''}`.trim() || 'Unnamed'}</div>
                              <div className="cust-code">{c.code}</div>
                            </div>
                          </div>
                        </td>
                        <td><div className="cust-email">{c.email || '—'}</div></td>
                        <td><div style={{fontSize:'.78rem'}}>{c.city || '—'}</div></td>
                        <td>
                          <span className={`nl-badge ${c.newsletter?'nl-yes':'nl-no'}`}>
                            {c.newsletter ? '✓ Yes' : '✗ No'}
                          </span>
                        </td>
                        <td><span className="spent-val">{c.transaction_count || 0}</span></td>
                        <td><div style={{fontFamily:'var(--font-mono)',fontSize:'.68rem',color:'var(--loy-muted)'}}>{fmtDate(c.created_at)}</div></td>
                        <td><button className="loy-action-btn">View</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            {totalPages > 1 && (
              <div className="loy-pagination">
                <span className="loy-page-info">{(page-1)*PAGE_SIZE+1}–{Math.min(page*PAGE_SIZE,filtered.length)} of {filtered.length}</span>
                <button className="loy-page-btn" onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1}>‹</button>
                {Array.from({length:Math.min(5,totalPages)},(_,i)=>i+1).map(p=>(
                  <button key={p} className={`loy-page-btn${page===p?' active':''}`} onClick={()=>setPage(p)}>{p}</button>
                ))}
                <button className="loy-page-btn" onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages}>›</button>
              </div>
            )}
          </div>

          {/* Transactions */}
          <div className="loy-card">
            <div className="loy-card__header">
              <div className="loy-card__title">💳 Transactions</div>
              <div className="loy-card__badge">{txns.length} total</div>
            </div>
            <div className="loy-txn-list">
              {txns.length === 0 ? (
                <div className="loy-empty">
                  <div className="loy-empty__icon">💳</div>
                  <div className="loy-empty__text">No transactions yet</div>
                </div>
              ) : txns.slice(0,8).map((t,i) => {
                const type = txnType(t);
                return (
                  <div className="loy-txn-item" key={t.id||i}>
                    <div className={`txn-icon ${type}`}>
                      {type==='full'?'💰':type==='discount'?'🏷️':'💸'}
                    </div>
                    <div className="txn-info">
                      <div className="txn-customer">{t.customer_name || 'Unknown'}</div>
                      <div className="txn-time">{fmtDate(t.timestamp)} {fmtTime(t.timestamp)}</div>
                    </div>
                    <span className={`txn-type ${type}`}>{t.type_label || type}</span>
                    <div className={`txn-amount ${parseFloat(t.value)>=0?'pos':'neg'}`}>
                      {parseFloat(t.value)>=0?'+':''}{parseFloat(t.value||0).toFixed(2)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Bottom Grid ── */}
        <div className="loy-bottom-grid">

          {/* Events */}
          <div className="loy-card">
            <div className="loy-card__header">
              <div className="loy-card__title">📋 Events</div>
              <div className="loy-card__badge">{events.length} total</div>
            </div>
            <div className="loy-evt-list">
              {events.length === 0 ? (
                <div className="loy-empty">
                  <div className="loy-empty__icon">📋</div>
                  <div className="loy-empty__text">No events recorded</div>
                </div>
              ) : events.slice(0,8).map((e,i) => (
                <div className="loy-evt-item" key={e.id||i}>
                  <div className="evt-dot-wrap">
                    <div className="evt-dot"/>
                    {i < Math.min(events.length,8)-1 && <div className="evt-line"/>}
                  </div>
                  <div className="evt-content">
                    <div className="evt-action">{e.action}</div>
                    {e.description && <div className="evt-desc">{e.description}</div>}
                    <div className="evt-meta">{fmtDate(e.timestamp)} · {fmtTime(e.timestamp)}</div>
                  </div>
                  <div className="evt-who">
                    {e.is_anonymous ? 'Anonymous' : e.customer_name || 'Unknown'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Action Stats */}
          <div className="loy-card">
            <div className="loy-card__header">
              <div className="loy-card__title">📊 Top Actions</div>
            </div>
            <div className="action-stat-list">
              {actionStats.length === 0 ? (
                <div className="loy-empty">
                  <div className="loy-empty__icon">📊</div>
                  <div className="loy-empty__text">No action data yet</div>
                </div>
              ) : actionStats.map((a,i) => (
                <div className="action-stat-item" key={i}>
                  <div className="action-name">{a.action}</div>
                  <div className="action-bar-wrap">
                    <div className="action-bar" style={{width:`${(a.count/maxAction)*100}%`}}/>
                  </div>
                  <div className="action-count">{a.count}</div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}