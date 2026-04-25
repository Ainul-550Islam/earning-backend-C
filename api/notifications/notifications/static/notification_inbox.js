/**
 * Notification Inbox Widget — Embeddable JS Component
 * Like Knock/Novu — drop this <script> tag into any page.
 *
 * Usage:
 *   <script src="/static/notification_inbox.js"></script>
 *   <div id="notification-inbox"></div>
 *   <script>
 *     NotificationInbox.init({
 *       apiUrl: '/api/notifications',
 *       wsUrl: 'ws://yoursite.com/ws/notifications/',
 *       token: 'Bearer xxx',
 *       theme: 'light',
 *       position: 'bottom-right',
 *       maxItems: 20,
 *     });
 *   </script>
 */
(function(window){
  'use strict';
  const NotificationInbox = {
    config: {}, _ws: null, _notifications: [], _unreadCount: 0,

    init(options) {
      this.config = Object.assign({ apiUrl:'/api/notifications', wsUrl:null, token:'', theme:'light', position:'bottom-right', maxItems:20 }, options);
      this._render(); this._fetchNotifications();
      if (this.config.wsUrl) this._connectWebSocket();
    },

    _render() {
      const s = document.createElement('style');
      const dark = this.config.theme === 'dark';
      s.textContent = `.ni-bell{position:fixed;${this.config.position.includes('right')?'right:20px':'left:20px'};${this.config.position.includes('bottom')?'bottom:20px':'top:20px'};z-index:9999;cursor:pointer;background:#1a73e8;border-radius:50%;width:48px;height:48px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 12px rgba(0,0,0,.2)}.ni-bell svg{width:24px;height:24px;fill:white}.ni-badge{position:absolute;top:-4px;right:-4px;background:#e53935;color:white;border-radius:50%;min-width:18px;height:18px;font-size:11px;font-weight:bold;display:flex;align-items:center;justify-content:center;padding:0 4px}.ni-panel{position:fixed;${this.config.position.includes('right')?'right:20px':'left:20px'};${this.config.position.includes('bottom')?'bottom:80px':'top:80px'};width:380px;max-height:500px;background:${dark?'#1e1e2e':'#fff'};border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.15);z-index:9998;display:none;flex-direction:column;overflow:hidden}.ni-header{padding:16px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;color:${dark?'#fff':'#333'}}.ni-header h3{margin:0;font-size:16px;font-weight:600}.ni-mark-all{font-size:12px;color:#1a73e8;cursor:pointer;background:none;border:none;padding:4px 8px;border-radius:4px}.ni-list{overflow-y:auto;flex:1}.ni-item{padding:14px 16px;border-bottom:1px solid #f0f0f0;cursor:pointer;display:flex;gap:12px;transition:background .15s;background:${dark?'#1e1e2e':'#fff'}}.ni-item:hover{background:${dark?'#2a2a3e':'#f8f9ff'}}.ni-item.unread{background:${dark?'#252540':'#f0f4ff'}}.dot{width:8px;height:8px;background:#1a73e8;border-radius:50%;margin-top:6px;flex-shrink:0}.dot.read{background:transparent}.ni-title{font-weight:600;font-size:14px;margin:0 0 4px;color:${dark?'#fff':'#1a1a2e'}}.ni-msg{font-size:13px;color:${dark?'#aaa':'#666'};margin:0;line-height:1.4}.ni-time{font-size:11px;color:#999;margin-top:4px}.ni-empty{padding:40px;text-align:center;color:#999}`;
      document.head.appendChild(s);

      const bell = document.createElement('div');
      bell.className = 'ni-bell';
      bell.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5S10.5 3.17 10.5 4v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>';
      this._badge = document.createElement('span');
      this._badge.className = 'ni-badge';
      this._badge.style.display = 'none';
      bell.appendChild(this._badge);
      document.body.appendChild(bell);

      this._panel = document.createElement('div');
      this._panel.className = 'ni-panel';
      this._panel.innerHTML = '<div class="ni-header"><h3>Notifications</h3><button class="ni-mark-all" onclick="NotificationInbox._markAllRead()">Mark all read</button></div><div class="ni-list" id="ni-list"></div>';
      document.body.appendChild(this._panel);

      bell.addEventListener('click', () => { this._panel.style.display = this._panel.style.display==='flex'?'none':'flex'; });
      document.addEventListener('click', (e) => { if (!bell.contains(e.target) && !this._panel.contains(e.target)) this._panel.style.display='none'; });
    },

    async _fetchNotifications() {
      try {
        const r = await fetch(`${this.config.apiUrl}/notifications/?page_size=${this.config.maxItems}`, {headers:{'Authorization':this.config.token}});
        const d = await r.json();
        this._notifications = d.results||[];
        this._unreadCount = this._notifications.filter(n=>!n.is_read).length;
        this._renderList(); this._updateBadge();
      } catch(e){}
    },

    _renderList() {
      const list = document.getElementById('ni-list');
      if (!list) return;
      if (!this._notifications.length) { list.innerHTML='<div class="ni-empty">No notifications yet</div>'; return; }
      list.innerHTML = this._notifications.map(n =>
        `<div class="ni-item ${n.is_read?'':'unread'}" onclick="NotificationInbox._markRead(${n.id},this)" data-url="${n.action_url||''}">
          <div class="dot ${n.is_read?'read':''}"></div>
          <div><p class="ni-title">${n.title}</p><p class="ni-msg">${(n.message||'').substring(0,80)}</p><p class="ni-time">${this._timeAgo(n.created_at)}</p></div>
        </div>`).join('');
    },

    async _markRead(id, el) {
      el.classList.remove('unread'); el.querySelector('.dot').classList.add('read');
      this._unreadCount=Math.max(0,this._unreadCount-1); this._updateBadge();
      const url=el.dataset.url; if(url) window.open(url,'_blank');
      try { await fetch(`${this.config.apiUrl}/notifications/${id}/mark-read/`,{method:'POST',headers:{'Authorization':this.config.token}}); } catch(e){}
    },

    async _markAllRead() {
      try { await fetch(`${this.config.apiUrl}/notifications/mark-all-read/`,{method:'POST',headers:{'Authorization':this.config.token,'Content-Type':'application/json'}}); } catch(e){}
      this._unreadCount=0; this._notifications.forEach(n=>n.is_read=true);
      this._updateBadge(); this._renderList();
    },

    _updateBadge() {
      this._badge.style.display = this._unreadCount>0?'flex':'none';
      this._badge.textContent = this._unreadCount>99?'99+':this._unreadCount;
    },

    _connectWebSocket() {
      try {
        this._ws = new WebSocket(this.config.wsUrl);
        this._ws.onmessage = (e) => {
          const msg = JSON.parse(e.data);
          if (msg.type==='new_notification') { this._notifications.unshift(msg.data); this._unreadCount++; this._updateBadge(); this._renderList(); }
          else if (msg.type==='notification_count') { this._unreadCount=msg.unread; this._updateBadge(); }
        };
        this._ws.onclose = () => setTimeout(()=>this._connectWebSocket(), 5000);
      } catch(e){}
    },

    _timeAgo(d) {
      const diff=(Date.now()-new Date(d))/1000;
      if(diff<60) return 'just now';
      if(diff<3600) return Math.floor(diff/60)+'m ago';
      if(diff<86400) return Math.floor(diff/3600)+'h ago';
      return Math.floor(diff/86400)+'d ago';
    },
  };
  window.NotificationInbox = NotificationInbox;
})(window);
