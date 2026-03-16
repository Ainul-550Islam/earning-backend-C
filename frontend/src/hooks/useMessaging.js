// src/hooks/useMessaging.js
import { useState, useEffect, useCallback, useRef } from 'react';
import { chatApi, inboxApi, supportApi, broadcastApi } from '../api/endpoints/Messaging';
import toast from 'react-hot-toast';

// ─── useChats ─────────────────────────────────────────────────────────────────
export function useChats() {
  const [chats, setChats]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const fetchChats = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const { data } = await chatApi.list(params);
      setChats(data.results ?? data);
    } catch (e) {
      setError(e);
      toast.error('Failed to load chats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchChats(); }, [fetchChats]);

  const createDirect = useCallback(async (userId) => {
    try {
      const { data } = await chatApi.createDirect(userId);
      setChats(prev => {
        const exists = prev.find(c => c.id === data.id);
        return exists ? prev : [data, ...prev];
      });
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to create chat');
      throw e;
    }
  }, []);

  const createGroup = useCallback(async (name, memberIds) => {
    try {
      const { data } = await chatApi.createGroup(name, memberIds);
      setChats(prev => [data, ...prev]);
      toast.success('Group chat created');
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to create group');
      throw e;
    }
  }, []);

  return { chats, loading, error, fetchChats, createDirect, createGroup };
}

// ─── useChatMessages ──────────────────────────────────────────────────────────
export function useChatMessages(chatId) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [hasMore, setHasMore]   = useState(true);

  const fetchMessages = useCallback(async ({ before_id, limit = 30 } = {}) => {
    if (!chatId) return;
    setLoading(true);
    try {
      const { data } = await chatApi.getMessages(chatId, { limit, before_id });
      const results = data.results ?? data;
      if (before_id) {
        setMessages(prev => [...results, ...prev]);
      } else {
        setMessages(results);
      }
      setHasMore(results.length === limit);
    } catch (e) {
      toast.error('Failed to load messages');
    } finally {
      setLoading(false);
    }
  }, [chatId]);

  useEffect(() => {
    setMessages([]);
    fetchMessages();
  }, [chatId, fetchMessages]);

  const sendMessage = useCallback(async (payload) => {
    try {
      const { data } = await chatApi.sendMessage(chatId, payload);
      setMessages(prev => [...prev, data]);
      return data;
    } catch (e) {
      const msg = e?.detail || e?.content?.[0] || 'Failed to send message';
      toast.error(msg);
      throw e;
    }
  }, [chatId]);

  const deleteMessage = useCallback(async (messageId) => {
    try {
      const { data } = await chatApi.deleteMessage(chatId, messageId);
      // Replace with tombstone returned by backend
      setMessages(prev => prev.map(m => m.id === messageId ? data : m));
      toast.success('Message deleted');
    } catch (e) {
      toast.error(e?.detail || 'Failed to delete message');
    }
  }, [chatId]);

  const loadMore = useCallback(() => {
    if (!messages.length || !hasMore || loading) return;
    fetchMessages({ before_id: messages[0].id });
  }, [messages, hasMore, loading, fetchMessages]);

  return { messages, setMessages, loading, hasMore, sendMessage, deleteMessage, loadMore };
}

// ─── useInbox ─────────────────────────────────────────────────────────────────
export function useInbox() {
  const [items, setItems]           = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading]       = useState(true);

  const fetchInbox = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const [inboxRes, countRes] = await Promise.all([
        inboxApi.list(params),
        inboxApi.unreadCount(),
      ]);
      setItems(inboxRes.data.results ?? inboxRes.data);
      setUnreadCount(countRes.data.unread_count);
    } catch {
      toast.error('Failed to load inbox');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchInbox(); }, [fetchInbox]);

  const markRead = useCallback(async (itemIds) => {
    try {
      await inboxApi.markRead(itemIds);
      setItems(prev => prev.map(item =>
        itemIds.includes(item.id) ? { ...item, is_read: true } : item
      ));
      setUnreadCount(prev => Math.max(0, prev - itemIds.length));
    } catch {
      toast.error('Failed to mark as read');
    }
  }, []);

  const archive = useCallback(async (id) => {
    try {
      await inboxApi.archive(id);
      setItems(prev => prev.filter(item => item.id !== id));
      toast.success('Archived');
    } catch {
      toast.error('Failed to archive');
    }
  }, []);

  return { items, unreadCount, loading, fetchInbox, markRead, archive };
}

// ─── useSupportThreads ────────────────────────────────────────────────────────
export function useSupportThreads() {
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchThreads = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const { data } = await supportApi.list(params);
      setThreads(data.results ?? data);
    } catch {
      toast.error('Failed to load support threads');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchThreads(); }, [fetchThreads]);

  const createThread = useCallback(async (subject, initial_message, priority = 'NORMAL') => {
    try {
      const { data } = await supportApi.create(subject, initial_message, priority);
      setThreads(prev => [data, ...prev]);
      toast.success('Support ticket created');
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to create ticket');
      throw e;
    }
  }, []);

  const replyThread = useCallback(async (threadId, content) => {
    try {
      const { data } = await supportApi.reply(threadId, content);
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to send reply');
      throw e;
    }
  }, []);

  const transitionThread = useCallback(async (threadId, newStatus) => {
    try {
      const { data } = await supportApi.transition(threadId, newStatus);
      setThreads(prev => prev.map(t => t.id === threadId ? data : t));
      toast.success(`Status → ${newStatus}`);
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to update status');
    }
  }, []);

  return { threads, loading, fetchThreads, createThread, replyThread, transitionThread };
}

// ─── useBroadcasts ────────────────────────────────────────────────────────────
export function useBroadcasts() {
  const [broadcasts, setBroadcasts] = useState([]);
  const [loading, setLoading]       = useState(true);

  const fetchBroadcasts = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const { data } = await broadcastApi.list(params);
      setBroadcasts(data.results ?? data);
    } catch {
      toast.error('Failed to load broadcasts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchBroadcasts(); }, [fetchBroadcasts]);

  const createBroadcast = useCallback(async (payload) => {
    try {
      const { data } = await broadcastApi.create(payload);
      setBroadcasts(prev => [data, ...prev]);
      toast.success('Broadcast created');
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Failed to create broadcast');
      throw e;
    }
  }, []);

  const sendBroadcast = useCallback(async (id, async_ = false) => {
    try {
      const fn = async_ ? broadcastApi.sendAsync : broadcastApi.send;
      const { data } = await fn(id);
      if (!async_) {
        setBroadcasts(prev => prev.map(b => b.id === id ? { ...b, status: 'SENT' } : b));
      }
      toast.success(async_ ? 'Queued for delivery' : 'Broadcast sent!');
      return data;
    } catch (e) {
      toast.error(e?.detail || 'Send failed');
    }
  }, []);

  const deleteBroadcast = useCallback(async (id) => {
    try {
      await broadcastApi.delete(id);
      setBroadcasts(prev => prev.filter(b => b.id !== id));
      toast.success('Broadcast deleted');
    } catch (e) {
      toast.error(e?.detail || 'Delete failed');
    }
  }, []);

  return { broadcasts, loading, fetchBroadcasts, createBroadcast, sendBroadcast, deleteBroadcast };
}