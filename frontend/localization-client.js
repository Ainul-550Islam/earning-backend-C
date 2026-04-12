/**
 * World #1 Localization Client — JS/React/Vue integration
 * CDN: <script src="/static/localization/localization-client.js"></script>
 * npm: import { LocalizationClient } from './localization-client'
 *
 * Features:
 * - Language pack lazy loading + caching (localStorage + memory)
 * - ICU MessageFormat formatting (plural, select, number)
 * - RTL detection + html dir attribute setter
 * - Currency display formatting
 * - Auto-detect language from browser/IP
 * - OTA update polling
 */

(function (global) {
  'use strict';

  // ── Config ─────────────────────────────────────────────────────
  const DEFAULT_CONFIG = {
    apiBase: '/api/localization',           // Django API base URL
    defaultLanguage: 'en',
    fallbackLanguage: 'en',
    namespace: 'global',
    cacheKey: 'loc_pack_v1',
    cacheMaxAge: 86400000,                  // 24h in ms
    autoDetect: true,                       // Detect from browser
    pollInterval: 0,                        // 0 = no polling; set ms for OTA updates
    debug: false,
  };

  // ── LocalizationClient ─────────────────────────────────────────
  class LocalizationClient {
    constructor(config = {}) {
      this.config = Object.assign({}, DEFAULT_CONFIG, config);
      this._translations = {};
      this._meta = {};
      this._language = this.config.defaultLanguage;
      this._loaded = false;
      this._loadPromise = null;
      this._pollingTimer = null;
    }

    // ── Initialization ──────────────────────────────────────────

    async init(language = null) {
      const lang = language || await this._detectLanguage();
      this._language = lang;
      await this._loadPack(lang);
      this._applyRTL();
      if (this.config.pollInterval > 0) {
        this._startPolling();
      }
      return this;
    }

    async _detectLanguage() {
      // 1. localStorage preference
      const stored = localStorage.getItem('loc_language');
      if (stored) return stored;

      // 2. HTML lang attribute
      const htmlLang = document.documentElement.lang;
      if (htmlLang) return htmlLang.split('-')[0];

      // 3. Browser navigator.language
      const browserLang = (navigator.language || navigator.userLanguage || '').split('-')[0].toLowerCase();

      // 4. Check if supported
      if (browserLang && browserLang !== 'en') {
        try {
          const resp = await fetch(`${this.config.apiBase}/public/detect-language/?browser_lang=${browserLang}`);
          if (resp.ok) {
            const data = await resp.json();
            return data.language || browserLang;
          }
        } catch (_) {}
        return browserLang;
      }

      return this.config.defaultLanguage;
    }

    async _loadPack(language) {
      if (this._loadPromise) return this._loadPromise;

      this._loadPromise = (async () => {
        // 1. Try localStorage cache
        const cacheData = this._readCache(language);
        if (cacheData) {
          this._translations = cacheData.translations || {};
          this._meta = cacheData.meta || {};
          this._log(`Loaded ${language} from cache (${Object.keys(this._translations).length} keys)`);
          this._loaded = true;
          return;
        }

        // 2. Fetch from API
        try {
          const url = `${this.config.apiBase}/public/translations/${language}/`;
          const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const data = await resp.json();

          this._translations = data.translations || data.data?.translations || {};
          this._meta = data.meta || data.data?.meta || {};

          // Cache it
          this._writeCache(language, { translations: this._translations, meta: this._meta });
          this._log(`Loaded ${language} from API (${Object.keys(this._translations).length} keys)`);
        } catch (err) {
          this._log(`Failed to load ${language}, trying fallback: ${err.message}`, 'warn');
          // Try fallback language
          if (language !== this.config.fallbackLanguage) {
            await this._loadPack(this.config.fallbackLanguage);
          }
        }
        this._loaded = true;
      })();

      return this._loadPromise;
    }

    // ── Translation ─────────────────────────────────────────────

    /**
     * t('offer.title') → 'Available Offers'
     * t('earning.total', {count: 5}) → '5 total earnings'
     * t('pagination.of', {page: 2, total: 10}) → '2 of 10'
     */
    t(key, values = {}, fallback = null) {
      const template = this._translations[key];
      if (!template) {
        this._log(`Missing key: ${key}`, 'warn');
        return fallback || key;
      }
      if (!values || Object.keys(values).length === 0) {
        return template;
      }
      return this._format(template, values);
    }

    /**
     * Alias for t() — React-style
     */
    translate(key, values, fallback) {
      return this.t(key, values, fallback);
    }

    /**
     * Pluralization:
     * plural('earning.count', 5, {}, 'earnings') → '5 earnings'
     */
    plural(key, count, values = {}, defaultSuffix = '') {
      return this.t(key, { ...values, count });
    }

    // ── Language management ─────────────────────────────────────

    async setLanguage(language) {
      this._language = language;
      this._translations = {};
      this._meta = {};
      this._loaded = false;
      this._loadPromise = null;
      await this._loadPack(language);
      this._applyRTL();
      localStorage.setItem('loc_language', language);
      document.documentElement.lang = language;
      // Dispatch event for React/Vue to re-render
      window.dispatchEvent(new CustomEvent('localization:language-changed', {
        detail: { language, isRTL: this.isRTL() }
      }));
    }

    getLanguage() { return this._language; }
    isRTL() { return this._meta.is_rtl === true || this._meta.text_direction === 'rtl'; }
    getDirection() { return this.isRTL() ? 'rtl' : 'ltr'; }
    getBCP47() { return this._meta.bcp47 || this._language; }

    // ── RTL support ─────────────────────────────────────────────

    _applyRTL() {
      const dir = this.getDirection();
      document.documentElement.dir = dir;
      document.documentElement.lang = this.getBCP47();
      // Apply RTL class for CSS
      if (dir === 'rtl') {
        document.body.classList.add('rtl');
        document.body.classList.remove('ltr');
      } else {
        document.body.classList.add('ltr');
        document.body.classList.remove('rtl');
      }
    }

    // ── Currency formatting ─────────────────────────────────────

    /**
     * formatCurrency(1234.56, 'BDT') → '৳1,234.56'
     * formatCurrency(1234.56, 'EUR', 'de') → '1.234,56 €'
     */
    async formatCurrency(amount, currencyCode, language = null) {
      try {
        const lang = language || this._language;
        const url = `${this.config.apiBase}/currencies/format/?amount=${amount}&currency=${currencyCode}&lang=${lang}`;
        const resp = await fetch(url);
        if (resp.ok) {
          const data = await resp.json();
          return data.formatted || `${currencyCode} ${amount}`;
        }
      } catch (_) {}
      // Fallback: basic format
      return new Intl.NumberFormat(this._language, {
        style: 'currency', currency: currencyCode, maximumFractionDigits: 2
      }).format(amount);
    }

    /**
     * Synchronous currency format (uses Intl.NumberFormat)
     */
    formatCurrencySync(amount, currencyCode) {
      try {
        return new Intl.NumberFormat(this.getBCP47(), {
          style: 'currency', currency: currencyCode
        }).format(amount);
      } catch (_) {
        return `${currencyCode} ${Number(amount).toFixed(2)}`;
      }
    }

    // ── OTA updates ─────────────────────────────────────────────

    _startPolling() {
      this._pollingTimer = setInterval(async () => {
        try {
          const url = `${this.config.apiBase}/public/translations/${this._language}/checksum/`;
          const resp = await fetch(url);
          if (resp.ok) {
            const { checksum } = await resp.json();
            const cached = this._readCache(this._language);
            if (cached && cached.checksum !== checksum) {
              this._log(`New translations available for ${this._language} — refreshing`);
              this._invalidateCache(this._language);
              await this._loadPack(this._language);
              window.dispatchEvent(new CustomEvent('localization:updated', {
                detail: { language: this._language }
              }));
            }
          }
        } catch (_) {}
      }, this.config.pollInterval);
    }

    stopPolling() {
      if (this._pollingTimer) {
        clearInterval(this._pollingTimer);
        this._pollingTimer = null;
      }
    }

    // ── ICU formatting (client-side) ────────────────────────────

    _format(template, values) {
      let result = template;
      // Simple {key} replacement
      for (const [key, val] of Object.entries(values)) {
        result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), val);
      }
      // Basic plural: {count, plural, one {# item} other {# items}}
      result = result.replace(
        /\{(\w+),\s*plural,([^}]+(?:\{[^}]*\}[^}]*)*)\}/g,
        (match, varName, options) => {
          const count = values[varName] ?? 0;
          const opts = this._parsePluralOptions(options);
          const key = count === 1 ? 'one' : 'other';
          const tpl = opts[`=${count}`] || opts[key] || opts['other'] || match;
          return tpl.replace(/#/g, count);
        }
      );
      return result;
    }

    _parsePluralOptions(optionsStr) {
      const opts = {};
      const re = /(\S+)\s*\{([^}]*)\}/g;
      let m;
      while ((m = re.exec(optionsStr)) !== null) {
        opts[m[1]] = m[2];
      }
      return opts;
    }

    // ── Cache ──────────────────────────────────────────────────

    _readCache(language) {
      try {
        const raw = localStorage.getItem(`${this.config.cacheKey}_${language}`);
        if (!raw) return null;
        const data = JSON.parse(raw);
        if (Date.now() - data.timestamp > this.config.cacheMaxAge) {
          localStorage.removeItem(`${this.config.cacheKey}_${language}`);
          return null;
        }
        return data;
      } catch (_) { return null; }
    }

    _writeCache(language, data) {
      try {
        localStorage.setItem(`${this.config.cacheKey}_${language}`, JSON.stringify({
          ...data, timestamp: Date.now()
        }));
      } catch (_) {}
    }

    _invalidateCache(language) {
      try { localStorage.removeItem(`${this.config.cacheKey}_${language}`); } catch (_) {}
    }

    _log(msg, level = 'log') {
      if (this.config.debug) console[level](`[Localization] ${msg}`);
    }

    // ── React/Vue helpers ────────────────────────────────────────

    /**
     * React Hook usage:
     * const { t, language, setLanguage } = useLocalization();
     */
    getReactHook() {
      const client = this;
      return function useLocalization() {
        const [lang, setLang] = typeof React !== 'undefined'
          ? React.useState(client.getLanguage()) : [client.getLanguage(), () => {}];

        const changeLanguage = async (newLang) => {
          await client.setLanguage(newLang);
          setLang(newLang);
        };

        return {
          t: (key, values, fallback) => client.t(key, values, fallback),
          language: lang,
          setLanguage: changeLanguage,
          isRTL: client.isRTL(),
          direction: client.getDirection(),
        };
      };
    }
  }

  // ── Global instance factory ─────────────────────────────────────
  global.LocalizationClient = LocalizationClient;
  global.createLocalization = (config) => new LocalizationClient(config);

  // Auto-init if data-auto-init attribute present
  // <script src="localization-client.js" data-auto-init data-language="bn" data-api-base="/api/localization">
  if (typeof document !== 'undefined') {
    const script = document.currentScript;
    if (script && script.hasAttribute('data-auto-init')) {
      const lang = script.getAttribute('data-language') || null;
      const apiBase = script.getAttribute('data-api-base') || '/api/localization';
      global._loc = new LocalizationClient({ apiBase, debug: true });
      global._loc.init(lang).then(() => {
        window.dispatchEvent(new CustomEvent('localization:ready', { detail: global._loc }));
      });
    }
  }

  // ES Module export (for bundlers)
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LocalizationClient };
  }

})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : {}));
