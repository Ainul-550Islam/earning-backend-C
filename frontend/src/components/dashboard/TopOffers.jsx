// src/components/dashboard/TopOffers.jsx
import React, { useState } from 'react';
// import useTasks from '../../hooks/useTasks';
import { useTasks } from '../../hooks/useTasks';
import { Loader2, Flame, Menu } from 'lucide-react';

const badgeConfig = {
  'Daily':       { label:'DAILY',  color:'#00f3ff', bg:'rgba(0,243,255,0.12)'   },
  'Gamified':    { label:'GAME',   color:'#ff00ff', bg:'rgba(255,0,255,0.12)'   },
  'Social':      { label:'SOCIAL', color:'#00ff00', bg:'rgba(0,255,0,0.12)'     },
  'Survey':      { label:'SURVEY', color:'#ffd700', bg:'rgba(255,215,0,0.12)'   },
  'App Install': { label:'APP',    color:'#a78bfa', bg:'rgba(167,139,250,0.12)' },
};

const dotColors = [
  '#00f3ff','#ff00ff','#ffd700','#00ff00','#a78bfa',
  '#ff6600','#00ffcc','#ff3366','#66ff00','#ff9900',
  '#00ccff','#ff0066','#ccff00','#6600ff','#ff6699',
  '#00ff99','#ff3300','#0099ff','#ff9933','#33ff00',
];

const LIMIT_OPTIONS = [20, 50, 70, 100];

const TopOffers = () => {
  const [limit, setLimit] = useState(100);
  const [showLimitMenu, setShowLimitMenu] = useState(false);
  // const { tasks, loading, totalCount } = useTasks({ limit });
  const { tasks: rawTasks, loading, totalCount } = useTasks({ limit });
  const tasks = Array.isArray(rawTasks) ? rawTasks : rawTasks?.results || [];

  return (
    <div style={{
      borderRadius: 10,
      background: 'rgba(8,8,24,0.80)',
      border: '1px solid rgba(255,0,255,0.25)',
      boxShadow: '0 0 15px rgba(255,0,255,0.08)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
      height: '100%',
    }}>

      {/* ── Header ── */}
      <div style={{
        padding: '10px 12px 8px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Flame style={{ width: 14, height: 14, color: '#ff6600' }} />
          <span style={{
            fontFamily: 'Orbitron, sans-serif', fontSize: 12,
            fontWeight: 700, color: '#fff', letterSpacing: '0.1em',
          }}>
            Top Offers
          </span>
          {/* Count badge */}
          <span style={{
            padding: '1px 6px', borderRadius: 10,
            background: 'rgba(255,0,255,0.15)',
            color: '#ff00ff', fontSize: 9,
            fontFamily: 'Orbitron, sans-serif', fontWeight: 700,
            border: '1px solid rgba(255,0,255,0.3)',
          }}>
            {tasks.length}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
          <span style={{ color: '#00f3ff', fontSize: 11, cursor: 'pointer', textShadow: '0 0 6px #00f3ff' }}>
            View All
          </span>

          {/* Limit selector */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowLimitMenu(!showLimitMenu)}
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 6, padding: '2px 8px',
                color: '#9ca3af', fontSize: 10, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
                fontFamily: 'Orbitron, sans-serif',
              }}
            >
              {limit} <Menu style={{ width: 10, height: 10 }} />
            </button>

            {showLimitMenu && (
              <div style={{
                position: 'absolute', top: '100%', right: 0, marginTop: 4,
                background: 'rgba(8,8,28,0.98)',
                border: '1px solid rgba(0,243,255,0.25)',
                borderRadius: 8, overflow: 'hidden',
                zIndex: 100, minWidth: 70,
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              }}>
                {LIMIT_OPTIONS.map(opt => (
                  <div
                    key={opt}
                    onClick={() => { setLimit(opt); setShowLimitMenu(false); }}
                    style={{
                      padding: '7px 12px', cursor: 'pointer',
                      fontSize: 11, color: opt === limit ? '#00f3ff' : '#d1d5db',
                      background: opt === limit ? 'rgba(0,243,255,0.08)' : 'transparent',
                      fontFamily: 'Orbitron, sans-serif',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,243,255,0.06)'}
                    onMouseLeave={e => e.currentTarget.style.background = opt === limit ? 'rgba(0,243,255,0.08)' : 'transparent'}
                  >
                    {opt} tasks
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Task List ── */}
      <div style={{
        flex: 1, overflowY: 'auto',
        padding: '6px 8px',
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(255,0,255,0.2) transparent',
      }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 30 }}>
            <Loader2 style={{ width: 20, height: 20, color: '#00f3ff' }} />
            <span style={{ color: '#6b7280', fontSize: 11, marginLeft: 8 }}>Loading {limit} tasks...</span>
          </div>
        ) : (
          tasks.map((task, idx) => {
            const badge = badgeConfig[task.category] || badgeConfig['App Install'];
            return (
              <div
                key={task.id || idx}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '5px 6px', borderRadius: 6, marginBottom: 2,
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.04)',
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
                onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
              >
                {/* Left: index + dot + name */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                  <span style={{ color: '#4b5563', fontSize: 8, width: 14, textAlign: 'right', flexShrink: 0 }}>
                    {idx + 1}
                  </span>
                  <div style={{
                    width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                    background: dotColors[idx % dotColors.length],
                    boxShadow: `0 0 4px ${dotColors[idx % dotColors.length]}`,
                  }} />
                  <span style={{
                    color: '#e5e7eb', fontSize: 11,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {task.title}
                  </span>
                </div>

                {/* Right: reward + badge */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0, marginLeft: 6 }}>
                  <span style={{
                    color: '#ffd700', fontSize: 10, fontWeight: 600,
                    whiteSpace: 'nowrap', textShadow: '0 0 6px #ffd70060',
                  }}>
                    {task.reward || '500 Points'}
                  </span>
                  <span style={{
                    padding: '1px 5px', borderRadius: 3,
                    fontSize: 8, fontFamily: 'Orbitron, sans-serif',
                    fontWeight: 700, letterSpacing: '0.05em',
                    background: badge.bg, color: badge.color,
                    border: `1px solid ${badge.color}40`,
                    textShadow: `0 0 5px ${badge.color}`,
                    whiteSpace: 'nowrap',
                  }}>
                    {badge.label}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Footer: total count ── */}
      <div style={{
        padding: '6px 12px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{ color: '#6b7280', fontSize: 9, fontFamily: 'Orbitron, sans-serif' }}>
          Showing {tasks.length} offers
        </span>
        <span style={{ color: '#6b7280', fontSize: 9 }}>
          Total: {totalCount}
        </span>
      </div>
    </div>
  );
};

export default TopOffers;