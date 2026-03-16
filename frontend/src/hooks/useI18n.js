export const useLanguages = () => ({ languages: [], loading: false, error: null, refetch: () => {} });
export const useCountries = () => ({ countries: [], loading: false, error: null, refetch: () => {} });
export const useCurrencies = () => ({ currencies: [], loading: false, error: null, staleRateCurrencies: [], refetch: () => {} });
export const useTimezones = () => ({ timezones: [], loading: false, error: null, refetch: () => {} });
export const useTranslations = () => ({ translations: [], pendingTranslations: [], loading: false, error: null, refetch: () => {} });
export const useTranslationKeys = () => ({ keys: [], categories: [], loading: false, error: null, refetch: () => {} });
export const useMissingTranslations = () => ({ missing: [], loading: false, error: null, refetch: () => {} });