// src/design-system/components/CyberInput.jsx
import React from 'react';
import PropTypes from 'prop-types';

const CyberInput = ({ 
  label, 
  type = 'text', 
  placeholder, 
  value, 
  onChange, 
  name, 
  icon: Icon, 
  error 
}) => {
  return (
    <div className="relative group">
      {label && (
        <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 ml-1">
          {label}
        </label>
      )}
      
      <div className="relative">
        {Icon && (
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-neon-cyan transition-colors">
            <Icon className="w-5 h-5" />
          </div>
        )}
        
        <input
          type={type}
          name={name}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className={`
            w-full bg-cyber-dark/60 border rounded-lg py-3 
            ${Icon ? 'pl-12' : 'pl-4'} pr-4 
            text-white placeholder-gray-600 
            transition-all duration-300
            focus:outline-none focus:ring-1
            ${error 
              ? 'border-neon-red/50 focus:border-neon-red focus:ring-neon-red/20' 
              : 'border-white/10 focus:border-neon-cyan/50 focus:ring-neon-cyan/20'}
          `}
        />
        
        {/* Neon Glow Effect on Focus */}
        <div className="absolute inset-0 rounded-lg border-2 border-transparent group-focus-within:border-neon-cyan/10 pointer-events-none"></div>
      </div>
      
      {error && (
        <p className="text-neon-red text-xs mt-1 ml-1 animate-pulse">{error}</p>
      )}
    </div>
  );
};

CyberInput.propTypes = {
  label: PropTypes.string,
  type: PropTypes.string,
  placeholder: PropTypes.string,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  name: PropTypes.string,
  icon: PropTypes.elementType,
  error: PropTypes.string,
};

export default CyberInput;