import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import client from '../api/client';
import toast from 'react-hot-toast';
import { Eye, EyeOff, Mail, Lock } from 'lucide-react';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [remember, setRemember] = useState(true);
  const [mounted, setMounted] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const handleLogin = async e => {
    e.preventDefault();
    if (!username || !password) { toast.error('Please fill in all fields'); return; }
    try {
      setLoading(true);
      const res = await client.post('/auth/login/', { username_or_email: username, password });
      const token = res.data.tokens?.access || res.data.token || res.data.access;
      if (token) {
        localStorage.setItem('adminAccessToken', token);
        localStorage.setItem('token', token);
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

  const handleGoogleLogin = () => {
    const backendURL = import.meta.env.VITE_API_BASE_URL?.replace('/api', '') || 'http://localhost:8000';
    window.location.href = `${backendURL}/auth/social/login/google-oauth2/`;
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        .lp-root { min-height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; background: #0a0a0f; font-family: 'Exo 2', sans-serif; position: relative; overflow: hidden; }
        .lp-bg { position: absolute; inset: 0; background: radial-gradient(ellipse at 20% 50%, rgba(0,245,255,0.05) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(139,0,255,0.05) 0%, transparent 60%); }
        .lp-card { position: relative; z-index: 1; width: 100%; max-width: 420px; background: rgba(10,10,20,0.95); border: 1px solid rgba(0,245,255,0.2); border-radius: 16px; padding: 40px; box-shadow: 0 0 40px rgba(0,245,255,0.1); }
        .lp-logo { text-align: center; margin-bottom: 32px; }
        .lp-logo-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #00f5ff, #8b00ff); border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; font-size: 28px; margin-bottom: 12px; }
        .lp-title { font-family: 'Orbitron', sans-serif; font-size: 22px; font-weight: 700; color: #00f5ff; letter-spacing: 2px; }
        .lp-subtitle { font-size: 13px; color: rgba(255,255,255,0.4); margin-top: 4px; }
        .lp-field { margin-bottom: 16px; }
        .lp-input-wrap { position: relative; display: flex; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(0,245,255,0.2); border-radius: 10px; transition: border 0.2s; }
        .lp-input-wrap:focus-within { border-color: #00f5ff; box-shadow: 0 0 12px rgba(0,245,255,0.15); }
        .lp-icon { position: absolute; left: 14px; color: rgba(0,245,255,0.5); width: 18px; height: 18px; }
        .lp-input { width: 100%; background: transparent; border: none; outline: none; padding: 14px 14px 14px 44px; color: #fff; font-size: 14px; font-family: 'Exo 2', sans-serif; }
        .lp-eye { position: absolute; right: 14px; background: none; border: none; cursor: pointer; color: rgba(255,255,255,0.4); padding: 4px; }
        .lp-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .lp-remember { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .lp-checkbox { width: 16px; height: 16px; border: 1px solid rgba(0,245,255,0.4); border-radius: 4px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
        .lp-checkbox.checked { background: #00f5ff; border-color: #00f5ff; }
        .lp-checkbox.checked::after { content: '✓'; font-size: 11px; color: #000; font-weight: bold; }
        .lp-remember-text { font-size: 13px; color: rgba(255,255,255,0.5); }
        .lp-forgot { background: none; border: none; color: #00f5ff; font-size: 13px; cursor: pointer; text-decoration: none; }
        .lp-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #00f5ff, #0099cc); border: none; border-radius: 10px; color: #000; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700; letter-spacing: 2px; cursor: pointer; transition: all 0.2s; margin-bottom: 16px; }
        .lp-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(0,245,255,0.3); }
        .lp-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .lp-divider { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
        .lp-divider-line { flex: 1; height: 1px; background: rgba(255,255,255,0.1); }
        .lp-divider-text { font-size: 12px; color: rgba(255,255,255,0.3); }
        .lp-google-btn { width: 100%; padding: 13px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; color: #fff; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; transition: all 0.2s; margin-bottom: 20px; font-family: 'Exo 2', sans-serif; }
        .lp-google-btn:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.3); }
        .lp-footer { text-align: center; font-size: 13px; color: rgba(255,255,255,0.4); }
        .lp-footer a { color: #00f5ff; text-decoration: none; }
        .lp-footer a:hover { text-decoration: underline; }
        .lp-spinner { width: 20px; height: 20px; border: 2px solid rgba(0,0,0,0.3); border-top-color: #000; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div className="lp-root">
        <div className="lp-bg" />
        <div className={`lp-card`} style={{ opacity: mounted ? 1 : 0, transform: mounted ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.4s ease' }}>
          <div className="lp-logo">
            <div className="lp-logo-icon">⚡</div>
            <div className="lp-title">WELCOME</div>
            <div className="lp-subtitle">Sign in to your account</div>
          </div>
          <form onSubmit={handleLogin}>
            <div className="lp-field">
              <div className="lp-input-wrap">
                <Mail className="lp-icon" />
                <input className="lp-input" type="text" placeholder="Username or Email" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" />
              </div>
            </div>
            <div className="lp-field">
              <div className="lp-input-wrap">
                <Lock className="lp-icon" />
                <input className="lp-input" type={showPass ? 'text' : 'password'} placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
                <button type="button" className="lp-eye" onClick={() => setShowPass(v => !v)}>
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div className="lp-row">
              <div className="lp-remember" onClick={() => setRemember(v => !v)}>
                <div className={`lp-checkbox ${remember ? 'checked' : ''}`} />
                <span className="lp-remember-text">Remember me</span>
              </div>
              <Link to="/forgot-password" className="lp-forgot">Forgot password?</Link>
            </div>
            <button type="submit" className="lp-btn" disabled={loading}>
              {loading ? <div className="lp-spinner" /> : 'LOG IN'}
            </button>
          </form>
          <div className="lp-divider">
            <div className="lp-divider-line" />
            <span className="lp-divider-text">OR</span>
            <div className="lp-divider-line" />
          </div>
          <button className="lp-google-btn" onClick={handleGoogleLogin}>
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
            Continue with Google
          </button>
          <div className="lp-footer">
            Don't have an account? <Link to="/signup">Sign Up</Link>
          </div>
        </div>
      </div>
    </>
  );
};
export default Login;
