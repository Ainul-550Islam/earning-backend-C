/**
 * YourPlatform Offerwall SDK v2.0
 * Publisher embeds this script to show offerwall on their site
 * Usage: <script src="/static/promotions/js/offerwall-sdk.js"
 *              data-pub="123" data-container="offerwall-div"></script>
 */
(function(window, document) {
  'use strict';

  var OW = window.OfferwallSDK = {
    version: '2.0.0',
    _config: {},
    _offers: [],
    _initialized: false,

    init: function(config) {
      this._config = Object.assign({
        publisherId: 0,
        container: 'offerwall',
        apiBase: '/api/promotions/',
        theme: 'dark',            // dark / light / custom
        primaryColor: '#6C63FF',
        currencyName: 'Coins',
        currencyIcon: '🪙',
        limit: 20,
        showSearch: true,
        showCategories: true,
        autoLoad: true,
        onConversion: null,
        onError: null,
      }, config);

      this._detectVisitor();
      if (this._config.autoLoad) {
        this._render();
        this._loadOffers();
      }
      this._initialized = true;
      return this;
    },

    _detectVisitor: function() {
      var ua = navigator.userAgent.toLowerCase();
      this._visitor = {
        device:  /mobile|android|iphone|ipad/i.test(ua) ? 'mobile' : 'desktop',
        country: 'US',  // Override with CF-IPCountry from server
        id:      this._getVisitorId(),
      };
    },

    _getVisitorId: function() {
      var id = localStorage.getItem('_ow_vid');
      if (!id) {
        id = 'v_' + Math.random().toString(36).substr(2, 16) + Date.now().toString(36);
        localStorage.setItem('_ow_vid', id);
      }
      return id;
    },

    _render: function() {
      var container = document.getElementById(this._config.container);
      if (!container) {
        container = document.createElement('div');
        container.id = this._config.container;
        document.body.appendChild(container);
      }
      container.innerHTML = this._getLoadingHTML();
      this._injectStyles();
    },

    _injectStyles: function() {
      if (document.getElementById('_ow_styles')) return;
      var style = document.createElement('style');
      style.id = '_ow_styles';
      var c = this._config.primaryColor;
      style.textContent = [
        '.ow-wrap{font-family:Inter,system-ui,sans-serif;max-width:800px;margin:0 auto}',
        '.ow-header{display:flex;justify-content:space-between;align-items:center;padding:12px 0;margin-bottom:16px}',
        '.ow-title{font-size:18px;font-weight:600;color:' + (this._config.theme==='dark'?'#fff':'#0f172a') + '}',
        '.ow-offer-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}',
        '.ow-offer-card{background:' + (this._config.theme==='dark'?'#1e293b':'#fff') + ';border:1px solid' + (this._config.theme==='dark'?'#334155':'#e2e8f0') + ';border-radius:12px;padding:16px;cursor:pointer;transition:transform .2s}',
        '.ow-offer-card:hover{transform:translateY(-2px)}',
        '.ow-offer-title{font-size:14px;font-weight:500;margin:8px 0 4px;color:' + (this._config.theme==='dark'?'#f1f5f9':'#0f172a') + '}',
        '.ow-offer-payout{font-size:16px;font-weight:700;color:' + c + '}',
        '.ow-offer-btn{width:100%;padding:8px;background:' + c + ';color:white;border:none;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;margin-top:12px}',
        '.ow-offer-btn:hover{opacity:0.9}',
        '.ow-badge{display:inline-block;background:' + c + '20;color:' + c + ';font-size:11px;padding:2px 8px;border-radius:20px;margin-bottom:8px}',
        '.ow-loading{text-align:center;padding:40px;color:#94a3b8}',
        '.ow-search{width:100%;padding:10px;border:1px solid #334155;border-radius:8px;background:#0f172a;color:#fff;font-size:14px;margin-bottom:16px}',
        '.ow-cats{display:flex;gap:8px;margin-bottom:16px;overflow-x:auto}',
        '.ow-cat{padding:6px 12px;border-radius:20px;border:1px solid #334155;background:transparent;color:#94a3b8;cursor:pointer;font-size:12px;white-space:nowrap}',
        '.ow-cat.active{background:' + c + ';color:white;border-color:' + c + '}',
      ].join('');
      document.head.appendChild(style);
    },

    _getLoadingHTML: function() {
      return '<div class="ow-wrap"><div class="ow-loading">Loading offers...</div></div>';
    },

    _loadOffers: function() {
      var self = this;
      var params = new URLSearchParams({
        pub: this._config.publisherId,
        device: this._visitor.device,
        limit: this._config.limit,
      });
      fetch(this._config.apiBase + 'offerwall/?' + params)
        .then(function(r) { return r.json(); })
        .then(function(data) {
          self._offers = data.offers || [];
          self._renderOffers(self._offers);
        })
        .catch(function(e) {
          if (self._config.onError) self._config.onError(e);
          console.error('[OW] Failed to load offers:', e);
        });
    },

    _renderOffers: function(offers) {
      var container = document.getElementById(this._config.container);
      if (!container) return;

      var html = '<div class="ow-wrap">';
      html += '<div class="ow-header"><span class="ow-title">Complete Offers & Earn ' + this._config.currencyIcon + ' ' + this._config.currencyName + '</span></div>';

      if (this._config.showSearch) {
        html += '<input class="ow-search" type="text" placeholder="Search offers..." oninput="OfferwallSDK._search(this.value)">';
      }

      html += '<div class="ow-offer-grid" id="_ow_grid">';
      offers.forEach(function(offer) {
        html += this._renderOfferCard(offer);
      }, this);
      html += '</div></div>';

      container.innerHTML = html;
    },

    _renderOfferCard: function(offer) {
      var payout = offer.vc_payout || offer.payout_display || ('$' + offer.payout);
      return [
        '<div class="ow-offer-card" data-id="' + offer.id + '">',
        '<span class="ow-badge">' + (offer.category || 'offer') + '</span>',
        '<div class="ow-offer-title">' + this._esc(offer.title) + '</div>',
        '<div class="ow-offer-payout">' + payout + '</div>',
        '<div style="font-size:11px;color:#94a3b8;margin-top:4px">' + (offer.estimated_time || '2-5 min') + '</div>',
        '<button class="ow-offer-btn" onclick="OfferwallSDK._openOffer(' + offer.id + ')">',
        offer.is_featured ? '⭐ ' : '',
        'Start Task →</button>',
        '</div>',
      ].join('');
    },

    _openOffer: function(offerId) {
      var offer = this._offers.find(function(o) { return o.id === offerId; });
      if (!offer) return;
      var url = offer.tracking_url + '&vid=' + this._visitor.id;
      window.open(url, '_blank', 'width=800,height=600');
      this._trackClick(offerId);
    },

    _trackClick: function(offerId) {
      fetch(this._config.apiBase + 'cpc/click/' + offerId + '/?pub=' + this._config.publisherId, {
        method: 'GET', mode: 'no-cors',
      }).catch(function() {});
    },

    _search: function(query) {
      var filtered = this._offers.filter(function(o) {
        return !query || o.title.toLowerCase().includes(query.toLowerCase());
      });
      var grid = document.getElementById('_ow_grid');
      if (grid) {
        grid.innerHTML = filtered.map(function(o) {
          return OfferwallSDK._renderOfferCard(o);
        }).join('');
      }
    },

    _esc: function(str) {
      return String(str || '').replace(/[&<>"']/g, function(c) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
      });
    },

    // Public API
    refresh: function() { this._loadOffers(); },
    destroy: function() {
      var c = document.getElementById(this._config.container);
      if (c) c.innerHTML = '';
    },
  };

  // Auto-init from data attributes
  document.addEventListener('DOMContentLoaded', function() {
    var script = document.currentScript || document.querySelector('[data-pub]');
    if (script && script.dataset.pub) {
      OW.init({
        publisherId: parseInt(script.dataset.pub),
        container: script.dataset.container || 'offerwall',
        theme: script.dataset.theme || 'dark',
      });
    }
  });

})(window, document);
