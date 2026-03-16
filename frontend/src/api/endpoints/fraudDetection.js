// src/api/endpoints/fraudDetection.js
import client from '../client';

// Alerts
export const getAlerts      = (params={}) => client.get('/fraud_detection/alerts/', { params });
export const createAlert    = (data)      => client.post('/fraud_detection/alerts/', data);
export const updateAlert    = (id, data)  => client.patch(`/fraud_detection/alerts/${id}/`, data);
export const deleteAlert    = (id)        => client.delete(`/fraud_detection/alerts/${id}/`);
export const resolveAlert   = (id)        => client.patch(`/fraud_detection/alerts/${id}/`, { is_resolved: true, resolved_at: new Date().toISOString() });
export const bulkResolve    = (ids)       => client.post('/fraud_detection/alerts/bulk-resolve/', { alert_ids: ids, notes: 'Resolved by admin' });

// Rules
export const getRules       = (params={}) => client.get('/fraud_detection/rules/', { params });
export const createRule     = (data)      => client.post('/fraud_detection/rules/', data);
export const updateRule     = (id, data)  => client.patch(`/fraud_detection/rules/${id}/`, data);
export const deleteRule     = (id)        => client.delete(`/fraud_detection/rules/${id}/`);

// Attempts
export const getAttempts    = (params={}) => client.get('/fraud_detection/attempts/', { params });
export const bulkAttempts   = (data)      => client.post('/fraud_detection/attempts/bulk-update/', data);

// Risk Profiles
export const getHighRiskUsers = (params={}) => client.get('/fraud_detection/risk-profiles/high-risk/', { params });
export const getRiskProfiles  = (params={}) => client.get('/fraud_detection/risk-profiles/', { params });

// Settings
export const getSettings    = ()     => client.get('/fraud_detection/settings/block-vpn/');
export const saveSettings   = (data) => client.post('/fraud_detection/settings/block-vpn/', data);

// Dashboard
export const getDashboard   = ()     => client.get('/fraud_detection/dashboard/');
export const getStatistics  = (days=30) => client.get('/fraud_detection/statistics/', { params: { days } });