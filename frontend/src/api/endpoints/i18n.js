// src/api/endpoints/i18n.js
import client from '../client';

const i18nAPI = {

  // ─── LANGUAGES ────────────────────────────────────────────────────────────

  getLanguages: (params = {}) =>
    client.get('/i18n/languages/', { params }),
  // params: { is_active, is_default, is_rtl, page }

  getLanguage: (id) =>
    client.get(`/i18n/languages/${id}/`),

  createLanguage: (data) =>
    client.post('/i18n/languages/', data),
  // data: { code, name, name_native, is_active, is_default, is_rtl, flag_emoji, locale_code }

  updateLanguage: (id, data) =>
    client.patch(`/i18n/languages/${id}/`, data),

  deleteLanguage: (id) =>
    client.delete(`/i18n/languages/${id}/`),

  setDefaultLanguage: (id) =>
    client.patch(`/i18n/languages/${id}/`, { is_default: true }),


  // ─── COUNTRIES ────────────────────────────────────────────────────────────

  getCountries: (params = {}) =>
    client.get('/i18n/countries/', { params }),
  // params: { is_active, page }

  getCountry: (id) =>
    client.get(`/i18n/countries/${id}/`),

  createCountry: (data) =>
    client.post('/i18n/countries/', data),
  // data: { code, name, phone_code, phone_digits, flag_emoji, is_active }

  updateCountry: (id, data) =>
    client.patch(`/i18n/countries/${id}/`, data),

  deleteCountry: (id) =>
    client.delete(`/i18n/countries/${id}/`),


  // ─── CURRENCIES ───────────────────────────────────────────────────────────

  getCurrencies: (params = {}) =>
    client.get('/i18n/currencies/', { params }),

  getCurrency: (id) =>
    client.get(`/i18n/currencies/${id}/`),

  createCurrency: (data) =>
    client.post('/i18n/currencies/', data),
  // data: { code, name, symbol, decimal_digits, is_active, is_default, exchange_rate }

  updateCurrency: (id, data) =>
    client.patch(`/i18n/currencies/${id}/`, data),

  deleteCurrency: (id) =>
    client.delete(`/i18n/currencies/${id}/`),

  setDefaultCurrency: (id) =>
    client.patch(`/i18n/currencies/${id}/`, { is_default: true }),

  updateExchangeRate: (id, rate) =>
    client.patch(`/i18n/currencies/${id}/`, { exchange_rate: rate }),


  // ─── TIMEZONES ────────────────────────────────────────────────────────────

  getTimezones: (params = {}) =>
    client.get('/i18n/timezones/', { params }),

  getTimezone: (id) =>
    client.get(`/i18n/timezones/${id}/`),

  createTimezone: (data) =>
    client.post('/i18n/timezones/', data),

  updateTimezone: (id, data) =>
    client.patch(`/i18n/timezones/${id}/`, data),

  deleteTimezone: (id) =>
    client.delete(`/i18n/timezones/${id}/`),


  // ─── CITIES ───────────────────────────────────────────────────────────────

  getCities: (params = {}) =>
    client.get('/i18n/cities/', { params }),
  // params: { country, is_active, is_capital, page }

  getCitiesByCountry: (countryCode) =>
    client.get('/i18n/cities/', { params: { country__code: countryCode, is_active: true } }),

  getCity: (id) =>
    client.get(`/i18n/cities/${id}/`),

  createCity: (data) =>
    client.post('/i18n/cities/', data),

  updateCity: (id, data) =>
    client.patch(`/i18n/cities/${id}/`, data),

  deleteCity: (id) =>
    client.delete(`/i18n/cities/${id}/`),


  // ─── TRANSLATION KEYS ─────────────────────────────────────────────────────

  getTranslationKeys: (params = {}) =>
    client.get('/i18n/translation-keys/', { params }),
  // params: { category, is_plural, is_html, search, page }

  getTranslationKey: (id) =>
    client.get(`/i18n/translation-keys/${id}/`),

  createTranslationKey: (data) =>
    client.post('/i18n/translation-keys/', data),
  // data: { key, description, category, context, is_plural, is_html, max_length }

  updateTranslationKey: (id, data) =>
    client.patch(`/i18n/translation-keys/${id}/`, data),

  deleteTranslationKey: (id) =>
    client.delete(`/i18n/translation-keys/${id}/`),

  getCategories: () =>
    client.get('/i18n/translation-keys/categories/'),


  // ─── TRANSLATIONS ─────────────────────────────────────────────────────────

  getTranslations: (params = {}) =>
    client.get('/i18n/translations/', { params }),
  // params: { language, key, is_approved, source, page }

  getTranslation: (id) =>
    client.get(`/i18n/translations/${id}/`),

  createTranslation: (data) =>
    client.post('/i18n/translations/', data),
  // data: { key, language, value, value_plural, source, is_approved }

  updateTranslation: (id, data) =>
    client.patch(`/i18n/translations/${id}/`, data),

  deleteTranslation: (id) =>
    client.delete(`/i18n/translations/${id}/`),

  approveTranslation: (id) =>
    client.patch(`/i18n/translations/${id}/`, { is_approved: true }),

  bulkApprove: (ids) =>
    client.post('/i18n/translations/bulk-approve/', { ids }),

  bulkCreate: (translations) =>
    client.post('/i18n/translations/bulk-create/', { translations }),
  // translations: [{ key_id, language_id, value, source }, ...]

  exportTranslations: (languageCode, format = 'json') =>
    client.get('/i18n/translations/export/', { params: { language: languageCode, format } }),

  importTranslations: (formData) =>
    client.post('/i18n/translations/import/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),


  // ─── TRANSLATION CACHE ────────────────────────────────────────────────────

  getCacheStats: () =>
    client.get('/i18n/translation-cache/stats/'),

  clearCache: (languageCode = null) =>
    client.post('/i18n/translation-cache/clear/', { language_code: languageCode }),

  clearExpiredCache: () =>
    client.post('/i18n/translation-cache/clear-expired/'),


  // ─── MISSING TRANSLATIONS ─────────────────────────────────────────────────

  getMissingTranslations: (params = {}) =>
    client.get('/i18n/missing-translations/', { params }),
  // params: { language, resolved, page }

  resolveMissing: (id) =>
    client.patch(`/i18n/missing-translations/${id}/`, { resolved: true }),

  bulkResolveMissing: (ids) =>
    client.post('/i18n/missing-translations/bulk-resolve/', { ids }),

  getMissingStats: () =>
    client.get('/i18n/missing-translations/stats/'),


  // ─── USER LANGUAGE PREFERENCES ────────────────────────────────────────────

  getUserPreference: (userId) =>
    client.get(`/i18n/user-preferences/${userId}/`),

  updateUserPreference: (userId, data) =>
    client.patch(`/i18n/user-preferences/${userId}/`, data),
  // data: { primary_language, ui_language, content_language, auto_translate }

};

export default i18nAPI;