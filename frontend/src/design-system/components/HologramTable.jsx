// src/design-system/components/HologramTable.jsx
import React from 'react';
import PropTypes from 'prop-types';

const HologramTable = ({ columns, data, loading }) => {
  
  if (loading) {
    return (
      <div className="w-full h-64 flex items-center justify-center bg-cyber-panel/30 rounded-lg border border-white/5">
        <div className="flex flex-col items-center space-y-2">
          <div className="w-8 h-8 border-2 border-t-transparent border-neon-cyan rounded-full animate-spin"></div>
          <span className="text-gray-500 text-sm">Scanning Data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto custom-scrollbar relative border border-white/10 rounded-lg">
      {/* Hologram Scan Line Effect */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
        <div className="w-full h-1 bg-gradient-to-r from-transparent via-neon-cyan/20 to-transparent animate-pulse-slow absolute top-0"></div>
      </div>

      <table className="w-full text-left border-collapse relative z-10">
        <thead>
          <tr className="bg-white/5 border-b border-white/10">
            {columns.map((col) => (
              <th 
                key={col.key} 
                className="py-4 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {data.map((row, rowIndex) => (
            <tr 
              key={row.id || rowIndex} 
              className="hover:bg-neon-cyan/5 transition-colors duration-200 group"
            >
              {columns.map((col) => (
                <td key={col.key} className="py-4 px-6 text-sm text-gray-300 whitespace-nowrap">
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

HologramTable.propTypes = {
  columns: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    render: PropTypes.func
  })).isRequired,
  data: PropTypes.array.isRequired,
  loading: PropTypes.bool,
};

export default HologramTable;