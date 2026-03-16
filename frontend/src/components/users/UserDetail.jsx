// src/components/users/UserDetail.jsx
import React from 'react';
import { User, Mail, Shield, Calendar, Activity } from 'lucide-react';
import GlassCard from '../../design-system/components/GlassCard';
import NeonBadge from '../../design-system/components/NeonBadge';
import { formatDate } from '../../utils/formatters';

const UserDetail = ({ user }) => {
  if (!user) return null;

  return (
    <GlassCard neonColor="cyan" className="relative overflow-hidden">
      {/* Decorative Header */}
      <div className="h-24 bg-gradient-to-r from-neon-cyan/20 to-neon-pink/20 relative">
        <div className="absolute -bottom-10 left-6">
          <div className="w-20 h-20 rounded-full bg-cyber-dark border-4 border-neon-cyan p-1 shadow-neon-cyan">
            <div className="w-full h-full rounded-full bg-gray-800 flex items-center justify-center">
              <User className="w-10 h-10 text-gray-500" />
            </div>
          </div>
        </div>
      </div>

      <div className="pt-12 px-6 pb-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-white">{user.username}</h2>
            <p className="text-gray-500 text-sm flex items-center mt-1">
              <Mail className="w-3 h-3 mr-1" /> {user.email}
            </p>
          </div>
          <NeonBadge text={user.status || 'ACTIVE'} variant="success" />
        </div>

        <div className="grid grid-cols-2 gap-4 mt-6 border-t border-white/10 pt-4">
          <div className="flex items-center space-x-2 text-gray-400">
            <Shield className="w-4 h-4 text-neon-gold" />
            <span className="text-sm">{user.role || 'User'}</span>
          </div>
          <div className="flex items-center space-x-2 text-gray-400">
            <Calendar className="w-4 h-4" />
            <span className="text-sm">Joined {formatDate(user.date_joined)}</span>
          </div>
        </div>
        
        {/* Quick Actions could go here */}
      </div>
    </GlassCard>
  );
};

export default UserDetail;