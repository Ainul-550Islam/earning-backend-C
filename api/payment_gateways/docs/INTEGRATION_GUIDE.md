# Payment Gateway Integration Guide
<!-- FILE 145 of 257 -->

## System Overview

This payment_gateways module supports **8 payment gateways**:
- 🇧🇩 **BD Gateways**: bKash, Nagad, SSLCommerz, AmarPay, Upay, ShurjoPay
- 🌍 **International**: Stripe, PayPal

---

## Quick Start

### 1. Install & Migrate
```bash
pip install -r requirements.txt
python manage.py migrate payment_gateways
python manage.py migrate payment_gateway_refunds
python manage.py seed_gateways
python manage.py loaddata gateways currencies refund_policies
```

### 2. Add to INSTALLED_APPS (settings.py)
```python
INSTALLED_APPS = [
    ...
    'api.payment_gateways',
    'api.payment_gateways.refunds',
]
```

### 3. Add to main urls.py
```python
urlpatterns = [
    path('api/payment/', include('api.payment_gateways.urls')),
]
```

---

## API Endpoints

### Deposit (Initiate Payment)
```
POST /api/payment/transactions/deposit/
{
    "gateway": "bkash",   # or nagad, sslcommerz, amarpay, upay, shurjopay, stripe, paypal
    "amount": "500.00",
    "currency": "BDT"
}
Response:
{
    "payment_url": "https://pay.bkash.com/...",
    "transaction_id": "uuid",
    "reference_id": "BKASH_1234567890"
}
```

### Verify Payment
```
POST /api/payment/transactions/verify/
{
    "gateway": "bkash",
    "payment_id": "PAY_BKASH_001"
}
```

### Withdrawal
```
POST /api/payment/transactions/withdraw/
{
    "amount": "500.00",
    "payment_method_id": 1
}
```

### Transaction History
```
GET /api/payment/transactions/history/
GET /api/payment/transactions/?gateway=bkash&status=completed
```

### Refund
```
POST /api/payment/refunds/refunds/initiate/
{
    "transaction_id": 42,
    "amount": "100.00",
    "reason": "customer_request",
    "notes": "Customer changed mind"
}

GET /api/payment/refunds/refunds/my_refunds/
```

### Active Gateways
```
GET /api/payment/user/gateways/deposit/     # For deposits
GET /api/payment/user/gateways/active/      # For withdrawals
```

---

## Webhook URLs (Register in gateway dashboards)

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

---

## Deposit Flow

```
User → POST /transactions/deposit/ {gateway, amount}
     → API returns {payment_url}
     → Frontend redirects user to payment_url
     → User completes payment on gateway page
     → Gateway POSTs to /webhooks/{gateway}/
     → Webhook handler verifies + credits user balance
     → User sees completed status
```

---

## Fraud Detection

Every deposit is checked automatically:
```python
from api.payment_gateways.fraud.FraudDetector import FraudDetector

detector = FraudDetector()
result = detector.check(user, amount, gateway, ip_address)

if result['action'] == 'block':
    raise PermissionDenied('Transaction blocked by fraud detection')
elif result['action'] == 'flag':
    # Log and notify admin but allow
    pass
```

Risk levels: `low (0-30)` → `medium (31-60)` → `high (61-80)` → `critical (81-100)`

---

## Start Celery (Background Tasks)

```bash
# Worker
celery -A config worker -l info -Q default,payments,refunds,reports

# Beat (periodic tasks)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Monitor
celery -A config flower --port=5555
```

---

## Management Commands

```bash
# Seed all 8 gateways
python manage.py seed_gateways

# Reconcile payments
python manage.py reconcile --date 2024-01-15
python manage.py reconcile --gateway bkash

# Sync stuck transactions
python manage.py sync_txns --hours 24
python manage.py sync_txns --gateway stripe

# Export transactions
python manage.py export_report --from 2024-01-01 --to 2024-01-31
python manage.py export_report --user 42

# Retry failed webhooks
python manage.py retry_webhooks

# Cleanup old data
python manage.py cleanup --days 30
```

---

## Code Examples

### Process a deposit
```python
from api.payment_gateways.services.PaymentFactory import PaymentFactory

processor = PaymentFactory.get_processor('bkash')
result = processor.process_deposit(user=request.user, amount=500)
# Redirect user to: result['payment_url']
```

### Process a refund
```python
from api.payment_gateways.refunds.RefundFactory import RefundFactory

processor = RefundFactory.get_processor('stripe')
result = processor.process_refund(
    transaction=txn,
    amount=Decimal('100.00'),
    reason='customer_request'
)
```

### Check refund status
```python
status = RefundFactory.check_refund_status('stripe', refund_request)
```

---

## Environment Variables Reference

See `settings_payment_gateways.py` for all required environment variables.
