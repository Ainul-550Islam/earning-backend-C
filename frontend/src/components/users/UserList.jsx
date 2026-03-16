// src/components/users/UserList.jsx
import React from 'react';
import { User, Mail, Shield, MoreVertical } from 'lucide-react';
import GlassCard from '../../design-system/components/GlassCard';
import NeonBadge from '../../design-system/components/NeonBadge';
import { formatDate } from '../../utils/formatters';

const UserList = ({ users, loading }) => {
  
  const getRoleVariant = (role) => {
    switch (role) {
      case 'ADMIN': return 'danger';
      case 'MODERATOR': return 'warning';
      default: return 'info';
    }
  };

  const getStatusVariant = (status) => {
    return status === 'ACTIVE' ? 'success' : 'default';
  };

  if (loading) {
    return (
      <GlassCard className="p-10 flex justify-center items-center">
        <div className="w-8 h-8 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></div>
      </GlassCard>
    );
  }

  return (
    <GlassCard neonColor="cyan" className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-white/5 border-b border-white/10">
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">User</th>
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Contact</th>
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Role</th>
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Joined</th>
              <th className="py-4 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {users.map((user) => (
              <tr 
                key={user.id} 
                className="hover:bg-neon-cyan/5 transition-colors duration-200 group"
              >
                {/* User Info */}
                <td className="py-4 px-6">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-neon-cyan to-neon-pink p-[1px]">
                      <div className="w-full h-full rounded-full bg-cyber-dark flex items-center justify-center">
                        <User className="w-5 h-5 text-gray-400 group-hover:text-neon-cyan transition-colors" />
                      </div>
                    </div>
                    <div>
                      <p className="text-white font-medium">{user.username || 'Unknown'}</p>
                      <p className="text-xs text-gray-500">ID: {user.id}</p>
                    </div>
                  </div>
                </td>

                {/* Contact */}
                <td className="py-4 px-6 text-sm text-gray-400 flex items-center space-x-1">
                  <Mail className="w-3 h-3" />
                  <span>{user.email || 'N/A'}</span>
                </td>

                {/* Role */}
                <td className="py-4 px-6">
                  <div className="flex items-center space-x-1">
                    <Shield className="w-3 h-3 text-neon-gold" />
                    <NeonBadge text={user.role || 'USER'} variant={getRoleVariant(user.role)} />
                  </div>
                </td>

                {/* Status */}
                <td className="py-4 px-6">
                  <NeonBadge text={user.status || 'PENDING'} variant={getStatusVariant(user.status)} />
                </td>

                {/* Joined Date */}
                <td className="py-4 px-6 text-xs text-gray-500">
                  {formatDate(user.date_joined)}
                </td>

                {/* Actions */}
                <td className="py-4 px-6">
                  <button className="text-gray-500 hover:text-neon-cyan transition-colors">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
};

export default UserList;