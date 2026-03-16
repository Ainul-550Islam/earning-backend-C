// src/components/common/ErrorBoundary.jsx
import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen bg-cyber-dark flex flex-col items-center justify-center text-center p-6 relative overflow-hidden">
          {/* Background Effect */}
          <div className="absolute inset-0 bg-neon-pink/5"></div>
          
          <div className="relative z-10 bg-cyber-panel/80 backdrop-blur-xl border border-neon-pink/30 rounded-2xl p-10 max-w-lg shadow-neon-pink/20">
            <div className="flex justify-center mb-6">
              <div className="p-4 border border-neon-pink/30 rounded-full bg-neon-pink/10 animate-pulse">
                <AlertTriangle className="w-12 h-12 text-neon-pink" />
              </div>
            </div>
            
            <h1 className="text-2xl font-bold text-white font-cyber mb-2">SYSTEM FAILURE</h1>
            <p className="text-gray-400 mb-6">
              A critical error occurred in the mainframe. The admin has been notified.
            </p>
            
            <div className="bg-cyber-dark/50 p-3 rounded mb-6 text-left">
              <code className="text-xs text-neon-pink break-all">
                {this.state.error?.message || 'Unknown Error'}
              </code>
            </div>

            <button 
              onClick={() => window.location.reload()} 
              className="px-6 py-2 bg-neon-pink/10 border border-neon-pink text-neon-pink rounded-lg hover:bg-neon-pink/20 transition-colors flex items-center space-x-2 mx-auto"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reboot System</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;