import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import client from '../api/client';
import toast from 'react-hot-toast';
import { Lock, EyeOff, Eye } from 'lucide-react';

const ResetPassword = () => {
  const { uid, token } = useParams();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [mounted, setMounted] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!password || !confirm) { toast.error('Please fill in all fields'); return; }
    if (password !== confirm) { toast.error('Passwords do not match'); return; }
    if (password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    try {
      setLoading(true);
      await client.post('/auth/password/reset/confirm/', { uid, token, password });
      setDone(true);
      toast.success('Password reset successful!');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Reset failed. Link may be expired.');
    } finally { setLoading(false); }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        .rp-root { min-height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; background: #0a0a0f; font-family: 'Exo 2', sans-serif; }
        .rp-card { position: relative; z-index: 1; width: 100%; max-width: 400px; background: rgba(10,10,20,0.95); border: 1px solid rgba(0,245,255,0.2); border-radius: 16px; padding: 40px; box-shadow: 0 0 40px rgba(0,245,255,0.1); }
        .rp-logo { text-align: center; margin-bottom: 28px; }
        .rp-logo-icon { width: 60px; height: 60px; background: linear-gradient(135deg, #00f5ff, #8b00ff); border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; font-size: 28px; margin-bottom: 12px; }
        .rp-title { font-family: 'Orbitron', sans-serif; font-size: 18px; font-weight: 700; color: #00f5ff; letter-spacing: 2px; }
        .rp-subtitle { font-size: 13px; color: rgba(255,255,255,0.4); margin-top: 6px; }
        .rp-field { margin-bottom: 16px; }
        .rp-input-wrap { position: relative; display: flex; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(0,245,255,0.2); border-radius: 10px; transition: border 0.2s; }
        .rp-input-wrap:focus-within { border-color: #00f5ff; box-shadow: 0 0 12px rgba(0,245,255,0.15); }
        .rp-icon { position: absolute; left: 14px; color: rgba(0,245,255,0.5); width: 18px; height: 18px; }
        .rp-input { width: 100%; background: transparent; border: none; outline: none; padding: 14px 14px 14px 44px; color: #fff; font-size: 14px; font-family: 'Exo 2', sans-serif; }
        .rp-eye { position: absolute; right: 14px; background: none; border: none; cursor: pointer; color: rgba(255,255,255,0.4); padding: 4px; }
        .rp-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #00f5ff, #0099cc); border: none; border-radius: 10px; color: #000; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700; letter-spacing: 2px; cursor: pointer; transition: all 0.2s; }
        .rp-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(0,245,255,0.3); }
        .rp-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .rp-success { text-align: center; padding: 20px 0; }
        .rp-success-icon { font-size: 48px; margin-bottom: 16px; }
        .rp-success-title { font-family: 'Orbitron', sans-serif; font-size: 16px; color: #00f5ff; margin-bottom: 8px; }
        .rp-spinner { width: 20px; height: 20px; border: 2px solid rgba(0,0,0,0.3); border-top-color: #000; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div className="rp-root">
        <div className="rp-card" style={{ opacity: mounted ? 1 : 0, transform: mounted ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.4s ease' }}>
          {done ? (
            <div className="rp-success">
              <div className="rp-success-icon">✅</div>
              <div className="rp-success-title">PASSWORD RESET!</div>
              <p style={{color: 'rgba(255,255,255,0.5)', fontSize: 13}}>Redirecting to login...</p>
            </div>
          ) : (
            <>
              <div className="rp-logo">
                <div className="rp-logo-icon">🔐</div>
                <div className="rp-title">RESET PASSWORD</div>
                <div className="rp-subtitle">Enter your new password</div>
              </div>
              <form onSubmit={handleSubmit}>
                <div className="rp-field">
                  <div className="rp-input-wrap">
                    <Lock className="rp-icon" />
                    <input className="rp-input" type={showPass ? 'text' : 'password'} placeholder="New password" value={password} onChange={e => setPassword(e.target.value)} />
                    <button type="button" className="rp-eye" onClick={() => setShowPass(v => !v)}>
                      {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <div className="rp-field">
                  <div className="rp-input-wrap">
                    <Lock className="rp-icon" />
                    <input className="rp-input" type="password" placeholder="Confirm new password" value={confirm} onChange={e => setConfirm(e.target.value)} />
                  </div>
                </div>
                <button type="submit" className="rp-btn" disabled={loading}>
                  {loading ? <div className="rp-spinner" /> : 'RESET PASSWORD'}
                </button>
              </form>
              <div style={{textAlign:'center', marginTop:16}}>
                <Link to="/login" style={{color:'#00f5ff', fontSize:13}}>Back to Login</Link>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
};
export default ResetPassword;
