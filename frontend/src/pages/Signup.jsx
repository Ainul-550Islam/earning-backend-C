import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import client from '../api/client';
import toast from 'react-hot-toast';
import { Eye, EyeOff, Mail, Lock, User } from 'lucide-react';

const Signup = () => {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [mounted, setMounted] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const handleChange = e => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSignup = async e => {
    e.preventDefault();
    if (!form.username || !form.email || !form.password) { toast.error('Please fill in all fields'); return; }
    if (form.password !== form.confirm_password) { toast.error('Passwords do not match'); return; }
    if (form.password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    try {
      setLoading(true);
      await client.post('/auth/register/', {...form, password_confirm: form.confirm_password});
      toast.success('Account created! Please login.');
      setTimeout(() => navigate('/login'), 1000);
    } catch (err) {
      const errors = err.response?.data;
      if (errors) {
        Object.values(errors).forEach(e => toast.error(Array.isArray(e) ? e[0] : e));
      } else {
        toast.error('Registration failed. Try again.');
      }
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
        .sp-root { min-height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; background: #0a0a0f; font-family: 'Exo 2', sans-serif; }
        .sp-bg { position: absolute; inset: 0; background: radial-gradient(ellipse at 80% 50%, rgba(139,0,255,0.05) 0%, transparent 60%), radial-gradient(ellipse at 20% 20%, rgba(0,245,255,0.05) 0%, transparent 60%); }
        .sp-card { position: relative; z-index: 1; width: 100%; max-width: 420px; background: rgba(10,10,20,0.95); border: 1px solid rgba(139,0,255,0.2); border-radius: 16px; padding: 40px; box-shadow: 0 0 40px rgba(139,0,255,0.1); }
        .sp-logo { text-align: center; margin-bottom: 28px; }
        .sp-logo-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #8b00ff, #00f5ff); border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; font-size: 28px; margin-bottom: 12px; }
        .sp-title { font-family: 'Orbitron', sans-serif; font-size: 20px; font-weight: 700; color: #8b00ff; letter-spacing: 2px; }
        .sp-subtitle { font-size: 13px; color: rgba(255,255,255,0.4); margin-top: 4px; }
        .sp-field { margin-bottom: 14px; }
        .sp-input-wrap { position: relative; display: flex; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(139,0,255,0.2); border-radius: 10px; transition: border 0.2s; }
        .sp-input-wrap:focus-within { border-color: #8b00ff; box-shadow: 0 0 12px rgba(139,0,255,0.15); }
        .sp-icon { position: absolute; left: 14px; color: rgba(139,0,255,0.5); width: 18px; height: 18px; }
        .sp-input { width: 100%; background: transparent; border: none; outline: none; padding: 13px 14px 13px 44px; color: #fff; font-size: 14px; font-family: 'Exo 2', sans-serif; }
        .sp-eye { position: absolute; right: 14px; background: none; border: none; cursor: pointer; color: rgba(255,255,255,0.4); padding: 4px; }
        .sp-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #8b00ff, #6600cc); border: none; border-radius: 10px; color: #fff; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700; letter-spacing: 2px; cursor: pointer; transition: all 0.2s; margin-bottom: 16px; }
        .sp-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(139,0,255,0.3); }
        .sp-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .sp-divider { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
        .sp-divider-line { flex: 1; height: 1px; background: rgba(255,255,255,0.1); }
        .sp-divider-text { font-size: 12px; color: rgba(255,255,255,0.3); }
        .sp-google-btn { width: 100%; padding: 13px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; color: #fff; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; transition: all 0.2s; margin-bottom: 20px; font-family: 'Exo 2', sans-serif; }
        .sp-google-btn:hover { background: rgba(255,255,255,0.1); }
        .sp-footer { text-align: center; font-size: 13px; color: rgba(255,255,255,0.4); }
        .sp-footer a { color: #8b00ff; text-decoration: none; }
        .sp-spinner { width: 20px; height: 20px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div className="sp-root">
        <div className="sp-bg" />
        <div className="sp-card" style={{ opacity: mounted ? 1 : 0, transform: mounted ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.4s ease' }}>
          <div className="sp-logo">
            <div className="sp-logo-icon">🚀</div>
            <div className="sp-title">CREATE ACCOUNT</div>
            <div className="sp-subtitle">Join the earning platform</div>
          </div>
          <form onSubmit={handleSignup}>
            <div className="sp-field">
              <div className="sp-input-wrap">
                <User className="sp-icon" />
                <input className="sp-input" type="text" name="username" placeholder="Username" value={form.username} onChange={handleChange} />
              </div>
            </div>
            <div className="sp-field">
              <div className="sp-input-wrap">
                <Mail className="sp-icon" />
                <input className="sp-input" type="email" name="email" placeholder="Email address" value={form.email} onChange={handleChange} />
              </div>
            </div>
            <div className="sp-field">
              <div className="sp-input-wrap">
                <Lock className="sp-icon" />
                <input className="sp-input" type={showPass ? 'text' : 'password'} name="password" placeholder="Password" value={form.password} onChange={handleChange} />
                <button type="button" className="sp-eye" onClick={() => setShowPass(v => !v)}>
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div className="sp-field">
              <div className="sp-input-wrap">
                <Lock className="sp-icon" />
                <input className="sp-input" type="password" name="confirm_password" placeholder="Confirm password" value={form.confirm_password} onChange={handleChange} />
              </div>
            </div>
            <button type="submit" className="sp-btn" disabled={loading}>
              {loading ? <div className="sp-spinner" /> : 'SIGN UP'}
            </button>
          </form>
          <div className="sp-divider">
            <div className="sp-divider-line" />
            <span className="sp-divider-text">OR</span>
            <div className="sp-divider-line" />
          </div>
          <button className="sp-google-btn" onClick={handleGoogleLogin}>
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
            Continue with Google
          </button>
          <div className="sp-footer">
            Already have an account? <Link to="/login">Log In</Link>
          </div>
        </div>
      </div>
    </>
  );
};
export default Signup;
