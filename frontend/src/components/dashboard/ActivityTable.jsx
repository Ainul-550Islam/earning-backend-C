// src/components/dashboard/ActivityTable.jsx
import React, { useState, useEffect } from 'react';

const getToken = () => localStorage.getItem('adminAccessToken');
const apiFetch = (url) =>
  fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } }).then(r => r.json());

const statusStyle = {
  urgent:   { bg:'rgba(255,50,50,0.18)',  color:'#ff6060', border:'rgba(255,50,50,0.35)'  },
  warning:  { bg:'rgba(255,140,0,0.18)',  color:'#ffaa40', border:'rgba(255,140,0,0.35)'  },
  done:     { bg:'rgba(0,255,100,0.15)',  color:'#00ff66', border:'rgba(0,255,100,0.35)'  },
  pending:  { bg:'rgba(255,215,0,0.15)',  color:'#ffd700', border:'rgba(255,215,0,0.35)'  },
  info:     { bg:'rgba(0,150,255,0.15)',  color:'#4da6ff', border:'rgba(0,150,255,0.35)'  },
};

const moduleColors = {
  'Wallet':    '#00f3ff',
  'Tasks':     '#00ff00',
  'KYC':       '#ffd700',
  'Security':  '#ff00ff',
  'Referral':  '#ff8800',
  'Support':   '#aa88ff',
  'System':    '#888888',
};

const timeAgo = (dateStr) => {
  if (!dateStr) return '—';
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
};

const buildActivities = (notifications, tickets, completions, users) => {
  const activities = [];

  // Notifications থেকে
  if (Array.isArray(notifications?.results)) {
    notifications.results.slice(0, 3).forEach(n => {
      activities.push({
        user: n.user?.username || 'User',
        action: n.title || 'Notification',
        module: 'System',
        status: n.is_read ? 'Read' : 'New',
        statusType: n.is_read ? 'done' : 'info',
        time: timeAgo(n.created_at),
      });
    });
  }

  // Support tickets থেকে
  if (Array.isArray(tickets)) {
    tickets.slice(0, 2).forEach(t => {
      activities.push({
        user: t.user?.username || 'User',
        action: t.subject || 'Support Ticket',
        module: 'Support',
        status: t.status === 'open' ? 'Open' : t.status === 'resolved' ? 'Done' : 'Pending',
        statusType: t.status === 'open' ? 'urgent' : t.status === 'resolved' ? 'done' : 'pending',
        time: timeAgo(t.created_at),
      });
    });
  }

  // Task completions থেকে
  if (Array.isArray(completions?.data)) {
    completions.data.slice(0, 2).forEach(c => {
      activities.push({
        user: c.user?.username || 'User',
        action: 'Task Complete',
        module: 'Tasks',
        status: c.status === 'completed' ? 'Done' : 'Pending',
        statusType: c.status === 'completed' ? 'done' : 'pending',
        time: timeAgo(c.completed_at),
      });
    });
  }

  // Real users থেকে recent signups
  if (Array.isArray(users)) {
    users.slice(0, 2).forEach(u => {
      activities.push({
        user: u.username,
        action: 'New Signup',
        module: 'System',
        status: u.is_verified ? 'Verified' : 'Pending',
        statusType: u.is_verified ? 'done' : 'pending',
        time: timeAgo(u.created_at),
      });
    });
  }

  // Sort by most recent (time string এ র্যান্ডম sort না করে index অনুযায়ী)
  return activities.slice(0, 8);
};

const ActivityTable = () => {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [notifications, tickets, completions, users] = await Promise.all([
          apiFetch('/api/notifications/'),
          apiFetch('/api/support/tickets/').catch(() => []),
          apiFetch('/api/tasks/completions/'),
          apiFetch('/api/users/'),
        ]);

        const acts = buildActivities(notifications, tickets, completions, users);

        // Fallback যদি কিছুই না আসে
        if (acts.length === 0) {
          setActivities([
            { user:'—', action:'No activities yet', module:'System', status:'—', statusType:'info', time:'—' }
          ]);
        } else {
          setActivities(acts);
        }
      } catch (e) {
        console.error('ActivityTable error:', e);
        setActivities([
          { user:'—', action:'Could not load activities', module:'System', status:'Error', statusType:'urgent', time:'—' }
        ]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div style={{
      borderRadius:8, padding:'10px 12px',
      background:'rgba(8,8,28,0.85)',
      border:'1px solid rgba(0,243,255,0.20)',
      boxShadow:'0 0 12px rgba(0,243,255,0.06)',
    }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <span style={{ fontFamily:'Orbitron, sans-serif', fontSize:11, fontWeight:700, color:'#fff', letterSpacing:'0.1em', textTransform:'uppercase' }}>
          Recent Activities
        </span>
        <div style={{ width:20, height:2, background:'linear-gradient(90deg,#ff00ff,transparent)' }} />
      </div>

      {loading ? (
        <div style={{ color:'#4b5563', fontSize:11, textAlign:'center', padding:'20px 0' }}>Loading...</div>
      ) : (
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead>
            <tr>
              {['User','Action','Module','Status','Time'].map(h => (
                <th key={h} style={{ textAlign:'left', padding:'4px 8px', color:'#4b5563', fontSize:9, textTransform:'uppercase', letterSpacing:'0.1em', fontWeight:700, borderBottom:'1px solid rgba(255,255,255,0.06)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activities.map((row, i) => {
              const ss = statusStyle[row.statusType] || statusStyle.info;
              const mc = moduleColors[row.module] || '#888';
              return (
                <tr key={i} style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }}
                  onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.03)'}
                  onMouseLeave={e => e.currentTarget.style.background='transparent'}
                >
                  <td style={{ padding:'6px 8px', color:'#e5e7eb', fontSize:11, fontWeight:600, whiteSpace:'nowrap' }}>{row.user}</td>
                  <td style={{ padding:'6px 8px', color:'#9ca3af', fontSize:11, whiteSpace:'nowrap' }}>{row.action}</td>
                  <td style={{ padding:'6px 8px', fontSize:11, fontWeight:700, whiteSpace:'nowrap', color:mc, textShadow:`0 0 6px ${mc}80` }}>{row.module}</td>
                  <td style={{ padding:'6px 8px' }}>
                    <span style={{ padding:'2px 7px', borderRadius:4, fontSize:9, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.05em', background:ss.bg, color:ss.color, border:`1px solid ${ss.border}` }}>
                      {row.status}
                    </span>
                  </td>
                  <td style={{ padding:'6px 8px', color:'#6b7280', fontSize:10, whiteSpace:'nowrap' }}>{row.time}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ActivityTable;