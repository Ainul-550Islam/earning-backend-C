// src/components/wallet/WithdrawalTable.jsx
import { useState } from 'react';
import { useWithdrawalRequests } from '../../hooks/useWallet';

const STATUS_CONFIG = {
  pending:   { label: 'PENDING',   color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  glow: '0 0 8px rgba(245,158,11,0.4)'  },
  approved:  { label: 'APPROVED',  color: '#10b981', bg: 'rgba(16,185,129,0.1)',  glow: '0 0 8px rgba(16,185,129,0.4)'  },
  rejected:  { label: 'REJECTED',  color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   glow: '0 0 8px rgba(239,68,68,0.4)'   },
  cancelled: { label: 'CANCELLED', color: '#6b7280', bg: 'rgba(107,114,128,0.1)', glow: '0 0 8px rgba(107,114,128,0.3)' },
};

const METHOD_ICONS = {
  bkash:  { icon: '৳', color: '#e2136e' },
  nagad:  { icon: '৳', color: '#f26522' },
  rocket: { icon: '৳', color: '#8b2fc9' },
  bank:   { icon: '🏦', color: '#3b82f6' },
  default:{ icon: '💳', color: '#6b7280' },
};

// ── Reject Modal ─────────────────────────────────────────────────────────────
const RejectModal = ({ request, onConfirm, onClose }) => {
  const [note, setNote] = useState('');

  return (
    <div style={styles.modalOverlay}>
      <div style={styles.modalBox}>
        <div style={styles.modalHeader}>
          <span style={{ color: '#ef4444', fontSize: 13, letterSpacing: 2, fontFamily: 'monospace' }}>
            ⚠ REJECT WITHDRAWAL
          </span>
          <button onClick={onClose} style={styles.modalClose}>✕</button>
        </div>
        <p style={{ color: '#9ca3af', fontSize: 13, margin: '0 0 16px' }}>
          User: <span style={{ color: '#e2e8f0' }}>{request?.user_username || request?.user}</span>
          &nbsp;|&nbsp; Amount: <span style={{ color: '#ef4444' }}>৳{request?.amount}</span>
        </p>
        <textarea
          placeholder="Rejection reason (admin note)..."
          value={note}
          onChange={e => setNote(e.target.value)}
          style={styles.textarea}
        />
        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button onClick={onClose} style={styles.btnCancel}>Cancel</button>
          <button
            onClick={() => { onConfirm(request.id, note); onClose(); }}
            style={styles.btnReject}
            disabled={!note.trim()}
          >
            Confirm Reject
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function WithdrawalTable() {
  const [statusFilter, setStatusFilter] = useState('pending');
  const [rejectTarget, setRejectTarget] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [toast, setToast] = useState(null);

  const { requests, loading, error, setParams, refetch, approveWithdrawal, rejectWithdrawal } =
    useWithdrawalRequests({ status: statusFilter });

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleFilterChange = (status) => {
    setStatusFilter(status);
    setParams({ status });
  };

  const handleApprove = async (id) => {
    setActionLoading(id + '_approve');
    try {
      await approveWithdrawal(id);
      showToast('Withdrawal approved!', 'success');
    } catch {
      showToast('Approve failed!', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id, note) => {
    setActionLoading(id + '_reject');
    try {
      await rejectWithdrawal(id, note);
      showToast('Withdrawal rejected.', 'error');
    } catch {
      showToast('Reject failed!', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const methodConfig = (method) =>
    METHOD_ICONS[method?.toLowerCase()] || METHOD_ICONS.default;

  return (
    <div style={styles.wrapper}>
      {/* Toast */}
      {toast && (
        <div style={{ ...styles.toast, borderColor: toast.type === 'success' ? '#10b981' : '#ef4444' }}>
          <span style={{ color: toast.type === 'success' ? '#10b981' : '#ef4444' }}>
            {toast.type === 'success' ? '✓' : '✕'}
          </span>
          &nbsp;{toast.msg}
        </div>
      )}

      {/* Header */}
      <div style={styles.header}>
        <div>
          <div style={styles.title}>WITHDRAWAL REQUESTS</div>
          <div style={styles.subtitle}>Manage user withdrawal queue</div>
        </div>
        <button onClick={refetch} style={styles.refreshBtn}>
          ↻ Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div style={styles.filterRow}>
        {['pending', 'approved', 'rejected', 'cancelled'].map(s => (
          <button
            key={s}
            onClick={() => handleFilterChange(s)}
            style={{
              ...styles.filterTab,
              ...(statusFilter === s ? {
                color: STATUS_CONFIG[s].color,
                borderColor: STATUS_CONFIG[s].color,
                background: STATUS_CONFIG[s].bg,
                boxShadow: STATUS_CONFIG[s].glow,
              } : {}),
            }}
          >
            {STATUS_CONFIG[s].label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={styles.tableWrapper}>
        {loading ? (
          <div style={styles.centerMsg}>
            <div style={styles.spinner} />
            <span style={{ color: '#6b7280', fontSize: 13 }}>Loading...</span>
          </div>
        ) : error ? (
          <div style={styles.centerMsg}>
            <span style={{ color: '#ef4444' }}>⚠ {error}</span>
          </div>
        ) : requests.length === 0 ? (
          <div style={styles.centerMsg}>
            <span style={{ color: '#4b5563', fontSize: 13 }}>No {statusFilter} requests found.</span>
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                {['User', 'Amount', 'Method / Account', 'Status', 'Date', 'Actions'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {requests.map((req, i) => {
                const mc = methodConfig(req.method);
                const sc = STATUS_CONFIG[req.status] || STATUS_CONFIG.pending;
                const isActing = actionLoading?.startsWith(String(req.id));

                return (
                  <tr
                    key={req.id}
                    style={{
                      ...styles.tr,
                      animationDelay: `${i * 40}ms`,
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* User */}
                    <td style={styles.td}>
                      <div style={styles.userCell}>
                        <div style={styles.avatar}>
                          {(req.user_username || req.user || 'U')[0].toUpperCase()}
                        </div>
                        <div>
                          <div style={{ color: '#e2e8f0', fontSize: 13 }}>
                            {req.user_username || req.user}
                          </div>
                          <div style={{ color: '#4b5563', fontSize: 11 }}>ID #{req.id}</div>
                        </div>
                      </div>
                    </td>

                    {/* Amount */}
                    <td style={styles.td}>
                      <div style={{ color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'monospace' }}>
                        ৳{parseFloat(req.amount).toLocaleString()}
                      </div>
                      {req.fee > 0 && (
                        <div style={{ color: '#6b7280', fontSize: 11 }}>
                          Fee: ৳{req.fee}
                        </div>
                      )}
                    </td>

                    {/* Method */}
                    <td style={styles.td}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ color: mc.color, fontSize: 16 }}>{mc.icon}</span>
                        <div>
                          <div style={{ color: '#cbd5e1', fontSize: 12, textTransform: 'capitalize' }}>
                            {req.method}
                          </div>
                          <div style={{ color: '#4b5563', fontSize: 11, fontFamily: 'monospace' }}>
                            {req.account_number}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Status */}
                    <td style={styles.td}>
                      <span style={{
                        ...styles.badge,
                        color: sc.color,
                        background: sc.bg,
                        boxShadow: sc.glow,
                      }}>
                        {sc.label}
                      </span>
                    </td>

                    {/* Date */}
                    <td style={styles.td}>
                      <div style={{ color: '#6b7280', fontSize: 12 }}>
                        {new Date(req.created_at).toLocaleDateString('en-GB', {
                          day: '2-digit', month: 'short', year: 'numeric'
                        })}
                      </div>
                      <div style={{ color: '#374151', fontSize: 11 }}>
                        {new Date(req.created_at).toLocaleTimeString('en-GB', {
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </div>
                    </td>

                    {/* Actions */}
                    <td style={styles.td}>
                      {req.status === 'pending' ? (
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            onClick={() => handleApprove(req.id)}
                            disabled={isActing}
                            style={{ ...styles.actionBtn, ...styles.approveBtn }}
                          >
                            {actionLoading === req.id + '_approve' ? '...' : '✓ Approve'}
                          </button>
                          <button
                            onClick={() => setRejectTarget(req)}
                            disabled={isActing}
                            style={{ ...styles.actionBtn, ...styles.rejectBtn }}
                          >
                            ✕ Reject
                          </button>
                        </div>
                      ) : (
                        <span style={{ color: '#374151', fontSize: 12 }}>
                          {req.admin_note ? `Note: ${req.admin_note.slice(0, 20)}...` : '—'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Reject Modal */}
      {rejectTarget && (
        <RejectModal
          request={rejectTarget}
          onConfirm={handleReject}
          onClose={() => setRejectTarget(null)}
        />
      )}

      <style>{`
        @keyframes fadeInRow {
          from { opacity: 0; transform: translateX(-8px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        tbody tr {
          animation: fadeInRow 0.25s ease both;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = {
  wrapper: {
    background: '#0d1117',
    border: '1px solid #1f2937',
    borderRadius: 12,
    padding: 24,
    position: 'relative',
    fontFamily: "'DM Sans', sans-serif",
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
  },
  title: {
    color: '#e2e8f0',
    fontSize: 14,
    fontWeight: 700,
    letterSpacing: 3,
    fontFamily: 'monospace',
  },
  subtitle: {
    color: '#4b5563',
    fontSize: 12,
    marginTop: 4,
  },
  refreshBtn: {
    background: 'transparent',
    border: '1px solid #1f2937',
    borderRadius: 6,
    color: '#6b7280',
    padding: '6px 14px',
    fontSize: 12,
    cursor: 'pointer',
    letterSpacing: 1,
    transition: 'all 0.2s',
  },
  filterRow: {
    display: 'flex',
    gap: 8,
    marginBottom: 20,
    flexWrap: 'wrap',
  },
  filterTab: {
    background: 'transparent',
    border: '1px solid #1f2937',
    borderRadius: 6,
    color: '#4b5563',
    padding: '6px 16px',
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 2,
    cursor: 'pointer',
    fontFamily: 'monospace',
    transition: 'all 0.2s',
  },
  tableWrapper: {
    overflowX: 'auto',
    minHeight: 120,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    color: '#374151',
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 2,
    textAlign: 'left',
    padding: '10px 14px',
    borderBottom: '1px solid #1f2937',
    textTransform: 'uppercase',
    fontFamily: 'monospace',
  },
  tr: {
    borderBottom: '1px solid #111827',
    transition: 'background 0.15s',
  },
  td: {
    padding: '14px',
    verticalAlign: 'middle',
  },
  userCell: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: 'linear-gradient(135deg, #1e3a5f, #0f2744)',
    border: '1px solid #1e40af',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#60a5fa',
    fontSize: 13,
    fontWeight: 700,
    flexShrink: 0,
  },
  badge: {
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 1.5,
    fontFamily: 'monospace',
  },
  actionBtn: {
    border: 'none',
    borderRadius: 6,
    padding: '6px 12px',
    fontSize: 11,
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: 1,
    transition: 'all 0.2s',
  },
  approveBtn: {
    background: 'rgba(16,185,129,0.1)',
    color: '#10b981',
    border: '1px solid rgba(16,185,129,0.3)',
  },
  rejectBtn: {
    background: 'rgba(239,68,68,0.1)',
    color: '#ef4444',
    border: '1px solid rgba(239,68,68,0.3)',
  },
  centerMsg: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: '40px 0',
  },
  spinner: {
    width: 24,
    height: 24,
    border: '2px solid #1f2937',
    borderTop: '2px solid #3b82f6',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  // Modal
  modalOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    backdropFilter: 'blur(4px)',
  },
  modalBox: {
    background: '#0d1117',
    border: '1px solid #ef4444',
    borderRadius: 12,
    padding: 24,
    width: 420,
    boxShadow: '0 0 30px rgba(239,68,68,0.15)',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalClose: {
    background: 'transparent',
    border: 'none',
    color: '#6b7280',
    fontSize: 16,
    cursor: 'pointer',
  },
  textarea: {
    width: '100%',
    background: '#111827',
    border: '1px solid #1f2937',
    borderRadius: 8,
    color: '#e2e8f0',
    padding: 12,
    fontSize: 13,
    resize: 'vertical',
    minHeight: 80,
    outline: 'none',
    boxSizing: 'border-box',
  },
  btnCancel: {
    flex: 1,
    background: 'transparent',
    border: '1px solid #1f2937',
    borderRadius: 8,
    color: '#6b7280',
    padding: '10px',
    cursor: 'pointer',
    fontSize: 13,
  },
  btnReject: {
    flex: 1,
    background: 'rgba(239,68,68,0.15)',
    border: '1px solid #ef4444',
    borderRadius: 8,
    color: '#ef4444',
    padding: '10px',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 700,
  },
  toast: {
    position: 'fixed',
    top: 24,
    right: 24,
    background: '#0d1117',
    border: '1px solid',
    borderRadius: 8,
    padding: '12px 20px',
    color: '#e2e8f0',
    fontSize: 13,
    zIndex: 2000,
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
  },
};


