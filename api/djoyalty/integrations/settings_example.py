# api/djoyalty/integrations/settings_example.py
"""
Djoyalty Integration Settings -- Complete Configuration Guide।
এই file থেকে copy করে আপনার settings.py এ রাখুন।

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
সব integration optional -- শুধু যেটা দরকার সেটা configure করুন।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ─── Core Djoyalty Settings ───────────────────────────────────────────────────
DJOYALTY = {
    'DEFAULT_EARN_RATE': 1,          # 1 point per 1 BDT
    'DEFAULT_POINT_VALUE': 0.01,     # 1 point = 0.01 BDT
    'DEFAULT_EXPIRY_DAYS': 365,      # Points expire in 1 year
    'CURRENCY': 'BDT',
    'CASHOUT_ENABLED': True,
    'SPIN_WHEEL_ENABLED': True,
    'QR_EARN_ENABLED': True,
    'RECEIPT_SCAN_ENABLED': True,
    'FAMILY_ACCOUNTS_ENABLED': True,
    'ECO_LOYALTY_ENABLED': True,
    'AI_PERSONALIZATION_ENABLED': True,
    'REDEMPTION_AUTO_APPROVE_THRESHOLD': 1000,   # Points below this = auto approve
    'MAX_DAILY_EARN': 10000,
}

# ─── bKash Integration ────────────────────────────────────────────────────────
DJOYALTY_BKASH = {
    'APP_KEY': 'your-bkash-app-key',          # from bKash merchant portal
    'APP_SECRET': 'your-bkash-app-secret',
    'USERNAME': 'your-bkash-username',
    'PASSWORD': 'your-bkash-password',
    'SANDBOX': True,  # Set False in production
}
# Callback URL for bKash redirect
BKASH_CALLBACK_URL = 'https://yourdomain.com/api/loyalty/payments/bkash/callback/'

# ─── Nagad Integration ────────────────────────────────────────────────────────
DJOYALTY_NAGAD = {
    'MERCHANT_ID': 'your-nagad-merchant-id',
    'MERCHANT_NUMBER': '01XXXXXXXXX',
    'PUBLIC_KEY': 'base64-encoded-nagad-public-key',
    'PRIVATE_KEY': 'base64-encoded-merchant-private-key',
    'SANDBOX': True,
}
NAGAD_CALLBACK_URL = 'https://yourdomain.com/api/loyalty/payments/nagad/callback/'

# ─── SSLCommerz Integration ───────────────────────────────────────────────────
DJOYALTY_SSLCOMMERZ = {
    'STORE_ID': 'your-sslcommerz-store-id',
    'STORE_PASSWD': 'your-sslcommerz-password',
    'SANDBOX': True,
}
SSLCOMMERZ_IPN_URL = 'https://yourdomain.com/api/loyalty/payments/sslcommerz/ipn/'

# ─── SMS Settings ─────────────────────────────────────────────────────────────
DJOYALTY_SMS_PROVIDER = 'bulksmsbd'   # 'bulksmsbd' | 'sslwireless' | 'twilio'

DJOYALTY_SMS = {
    # BulkSMSBD (Bangladesh -- most popular)
    'BULKSMSBD': {
        'API_KEY': 'your-bulksmsbd-api-key',   # from bulksmsbd.com
        'SENDER_ID': 'YourBrand',              # Approved sender ID
    },
    # SSL Wireless
    'SSLWIRELESS': {
        'API_TOKEN': 'your-ssl-wireless-token',
        'SID': 'your-sid',
    },
    # Twilio (International)
    'TWILIO': {
        'ACCOUNT_SID': 'ACxxxxxxxxxxxxxxxx',
        'AUTH_TOKEN': 'your-auth-token',
        'FROM_NUMBER': '+1234567890',
    },
}

# ─── Email Settings ───────────────────────────────────────────────────────────
DJOYALTY_EMAIL_PROVIDER = 'smtp'     # 'smtp' | 'sendgrid' | 'mailgun'
DJOYALTY_EMAIL_FROM = 'loyalty@yourbrand.com'

# Django SMTP (built-in)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'

# SendGrid (alternative)
DJOYALTY_SENDGRID_API_KEY = 'SG.xxxxxxxxxxxxxxxx'

# Mailgun (alternative)
DJOYALTY_MAILGUN_API_KEY = 'key-xxxxxxxx'
DJOYALTY_MAILGUN_DOMAIN = 'mg.yourdomain.com'

# ─── Firebase FCM (Push Notifications) ───────────────────────────────────────
# Option 1: JSON file path
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/path/to/firebase-credentials.json'

# Option 2: Dict directly in settings
DJOYALTY_FIREBASE_CREDENTIALS = {
    'type': 'service_account',
    'project_id': 'your-project-id',
    'private_key_id': 'key-id',
    'private_key': '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n',
    'client_email': 'firebase-adminsdk@your-project.iam.gserviceaccount.com',
    'client_id': '123456789',
    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
    'token_uri': 'https://oauth2.googleapis.com/token',
}

# ─── Google Vision OCR (Receipt Scanning) ────────────────────────────────────
DJOYALTY_GOOGLE_VISION_API_KEY = 'AIzaxxxxxxxxxxxxxxxx'

# ─── Celery (Background Tasks) ────────────────────────────────────────────────
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULE = {
    # Points expiry -- daily at midnight
    'expire-points-daily': {
        'task': 'djoyalty.tasks.points_expiry_tasks.expire_points_task',
        'schedule': {'hour': 0, 'minute': 0},  # crontab(hour=0, minute=0)
    },
    # Tier evaluation -- 1st of each month
    'evaluate-tiers-monthly': {
        'task': 'djoyalty.tasks.tier_evaluation_tasks.evaluate_all_tiers_task',
        'schedule': {'day_of_month': 1, 'hour': 2},
    },
    # Streak reset -- daily at 00:30
    'reset-broken-streaks': {
        'task': 'djoyalty.tasks.streak_reset_tasks.reset_broken_streaks_task',
        'schedule': {'hour': 0, 'minute': 30},
    },
    # AI churn scan -- daily at 3am
    'ai-churn-scan-daily': {
        'task': 'djoyalty.tasks.fraud_check_tasks.run_churn_scan_task',
        'schedule': {'hour': 3, 'minute': 0},
    },
    # Daily insights -- 1am
    'generate-daily-insights': {
        'task': 'djoyalty.tasks.insight_tasks.generate_daily_insight_task',
        'schedule': {'hour': 1, 'minute': 0},
    },
    # Partner sync -- every 6 hours
    'partner-sync': {
        'task': 'djoyalty.tasks.partner_sync_tasks.sync_all_partners_task',
        'schedule': {'hour': '*/6'},
    },
    # Leaderboard update -- hourly
    'leaderboard-update': {
        'task': 'djoyalty.tasks.leaderboard_tasks.update_leaderboard_task',
        'schedule': {'minute': 0},
    },
    # Voucher expiry check -- daily
    'expire-vouchers': {
        'task': 'djoyalty.tasks.voucher_expiry_tasks.expire_vouchers_task',
        'schedule': {'hour': 0, 'minute': 10},
    },
    # Subscription renewal reminders -- daily
    'subscription-renewals': {
        'task': 'djoyalty.tasks.subscription_tasks.process_subscription_renewals_task',
        'schedule': {'hour': 8, 'minute': 0},
    },
    # Fraud check -- every hour
    'fraud-check-hourly': {
        'task': 'djoyalty.tasks.fraud_check_tasks.hourly_fraud_check_task',
        'schedule': {'minute': 0},
    },
}

# ─── Cache (Redis) ────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
    }
}

# ─── Installed Apps ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # ... your apps
    'rest_framework',
    'djoyalty',
    # Optional: for FCM device management
    # 'fcm_django',
]

# ─── URLs ─────────────────────────────────────────────────────────────────────
# In your urls.py:
# urlpatterns = [
#     path('api/loyalty/', include('djoyalty.urls')),
# ]

# ─── Required Packages ───────────────────────────────────────────────────────
# pip install djangorestframework celery redis
# pip install firebase-admin          # For push notifications
# pip install google-cloud-vision     # For receipt OCR
# pip install sendgrid                # For SendGrid email
# pip install twilio                  # For Twilio SMS
# pip install cryptography            # For Nagad encryption
# pip install pytesseract Pillow      # For Tesseract OCR (offline)
