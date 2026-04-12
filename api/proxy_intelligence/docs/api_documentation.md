# Proxy Intelligence — REST API Documentation

**Base URL:** `/api/proxy-intelligence/`
**Authentication:** JWT Bearer Token (`Authorization: Bearer <token>`)
**Content-Type:** `application/json`

---

## IP Intelligence

### Check a Single IP

```http
POST /api/proxy-intelligence/ip-intelligence/check/
```

**Request Body:**
```json
{
  "ip_address": "1.2.3.4",
  "include_geo": true,
  "include_threat_feeds": false,
  "include_vpn_check": true,
  "include_proxy_check": true,
  "include_tor_check": true,
  "strict_mode": false
}
```

**Response:**
```json
{
  "ip_address": "1.2.3.4",
  "risk_score": 75,
  "risk_level": "high",
  "recommended_action": "challenge",
  "is_vpn": true,
  "is_proxy": false,
  "is_tor": false,
  "is_datacenter": true,
  "is_blacklisted": false,
  "is_whitelisted": false,
  "vpn_provider": "NordVPN",
  "proxy_type": "",
  "country_code": "NL",
  "country_name": "Netherlands",
  "city": "Amsterdam",
  "region": "North Holland",
  "isp": "M247 Europe",
  "asn": "AS9009",
  "latitude": 52.3676,
  "longitude": 4.9041,
  "timezone": "Europe/Amsterdam",
  "fraud_score": 30,
  "abuse_confidence_score": 0,
  "detection_methods": ["asn_database", "isp_keyword_analysis"],
  "flags": ["vpn", "datacenter"],
  "response_time_ms": 45.2,
  "checked_at": "2025-01-15T10:30:00Z"
}
```

---

### Bulk IP Check

```http
POST /api/proxy-intelligence/ip-intelligence/bulk-check/
```

**Request Body:**
```json
{
  "ip_addresses": ["1.2.3.4", "5.6.7.8", "9.10.11.12"],
  "include_geo": false
}
```

**Response:**
```json
{
  "total": 3,
  "clean_count": 2,
  "flagged_count": 1,
  "blocked_count": 0,
  "response_time_ms": 120.5,
  "results": [...]
}
```

---

### Get IP Intelligence Record

```http
GET /api/proxy-intelligence/ip-intelligence/?ip=1.2.3.4
```

### List All IP Intelligence Records

```http
GET /api/proxy-intelligence/ip-intelligence/
GET /api/proxy-intelligence/ip-intelligence/?risk_level=high&is_vpn=true
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `ip` | string | Filter by exact IP |
| `risk_level` | string | `very_low`, `low`, `medium`, `high`, `critical` |
| `is_vpn` | bool | Filter VPN IPs |
| `is_proxy` | bool | Filter proxy IPs |
| `is_tor` | bool | Filter Tor IPs |
| `country_code` | string | Filter by country (e.g. `RU`) |

---

## Dashboard

### Get Dashboard Statistics

```http
GET /api/proxy-intelligence/dashboard/
```

**Response:**
```json
{
  "total_ips_checked": 15420,
  "high_risk_ips": 342,
  "vpn_detected": 891,
  "proxy_detected": 234,
  "tor_detected": 45,
  "blacklisted_ips": 127,
  "fraud_attempts_today": 23,
  "anomalies_today": 8,
  "high_risk_users": 156,
  "avg_risk_score": 18.4,
  "tor_exit_nodes_tracked": 1247,
  "malicious_ips_in_db": 4891
}
```

---

## Blacklist Management

### List Active Blacklisted IPs

```http
GET /api/proxy-intelligence/blacklist/
```

### Add IP to Blacklist

```http
POST /api/proxy-intelligence/blacklist/
```

```json
{
  "ip_address": "1.2.3.4",
  "reason": "fraud",
  "description": "Click fraud detected",
  "is_permanent": false,
  "expires_hours": 72
}
```

**Reason values:** `fraud`, `abuse`, `spam`, `bot`, `scraping`, `manual`, `threat_feed`, `rate_limit`

### Bulk Add to Blacklist

```http
POST /api/proxy-intelligence/blacklist/bulk-add/
```

```json
{
  "ip_addresses": ["1.2.3.4", "5.6.7.8"],
  "reason": "spam",
  "source": "threat_feed"
}
```

### Remove IP from Blacklist

```http
POST /api/proxy-intelligence/blacklist/{id}/deactivate/
```

---

## Whitelist Management

### List Whitelisted IPs

```http
GET /api/proxy-intelligence/whitelist/
```

### Add IP to Whitelist

```http
POST /api/proxy-intelligence/whitelist/
```

```json
{
  "ip_address": "203.0.113.0",
  "label": "Office Network",
  "description": "Dhaka HQ office IP"
}
```

---

## Tor Exit Nodes

### List Active Tor Exit Nodes

```http
GET /api/proxy-intelligence/tor-nodes/
```

### Sync Tor Node List

```http
POST /api/proxy-intelligence/tor-nodes/sync/
```

---

## Device Fingerprints

### Submit Device Fingerprint

```http
POST /api/proxy-intelligence/device-fingerprints/
```

```json
{
  "canvas_hash": "a3f5c2d1...",
  "webgl_hash": "b7e9a4c2...",
  "audio_hash": "c1d3e5f7...",
  "user_agent": "Mozilla/5.0 ...",
  "screen": "1920x1080",
  "timezone": "Asia/Dhaka",
  "language": "en-US",
  "platform": "Win32",
  "hardware_concurrency": 8,
  "device_memory": 8,
  "touch_points": 0,
  "plugins": ["PDF Viewer"],
  "fonts": ["Arial", "Verdana", "Times New Roman"]
}
```

**Response:**
```json
{
  "fingerprint_hash": "sha256hex...",
  "is_new": true,
  "is_suspicious": false,
  "spoofing_detected": false,
  "risk_score": 0,
  "flags": [],
  "device_type": "desktop",
  "browser_name": "Chrome",
  "os_name": "Windows"
}
```

---

## Fraud Attempts

### List Fraud Attempts

```http
GET /api/proxy-intelligence/fraud-attempts/
GET /api/proxy-intelligence/fraud-attempts/?status=detected&fraud_type=click_fraud
```

### Resolve a Fraud Attempt

```http
POST /api/proxy-intelligence/fraud-attempts/{id}/resolve/
```

```json
{
  "is_false_positive": false,
  "notes": "Confirmed: user submitted 47 fake completions"
}
```

---

## User Risk Profiles

### Get User Risk Profile

```http
GET /api/proxy-intelligence/risk-profiles/{user_id}/
```

**Response:**
```json
{
  "user_id": 12345,
  "overall_risk_score": 65,
  "risk_level": "high",
  "is_high_risk": true,
  "vpn_usage_detected": true,
  "multi_account_detected": false,
  "fraud_attempts_count": 3,
  "last_assessed": "2025-01-15T10:00:00Z"
}
```

### List High Risk Users

```http
GET /api/proxy-intelligence/risk-profiles/?is_high_risk=true
```

---

## Analytics

### Risk Distribution

```http
GET /api/proxy-intelligence/risk-profiles/distribution/
```

### Anomaly Detection Logs

```http
GET /api/proxy-intelligence/anomalies/
```

---

## Velocity Check

```http
POST /api/proxy-intelligence/velocity-check/
```

```json
{
  "ip_address": "1.2.3.4",
  "action_type": "login",
  "threshold": 5,
  "window_seconds": 60
}
```

**Response:**
```json
{
  "ip_address": "1.2.3.4",
  "action_type": "login",
  "request_count": 7,
  "threshold": 5,
  "window_seconds": 60,
  "exceeded": true,
  "recommended_action": "rate_limit"
}
```

---

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_IP` | IP address format is invalid |
| 403 | `IP_BLACKLISTED` | IP is on the active blacklist |
| 429 | `RATE_LIMITED` | Too many requests from this IP |
| 503 | `SERVICE_UNAVAILABLE` | External API temporarily down |

```json
{
  "error": "INVALID_IP",
  "message": "'999.999.999.999' is not a valid IP address.",
  "status_code": 400
}
```

---

## Pagination

All list endpoints support pagination:

```http
GET /api/proxy-intelligence/ip-intelligence/?page=2&page_size=50
```

```json
{
  "count": 15420,
  "next": "https://example.com/api/proxy-intelligence/ip-intelligence/?page=3",
  "previous": "https://example.com/api/proxy-intelligence/ip-intelligence/?page=1",
  "results": [...]
}
```
