# Webhook Setup Guide

## Overview

PostbackEngine fires outbound webhooks when conversions are approved.
This enables real-time integration with external systems.

## Supported Platforms

### Zapier
```python
# settings.py
POSTBACK_ENGINE = {
    "ZAPIER_WEBHOOK_URLS": {
        "conversion.approved": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
        "fraud.detected": "https://hooks.zapier.com/hooks/catch/12345/xyz123/",
    }
}
```

### Make.com (Integromat)
```python
POSTBACK_ENGINE = {
    "MAKE_WEBHOOK_URLS": {
        "conversion.approved": "https://hook.eu1.make.com/abc123/",
        "*": "https://hook.eu1.make.com/all_events/",
    }
}
```

### Custom Webhook
Register via network metadata:
```json
{
  "webhooks": [
    {
      "url": "https://your-system.com/conversion-webhook",
      "events": ["conversion.approved", "conversion.reversed"],
      "secret": "your_webhook_secret"
    }
  ]
}
```

## Webhook Payload — conversion.approved

```json
{
  "event": "conversion.approved",
  "conversion_id": "uuid",
  "lead_id": "user_123",
  "offer_id": "offer_001",
  "network": "cpalead",
  "user_id": "42",
  "payout_usd": 0.50,
  "points_awarded": 500,
  "currency": "USD",
  "converted_at": "2024-01-15T10:30:00Z"
}
```

## Signature Verification

All webhooks are signed with HMAC-SHA256:
```
X-Webhook-Signature: <hex_signature>
X-Webhook-Timestamp: <unix_timestamp>
```

Verify: `HMAC-SHA256(secret, f"{timestamp}.{body}")`

## Retry Policy

Failed webhooks retry with backoff: 1m → 5m → 15m (max 3 attempts).
