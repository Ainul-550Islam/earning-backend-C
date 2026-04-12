# SmartLink API Reference

## Authentication

### Get JWT Token
```http
POST /api/auth/token/
Content-Type: application/json

{"username": "publisher1", "password": "mypassword"}
```
Response:
```json
{"access": "eyJ...", "refresh": "eyJ..."}
```

### Use Token
```http
GET /api/smartlink/smartlinks/
Authorization: Bearer eyJ...
```

### API Key (for integrations)
```http
GET /api/smartlink/smartlinks/
X-SmartLink-API-Key: your-api-key-here
```

---

## SmartLink Endpoints

### Create SmartLink with Full Config
```http
POST /api/smartlink/smartlinks/generate/
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "name": "Bangladesh Mobile Campaign",
  "type": "geo_specific",
  "rotation_method": "epc_optimized",
  "offers": [
    {"offer_id": 101, "weight": 600, "cap_per_day": 500},
    {"offer_id": 102, "weight": 400, "cap_per_day": 300}
  ],
  "fallback_url": "https://fallback.example.com",
  "targeting": {
    "logic": "AND",
    "geo":    {"mode": "whitelist", "countries": ["BD"]},
    "device": {"mode": "whitelist", "device_types": ["mobile"]},
    "os":     {"mode": "whitelist", "os_types": ["android"]},
    "isp":    {"mode": "whitelist", "isps": ["Grameenphone", "Robi"]},
    "time":   {"days_of_week": [0,1,2,3,4,5,6], "start_hour": 8, "end_hour": 22}
  },
  "rotation": {
    "auto_optimize_epc": true,
    "optimization_interval_minutes": 30
  }
}
```

### Redirect URL
```http
GET /go/abc123/?sub1=campaign1&sub2=adset1&sub3=creative1
→ HTTP 302 → https://offer.example.com/lp?sub1=campaign1&...
```

---

## Postback (S2S Conversion)
```http
GET /postback/?click_id=123&offer_id=456&payout=2.50&token=abc123de
→ HTTP 200 OK

# Pixel postback (returns 1×1 transparent GIF)
GET /pixel/?click_id=123&offer_id=456&payout=2.50
→ HTTP 200 image/gif
```

---

## WebSocket

### Live SmartLink Stats
```javascript
const ws = new WebSocket('wss://api.example.com/ws/smartlink/abc123/live/');
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  // data.type: 'snapshot' | 'click' | 'conversion' | 'stats_update'
  console.log(data);
};
// Send ping
ws.send(JSON.stringify({type: 'ping'}));
```

---

## Error Responses

All errors return:
```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Validation failed. Please check your input.",
    "request_id": "a1b2c3d4",
    "status": 400,
    "field_errors": {
      "slug": ["This slug is already in use."]
    }
  }
}
```

| Code | Status | Meaning |
|---|---|---|
| `not_authenticated` | 401 | No or invalid token |
| `permission_denied` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `validation_error` | 400 | Invalid input |
| `slug_conflict` | 409 | Slug already taken |
| `slug_reserved` | 400 | Slug is reserved |
| `no_offer_available` | 503 | No offers in pool match |
| `offer_cap_reached` | 503 | Offer cap exhausted |
| `rate_limit_exceeded` | 429 | Too many requests |
| `click_blocked` | 403 | Fraud/bot blocked |
| `smartlink_inactive` | 410 | Link is disabled |
