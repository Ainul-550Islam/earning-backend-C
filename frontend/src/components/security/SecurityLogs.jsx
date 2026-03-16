// src/components/security/SecurityLogs.jsx
import React, { useState, useEffect } from 'react';
import { Shield, Terminal } from 'lucide-react';
import GlassCard from '../../design-system/components/GlassCard';
import HologramTable from '../../design-system/components/HologramTable';
import client from '../../api/client';

const SecurityLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await client.get('/security/logs/');
        setLogs(res.data.results || res.data);
      } catch (err) {
        console.error("Failed to fetch logs", err);
      } finally {
        setLoading(false);
      }
    };
    fetchLogs();
  }, []);

  const columns = [
    { key: 'timestamp', title: 'Time' },
    { key: 'action', title: 'Event' },
    { key: 'ip_address', title: 'IP Address' },
    { 
      key: 'status', 
      title: 'Status',
      render: (row) => (
        <span className={`${row.status === 'FAILED' ? 'text-neon-red' : 'text-neon-lime'}`}>
          {row.status}
        </span>
      )
    },
  ];

  return (
    <GlassCard neonColor="pink">
      <div className="flex items-center space-x-2 mb-4 border-b border-white/10 pb-4">
        <Terminal className="w-5 h-5 text-neon-pink" />
        <h3 className="text-lg font-bold text-white">Security Event Logs</h3>
      </div>
      <HologramTable columns={columns} data={logs} loading={loading} />
    </GlassCard>
  );
};

export default SecurityLogs;