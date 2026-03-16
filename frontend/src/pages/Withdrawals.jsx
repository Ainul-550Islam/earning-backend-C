import React, { useState, useEffect } from 'react';
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
