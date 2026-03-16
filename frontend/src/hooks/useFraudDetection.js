// src/hooks/useFraudDetection.js
import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';

const useFraudDetection = () => {
  const [alerts, setAlerts]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const res = await client.get('/fraud_detection/alerts/');
      setAlerts(res.data.results || res.data || []);
      setError(null);
    } catch (err) {
      console.error('Security scan failed', err);
      setError('Failed to load security alerts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  // NOTE: This hook is a lightweight standalone fetcher.
  // If you are already using FraudDetection.jsx which does its own fetchAll(),
  // do NOT use this hook inside that same component — it will cause a double API call.
  // Use this hook only in separate components that need just the alerts list.

  return { alerts, loading, error, refetch: fetchAlerts };
};

export default useFraudDetection;