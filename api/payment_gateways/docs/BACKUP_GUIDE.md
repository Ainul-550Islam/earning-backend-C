# Payment Gateways — Backup & Integration Guide

## ✅ Safe to Backup? YES — No Conflicts

### Your existing apps vs payment_gateways

| Your App | Our App | Conflict? | Why Safe |
|----------|---------|-----------|----------|
| `api.smartlink` | `api.payment_gateways.smartlink` | ✅ NO | Different Django labels |
| `api.support` | `api.payment_gateways.support` | ✅ NO | Different labels |
| `api.notifications` | `api.payment_gateways.notifications` | ✅ NO | Different labels |
| `api.wallet` | WalletAdapter (bridge) | ✅ NO | We call YOUR wallet |
| `api.fraud_detection` | FraudAdapter (bridge) | ✅ NO | We call YOUR fraud system |
| `api.postback_engine` | PostbackAdapter (bridge) | ✅ NO | We call YOUR postback |
| `api.offerwall` | `api.payment_gateways.locker` | ✅ NO | Different labels |

---

## Step 1: Add to INSTALLED_APPS

```python
# settings.py — Add AFTER existing apps
INSTALLED_APPS = [
    # ...your existing apps...
    
    # Payment Gateways — World #1 System
    'api.payment_gateways',
    'api.payment_gateways.refunds',
    'api.payment_gateways.fraud',
    'api.payment_gateways.notifications',
    'api.payment_gateways.reports',
    'api.payment_gateways.schedules',
    'api.payment_gateways.referral',
    'api.payment_gateways.tracking',
    'api.payment_gateways.offers',
    'api.payment_gateways.rtb',
    'api.payment_gateways.publisher',
    'api.payment_gateways.locker',
    'api.payment_gateways.blacklist',
    'api.payment_gateways.integrations',
    'api.payment_gateways.smartlink',
    'api.payment_gateways.bonuses',
    'api.payment_gateways.support',
]
```

## Step 2: Add to MIDDLEWARE

```python
MIDDLEWARE = [
    # ...your existing middleware including:
    # 'api.smartlink.middleware.SmartLinkRedirectMiddleware',
    # 'api.fraud_detection.middleware.FraudDetectionMiddleware',
    
    # Add LAST:
    'api.payment_gateways.middleware.WebhookSignatureMiddleware',
]
```

## Step 3: Add to urls.py

```python
# project/urls.py
urlpatterns = [
    # ...existing urls...
    path('api/payment/', include('api.payment_gateways.urls')),
]
```

## Step 4: Add environment variables to .env

```env
# BD Gateways
BKASH_APP_KEY=your_key
BKASH_APP_SECRET=your_secret
BKASH_USERNAME=your_username
BKASH_PASSWORD=your_password
BKASH_SANDBOX=True
BKASH_WEBHOOK_SECRET=your_webhook_secret

NAGAD_MERCHANT_ID=your_merchant_id
NAGAD_MERCHANT_PRIVATE_KEY=your_private_key
NAGAD_PUBLIC_KEY=nagad_public_key
NAGAD_SANDBOX=True

SSLCOMMERZ_STORE_ID=your_store_id
SSLCOMMERZ_STORE_PASSWORD=your_password
SSLCOMMERZ_SANDBOX=True

AMARPAY_STORE_ID=your_store_id
AMARPAY_SIGNATURE_KEY=your_key
AMARPAY_SANDBOX=True

UPAY_MERCHANT_ID=your_merchant_id
UPAY_MERCHANT_KEY=your_key
UPAY_SANDBOX=True

SHURJOPAY_USERNAME=your_username
SHURJOPAY_PASSWORD=your_password
SHURJOPAY_RETURN_URL=https://yourdomain.com/payment/success/
SHURJOPAY_SANDBOX=True

# International Gateways
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_secret
PAYPAL_WEBHOOK_ID=your_webhook_id
PAYPAL_SANDBOX=True

PAYONEER_CLIENT_ID=your_id
PAYONEER_CLIENT_SECRET=your_secret
PAYONEER_SANDBOX=True

COINBASE_COMMERCE_API_KEY=your_key
COINBASE_WEBHOOK_SECRET=your_secret

WIRE_BANK_NAME=Dutch-Bangla Bank Limited
WIRE_ACCOUNT_NAME=Your Company Ltd
WIRE_ACCOUNT_NUMBER=1234567890
WIRE_SWIFT_CODE=DBBLBDDH

# System
SITE_URL=https://yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
LOCKER_CDN_URL=https://cdn.yourdomain.com/locker
```

## Step 5: Run Migrations (in order)

```bash
python manage.py migrate payment_gateways
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

# Load fixtures
python manage.py loaddata api/payment_gateways/fixtures/gateways.json
python manage.py loaddata api/payment_gateways/fixtures/currencies.json
python manage.py loaddata api/payment_gateways/fixtures/refund_policies.json
```

## Step 6: Register Webhook URLs with each gateway

| Gateway | Webhook URL |
|---------|-------------|
| bKash | `https://yourdomain.com/api/payment/webhooks/bkash/` |
| Nagad | `https://yourdomain.com/api/payment/webhooks/nagad/` |
| SSLCommerz | `https://yourdomain.com/api/payment/webhooks/sslcommerz/` |
| AmarPay | `https://yourdomain.com/api/payment/webhooks/amarpay/` |
| Upay | `https://yourdomain.com/api/payment/webhooks/upay/` |
| ShurjoPay | `https://yourdomain.com/api/payment/webhooks/shurjopay/` |
| Stripe | `https://yourdomain.com/api/payment/webhooks/stripe/` |
| PayPal | `https://yourdomain.com/api/payment/webhooks/paypal/` |

## Step 7: Add to Celery Beat schedule

```python
# Your celery.py — merge our schedule
from api.payment_gateways.settings_integration import CELERYBEAT_SCHEDULE_PAYMENT_GATEWAYS

app.conf.beat_schedule.update(CELERYBEAT_SCHEDULE_PAYMENT_GATEWAYS)
```

## Step 8: Start services

```bash
# Celery worker
celery -A config worker -l info -Q default,payments,refunds,webhooks

# Celery Beat (scheduler)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## ⚠️ Known Issues & Solutions

### Issue 1: api.support label conflict
If your `api.support` app uses label `'support'`, our `api.payment_gateways.support`
uses label `'payment_gateways_support'` — NO conflict.

### Issue 2: api.notifications label conflict  
If your `api.notifications` uses label `'notifications'`, ours uses
`'payment_gateways_notifications'` — NO conflict.

### Issue 3: Circular import in PaymentProcessor
Fixed: models are imported inside methods, not at module level.

### Issue 4: integrations_adapters has no migrations
No migration needed — it's pure Python adapters with no models.

---

## Integration with Your Existing Apps

### api.wallet → WalletAdapter
```python
# In DepositService.py, we call:
from api.payment_gateways.integrations_adapters.WalletAdapter import WalletAdapter
WalletAdapter().credit_deposit(user, amount, gateway, reference_id)
# → This calls api.wallet.models.WalletTransaction.objects.create(...)
```

### api.fraud_detection → FraudAdapter
```python
from api.payment_gateways.integrations_adapters.FraudAdapter import FraudAdapter
result = FraudAdapter().check(user, amount, gateway, ip)
# → This calls api.fraud_detection.services.FraudDetectionService().check_transaction(...)
```

### api.postback_engine → PostbackAdapter
```python
from api.payment_gateways.integrations_adapters.PostbackAdapter import PostbackAdapter
PostbackAdapter().process_incoming(params, url, ip)
# → This calls api.postback_engine.services.PostbackService().process(...)
```
