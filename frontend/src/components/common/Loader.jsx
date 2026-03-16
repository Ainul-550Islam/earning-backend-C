// src/components/common/Loader.jsx
import React from 'react';

const Loader = ({ fullScreen = false }) => {
  return (
    <div className={`flex items-center justify-center ${fullScreen ? 'h-screen w-screen bg-cyber-dark' : 'h-full w-full py-10'}`}>
      <div className="relative">
        {/* Outer Ring */}
        <div className="w-16 h-16 rounded-full border-t-2 border-b-2 border-neon-cyan animate-spin"></div>
        {/* Inner Ring */}
        <div className="absolute top-1 left-1 w-14 h-14 rounded-full border-r-2 border-l-2 border-neon-pink animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-neon-cyan rounded-full animate-pulse"></div>
      </div>
    </div>
  );
};

export default Loader;