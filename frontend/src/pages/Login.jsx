// src/pages/Login.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';
import toast from 'react-hot-toast';
import { Eye, EyeOff, Mail, Lock } from 'lucide-react';

const Login = () => {
  const [username, setUsername]   = useState('');
  const [password, setPassword]   = useState('');
  const [loading,  setLoading]    = useState(false);
  const [showPass, setShowPass]   = useState(false);
  const [remember, setRemember]   = useState(true);
  const [mounted,  setMounted]    = useState(false);
  const navigate = useNavigate();

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const handleLogin = async e => {
    e.preventDefault();
    if (!username || !password) { toast.error('Please fill in all fields'); return; }
    try {
      setLoading(true);
      const res = await client.post('/auth/login/', { username_or_email: username, password });
      const token = res.data.tokens?.access || res.data.tokens?.token || res.data.access || res.data.token;
      if (token) {
        localStorage.setItem('adminAccessToken', token);
        if (res.data.tokens?.refresh || res.data.refresh) {
          localStorage.setItem('adminRefreshToken', res.data.tokens?.refresh || res.data.refresh);
        }
        toast.success('Welcome back!');
        setTimeout(() => navigate('/'), 500);
      } else throw new Error('No token');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed. Check your credentials.');
    } finally { setLoading(false); }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .lp-root {
          min-height: 100vh;
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #020818;
          position: relative;
          overflow: hidden;
          font-family: 'Exo 2', sans-serif;
        }

        /* ── Deep space background ── */
        .lp-bg {
          position: absolute;
          inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 50% 0%,   #0a1a4a 0%, transparent 70%),
            radial-gradient(ellipse 60% 50% at 80% 60%,  #0d0a2e 0%, transparent 60%),
            radial-gradient(ellipse 50% 40% at 20% 80%,  #0a1535 0%, transparent 60%),
            radial-gradient(ellipse 100% 100% at 50% 50%, #020818 0%, #020818 100%);
          z-index: 0;
        }

        /* Stars */
        .lp-stars {
          position: absolute;
          inset: 0;
          z-index: 1;
          background-image:
            radial-gradient(1px 1px at 5%  8%,  rgba(255,255,255,.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 12% 22%, rgba(255,255,255,.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 18% 55%, rgba(180,200,255,.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 25% 80%, rgba(255,255,255,.6) 0%, transparent 100%),
            radial-gradient(2px 2px at 32% 12%, rgba(255,255,255,.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 38% 67%, rgba(255,255,255,.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 45% 35%, rgba(180,220,255,.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 52% 90%, rgba(255,255,255,.6) 0%, transparent 100%),
            radial-gradient(2px 2px at 58% 18%, rgba(255,255,255,.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 65% 72%, rgba(255,255,255,.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 72% 44%, rgba(180,200,255,.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 78% 28%, rgba(255,255,255,.5) 0%, transparent 100%),
            radial-gradient(2px 2px at 84% 85%, rgba(255,255,255,.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 90% 15%, rgba(180,220,255,.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 95% 60%, rgba(255,255,255,.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 8%  45%, rgba(255,255,255,.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 42% 58%, rgba(255,255,255,.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 67% 33%, rgba(180,200,255,.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 88% 50%, rgba(255,255,255,.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 15% 95%, rgba(255,255,255,.5) 0%, transparent 100%);
          animation: twinkle 6s ease-in-out infinite alternate;
        }
        @keyframes twinkle { 0%{opacity:.6} 100%{opacity:1} }

        /* Planet (bottom right) */
        .lp-planet {
          position: absolute;
          bottom: -80px;
          right: -60px;
          width: 380px;
          height: 380px;
          border-radius: 50%;
          background: radial-gradient(circle at 35% 35%,
            #1a3a8a 0%,
            #0d2060 30%,
            #060f30 70%,
            #020818 100%
          );
          box-shadow:
            0 0 60px rgba(30,80,200,.4),
            0 0 120px rgba(20,60,160,.2),
            inset -20px -20px 60px rgba(0,0,0,.5);
          z-index: 1;
          overflow: hidden;
        }
        .lp-planet::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: 50%;
          background: repeating-linear-gradient(
            -30deg,
            transparent,
            transparent 8px,
            rgba(30,100,255,.06) 8px,
            rgba(30,100,255,.06) 16px
          );
        }

        /* Orbital rings */
        .lp-ring {
          position: absolute;
          border-radius: 50%;
          border: 1px solid;
          z-index: 2;
          transform-origin: center center;
        }
        .lp-ring-1 {
          width: 700px; height: 200px;
          bottom: 80px; right: -180px;
          border-color: rgba(0,200,255,.25);
          box-shadow: 0 0 20px rgba(0,200,255,.1);
          transform: rotate(-20deg);
          animation: ringFloat 8s ease-in-out infinite alternate;
        }
        .lp-ring-2 {
          width: 600px; height: 160px;
          bottom: 60px; right: -140px;
          border-color: rgba(180,100,255,.2);
          box-shadow: 0 0 15px rgba(180,100,255,.08);
          transform: rotate(-22deg);
          animation: ringFloat 10s ease-in-out infinite alternate-reverse;
        }
        @keyframes ringFloat {
          0%   { transform: rotate(-20deg) scaleX(1); }
          100% { transform: rotate(-18deg) scaleX(1.02); }
        }

        /* ── Glass card ── */
        .lp-card {
          position: relative;
          z-index: 10;
          width: 460px;
          background: rgba(8, 18, 50, 0.65);
          border: 1px solid rgba(50, 120, 220, 0.3);
          border-radius: 24px;
          padding: 52px 48px 44px;
          backdrop-filter: blur(32px) saturate(1.4);
          -webkit-backdrop-filter: blur(32px) saturate(1.4);
          box-shadow:
            0 0 0 1px rgba(100,180,255,.08),
            0 8px 80px rgba(0,20,80,.6),
            0 2px 0 rgba(255,255,255,.04) inset,
            0 -1px 0 rgba(0,0,0,.3) inset;
          opacity: 0;
          transform: translateY(24px);
          transition: opacity .7s ease, transform .7s ease;
        }
        .lp-card.visible {
          opacity: 1;
          transform: translateY(0);
        }

        /* Top border glow */
        .lp-card::before {
          content: '';
          position: absolute;
          top: 0; left: 15%; right: 15%;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(0,200,255,.6), rgba(100,140,255,.6), transparent);
        }

        /* ── Diamond logo ── */
        .lp-logo {
          display: flex;
          justify-content: center;
          margin-bottom: 24px;
        }
        .lp-diamond {
          width: 52px; height: 52px;
          background: linear-gradient(135deg, #ffd700, #ff8c00);
          clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
          box-shadow:
            0 0 20px rgba(255,180,0,.5),
            0 0 40px rgba(255,140,0,.3);
          animation: diamondGlow 3s ease-in-out infinite alternate;
        }
        @keyframes diamondGlow {
          0%   { box-shadow: 0 0 20px rgba(255,180,0,.5), 0 0 40px rgba(255,140,0,.3); }
          100% { box-shadow: 0 0 30px rgba(255,200,0,.8), 0 0 60px rgba(255,160,0,.5); }
        }

        /* ── Title ── */
        .lp-title {
          text-align: center;
          font-family: 'Orbitron', sans-serif;
          font-size: 26px;
          font-weight: 700;
          color: #fff;
          letter-spacing: 4px;
          margin-bottom: 36px;
          text-shadow: 0 0 30px rgba(100,180,255,.4);
        }

        /* ── Input group ── */
        .lp-field {
          position: relative;
          margin-bottom: 16px;
        }
        .lp-field-icon {
          position: absolute;
          left: 16px; top: 50%;
          transform: translateY(-50%);
          width: 34px; height: 34px;
          border-radius: 8px;
          background: rgba(0,150,220,.15);
          border: 1px solid rgba(0,200,255,.2);
          display: flex; align-items: center; justify-content: center;
          pointer-events: none;
        }
        .lp-input {
          width: 100%;
          height: 54px;
          background: rgba(5, 15, 45, 0.7);
          border: 1px solid rgba(50,120,220,.3);
          border-radius: 12px;
          padding: 0 44px 0 62px;
          color: #e0eeff;
          font-size: 15px;
          font-family: 'Exo 2', sans-serif;
          font-weight: 400;
          outline: none;
          transition: border-color .25s, box-shadow .25s, background .25s;
        }
        .lp-input::placeholder { color: rgba(140,170,220,.45); }
        .lp-input:focus {
          border-color: rgba(0,200,255,.5);
          background: rgba(5,20,60,.8);
          box-shadow: 0 0 0 3px rgba(0,180,255,.1), 0 0 20px rgba(0,150,220,.15);
        }
        .lp-eye {
          position: absolute;
          right: 14px; top: 50%;
          transform: translateY(-50%);
          background: none; border: none;
          cursor: pointer; padding: 4px;
          color: rgba(100,160,220,.5);
          transition: color .2s;
        }
        .lp-eye:hover { color: rgba(0,200,255,.8); }

        /* ── Row: Remember + Forgot ── */
        .lp-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 28px;
          margin-top: 4px;
        }
        .lp-remember {
          display: flex; align-items: center; gap: 9px;
          cursor: pointer; user-select: none;
        }
        .lp-checkbox {
          width: 18px; height: 18px;
          border: 1.5px solid rgba(0,200,255,.5);
          border-radius: 4px;
          background: rgba(0,180,255,.12);
          display: flex; align-items: center; justify-content: center;
          transition: all .2s;
          flex-shrink: 0;
        }
        .lp-checkbox.checked {
          background: rgba(0,180,255,.3);
          border-color: rgba(0,220,255,.8);
          box-shadow: 0 0 8px rgba(0,200,255,.4);
        }
        .lp-checkbox.checked::after {
          content: '✓';
          color: #00d4ff;
          font-size: 11px;
          font-weight: 700;
          line-height: 1;
        }
        .lp-remember-text {
          font-size: 13px;
          color: rgba(160,200,240,.7);
          font-family: 'Exo 2', sans-serif;
        }
        .lp-forgot {
          background: none; border: none;
          color: #00b4ff;
          font-size: 13px;
          font-family: 'Exo 2', sans-serif;
          cursor: pointer;
          transition: color .2s, text-shadow .2s;
          text-decoration: none;
        }
        .lp-forgot:hover {
          color: #00d4ff;
          text-shadow: 0 0 10px rgba(0,200,255,.5);
        }

        /* ── Login button ── */
        .lp-btn {
          width: 100%;
          height: 54px;
          background: linear-gradient(135deg, #0a4a7a, #0d6090, #0a7aaa);
          border: 1px solid rgba(0,180,255,.4);
          border-radius: 12px;
          color: #fff;
          font-family: 'Orbitron', sans-serif;
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 3px;
          cursor: pointer;
          position: relative;
          overflow: hidden;
          transition: all .25s ease;
          box-shadow:
            0 0 20px rgba(0,130,200,.3),
            0 4px 15px rgba(0,0,0,.4),
            inset 0 1px 0 rgba(255,255,255,.08);
        }
        .lp-btn:hover:not(:disabled) {
          background: linear-gradient(135deg, #0d5a90, #1070a8, #0d8abc);
          box-shadow: 0 0 35px rgba(0,160,230,.5), 0 4px 20px rgba(0,0,0,.4);
          transform: translateY(-1px);
        }
        .lp-btn:active:not(:disabled) { transform: translateY(0); }
        .lp-btn:disabled { opacity: .7; cursor: not-allowed; }
        .lp-btn::before {
          content: '';
          position: absolute;
          top: 0; left: -100%;
          width: 60%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,.07), transparent);
          transition: left .5s;
        }
        .lp-btn:hover::before { left: 150%; }

        /* spinner */
        .lp-spinner {
          width: 20px; height: 20px;
          border: 2px solid rgba(255,255,255,.2);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin .7s linear infinite;
          margin: auto;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ── Footer ── */
        .lp-footer {
          text-align: center;
          margin-top: 22px;
          font-size: 13px;
          color: rgba(140,170,210,.55);
          font-family: 'Exo 2', sans-serif;
        }
        .lp-footer span {
          color: rgba(0,180,255,.7);
          cursor: pointer;
          transition: color .2s;
        }
        .lp-footer span:hover { color: #00d4ff; }
      `}</style>

      <div className="lp-root">
        {/* Background layers */}
        <div className="lp-bg" />
        <div className="lp-stars" />
        <div className="lp-planet" />
        <div className="lp-ring lp-ring-1" />
        <div className="lp-ring lp-ring-2" />

        {/* Glass card */}
        <div className={`lp-card ${mounted ? 'visible' : ''}`}>

          {/* Diamond logo */}
          <div className="lp-logo">
            <div className="lp-diamond" />
          </div>

          {/* Title */}
          <h1 className="lp-title">WELCOME</h1>

          {/* Form */}
          <form onSubmit={handleLogin}>

            {/* Email */}
            <div className="lp-field">
              <div className="lp-field-icon">
                <Mail style={{ width:16, height:16, color:'#00c4ff' }} />
              </div>
              <input
                className="lp-input"
                type="text"
                placeholder="Email"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>

            {/* Password */}
            <div className="lp-field">
              <div className="lp-field-icon">
                <Lock style={{ width:16, height:16, color:'#00c4ff' }} />
              </div>
              <input
                className="lp-input"
                type={showPass ? 'text' : 'password'}
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button type="button" className="lp-eye" onClick={() => setShowPass(v => !v)}>
                {showPass
                  ? <EyeOff style={{ width:16, height:16 }} />
                  : <Eye    style={{ width:16, height:16 }} />
                }
              </button>
            </div>

            {/* Remember + Forgot */}
            <div className="lp-row">
              <div className="lp-remember" onClick={() => setRemember(v => !v)}>
                <div className={`lp-checkbox ${remember ? 'checked' : ''}`} />
                <span className="lp-remember-text">Remember me</span>
              </div>
              <button type="button" className="lp-forgot">Forgot password?</button>
            </div>

            {/* Submit */}
            <button type="submit" className="lp-btn" disabled={loading}>
              {loading ? <div className="lp-spinner" /> : 'LOG IN'}
            </button>

          </form>

          {/* Footer */}
          <div className="lp-footer">
            Don't have an account? <span onClick={() => toast('Contact admin to create account')}>Sign Up</span>
          </div>
        </div>
      </div>
    </>
  );
};

export default Login;



// // src/pages/Login.jsx
// import React, { useState } from 'react';
// import { useNavigate } from 'react-router-dom';
// import client from '../api/client';
// import toast from 'react-hot-toast';
// import '../styles/login.css';
// import {
//   Home, Heart, Menu, Search, Eye, EyeOff,
//   Power, Mail, MapPin, CheckCircle, MoreVertical,
//   AlignJustify, Globe, Camera, X, Plus, RefreshCw,
//   ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
//   SkipBack, SkipForward, Play, Square, Pause, User,
//   Share2, Download, FolderOpen
// } from 'lucide-react';

// /* ── Toggle ── */
// const Toggle = ({ on, onChange }) => (
//   <div className="toggle-row">
//     <span className="toggle-label">{on ? 'ON' : 'OFF'}</span>
//     <div className={`toggle-track ${on ? 'on' : 'off'}`} onClick={() => onChange(!on)}>
//       <div className="toggle-knob" />
//     </div>
//   </div>
// );

// /* ── Gold Circle ── */
// const GoldBtn = ({ icon: Icon, label, onClick }) => (
//   <div className="gold-btn-wrap">
//     <div className="gold-circle" onClick={onClick}>
//       <Icon style={{ width: 22, height: 22, color: 'rgba(255,240,185,0.96)', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))' }} />
//     </div>
//     {label && <span className="gold-label">{label}</span>}
//   </div>
// );

// /* ── Red Button ── */
// const RedBtn = ({ label, icon: Icon, onClick }) => (
//   <button className="red-btn" onClick={onClick}>
//     {Icon && <Icon style={{ width: 14, height: 14 }} />}
//     {label}
//   </button>
// );

// /* ── Purple Media ── */
// const PurpleBtn = ({ icon: Icon, label, onClick }) => (
//   <div className="purple-btn-wrap">
//     <div className="purple-square" onClick={onClick}>
//       <Icon style={{ width: 26, height: 26, color: 'rgba(212,162,255,0.96)', filter: 'drop-shadow(0 0 4px rgba(182,102,255,0.5))' }} />
//     </div>
//     {label && <span className="purple-label">{label}</span>}
//   </div>
// );

// /* ── Arrow ── */
// const ArrowBtn = ({ icon: Icon, onClick }) => (
//   <button className="arrow-btn" onClick={onClick}>
//     <Icon style={{ width: 20, height: 20 }} />
//   </button>
// );

// /* ── Green Slider ── */
// const GreenSlider = ({ defaultVal = 60 }) => {
//   const [val, setVal] = useState(defaultVal);
//   const handleClick = e => {
//     const rect = e.currentTarget.getBoundingClientRect();
//     const pct = Math.round((1 - (e.clientY - rect.top) / rect.height) * 100);
//     setVal(Math.min(100, Math.max(0, pct)));
//   };
//   return (
//     <div className="slider-wrap">
//       <div className="slider-track" onClick={handleClick}>
//         <div className="slider-fill" style={{ height: `${val}%` }} />
//         <div className="slider-thumb" style={{ bottom: `calc(${val}% - 11px)` }} />
//       </div>
//     </div>
//   );
// };

// /* ── Nav Item ── */
// const NavItem = ({ icon: Icon, label, onClick }) => (
//   <button className="nav-item" onClick={onClick}>
//     <Icon style={{ width: 15, height: 15 }} /> {label}
//   </button>
// );

// /* ══════════════════════════
//    MAIN LOGIN PAGE
// ══════════════════════════ */
// const Login = () => {
//   const [username, setUsername] = useState('');
//   const [password, setPassword] = useState('');
//   const [loading, setLoading] = useState(false);
//   const [showPass, setShowPass] = useState(false);
//   const [t1, setT1] = useState(true);
//   const [t2, setT2] = useState(false);
//   const [t3, setT3] = useState(false);
//   const [t4, setT4] = useState(true);
//   const [isPlaying, setIsPlaying] = useState(false);
//   const [searchQ, setSearchQ] = useState('');
//   const navigate = useNavigate();

//   const handleLogin = async e => {
//     e.preventDefault();
//     if (!username || !password) { toast.error('Please fill in all fields'); return; }
//     try {
//       setLoading(true);
//       const res = await client.post('/auth/login/', { username_or_email: username, password });
//       const token = res.data.tokens?.access || res.data.tokens?.token || res.data.access || res.data.token;
//       if (token) {
//         localStorage.setItem('adminAccessToken', token);
//         toast.success('Login Successful!');
//         setTimeout(() => navigate('/'), 500);
//       } else throw new Error('No token');
//     } catch (err) {
//       toast.error(err.response?.data?.detail || 'Login Failed!');
//     } finally { setLoading(false); }
//   };

//   return (
//     <div className="login-page">
//       <div className="login-grid">

//         {/* ════ COL 1 ════ */}
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

//           {/* Toggles + Search */}
//           <div className="glass-panel" style={{ padding: '14px 18px', display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 12, columnGap: 14, alignItems: 'center' }}>
//             <Toggle on={t1} onChange={setT1} />
//             <div className="search-bar">
//               <Search style={{ width: 13, height: 13, color: 'rgba(128,192,255,0.65)', flexShrink: 0 }} />
//               <input className="search-input" value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="SEARCH" />
//             </div>
//             <Toggle on={t2} onChange={setT2} />
//             <Toggle on={t3} onChange={setT3} />
//           </div>

//           {/* SIGN IN */}
//           <div className="signin-card">
//             <div className="corner-bl" /><div className="corner-br" />
//             <h2 className="signin-title">SIGN IN</h2>
//             <form onSubmit={handleLogin}>
//               <input className="login-input" type="text" placeholder="username@mail.com" value={username} onChange={e => setUsername(e.target.value)} />
//               <div style={{ position: 'relative', marginBottom: 18 }}>
//                 <input className="login-input" type={showPass ? 'text' : 'password'} placeholder="password" value={password} onChange={e => setPassword(e.target.value)} style={{ marginBottom: 0, paddingRight: 40 }} />
//                 <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
//                   {showPass ? <EyeOff style={{ width: 14, height: 14, color: 'rgba(138,192,196,0.50)' }} /> : <Eye style={{ width: 14, height: 14, color: 'rgba(138,192,196,0.50)' }} />}
//                 </button>
//               </div>
//               <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
//                 <button type="submit" className="login-btn" disabled={loading}>
//                   {loading ? <div className="spinner" /> : 'LOGIN IN'}
//                 </button>
//                 <button type="button" className="forgot-link">Forgot Password?</button>
//               </div>
//             </form>
//           </div>

//           {/* Avatar + Nav */}
//           <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 10 }}>
//             <div className="avatar-box">
//               <div className="avatar-icon">
//                 <User style={{ width: 28, height: 28, color: 'rgba(88,172,255,0.86)' }} />
//               </div>
//             </div>
//             <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
//               <NavItem icon={Home}  label="HOME" onClick={() => toast('🏠 Home')} />
//               <NavItem icon={Heart} label="LIKE" onClick={() => toast('❤️ Liked!')} />
//               <NavItem icon={Menu}  label="MENU" onClick={() => toast('☰ Menu')} />
//             </div>
//           </div>

//           {/* Contact button */}
//           <button className="contact-btn" onClick={() => toast('📧 admin@earning.com')}>
//             CONTACT
//           </button>
//         </div>

//         {/* ════ COL 2 ════ */}
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

//           {/* Top toggles */}
//           <div className="glass-panel" style={{ padding: '14px 18px', display: 'flex', gap: 22, alignItems: 'center', flexWrap: 'wrap' }}>
//             <Toggle on={t4} onChange={setT4} />
//             <Toggle on={!t4} onChange={v => setT4(!v)} />
//           </div>

//           {/* D-Pad */}
//           <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
//             <div style={{ display: 'flex', gap: 8 }}>
//               <div style={{ width: 48, height: 48 }} />
//               <ArrowBtn icon={ChevronUp} onClick={() => toast.success('↑ Up')} />
//               <div style={{ width: 48, height: 48 }} />
//             </div>
//             <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
//               <ArrowBtn icon={ChevronLeft} onClick={() => toast.success('← Left')} />
//               <div className="dpad-center">
//                 <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(172,182,255,0.42)' }} />
//               </div>
//               <ArrowBtn icon={ChevronRight} onClick={() => toast.success('→ Right')} />
//             </div>
//             <div style={{ display: 'flex', gap: 8 }}>
//               <div style={{ width: 48, height: 48 }} />
//               <ArrowBtn icon={ChevronDown} onClick={() => toast.success('↓ Down')} />
//               <div style={{ width: 48, height: 48 }} />
//             </div>
//           </div>

//           {/* Mood */}
//           <div className="mood-card">
//             <p style={{ margin: '0 0 5px', color: 'rgba(222,198,255,0.95)', fontSize: 13, fontWeight: 700 }}>Current Mood: Ambient Electronic</p>
//             <p style={{ margin: '0 0 3px', color: 'rgba(172,142,242,0.72)', fontSize: 11 }}>Current #Artist Name</p>
//             <p style={{ margin: '0 0 3px', color: 'rgba(172,142,242,0.72)', fontSize: 11 }}>Artist: Elise Semme</p>
//             <p style={{ margin: 0, color: 'rgba(172,142,242,0.72)', fontSize: 11 }}>Artist: Morin Stnua</p>
//           </div>

//           {/* Red buttons */}
//           <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
//             <RedBtn label="SHARE"    icon={Share2}     onClick={() => toast('🔗 Shared!')} />
//             <RedBtn label="DOWNLOAD" icon={Download}   onClick={() => toast('⬇️ Downloading...')} />
//             <RedBtn label="OPEN"     icon={FolderOpen} onClick={() => toast('📂 Opened!')} />
//             <RedBtn label="HOME"     icon={Home}       onClick={() => navigate('/')} />
//           </div>

//           {/* Sliders */}
//           <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'center', gap: 28 }}>
//             <GreenSlider defaultVal={72} />
//             <GreenSlider defaultVal={40} />
//           </div>
//         </div>

//         {/* ════ COL 3 ════ */}
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

//           {/* Gold row 1 */}
//           <div className="glass-panel" style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 12 }}>
//             <GoldBtn icon={Power}        label="Master Power"   onClick={() => toast('⚡ Power')} />
//             <GoldBtn icon={Mail}         label="Email Best"     onClick={() => toast('📧 Email')} />
//             <GoldBtn icon={MapPin}       label="Geo-Services"   onClick={() => toast('📍 Geo')} />
//             <GoldBtn icon={CheckCircle}  label="Cloud Settings" onClick={() => toast('✅ Cloud')} />
//             <GoldBtn icon={MoreVertical} label="Cloud Settings" onClick={() => toast('⚙️ Settings')} />
//             <GoldBtn icon={AlignJustify} label="Eioar Settings" onClick={() => toast('☰ Eioar')} />
//           </div>

//           {/* Gold row 2 */}
//           <div className="glass-panel" style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 12 }}>
//             <GoldBtn icon={Globe}     label="Ment"          onClick={() => toast('🌐 Globe')} />
//             <GoldBtn icon={Menu}      label="Mesteament"    onClick={() => toast('☰ Menu')} />
//             <GoldBtn icon={Camera}    label="Foto Settings" onClick={() => toast('📷 Camera')} />
//             <GoldBtn icon={X}         label="X nlore"       onClick={() => toast('❌ Close')} />
//             <GoldBtn icon={Plus}      label="Cloud Settings"onClick={() => toast('➕ Add')} />
//             <GoldBtn icon={RefreshCw} label="Cloud Settings"onClick={() => toast('🔄 Refresh')} />
//           </div>

//           {/* Purple media 2x3 */}
//           <div className="glass-panel" style={{ padding: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
//             <PurpleBtn icon={Play}        label="Geo-Services"  onClick={() => { setIsPlaying(true); toast.success('▶ Playing'); }} />
//             <PurpleBtn icon={SkipBack}    label="Cloud Settings"onClick={() => toast('⏮ Prev')} />
//             <PurpleBtn icon={SkipForward} label="Wiart Settings"onClick={() => toast('⏭ Next')} />
//             <PurpleBtn icon={Square}      label="Cloud Settings"onClick={() => { setIsPlaying(false); toast('⏹ Stopped'); }} />
//             <PurpleBtn icon={SkipBack}    label="Olien Settings"onClick={() => toast('⏪ Rewind')} />
//             <PurpleBtn icon={Pause}       label="Pous Settings" onClick={() => { setIsPlaying(false); toast('⏸ Paused'); }} />
//           </div>

//           {/* Now Playing */}
//           {isPlaying && (
//             <div className="now-playing">
//               <div className="bar-vis">
//                 {[9, 15, 11, 17, 7].map((h, i) => (
//                   <span key={i} style={{ height: h, animationDelay: `${i * 0.12}s` }} />
//                 ))}
//               </div>
//               <span style={{ color: 'rgba(195,142,255,0.90)', fontSize: 10, fontFamily: 'Orbitron, sans-serif', letterSpacing: '0.10em' }}>NOW PLAYING</span>
//             </div>
//           )}
//         </div>
//       </div>
//     </div>
//   );
// };

// export default Login;