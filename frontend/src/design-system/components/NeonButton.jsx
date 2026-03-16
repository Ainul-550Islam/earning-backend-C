// src/design-system/components/NeonButton.jsx
import React from 'react';
import PropTypes from 'prop-types';

const NeonButton = ({ 
  text, 
  onClick, 
  icon: Icon, 
  color = 'cyan', 
  type = 'button', 
  disabled = false,
  className = '' 
}) => {
  
  const colorVariants = {
    cyan: {
      text: 'text-neon-cyan',
      border: 'border-neon-cyan',
      shadow: 'hover:shadow-[0_0_15px_rgba(0,243,255,0.4)]',
      bg: 'bg-neon-cyan/10'
    },
    pink: {
      text: 'text-neon-pink',
      border: 'border-neon-pink',
      shadow: 'hover:shadow-[0_0_15px_rgba(255,0,255,0.4)]',
      bg: 'bg-neon-pink/10'
    },
    gold: {
      text: 'text-neon-gold',
      border: 'border-neon-gold',
      shadow: 'hover:shadow-[0_0_15px_rgba(255,215,0,0.4)]',
      bg: 'bg-neon-gold/10'
    },
    lime: {
      text: 'text-neon-lime',
      border: 'border-neon-lime',
      shadow: 'hover:shadow-[0_0_15px_rgba(0,255,0,0.4)]',
      bg: 'bg-neon-lime/10'
    }
  };

  const styles = colorVariants[color] || colorVariants.cyan;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`
        relative group flex items-center justify-center space-x-2 
        px-6 py-2.5 rounded-lg font-semibold text-sm uppercase tracking-wider
        border transition-all duration-300
        ${styles.text} ${styles.border} ${styles.shadow}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-white/5'}
        ${className}
      `}
    >
      {/* Glitch Effect on Hover */}
      <span className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-transparent via-white/10 to-transparent"></span>
      
      {Icon && <Icon className="w-4 h-4 relative z-10" />}
      <span className="relative z-10">{text}</span>
    </button>
  );
};

NeonButton.propTypes = {
  text: PropTypes.string.isRequired,
  onClick: PropTypes.func,
  icon: PropTypes.elementType,
  color: PropTypes.oneOf(['cyan', 'pink', 'gold', 'lime']),
  type: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};

export default NeonButton;