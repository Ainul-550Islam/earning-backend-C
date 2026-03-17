/**
 * src/api/endpoints/subscription.js
 * Complete Subscription API endpoints
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api');

// ============================================================================
// SUBSCRIPTION ENDPOINTS
// ============================================================================

export const subscriptionEndpoints = {
  // List all subscriptions
  list: () => `${API_BASE_URL}/subscriptions/`,
  
  // Get single subscription
  detail: (id) => `${API_BASE_URL}/subscriptions/${id}/`,
  
  // Get current active subscription
  active: () => `${API_BASE_URL}/subscriptions/me/`,
  
  // Subscribe to a plan
  subscribe: () => `${API_BASE_URL}/subscriptions/subscribe/`,
  
  // Cancel subscription
  cancel: (id) => `${API_BASE_URL}/subscriptions/${id}/cancel/`,
  
  // Change plan
  changePlan: (id) => `${API_BASE_URL}/subscriptions/${id}/change-plan/`,
  
  // Pause subscription
  pause: (id) => `${API_BASE_URL}/subscriptions/${id}/pause/`,
  
  // Resume subscription
  resume: (id) => `${API_BASE_URL}/subscriptions/${id}/resume/`,
};

// ============================================================================
// SUBSCRIPTION API SERVICE
// ============================================================================

export const getToken = () => localStorage.getItem('authToken');

const fetchWithAuth = async (url, options = {}) => {
  const token = getToken();
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  if (token) {
    defaultHeaders['Authorization'] = `Token ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}`,
    }));
    throw new Error(error.detail || 'API Error');
  }

  return response.json();
};

// ============================================================================
// SUBSCRIPTION API CALLS
// ============================================================================

export const subscriptionAPI = {
  /**
   * Get all user subscriptions (paginated)
   * @param {number} page - Page number
   * @param {string} status - Filter by status (optional)
   * @returns {Promise}
   */
  getSubscriptions: async (page = 1, status = '') => {
    const params = new URLSearchParams({ page });
    if (status) params.append('status', status);
    
    return fetchWithAuth(`${subscriptionEndpoints.list()}?${params}`);
  },

  /**
   * Get active/current subscription
   * @returns {Promise}
   */
  getActiveSubscription: async () => {
    try {
      return await fetchWithAuth(subscriptionEndpoints.active());
    } catch (error) {
      // No active subscription
      return null;
    }
  },

  /**
   * Get single subscription detail
   * @param {string} id - Subscription ID
   * @returns {Promise}
   */
  getSubscription: async (id) => {
    return fetchWithAuth(subscriptionEndpoints.detail(id));
  },

  /**
   * Subscribe to a plan
   * @param {string} planId - Plan ID to subscribe to
   * @param {object} options - Additional options
   * @returns {Promise}
   */
  subscribe: async (planId, options = {}) => {
    return fetchWithAuth(subscriptionEndpoints.subscribe(), {
      method: 'POST',
      body: JSON.stringify({
        plan_id: planId,
        payment_method: options.paymentMethod || null,
        coupon_code: options.couponCode || null,
      }),
    });
  },

  /**
   * Cancel subscription
   * @param {string} id - Subscription ID
   * @param {object} options - Cancellation options
   * @returns {Promise}
   */
  cancelSubscription: async (id, options = {}) => {
    return fetchWithAuth(subscriptionEndpoints.cancel(id), {
      method: 'POST',
      body: JSON.stringify({
        reason: options.reason || '',
        comment: options.comment || '',
        at_period_end: options.atPeriodEnd !== false,
      }),
    });
  },

  /**
   * Change subscription plan
   * @param {string} id - Subscription ID
   * @param {string} newPlanId - New plan ID
   * @returns {Promise}
   */
  changePlan: async (id, newPlanId) => {
    return fetchWithAuth(subscriptionEndpoints.changePlan(id), {
      method: 'POST',
      body: JSON.stringify({
        new_plan_id: newPlanId,
      }),
    });
  },

  /**
   * Pause subscription
   * @param {string} id - Subscription ID
   * @param {string} resumeAt - Resume date (optional)
   * @returns {Promise}
   */
  pauseSubscription: async (id, resumeAt = null) => {
    return fetchWithAuth(subscriptionEndpoints.pause(id), {
      method: 'POST',
      body: JSON.stringify({
        resume_at: resumeAt,
      }),
    });
  },

  /**
   * Resume paused subscription
   * @param {string} id - Subscription ID
   * @returns {Promise}
   */
  resumeSubscription: async (id) => {
    return fetchWithAuth(subscriptionEndpoints.resume(id), {
      method: 'POST',
    });
  },
};

// ============================================================================
// SUBSCRIPTION STATUS HELPERS
// ============================================================================

export const SubscriptionStatus = {
  PENDING: 'pending',
  ACTIVE: 'active',
  TRIALING: 'trialing',
  PAUSED: 'paused',
  CANCELLED: 'cancelled',
  EXPIRED: 'expired',
  PAST_DUE: 'past_due',
};

export const getStatusColor = (status) => {
  const colors = {
    active: '#10b981',
    trialing: '#8b5cf6',
    paused: '#f59e0b',
    cancelled: '#ef4444',
    expired: '#6b7280',
    past_due: '#dc2626',
    pending: '#3b82f6',
  };
  return colors[status] || '#6b7280';
};

export const getStatusLabel = (status) => {
  const labels = {
    active: 'Active',
    trialing: 'Trial',
    paused: 'Paused',
    cancelled: 'Cancelled',
    expired: 'Expired',
    past_due: 'Past Due',
    pending: 'Pending',
  };
  return labels[status] || status;
};
