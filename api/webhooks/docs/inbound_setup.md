# Inbound Webhook Setup Guide

This guide provides comprehensive instructions for configuring inbound webhooks
from external payment gateways and other third-party services.

## 🎯 Overview

Inbound webhooks allow your application to receive real-time notifications
from external services like payment gateways, CRMs, and other SaaS platforms.
This guide covers setup for popular payment gateways and webhook providers.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Supported Providers](#supported-providers)
- [Security Configuration](#security-configuration)
- [Webhook Registration](#webhook-registration)
- [Testing Your Webhooks](#testing-your-webhooks)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Provider-Specific Guides](#provider-specific-guides)

## 🚀 Quick Start

### 1. Create Inbound Webhook Configuration

```python
# In Django admin or via API
from api.webhooks.models import InboundWebhook

# Create inbound webhook for Stripe
webhook = InboundWebhook.objects.create(
    source='stripe',
    url_token='stripe-webhooks-12345',
    secret='your-stripe-webhook-secret',
    is_active=True,
)
```

### 2. Configure Webhook Endpoint

```python
# urls.py
from django.urls import path
from api.webhooks.views import inbound_webhook_receiver

urlpatterns = [
    path('webhooks/inbound/<str:url_token>/', inbound_webhook_receiver, name='inbound_webhook_receiver'),
]
```

### 3. Test Webhook Reception

```bash
# Test webhook endpoint
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Stripe-Signature: <signature>" \
  -d '{"event": {"type": "payment_intent.succeeded"}}' \
  https://your-domain.com/api/webhooks/inbound/stripe-webhooks-12345/
```

## 🌐 Supported Providers

### Payment Gateways

#### Stripe
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/stripe-<token>/`
- **Documentation**: [Stripe Webhooks](https://stripe.com/docs/webhooks)
- **Signature Header**: `Stripe-Signature`
- **Timestamp Header**: `Stripe-Idempotency-Key` (optional)

#### PayPal
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/paypal-<token>/`
- **Documentation**: [PayPal Webhooks](https://developer.paypal.com/docs/api/webhooks/)
- **Signature Header**: `PAYPAL-AUTH-SHA256`
- **Timestamp Header**: `PAYPAL-AUTH-ALGO` (optional)

#### bKash
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/bkash-<token>/`
- **Documentation**: [bKash Webhooks](https://developer.bkash.com/docs/webhooks/)
- **Signature Header**: `X-BKash-Signature`
- **Timestamp Header**: `X-BKash-Timestamp`

#### Nagad
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/nagad-<token>/`
- **Documentation**: [Nagad Webhooks](https://developer.nagad.com/docs/webhooks/)
- **Signature Header**: `X-Nagad-Signature`
- **Timestamp Header**: `X-Nagad-Timestamp`

### CRMs & SaaS Platforms

#### Shopify
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/shopify-<token>/`
- **Documentation**: [Shopify Webhooks](https://shopify.dev/docs/webhooks/)
- **Signature Header**: `X-Shopify-Hmac-Sha256`
- **Timestamp Header**: `X-Shopify-Shop-Api-Call-Time`

#### Salesforce
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/salesforce-<token>/`
- **Documentation**: [Salesforce Webhooks](https://developer.salesforce.com/docs/api_outbound/webhooks/)
- **Signature Header**: `X-SFDC-Webhooks-Signature`
- **Timestamp Header**: `X-SFDC-Webhooks-Request-Timestamp`

#### GitHub
- **Webhook URL**: `https://your-domain.com/api/webhooks/inbound/github-<token>/`
- **Documentation**: [GitHub Webhooks](https://docs.github.com/en/developers/webhooks/)
- **Signature Header**: `X-Hub-Signature-256`
- **Timestamp Header**: `X-Hub-Signature-Timestamp`

## 🔒 Security Configuration

### 1. Generate Strong Secrets

```python
import secrets
import string

def generate_webhook_secret(length=32):
    """Generate a secure webhook secret."""
    characters = string.ascii_letters + string.digits + string.punctuation
    secret = ''.join(secrets.choice(characters) for _ in range(length))
    return secret

# Generate secret for new webhook
secret = generate_webhook_secret(32)
```

### 2. Store Secrets Securely

```python
# Use environment variables in production
import os

WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
if not WEBHOOK_SECRET:
    raise ValueError("Webhook secret not configured")
```

### 3. Configure HTTPS

```nginx
# nginx configuration
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    location /api/webhooks/inbound/ {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/private.key;
}
```

### 4. IP Whitelisting

```python
# Configure allowed IP addresses
ALLOWED_IPS = [
    '52.205.176.0',  # Stripe
    '173.0.82.0',     # PayPal
    '104.196.0.0',     # bKash
    '52.205.176.0',     # Nagad
]

# In webhook receiver
from django.http import HttpResponseForbidden

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def webhook_receiver(request):
    client_ip = get_client_ip(request)
    if client_ip not in ALLOWED_IPS:
        return HttpResponseForbidden("IP not allowed")
```

## 📝 Webhook Registration

### 1. Register Webhook with Provider

#### Stripe Registration
```bash
# Using Stripe CLI
stripe listen --forward-to localhost:8000/api/webhooks/inbound/stripe-webhooks-12345 \
  --events payment_intent.succeeded,payment_intent.payment_failed
```

#### PayPal Registration
```bash
# Using PayPal Developer Dashboard
# 1. Go to PayPal Developer Dashboard
# 2. Navigate to Webhooks section
# 3. Create webhook with URL: https://your-domain.com/api/webhooks/inbound/paypal-<token>/
# 4. Select events: PAYMENT.SALE.COMPLETED, PAYMENT.SALE.DENIED
# 5. Save webhook ID for configuration
```

#### bKash Registration
```bash
# Using bKash API
curl -X POST \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-domain.com/api/webhooks/inbound/bkash-<token>/",
    "events": ["payment.success", "payment.fail"],
    "is_active": true
  }' \
  https://merchant.bkash.com/api/v1.2/webhooks
```

### 2. Store Provider Configuration

```python
# Store webhook configuration in database
from api.webhooks.models import InboundWebhook, InboundWebhookRoute

# Create webhook configuration
webhook = InboundWebhook.objects.create(
    source='stripe',
    url_token='stripe-webhooks-12345',
    secret='your-stripe-webhook-secret',
    is_active=True,
)

# Create routing rules
InboundWebhookRoute.objects.create(
    inbound=webhook,
    event_pattern='payment_intent.*',
    handler_function='stripe_payment_handler',
    is_active=True,
)
```

## 🧪 Testing Your Webhooks

### 1. Use Provider Test Tools

#### Stripe CLI Testing
```bash
# Forward Stripe webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/inbound/stripe-webhooks-12345 \
  --events payment_intent.succeeded

# Trigger test event
stripe payment_intents.create \
  --amount 2000 \
  --currency usd \
  --confirm true \
  --payment-method card
```

#### PayPal Sandbox Testing
```bash
# Use PayPal sandbox
curl -X POST \
  -H "Content-Type: application/json" \
  -H "PAYPAL-AUTH-SHA256: <signature>" \
  -d '{"event": {"type": "payment.sale.completed"}}' \
  https://api.sandbox.paypal.com/v1/notifications/webhooks-events
```

### 2. Manual Testing

```bash
# Test webhook endpoint manually
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Stripe-Signature: $(echo -n '{"test": "data"}' | openssl dgst -sha256 -hmac 'your-secret-key')" \
  -H "X-Stripe-Idempotency-Key: test-key-12345" \
  -d '{"event": {"type": "payment_intent.succeeded"}}' \
  https://your-domain.com/api/webhooks/inbound/stripe-webhooks-12345/
```

### 3. Automated Testing

```python
# Test webhook with pytest
import pytest
from django.test import Client
from django.urls import reverse

def test_webhook_endpoint():
    client = Client()
    
    # Test valid webhook
    response = client.post(
        reverse('inbound_webhook_receiver', kwargs={'url_token': 'stripe-webhooks-12345'}),
        data={
            'event': {'type': 'payment_intent.succeeded'},
            'data': {
                'id': 'pi_123456789',
                'amount': 2000,
                'currency': 'usd'
            }
        },
        HTTP_X_STRIPE_SIGNATURE='valid-signature'
    )
    
    assert response.status_code == 200
    assert response.json()['status'] == 'success'
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Signature Verification Failed
```bash
# Check secret configuration
echo "Webhook secret: $WEBHOOK_SECRET"

# Test signature generation
echo '{"test": "data"}' | openssl dgst -sha256 -hmac 'your-secret-key'

# Compare with received signature
echo "Expected: $(echo -n '{"test": "data"}' | openssl dgst -sha256 -hmac 'your-secret-key')"
echo "Received: $RECEIVED_SIGNATURE"
```

#### 2. Webhook Not Received
```bash
# Check network connectivity
curl -I https://your-domain.com/api/webhooks/inbound/stripe-webhooks-12345/

# Check logs
tail -f /var/log/nginx/access.log | grep "stripe-webhooks-12345"

# Check Django logs
python manage.py shell
from api.webhooks.models import InboundWebhookLog
InboundWebhookLog.objects.filter(
    inbound__url_token='stripe-webhooks-12345'
).order_by('-created_at')[:10]
```

#### 3. JSON Parsing Errors
```python
# Validate JSON structure
import json

def validate_webhook_payload(payload):
    try:
        data = json.loads(payload)
        required_fields = ['event', 'data']
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
```

#### 4. Rate Limiting
```python
# Check rate limiting
from django.core.cache import cache
from django.http import HttpResponseTooManyRequests

def check_rate_limit(request):
    client_ip = get_client_ip(request)
    cache_key = f"webhook_rate_limit:{client_ip}"
    
    if cache.get(cache_key, 0) >= 10:
        return HttpResponseTooManyRequests("Rate limit exceeded")
    
    cache.set(cache_key, 1, timeout=60)
    return None
```

## 📈 Best Practices

### 1. Security
- Always use HTTPS for webhook URLs
- Implement signature verification
- Use strong, randomly generated secrets
- Rotate secrets regularly
- Implement IP whitelisting
- Log all webhook activities
- Use environment variables for secrets

### 2. Reliability
- Implement retry logic for failed deliveries
- Use idempotency keys to prevent duplicate processing
- Monitor webhook health and uptime
- Set appropriate timeouts
- Implement graceful degradation

### 3. Performance
- Process webhooks asynchronously
- Use database transactions for data consistency
- Implement proper error handling
- Monitor processing times
- Use efficient JSON parsing
- Cache frequently accessed data

### 4. Monitoring
- Log all webhook events
- Track success and failure rates
- Monitor response times
- Set up alerts for failures
- Use structured logging
- Implement health checks

## 📚 Provider-Specific Guides

### Stripe Configuration
```python
# settings.py
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
STRIPE_WEBHOOK_ENDPOINT = '/api/webhooks/inbound/stripe-<token>/'
STRIPE_ALLOWED_EVENTS = [
    'payment_intent.succeeded',
    'payment_intent.payment_failed',
    'payment_intent.canceled',
    'invoice.payment_succeeded',
    'invoice.payment_failed',
]
```

### PayPal Configuration
```python
# settings.py
PAYPAL_WEBHOOK_SECRET = os.getenv('PAYPAL_WEBHOOK_SECRET')
PAYPAL_WEBHOOK_ENDPOINT = '/api/webhooks/inbound/paypal-<token>/'
PAYPAL_ALLOWED_EVENTS = [
    'PAYMENT.SALE.COMPLETED',
    'PAYMENT.SALE.DENIED',
    'PAYMENT.CAPTURE.COMPLETED',
    'PAYMENT.CAPTURE.DENIED',
]
```

### bKash Configuration
```python
# settings.py
BKASH_WEBHOOK_SECRET = os.getenv('BKASH_WEBHOOK_SECRET')
BKASH_WEBHOOK_ENDPOINT = '/api/webhooks/inbound/bkash-<token>/'
BKASH_ALLOWED_EVENTS = [
    'payment.success',
    'payment.fail',
    'transfer.success',
    'transfer.fail',
]
```

## 🆘 Support

For questions about inbound webhook setup:
- Check the [API Documentation](api_reference.md)
- Review the [Event Types Reference](event_types.md)
- Contact the development team

---

*Last updated: January 1, 2026*
