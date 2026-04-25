# api/payment_gateways/settings_integration.py
# =============================================================================
# COMPLETE INTEGRATION GUIDE — Add to your project's settings.py
# =============================================================================
# This file shows EVERYTHING you need to add to your existing settings.py
# to integrate payment_gateways with your existing system.
# 
# Your existing INSTALLED_APPS already has:
#   'api.smartlink', 'api.wallet', 'api.notifications', 'api.support',
#   'api.fraud_detection', 'api.postback_engine', etc.
# 
# payment_gateways sub-apps use DIFFERENT labels (payment_gateways_*),
# so there are NO conflicts with your existing apps.
# =============================================================================

# ── 1. INSTALLED_APPS — Add AFTER your existing apps ─────────────────────────
PAYMENT_GATEWAY_APPS = [
    # Core payment gateway
    'api.payment_gateways',

    # Sub-apps (all use label prefix 'payment_gateways_*' — no conflicts)
    'api.payment_gateways.refunds',        # label: payment_gateways_refunds
    'api.payment_gateways.fraud',          # label: payment_gateways_fraud
    'api.payment_gateways.notifications',  # label: payment_gateways_notifications ≠ your api.notifications
    'api.payment_gateways.reports',        # label: payment_gateways_reports
    'api.payment_gateways.schedules',      # label: payment_gateways_schedules
    'api.payment_gateways.referral',       # label: payment_gateways_referral
    'api.payment_gateways.tracking',       # label: payment_gateways_tracking
    'api.payment_gateways.offers',         # label: payment_gateways_offers
    'api.payment_gateways.rtb',            # label: payment_gateways_rtb
    'api.payment_gateways.publisher',      # label: payment_gateways_publisher
    'api.payment_gateways.locker',         # label: payment_gateways_locker ≠ your api.offerwall
    'api.payment_gateways.blacklist',      # label: payment_gateways_blacklist
    'api.payment_gateways.integrations',   # label: payment_gateways_integrations
    'api.payment_gateways.smartlink',      # label: payment_gateways_smartlink ≠ your api.smartlink
    'api.payment_gateways.bonuses',        # label: payment_gateways_bonuses
    'api.payment_gateways.support',        # label: payment_gateways_support ≠ your api.support
    'api.payment_gateways.cache',          # label: payment_gateways_cache
]
# In your settings.py:
# INSTALLED_APPS = [...your existing apps...] + PAYMENT_GATEWAY_APPS

# ── 2. MIDDLEWARE — Add AFTER existing middleware ─────────────────────────────
# Add this to your MIDDLEWARE list (after authentication middleware):
#
# MIDDLEWARE = [
#     ...existing middleware...
#     'api.payment_gateways.middleware.WebhookSignatureMiddleware',
# ]
#
# NOTE: Your existing middleware is fine — our webhook verifier works
# alongside 'api.fraud_detection.middleware.FraudDetectionMiddleware'
# and 'api.smartlink.middleware.SmartLinkRedirectMiddleware'

# ── 3. URL CONFIGURATION ───────────────────────────────────────────────────────
# In your project's urls.py, add:
#
# urlpatterns = [
#     ...existing urls...
#     path('api/payment/', include('api.payment_gateways.urls')),
# ]
#
# This gives you:
#   /api/payment/gateways/                    — Gateway management
#   /api/payment/transactions/                — Transaction history
#   /api/payment/deposits/                    — Deposit management
#   /api/payment/withdrawals/                 — Withdrawal management
#   /api/payment/tracking/postback/           — S2S postback endpoint
#   /api/payment/tracking/pixel.gif           — Pixel tracking
#   /api/payment/offers/                      — CPA/CPI offers
#   /api/payment/smartlinks/                  — SmartLinks (separate from api.smartlink)
#   /api/payment/locker/                      — Content lockers (separate from api.offerwall)
#   /api/payment/status/                      — Public gateway status page
#   /api/payment/webhooks/bkash/              — bKash webhook
#   /api/payment/webhooks/stripe/             — Stripe webhook
#   ...etc

# ── 4. GATEWAY CREDENTIALS ────────────────────────────────────────────────────
import os

BKASH_APP_KEY        = os.environ.get('BKASH_APP_KEY', '')
BKASH_APP_SECRET     = os.environ.get('BKASH_APP_SECRET', '')
BKASH_USERNAME       = os.environ.get('BKASH_USERNAME', '')
BKASH_PASSWORD       = os.environ.get('BKASH_PASSWORD', '')
BKASH_SANDBOX        = os.environ.get('BKASH_SANDBOX', 'True') == 'True'
BKASH_WEBHOOK_SECRET = os.environ.get('BKASH_WEBHOOK_SECRET', '')
BKASH_CALLBACK_URL   = os.environ.get('BKASH_CALLBACK_URL', 'https://yourdomain.com/api/payment/webhooks/bkash/')

NAGAD_MERCHANT_ID          = os.environ.get('NAGAD_MERCHANT_ID', '')
NAGAD_MERCHANT_PRIVATE_KEY = os.environ.get('NAGAD_MERCHANT_PRIVATE_KEY', '')
NAGAD_PUBLIC_KEY           = os.environ.get('NAGAD_PUBLIC_KEY', '')
NAGAD_SANDBOX              = os.environ.get('NAGAD_SANDBOX', 'True') == 'True'
NAGAD_CALLBACK_URL         = os.environ.get('NAGAD_CALLBACK_URL', 'https://yourdomain.com/api/payment/webhooks/nagad/')

SSLCOMMERZ_STORE_ID       = os.environ.get('SSLCOMMERZ_STORE_ID', '')
SSLCOMMERZ_STORE_PASSWORD = os.environ.get('SSLCOMMERZ_STORE_PASSWORD', '')
SSLCOMMERZ_SANDBOX        = os.environ.get('SSLCOMMERZ_SANDBOX', 'True') == 'True'
SSLCOMMERZ_IPN_URL        = os.environ.get('SSLCOMMERZ_IPN_URL', 'https://yourdomain.com/api/payment/webhooks/sslcommerz/')

AMARPAY_STORE_ID      = os.environ.get('AMARPAY_STORE_ID', 'aamarpay')
AMARPAY_SIGNATURE_KEY = os.environ.get('AMARPAY_SIGNATURE_KEY', '')
AMARPAY_SANDBOX       = os.environ.get('AMARPAY_SANDBOX', 'True') == 'True'

UPAY_MERCHANT_ID   = os.environ.get('UPAY_MERCHANT_ID', '')
UPAY_MERCHANT_KEY  = os.environ.get('UPAY_MERCHANT_KEY', '')
UPAY_SANDBOX       = os.environ.get('UPAY_SANDBOX', 'True') == 'True'

SHURJOPAY_USERNAME   = os.environ.get('SHURJOPAY_USERNAME', '')
SHURJOPAY_PASSWORD   = os.environ.get('SHURJOPAY_PASSWORD', '')
SHURJOPAY_RETURN_URL = os.environ.get('SHURJOPAY_RETURN_URL', 'https://yourdomain.com/payment/success/')
SHURJOPAY_SANDBOX    = os.environ.get('SHURJOPAY_SANDBOX', 'True') == 'True'

STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

PAYPAL_CLIENT_ID      = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET  = os.environ.get('PAYPAL_CLIENT_SECRET', '')
PAYPAL_WEBHOOK_ID     = os.environ.get('PAYPAL_WEBHOOK_ID', '')
PAYPAL_SANDBOX        = os.environ.get('PAYPAL_SANDBOX', 'True') == 'True'

PAYONEER_CLIENT_ID     = os.environ.get('PAYONEER_CLIENT_ID', '')
PAYONEER_CLIENT_SECRET = os.environ.get('PAYONEER_CLIENT_SECRET', '')
PAYONEER_SANDBOX       = os.environ.get('PAYONEER_SANDBOX', 'True') == 'True'

COINBASE_COMMERCE_API_KEY = os.environ.get('COINBASE_COMMERCE_API_KEY', '')
COINBASE_WEBHOOK_SECRET   = os.environ.get('COINBASE_WEBHOOK_SECRET', '')

WIRE_BANK_NAME     = os.environ.get('WIRE_BANK_NAME', 'Dutch-Bangla Bank Limited')
WIRE_ACCOUNT_NAME  = os.environ.get('WIRE_ACCOUNT_NAME', '')
WIRE_ACCOUNT_NUMBER= os.environ.get('WIRE_ACCOUNT_NUMBER', '')
WIRE_SWIFT_CODE    = os.environ.get('WIRE_SWIFT_CODE', 'DBBLBDDH')

# ── 5. CELERY CONFIGURATION ────────────────────────────────────────────────────
# Your existing celery config should work. Just add our beat schedules:
# In your celery.py or settings.py, merge our beat_schedule from:
#   api.payment_gateways.celery (app.conf.beat_schedule)
#
# OR add to your existing beat schedule:
from datetime import timedelta
CELERYBEAT_SCHEDULE_PAYMENT_GATEWAYS = {
    'pg-check-gateway-health':        {'task': 'api.payment_gateways.tasks.gateway_health_tasks.check_all_gateways',                  'schedule': timedelta(minutes=5)},
    'pg-verify-pending-deposits':     {'task': 'api.payment_gateways.tasks.deposit_verification_tasks.verify_pending_deposits',        'schedule': timedelta(minutes=10)},
    'pg-nightly-reconciliation':      {'task': 'api.payment_gateways.tasks.reconciliation_tasks.nightly_reconciliation',              'schedule': timedelta(hours=24)},
    'pg-daily-fast-pay':              {'task': 'api.payment_gateways.tasks.usdt_fastpay_tasks.process_daily_fastpay',                 'schedule': timedelta(hours=24)},
    'pg-sync-exchange-rates':         {'task': 'api.payment_gateways.tasks.exchange_rate_tasks.sync_exchange_rates',                  'schedule': timedelta(hours=1)},
    'pg-aggregate-analytics':         {'task': 'api.payment_gateways.tasks.analytics_tasks.aggregate_daily_analytics',               'schedule': timedelta(hours=1)},
    'pg-check-failure-alerts':        {'task': 'api.payment_gateways.tasks.alert_tasks.check_failure_rate_alerts',                    'schedule': timedelta(hours=4)},
    'pg-cleanup-old-logs':            {'task': 'api.payment_gateways.tasks.alert_tasks.cleanup_old_logs',                             'schedule': timedelta(days=7)},
    'pg-pay-referral-commissions':    {'task': 'api.payment_gateways.tasks.referral_tasks.pay_pending_commissions',                   'schedule': timedelta(hours=24)},
    'pg-process-approved-payouts':    {'task': 'api.payment_gateways.tasks.withdrawal_processing_tasks.process_approved_payouts',     'schedule': timedelta(hours=24)},
}
# Add to your CELERYBEAT_SCHEDULE: {**CELERYBEAT_SCHEDULE, **CELERYBEAT_SCHEDULE_PAYMENT_GATEWAYS}

# ── 6. CACHE CONFIGURATION ────────────────────────────────────────────────────
# Your existing Redis cache config works fine. We use cache.get/set with:
#   Prefixes: 'gw_health:', 'gw_success_rate:', 'exchange_rate:', 'cap_check:', etc.
# No additional cache config needed if CACHES['default'] uses Redis.

# ── 7. SITE URL ───────────────────────────────────────────────────────────────
SITE_URL = os.environ.get('SITE_URL', 'https://yourdomain.com')
LOCKER_CDN_URL = os.environ.get('LOCKER_CDN_URL', 'https://cdn.yourdomain.com/locker')

# ── 8. ADMIN EMAIL ────────────────────────────────────────────────────────────
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@yourdomain.com')

# ── 9. MIGRATION COMMANDS ──────────────────────────────────────────────────────
# Run in this order:
MIGRATION_COMMANDS = """
python manage.py migrate payment_gateways 0006_deposit_withdrawal_gateway_config
python manage.py migrate payment_gateways_refunds
python manage.py migrate payment_gateways_fraud
python manage.py migrate payment_gateways_notifications
python manage.py migrate payment_gateways_reports
python manage.py migrate payment_gateways_schedules
python manage.py migrate payment_gateways_referral
python manage.py migrate payment_gateways_offers
python manage.py migrate payment_gateways_tracking
python manage.py migrate payment_gateways_locker
python manage.py migrate payment_gateways_blacklist
python manage.py migrate payment_gateways_integrations
python manage.py migrate payment_gateways_smartlink
python manage.py migrate payment_gateways_bonuses
python manage.py migrate payment_gateways_support
python manage.py migrate payment_gateways_publisher

# Load seed data
python manage.py loaddata api/payment_gateways/fixtures/gateways.json
python manage.py loaddata api/payment_gateways/fixtures/currencies.json
python manage.py loaddata api/payment_gateways/fixtures/refund_policies.json
"""
