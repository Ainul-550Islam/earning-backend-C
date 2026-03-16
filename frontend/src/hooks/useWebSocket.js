// src/hooks/useWebSocket.js
// ═══════════════════════════════════════════════════════════════════
// BULLETPROOF WebSocket Hook — Defensive Coding Edition
// Django Channels: ChatConsumer + SupportConsumer
//
// Defenses:
//   ✅ Stable connect() — never re-creates (empty deps)
//   ✅ Callback refs   — onMessage/onOpen/onClose never cause reconnect
//   ✅ Guard clauses   — null/undefined safe everywhere
//   ✅ Duplicate conn  — blocks if already OPEN or CONNECTING
//   ✅ JSON parse      — handles Python True/False/None + malformed
//   ✅ Reconnect loop  — exponential backoff, skips auth errors (4xxx)
//   ✅ Memory leak     — cleanup on unmount, clears all timers
//   ✅ Stale closure   — all refs updated before use
//   ✅ Rate limiting   — max 10 retries then gives up
//   ✅ Visibility API  — reconnects when tab becomes visible again
//   ✅ Online/offline  — reconnects when network comes back
//   ✅ Token refresh   — re-reads token on every connect attempt
//   ✅ Message queue   — buffers sends while connecting, flushes on open
// ═══════════════════════════════════════════════════════════════════

import { useEffect, useRef, useCallback, useState } from 'react';
import toast from 'react-hot-toast';

// ── Constants ─────────────────────────────────────────────────────
const WS_BASE        = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
const MAX_RETRIES    = 10;
const MAX_BACKOFF_MS = 30_000;
const MSG_QUEUE_MAX  = 50;

export const WS_STATE = {
  CONNECTING:  'CONNECTING',
  CONNECTED:   'CONNECTED',
  DISCONNECTED:'DISCONNECTED',
  ERROR:       'ERROR',
};

// ── Safe JSON parse ───────────────────────────────────────────────
// Handles: standard JSON, Python True/False/None, unexpected types
function safeParseJSON(raw) {
  if (!raw || typeof raw !== 'string') return null;
  // First try: standard JSON
  try { return JSON.parse(raw); } catch (_) {}
  // Second try: fix Python-style literals
  try {
    const fixed = raw
      .replace(/\bTrue\b/g,  'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/\bNone\b/g,  'null');
    return JSON.parse(fixed);
  } catch (_) {}
  // Give up
  console.warn('[WS] Could not parse message:', raw.slice(0, 200));
  return null;
}

// ── Get auth token safely ─────────────────────────────────────────
function getAuthToken() {
  try { return localStorage.getItem('adminAccessToken') || ''; }
  catch (_) { return ''; }
}

// ── Build WS URL safely ───────────────────────────────────────────
function buildUrl(base) {
  if (!base || typeof base !== 'string') return null;
  const token = getAuthToken();
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

// ══════════════════════════════════════════════════════════════════
// useWebSocketBase — core hook, all defenses live here
// ══════════════════════════════════════════════════════════════════
function useWebSocketBase(url, {
  onMessage,
  onOpen,
  onClose,
  enabled = true,
} = {}) {

  // ── Refs (never cause re-renders) ───────────────────────────────
  const wsRef         = useRef(null);
  const mountedRef    = useRef(true);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef(null);
  const urlRef        = useRef(url);
  const enabledRef    = useRef(enabled);
  const msgQueueRef   = useRef([]); // buffered messages while connecting

  // Keep latest callbacks in refs — prevents connect() re-creation
  const onMessageRef = useRef(onMessage);
  const onOpenRef    = useRef(onOpen);
  const onCloseRef   = useRef(onClose);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onOpenRef.current    = onOpen;    }, [onOpen]);
  useEffect(() => { onCloseRef.current   = onClose;   }, [onClose]);
  useEffect(() => { urlRef.current       = url;       }, [url]);
  useEffect(() => { enabledRef.current   = enabled;   }, [enabled]);

  const [state, setState] = useState(WS_STATE.DISCONNECTED);

  // ── Flush message queue ─────────────────────────────────────────
  const flushQueue = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const queue = msgQueueRef.current.splice(0);
    queue.forEach(payload => {
      try { ws.send(payload); } catch (e) {
        console.warn('[WS] flush send failed:', e);
      }
    });
  }, []);

  // ── connect — stable, never re-creates ─────────────────────────
  const connect = useCallback(() => {
    // Guard: disabled, no URL, unmounted, too many retries
    if (!enabledRef.current)               return;
    if (!urlRef.current)                   return;
    if (!mountedRef.current)               return;
    if (retryCountRef.current >= MAX_RETRIES) {
      console.error(`[WS] Max retries (${MAX_RETRIES}) reached for ${urlRef.current}`);
      setState(WS_STATE.ERROR);
      return;
    }

    // Guard: already open or connecting
    const ws = wsRef.current;
    if (ws && (ws.readyState === WebSocket.OPEN ||
               ws.readyState === WebSocket.CONNECTING)) return;

    const fullUrl = buildUrl(urlRef.current);
    if (!fullUrl) return;

    setState(WS_STATE.CONNECTING);

    let newWs;
    try {
      newWs = new WebSocket(fullUrl);
    } catch (e) {
      console.error('[WS] Failed to create WebSocket:', e);
      setState(WS_STATE.ERROR);
      return;
    }
    wsRef.current = newWs;

    // ── onopen ──
    newWs.onopen = () => {
      if (!mountedRef.current) { newWs.close(1000); return; }
      retryCountRef.current = 0;
      setState(WS_STATE.CONNECTED);
      try { onOpenRef.current?.(); } catch (e) { console.error('[WS] onOpen error:', e); }
      flushQueue();
    };

    // ── onmessage ──
    newWs.onmessage = (e) => {
      if (!mountedRef.current) return;
      const data = safeParseJSON(e.data);
      if (data === null) return; // unparseable, already warned
      try { onMessageRef.current?.(data); }
      catch (e) { console.error('[WS] onMessage handler error:', e); }
    };

    // ── onerror ──
    newWs.onerror = (e) => {
      if (!mountedRef.current) return;
      console.warn('[WS] Socket error on', urlRef.current, e);
      setState(WS_STATE.ERROR);
      // onclose will fire after onerror — reconnect logic lives there
    };

    // ── onclose ──
    newWs.onclose = (e) => {
      if (!mountedRef.current) return;
      setState(WS_STATE.DISCONNECTED);
      try { onCloseRef.current?.(e); } catch (err) { console.error('[WS] onClose error:', err); }

      // Auth errors (4001-4003) → do NOT retry
      if (e.code >= 4001 && e.code <= 4003) {
        console.warn(`[WS] Auth error (${e.code}), not retrying.`);
        setState(WS_STATE.ERROR);
        return;
      }
      // Normal close (1000) → do NOT retry
      if (e.code === 1000) return;

      // Retry with exponential backoff
      const delay = Math.min(1000 * 2 ** retryCountRef.current, MAX_BACKOFF_MS);
      retryCountRef.current += 1;
      console.info(`[WS] Reconnecting in ${delay}ms (attempt ${retryCountRef.current}/${MAX_RETRIES})…`);
      retryTimerRef.current = setTimeout(connect, delay);
    };

  }, []); // ← intentionally empty: connect is fully stable

  // ── disconnect ──────────────────────────────────────────────────
  const disconnect = useCallback((code = 1000) => {
    clearTimeout(retryTimerRef.current);
    retryCountRef.current = MAX_RETRIES; // prevent auto-retry after manual disconnect
    try { wsRef.current?.close(code); } catch (_) {}
  }, []);

  // ── send — queues if not yet connected ──────────────────────────
  const send = useCallback((data) => {
    if (!data) return false;
    let payload;
    try { payload = JSON.stringify(data); }
    catch (e) { console.error('[WS] send: could not serialize data:', e); return false; }

    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      try { ws.send(payload); return true; }
      catch (e) { console.warn('[WS] send failed:', e); return false; }
    }

    // Buffer message if connecting
    if (ws?.readyState === WebSocket.CONNECTING) {
      if (msgQueueRef.current.length < MSG_QUEUE_MAX) {
        msgQueueRef.current.push(payload);
        return true; // optimistic
      }
      console.warn('[WS] Message queue full, dropping message');
    }
    return false;
  }, []);

  // ── Lifecycle: connect / cleanup ────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    retryCountRef.current = 0;
    if (enabled && url) connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(retryTimerRef.current);
      msgQueueRef.current = [];
      try { wsRef.current?.close(1000); } catch (_) {}
    };
  }, [url, enabled]); // reconnect only when url or enabled actually changes

  // ── Visibility API: reconnect when tab becomes active ───────────
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' &&
          enabledRef.current && urlRef.current &&
          wsRef.current?.readyState !== WebSocket.OPEN) {
        retryCountRef.current = 0;
        clearTimeout(retryTimerRef.current);
        connect();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [connect]);

  // ── Online/offline: reconnect when network returns ──────────────
  useEffect(() => {
    const handleOnline = () => {
      if (enabledRef.current && urlRef.current) {
        retryCountRef.current = 0;
        clearTimeout(retryTimerRef.current);
        console.info('[WS] Network online — reconnecting…');
        connect();
      }
    };
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [connect]);

  return { send, disconnect, reconnect: connect, state };
}

// ══════════════════════════════════════════════════════════════════
// useChatWebSocket
// import.meta.env.VITE_WS_URL or 'ws://localhost:8000/ws'/chat/<chatId>/
// ══════════════════════════════════════════════════════════════════
export function useChatWebSocket(chatId, { onNewMessage, onTyping } = {}) {
  const [typingUsers, setTypingUsers] = useState([]);
  const typingTimers = useRef({});

  const url = chatId ? `${WS_BASE}/chat/${chatId}/` : null;

  const handleMessage = useCallback((data) => {
    if (!data?.type) return;
    switch (data.type) {

      case 'chat.message.broadcast':
        if (typeof onNewMessage === 'function') onNewMessage(data);
        break;

      case 'chat.typing.broadcast': {
        if (typeof onTyping === 'function') onTyping(data);
        const { user_id, user_name, is_typing } = data;
        if (!user_id) break;
        clearTimeout(typingTimers.current[user_id]);
        if (is_typing) {
          setTypingUsers(prev =>
            prev.find(u => u.user_id === user_id)
              ? prev
              : [...prev, { user_id, user_name: user_name || 'Someone' }]
          );
          typingTimers.current[user_id] = setTimeout(() => {
            setTypingUsers(prev => prev.filter(u => u.user_id !== user_id));
          }, 3500);
        } else {
          setTypingUsers(prev => prev.filter(u => u.user_id !== user_id));
        }
        break;
      }

      case 'chat.read.ack':
        // acknowledged silently
        break;

      case 'error':
        if (data.code === 'rate_limit') {
          toast.error('⚡ Rate limited — slow down!');
        } else {
          console.warn('[WS Chat] Server error:', data);
          toast.error(data.detail || 'Chat error');
        }
        break;

      default:
        console.debug('[WS Chat] Unknown message type:', data.type);
    }
  }, [onNewMessage, onTyping]);

  const handleOpen = useCallback(() => {
    console.info(`[WS] Chat ${chatId} connected ✅`);
  }, [chatId]);

  const { send, state, disconnect, reconnect } = useWebSocketBase(url, {
    onMessage: handleMessage,
    onOpen:    handleOpen,
    enabled:   !!chatId,
  });

  const sendMessage = useCallback((content, {
    message_type = 'TEXT',
    reply_to_id  = null,
    attachments  = [],
  } = {}) => {
    if (!content?.trim()) return false;
    return send({
      type: 'chat.message',
      content: content.trim(),
      message_type,
      ...(reply_to_id ? { reply_to_id } : {}),
      attachments: Array.isArray(attachments) ? attachments : [],
    });
  }, [send]);

  const sendTyping = useCallback((is_typing = true) => {
    send({ type: 'chat.typing', is_typing: Boolean(is_typing) });
  }, [send]);

  const markRead = useCallback((item_ids) => {
    if (!Array.isArray(item_ids) || !item_ids.length) return;
    send({ type: 'chat.read', item_ids });
  }, [send]);

  return { sendMessage, sendTyping, markRead, state, disconnect, reconnect, typingUsers };
}

// ══════════════════════════════════════════════════════════════════
// useSupportWebSocket
// import.meta.env.VITE_WS_URL or 'ws://localhost:8000/ws'/support/<threadId>/
// ══════════════════════════════════════════════════════════════════
export function useSupportWebSocket(threadId, { onNewMessage } = {}) {
  const url = threadId ? `${WS_BASE}/support/${threadId}/` : null;

  const handleMessage = useCallback((data) => {
    if (!data?.type) return;
    switch (data.type) {
      case 'support.message.broadcast':
        if (typeof onNewMessage === 'function') onNewMessage(data);
        break;
      case 'error':
        console.warn('[WS Support] Server error:', data);
        toast.error(data.detail || 'Support error');
        break;
      default:
        console.debug('[WS Support] Unknown type:', data.type);
    }
  }, [onNewMessage]);

  const handleOpen = useCallback(() => {
    console.info(`[WS] Support thread ${threadId} connected ✅`);
  }, [threadId]);

  const { send, state, disconnect, reconnect } = useWebSocketBase(url, {
    onMessage: handleMessage,
    onOpen:    handleOpen,
    enabled:   !!threadId,
  });

  const sendMessage = useCallback((content) => {
    if (!content?.trim()) return false;
    return send({ type: 'support.message', content: content.trim() });
  }, [send]);

  return { sendMessage, state, disconnect, reconnect };
}

// ══════════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════════
export function wsStateColor(state) {
  return {
    [WS_STATE.CONNECTED]:    '#00ff88',
    [WS_STATE.CONNECTING]:   '#ffd700',
    [WS_STATE.DISCONNECTED]: '#888888',
    [WS_STATE.ERROR]:        '#ff3355',
  }[state] ?? '#888888';
}

export function wsStateLabel(state) {
  return {
    [WS_STATE.CONNECTED]:    'LIVE',
    [WS_STATE.CONNECTING]:   'CONNECTING',
    [WS_STATE.DISCONNECTED]: 'OFFLINE',
    [WS_STATE.ERROR]:        'ERROR',
  }[state] ?? 'OFFLINE';
}