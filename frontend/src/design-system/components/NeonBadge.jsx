// src/design-system/components/NeonBadge.jsx
import React from 'react';
import PropTypes from 'prop-types';

const variantStyles = {
  default: {
    background: 'rgba(107,114,128,0.20)',
    color: '#d1d5db',
    border: '1px solid rgba(107,114,128,0.35)',
    boxShadow: 'none',
  },
  info: { // cyan - DAILY
    background: 'rgba(0,243,255,0.12)',
    color: '#00f3ff',
    border: '1px solid rgba(0,243,255,0.35)',
    boxShadow: '0 0 8px rgba(0,243,255,0.30)',
  },
  success: { // lime - SOCIAL
    background: 'rgba(0,255,0,0.10)',
    color: '#00ff00',
    border: '1px solid rgba(0,255,0,0.35)',
    boxShadow: '0 0 8px rgba(0,255,0,0.25)',
  },
  warning: { // gold - SURVEY
    background: 'rgba(255,215,0,0.12)',
    color: '#ffd700',
    border: '1px solid rgba(255,215,0,0.35)',
    boxShadow: '0 0 8px rgba(255,215,0,0.30)',
  },
  danger: { // pink - GAME
    background: 'rgba(255,0,255,0.12)',
    color: '#ff00ff',
    border: '1px solid rgba(255,0,255,0.35)',
    boxShadow: '0 0 8px rgba(255,0,255,0.30)',
  },
};

const NeonBadge = ({ text, variant = 'default', pulse = false }) => {
  const s = variantStyles[variant] || variantStyles.default;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1px 6px',
        borderRadius: '4px',
        fontSize: '9px',
        fontFamily: 'Orbitron, sans-serif',
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
        background: s.background,
        color: s.color,
        border: s.border,
        boxShadow: s.boxShadow,
        textShadow: `0 0 6px ${s.color}`,
        animation: pulse ? 'pulse 2s infinite' : 'none',
        transition: 'all 0.2s',
      }}
    >
      {text}
    </span>
  );
};

NeonBadge.propTypes = {
  text: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(['default', 'success', 'warning', 'danger', 'info']),
  pulse: PropTypes.bool,
};

export default NeonBadge;