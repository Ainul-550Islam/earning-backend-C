import React, { useState, useEffect } from 'react';
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
