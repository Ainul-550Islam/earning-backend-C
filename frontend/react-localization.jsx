/**
 * React Localization Provider — World #1 System
 * Usage:
 *   import { LocalizationProvider, useTranslation, useCurrency } from './react-localization'
 *
 *   <LocalizationProvider defaultLanguage="bn" apiBase="/api/localization">
 *     <App />
 *   LocalizationProvider>
 *
 *   function MyComponent() {
 *     const { t, language, setLanguage, isRTL } = useTranslation()
 *     const { format, convert } = useCurrency()
 *     return <div dir={isRTL ? 'rtl' : 'ltr'}>{t('offer.title')}</div>
 *   }
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

// ── Context ─────────────────────────────────────────────────────
const LocalizationContext = createContext(null);

// ── Provider ─────────────────────────────────────────────────────
export function LocalizationProvider({
  children,
  defaultLanguage = 'en',
  fallbackLanguage = 'en',
  apiBase = '/api/localization',
  namespace = 'global',
  autoDetect = true,
  pollInterval = 0,
}) {
  const [language, setLanguageState] = useState(defaultLanguage);
  const [translations, setTranslations] = useState({});
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const cache = useRef({});
  const pollTimer = useRef(null);

  // ── Load language pack ────────────────────────────────────────
  const loadPack = useCallback(async (lang) => {
    // Check memory cache
    if (cache.current[lang]) {
      setTranslations(cache.current[lang].translations);
      setMeta(cache.current[lang].meta);
      return;
    }
    // Check localStorage cache
    try {
      const stored = localStorage.getItem(`loc_pack_${lang}_${namespace}`);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Date.now() - parsed.timestamp < 86400000) { // 24h
          cache.current[lang] = parsed;
          setTranslations(parsed.translations);
          setMeta(parsed.meta || {});
          return;
        }
      }
    } catch (_) {}

    // Fetch from API
    try {
      const res = await fetch(`${apiBase}/public/translations/${lang}/`, {
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const pack = {
        translations: data.translations || data.data?.translations || {},
        meta: data.meta || data.data?.meta || {},
        timestamp: Date.now(),
      };
      cache.current[lang] = pack;
      // Save to localStorage
      try {
        localStorage.setItem(`loc_pack_${lang}_${namespace}`, JSON.stringify(pack));
      } catch (_) {}
      setTranslations(pack.translations);
      setMeta(pack.meta);
    } catch (err) {
      if (lang !== fallbackLanguage) {
        await loadPack(fallbackLanguage);
      } else {
        setError(err.message);
      }
    }
  }, [apiBase, namespace, fallbackLanguage]);

  // ── Init ─────────────────────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      let lang = defaultLanguage;
      if (autoDetect) {
        lang = localStorage.getItem('loc_language')
          || document.documentElement.lang?.split('-')[0]
          || navigator.language?.split('-')[0]?.toLowerCase()
          || defaultLanguage;
      }
      setLanguageState(lang);
      await loadPack(lang);
      setLoading(false);
    };
    init();
  }, []);

  // ── OTA polling ───────────────────────────────────────────────
  useEffect(() => {
    if (!pollInterval) return;
    pollTimer.current = setInterval(async () => {
      try {
        const res = await fetch(`${apiBase}/public/ota-checksum/${language}/`);
        if (res.ok) {
          const { checksum } = await res.json();
          const cached = cache.current[language];
          if (cached?.checksum && cached.checksum !== checksum) {
            delete cache.current[language];
            localStorage.removeItem(`loc_pack_${language}_${namespace}`);
            await loadPack(language);
          }
        }
      } catch (_) {}
    }, pollInterval);
    return () => clearInterval(pollTimer.current);
  }, [language, pollInterval]);

  // ── Apply RTL ─────────────────────────────────────────────────
  useEffect(() => {
    const isRTL = meta.is_rtl === true || meta.text_direction === 'rtl';
    document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
    document.documentElement.lang = meta.bcp47 || language;
    document.body.classList.toggle('rtl', isRTL);
    document.body.classList.toggle('ltr', !isRTL);
  }, [meta, language]);

  // ── Set language ──────────────────────────────────────────────
  const setLanguage = useCallback(async (lang) => {
    setLoading(true);
    setLanguageState(lang);
    localStorage.setItem('loc_language', lang);
    await loadPack(lang);
    setLoading(false);
  }, [loadPack]);

  // ── Translate function ────────────────────────────────────────
  const t = useCallback((key, values = {}, fallback = null) => {
    const template = translations[key];
    if (!template) return fallback || key;
    if (!values || Object.keys(values).length === 0) return template;
    // Simple {key} interpolation
    let result = template;
    for (const [k, v] of Object.entries(values)) {
      result = result.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    }
    // Basic plural
    result = result.replace(
      /\{(\w+),\s*plural,([^}]+(?:\{[^}]*\}[^}]*)*)\}/g,
      (match, varName, options) => {
        const count = values[varName] ?? 0;
        const opts = {};
        const re = /(\S+)\s*\{([^}]*)\}/g;
        let m;
        while ((m = re.exec(options)) !== null) opts[m[1]] = m[2];
        const form = count === 1 ? 'one' : 'other';
        return (opts[`=${count}`] || opts[form] || opts['other'] || match).replace(/#/g, count);
      }
    );
    return result;
  }, [translations]);

  const isRTL = meta.is_rtl === true || meta.text_direction === 'rtl';

  const value = {
    t, language, setLanguage, loading, error,
    isRTL, direction: isRTL ? 'rtl' : 'ltr',
    meta, translations,
    bcp47: meta.bcp47 || language,
  };

  return (
    <LocalizationContext.Provider value={value}>
      {children}
    </LocalizationContext.Provider>
  );
}

// ── Hooks ─────────────────────────────────────────────────────────
export function useTranslation() {
  const ctx = useContext(LocalizationContext);
  if (!ctx) throw new Error('useTranslation must be used inside LocalizationProvider');
  return ctx;
}

export function useCurrency() {
  const { language } = useTranslation();

  const format = useCallback((amount, currencyCode) => {
    try {
      return new Intl.NumberFormat(language, {
        style: 'currency', currency: currencyCode
      }).format(amount);
    } catch (_) {
      return `${currencyCode} ${Number(amount).toFixed(2)}`;
    }
  }, [language]);

  const formatAsync = useCallback(async (amount, currencyCode, apiBase = '/api/localization') => {
    try {
      const res = await fetch(`${apiBase}/currencies/format/?amount=${amount}&currency=${currencyCode}&lang=${language}`);
      if (res.ok) {
        const data = await res.json();
        return data.formatted;
      }
    } catch (_) {}
    return format(amount, currencyCode);
  }, [language, format]);

  return { format, formatAsync };
}

// ── HOC ───────────────────────────────────────────────────────────
export function withTranslation(Component) {
  return function TranslatedComponent(props) {
    const localization = useTranslation();
    return <Component {...props} {...localization} />;
  };
}

// ── Trans component ───────────────────────────────────────────────
export function Trans({ i18nKey, values, fallback, children }) {
  const { t } = useTranslation();
  return React.createElement(React.Fragment, null, t(i18nKey, values, fallback || children));
}
