// src/context/ThemeContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';

const THEMES = [
  {
    name: 'cyan',
    primary: '#00f3ff',
    secondary: '#ff00ff',
    bg1: 'rgba(0,50,130,0.22)',
    bg2: 'rgba(90,0,130,0.22)',
    headerBorder: 'rgba(0,243,255,0.12)',
    sidebarBorder: 'rgba(0,243,255,0.12)',
  },
  {
    name: 'pink',
    primary: '#ff00ff',
    secondary: '#00f3ff',
    bg1: 'rgba(120,0,80,0.22)',
    bg2: 'rgba(60,0,120,0.22)',
    headerBorder: 'rgba(255,0,255,0.12)',
    sidebarBorder: 'rgba(255,0,255,0.12)',
  },
  {
    name: 'gold',
    primary: '#ffd700',
    secondary: '#ff6600',
    bg1: 'rgba(80,50,0,0.22)',
    bg2: 'rgba(100,30,0,0.22)',
    headerBorder: 'rgba(255,215,0,0.12)',
    sidebarBorder: 'rgba(255,215,0,0.12)',
  },
  {
    name: 'lime',
    primary: '#00ff00',
    secondary: '#00f3ff',
    bg1: 'rgba(0,80,30,0.22)',
    bg2: 'rgba(0,60,80,0.22)',
    headerBorder: 'rgba(0,255,0,0.12)',
    sidebarBorder: 'rgba(0,255,0,0.12)',
  },
];

const ThemeContext = createContext(THEMES[0]);

export const ThemeProvider = ({ children }) => {
  const [themeIndex, setThemeIndex] = useState(0);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setTransitioning(true);
      setTimeout(() => {
        setThemeIndex(i => (i + 1) % THEMES.length);
        setTransitioning(false);
      }, 500); // 500ms fade transition
    }, 60000); // 1 minute

    return () => clearInterval(interval);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme: THEMES[themeIndex], transitioning, THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
export { THEMES };