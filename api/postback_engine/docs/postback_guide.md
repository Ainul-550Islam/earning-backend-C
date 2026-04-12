# Postback Engine – Integration Guide

## Overview
The Postback Engine receives S2S (Server-to-Server) postbacks from CPA networks,
validates them, de-duplicates leads, and credits user wallets.

## Postback URL Format
```
GET /api/postback_engine/postback/{network_key}/?{params}
POST /api/postback_engine/postback/{network_key}/
```

## Standard Parameters
| Parameter       | Description                        |
|-----------------|------------------------------------|
| `lead_id`       | Unique lead/click ID from network  |
| `offer_id`      | Offer/campaign identifier          |
| `payout`        | Conversion payout amount           |
| `currency`      | Currency code (USD, BDT, etc.)     |
| `transaction_id`| Unique transaction ID              |
| `sig`           | HMAC-SHA256 signature              |
| `ts`            | Unix timestamp                     |

## Signature Verification
```
message = urlencode(sorted(params.items())) + f"&ts={timestamp}"
signature = hmac.new(SECRET_KEY, message, sha256).hexdigest()
```

## Network-Specific Param Names
Each network uses different param names. The Engine handles mapping via
`AdNetworkConfig.field_mapping`. Example for CPALead:
```json
{
  "lead_id": "sub1",
  "offer_id": "oid",
  "payout": "amount",
  "transaction_id": "sid"
}
```

## Response
The engine always returns `HTTP 200 OK` with a JSON body:
```json
{"status": "ok", "ref": "<raw_log_uuid>"}
```

## Adding a New Network
1. Create an `AdNetworkConfig` via Django Admin
2. Set `network_key`, `secret_key`, `field_mapping`
3. Use test mode to validate postbacks
4. Set status to `active`

## Fraud Detection
Fraud score 0–100 is computed per request.
- Score ≥ 60: flagged for review
- Score ≥ 80: auto-blocked + IP blacklisted

## Retry Policy
Failed postbacks are retried with exponential backoff:
- Attempt 1: +30s
- Attempt 2: +2 min
- Attempt 3: +5 min
- Attempt 4: +15 min
- Attempt 5: +1 hour
