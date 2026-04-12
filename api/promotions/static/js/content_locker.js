/**
 * YourPlatform Content Locker SDK v2.0
 * Usage:
 *   Link Locker: <a href="url" class="locked-link" data-title="Title">Download</a>
 *                <script src="/static/js/content_locker.js" data-pub="123"></script>
 *   Content Locker: <div data-content-lock="LOCK_TOKEN">Hidden content</div>
 */
(function(w, d) {
  'use strict';

  var CL = w.ContentLockerSDK = {
    _config: { apiBase: '/api/promotions/', publisherId: 0 },
    _visitorId: null,

    init: function(config) {
      Object.assign(this._config, config);
      this._visitorId = this._getVisitorId();
      this._initLinkLockers();
      this._initContentLockers();
    },

    _getVisitorId: function() {
      var id = localStorage.getItem('_cl_vid');
      if (!id) {
        id = 'cl_' + Math.random().toString(36).substr(2,16);
        localStorage.setItem('_cl_vid', id);
      }
      return id;
    },

    _initLinkLockers: function() {
      var links = d.querySelectorAll('a[data-lock-token], .locked-link');
      links.forEach(function(link) {
        var token = link.dataset.lockToken || link.href;
        link.addEventListener('click', function(e) {
          e.preventDefault();
          CL._showLinkLockerModal(token, link.dataset.title || link.textContent);
        });
      });
    },

    _initContentLockers: function() {
      d.querySelectorAll('[data-content-lock]').forEach(function(el) {
        var token = el.dataset.contentLock;
        CL._checkContentLocked(token, function(locked) {
          if (locked) CL._overlayContent(el, token);
        });
      });
    },

    _checkContentLocked: function(token, cb) {
      fetch(CL._config.apiBase + 'locker/content/' + token + '/check/?visitor_id=' + CL._visitorId)
        .then(function(r) { return r.json(); })
        .then(function(d) { cb(!d.unlocked); })
        .catch(function() { cb(false); });
    },

    _overlayContent: function(el, token) {
      el.style.display = 'none';
      var overlay = d.createElement('div');
      overlay.className = 'cl-overlay';
      overlay.innerHTML = [
        '<div class="cl-box">',
        '<div class="cl-lock-icon">🔒</div>',
        '<h3 class="cl-title">Unlock This Content</h3>',
        '<p class="cl-desc">Complete 1 free offer to reveal this content instantly</p>',
        '<button class="cl-btn" onclick="ContentLockerSDK.open(\'' + token + '\')">',
        'Unlock Free →</button></div>',
      ].join('');
      el.parentNode.insertBefore(overlay, el);
      this._injectStyles();
    },

    open: function(token) {
      this._loadOffersModal(token);
    },

    _loadOffersModal: function(token) {
      var self = this;
      fetch(this._config.apiBase + 'locker/content/' + token + '/offers/?visitor_id=' + this._visitorId)
        .then(function(r) { return r.json(); })
        .then(function(data) { self._showOffersModal(token, data.offers || []); })
        .catch(function() { self._showOffersModal(token, []); });
    },

    _showOffersModal: function(token, offers) {
      var self = this;
      var modal = d.createElement('div');
      modal.id = '_cl_modal';
      modal.innerHTML = [
        '<div class="cl-modal-bg" onclick="ContentLockerSDK._closeModal()">',
        '<div class="cl-modal" onclick="event.stopPropagation()">',
        '<div class="cl-modal-header"><span>🔓 Unlock Content</span>',
        '<button onclick="ContentLockerSDK._closeModal()" class="cl-close">✕</button></div>',
        '<p style="font-size:13px;color:#94a3b8;margin:12px 0">Complete any offer below to unlock:</p>',
        '<div class="cl-offers">',
        offers.map(function(o) {
          return '<div class="cl-offer" onclick="ContentLockerSDK._startOffer(\'' + token + '\', ' + (o.offer_id||0) + ', \'' + (o.offer_url||'#') + '\')">' +
            '<span class="cl-offer-title">' + (o.title||'Free Offer') + '</span>' +
            '<span class="cl-offer-pay">' + (o.payout_display||'$0.50') + '</span>' +
            '<button class="cl-offer-btn">' + (o.cta||'Start') + '</button></div>';
        }).join('') || '<div style="text-align:center;padding:20px;color:#94a3b8">No offers available for your location</div>',
        '</div></div></div>',
      ].join('');
      d.body.appendChild(modal);
    },

    _startOffer: function(token, offerId, offerUrl) {
      var win = window.open(offerUrl, '_blank');
      var checkInterval = setInterval(function() {
        if (win && win.closed) {
          clearInterval(checkInterval);
          CL._checkAndUnlock(token, offerId);
        }
      }, 1000);
    },

    _checkAndUnlock: function(token, offerId) {
      var self = this;
      fetch(self._config.apiBase + 'locker/content/' + token + '/unlock/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({visitor_id: self._visitorId, offer_id: offerId}),
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.unlocked) {
          self._closeModal();
          self._revealContent(token);
        }
      });
    },

    _revealContent: function(token) {
      var el = d.querySelector('[data-content-lock="' + token + '"]');
      var overlay = el && el.previousElementSibling;
      if (overlay && overlay.classList.contains('cl-overlay')) overlay.remove();
      if (el) el.style.display = '';
    },

    _closeModal: function() {
      var m = d.getElementById('_cl_modal');
      if (m) m.remove();
    },

    _showLinkLockerModal: function(token, title) {
      alert('Link locker: ' + title + '\nToken: ' + token);
    },

    _injectStyles: function() {
      if (d.getElementById('_cl_styles')) return;
      var s = d.createElement('style');
      s.id = '_cl_styles';
      s.textContent = '.cl-overlay{text-align:center;padding:40px;background:#1e293b;border-radius:12px;border:1px solid #334155}' +
        '.cl-lock-icon{font-size:48px;margin-bottom:12px}.cl-title{font-size:18px;font-weight:600;color:#f1f5f9}' +
        '.cl-desc{font-size:13px;color:#94a3b8;margin:8px 0 16px}.cl-btn{background:#6C63FF;color:white;border:none;' +
        'padding:10px 24px;border-radius:8px;font-size:14px;font-weight:500;cursor:pointer}' +
        '.cl-modal-bg{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:99999;display:flex;align-items:center;justify-content:center}' +
        '.cl-modal{background:#1e293b;border-radius:16px;padding:24px;width:90%;max-width:440px;max-height:80vh;overflow-y:auto}' +
        '.cl-modal-header{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:16px;color:#f1f5f9}' +
        '.cl-close{background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer}' +
        '.cl-offer{display:flex;align-items:center;justify-content:space-between;padding:12px;background:#0f172a;border-radius:8px;margin:8px 0;cursor:pointer}' +
        '.cl-offer-title{font-size:13px;color:#f1f5f9;flex:1}.cl-offer-pay{font-size:14px;font-weight:700;color:#6C63FF;margin:0 12px}' +
        '.cl-offer-btn{background:#6C63FF;color:white;border:none;padding:6px 14px;border-radius:6px;font-size:12px;cursor:pointer}';
      d.head.appendChild(s);
    },
  };

  // Auto-init
  d.addEventListener('DOMContentLoaded', function() {
    var s = d.querySelector('[data-pub]');
    if (s) {
      CL.init({ publisherId: parseInt(s.dataset.pub || '0') });
    }
  });

})(window, document);
