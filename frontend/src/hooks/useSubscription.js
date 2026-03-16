/**
 * src/hooks/useSubscription.js
 * Custom React hooks for subscription management
 */

import { useState, useEffect, useCallback } from 'react';
import { subscriptionAPI } from '../api/endpoints/subscription';

// ============================================================================
// GET SUBSCRIPTIONS HOOK
// ============================================================================

/**
 * Hook to fetch user subscriptions
 * @param {number} page - Page number
 * @param {string} status - Filter by status
 * @returns {object} - { subscriptions, loading, error, refetch }
 */
export const useSubscriptions = (page = 1, status = '') => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({});

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.getSubscriptions(page, status);
      if (data.results) {
        setSubscriptions(data.results);
        setPagination({
          count: data.count,
          next: data.next,
          previous: data.previous,
        });
      } else {
        setSubscriptions(data);
      }
    } catch (err) {
      setError(err.message);
      setSubscriptions([]);
    } finally {
      setLoading(false);
    }
  }, [page, status]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  return { subscriptions, loading, error, pagination, refetch: fetchSubscriptions };
};

// ============================================================================
// GET ACTIVE SUBSCRIPTION HOOK
// ============================================================================

/**
 * Hook to fetch active/current subscription
 * @returns {object} - { subscription, loading, error, refetch }
 */
export const useActiveSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchActiveSubscription = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.getActiveSubscription();
      setSubscription(data);
    } catch (err) {
      setError(err.message);
      setSubscription(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActiveSubscription();
  }, [fetchActiveSubscription]);

  return { subscription, loading, error, refetch: fetchActiveSubscription };
};

// ============================================================================
// GET SINGLE SUBSCRIPTION HOOK
// ============================================================================

/**
 * Hook to fetch single subscription detail
 * @param {string} id - Subscription ID
 * @returns {object} - { subscription, loading, error }
 */
export const useSubscription = (id) => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) return;

    const fetchSubscription = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await subscriptionAPI.getSubscription(id);
        setSubscription(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchSubscription();
  }, [id]);

  return { subscription, loading, error };
};

// ============================================================================
// SUBSCRIBE HOOK
// ============================================================================

/**
 * Hook to subscribe to a plan
 * @returns {object} - { subscribe, loading, error, success }
 */
export const useSubscribe = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const subscribe = useCallback(async (planId, options = {}) => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const data = await subscriptionAPI.subscribe(planId, options);
      setSuccess(true);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSuccess(false);
    setError(null);
  }, []);

  return { subscribe, loading, error, success, reset };
};

// ============================================================================
// CANCEL SUBSCRIPTION HOOK
// ============================================================================

/**
 * Hook to cancel subscription
 * @returns {object} - { cancel, loading, error }
 */
export const useCancelSubscription = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const cancel = useCallback(async (id, options = {}) => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.cancelSubscription(id, options);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { cancel, loading, error };
};

// ============================================================================
// CHANGE PLAN HOOK
// ============================================================================

/**
 * Hook to change subscription plan
 * @returns {object} - { changePlan, loading, error }
 */
export const useChangePlan = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const changePlan = useCallback(async (subscriptionId, newPlanId) => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.changePlan(subscriptionId, newPlanId);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { changePlan, loading, error };
};

// ============================================================================
// PAUSE SUBSCRIPTION HOOK
// ============================================================================

/**
 * Hook to pause subscription
 * @returns {object} - { pause, loading, error }
 */
export const usePauseSubscription = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const pause = useCallback(async (id, resumeAt = null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.pauseSubscription(id, resumeAt);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { pause, loading, error };
};

// ============================================================================
// RESUME SUBSCRIPTION HOOK
// ============================================================================

/**
 * Hook to resume paused subscription
 * @returns {object} - { resume, loading, error }
 */
export const useResumeSubscription = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const resume = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    try {
      const data = await subscriptionAPI.resumeSubscription(id);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { resume, loading, error };
};

// ============================================================================
// ALL SUBSCRIPTION OPERATIONS IN ONE HOOK
// ============================================================================

/**
 * Complete hook with all subscription operations
 * @returns {object} - All subscription functions and states
 */
export const useSubscriptionManager = () => {
  const subscriptions = useSubscriptions();
  const activeSubscription = useActiveSubscription();
  const subscribe = useSubscribe();
  const cancel = useCancelSubscription();
  const changePlan = useChangePlan();
  const pause = usePauseSubscription();
  const resume = useResumeSubscription();

  return {
    // Data
    subscriptions: subscriptions.subscriptions,
    activeSubscription: activeSubscription.subscription,
    
    // Loading states
    loading: subscriptions.loading || activeSubscription.loading,
    subscribeLoading: subscribe.loading,
    cancelLoading: cancel.loading,
    changePlanLoading: changePlan.loading,
    pauseLoading: pause.loading,
    resumeLoading: resume.loading,
    
    // Errors
    error: subscriptions.error || activeSubscription.error,
    subscribeError: subscribe.error,
    cancelError: cancel.error,
    changePlanError: changePlan.error,
    pauseError: pause.error,
    resumeError: resume.error,
    
    // Functions
    subscribe: subscribe.subscribe,
    cancel: cancel.cancel,
    changePlan: changePlan.changePlan,
    pause: pause.pause,
    resume: resume.resume,
    
    // Refresh
    refetch: subscriptions.refetch,
    refetchActive: activeSubscription.refetch,
  };
};
