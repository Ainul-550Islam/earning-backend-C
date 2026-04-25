# api/payment_gateways/settings_payment_gateways.py
# Paste these into your project's settings.py or a separate settings_local.py
# All values should come from environment variables in production.
import os

# ── bKash ─────────────────────────────────────────────────────────────────────
BKASH_APP_KEY      = os.environ.get('BKASH_APP_KEY', '')
BKASH_APP_SECRET   = os.environ.get('BKASH_APP_SECRET', '')
BKASH_USERNAME     = os.environ.get('BKASH_USERNAME', '')
BKASH_PASSWORD     = os.environ.get('BKASH_PASSWORD', '')
BKASH_CALLBACK_URL = os.environ.get('BKASH_CALLBACK_URL', 'https://yourdomain.com/api/payment/webhooks/bkash/')
BKASH_SANDBOX      = os.environ.get('BKASH_SANDBOX', 'True') == 'True'

# ── Nagad ─────────────────────────────────────────────────────────────────────
NAGAD_MERCHANT_ID          = os.environ.get('NAGAD_MERCHANT_ID', '')
NAGAD_MERCHANT_PRIVATE_KEY = os.environ.get('NAGAD_MERCHANT_PRIVATE_KEY', '')
NAGAD_PUBLIC_KEY           = os.environ.get('NAGAD_PUBLIC_KEY', '')
NAGAD_CALLBACK_URL         = os.environ.get('NAGAD_CALLBACK_URL', 'https://yourdomain.com/api/payment/webhooks/nagad/')
NAGAD_SANDBOX              = os.environ.get('NAGAD_SANDBOX', 'True') == 'True'

# ── SSLCommerz ────────────────────────────────────────────────────────────────
SSLCOMMERZ_STORE_ID       = os.environ.get('SSLCOMMERZ_STORE_ID', '')
SSLCOMMERZ_STORE_PASSWORD = os.environ.get('SSLCOMMERZ_STORE_PASSWORD', '')
SSLCOMMERZ_SUCCESS_URL    = os.environ.get('SSLCOMMERZ_SUCCESS_URL', 'https://yourdomain.com/payment/success/')
SSLCOMMERZ_FAIL_URL       = os.environ.get('SSLCOMMERZ_FAIL_URL', 'https://yourdomain.com/payment/fail/')
SSLCOMMERZ_CANCEL_URL     = os.environ.get('SSLCOMMERZ_CANCEL_URL', 'https://yourdomain.com/payment/cancel/')
SSLCOMMERZ_IPN_URL        = os.environ.get('SSLCOMMERZ_IPN_URL', 'https://yourdomain.com/api/payment/webhooks/sslcommerz/')
SSLCOMMERZ_SANDBOX        = os.environ.get('SSLCOMMERZ_SANDBOX', 'True') == 'True'

# ── AmarPay ───────────────────────────────────────────────────────────────────
AMARPAY_STORE_ID      = os.environ.get('AMARPAY_STORE_ID', 'aamarpay')
AMARPAY_SIGNATURE_KEY = os.environ.get('AMARPAY_SIGNATURE_KEY', '')
AMARPAY_SUCCESS_URL   = os.environ.get('AMARPAY_SUCCESS_URL', 'https://yourdomain.com/payment/success/')
AMARPAY_FAIL_URL      = os.environ.get('AMARPAY_FAIL_URL', 'https://yourdomain.com/payment/fail/')
AMARPAY_CANCEL_URL    = os.environ.get('AMARPAY_CANCEL_URL', 'https://yourdomain.com/payment/cancel/')
AMARPAY_SANDBOX       = os.environ.get('AMARPAY_SANDBOX', 'True') == 'True'

# ── Upay ──────────────────────────────────────────────────────────────────────
UPAY_MERCHANT_ID   = os.environ.get('UPAY_MERCHANT_ID', '')
UPAY_MERCHANT_KEY  = os.environ.get('UPAY_MERCHANT_KEY', '')
UPAY_MERCHANT_CODE = os.environ.get('UPAY_MERCHANT_CODE', '')
UPAY_MERCHANT_NAME = os.environ.get('UPAY_MERCHANT_NAME', '')
UPAY_SUCCESS_URL   = os.environ.get('UPAY_SUCCESS_URL', 'https://yourdomain.com/payment/success/')
UPAY_FAIL_URL      = os.environ.get('UPAY_FAIL_URL', 'https://yourdomain.com/payment/fail/')
UPAY_SANDBOX       = os.environ.get('UPAY_SANDBOX', 'True') == 'True'

# ── ShurjoPay ─────────────────────────────────────────────────────────────────
SHURJOPAY_USERNAME   = os.environ.get('SHURJOPAY_USERNAME', '')
SHURJOPAY_PASSWORD   = os.environ.get('SHURJOPAY_PASSWORD', '')
SHURJOPAY_RETURN_URL = os.environ.get('SHURJOPAY_RETURN_URL', 'https://yourdomain.com/payment/success/')
SHURJOPAY_CANCEL_URL = os.environ.get('SHURJOPAY_CANCEL_URL', 'https://yourdomain.com/payment/cancel/')
SHURJOPAY_CLIENT_IP  = os.environ.get('SHURJOPAY_CLIENT_IP', '127.0.0.1')
SHURJOPAY_SANDBOX    = os.environ.get('SHURJOPAY_SANDBOX', 'True') == 'True'

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# ── PayPal ────────────────────────────────────────────────────────────────────
PAYPAL_CLIENT_ID      = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET  = os.environ.get('PAYPAL_CLIENT_SECRET', '')
PAYPAL_WEBHOOK_ID     = os.environ.get('PAYPAL_WEBHOOK_ID', '')
PAYPAL_SANDBOX        = os.environ.get('PAYPAL_SANDBOX', 'True') == 'True'
PAYPAL_VERIFY_WEBHOOK = os.environ.get('PAYPAL_VERIFY_WEBHOOK', 'True') == 'True'

# ── SMS (optional) ────────────────────────────────────────────────────────────
SMS_PROVIDER         = os.environ.get('SMS_PROVIDER', 'twilio')
TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM          = os.environ.get('TWILIO_FROM', '')

# ── Push notifications (optional) ─────────────────────────────────────────────
FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY', '')

# ── Outgoing webhooks (optional) ──────────────────────────────────────────────
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL     = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# ── Redis cache ───────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}
