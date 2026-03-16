// src/components/security/FraudAlerts.jsx
import React, { useState, useEffect } from 'react';
import { AlertTriangle, Shield, UserX } from 'lucide-react';
import GlassCard from '../../design-system/components/GlassCard'; // PATH FIXED
import NeonBadge from '../../design-system/components/NeonBadge';
import client from '../../api/client';

const FraudAlerts = () => {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await client.get('/fraud_detection/alerts/');
        setAlerts(res.data.results || res.data);
      } catch (err) {
        console.error("Security scan failed", err);
      }
    };
    fetchAlerts();
  }, []);

  return (
    <GlassCard neonColor="pink" className="relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Shield className="w-5 h-5 text-neon-pink" />
          <h3 className="text-lg font-bold text-white">Fraud Detection System</h3>
        </div>
        <NeonBadge text="LIVE" variant="danger" pulse />
      </div>

      {/* Alerts List */}
      <div className="space-y-3 max-h-80 overflow-y-auto custom-scrollbar pr-2">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500 border border-dashed border-gray-700 rounded-lg">
            <Shield className="w-8 h-8 mx-auto mb-2 text-neon-lime" />
            <p>All Systems Secure</p>
          </div>
        ) : (
          alerts.map((alert) => {
            const isHighPriority = alert.risk_level === 'HIGH' || alert.risk_level === 'CRITICAL';
            
            return (
              <div 
                key={alert.id}
                className={`
                  relative p-4 rounded-lg border transition-all duration-300
                  ${isHighPriority 
                    ? 'bg-neon-red/5 border-neon-red/50 animate-pulse shadow-[0_0_15px_rgba(255,51,51,0.2)]' 
                    : 'bg-neon-gold/5 border-neon-gold/30'}
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className={`mt-1 p-1 rounded ${isHighPriority ? 'bg-neon-red/20 text-neon-red' : 'bg-neon-gold/20 text-neon-gold'}`}>
                      {isHighPriority ? <UserX className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">{alert.title || 'Suspicious Activity'}</h4>
                      <p className="text-xs text-gray-400 mt-0.5">{alert.description}</p>
                      <p className="text-xs text-gray-600 mt-1">User ID: {alert.user_id || 'Unknown'}</p>
                    </div>
                  </div>
                  <NeonBadge 
                    text={alert.risk_level} 
                    variant={isHighPriority ? 'danger' : 'warning'} 
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </GlassCard>
  );
};

export default FraudAlerts;