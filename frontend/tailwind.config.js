/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  // Safelist: এই classes গুলো dynamic হলেও Tailwind build এ রাখবে
  safelist: [
    'text-neon-cyan', 'text-neon-pink', 'text-neon-gold', 'text-neon-lime', 'text-neon-red',
    'bg-neon-cyan', 'bg-neon-pink', 'bg-neon-gold', 'bg-neon-lime',
    'border-neon-cyan', 'border-neon-pink', 'border-neon-gold', 'border-neon-lime',
    'bg-neon-cyan/10', 'bg-neon-pink/10', 'bg-neon-gold/10', 'bg-neon-lime/10',
    'bg-neon-cyan/20', 'bg-neon-pink/20', 'bg-neon-gold/20', 'bg-neon-lime/20',
    'border-neon-cyan/20', 'border-neon-pink/20', 'border-neon-gold/20', 'border-neon-lime/20',
    'border-neon-cyan/30', 'border-neon-pink/30', 'border-neon-gold/30', 'border-neon-lime/30',
    'shadow-neon-cyan', 'shadow-neon-pink', 'shadow-neon-gold',
    'bg-cyber-dark', 'bg-cyber-panel',
    'font-cyber', 'font-body',
  ],
  theme: {
    extend: {
      colors: {
        'cyber-dark':  '#050510',
        'cyber-panel': '#0a0a1a',
        'cyber-border':'rgba(255,255,255,0.10)',
        'neon-cyan':   '#00f3ff',
        'neon-pink':   '#ff00ff',
        'neon-gold':   '#ffd700',
        'neon-lime':   '#00ff00',
        'neon-red':    '#ff3333',
      },
      fontFamily: {
        'cyber': ['Orbitron', 'sans-serif'],
        'body':  ['Rajdhani', 'sans-serif'],
      },
      boxShadow: {
        'neon-cyan': '0 0 10px #00f3ff, 0 0 20px rgba(0,243,255,0.5)',
        'neon-pink': '0 0 10px #ff00ff, 0 0 20px rgba(255,0,255,0.5)',
        'neon-gold': '0 0 10px #ffd700, 0 0 20px rgba(255,215,0,0.5)',
        'neon-lime': '0 0 10px #00ff00, 0 0 20px rgba(0,255,0,0.5)',
        'glass':     '0 8px 32px 0 rgba(0,0,0,0.4)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4,0,0.6,1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%':   { opacity: '0.5' },
          '100%': { opacity: '1' },
        }
      },
    },
  },
  plugins: [],
}