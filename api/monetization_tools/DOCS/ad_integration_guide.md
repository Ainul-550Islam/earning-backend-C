# Ad Network Integration Guide

## Overview

monetization_tools supports multiple ad networks via a unified
mediation waterfall. Networks are configured in the Django admin
under **Monetization Tools > Ad Networks**.

---

## Supported Networks

| Network | Type | Postback | Bidding |
|---------|------|----------|---------|
| Google AdMob | CPM / Rewarded | Yes | Yes |
| Meta Audience Network | CPM / Native | Yes | Yes |
| AppLovin MAX | CPM / Rewarded | Yes | Yes |
| Unity Ads | CPM / Rewarded | Yes | No |
| IronSource | CPM / Offerwall | Yes | Yes |
| Vungle (Liftoff) | CPM / Rewarded | Yes | No |
| Chartboost | CPM / Rewarded | Yes | No |
| Tapjoy | CPA / Offerwall | Yes | No |
| Fyber (Digital Turbine) | CPM / Rewarded | Yes | No |

---

## Network Setup

### 1. Create AdNetwork record
```python
from api.monetization_tools.models import AdNetwork

AdNetwork.objects.create(
    network_type="admob",
    display_name="Google AdMob",
    api_key="YOUR_API_KEY",
    app_id="ca-app-pub-XXXXXXXX~YYYYYYYY",
    reporting_api_key="YOUR_REPORTING_KEY",
    priority=1,
    revenue_share=Decimal("0.70"),  # 70% to publisher
    floor_ecpm=Decimal("0.5000"),
    timeout_ms=300,
    is_active=True,
)
```

### 2. Add to Waterfall
```python
from api.monetization_tools.models import WaterfallConfig

WaterfallConfig.objects.create(
    ad_unit=ad_unit,
    ad_network=admob_network,
    priority=1,
    floor_ecpm=Decimal("0.5000"),
    timeout_ms=300,
    is_active=True,
)
```

---

## Postback Configuration

### Postback URL Format
```
https://yourdomain.com/api/monetization/postback/{network_type}/
```

### Required Parameters (universal)
| Parameter | Description |
|-----------|-------------|
| `txn_id` | Unique transaction ID from the network |
| `user_id` | Your internal user identifier |
| `offer_id` | Offer ID (for offerwall completions) |
| `reward` | Coin reward amount |
| `payout` | Revenue payout in USD |
| `sig` | HMAC signature for validation |

### Network-Specific Postback Params

#### Google AdMob / AdColony
```
?txn_id=TX123&user_id=UID&reward=100&currency=coins&sig=HMAC
```

#### IronSource / Tapjoy
```
?userId=UID&offerId=OID&amount=100&currency=Coins&verifier=MD5
```

#### Unity Ads
```
?productId=OID&gameUserId=UID&amount=100&sid=SID&hmac=HMAC
```

---

## Signature Validation

All postbacks are validated using HMAC-SHA256 (or MD5 for legacy):

```python
from api.monetization_tools.utils import verify_hmac_signature

is_valid = verify_hmac_signature(
    payload=request_body_or_query_string,
    signature=request.GET.get("sig"),
    secret=network.postback_secret,
)
```

Configure `postback_secret` in the AdNetwork record.

---

## Mediation Waterfall Logic

1. Request comes in for an ad unit
2. Header bidding partners bid in parallel (timeout: configurable)
3. Highest bid above floor price wins
4. If no bidder: waterfall starts at priority=1
5. Each network is tried in order until fill or timeout
6. Fill rate and eCPM are tracked per network per day

---

## Floor Price Configuration

Set via `FloorPriceConfig`:
```python
FloorPriceConfig.objects.create(
    ad_network=admob,
    country="US",
    ad_format="rewarded_video",
    device_type="mobile",
    floor_ecpm=Decimal("3.0000"),
    is_active=True,
)
```

Use the script for bulk updates:
```bash
python SCRIPTS/update_ad_config.py --action floor_price \
  --network admob --country US --format rewarded_video --ecpm 3.50
```
