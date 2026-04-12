# PostbackEngine API Reference

## Base URL
`/api/postback_engine/`

## Authentication
All admin endpoints require JWT token: `Authorization: Bearer <token>`

---

## Postback Endpoints

### Receive Postback (GET/POST)
`GET /postback/{network_key}/`

Receives an incoming postback from a CPA network.

**Query Parameters** (network-specific, mapped by adapter):
| Standard Field | CPALead | AdGate | OfferToro |
|---|---|---|---|
| `lead_id` | `sub1` | `user_id` | `user_id` |
| `payout` | `amount` | `reward` | `amount` |
| `offer_id` | `oid` | `offer_id` | `oid` |
| `transaction_id` | `sid` | `token` | `trans_id` |
| `status` | `status` | `status` | `type` |

**Response:**
```json
{"status": "ok", "message": "Postback processed"}
```

**Status Codes:**
- `200` — Processed (approved or duplicate)
- `400` — Rejected (fraud, invalid signature, schema error)
- `404` — Network not found

---

## Analytics Endpoints

### Real-time Stats
`GET /analytics/realtime/`

Returns last 5 minutes of activity from Redis counters.

```json
{
  "clicks": 234,
  "conversions": 12,
  "revenue_usd": 8.50,
  "fraud_attempts": 3,
  "cr_pct": 5.13,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Network Performance
`GET /analytics/networks/?days=30`

Per-network performance summary.

---

## Conversion Endpoints

### List Conversions
`GET /conversions/?page=1&status=approved`

### Get Conversion
`GET /conversions/{id}/`

### Approve Conversion
`POST /conversions/{id}/approve/`

### Reverse Conversion
`POST /conversions/{id}/reverse/`
```json
{"reason": "chargeback"}
```

---

## Admin Endpoints

### Queue Stats
`GET /admin/queue/stats/`

### Replay Failed
`POST /admin/replay/?network=cpalead&limit=100`

### Health Check
`GET /admin/health/`
