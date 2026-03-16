// src/design-system/components/GlassCard.jsx
import React from 'react';
import PropTypes from 'prop-types';

// Tailwind dynamic class সমস্যা এড়াতে inline style ব্যবহার
const neonStyles = {
  cyan: {
    border: 'rgba(0, 243, 255, 0.30)',
    shadow: '0 0 16px rgba(0,243,255,0.12), inset 0 0 16px rgba(0,243,255,0.04)',
    hoverBorder: 'rgba(0, 243, 255, 0.60)',
    hoverShadow: '0 0 24px rgba(0,243,255,0.20), inset 0 0 20px rgba(0,243,255,0.06)',
  },
  pink: {
    border: 'rgba(255, 0, 255, 0.30)',
    shadow: '0 0 16px rgba(255,0,255,0.12), inset 0 0 16px rgba(255,0,255,0.04)',
    hoverBorder: 'rgba(255, 0, 255, 0.60)',
    hoverShadow: '0 0 24px rgba(255,0,255,0.20), inset 0 0 20px rgba(255,0,255,0.06)',
  },
  gold: {
    border: 'rgba(255, 215, 0, 0.30)',
    shadow: '0 0 16px rgba(255,215,0,0.12), inset 0 0 16px rgba(255,215,0,0.04)',
    hoverBorder: 'rgba(255, 215, 0, 0.60)',
    hoverShadow: '0 0 24px rgba(255,215,0,0.20), inset 0 0 20px rgba(255,215,0,0.06)',
  },
  lime: {
    border: 'rgba(0, 255, 0, 0.30)',
    shadow: '0 0 16px rgba(0,255,0,0.12), inset 0 0 16px rgba(0,255,0,0.04)',
    hoverBorder: 'rgba(0, 255, 0, 0.60)',
    hoverShadow: '0 0 24px rgba(0,255,0,0.20), inset 0 0 20px rgba(0,255,0,0.06)',
  },
};

const GlassCard = ({
  children,
  className = '',
  neonColor = 'cyan',
  hoverEffect = true,
  padding = 'p-4',
}) => {
  const style = neonStyles[neonColor] || neonStyles.cyan;
  const [hovered, setHovered] = React.useState(false);

  return (
    <div
      onMouseEnter={() => hoverEffect && setHovered(true)}
      onMouseLeave={() => hoverEffect && setHovered(false)}
      className={`relative rounded-xl transition-all duration-300 ${padding} ${className}`}
      style={{
        background: 'rgba(8, 8, 24, 0.65)',
        backdropFilter: 'blur(18px)',
        WebkitBackdropFilter: 'blur(18px)',
        border: `1px solid ${hovered ? style.hoverBorder : style.border}`,
        boxShadow: hovered ? style.hoverShadow : style.shadow,
      }}
    >
      {/* Corner accents - ইমেজের cyberpunk corner lines */}
      <div style={{
        position: 'absolute', top: 0, right: 0,
        width: 16, height: 16,
        borderTop: `1px solid ${style.hoverBorder}`,
        borderRight: `1px solid ${style.hoverBorder}`,
        borderRadius: '0 12px 0 0',
      }} />
      <div style={{
        position: 'absolute', bottom: 0, left: 0,
        width: 16, height: 16,
        borderBottom: `1px solid ${style.hoverBorder}`,
        borderLeft: `1px solid ${style.hoverBorder}`,
        borderRadius: '0 0 0 12px',
      }} />

      {children}
    </div>
  );
};

GlassCard.propTypes = {
  children: PropTypes.node.isRequired,
  className: PropTypes.string,
  neonColor: PropTypes.oneOf(['cyan', 'pink', 'gold', 'lime']),
  hoverEffect: PropTypes.bool,
  padding: PropTypes.string,
};

export default GlassCard;