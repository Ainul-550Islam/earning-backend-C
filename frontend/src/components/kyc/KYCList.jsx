// src/components/kyc/KYCList.jsx
import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Clock } from 'lucide-react';
import GlassCard from '../../design-system/components/GlassCard';
import NeonBadge from '../../design-system/components/NeonBadge';
import client from '../../api/client';

const KYCList = () => {
  const [kycData, setKycData] = useState([]);

  useEffect(() => {
    const fetchKYC = async () => {
      try {
        const res = await client.get('/kyc/');
        const data = res.data; setKycData(Array.isArray(data) ? data : Array.isArray(data.results) ? data.results : []);
      } catch (err) {
        console.error("Failed to fetch KYC", err);
      }
    };
    fetchKYC();
  }, []);

  return (
    <div className="space-y-3">
      {kycData.map((item) => (
        <GlassCard key={item.id} className="flex items-center justify-between p-4">
          <div className="flex items-center space-x-4">
            <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center text-gray-400">
              ID
            </div>
            <div>
              <p className="text-white font-medium">{item.user_name}</p>
              <p className="text-xs text-gray-500">Submitted: {item.date}</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {item.status === 'PENDING' && <Clock className="w-4 h-4 text-neon-gold animate-pulse" />}
            {item.status === 'VERIFIED' && <CheckCircle className="w-4 h-4 text-neon-lime" />}
            {item.status === 'REJECTED' && <XCircle className="w-4 h-4 text-neon-pink" />}
            <NeonBadge text={item.status} variant={item.status === 'PENDING' ? 'warning' : item.status === 'VERIFIED' ? 'success' : 'danger'} />
          </div>
        </GlassCard>
      ))}
    </div>
  );
};

export default KYCList;