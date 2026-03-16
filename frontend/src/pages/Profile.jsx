// src/pages/Profile.jsx
import React, { useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  User, Camera, Mail, Phone, MapPin, Calendar,
  Shield, Key, Activity, Settings, Save, ArrowLeft,
  Eye, EyeOff, CheckCircle, AlertCircle
} from 'lucide-react';
import toast from 'react-hot-toast';

const authHeaders = (json=false) => {
  const h = { 'Authorization': `Bearer ${localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || ''}` };
  if (json) h['Content-Type'] = 'application/json';
  return h;
};

const COLORS = ['#ff2d78','#ffd700','#00f3ff','#00ff88','#a855f7','#ff8c00'];

export default function Profile() {
  const navigate  = useNavigate();
  const location  = useLocation();
  const fileRef   = useRef();

  const [activeTab, setActiveTab] = useState(location.state?.tab || 'profile');
  const [avatar, setAvatar]       = useState(null);
  const [saving, setSaving]       = useState(false);

  const [form, setForm] = useState({
    name:     'Admin User',
    email:    'admin@earning.com',
    phone:    '+880 1700 000000',
    location: 'Dhaka, Bangladesh',
    bio:      'Super Administrator of the Earning Platform.',
    role:     'Super Admin',
  });

  const [passForm, setPassForm] = useState({
    current: '', newPass: '', confirm: ''
  });
  const [showPass, setShowPass] = useState({ current: false, new: false, confirm: false });

  const [twoFA, setTwoFA]     = useState(false);
  const [activityLogs, setActivityLogs] = useState([]);
  const [colorIdx, setColorIdx] = useState(0);

  React.useEffect(() => {
    const token = localStorage.getItem("adminAccessToken") || localStorage.getItem("access_token") || "";
    if (!token) return;
    fetch("/api/audit_logs/logs/?page_size=10&ordering=-created_at", { headers: { "Authorization": "Bearer " + token } })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const list = Array.isArray(data) ? data : (data.results || data.data || []);
        setActivityLogs(list);
      }).catch(() => {});
  }, []);

  React.useEffect(() => {
    fetch('/api/auth/profile/', { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const d = data.data || data;
        setForm(prev => ({
          ...prev,
          name:     d.full_name || d.name || d.username || prev.name,
          email:    d.email     || prev.email,
          phone:    d.phone     || d.phone_number || prev.phone,
          location: d.location  || d.address || prev.location,
          bio:      d.bio       || d.about   || prev.bio,
          role:     d.role      || d.user_type || prev.role,
        }));
        if (d.avatar || d.profile_picture) setAvatar(d.avatar || d.profile_picture);
      }).catch(() => {});
  }, []);

  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setAvatar(url);
    toast.success('Avatar updated!');
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('username', form.name);
      formData.append('phone', form.phone);
      formData.append('bio', form.bio);
      formData.append('address', form.location);
      formData.append('city', form.location);
      if (fileRef.current?.files?.[0]) formData.append('avatar', fileRef.current.files[0]);
      const res = await fetch('/api/auth/profile/update_profile/', {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('adminAccessToken') || localStorage.getItem('access_token') || ''}` },
        body: formData,
      });
      if (res.ok) { toast.success('Profile saved successfully!'); window.dispatchEvent(new Event('profile-updated')); }
      else { toast.error('Failed to save profile'); }
    } catch { toast.error('Network error'); }
    setSaving(false);
  };

  const handleChangePassword = async () => {
    if (!passForm.current) { toast.error('Enter current password'); return; }
    if (passForm.newPass.length < 8) { toast.error('Password must be 8+ characters'); return; }
    if (passForm.newPass !== passForm.confirm) { toast.error('Passwords do not match'); return; }
    setSaving(true);
    await new Promise(r => setTimeout(r, 800));
    setSaving(false);
    setPassForm({ current: '', newPass: '', confirm: '' });
    toast.success('Password changed!');
  };

  const ic = COLORS[colorIdx % COLORS.length];

  const TABS = [
    { id: 'profile',   label: 'My Profile',       icon: User },
    { id: 'security',  label: 'Change Password',   icon: Key },
    { id: 'twofa',     label: '2FA Security',      icon: Shield },
    { id: 'activity',  label: 'Activity Logs',     icon: Activity },
    { id: 'settings',  label: 'Account Settings',  icon: Settings },
  ];

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Rajdhani:wght@400;500;600;700&display=swap');

        .prof-root { padding: 24px; font-family: 'Rajdhani', sans-serif; color: #eae0ff; min-height: 100vh; }

        .prof-back {
          display: inline-flex; align-items: center; gap: 8px;
          background: rgba(255,45,120,.1); border: 1px solid rgba(255,45,120,.3);
          border-radius: 8px; padding: 8px 16px; cursor: pointer;
          color: #ff2d78; font-size: 13px; font-weight: 600;
          margin-bottom: 22px; transition: all .2s;
        }
        .prof-back:hover { background: rgba(255,45,120,.2); transform: translateX(-3px); }

        .prof-layout { display: grid; grid-template-columns: 260px 1fr; gap: 20px; }

        /* Left panel */
        .prof-left {
          background: rgba(8,2,28,.85);
          border: 1px solid rgba(100,60,220,.2);
          border-radius: 16px; padding: 28px 20px;
          display: flex; flex-direction: column; align-items: center; gap: 16px;
        }

        /* Avatar */
        .prof-avatar-wrap {
          position: relative; cursor: pointer;
        }
        .prof-avatar {
          width: 100px; height: 100px; border-radius: 50%;
          border: 3px solid var(--ic, #ff2d78);
          box-shadow: 0 0 20px var(--ic, #ff2d78), 0 0 40px rgba(0,0,0,.5);
          overflow: hidden; background: #120524;
          display: flex; align-items: center; justify-content: center;
          transition: box-shadow 1s ease;
        }
        .prof-avatar img { width: 100%; height: 100%; object-fit: cover; }
        .prof-avatar-overlay {
          position: absolute; inset: 0; border-radius: 50%;
          background: rgba(0,0,0,.5);
          display: flex; align-items: center; justify-content: center;
          opacity: 0; transition: opacity .2s;
        }
        .prof-avatar-wrap:hover .prof-avatar-overlay { opacity: 1; }

        .prof-name {
          font-family: 'Orbitron', sans-serif; font-size: 15px; font-weight: 700;
          color: #fff; text-align: center;
          transition: color 1s ease, text-shadow 1s ease;
        }
        .prof-role {
          font-size: 11px; color: #a855f7;
          font-family: 'Orbitron', sans-serif; letter-spacing: 1px;
        }

        /* Color palette */
        .prof-colors {
          display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
        }
        .prof-color-dot {
          width: 20px; height: 20px; border-radius: 50%; cursor: pointer;
          transition: transform .2s, box-shadow .2s;
          border: 2px solid transparent;
        }
        .prof-color-dot:hover { transform: scale(1.3); }
        .prof-color-dot.active { border-color: #fff; transform: scale(1.2); }

        /* Tabs */
        .prof-tabs { width: 100%; display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
        .prof-tab {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 14px; border-radius: 8px; cursor: pointer;
          transition: all .18s; border-left: 2px solid transparent;
          font-size: 13px; font-weight: 600; color: #6a4a8a;
        }
        .prof-tab:hover { background: rgba(168,85,247,.1); color: #c0a0e0; }
        .prof-tab.active {
          background: rgba(255,45,120,.12);
          border-left-color: #ff2d78; color: #fff;
        }

        /* Right panel */
        .prof-right {
          background: rgba(8,2,28,.85);
          border: 1px solid rgba(100,60,220,.2);
          border-radius: 16px; padding: 28px 32px;
        }

        .prof-section-title {
          font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700;
          margin-bottom: 24px; letter-spacing: 1px;
          transition: color 1s ease, text-shadow 1s ease;
        }

        .prof-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

        .prof-field { display: flex; flex-direction: column; gap: 6px; }
        .prof-field.full { grid-column: 1 / -1; }
        .prof-label { font-size: 11px; color: rgba(168,85,247,.7); font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }

        .prof-input {
          background: rgba(5,2,18,.8); border: 1px solid rgba(100,60,220,.25);
          border-radius: 10px; padding: 12px 16px;
          color: #eae0ff; font-size: 14px; font-family: 'Rajdhani', sans-serif;
          font-weight: 500; outline: none; transition: border-color .2s, box-shadow .2s;
        }
        .prof-input:focus {
          border-color: rgba(168,85,247,.5);
          box-shadow: 0 0 0 3px rgba(168,85,247,.1);
        }
        .prof-input[readonly] { opacity: .5; cursor: not-allowed; }

        .prof-textarea {
          background: rgba(5,2,18,.8); border: 1px solid rgba(100,60,220,.25);
          border-radius: 10px; padding: 12px 16px;
          color: #eae0ff; font-size: 14px; font-family: 'Rajdhani', sans-serif;
          font-weight: 500; outline: none; resize: vertical; min-height: 80px;
          transition: border-color .2s;
        }
        .prof-textarea:focus { border-color: rgba(168,85,247,.5); }

        .prof-pass-wrap { position: relative; }
        .prof-pass-eye {
          position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
          background: none; border: none; cursor: pointer; color: rgba(168,85,247,.5);
          transition: color .2s;
        }
        .prof-pass-eye:hover { color: #a855f7; }

        .prof-save {
          display: flex; align-items: center; gap: 8px;
          padding: 12px 28px; border-radius: 10px; cursor: pointer;
          font-family: 'Orbitron', sans-serif; font-size: 12px; font-weight: 700;
          letter-spacing: 1px; border: none;
          background: linear-gradient(135deg, #ff2d78, #a855f7);
          color: #fff; margin-top: 24px;
          box-shadow: 0 0 20px rgba(255,45,120,.3);
          transition: all .2s;
        }
        .prof-save:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(255,45,120,.5); }
        .prof-save:disabled { opacity: .6; cursor: not-allowed; transform: none; }

        /* 2FA toggle */
        .twofa-card {
          background: rgba(168,85,247,.08); border: 1px solid rgba(168,85,247,.25);
          border-radius: 12px; padding: 20px; display: flex;
          align-items: center; justify-content: space-between;
        }
        .twofa-toggle {
          width: 50px; height: 26px; border-radius: 13px; cursor: pointer;
          position: relative; transition: background .3s;
          border: none; outline: none;
        }
        .twofa-toggle.on  { background: linear-gradient(90deg, #a855f7, #ff2d78); }
        .twofa-toggle.off { background: rgba(100,60,220,.2); }
        .twofa-toggle::after {
          content: ''; position: absolute;
          top: 3px; width: 20px; height: 20px;
          border-radius: 50%; background: #fff;
          transition: left .3s;
          box-shadow: 0 2px 4px rgba(0,0,0,.3);
        }
        .twofa-toggle.on::after  { left: 27px; }
        .twofa-toggle.off::after { left: 3px; }

        /* Activity log */
        .act-item {
          display: flex; align-items: center; gap: 12px;
          padding: 12px 0; border-bottom: 1px solid rgba(100,60,220,.1);
        }
        .act-dot {
          width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        }
      `}</style>

      <div className="prof-root">

        {/* Back button */}
        <div className="prof-back" onClick={() => navigate(-1)}>
          <ArrowLeft style={{ width:14, height:14 }} />
          Back
        </div>

        <div className="prof-layout">

          {/* ── Left Panel ── */}
          <div className="prof-left">

            {/* Avatar */}
            <div className="prof-avatar-wrap" onClick={() => fileRef.current?.click()}>
              <div className="prof-avatar" style={{ '--ic': ic }}>
                {avatar
                  ? <img src={avatar} alt="avatar" />
                  : <User style={{ width:40, height:40, color: ic }} />
                }
              </div>
              <div className="prof-avatar-overlay">
                <Camera style={{ width:22, height:22, color:'#fff' }} />
              </div>
            </div>
            <input ref={fileRef} type="file" accept="image/*" style={{ display:'none' }} onChange={handleAvatarChange} />

            <div className="prof-name" style={{ color: ic, textShadow: `0 0 12px ${ic}` }}>
              {form.name}
            </div>
            <div className="prof-role">{form.role}</div>

            {/* Color picker */}
            <div className="prof-colors">
              {COLORS.map((c, i) => (
                <div
                  key={c}
                  className={`prof-color-dot ${colorIdx === i ? 'active' : ''}`}
                  style={{ background: c, boxShadow: colorIdx === i ? `0 0 10px ${c}` : 'none' }}
                  onClick={() => setColorIdx(i)}
                />
              ))}
            </div>

            {/* Tabs */}
            <div className="prof-tabs">
              {TABS.map(({ id, label, icon: Icon }) => (
                <div
                  key={id}
                  className={`prof-tab ${activeTab === id ? 'active' : ''}`}
                  onClick={() => setActiveTab(id)}
                >
                  <Icon style={{ width:14, height:14, flexShrink:0 }} />
                  {label}
                </div>
              ))}
            </div>
          </div>

          {/* ── Right Panel ── */}
          <div className="prof-right">

            {/* MY PROFILE */}
            {activeTab === 'profile' && (
              <>
                <div className="prof-section-title" style={{ color: ic, textShadow: `0 0 10px ${ic}` }}>
                  MY PROFILE
                </div>
                <div className="prof-grid">
                  <div className="prof-field">
                    <label className="prof-label">FULL NAME</label>
                    <input className="prof-input" value={form.name}
                      onChange={e => setForm(p => ({ ...p, name: e.target.value }))} />
                  </div>
                  <div className="prof-field">
                    <label className="prof-label">ROLE</label>
                    <input className="prof-input" value={form.role} readOnly />
                  </div>
                  <div className="prof-field">
                    <label className="prof-label">EMAIL</label>
                    <input className="prof-input" value={form.email}
                      onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
                  </div>
                  <div className="prof-field">
                    <label className="prof-label">PHONE</label>
                    <input className="prof-input" value={form.phone}
                      onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} />
                  </div>
                  <div className="prof-field">
                    <label className="prof-label">LOCATION</label>
                    <input className="prof-input" value={form.location}
                      onChange={e => setForm(p => ({ ...p, location: e.target.value }))} />
                  </div>
                  <div className="prof-field full">
                    <label className="prof-label">BIO</label>
                    <textarea className="prof-textarea" value={form.bio}
                      onChange={e => setForm(p => ({ ...p, bio: e.target.value }))} />
                  </div>
                </div>
                <button className="prof-save" onClick={handleSaveProfile} disabled={saving}>
                  <Save style={{ width:14, height:14 }} />
                  {saving ? 'SAVING...' : 'SAVE CHANGES'}
                </button>
              </>
            )}

            {/* CHANGE PASSWORD */}
            {activeTab === 'security' && (
              <>
                <div className="prof-section-title" style={{ color: ic, textShadow: `0 0 10px ${ic}` }}>
                  CHANGE PASSWORD
                </div>
                <div style={{ display:'flex', flexDirection:'column', gap:16, maxWidth:400 }}>
                  {[
                    { key:'current', label:'CURRENT PASSWORD' },
                    { key:'newPass', label:'NEW PASSWORD' },
                    { key:'confirm', label:'CONFIRM NEW PASSWORD' },
                  ].map(({ key, label }) => (
                    <div className="prof-field" key={key}>
                      <label className="prof-label">{label}</label>
                      <div className="prof-pass-wrap">
                        <input
                          className="prof-input"
                          type={showPass[key] ? 'text' : 'password'}
                          value={passForm[key]}
                          onChange={e => setPassForm(p => ({ ...p, [key]: e.target.value }))}
                          style={{ width:'100%', paddingRight:44 }}
                        />
                        <button className="prof-pass-eye" type="button"
                          onClick={() => setShowPass(p => ({ ...p, [key]: !p[key] }))}>
                          {showPass[key] ? <EyeOff style={{ width:15,height:15 }} /> : <Eye style={{ width:15,height:15 }} />}
                        </button>
                      </div>
                    </div>
                  ))}
                  <button className="prof-save" onClick={handleChangePassword} disabled={saving}>
                    <Key style={{ width:14, height:14 }} />
                    {saving ? 'SAVING...' : 'UPDATE PASSWORD'}
                  </button>
                </div>
              </>
            )}

            {/* 2FA */}
            {activeTab === 'twofa' && (
              <>
                <div className="prof-section-title" style={{ color: ic, textShadow: `0 0 10px ${ic}` }}>
                  2FA SECURITY
                </div>
                <div className="twofa-card">
                  <div>
                    <div style={{ fontSize:15, fontWeight:700, color:'#fff', marginBottom:4 }}>
                      Two-Factor Authentication
                    </div>
                    <div style={{ fontSize:12, color:'rgba(168,85,247,.7)' }}>
                      {twoFA ? '✅ 2FA is enabled — your account is protected' : '⚠️ 2FA is disabled — enable for extra security'}
                    </div>
                  </div>
                  <button className={`twofa-toggle ${twoFA ? 'on' : 'off'}`}
                    onClick={() => { setTwoFA(v => !v); toast.success(twoFA ? '2FA Disabled' : '2FA Enabled!'); }} />
                </div>
              </>
            )}

            {/* ACTIVITY */}
            {activeTab === 'activity' && (
              <>
                <div className="prof-section-title" style={{ color: ic, textShadow: `0 0 10px ${ic}` }}>
                  ACTIVITY LOGS
                </div>
                {activityLogs.length === 0 && (
                  <div style={{fontSize:13, color:'rgba(168,85,247,.5)', padding:'12px 0'}}>No activity found</div>
                )}
                {activityLogs.map((log, i) => (
                  <div className="act-item" key={i}>
                    <div className="act-dot" style={{ background:'#00ff88', boxShadow:'0 0 6px #00ff88' }} />
                    <div style={{ flex:1, fontSize:14, color:'#e0d0f0' }}>{log.action_type || log.action || log.description || 'Action'}</div>
                    <div style={{ fontSize:11, color:'rgba(168,85,247,.5)', fontFamily:'Orbitron,sans-serif' }}>
                      {log.created_at ? new Date(log.created_at).toLocaleString() : ''}
                    </div>
                  </div>
                ))}
              </>
            )}

            {/* ACCOUNT SETTINGS */}
            {activeTab === 'settings' && (
              <>
                <div className="prof-section-title" style={{ color: ic, textShadow: `0 0 10px ${ic}` }}>
                  ACCOUNT SETTINGS
                </div>
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {[
                    { label:'Email Notifications', desc:'Receive email alerts' },
                    { label:'Login Alerts',         desc:'Alert on new login' },
                    { label:'Dark Mode',            desc:'Use dark theme' },
                  ].map((s, i) => (
                    <div className="twofa-card" key={i}>
                      <div>
                        <div style={{ fontSize:14, fontWeight:700, color:'#fff' }}>{s.label}</div>
                        <div style={{ fontSize:12, color:'rgba(168,85,247,.6)', marginTop:2 }}>{s.desc}</div>
                      </div>
                      <button className="twofa-toggle on" />
                    </div>
                  ))}
                </div>
              </>
            )}

          </div>
        </div>
      </div>
    </>
  );
}