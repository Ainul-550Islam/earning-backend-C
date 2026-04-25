# Production Setup Checklist
<!-- FILE 146 of 257 -->

## ✅ Pre-Production Checklist

### Django Settings
- [ ] `INSTALLED_APPS` includes `api.payment_gateways` and `api.payment_gateways.refunds`
- [ ] `CELERY_BROKER_URL` = `redis://localhost:6379/0`
- [ ] `CELERY_RESULT_BACKEND` = `redis://localhost:6379/0`
- [ ] `CACHES` configured with Redis backend
- [ ] `DEFAULT_FROM_EMAIL` set to your sender email
- [ ] `MEDIA_ROOT` configured for CSV exports
- [ ] `TIME_ZONE = 'Asia/Dhaka'` set

### Required Python Packages
```bash
pip install celery redis django-celery-beat
pip install pycryptodome          # Nagad RSA encryption
pip install stripe                # Optional: Stripe SDK
pip install paypalrestsdk         # Optional: PayPal SDK
pip install twilio                # Optional: SMS via Twilio
pip install channels              # Optional: WebSocket push notifications
```

---

## Gateway Credentials Checklist

### bKash
- [ ] `BKASH_APP_KEY`
- [ ] `BKASH_APP_SECRET`
- [ ] `BKASH_USERNAME`
- [ ] `BKASH_PASSWORD`
- [ ] `BKASH_CALLBACK_URL` = `https://yourdomain.com/api/payment/webhooks/bkash/`
- [ ] `BKASH_SANDBOX` = `False` (production)

### Nagad
- [ ] `NAGAD_MERCHANT_ID`
- [ ] `NAGAD_MERCHANT_PRIVATE_KEY` (RSA private key)
- [ ] `NAGAD_PUBLIC_KEY` (Nagad's public key)
- [ ] `NAGAD_CALLBACK_URL` = `https://yourdomain.com/api/payment/webhooks/nagad/`
- [ ] `NAGAD_SANDBOX` = `False`

### SSLCommerz
- [ ] `SSLCOMMERZ_STORE_ID`
- [ ] `SSLCOMMERZ_STORE_PASSWORD`
- [ ] `SSLCOMMERZ_SUCCESS_URL`
- [ ] `SSLCOMMERZ_FAIL_URL`
- [ ] `SSLCOMMERZ_CANCEL_URL`
- [ ] `SSLCOMMERZ_IPN_URL` = `https://yourdomain.com/api/payment/webhooks/sslcommerz/`
- [ ] `SSLCOMMERZ_SANDBOX` = `False`

### AmarPay
- [ ] `AMARPAY_STORE_ID`
- [ ] `AMARPAY_SIGNATURE_KEY`
- [ ] `AMARPAY_SUCCESS_URL`
- [ ] `AMARPAY_FAIL_URL`
- [ ] `AMARPAY_CANCEL_URL`
- [ ] `AMARPAY_SANDBOX` = `False`

### Upay
- [ ] `UPAY_MERCHANT_ID`
- [ ] `UPAY_MERCHANT_KEY`
- [ ] `UPAY_MERCHANT_CODE`
- [ ] `UPAY_MERCHANT_NAME`
- [ ] `UPAY_SUCCESS_URL`
- [ ] `UPAY_FAIL_URL`
- [ ] `UPAY_SANDBOX` = `False`

### ShurjoPay
- [ ] `SHURJOPAY_USERNAME`
- [ ] `SHURJOPAY_PASSWORD`
- [ ] `SHURJOPAY_RETURN_URL`
- [ ] `SHURJOPAY_CANCEL_URL`
- [ ] `SHURJOPAY_CLIENT_IP` (your server IP)
- [ ] `SHURJOPAY_SANDBOX` = `False`

### Stripe
- [ ] `STRIPE_SECRET_KEY` = `sk_live_...`
- [ ] `STRIPE_PUBLISHABLE_KEY` = `pk_live_...`
- [ ] `STRIPE_WEBHOOK_SECRET` = `whsec_...`
- [ ] Register webhook in Stripe Dashboard → webhook events: `payment_intent.*`, `charge.*`

### PayPal
- [ ] `PAYPAL_CLIENT_ID`
- [ ] `PAYPAL_CLIENT_SECRET`
- [ ] `PAYPAL_WEBHOOK_ID`
- [ ] `PAYPAL_SANDBOX` = `False`
- [ ] `PAYPAL_VERIFY_WEBHOOK` = `True`
- [ ] Register webhook in PayPal Developer Dashboard

---

## Database Setup
```bash
python manage.py migrate payment_gateways
python manage.py migrate payment_gateway_refunds
python manage.py migrate payment_gateways_notifications  # if app exists
python manage.py migrate payment_gateways_reports        # if app exists
python manage.py seed_gateways --force
python manage.py loaddata gateways currencies refund_policies
```

---

## Services Startup

### Supervisor config example
```ini
[program:celery_worker]
command=celery -A config worker -l info -Q default,payments,refunds
directory=/var/www/yourproject
autostart=true
autorestart=true

[program:celery_beat]
command=celery -A config beat -l info
directory=/var/www/yourproject
autostart=true
autorestart=true
```

---

## Security Checklist
- [ ] All webhook endpoints use HTTPS
- [ ] Webhook signatures verified for all gateways
- [ ] `PAYPAL_VERIFY_WEBHOOK = True` in production
- [ ] `BKASH_SANDBOX = False` in production
- [ ] API keys stored in environment variables, NOT in code
- [ ] Rate limiting configured (`cache/RateLimiter.py`)
- [ ] Fraud detection enabled (`fraud/FraudDetector.py`)
- [ ] Admin panel restricted to staff only (`IsAdminUser`)
- [ ] `DEBUG = False` in production
- [ ] `ALLOWED_HOSTS` properly configured

---

## Monitoring
- [ ] Celery Flower running for task monitoring
- [ ] Admin alerts configured (`tasks/notification_tasks.py`)
- [ ] Daily reconciliation scheduled (2 AM)
- [ ] Daily reports scheduled (6 AM)
- [ ] Balance integrity check scheduled (4 AM)
