# constants.py — World #1 Localization System constants
"""All magic numbers, strings, limits in one place"""

# ── Cache TTLs ──────────────────────────────────────────────────
CACHE_TTL_LANGUAGES    = 86400   # 24h
CACHE_TTL_COUNTRIES    = 86400
CACHE_TTL_CURRENCIES   = 86400
CACHE_TTL_TIMEZONES    = 86400
CACHE_TTL_TRANSLATIONS = 3600    # 1h
CACHE_TTL_USER_PREF    = 3600
CACHE_TTL_GEO_IP       = 86400
CACHE_TTL_EXCHANGE     = 3600
CACHE_TTL_COVERAGE     = 1800    # 30min
CACHE_TTL_ANALYTICS    = 1800

# ── Pagination ───────────────────────────────────────────────────
PAGE_SIZE_DEFAULT   = 20
PAGE_SIZE_MAX       = 200
PAGE_SIZE_LANGUAGES = 100
PAGE_SIZE_CITIES    = 50

# ── Translation limits ────────────────────────────────────────────
MAX_TRANSLATION_TEXT_LENGTH    = 5000
MAX_BULK_TRANSLATE_ITEMS       = 100
MAX_IMPORT_KEYS_PER_REQUEST    = 10000
MAX_TRANSLATION_KEY_LENGTH     = 255
MAX_TRANSLATION_VALUE_LENGTH   = 10000
TM_MIN_MATCH_SCORE             = 70    # %
TM_EXACT_MATCH_SCORE           = 100

# ── Provider priority ─────────────────────────────────────────────
PROVIDER_PRIORITY_DEEPL   = 1
PROVIDER_PRIORITY_GOOGLE  = 2
PROVIDER_PRIORITY_AZURE   = 3
PROVIDER_PRIORITY_AMAZON  = 4
PROVIDER_PRIORITY_OPENAI  = 5

# ── Quality scores ─────────────────────────────────────────────────
QUALITY_EXCELLENT_THRESHOLD = 90
QUALITY_GOOD_THRESHOLD      = 70
QUALITY_FAIR_THRESHOLD      = 50

# ── Language codes ────────────────────────────────────────────────
RTL_LANGUAGES   = ('ar', 'he', 'fa', 'ur', 'ps', 'sd', 'ug', 'yi', 'ku')
DEFAULT_LANGUAGE = 'en'
FALLBACK_LANGUAGE = 'en'

CJK_LANGUAGES   = ('zh', 'ja', 'ko')
INDIC_LANGUAGES = ('hi', 'bn', 'ta', 'te', 'ml', 'kn', 'mr', 'gu', 'pa', 'ne', 'si')

# ── CPAlead-specific ──────────────────────────────────────────────
CPALEAD_SUPPORTED_LANGUAGES = (
    'en', 'bn', 'hi', 'ar', 'ur', 'es', 'fr', 'de', 'zh',
    'id', 'ms', 'ta', 'ne', 'tr', 'si', 'pt', 'ru', 'ja',
    'ko', 'vi', 'th', 'fil', 'sw',
)
CPALEAD_SUPPORTED_CURRENCIES = (
    'USD', 'BDT', 'INR', 'EUR', 'GBP', 'PKR', 'NPR', 'LKR',
    'IDR', 'MYR', 'THB', 'VND', 'PHP', 'BRL', 'MXN', 'NGN',
    'EGP', 'SAR', 'AED', 'TRY', 'JPY', 'KRW', 'CAD', 'AUD',
)
EARNING_DISPLAY_DECIMAL_PLACES = 2
MIN_WITHDRAWAL_CURRENCY_DISPLAY = 10.0

# ── Analytics events ──────────────────────────────────────────────
EVENT_TRANSLATION_REQUEST     = 'translation_requested'
EVENT_TRANSLATION_MISSING     = 'translation_missing'
EVENT_LANGUAGE_SWITCH         = 'language_switch'
EVENT_CURRENCY_CONVERTED      = 'currency_converted'
EVENT_GEOLOCATION_LOOKUP      = 'geolocation_lookup'
EVENT_USER_PREF_UPDATED       = 'user_preference_updated'
EVENT_OFFER_VIEWED            = 'offer_viewed'
EVENT_REGION_DETECTED         = 'region_detected'
EVENT_LANGUAGE_PACK_DOWNLOAD  = 'language_pack_downloaded'

# ── Mime types / export formats ───────────────────────────────────
EXPORT_FORMAT_JSON  = 'json'
EXPORT_FORMAT_PO    = 'po'
EXPORT_FORMAT_XLIFF = 'xliff'
EXPORT_FORMAT_CSV   = 'csv'
EXPORT_FORMATS = (EXPORT_FORMAT_JSON, EXPORT_FORMAT_PO, EXPORT_FORMAT_XLIFF, EXPORT_FORMAT_CSV)

# ── GeoIP ─────────────────────────────────────────────────────────
GEOIP_CACHE_DAYS    = 30
GEOIP_TIMEOUT_SECS  = 5
GEOIP_FALLBACK_URL  = 'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,city,lat,lon,timezone,isp,proxy,hosting'

# ── Content ──────────────────────────────────────────────────────
CONTENT_TYPES = (
    'offer', 'landing_page', 'email', 'push_notification',
    'blog_post', 'faq', 'legal', 'product', 'category',
    'banner', 'popup', 'tooltip', 'error_message',
)
