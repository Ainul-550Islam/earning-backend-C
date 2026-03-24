// src/pages/Referral.jsx  —  100% Complete with full CRUD
//
// ENDPOINTS USED:
//  GET    /referral/stats/                            user own stats
//  GET    /referral/admin/overview/                   global stats + top referrers
//  GET    /referral/admin/stats-by-date/?days=30      chart data
//  GET    /referral/admin/list/?page&search           paginated referrals
//  POST   /referral/admin/create/                     create referral manually
//  DELETE /referral/admin/delete/{id}/                delete referral
//  POST   /referral/admin/give-bonus/{id}/            give signup bonus
//  POST   /referral/admin/adjust-commission/{id}/     add/deduct coins
//  GET    /referral/admin/earnings/?page              paginated earnings
//  DELETE /referral/admin/earnings/delete/{id}/       delete earning record
//  GET    /referral/admin/settings/                   get settings
//  PATCH  /referral/admin/settings/                   update settings
//  POST   /referral/admin/toggle-program/             quick on/off
//  GET    /referral/admin/search-users/?q=            user search for create modal

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Users, Gift, TrendingUp, DollarSign, Copy, CheckCheck,
  RefreshCw, Search, Settings, Trash2, ChevronRight, ChevronLeft,
  Shield, Activity, Star, ToggleLeft, ToggleRight, Edit3, Save,
  X, Loader2, Link, Award, BarChart2, Clock, Plus, AlertCircle,
  ArrowUp, ArrowDown, Zap, UserPlus, Coins
} from 'lucide-react';
import client from '../api/client';
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── Micro helpers ────────────────────────────────────────────────────────────
const SK = ({ w = '100%', h = 14, r = 6, s = {} }) => (
  <div style={{ width: w, height: h, borderRadius: r, background: 'linear-gradient(90deg,#0d2137 25%,#1a3a5c44 50%,#0d2137 75%)', backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite', ...s }} />
);

function useToast() {
  const [list, setList] = useState([]);
  const push = useCallback((msg, type = 'success') => {
    const id = Date.now();
    setList(p => [...p, { id, msg, type }]);
    setTimeout(() => setList(p => p.filter(t => t.id !== id)), 3400);
  }, []);
  return { list, push };
}

const Toasts = ({ list }) => (
  <div style={{ position: 'fixed', bottom: 22, right: 22, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
    {list.map(t => (
      <div key={t.id} style={{
        padding: '10px 16px', borderRadius: 8, fontSize: 12, fontFamily: "'Courier New',monospace",
        background: t.type === 'error' ? '#ff3d7120' : t.type === 'warn' ? '#ffd70020' : '#00ff8820',
        border: `1px solid ${t.type === 'error' ? '#ff3d7155' : t.type === 'warn' ? '#ffd70055' : '#00ff8855'}`,
        color: t.type === 'error' ? '#ff3d71' : t.type === 'warn' ? '#ffd700' : '#00ff88',
        animation: 'slideIn .3s ease', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>{t.type === 'error' ? '✗' : t.type === 'warn' ? '⚠' : '✓'} {t.msg}</div>
    ))}
  </div>
);

const Stat = ({ label, value, icon: Icon, color, sub, loading }) => (
  <div style={{ background: `linear-gradient(135deg,${color}10,${color}06)`, border: `1px solid ${color}33`, borderRadius: 10, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
    <div style={{ width: 40, height: 40, borderRadius: 10, background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <Icon style={{ width: 18, height: 18, color }} />
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 9, color: '#7a9cc0', letterSpacing: 1.2, fontFamily: "'Courier New',monospace" }}>{label}</div>
      {loading ? <SK h={20} w={70} r={4} s={{ marginTop: 4 }} /> : (
        <div style={{ fontSize: 20, fontWeight: 800, color: '#e0f0ff', fontFamily: "'Courier New',monospace", lineHeight: 1.2 }}>{value}</div>
      )}
      {sub && !loading && <div style={{ fontSize: 10, color: '#7a9cc044', marginTop: 1, fontFamily: "'Courier New',monospace" }}>{sub}</div>}
    </div>
  </div>
);

// ─── Simple bar chart ─────────────────────────────────────────────────────────
const MiniChart = ({ data, color }) => {
  if (!data?.length) return <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#7a9cc044', fontSize: 11, fontFamily: "'Courier New',monospace" }}>NO DATA</div>;
  const max = Math.max(...data.map(d => d.total_commission), 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 80, padding: '0 4px' }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }} title={`${d.date}: ${d.total_commission} coins`}>
          <div style={{ width: '100%', background: `${color}33`, border: `1px solid ${color}44`, borderRadius: '3px 3px 0 0', height: Math.max(4, (d.total_commission / max) * 70), transition: 'height .4s ease', boxShadow: d.total_commission > 0 ? `0 0 6px ${color}44` : 'none' }} />
        </div>
      ))}
    </div>
  );
};

// ─── Settings Modal ───────────────────────────────────────────────────────────
const SettingsModal = ({ settings, onClose, onSaved, toast }) => {
  const [form, setForm] = useState({ ...settings });
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await client.patch('/referral/admin/settings/', form);
      toast('Settings saved');
      onSaved();
      onClose();
    } catch { toast('Save failed', 'error'); }
    finally { setSaving(false); }
  };

  const inp = { width: '100%', background: '#050b14', border: '1px solid #1a3a5c', borderRadius: 8, padding: '9px 12px', color: '#e0f0ff', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: "'Courier New',monospace" };
  const lbl = { fontSize: 10, color: '#7a9cc0', letterSpacing: 1.4, marginBottom: 5, display: 'block', fontFamily: "'Courier New',monospace" };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: '#000b', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
      <div style={{ background: 'linear-gradient(135deg,#060f1e,#0a1628)', border: '1px solid #ffd70044', borderRadius: 14, padding: 26, width: 420, maxWidth: '92vw', boxShadow: '0 24px 80px #ffd70018', animation: 'fadeUp .3s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#ffd700', animation: 'pulse 1.5s infinite' }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace", letterSpacing: 1 }}>PROGRAM SETTINGS</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a9cc0' }}><X style={{ width: 17, height: 17 }} /></button>
        </div>

        {/* Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 14px', background: form.is_active ? '#00ff8810' : '#1a3a5c22', border: `1px solid ${form.is_active ? '#00ff8833' : '#1a3a5c'}`, borderRadius: 8, marginBottom: 18, cursor: 'pointer' }} onClick={() => setForm(p => ({ ...p, is_active: !p.is_active }))}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace" }}>PROGRAM STATUS</div>
            <div style={{ fontSize: 10, color: '#7a9cc0', marginTop: 2 }}>{form.is_active ? 'Referral program is LIVE' : 'Program is paused'}</div>
          </div>
          <div style={{ background: form.is_active ? '#00ff8820' : '#1a3a5c33', border: `1px solid ${form.is_active ? '#00ff8855' : '#1a3a5c'}`, borderRadius: 20, padding: '5px 14px', color: form.is_active ? '#00ff88' : '#7a9cc0', fontSize: 11, fontFamily: "'Courier New',monospace" }}>
            {form.is_active ? '● ACTIVE' : '○ PAUSED'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
          {[{ k: 'referrer_signup_bonus', l: 'REFERRER SIGNUP BONUS' }, { k: 'direct_signup_bonus', l: 'NEW USER BONUS' }].map(f => (
            <div key={f.k}>
              <label style={lbl}>{f.l} (COINS)</label>
              <input type="number" min="0" style={inp} value={form[f.k]} onChange={e => setForm(p => ({ ...p, [f.k]: parseFloat(e.target.value) || 0 }))}
                onFocus={e => e.target.style.borderColor = '#ffd70066'} onBlur={e => e.target.style.borderColor = '#1a3a5c'} />
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 22 }}>
          <label style={lbl}>LIFETIME COMMISSION RATE (%)</label>
          <input type="number" min="0" max="100" step="0.01" style={inp} value={form.lifetime_commission_rate}
            onChange={e => setForm(p => ({ ...p, lifetime_commission_rate: parseFloat(e.target.value) || 0 }))}
            onFocus={e => e.target.style.borderColor = '#ffd70066'} onBlur={e => e.target.style.borderColor = '#1a3a5c'} />
          <div style={{ fontSize: 10, color: '#7a9cc033', marginTop: 5, fontFamily: "'Courier New',monospace" }}>Referrer earns this % from every coin their referred user earns</div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 8, padding: 10, color: '#7a9cc0', fontSize: 11, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>CANCEL</button>
          <button onClick={save} disabled={saving} style={{ flex: 2, background: 'linear-gradient(135deg,#ffd70022,#ffd70011)', border: '1px solid #ffd70055', borderRadius: 8, padding: 10, color: '#ffd700', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            {saving ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> : <Save style={{ width: 13, height: 13 }} />}
            {saving ? 'SAVING…' : 'SAVE'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Create Referral Modal ────────────────────────────────────────────────────
const CreateModal = ({ onClose, onCreated, toast }) => {
  const [referrer, setReferrer] = useState('');
  const [referred, setReferred] = useState('');
  const [giveBonus, setGiveBonus] = useState(false);
  const [saving, setSaving] = useState(false);
  const [referrerSugg, setReferrerSugg] = useState([]);
  const [referredSugg, setReferredSugg] = useState([]);
  const searchTimer = useRef(null);

  const searchUsers = async (q, setSugg) => {
    if (q.length < 2) { setSugg([]); return; }
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await client.get('/referral/admin/search-users/', { params: { q } });
        setSugg(r.data.results ?? []);
      } catch { setSugg([]); }
    }, 300);
  };

  const save = async () => {
    if (!referrer.trim() || !referred.trim()) { toast('Both usernames required', 'error'); return; }
    setSaving(true);
    try {
      await client.post('/referral/admin/create/', { referrer_username: referrer, referred_username: referred, give_bonus: giveBonus });
      toast('Referral created successfully');
      onCreated();
      onClose();
    } catch (e) {
      toast(e?.response?.data?.error || 'Create failed', 'error');
    } finally { setSaving(false); }
  };

  const inputBox = (label, val, setVal, sugg, setSugg) => (
    <div style={{ marginBottom: 14, position: 'relative' }}>
      <div style={{ fontSize: 10, color: '#7a9cc0', letterSpacing: 1.4, marginBottom: 5, fontFamily: "'Courier New',monospace" }}>{label}</div>
      <input value={val} onChange={e => { setVal(e.target.value); searchUsers(e.target.value, setSugg); }}
        placeholder="Type username…"
        style={{ width: '100%', background: '#050b14', border: '1px solid #1a3a5c', borderRadius: 8, padding: '9px 12px', color: '#e0f0ff', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: "'Courier New',monospace" }}
        onFocus={e => e.target.style.borderColor = '#00d4ff66'} onBlur={e => { setTimeout(() => setSugg([]), 200); e.target.style.borderColor = '#1a3a5c'; }} />
      {sugg.length > 0 && (
        <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 8, zIndex: 50, maxHeight: 160, overflowY: 'auto', boxShadow: '0 8px 24px #00000066' }}>
          {sugg.map(u => (
            <div key={u.id} onMouseDown={() => { setVal(u.username); setSugg([]); }} style={{ padding: '9px 13px', cursor: 'pointer', fontSize: 12, color: '#e0f0ff', fontFamily: "'Courier New',monospace", borderBottom: '1px solid #1a3a5c22' }}
              onMouseEnter={e => e.currentTarget.style.background = '#1a3a5c33'} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              {u.username} <span style={{ color: '#7a9cc0', fontSize: 10 }}>{u.email}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: '#000b', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
      <div style={{ background: 'linear-gradient(135deg,#060f1e,#0a1628)', border: '1px solid #00d4ff44', borderRadius: 14, padding: 26, width: 420, maxWidth: '92vw', boxShadow: '0 24px 80px #00d4ff18', animation: 'fadeUp .3s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#00d4ff', animation: 'pulse 1.5s infinite' }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace", letterSpacing: 1 }}>CREATE REFERRAL</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a9cc0' }}><X style={{ width: 17, height: 17 }} /></button>
        </div>

        {inputBox('REFERRER (WHO REFERRED)', referrer, setReferrer, referrerSugg, setReferrerSugg)}
        <div style={{ textAlign: 'center', color: '#7a9cc0', fontSize: 18, marginBottom: 10 }}>↓</div>
        {inputBox('REFERRED USER (NEW MEMBER)', referred, setReferred, referredSugg, setReferredSugg)}

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: giveBonus ? '#00ff8810' : '#1a3a5c11', border: `1px solid ${giveBonus ? '#00ff8833' : '#1a3a5c'}`, borderRadius: 8, marginBottom: 20, cursor: 'pointer' }} onClick={() => setGiveBonus(v => !v)}>
          <div style={{ width: 18, height: 18, borderRadius: 4, background: giveBonus ? '#00ff88' : 'transparent', border: `2px solid ${giveBonus ? '#00ff88' : '#7a9cc0'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all .2s', flexShrink: 0 }}>
            {giveBonus && <span style={{ color: '#000', fontSize: 11, fontWeight: 900 }}>✓</span>}
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#e0f0ff', fontFamily: "'Courier New',monospace", fontWeight: 600 }}>Give signup bonus immediately</div>
            <div style={{ fontSize: 10, color: '#7a9cc0', marginTop: 1 }}>Both users will receive their signup bonuses now</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 8, padding: 10, color: '#7a9cc0', fontSize: 11, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>CANCEL</button>
          <button onClick={save} disabled={saving} style={{ flex: 2, background: 'linear-gradient(135deg,#00d4ff22,#00d4ff11)', border: '1px solid #00d4ff55', borderRadius: 8, padding: 10, color: '#00d4ff', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            {saving ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> : <Plus style={{ width: 13, height: 13 }} />}
            {saving ? 'CREATING…' : 'CREATE REFERRAL'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Adjust Commission Modal ──────────────────────────────────────────────────
const AdjustModal = ({ referral, onClose, onDone, toast }) => {
  const [amount, setAmount] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!amount || isNaN(parseFloat(amount))) { toast('Enter valid amount', 'error'); return; }
    setSaving(true);
    try {
      await client.post(`/referral/admin/adjust-commission/${referral.id}/`, { amount: parseFloat(amount) });
      toast(`Commission adjusted: ${parseFloat(amount) > 0 ? '+' : ''}${amount} coins`);
      onDone();
      onClose();
    } catch (e) {
      toast(e?.response?.data?.error || 'Adjust failed', 'error');
    } finally { setSaving(false); }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1001, background: '#000b', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
      <div style={{ background: 'linear-gradient(135deg,#060f1e,#0a1628)', border: '1px solid #ffd70044', borderRadius: 12, padding: 24, width: 360, maxWidth: '92vw', animation: 'fadeUp .2s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#ffd700', fontFamily: "'Courier New',monospace" }}>ADJUST COMMISSION</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a9cc0' }}><X style={{ width: 16, height: 16 }} /></button>
        </div>
        <div style={{ fontSize: 11, color: '#7a9cc0', fontFamily: "'Courier New',monospace", marginBottom: 16 }}>
          Referral: <span style={{ color: '#00d4ff' }}>{referral.referrer}</span> → <span style={{ color: '#e0f0ff' }}>{referral.referred_user}</span>
          <br />Current commission: <span style={{ color: '#ffd700' }}>{referral.total_commission_earned} coins</span>
        </div>
        <div style={{ fontSize: 10, color: '#7a9cc0', letterSpacing: 1.4, marginBottom: 6, fontFamily: "'Courier New',monospace" }}>AMOUNT (positive = add, negative = deduct)</div>
        <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} placeholder="e.g. 100 or -50"
          style={{ width: '100%', background: '#050b14', border: '1px solid #ffd70044', borderRadius: 8, padding: '10px 12px', color: '#e0f0ff', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: "'Courier New',monospace", marginBottom: 18 }}
          onFocus={e => e.target.style.borderColor = '#ffd70099'} onBlur={e => e.target.style.borderColor = '#ffd70044'} />
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 8, padding: 10, color: '#7a9cc0', fontSize: 11, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>CANCEL</button>
          <button onClick={save} disabled={saving} style={{ flex: 2, background: '#ffd70020', border: '1px solid #ffd70055', borderRadius: 8, padding: 10, color: '#ffd700', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            {saving ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <Edit3 style={{ width: 12, height: 12 }} />}
            APPLY
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Confirm Delete Modal ─────────────────────────────────────────────────────
const ConfirmDelete = ({ msg, onConfirm, onClose, loading }) => (
  <div style={{ position: 'fixed', inset: 0, zIndex: 1002, background: '#000c', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
    <div style={{ background: 'linear-gradient(135deg,#060f1e,#0a1628)', border: '1px solid #ff3d7144', borderRadius: 12, padding: 24, width: 340, maxWidth: '92vw', animation: 'fadeUp .2s ease' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: '#ff3d7120', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <AlertCircle style={{ width: 16, height: 16, color: '#ff3d71' }} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace" }}>CONFIRM DELETE</span>
      </div>
      <p style={{ fontSize: 12, color: '#aac', marginBottom: 20, lineHeight: 1.6, fontFamily: "'Courier New',monospace" }}>{msg}</p>
      <div style={{ display: 'flex', gap: 10 }}>
        <button onClick={onClose} style={{ flex: 1, background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 8, padding: 10, color: '#7a9cc0', fontSize: 11, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>CANCEL</button>
        <button onClick={onConfirm} disabled={loading} style={{ flex: 1, background: '#ff3d7120', border: '1px solid #ff3d7155', borderRadius: 8, padding: 10, color: '#ff3d71', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          {loading ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <Trash2 style={{ width: 12, height: 12 }} />}
          DELETE
        </button>
      </div>
    </div>
  </div>
);

// ─── Pagination ───────────────────────────────────────────────────────────────
const Pages = ({ page, total, onChange }) => total <= 1 ? null : (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginTop: 14 }}>
    <button onClick={() => onChange(p => Math.max(1, p - 1))} disabled={page === 1}
      style={{ background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 6, padding: '6px 11px', color: page === 1 ? '#1a3a5c' : '#7a9cc0', cursor: page === 1 ? 'not-allowed' : 'pointer' }}>
      <ChevronLeft style={{ width: 13, height: 13 }} />
    </button>
    <span style={{ fontSize: 11, color: '#7a9cc0', fontFamily: "'Courier New',monospace" }}>
      PAGE <span style={{ color: '#bf5fff', fontWeight: 700 }}>{page}</span> / {total}
    </span>
    <button onClick={() => onChange(p => Math.min(total, p + 1))} disabled={page === total}
      style={{ background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 6, padding: '6px 11px', color: page === total ? '#1a3a5c' : '#7a9cc0', cursor: page === total ? 'not-allowed' : 'pointer' }}>
      <ChevronRight style={{ width: 13, height: 13 }} />
    </button>
  </div>
);

// ─── Decode JWT payload (no library needed) ───────────────────────────────────
function decodeJWT(token) {
  try {
    const payload = token.split('.')[1];
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    return decoded;
  } catch { return null; }
}

function getIsAdmin() {
  // Try all known token keys
  const token = localStorage.getItem('adminAccessToken')
    || localStorage.getItem('access_token')
    || localStorage.getItem('token');
  if (token) {
    const payload = decodeJWT(token);
    if (payload) {
      // Django SimpleJWT puts is_staff in token if configured
      if (payload.is_staff !== undefined) return !!payload.is_staff;
      if (payload.is_admin !== undefined) return !!payload.is_admin;
      if (payload.role === 'admin') return true;
    }
  }
  // Fallback: check localStorage keys directly
  const keys = ['user', 'userData', 'admin', 'profile'];
  for (const k of keys) {
    try {
      const v = JSON.parse(localStorage.getItem(k) || 'null');
      if (v?.is_staff) return true;
      if (v?.is_admin) return true;
      if (v?.role === 'admin') return true;
    } catch {}
  }
  return false;
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function Referral() {
  const [isAdmin, setIsAdmin] = useState(getIsAdmin());

  const [userStats, setUserStats]   = useState(null);
  const [copied, setCopied]         = useState(false);
  const [overview, setOverview]     = useState(null);
  const [chartData, setChartData]   = useState([]);
  const [chartDays, setChartDays]   = useState(30);
  const [referrals, setReferrals]   = useState([]);
  const [earnings, setEarnings]     = useState([]);
  const [settings, setSettings]     = useState(null);
  const [tab, setTab]               = useState('overview');
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch]         = useState('');
  const [page, setPage]             = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const PAGE_SIZE = 15;

  const [modal, setModal]           = useState(null); // null | 'settings' | 'create' | {adjust} | {delRef} | {delEarn}
  const [actioning, setActioning]   = useState(null); // id being actioned
  const { list: toasts, push: toast } = useToast();

  // ── Fetch user stats ──────────────────────────────────────────────────────
  const fetchUser = async () => {
    try { const r = await client.get('/referral/stats/'); setUserStats(r.data); } catch {}
    // Verify admin status from /profile/ API
    try {
      const meRes = await client.get('/profile/');
      if (meRes?.data) {
        const u = meRes.data;
        const admin = !!(u.is_staff || u.is_admin || u.is_superuser || u.role === 'admin');
        setIsAdmin(admin);
        try { localStorage.setItem('user', JSON.stringify(u)); } catch {}
      }
    } catch (e) {
      console.warn('[Referral] Profile fetch failed:', e?.response?.status);
    }
  };

  // ── Fetch admin data ──────────────────────────────────────────────────────
  const fetchAdmin = useCallback(async (t = tab, pg = page, silent = false) => {
    if (!isAdmin) return;
    if (!silent) setLoading(true); else setRefreshing(true);
    try {
      if (t === 'overview') {
        const [ov, st, ch] = await Promise.all([
          client.get('/referral/admin/overview/'),
          client.get('/referral/admin/settings/'),
          client.get('/referral/admin/stats-by-date/', { params: { days: chartDays } }),
        ]);
        setOverview(ov.data); setSettings(st.data); setChartData(ch.data.data ?? []);
      } else if (t === 'referrals') {
        const r = await client.get('/referral/admin/list/', { params: { page: pg, page_size: PAGE_SIZE, search } });
        setReferrals(r.data.results ?? []);
        setTotalPages(Math.ceil((r.data.total ?? 0) / PAGE_SIZE) || 1);
      } else if (t === 'earnings') {
        const r = await client.get('/referral/admin/earnings/', { params: { page: pg, page_size: PAGE_SIZE } });
        setEarnings(r.data.results ?? []);
        setTotalPages(Math.ceil((r.data.total ?? 0) / PAGE_SIZE) || 1);
      }
    } catch (e) { toast(e?.response?.data?.error || 'Load failed', 'error'); }
    finally { setLoading(false); setRefreshing(false); }
  }, [tab, page, search, chartDays, isAdmin]);

  // On mount: fetch user first, then admin data (isAdmin may update after fetchUser)
  useEffect(() => { fetchUser(); }, []); // eslint-disable-line
  // When isAdmin becomes true (after API verify), load admin data
  useEffect(() => {
    if (isAdmin) {
      setLoading(true);
      fetchAdmin(tab, 1);
    }
  }, [isAdmin]);
  useEffect(() => { if (isAdmin) { setPage(1); fetchAdmin(tab, 1); } }, [tab, search, chartDays]);
  useEffect(() => { if (isAdmin) fetchAdmin(tab, page); }, [page]);

  // ── Copy code ─────────────────────────────────────────────────────────────
  const copyCode = () => {
    const code = userStats?.refer_code; if (!code) return;
    navigator.clipboard.writeText(code).then(() => { setCopied(true); toast('Code copied!'); setTimeout(() => setCopied(false), 2000); });
  };

  // ── Give bonus ────────────────────────────────────────────────────────────
  const giveBonus = async (id) => {
    setActioning(id);
    try {
      const r = await client.post(`/referral/admin/give-bonus/${id}/`);
      toast(`Bonus given — referrer +${r.data.referrer_bonus}, user +${r.data.referred_bonus} coins`);
      fetchAdmin(tab, page, true);
    } catch (e) { toast(e?.response?.data?.error || 'Failed', 'error'); }
    finally { setActioning(null); }
  };

  // ── Toggle program ────────────────────────────────────────────────────────
  const toggleProgram = async () => {
    try {
      const r = await client.post('/referral/admin/toggle-program/');
      setOverview(p => p ? { ...p, program_active: r.data.is_active } : p);
      setSettings(p => p ? { ...p, is_active: r.data.is_active } : p);
      toast(`Program ${r.data.is_active ? 'activated' : 'paused'}`);
    } catch { toast('Toggle failed', 'error'); }
  };

  // ── Delete referral ───────────────────────────────────────────────────────
  const doDeleteReferral = async () => {
    const id = modal?.delRef?.id; if (!id) return;
    setActioning(id);
    try {
      await client.delete(`/referral/admin/delete/${id}/`);
      toast('Referral deleted'); setModal(null);
      fetchAdmin(tab, page, true);
    } catch { toast('Delete failed', 'error'); }
    finally { setActioning(null); }
  };

  // ── Delete earning ────────────────────────────────────────────────────────
  const doDeleteEarning = async () => {
    const id = modal?.delEarn?.id; if (!id) return;
    setActioning(id);
    try {
      await client.delete(`/referral/admin/earnings/delete/${id}/`);
      toast('Earning deleted'); setModal(null);
      fetchAdmin(tab, page, true);
    } catch { toast('Delete failed', 'error'); }
    finally { setActioning(null); }
  };

  const TH = ({ children }) => <th style={{ padding: '10px 14px', fontSize: 9, color: '#7a9cc0', letterSpacing: 1.5, fontFamily: "'Courier New',monospace", fontWeight: 700, textAlign: 'left', borderBottom: '1px solid #1a3a5c', whiteSpace: 'nowrap' }}>{children}</th>;
  const TD = ({ children, style = {} }) => <td style={{ padding: '10px 14px', fontSize: 11, color: '#c0d8f0', fontFamily: "'Courier New',monospace", borderBottom: '1px solid #1a3a5c18', ...style }}>{children}</td>;

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg,#020912 0%,#050e1a 50%,#030a14 100%)', color: '#e0f0ff', fontFamily: "'Segoe UI',sans-serif" }}>
      <style>{`
        @keyframes fadeUp  { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes spin    { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes slideIn { from{opacity:0;transform:translateX(12px)} to{opacity:1;transform:translateX(0)} }
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-thumb{background:#1a3a5c;border-radius:4px}
        tr:hover td { background: rgba(10,22,40,0.5) !important; }
        .act-btn:hover { opacity:.8; transform:translateY(-1px); }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ borderBottom: '1px solid #1a3a5c66', padding: '18px 26px 14px', background: 'linear-gradient(180deg,#040c18,transparent)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#7a9cc0', letterSpacing: 2, marginBottom: 12, fontFamily: "'Courier New',monospace" }}>
          <span>EARNNEXUS</span><ChevronRight style={{ width: 10, height: 10 }} /><span>ADMIN</span><ChevronRight style={{ width: 10, height: 10 }} /><span style={{ color: '#bf5fff' }}>REFERRAL</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: 10, background: 'linear-gradient(135deg,#bf5fff22,#bf5fff11)', border: '1px solid #bf5fff44', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px #bf5fff22' }}>
              <Users style={{ width: 20, height: 20, color: '#bf5fff' }} />
            </div>
            <div>
              <PageEndpointPanel pageKey="Referral" title="Referral Endpoints" />
              <h1 style={{ fontSize: 20, fontWeight: 900, letterSpacing: 3, fontFamily: "'Courier New',monospace", margin: 0, background: 'linear-gradient(90deg,#e0f0ff,#bf5fff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>REFERRAL PROGRAM</h1>
              <p style={{ fontSize: 10, color: '#7a9cc0', margin: 0, letterSpacing: 1, fontFamily: "'Courier New',monospace" }}>
                {isAdmin
                  ? `${overview?.total_referrals ?? '—'} REFERRALS · ${overview?.active_referrers ?? '—'} ACTIVE REFERRERS · PROGRAM ${overview?.program_active ? '● LIVE' : '○ PAUSED'}`
                  : `YOUR CODE: ${userStats?.refer_code ?? '…'} · ${userStats?.total_referrals ?? 0} REFERRALS`}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => { fetchUser(); fetchAdmin(tab, page, true); }} style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#1a3a5c22', border: '1px solid #1a3a5c', borderRadius: 8, padding: '8px 13px', color: refreshing ? '#00d4ff' : '#7a9cc0', fontSize: 10, cursor: 'pointer', fontFamily: "'Courier New',monospace", transition: 'all .2s' }}>
              <RefreshCw style={{ width: 12, height: 12, animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />REFRESH
            </button>
            {isAdmin && (
              <>
                <button onClick={toggleProgram} style={{ display: 'flex', alignItems: 'center', gap: 6, background: overview?.program_active ? '#ff6b3516' : '#00ff8816', border: `1px solid ${overview?.program_active ? '#ff6b3544' : '#00ff8844'}`, borderRadius: 8, padding: '8px 13px', color: overview?.program_active ? '#ff6b35' : '#00ff88', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace", transition: 'all .2s' }}>
                  {overview?.program_active ? <ToggleRight style={{ width: 13, height: 13 }} /> : <ToggleLeft style={{ width: 13, height: 13 }} />}
                  {overview?.program_active ? 'PAUSE' : 'ACTIVATE'}
                </button>
                <button onClick={() => setModal('create')} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'linear-gradient(135deg,#00d4ff22,#00d4ff0d)', border: '1px solid #00d4ff55', borderRadius: 8, padding: '8px 14px', color: '#00d4ff', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>
                  <Plus style={{ width: 13, height: 13 }} />CREATE
                </button>
                <button onClick={() => setModal('settings')} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'linear-gradient(135deg,#ffd70022,#ffd7000d)', border: '1px solid #ffd70055', borderRadius: 8, padding: '8px 14px', color: '#ffd700', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>
                  <Settings style={{ width: 13, height: 13 }} />SETTINGS
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      <div style={{ padding: '18px 26px' }}>

        {/* ── User referral code card ───────────────────────────────────────── */}
        <div style={{ background: 'linear-gradient(135deg,#bf5fff10,#bf5fff06)', border: '1px solid #bf5fff33', borderRadius: 12, padding: '16px 20px', marginBottom: 20, animation: 'fadeUp .4s ease both' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
            <div>
              <div style={{ fontSize: 9, color: '#bf5fff', letterSpacing: 2, fontFamily: "'Courier New',monospace", marginBottom: 6 }}>YOUR REFERRAL CODE</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 26, fontWeight: 900, color: '#e0f0ff', fontFamily: "'Courier New',monospace", letterSpacing: 5 }}>{userStats?.refer_code || '—'}</span>
                <button onClick={copyCode} className="act-btn" style={{ background: copied ? '#00ff8820' : '#bf5fff20', border: `1px solid ${copied ? '#00ff8855' : '#bf5fff55'}`, borderRadius: 6, padding: '6px 11px', color: copied ? '#00ff88' : '#bf5fff', fontSize: 10, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', gap: 5, transition: 'all .2s' }}>
                  {copied ? <CheckCheck style={{ width: 11, height: 11 }} /> : <Copy style={{ width: 11, height: 11 }} />}
                  {copied ? 'COPIED!' : 'COPY'}
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {[
                { l: 'REFERRED', v: userStats?.total_referrals ?? 0, c: '#bf5fff' },
                { l: 'COMMISSION', v: `${Number(userStats?.total_commission_earned ?? 0).toLocaleString()} coins`, c: '#ffd700' },
                { l: 'RECENT TXNS', v: userStats?.recent_earnings?.length ?? 0, c: '#00d4ff' },
              ].map(s => (
                <div key={s.l} style={{ background: '#0a1628', borderRadius: 8, padding: '8px 14px', textAlign: 'center', border: '1px solid #1a3a5c33', minWidth: 100 }}>
                  <div style={{ fontSize: 9, color: '#7a9cc0', letterSpacing: 1, fontFamily: "'Courier New',monospace", marginBottom: 3 }}>{s.l}</div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: s.c, fontFamily: "'Courier New',monospace" }}>{s.v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Admin panel ──────────────────────────────────────────────────── */}
        {isAdmin && (
          <>
            {/* Stats row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(170px,1fr))', gap: 10, marginBottom: 20 }}>
              <Stat label="TOTAL REFERRALS"  value={overview?.total_referrals ?? '—'}  icon={Users}      color="#bf5fff" loading={loading && !overview} />
              <Stat label="ACTIVE REFERRERS" value={overview?.active_referrers ?? '—'} icon={Activity}   color="#00d4ff" loading={loading && !overview} />
              <Stat label="COMMISSION PAID"  value={`${Number(overview?.total_commission_paid ?? 0).toLocaleString()}`} icon={DollarSign} color="#ffd700" loading={loading && !overview} sub="coins" />
              <Stat label="PROGRAM"          value={overview?.program_active ? 'LIVE' : 'PAUSED'} icon={Shield} color={overview?.program_active ? '#00ff88' : '#ff6b35'} loading={loading && !overview} />
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid #1a3a5c33' }}>
              {[
                { k: 'overview',  l: 'OVERVIEW',  I: BarChart2 },
                { k: 'referrals', l: 'REFERRALS', I: Users },
                { k: 'earnings',  l: 'EARNINGS',  I: TrendingUp },
              ].map(t => (
                <button key={t.k} onClick={() => setTab(t.k)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', borderBottom: `2px solid ${tab === t.k ? '#bf5fff' : 'transparent'}`, padding: '9px 14px', color: tab === t.k ? '#bf5fff' : '#7a9cc0', fontSize: 10, cursor: 'pointer', fontFamily: "'Courier New',monospace", fontWeight: tab === t.k ? 700 : 400, letterSpacing: 1, transition: 'all .2s', marginBottom: -1 }}>
                  <t.I style={{ width: 12, height: 12 }} />{t.l}
                </button>
              ))}
              {/* search */}
              {tab === 'referrals' && (
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 7, background: '#050b14', border: '1px solid #1a3a5c', borderRadius: 7, padding: '5px 11px', marginBottom: 4 }}>
                  <Search style={{ width: 11, height: 11, color: '#7a9cc0' }} />
                  <input placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)}
                    style={{ background: 'none', border: 'none', outline: 'none', color: '#e0f0ff', fontSize: 11, width: 130, fontFamily: "'Courier New',monospace" }} />
                </div>
              )}
              {/* chart days selector */}
              {tab === 'overview' && (
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 4, alignItems: 'center', marginBottom: 4 }}>
                  {[7, 14, 30].map(d => (
                    <button key={d} onClick={() => setChartDays(d)} style={{ background: chartDays === d ? '#bf5fff20' : 'transparent', border: `1px solid ${chartDays === d ? '#bf5fff55' : '#1a3a5c'}`, borderRadius: 5, padding: '4px 10px', color: chartDays === d ? '#bf5fff' : '#7a9cc0', fontSize: 10, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>{d}D</button>
                  ))}
                </div>
              )}
            </div>

            {/* ── Overview ─────────────────────────────────────────────────── */}
            {tab === 'overview' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, animation: 'fadeUp .3s ease both' }}>
                {/* Chart */}
                <div style={{ background: '#060f1e', border: '1px solid #bf5fff33', borderRadius: 10, padding: '16px 18px' }}>
                  <div style={{ fontSize: 10, color: '#bf5fff', fontWeight: 700, fontFamily: "'Courier New',monospace", letterSpacing: 1, marginBottom: 14 }}>COMMISSION EARNED — LAST {chartDays} DAYS</div>
                  <MiniChart data={chartData} color="#bf5fff" />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 9, color: '#7a9cc044', fontFamily: "'Courier New',monospace" }}>
                    <span>{chartData[0]?.date || ''}</span><span>{chartData[chartData.length - 1]?.date || ''}</span>
                  </div>
                </div>

                {/* Settings preview */}
                <div style={{ background: '#060f1e', border: '1px solid #ffd70033', borderRadius: 10, padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: '#ffd700', fontFamily: "'Courier New',monospace", letterSpacing: 1 }}>CURRENT SETTINGS</span>
                    <button onClick={() => setModal('settings')} style={{ background: '#ffd70016', border: '1px solid #ffd70033', borderRadius: 5, padding: '3px 9px', color: '#ffd700', fontSize: 9, cursor: 'pointer', fontFamily: "'Courier New',monospace" }}>EDIT</button>
                  </div>
                  {loading && !settings ? (
                    <><SK h={13} s={{ marginBottom: 8 }} /><SK h={13} s={{ marginBottom: 8 }} /><SK h={13} /></>
                  ) : settings ? [
                    { l: 'Referrer bonus', v: `${settings.referrer_signup_bonus} coins` },
                    { l: 'New user bonus', v: `${settings.direct_signup_bonus} coins` },
                    { l: 'Commission rate', v: `${settings.lifetime_commission_rate}%` },
                    { l: 'Status', v: settings.is_active ? '✓ LIVE' : '✗ PAUSED' },
                  ].map(r => (
                    <div key={r.l} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #1a3a5c22' }}>
                      <span style={{ fontSize: 11, color: '#7a9cc0', fontFamily: "'Courier New',monospace" }}>{r.l}</span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace" }}>{r.v}</span>
                    </div>
                  )) : null}
                </div>

                {/* Top referrers */}
                <div style={{ background: '#060f1e', border: '1px solid #00d4ff33', borderRadius: 10, padding: '16px 18px', gridColumn: '1/-1' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#00d4ff', fontFamily: "'Courier New',monospace", letterSpacing: 1, display: 'block', marginBottom: 14 }}>TOP REFERRERS</span>
                  {loading && !overview ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{[1,2,3,4,5].map(i => <SK key={i} h={30} r={6} />)}</div>
                  ) : (overview?.top_referrers ?? []).length === 0 ? (
                    <div style={{ textAlign: 'center', color: '#7a9cc044', fontFamily: "'Courier New',monospace", fontSize: 11, padding: '20px 0' }}>NO DATA YET</div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 8 }}>
                      {(overview?.top_referrers ?? []).map((r, i) => (
                        <div key={r.id} style={{ background: i === 0 ? '#ffd70008' : '#0a1628', borderRadius: 8, padding: '10px 12px', border: `1px solid ${i < 3 ? ['#ffd70033','#aaa22','#cd7f3222'][i] : '#1a3a5c22'}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{ width: 24, height: 24, borderRadius: 6, background: i < 3 ? ['#ffd70033','#aaa22','#cd7f3222'][i] : '#1a3a5c22', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800, color: i < 3 ? ['#ffd700','#aaa','#cd7f32'][i] : '#7a9cc0', fontFamily: "'Courier New',monospace", flexShrink: 0 }}>#{i + 1}</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, color: '#e0f0ff', fontFamily: "'Courier New',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.username}</div>
                            <div style={{ fontSize: 10, color: '#7a9cc0', fontFamily: "'Courier New',monospace" }}>{r.referral_count} refs</div>
                          </div>
                          <div style={{ fontSize: 12, fontWeight: 800, color: '#ffd700', fontFamily: "'Courier New',monospace" }}>{Number(r.total_earned).toLocaleString()}c</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Referrals table ───────────────────────────────────────────── */}
            {tab === 'referrals' && (
              <div style={{ animation: 'fadeUp .3s ease both' }}>
                <div style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid #1a3a5c33' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', background: '#060f1e' }}>
                    <thead><tr>
                      <TH>REFERRER</TH><TH>REFERRED USER</TH><TH>BONUS</TH>
                      <TH>COMMISSION</TH><TH>JOINED</TH><TH>ACTIONS</TH>
                    </tr></thead>
                    <tbody>
                      {loading ? Array(8).fill(0).map((_, i) => (
                        <tr key={i}>{[1,2,3,4,5,6].map(j => <td key={j} style={{ padding: '11px 14px' }}><SK h={11} r={3} /></td>)}</tr>
                      )) : referrals.length === 0 ? (
                        <tr><TD style={{ textAlign: 'center', padding: '40px', color: '#7a9cc033', gridColumn: '1/-1' }}>NO REFERRALS FOUND</TD></tr>
                      ) : referrals.map(r => (
                        <tr key={r.id}>
                          <TD><span style={{ color: '#00d4ff', fontWeight: 700 }}>{r.referrer}</span></TD>
                          <TD>{r.referred_user}</TD>
                          <TD>
                            {r.signup_bonus_given
                              ? <span style={{ color: '#00ff88', fontWeight: 700 }}>✓ GIVEN</span>
                              : <button onClick={() => giveBonus(r.id)} disabled={actioning === r.id} className="act-btn" style={{ background: '#ffd70016', border: '1px solid #ffd70033', borderRadius: 5, padding: '4px 9px', color: '#ffd700', fontSize: 9, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', gap: 4 }}>
                                  {actioning === r.id ? <Loader2 style={{ width: 10, height: 10, animation: 'spin 1s linear infinite' }} /> : <Gift style={{ width: 10, height: 10 }} />}
                                  GIVE BONUS
                                </button>}
                          </TD>
                          <TD><span style={{ color: '#ffd700', fontWeight: 700 }}>{Number(r.total_commission_earned).toLocaleString()}</span> <span style={{ color: '#7a9cc0' }}>coins</span></TD>
                          <TD style={{ color: '#7a9cc0' }}>{r.joined_at}</TD>
                          <TD>
                            <div style={{ display: 'flex', gap: 5 }}>
                              <button onClick={() => setModal({ adjust: r })} className="act-btn" style={{ background: '#ffd70016', border: '1px solid #ffd70033', borderRadius: 5, padding: '5px 9px', color: '#ffd700', fontSize: 9, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', gap: 4 }} title="Adjust commission">
                                <Edit3 style={{ width: 10, height: 10 }} />ADJ
                              </button>
                              <button onClick={() => setModal({ delRef: r })} className="act-btn" style={{ background: '#ff3d7116', border: '1px solid #ff3d7133', borderRadius: 5, padding: '5px 9px', color: '#ff3d71', fontSize: 9, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', gap: 4 }} title="Delete referral">
                                <Trash2 style={{ width: 10, height: 10 }} />DEL
                              </button>
                            </div>
                          </TD>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pages page={page} total={totalPages} onChange={setPage} />
              </div>
            )}

            {/* ── Earnings table ────────────────────────────────────────────── */}
            {tab === 'earnings' && (
              <div style={{ animation: 'fadeUp .3s ease both' }}>
                <div style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid #1a3a5c33' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', background: '#060f1e' }}>
                    <thead><tr>
                      <TH>REFERRER</TH><TH>FROM USER</TH><TH>AMOUNT</TH><TH>RATE</TH><TH>DATE</TH><TH>ACTION</TH>
                    </tr></thead>
                    <tbody>
                      {loading ? Array(8).fill(0).map((_, i) => (
                        <tr key={i}>{[1,2,3,4,5,6].map(j => <td key={j} style={{ padding: '11px 14px' }}><SK h={11} r={3} /></td>)}</tr>
                      )) : earnings.length === 0 ? (
                        <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#7a9cc033', fontFamily: "'Courier New',monospace", fontSize: 11 }}>NO EARNINGS YET</td></tr>
                      ) : earnings.map(e => (
                        <tr key={e.id}>
                          <TD><span style={{ color: '#00d4ff', fontWeight: 700 }}>{e.referrer}</span></TD>
                          <TD>{e.referred_user}</TD>
                          <TD><span style={{ color: '#00ff88', fontWeight: 800 }}>+{Number(e.amount).toLocaleString()}</span> <span style={{ color: '#7a9cc0' }}>coins</span></TD>
                          <TD><span style={{ color: '#bf5fff' }}>{e.commission_rate}%</span></TD>
                          <TD style={{ color: '#7a9cc0' }}>{e.date}</TD>
                          <TD>
                            <button onClick={() => setModal({ delEarn: e })} className="act-btn" style={{ background: '#ff3d7116', border: '1px solid #ff3d7133', borderRadius: 5, padding: '5px 9px', color: '#ff3d71', fontSize: 9, cursor: 'pointer', fontFamily: "'Courier New',monospace", display: 'flex', alignItems: 'center', gap: 4 }}>
                              <Trash2 style={{ width: 10, height: 10 }} />DEL
                            </button>
                          </TD>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pages page={page} total={totalPages} onChange={setPage} />
              </div>
            )}
          </>
        )}

        {/* ── Non-admin: own referred users grid ───────────────────────────── */}
        {!isAdmin && (
          <div style={{ marginTop: 4 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#bf5fff', fontFamily: "'Courier New',monospace", letterSpacing: 1.2, marginBottom: 14 }}>YOUR REFERRED USERS</div>
            {(userStats?.referrals ?? []).length === 0 ? (
              <div style={{ textAlign: 'center', padding: '50px', border: '1px dashed #1a3a5c', borderRadius: 10 }}>
                <Users style={{ width: 32, height: 32, color: '#1a3a5c', margin: '0 auto 12px' }} />
                <div style={{ fontSize: 12, color: '#7a9cc0', fontFamily: "'Courier New',monospace" }}>NO REFERRALS YET — SHARE YOUR CODE!</div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 10 }}>
                {(userStats?.referrals ?? []).map((r, i) => (
                  <div key={i} style={{ background: '#060f1e', border: '1px solid #bf5fff22', borderRadius: 10, padding: '14px 16px', animation: `fadeUp .3s ease ${i * .05}s both` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 8, background: '#bf5fff22', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800, color: '#bf5fff', fontFamily: "'Courier New',monospace" }}>{r.username.charAt(0).toUpperCase()}</div>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#e0f0ff', fontFamily: "'Courier New',monospace" }}>{r.username}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 9, color: '#7a9cc0', fontFamily: "'Courier New',monospace" }}>COMMISSION</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#ffd700', fontFamily: "'Courier New',monospace" }}>{Number(r.commission_earned).toLocaleString()} coins</span>
                    </div>
                    <div style={{ fontSize: 9, color: '#7a9cc033', marginTop: 5, fontFamily: "'Courier New',monospace" }}>{r.joined_at}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modals ─────────────────────────────────────────────────────────── */}
      {modal === 'settings' && settings && (
        <SettingsModal settings={settings} onClose={() => setModal(null)} onSaved={() => fetchAdmin('overview', 1, true)} toast={toast} />
      )}
      {modal === 'create' && (
        <CreateModal onClose={() => setModal(null)} onCreated={() => fetchAdmin(tab, page, true)} toast={toast} />
      )}
      {modal?.adjust && (
        <AdjustModal referral={modal.adjust} onClose={() => setModal(null)} onDone={() => fetchAdmin(tab, page, true)} toast={toast} />
      )}
      {modal?.delRef && (
        <ConfirmDelete
          msg={`Delete referral: "${modal.delRef.referrer}" → "${modal.delRef.referred_user}"? This cannot be undone.`}
          onConfirm={doDeleteReferral} onClose={() => setModal(null)} loading={!!actioning}
        />
      )}
      {modal?.delEarn && (
        <ConfirmDelete
          msg={`Delete earning record: +${modal.delEarn.amount} coins from "${modal.delEarn.referred_user}" to "${modal.delEarn.referrer}"?`}
          onConfirm={doDeleteEarning} onClose={() => setModal(null)} loading={!!actioning}
        />
      )}

      <Toasts list={toasts} />
    </div>
  );
}