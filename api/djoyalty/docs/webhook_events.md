# Webhook Events — Djoyalty

## Overview
Djoyalty সব key events এর জন্য outbound webhooks পাঠায়।
Partner merchant এবং external systems events subscribe করতে পারে।

## Authentication
প্রতিটি webhook request এ HMAC-SHA256 signature থাকে।
```
Header: X-Loyalty-Signature: sha256=<hex_digest>
```

### Verify Signature
```python
from djoyalty.webhooks.webhook_security import verify_signature
is_valid = verify_signature(request.body, request.headers['X-Loyalty-Signature'], your_secret)
```

## Standard Payload Format
```json
{
  "event": "points.earned",
  "timestamp": "2026-04-06T10:30:00Z",
  "tenant_id": 1,
  "customer_code": "CUST001",
  "data": { ... }
}
```

## Event Types

### Points Events
| Event | When | Data |
|---|---|---|
| `points.earned` | Points credited | `points_earned`, `balance_after`, `source` |
| `points.burned` | Points debited | `points`, `source` |
| `points.expired` | Points expired | `points`, `expires_at` |
| `points.transferred` | P2P transfer | `points`, `from_customer`, `to_customer` |

### Tier Events
| Event | When | Data |
|---|---|---|
| `tier.changed` | Tier upgraded or downgraded | `from_tier`, `to_tier`, `change_type` |
| `tier.upgraded` | Specifically upgraded | `from_tier`, `to_tier`, `points_at_change` |
| `tier.downgraded` | Specifically downgraded | `from_tier`, `to_tier` |

### Engagement Events
| Event | When | Data |
|---|---|---|
| `badge.unlocked` | New badge earned | `badge_name`, `badge_icon`, `points_reward` |
| `streak.milestone` | Streak milestone reached | `milestone_days`, `points` |
| `challenge.completed` | Challenge finished | `challenge_name`, `points_awarded` |

### Redemption Events
| Event | When | Data |
|---|---|---|
| `redemption.status_changed` | Status updated | `redemption_id`, `status`, `points_used`, `redemption_type` |
| `voucher.used` | Voucher redeemed | `voucher_code`, `discount_applied`, `order_reference` |
| `gift_card.redeemed` | Gift card used | `code`, `amount`, `remaining_value` |

### Customer Events
| Event | When | Data |
|---|---|---|
| `customer.registered` | New customer | `customer_code`, `email` |
| `campaign.joined` | Campaign joined | `campaign_name`, `campaign_type` |

### System Events
| Event | When | Data |
|---|---|---|
| `fraud.detected` | Fraud flagged | `risk_level`, `action_taken`, `description` |
| `subscription.renewed` | Monthly renewal | `plan_name`, `bonus_points` |

## Registering Endpoints
```python
from djoyalty.webhooks.webhook_registry import WebhookRegistry

WebhookRegistry.register(
    url='https://your-system.com/webhook',
    events=['points.earned', 'tier.changed', 'badge.unlocked'],
    secret='your-hmac-secret',
    name='Your System Integration',
)
```

## Retry Policy
Failed deliveries retry with exponential backoff:
```
Attempt 1: immediate
Attempt 2: after 10 seconds
Attempt 3: after 30 seconds
Attempt 4: after 60 seconds
Attempt 5: after 300 seconds (5 min)
```
Max retries: **5 attempts**
Timeout per attempt: **10 seconds**

## Celery Task
```
djoyalty.check_partner_webhooks  # Hourly health check
```
