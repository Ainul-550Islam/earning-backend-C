# =============================================================================
# SETTINGS_GUIDE.py — Copy these to your settings.py
# promotions app — World-class production configuration
# =============================================================================

# ── Installed Apps ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # ... existing apps ...
    'promotions',
    'django_celery_beat',
    'django_celery_results',
    'rest_framework',
    'corsheaders',
    'django_filters',
]

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ── Import Promotions Beat Schedule ──────────────────────────────────────────
from api.promotions.celery_config.beat_schedule import PROMOTIONS_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {
    **getattr(globals(), 'CELERY_BEAT_SCHEDULE', {}),
    **PROMOTIONS_BEAT_SCHEDULE,
}

# ── Redis Cache ───────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
        },
        'TIMEOUT': 300,
    }
}

# ── Site URL ─────────────────────────────────────────────────────────────────
SITE_URL = 'https://yourplatform.com'  # Change to your domain

# ── Firebase (FCM Push) ───────────────────────────────────────────────────────
FCM_SERVER_KEY = ''        # Get from Firebase Console
FCM_PROJECT_ID = ''        # Firebase project ID

# ── APNs (iOS Push) ──────────────────────────────────────────────────────────
APNS_BUNDLE_ID = 'com.yourplatform.app'
APNS_AUTH_KEY = ''         # .p8 key content
APNS_KEY_ID = ''           # 10-char key ID
APNS_TEAM_ID = ''          # Apple Team ID
APNS_SANDBOX = True        # False in production

# ── Twilio (SMS) ──────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = ''
TWILIO_AUTH_TOKEN = ''
TWILIO_FROM_NUMBER = ''

# ── Crypto Payments ───────────────────────────────────────────────────────────
USDT_MINIMUM_PAYOUT = 25.00     # Minimum USDT withdrawal
BTC_MINIMUM_PAYOUT = 50.00      # Minimum BTC withdrawal
CRYPTO_PAYOUT_HOT_WALLET_TRC20 = ''   # Your TRC20 wallet for sending USDT
CRYPTO_PAYOUT_HOT_WALLET_ETH = ''     # Your ETH wallet

# ── Payment Gateways ──────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = ''
STRIPE_PUBLISHABLE_KEY = ''
STRIPE_WEBHOOK_SECRET = ''
PAYPAL_CLIENT_ID = ''
PAYPAL_CLIENT_SECRET = ''
PAYPAL_MODE = 'sandbox'  # 'live' in production

# ── Anti-fraud ────────────────────────────────────────────────────────────────
FRAUD_DETECTION_ENABLED = True
MIN_FRAUD_SCORE_THRESHOLD = 0.75  # Block if score > 0.75
MAX_SUBMISSIONS_PER_IP_PER_DAY = 10
MAX_SUBMISSIONS_PER_USER_PER_DAY = 50

# ── Publisher Settings ────────────────────────────────────────────────────────
PUBLISHER_MIN_PAYOUT_USD = 10.00
PUBLISHER_DAILY_PAYOUT_THRESHOLD = 10.00
FIRST_PAYOUT_BONUS_RATE = 0.20     # 20% first payout bonus
WELCOME_BONUS_USD = 2.00           # $2 signup bonus

# ── Platform Commission ───────────────────────────────────────────────────────
PLATFORM_COMMISSION_RATE = 0.20    # 20% platform cut
REFERRAL_COMMISSION_RATE_L1 = 0.05  # 5% level 1 referral
REFERRAL_COMMISSION_RATE_L2 = 0.02  # 2% level 2 referral
REFERRAL_COMMISSION_RATE_L3 = 0.01  # 1% level 3 referral

# ── Content Locking ───────────────────────────────────────────────────────────
CONTENT_LOCK_DEFAULT_TTL = 3600 * 24    # 24h unlock validity
CONTENT_LOCK_OFFERS_REQUIRED = 1         # Default: 1 offer to unlock

# ── RTB Settings ─────────────────────────────────────────────────────────────
RTB_AUCTION_INTERVAL_SECONDS = 60
RTB_MIN_FLOOR_PRICE = 0.01
RTB_MAX_BIDS_PER_AUCTION = 100

# ── Email ─────────────────────────────────────────────────────────────────────
DEFAULT_FROM_EMAIL = 'noreply@yourplatform.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = ''  # SendGrid API key

# ── Security ─────────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'https://yourplatform.com',
    'https://www.yourplatform.com',
]

# ── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '2000/hour',
    },
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ── Promotions App Config ─────────────────────────────────────────────────────
PROMOTIONS_CONFIG = {
    'OFFERWALL_OFFERS_PER_PAGE': 20,
    'SMARTLINK_RESCORE_INTERVAL': 600,         # 10 minutes
    'SUBID_MAX_LENGTH': 64,
    'QUIZ_SESSION_TTL': 3600,                   # 1 hour
    'CPC_DEDUP_WINDOW': 3600,                   # 1 hour same visitor
    'CPI_INSTALL_DEDUP_DAYS': 30,               # 30 days install dedup
    'LEADERBOARD_CACHE_TTL': 300,               # 5 minutes
    'PUBLISHER_DASHBOARD_CACHE_TTL': 120,        # 2 minutes
    'VIRTUAL_CURRENCY_ROUNDING': 'floor',
    'EMAIL_SUBMIT_DEDUP_TTL': 3600 * 24 * 365,  # 1 year dedup
    'WHITE_LABEL_CUSTOM_DOMAINS': True,
    'PAY_PER_CALL_MIN_DURATION': 60,             # 60 seconds minimum
    'API_KEY_RATE_LIMIT': 1000,                  # per hour
}
