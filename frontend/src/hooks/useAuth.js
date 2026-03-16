// src/hooks/useAuth.js
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('adminAccessToken');

      if (!token) {
        setLoading(false);
        navigate('/login');
        return;
      }

      try {
        const response = await client.get('/users/me/');
        setUser(response.data);
      } catch (error) {
        console.error("Auth verification failed", error);
        localStorage.removeItem('adminAccessToken');
        setUser(null);
        navigate('/login');
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
  }, []);

  const logout = () => {
    localStorage.removeItem('adminAccessToken');
    setUser(null);
    navigate('/login');
  };

  return { user, loading, logout, isAuthenticated: !!user };
};

export default useAuth;