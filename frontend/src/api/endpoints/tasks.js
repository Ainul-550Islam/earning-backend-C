// src/api/endpoints/tasks.js
import client from '../client';

const tasksAPI = {

  // ─── MASTER TASKS ──────────────────────────────────────

  // সব tasks list (filter সহ)
  getTasks: (params = {}) =>
    client.get('/tasks/', { params }),
  // params: { system_type, category, is_active, is_featured, search, page }

  // একটি task detail
  getTaskDetail: (taskId) =>
    client.get(`/tasks/${taskId}/`),

  // Task create
  createTask: (data) =>
    client.post('/tasks/', data),

  // Task update
  updateTask: (taskId, data) =>
    client.patch(`/tasks/${taskId}/`, data),

  // Task delete
  deleteTask: (taskId) =>
    client.delete(`/tasks/${taskId}/`),

  // Bulk activate
  bulkActivate: (taskIds) =>
    client.post('/tasks/bulk-activate/', { task_ids: taskIds }),

  // Bulk deactivate
  bulkDeactivate: (taskIds) =>
    client.post('/tasks/bulk-deactivate/', { task_ids: taskIds }),

  // Dashboard stats (active tasks, total completions etc.)
  getTaskDashboardStats: () =>
    client.get('/tasks/dashboard-stats/'),


  // ─── TASK COMPLETIONS ─────────────────────────────────

  // সব completions list
  getCompletions: (params = {}) =>
    client.get('/tasks/completions/', { params }),
  // params: { status, task, user, page }

  // একটি completion detail
  getCompletionDetail: (completionId) =>
    client.get(`/tasks/completions/${completionId}/`),

  // Completion verify (admin)
  verifyCompletion: (completionId) =>
    client.post(`/tasks/completions/${completionId}/verify/`),

  // User এর completions
  getUserCompletions: (userId, params = {}) =>
    client.get(`/tasks/completions/`, { params: { user: userId, ...params } }),


  // ─── ADMIN LEDGER ──────────────────────────────────────

  // Admin profit ledger list
  getAdminLedger: (params = {}) =>
    client.get('/tasks/admin-ledger/', { params }),
  // params: { source_type, page }

  // Admin profit summary
  getAdminProfitSummary: (days = 30) =>
    client.get('/tasks/admin-ledger/profit-summary/', { params: { days } }),

  // Daily profit (chart data)
  getDailyProfit: (days = 30) =>
    client.get('/tasks/admin-ledger/daily-profit/', { params: { days } }),

  // Profit by source
  getProfitBySource: (days = 30) =>
    client.get('/tasks/admin-ledger/by-source/', { params: { days } }),

};

export default tasksAPI;