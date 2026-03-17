import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import client from '../api/client';
import toast from 'react-hot-toast';
import { Mail, ArrowLeft } from 'lucide-react';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!email) { toast.error('Please enter your email'); return; }
    try {
      setLoading(true);
      await client.post('/auth/password/reset/', { email });
      setSent(true);
      toast.success('Reset email sent!');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed. Check your email.');
    } finally { setLoading(false); }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        .fp-root { min-height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; background: #0a0a0f; font-family: 'Exo 2', sans-serif; }
        .fp-card { position: relative; z-index: 1; width: 100%; max-width: 400px; background: rgba(10,10,20,0.95); border: 1px solid rgba(0,245,255,0.2); border-radius: 16px; padding: 40px; box-shadow: 0 0 40px rgba(0,245,255,0.1); }
        .fp-back { display: flex; align-items: center; gap: 8px; color: rgba(255,255,255,0.4); font-size: 13px; text-decoration: none; margin-bottom: 24px; transition: color 0.2s; }
        .fp-back:hover { color: #00f5ff; }
        .fp-logo { text-align: center; margin-bottom: 28px; }
        .fp-logo-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #00f5ff, #8b00ff); border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; font-size: 28px; margin-bottom: 12px; }
        .fp-title { font-family: 'Orbitron', sans-serif; font-size: 18px; font-weight: 700; color: #00f5ff; letter-spacing: 2px; }
        .fp-subtitle { font-size: 13px; color: rgba(255,255,255,0.4); margin-top: 6px; line-height: 1.5; }
        .fp-field { margin-bottom: 20px; }
        .fp-input-wrap { position: relative; display: flex; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(0,245,255,0.2); border-radius: 10px; transition: border 0.2s; }
        .fp-input-wrap:focus-within { border-color: #00f5ff; box-shadow: 0 0 12px rgba(0,245,255,0.15); }
        .fp-icon { position: absolute; left: 14px; color: rgba(0,245,255,0.5); width: 18px; height: 18px; }
        .fp-input { width: 100%; background: transparent; border: none; outline: none; padding: 14px 14px 14px 44px; color: #fff; font-size: 14px; font-family: 'Exo 2', sans-serif; }
        .fp-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #00f5ff, #0099cc); border: none; border-radius: 10px; color: #000; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700; letter-spacing: 2px; cursor: pointer; transition: all 0.2s; }
        .fp-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(0,245,255,0.3); }
        .fp-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .fp-success { text-align: center; padding: 20px 0; }
        .fp-success-icon { font-size: 48px; margin-bottom: 16px; }
        .fp-success-title { font-family: 'Orbitron', sans-serif; font-size: 16px; color: #00f5ff; margin-bottom: 8px; }
        .fp-success-text { font-size: 13px; color: rgba(255,255,255,0.5); line-height: 1.6; }
        .fp-spinner { width: 20px; height: 20px; border: 2px solid rgba(0,0,0,0.3); border-top-color: #000; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div className="fp-root">
        <div className="fp-card" style={{ opacity: mounted ? 1 : 0, transform: mounted ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.4s ease' }}>
          <Link to="/login" className="fp-back">
            <ArrowLeft size={16} /> Back to Login
          </Link>
          {sent ? (
            <div className="fp-success">
              <div className="fp-success-icon">📧</div>
              <div className="fp-success-title">EMAIL SENT!</div>
              <div className="fp-success-text">
                Check your inbox for password reset instructions. Check spam folder if not found.
              </div>
              <br />
              <Link to="/login" style={{ color: '#00f5ff', fontSize: 13 }}>Back to Login →</Link>
            </div>
          ) : (
            <>
              <div className="fp-logo">
                <div className="fp-logo-icon">🔑</div>
                <div className="fp-title">FORGOT PASSWORD</div>
                <div className="fp-subtitle">Enter your email and we'll send you a reset link</div>
              </div>
              <form onSubmit={handleSubmit}>
                <div className="fp-field">
                  <div className="fp-input-wrap">
                    <Mail className="fp-icon" />
                    <input className="fp-input" type="email" placeholder="Your email address" value={email} onChange={e => setEmail(e.target.value)} />
                  </div>
                </div>
                <button type="submit" className="fp-btn" disabled={loading}>
                  {loading ? <div className="fp-spinner" /> : 'SEND RESET LINK'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  );
};
export default ForgotPassword;
