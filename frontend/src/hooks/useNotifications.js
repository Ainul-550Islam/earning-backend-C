// src/hooks/useNotifications.js
import { useState, useEffect, useCallback, useRef } from 'react';
import notificationsAPI from '../api/endpoints/notifications';


// ─── 1. User Notifications (Main Bell/Inbox) ──────────────────────────────
export const useNotifications = (initialParams = {}) => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const [listRes, countRes] = await Promise.all([
        notificationsAPI.getAll(params),
        notificationsAPI.getUnreadCount(),
      ]);
      const data = listRes.data; setNotifications(Array.isArray(data) ? data : Array.isArray(data.results) ? data.results : []);
      setUnreadCount(countRes.data.count ?? countRes.data.unread_count ?? 0);
    } catch (err) {
      setError(err.response?.data?.message || 'Notifications load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchNotifications(); }, [fetchNotifications]);

  const markAsRead = async (id) => {
    await notificationsAPI.markAsRead(id);
    setNotifications(prev =>
      prev.map(n => n.id === id ? { ...n, is_read: true, status: 'read' } : n)
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  const markAllAsRead = async () => {
    await notificationsAPI.markAllAsRead();
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true, status: 'read' })));
    setUnreadCount(0);
  };

  const archiveNotification = async (id, reason = '') => {
    await notificationsAPI.archive(id, reason);
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const deleteNotification = async (id) => {
    await notificationsAPI.delete(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const pinNotification = async (id) => {
    await notificationsAPI.pin(id);
    setNotifications(prev =>
      prev.map(n => n.id === id ? { ...n, is_pinned: true } : n)
    );
  };

  return {
    notifications, unreadCount, loading, error,
    setParams, refetch: fetchNotifications,
    markAsRead, markAllAsRead,
    archiveNotification, deleteNotification, pinNotification,
    unreadNotifications: notifications.filter(n => !n.is_read),
    pinnedNotifications: notifications.filter(n => n.is_pinned),
    urgentNotifications: notifications.filter(n =>
      ['urgent', 'critical'].includes(n.priority) && !n.is_read
    ),
  };
};


// ─── 2. Notification Stats (Admin Dashboard Card) ─────────────────────────
export const useNotificationStats = (dateRange = {}) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getStats(dateRange);
      setStats(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Stats load failed');
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(dateRange)]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return {
    stats, loading, error, refetch: fetchStats,
    total: stats?.total || 0,
    unread: stats?.unread || 0,
    delivered: stats?.delivered || 0,
    failed: stats?.failed || 0,
    byType: stats?.by_type || [],
    byChannel: stats?.by_channel || [],
  };
};


// ─── 3. Notification Templates ────────────────────────────────────────────
export const useNotificationTemplates = (initialParams = {}) => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getTemplates(params);
      setTemplates(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Templates load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const createTemplate = async (data) => {
    setSaving(true);
    try {
      const res = await notificationsAPI.createTemplate(data);
      setTemplates(prev => [res.data, ...prev]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateTemplate = async (id, data) => {
    setSaving(true);
    try {
      const res = await notificationsAPI.updateTemplate(id, data);
      setTemplates(prev => prev.map(t => t.id === id ? res.data : t));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteTemplate = async (id) => {
    await notificationsAPI.deleteTemplate(id);
    setTemplates(prev => prev.filter(t => t.id !== id));
  };

  const previewTemplate = async (id, context = {}) => {
    const res = await notificationsAPI.previewTemplate(id, context);
    return res.data;
  };

  return {
    templates, loading, saving, error,
    setParams, refetch: fetchTemplates,
    createTemplate, updateTemplate, deleteTemplate, previewTemplate,
    activeTemplates: templates.filter(t => t.is_active),
  };
};


// ─── 4. User Notification Preferences ────────────────────────────────────
export const useNotificationPreferences = (userId = null) => {
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const fetchPreferences = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getPreferences(userId);
      setPreferences(res.data.results?.[0] || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Preferences load failed');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { fetchPreferences(); }, [fetchPreferences]);

  const updatePreferences = async (data) => {
    setSaving(true);
    try {
      const res = await notificationsAPI.updatePreferences(data);
      setPreferences(res.data);
      return res.data;
    } finally { setSaving(false); }
  };

  const toggleDND = async (until = null) => {
    return updatePreferences({
      do_not_disturb: !preferences?.do_not_disturb,
      do_not_disturb_until: until,
    });
  };

  return {
    preferences, loading, saving, error,
    refetch: fetchPreferences,
    updatePreferences, toggleDND,
    isDND: preferences?.do_not_disturb || false,
  };
};


// ─── 5. Notification Campaigns (Admin) ───────────────────────────────────
export const useNotificationCampaigns = (initialParams = {}) => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getCampaigns(params);
      setCampaigns(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Campaigns load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const createCampaign = async (data) => {
    const res = await notificationsAPI.createCampaign(data);
    setCampaigns(prev => [res.data, ...prev]);
    return res.data;
  };

  const startCampaign = async (id) => {
    await notificationsAPI.startCampaign(id);
    setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status: 'running' } : c));
  };

  const pauseCampaign = async (id) => {
    await notificationsAPI.pauseCampaign(id);
    setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status: 'paused' } : c));
  };

  const cancelCampaign = async (id) => {
    await notificationsAPI.cancelCampaign(id);
    setCampaigns(prev => prev.map(c => c.id === id ? { ...c, status: 'cancelled' } : c));
  };

  return {
    campaigns, loading, error,
    setParams, refetch: fetchCampaigns,
    createCampaign, startCampaign, pauseCampaign, cancelCampaign,
    activeCampaigns: campaigns.filter(c => c.status === 'running'),
    draftCampaigns: campaigns.filter(c => c.status === 'draft'),
    completedCampaigns: campaigns.filter(c => c.status === 'completed'),
  };
};


// ─── 6. Notices/Announcements (Admin) ────────────────────────────────────
export const useNotices = (initialParams = {}) => {
  const [notices, setNotices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchNotices = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getNotices(params);
      setNotices(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Notices load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchNotices(); }, [fetchNotices]);

  const createNotice = async (data) => {
    setSaving(true);
    try {
      const res = await notificationsAPI.createNotice(data);
      setNotices(prev => [res.data, ...prev]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateNotice = async (id, data) => {
    setSaving(true);
    try {
      const res = await notificationsAPI.updateNotice(id, data);
      setNotices(prev => prev.map(n => n.id === id ? res.data : n));
      return res.data;
    } finally { setSaving(false); }
  };

  const publishNotice = async (id) => {
    await notificationsAPI.publishNotice(id);
    setNotices(prev =>
      prev.map(n => n.id === id ? { ...n, is_published: true, status: 'published' } : n)
    );
  };

  const unpublishNotice = async (id) => {
    await notificationsAPI.unpublishNotice(id);
    setNotices(prev =>
      prev.map(n => n.id === id ? { ...n, is_published: false, status: 'draft' } : n)
    );
  };

  const archiveNotice = async (id) => {
    await notificationsAPI.archiveNotice(id);
    setNotices(prev => prev.map(n => n.id === id ? { ...n, status: 'archived' } : n));
  };

  const deleteNotice = async (id) => {
    await notificationsAPI.deleteNotice(id);
    setNotices(prev => prev.filter(n => n.id !== id));
  };

  return {
    notices, loading, saving, error,
    setParams, refetch: fetchNotices,
    createNotice, updateNotice,
    publishNotice, unpublishNotice, archiveNotice, deleteNotice,
    publishedNotices: notices.filter(n => n.is_published),
    pinnedNotices: notices.filter(n => n.is_pinned),
    urgentNotices: notices.filter(n => ['urgent', 'high'].includes(n.priority) && n.is_published),
    draftNotices: notices.filter(n => n.status === 'draft'),
  };
};


// ─── 7. Analytics ─────────────────────────────────────────────────────────
export const useNotificationAnalytics = (initialParams = {}) => {
  const [analytics, setAnalytics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      const res = await notificationsAPI.getAnalytics(params);
      setAnalytics(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Analytics load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const latest = analytics[0] || null;

  return {
    analytics, latest, loading, error,
    setParams, refetch: fetchAnalytics,
    totalSent: analytics.reduce((s, d) => s + (d.total_sent || 0), 0),
    totalRead: analytics.reduce((s, d) => s + (d.total_read || 0), 0),
    avgDeliveryRate: analytics.length
      ? (analytics.reduce((s, d) => s + (d.delivery_rate || 0), 0) / analytics.length).toFixed(1)
      : 0,
    avgOpenRate: analytics.length
      ? (analytics.reduce((s, d) => s + (d.open_rate || 0), 0) / analytics.length).toFixed(1)
      : 0,
  };
};


// ─── 8. Send Notification (Admin action) ─────────────────────────────────
export const useSendNotification = () => {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [lastSent, setLastSent] = useState(null);

  const send = async (data) => {
    setSending(true);
    setError(null);
    try {
      const res = await notificationsAPI.send(data);
      setLastSent(res.data);
      return res.data;
    } catch (err) {
      setError(err.response?.data || 'Failed to send');
      throw err;
    } finally {
      setSending(false);
    }
  };

  const sendBulk = async (data) => {
    setSending(true);
    setError(null);
    try {
      const res = await notificationsAPI.sendBulk(data);
      setLastSent(res.data);
      return res.data;
    } catch (err) {
      setError(err.response?.data || 'Failed to send bulk');
      throw err;
    } finally {
      setSending(false);
    }
  };

  return { send, sendBulk, sending, error, lastSent };
};


// ─── 9. Real-time Unread Count Polling ───────────────────────────────────
export const useNotificationPolling = (intervalMs = 30000) => {
  const [unreadCount, setUnreadCount] = useState(0);
  const intervalRef = useRef(null);

  const fetchCount = useCallback(async () => {
    try {
      const res = await notificationsAPI.getUnreadCount();
      setUnreadCount(res.data.count ?? res.data.unread_count ?? 0);
    } catch {}
  }, []);

  useEffect(() => {
    fetchCount();
    intervalRef.current = setInterval(fetchCount, intervalMs);
    return () => clearInterval(intervalRef.current);
  }, [fetchCount, intervalMs]);

  return { unreadCount, refetch: fetchCount };
};