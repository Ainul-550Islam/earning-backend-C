// src/components/dashboard/StatsCard.jsx
import React, { useState } from 'react';
import PropTypes from 'prop-types';

const neonConfig = {
  cyan: { color: '#00f3ff', border: 'rgba(0,243,255,0.35)', shadow: '0 0 15px rgba(0,243,255,0.12)', bg: 'rgba(0,243,255,0.07)' },
  gold: { color: '#ffd700', border: 'rgba(255,215,0,0.35)',  shadow: '0 0 15px rgba(255,215,0,0.12)',  bg: 'rgba(255,215,0,0.07)'  },
  lime: { color: '#00ff00', border: 'rgba(0,255,0,0.35)',    shadow: '0 0 15px rgba(0,255,0,0.12)',    bg: 'rgba(0,255,0,0.07)'    },
  pink: { color: '#ff00ff', border: 'rgba(255,0,255,0.35)',  shadow: '0 0 15px rgba(255,0,255,0.12)',  bg: 'rgba(255,0,255,0.07)'  },
};

const StatsCard = ({ title, value, icon: Icon, trend, trendValue, neonColor = 'cyan' }) => {
  const [hovered, setHovered] = useState(false);
  const cfg = neonConfig[neonColor] || neonConfig.cyan;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderRadius: 10, padding: '12px 14px',
        background: 'rgba(8,8,24,0.80)',
        border: `1px solid ${cfg.border}`,
        boxShadow: hovered ? cfg.shadow.replace('0.12', '0.25') : cfg.shadow,
        position: 'relative', overflow: 'hidden',
        transition: 'box-shadow 0.3s',
        cursor: 'default',
      }}
    >
      {/* glow blob */}
      <div style={{
        position: 'absolute', top: -10, right: -10,
        width: 60, height: 60, borderRadius: '50%',
        background: cfg.bg, filter: 'blur(14px)',
        transform: hovered ? 'scale(2)' : 'scale(1)',
        transition: 'transform 0.5s',
      }} />

      <div style={{ position: 'relative', zIndex: 1 }}>
        {/* Title + Icon row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ color: '#9ca3af', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            {title}
          </span>
          <div style={{
            width: 26, height: 26, borderRadius: 6,
            background: cfg.bg, border: `1px solid ${cfg.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <Icon style={{ width: 13, height: 13, color: cfg.color }} />
          </div>
        </div>

        {/* Value */}
        <div style={{
          fontSize: 24, fontWeight: 700,
          fontFamily: 'Orbitron, sans-serif',
          color: cfg.color,
          textShadow: `0 0 10px ${cfg.color}80`,
          lineHeight: 1, marginBottom: 4,
        }}>
          {value}
        </div>

        {/* Trend */}
        {trend && (
          <div style={{ fontSize: 11, fontWeight: 600, color: trend === 'up' ? '#00ff00' : '#ff3333' }}>
            {trend === 'up' ? '↑' : '↓'} {trendValue}
          </div>
        )}
      </div>

      {/* bottom line */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, transparent, ${cfg.color}80, transparent)`,
      }} />
    </div>
  );
};

StatsCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.elementType.isRequired,
  trend: PropTypes.oneOf(['up', 'down']),
  trendValue: PropTypes.string,
  neonColor: PropTypes.oneOf(['cyan', 'gold', 'pink', 'lime']),
};

export default StatsCard;