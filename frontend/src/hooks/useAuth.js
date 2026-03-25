// src/hooks/useAuth.js
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('adminAccessToken');
    if (!token) {
      setLoading(false);
      navigate('/login');
      return;
    }
    // Token আছে — user object বানাও
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUser({ username: payload.username || 'Admin', ...payload });
    } catch {
      setUser({ username: 'Admin' });
    }
    setLoading(false);
  }, []);

  const logout = () => {
    localStorage.removeItem('adminAccessToken');
    setUser(null);
    navigate('/login');
  };

  return { user, loading, logout, isAuthenticated: true };
};

export default useAuth;
