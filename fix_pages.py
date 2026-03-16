import os

pages = {
    'frontend/src/pages/Djoyalty.jsx': """import React, { useState, useEffect } from 'react';
import client from '../api/client';

export default function Djoyalty() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await client.get('/customers/');
        setCustomers(res.data.results || res.data || []);
      } catch (err) {
        setError('Failed to load loyalty data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div style={{color:'#c44fff',padding:40,textAlign:'center'}}>Loading Loyalty...</div>;
  if (error)   return <div style={{color:'#ff2d78',padding:40,textAlign:'center'}}>{error}</div>;

  return (
    <div style={{padding:24,color:'#eae0ff'}}>
      <h1 style={{fontFamily:'Orbitron',color:'#ffd700',marginBottom:24}}>Loyalty Program</h1>
      <div style={{background:'rgba(7,4,28,.88)',border:'1px solid rgba(100,60,220,.25)',borderRadius:14,padding:20}}>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead>
            <tr style={{borderBottom:'1px solid rgba(100,60,220,.25)'}}>
              {['Customer','Points','Tier','Status'].map(h=>(
                <th key={h} style={{padding:'10px 16px',textAlign:'left',color:'rgba(180,160,255,.5)',fontSize:11}}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {customers.length === 0 ? (
              <tr><td colSpan={4} style={{textAlign:'center',padding:40,color:'rgba(180,160,255,.4)'}}>No loyalty data yet</td></tr>
            ) : customers.map((c,i) => (
              <tr key={c.id||i} style={{borderBottom:'1px solid rgba(100,60,220,.07)'}}>
                <td style={{padding:'12px 16px'}}>{c.name||c.username||'Customer'}</td>
                <td style={{padding:'12px 16px',color:'#ffd700'}}>{c.points||0}</td>
                <td style={{padding:'12px 16px',color:'#c44fff'}}>{c.tier||'Bronze'}</td>
                <td style={{padding:'12px 16px',color:'#00ff88'}}>{c.status||'Active'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
""",
    'frontend/src/pages/Withdrawals.jsx': """import React, { useState, useEffect } from 'react';
import client from '../api/client';

export default function Withdrawals() {
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await client.get('/wallet/withdrawals/');
        setWithdrawals(res.data.results || res.data || []);
      } catch (err) {
        setError('Failed to load withdrawals');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div style={{color:'#c44fff',padding:40,textAlign:'center'}}>Loading Withdrawals...</div>;
  if (error)   return <div style={{color:'#ff2d78',padding:40,textAlign:'center'}}>{error}</div>;

  return (
    <div style={{padding:24,color:'#eae0ff'}}>
      <h1 style={{fontFamily:'Orbitron',color:'#00f3ff',marginBottom:24}}>Withdrawals</h1>
      <div style={{background:'rgba(7,4,28,.88)',border:'1px solid rgba(100,60,220,.25)',borderRadius:14,padding:20}}>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead>
            <tr style={{borderBottom:'1px solid rgba(100,60,220,.25)'}}>
              {['User','Amount','Method','Status','Date'].map(h=>(
                <th key={h} style={{padding:'10px 16px',textAlign:'left',color:'rgba(180,160,255,.5)',fontSize:11}}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {withdrawals.length === 0 ? (
              <tr><td colSpan={5} style={{textAlign:'center',padding:40,color:'rgba(180,160,255,.4)'}}>No withdrawals yet</td></tr>
            ) : withdrawals.map((w,i) => (
              <tr key={w.id||i} style={{borderBottom:'1px solid rgba(100,60,220,.07)'}}>
                <td style={{padding:'12px 16px'}}>{w.user||'User'}</td>
                <td style={{padding:'12px 16px',color:'#ffd700'}}>${w.amount||0}</td>
                <td style={{padding:'12px 16px',color:'#00f3ff'}}>{w.payment_method||'N/A'}</td>
                <td style={{padding:'12px 16px',color:w.status==='completed'?'#00ff88':w.status==='pending'?'#ffd700':'#ff2d78'}}>{w.status||'pending'}</td>
                <td style={{padding:'12px 16px',color:'rgba(180,160,255,.5)'}}>{w.created_at?.slice(0,10)||'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
""",
    'frontend/src/pages/AdminDashboard.jsx': """import React, { useState, useEffect } from 'react';
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
""",
}

for path, content in pages.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Created:', path)

print('All done!')