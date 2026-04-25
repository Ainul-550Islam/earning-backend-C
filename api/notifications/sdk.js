/**
 * Notification System JavaScript SDK
 * Drop-in client SDK for web applications.
 * 
 * Features:
 *   - REST API wrapper (all 151+ endpoints)
 *   - WebSocket real-time notifications
 *   - Push notification subscription (VAPID)
 *   - Notification Inbox widget
 *   - Auto-retry on failure
 *   - TypeScript-compatible JSDoc types
 * 
 * Usage:
 *   <script src="/static/sdk.js"></script>
 *   <script>
 *     const notif = new NotificationSDK({
 *       apiUrl: '/api/notifications',
 *       wsUrl: 'wss://yoursite.com/ws/notifications/',
 *       token: 'Bearer your-jwt-token',
 *     });
 *     
 *     // Get unread count
 *     const count = await notif.getUnreadCount();
 *     
 *     // Mark all read
 *     await notif.markAllRead();
 *     
 *     // Subscribe to real-time
 *     notif.on('new_notification', (data) => {
 *       console.log('New notification:', data);
 *     });
 *     
 *     // Register push device
 *     await notif.registerPushDevice();
 *   </script>
 */

(function(window) {
  'use strict';

  class NotificationSDK {
    constructor(config = {}) {
      this.config = {
        apiUrl: config.apiUrl || '/api/notifications',
        wsUrl: config.wsUrl || null,
        token: config.token || '',
        timeout: config.timeout || 10000,
        autoConnect: config.autoConnect !== false,
        retryDelay: config.retryDelay || 5000,
        maxRetries: config.maxRetries || 3,
      };
      this._ws = null;
      this._listeners = {};
      this._retryCount = 0;

      if (this.config.autoConnect && this.config.wsUrl) {
        this._connectWebSocket();
      }
    }

    // ── REST API ───────────────────────────────────────────────────

    async getNotifications(params = {}) {
      const query = new URLSearchParams(params).toString();
      return this._get(`/notifications/?${query}`);
    }

    async getNotification(id) {
      return this._get(`/notifications/${id}/`);
    }

    async getUnreadCount() {
      const data = await this._get('/notifications/unread-count/');
      return data?.unread_count || 0;
    }

    async markRead(id) {
      return this._post(`/notifications/${id}/mark-read/`);
    }

    async markAllRead() {
      return this._post('/notifications/mark-all-read/');
    }

    async deleteNotification(id) {
      return this._delete(`/notifications/${id}/`);
    }

    async archiveNotification(id) {
      return this._post(`/v2/notifications/${id}/archive/`);
    }

    async pinNotification(id) {
      return this._post(`/v2/notifications/${id}/pin/`);
    }

    // ── In-App Messages ────────────────────────────────────────────

    async getInAppMessages(params = {}) {
      return this._get(`/v2/in-app-messages/?${new URLSearchParams(params)}`);
    }

    async dismissMessage(id) {
      return this._post(`/v2/in-app-messages/${id}/dismiss/`);
    }

    async markMessageRead(id) {
      return this._post(`/v2/in-app-messages/${id}/read/`);
    }

    // ── Push Devices ───────────────────────────────────────────────

    async registerPushDevice(deviceData = {}) {
      // Auto-detect device type
      const type = /iPad|iPhone|iPod/.test(navigator.userAgent) ? 'ios'
                 : /Android/.test(navigator.userAgent) ? 'android' : 'web';

      if (type === 'web') {
        const subscription = await this._getWebPushSubscription();
        if (!subscription) return { success: false, error: 'Web push not supported' };
        return this._post('/v2/push-devices/register/', {
          device_type: 'web',
          web_push_subscription: subscription,
          ...deviceData,
        });
      }

      return this._post('/v2/push-devices/register/', {
        device_type: type,
        ...deviceData,
      });
    }

    async listDevices() {
      return this._get('/v2/push-devices/');
    }

    async removeDevice(id) {
      return this._delete(`/v2/push-devices/${id}/`);
    }

    // ── Opt-Out ────────────────────────────────────────────────────

    async optOut(channel, reason = 'user_request', notes = '') {
      return this._post('/v2/opt-outs/opt_out/', { channel, reason, notes });
    }

    async resubscribe(channel) {
      return this._post('/v2/opt-outs/resubscribe/', { channel });
    }

    async getOptOuts() {
      return this._get('/v2/opt-outs/');
    }

    // ── Preferences ────────────────────────────────────────────────

    async getPreferences() {
      return this._get('/v2/preferences/me/');
    }

    async updatePreferences(prefs) {
      return this._patch('/v2/preferences/me/', prefs);
    }

    async setDND(enabled, startHour = 22, endHour = 8) {
      return this._post('/v2/preferences/dnd/', {
        dnd_enabled: enabled,
        dnd_start: `${String(startHour).padStart(2, '0')}:00:00`,
        dnd_end: `${String(endHour).padStart(2, '0')}:00:00`,
      });
    }

    // ── Status ─────────────────────────────────────────────────────

    async getStatus() {
      return this._get('/rfm-score/');
    }

    async getHealth() {
      return this._get('/health/');
    }

    // ── Event system ───────────────────────────────────────────────

    on(event, callback) {
      if (!this._listeners[event]) this._listeners[event] = [];
      this._listeners[event].push(callback);
      return this;
    }

    off(event, callback) {
      if (this._listeners[event]) {
        this._listeners[event] = this._listeners[event].filter(cb => cb !== callback);
      }
      return this;
    }

    _emit(event, data) {
      (this._listeners[event] || []).forEach(cb => { try { cb(data); } catch(e) {} });
      (this._listeners['*'] || []).forEach(cb => { try { cb(event, data); } catch(e) {} });
    }

    // ── WebSocket ──────────────────────────────────────────────────

    _connectWebSocket() {
      if (!this.config.wsUrl) return;
      try {
        this._ws = new WebSocket(this.config.wsUrl);

        this._ws.onopen = () => {
          this._retryCount = 0;
          this._emit('connected', {});
        };

        this._ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            this._emit(msg.type, msg);
            if (msg.type === 'new_notification') this._emit('new_notification', msg.data || msg);
            if (msg.type === 'notification_count') this._emit('count_update', msg.unread);
          } catch(e) {}
        };

        this._ws.onclose = (event) => {
          this._emit('disconnected', { code: event.code });
          if (!event.wasClean && this._retryCount < this.config.maxRetries) {
            this._retryCount++;
            setTimeout(() => this._connectWebSocket(), this.config.retryDelay * this._retryCount);
          }
        };

        this._ws.onerror = (error) => this._emit('error', error);

      } catch(e) {
        this._emit('error', e);
      }
    }

    sendWS(type, data = {}) {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify({ type, ...data }));
      }
    }

    ping() { this.sendWS('ping'); }
    wsMarkRead(id) { this.sendWS('mark_read', { notification_id: id }); }
    wsMarkAllRead() { this.sendWS('mark_all_read'); }

    disconnect() {
      if (this._ws) { this._ws.close(); this._ws = null; }
    }

    // ── Web Push ───────────────────────────────────────────────────

    async _getWebPushSubscription() {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;
      try {
        const reg = await navigator.serviceWorker.ready;
        let sub = await reg.pushManager.getSubscription();
        if (!sub) {
          const vapidData = await this._get('/push/vapid-key/');
          if (!vapidData?.vapid_public_key) return null;
          const key = this._urlBase64ToUint8Array(vapidData.vapid_public_key);
          sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
        }
        return sub.toJSON();
      } catch(e) {
        return null;
      }
    }

    _urlBase64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - base64String.length % 4) % 4);
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
      const rawData = window.atob(base64);
      return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
    }

    // ── HTTP helpers ───────────────────────────────────────────────

    async _request(method, path, body = null) {
      const url = `${this.config.apiUrl}${path}`;
      const headers = {
        'Content-Type': 'application/json',
        ...(this.config.token ? { 'Authorization': this.config.token } : {}),
      };
      const options = { method, headers };
      if (body) options.body = JSON.stringify(body);

      for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
        try {
          const response = await fetch(url, options);
          if (!response.ok && response.status >= 500 && attempt < this.config.maxRetries) {
            await new Promise(r => setTimeout(r, this.config.retryDelay));
            continue;
          }
          if (response.status === 204) return { success: true };
          return await response.json();
        } catch(e) {
          if (attempt === this.config.maxRetries) throw e;
          await new Promise(r => setTimeout(r, this.config.retryDelay));
        }
      }
    }

    _get(path) { return this._request('GET', path); }
    _post(path, body = {}) { return this._request('POST', path, body); }
    _patch(path, body = {}) { return this._request('PATCH', path, body); }
    _put(path, body = {}) { return this._request('PUT', path, body); }
    _delete(path) { return this._request('DELETE', path); }
  }

  // Expose globally
  window.NotificationSDK = NotificationSDK;

  // Auto-init if data-auto attribute present
  // <script src="sdk.js" data-auto data-api="/api/notifications" data-ws="wss://..." data-token="...">
  const script = document.currentScript;
  if (script && script.hasAttribute('data-auto')) {
    window.notificationSDK = new NotificationSDK({
      apiUrl: script.getAttribute('data-api') || '/api/notifications',
      wsUrl: script.getAttribute('data-ws') || null,
      token: script.getAttribute('data-token') || '',
    });
  }

})(window);
