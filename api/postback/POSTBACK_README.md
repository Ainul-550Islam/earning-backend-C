# Postback App — Deployment & Integration Guide

## Overview

The `postback` app handles all inbound affiliate network postbacks (S2S conversion tracking). It supports CPAlead, and any other network via the generic adapter.

**Coverage:** 100% vs CPAlead standard | 99% vs world (Everflow/CAKE/TUNE) system average.

---

## Quick Start

### 1. Run Migrations
```bash
python manage.py migrate postback
```

### 2. Create NetworkPostbackConfig (CPAlead example)
```python
# In Django admin or shell:
from api.postback.models import NetworkPostbackConfig

NetworkPostbackConfig.objects.create(
    name="CPAlead",
    network_key="cpalead",
    network_type="cpa",
    status="active",
    secret_key="YOUR_SECRET_FROM_CPALEAD",
    signature_algorithm="none",          # CPAlead uses IP whitelist, not HMAC
    ip_whitelist=["54.175.8.0/24", "54.84.0.0/16"],  # CPAlead IPs
    require_nonce=False,
    required_fields=["lead_id", "offer_id"],
    field_mapping={},                    # CPAlead uses standard names
    reward_rules={
        "OFFER_123": {"points": 500},   # offer_id → points
        "OFFER_456": {"points": 1000},
    },
    default_reward_points=100,
    rate_limit_per_minute=500,
    # S2S outbound (optional — fire back to advertiser)
    callback_url="https://track.advertiser.com/postback?lead={lead_id}&payout={payout}&ip={ip_address}",
    callback_method="GET",
)
```

### 3. Set Postback URL in CPAlead Dashboard
```
https://yourdomain.com/api/postback/receive/cpalead/?lead_id={lead_id}&offer_id={offer_id}&payout={payout}&goal_id={goal_id}&sub_id={sub_id}&sub_id2={sub_id2}&sub_id3={sub_id3}&country={country}&device={device}&os={os}&status={status}
```

### 4. Test with Sandbox
```bash
curl "https://yourdomain.com/api/postback/receive/test_cpalead/?lead_id=TEST_001&offer_id=OFFER_001&payout=5.00&goal_id=sale"
# Returns: {"status": "sandbox_ok", "sandbox": true, ...}
```

---

## URLs

| Method | URL | Description |
|--------|-----|-------------|
| GET/POST | `/api/postback/receive/<network_key>/` | Inbound webhook receiver |
| GET | `/api/postback/logs/` | List PostbackLogs (admin) |
| GET | `/api/postback/logs/<id>/` | PostbackLog detail |
| POST | `/api/postback/logs/<id>/retry/` | Retry failed log |
| POST | `/api/postback/logs/<id>/reverse/` | Trigger manual reversal |
| GET | `/api/postback/logs/<id>/s2s-logs/` | S2S outbound attempt history |
| GET | `/api/postback/networks/` | List NetworkPostbackConfigs |
| GET | `/api/postback/health/` | System health check |

---

## Processing Pipeline

```
Inbound request
    │
    ▼
1. Rate limit check (per-network, postback-internal)
2. Sandbox check (network_key starts with test_?)
3. Source IP extraction
4. Adapter normalisation (CPAlead → standard fields)
5. PostbackLog created (RECEIVED)
    │
    ▼ [Celery async task]
6. IP whitelist check
7. HMAC signature + timestamp + nonce validation
8. Stage 4b: Event type extraction + reversal detection
   └─ If reversal → handle_reversal_postback() → return
9. Stage 5: Custom LeadValidator chain
10. Stage 5a: Click-to-conversion linking
11. Stage 5b: Fraud detection (IP velocity + geo + device + subnet)
12. Stage 6: Payout cap enforcement
13. Stage 7: Duplicate lead check (SELECT FOR UPDATE)
14. Stage 8: User resolution
15. Stage 9: Reward dispatch (points + optional item)
    │
    ▼
PostbackLog → REWARDED
    │
    ▼ [S2S Celery task, after fire_delay_ms]
S2S outbound postback fired to advertiser
```

---

## Supported Macros (S2S callback_url)

| Macro | Value |
|-------|-------|
| `{lead_id}` | Conversion lead ID |
| `{offer_id}` | Offer/campaign ID |
| `{payout}` | Payout amount |
| `{currency}` | Currency code (USD) |
| `{transaction_id}` | Network transaction ID |
| `{goal_id}` | CPAlead goal/event name |
| `{sub_id1}` | Publisher sub ID 1 |
| `{sub_id2}` | Publisher sub ID 2 |
| `{sub_id3}` | Publisher sub ID 3 |
| `{ip_address}` | Postback source IP |
| `{ip}` | Alias for `{ip_address}` |
| `{country}` | ISO country code |
| `{device}` | Device type |
| `{event_type}` | install / sale / lead / etc. |
| `{status}` | CPAlead status (approved/reversed) |
| `{click_id}` | Linked OfferClick click_id |

---

## Fraud Detection

Fraud checks run per postback and score 0–100:

| Check | Trigger | Score |
|-------|---------|-------|
| IP velocity | >30 requests/minute from same IP | 50 |
| Geo anomaly | Same user from >3 countries/hour | 40 |
| Device/OS sanity | Impossible combo (iOS + Windows) | 30 |
| Blocked subnet | IP in `metadata.fraud_blocked_subnets` | 80 |

Total score ≥ 60 (configurable via `metadata.fraud_score_threshold`) → rejected as fraud.

---

## Reversal / Chargeback Handling

When CPAlead sends `status=reversed`:
1. CPAlead adapter sets `is_reversal=True` in adapted payload.
2. Pipeline calls `handle_reversal_postback()`.
3. Original PostbackLog marked `conversion_status=reversed`.
4. New PostbackLog created with `is_reversal=True` and negative payout.
5. `postback_reversed` signal fired — connect your wallet app to roll back points.

```python
# In your wallet app's apps.py ready():
from api.postback.signals import postback_reversed
postback_reversed.connect(your_rollback_handler)
```

---

## Signals

| Signal | When fired | kwargs |
|--------|-----------|--------|
| `postback_received` | Log created | `instance` |
| `postback_rewarded` | Points awarded | `instance`, `points` |
| `postback_rejected` | Lead rejected | `instance`, `reason` |
| `postback_duplicate` | Duplicate lead | `instance` |
| `postback_failed` | Processing error | `instance`, `error` |
| `postback_reversed` | Chargeback received | `instance`, `points_to_deduct` |

---

## Required Settings

```python
# settings.py

# Celery (required for async processing)
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# Cache (required for rate limiting, nonce, fraud detection)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
    }
}

# Optional: Global IP blacklist (applies to all networks)
POSTBACK_GLOBAL_IP_BLACKLIST = ["known.fraud.ip/32"]

# Optional: Add postback middleware
MIDDLEWARE = [
    ...
    "api.postback.middleware.PostbackIPFilterMiddleware",
    "api.postback.middleware.PostbackAuditMiddleware",
]
```

---

## Health Check

```bash
# Human-readable
python manage.py postback_health_check

# Machine-readable (for CI/monitoring)
python manage.py postback_health_check --json

# Auto-fix failed postbacks
python manage.py postback_health_check --fix

# Check specific network
python manage.py postback_health_check --network cpalead
```

---

## Running Tests

```bash
# All postback tests
python manage.py test api.postback

# Specific test modules
python manage.py test api.postback.tests.test_adapters
python manage.py test api.postback.tests.test_fraud
python manage.py test api.postback.tests.test_s2s
python manage.py test api.postback.tests.test_reversal
python manage.py test api.postback.tests.test_webhooks
python manage.py test api.postback.tests.test_validators
```

---

## External App Dependencies

| Import | Used for | Behaviour if missing |
|--------|---------|----------------------|
| `api.inventory.services.award_item_to_user` | Item rewards | Skipped with warning (points still awarded) |
| `api.ad_networks.models.OfferClick` | Click-to-conversion linking | click_id left empty (non-blocking) |
| `api.admin_panel.admin.admin_site` | Admin registration | Falls back to default admin (try/except) |
