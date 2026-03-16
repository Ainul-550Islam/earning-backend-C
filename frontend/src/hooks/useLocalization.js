// src/hooks/useI18n.js
import { useState, useEffect, useCallback } from 'react';
import i18nAPI from '../api/endpoints/i18n';


// ─── 1. Languages ──────────────────────────────────────────────────────────
export const useLanguages = (initialParams = {}) => {
  const [languages, setLanguages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchLanguages = useCallback(async () => {
    try {
      setLoading(true);
      const res = await i18nAPI.getLanguages(params);
      setLanguages(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Languages load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchLanguages(); }, [fetchLanguages]);

  const createLanguage = async (data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.createLanguage(data);
      setLanguages(prev => [...prev, res.data]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateLanguage = async (id, data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.updateLanguage(id, data);
      setLanguages(prev => prev.map(l => l.id === id ? res.data : l));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteLanguage = async (id) => {
    await i18nAPI.deleteLanguage(id);
    setLanguages(prev => prev.filter(l => l.id !== id));
  };

  const setDefault = async (id) => {
    await i18nAPI.setDefaultLanguage(id);
    setLanguages(prev => prev.map(l => ({ ...l, is_default: l.id === id })));
  };

  return {
    languages, loading, saving, error,
    setParams, refetch: fetchLanguages,
    createLanguage, updateLanguage, deleteLanguage, setDefault,
    activeLanguages: languages.filter(l => l.is_active),
    defaultLanguage: languages.find(l => l.is_default),
    rtlLanguages: languages.filter(l => l.is_rtl),
  };
};


// ─── 2. Countries ──────────────────────────────────────────────────────────
export const useCountries = (initialParams = {}) => {
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchCountries = useCallback(async () => {
    try {
      setLoading(true);
      const res = await i18nAPI.getCountries(params);
      setCountries(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Countries load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchCountries(); }, [fetchCountries]);

  const createCountry = async (data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.createCountry(data);
      setCountries(prev => [...prev, res.data]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateCountry = async (id, data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.updateCountry(id, data);
      setCountries(prev => prev.map(c => c.id === id ? res.data : c));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteCountry = async (id) => {
    await i18nAPI.deleteCountry(id);
    setCountries(prev => prev.filter(c => c.id !== id));
  };

  return {
    countries, loading, saving, error,
    setParams, refetch: fetchCountries,
    createCountry, updateCountry, deleteCountry,
    activeCountries: countries.filter(c => c.is_active),
  };
};


// ─── 3. Currencies ─────────────────────────────────────────────────────────
export const useCurrencies = (initialParams = {}) => {
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchCurrencies = useCallback(async () => {
    try {
      setLoading(true);
      const res = await i18nAPI.getCurrencies(params);
      setCurrencies(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Currencies load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchCurrencies(); }, [fetchCurrencies]);

  const createCurrency = async (data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.createCurrency(data);
      setCurrencies(prev => [...prev, res.data]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateCurrency = async (id, data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.updateCurrency(id, data);
      setCurrencies(prev => prev.map(c => c.id === id ? res.data : c));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteCurrency = async (id) => {
    await i18nAPI.deleteCurrency(id);
    setCurrencies(prev => prev.filter(c => c.id !== id));
  };

  const setDefault = async (id) => {
    await i18nAPI.setDefaultCurrency(id);
    setCurrencies(prev => prev.map(c => ({ ...c, is_default: c.id === id })));
  };

  const updateRate = async (id, rate) => {
    const res = await i18nAPI.updateExchangeRate(id, rate);
    setCurrencies(prev => prev.map(c => c.id === id ? res.data : c));
  };

  return {
    currencies, loading, saving, error,
    setParams, refetch: fetchCurrencies,
    createCurrency, updateCurrency, deleteCurrency, setDefault, updateRate,
    activeCurrencies: currencies.filter(c => c.is_active),
    defaultCurrency: currencies.find(c => c.is_default),
    staleRateCurrencies: currencies.filter(c => c.needs_exchange_update),
  };
};


// ─── 4. Timezones ──────────────────────────────────────────────────────────
export const useTimezones = (initialParams = {}) => {
  const [timezones, setTimezones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchTimezones = useCallback(async () => {
    try {
      setLoading(true);
      const res = await i18nAPI.getTimezones(params);
      setTimezones(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Timezones load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchTimezones(); }, [fetchTimezones]);

  return {
    timezones, loading, error,
    setParams, refetch: fetchTimezones,
    activeTimezones: timezones.filter(t => t.is_active),
  };
};


// ─── 5. Translations (main editor) ────────────────────────────────────────
export const useTranslations = (initialParams = {}) => {
  const [translations, setTranslations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchTranslations = useCallback(async () => {
    try {
      setLoading(true);
      const res = await i18nAPI.getTranslations(params);
      setTranslations(res.data.results || res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Translations load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchTranslations(); }, [fetchTranslations]);

  const createTranslation = async (data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.createTranslation(data);
      setTranslations(prev => [res.data, ...prev]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateTranslation = async (id, data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.updateTranslation(id, data);
      setTranslations(prev => prev.map(t => t.id === id ? res.data : t));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteTranslation = async (id) => {
    await i18nAPI.deleteTranslation(id);
    setTranslations(prev => prev.filter(t => t.id !== id));
  };

  const approveTranslation = async (id) => {
    await i18nAPI.approveTranslation(id);
    setTranslations(prev =>
      prev.map(t => t.id === id ? { ...t, is_approved: true } : t)
    );
  };

  const bulkApprove = async (ids) => {
    await i18nAPI.bulkApprove(ids);
    setTranslations(prev =>
      prev.map(t => ids.includes(t.id) ? { ...t, is_approved: true } : t)
    );
  };

  return {
    translations, loading, saving, error,
    setParams, refetch: fetchTranslations,
    createTranslation, updateTranslation, deleteTranslation,
    approveTranslation, bulkApprove,
    pendingTranslations: translations.filter(t => !t.is_approved),
    autoTranslations: translations.filter(t => t.source === 'auto'),
  };
};


// ─── 6. Translation Keys ───────────────────────────────────────────────────
export const useTranslationKeys = (initialParams = {}) => {
  const [keys, setKeys] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [params, setParams] = useState(initialParams);

  const fetchKeys = useCallback(async () => {
    try {
      setLoading(true);
      const [keysRes, catsRes] = await Promise.all([
        i18nAPI.getTranslationKeys(params),
        i18nAPI.getCategories(),
      ]);
      setKeys(keysRes.data.results || keysRes.data);
      setCategories(catsRes.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Translation keys load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const createKey = async (data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.createTranslationKey(data);
      setKeys(prev => [res.data, ...prev]);
      return res.data;
    } finally { setSaving(false); }
  };

  const updateKey = async (id, data) => {
    setSaving(true);
    try {
      const res = await i18nAPI.updateTranslationKey(id, data);
      setKeys(prev => prev.map(k => k.id === id ? res.data : k));
      return res.data;
    } finally { setSaving(false); }
  };

  const deleteKey = async (id) => {
    await i18nAPI.deleteTranslationKey(id);
    setKeys(prev => prev.filter(k => k.id !== id));
  };

  return {
    keys, categories, loading, saving, error,
    setParams, refetch: fetchKeys,
    createKey, updateKey, deleteKey,
    htmlKeys: keys.filter(k => k.is_html),
    pluralKeys: keys.filter(k => k.is_plural),
  };
};


// ─── 7. Missing Translations ───────────────────────────────────────────────
export const useMissingTranslations = (initialParams = {}) => {
  const [missing, setMissing] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [params, setParams] = useState({ resolved: false, ...initialParams });

  const fetchMissing = useCallback(async () => {
    try {
      setLoading(true);
      const [listRes, statsRes] = await Promise.all([
        i18nAPI.getMissingTranslations(params),
        i18nAPI.getMissingStats(),
      ]);
      setMissing(listRes.data.results || listRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Missing translations load failed');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetchMissing(); }, [fetchMissing]);

  const resolve = async (id) => {
    await i18nAPI.resolveMissing(id);
    setMissing(prev => prev.filter(m => m.id !== id));
  };

  const bulkResolve = async (ids) => {
    await i18nAPI.bulkResolveMissing(ids);
    setMissing(prev => prev.filter(m => !ids.includes(m.id)));
  };

  return {
    missing, stats, loading, error,
    setParams, refetch: fetchMissing,
    resolve, bulkResolve,
    totalMissing: stats?.total || missing.length,
    byLanguage: stats?.by_language || [],
  };
};