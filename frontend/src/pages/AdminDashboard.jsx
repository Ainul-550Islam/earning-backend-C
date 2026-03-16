import React, { useState, useEffect } from 'react';
import client from '../api/client';

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await client.get('/users/dashboard-stats/');
        setStats(res.data);
      } catch (err) {
        setError('Failed to load dashboard stats');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div style={{color:'#c44fff',padding:40,textAlign:'center'}}>Loading Dashboard...</div>;
  if (error)   return <div style={{color:'#ff2d78',padding:40,textAlign:'center'}}>{error}</div>;

  const cards = [
    {label:'Total Users',  value:stats?.total_users||0,        color:'#ff2d78'},
    {label:'Active Users', value:stats?.active_users||0,       color:'#00f3ff'},
    {label:'Revenue',      value:'$'+(stats?.total_balance||0), color:'#ffd700'},
    {label:'Verified',     value:stats?.verified_users||0,     color:'#00ff88'},
  ];

  return (
    <div style={{padding:24,color:'#eae0ff'}}>
      <h1 style={{fontFamily:'Orbitron',color:'#c44fff',marginBottom:24}}>Admin Dashboard</h1>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:16}}>
        {cards.map((c,i) => (
          <div key={i} style={{background:'rgba(7,4,28,.88)',border:'1px solid rgba(100,60,220,.25)',borderRadius:14,padding:24}}>
            <div style={{fontFamily:'Share Tech Mono',fontSize:11,color:c.color,marginBottom:8}}>{c.label}</div>
            <div style={{fontFamily:'Orbitron',fontSize:28,fontWeight:900,color:c.color}}>{c.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
