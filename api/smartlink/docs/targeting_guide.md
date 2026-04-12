# SmartLink Targeting Guide

## 7 Targeting Dimensions

### 1. Geo Targeting (Country + Region + City)
```json
{
  "geo": {
    "mode": "whitelist",
    "countries": ["BD", "IN", "PK"],
    "regions": ["Dhaka Division", "Karnataka"],
    "cities": ["Dhaka", "Bangalore"]
  }
}
```
**Modes:** `whitelist` (only allow listed) | `blacklist` (block listed, allow rest)

### 2. Device Targeting
```json
{
  "device": {
    "mode": "whitelist",
    "device_types": ["mobile", "tablet"]
  }
}
```
**Types:** `mobile` | `tablet` | `desktop`

### 3. OS Targeting
```json
{
  "os": {
    "mode": "whitelist",
    "os_types": ["android", "ios"]
  }
}
```
**Types:** `android` | `ios` | `windows` | `mac` | `linux`

### 4. Browser Targeting
```json
{
  "browser": {
    "mode": "whitelist",
    "browsers": ["chrome", "safari"]
  }
}
```

### 5. Time Targeting (Day + Hour)
```json
{
  "time": {
    "days_of_week": [0, 1, 2, 3, 4],
    "start_hour": 9,
    "end_hour": 21,
    "timezone_name": "Asia/Dhaka"
  }
}
```
`days_of_week`: 0=Monday, 6=Sunday | `start_hour`/`end_hour`: 0-23 UTC

### 6. ISP / Carrier Targeting (Bangladesh example)
```json
{
  "isp": {
    "mode": "whitelist",
    "isps": ["Grameenphone", "Robi", "Banglalink", "Teletalk"],
    "asns": ["AS24389", "AS24386"]
  }
}
```

### 7. Language Targeting
```json
{
  "language": {
    "mode": "whitelist",
    "languages": ["bn", "en", "hi"]
  }
}
```

---

## AND vs OR Logic

```json
{
  "logic": "AND",
  "geo": {"mode": "whitelist", "countries": ["BD"]},
  "device": {"mode": "whitelist", "device_types": ["mobile"]}
}
```
**AND** = Must be Bangladesh AND mobile. US desktop → blocked.

```json
{
  "logic": "OR",
  "geo": {"mode": "whitelist", "countries": ["BD"]},
  "device": {"mode": "whitelist", "device_types": ["mobile"]}
}
```
**OR** = Bangladesh OR mobile. US desktop → blocked. US mobile → allowed.

---

## Test Targeting Rules
```http
POST /api/smartlink/smartlinks/{id}/targeting/{rule_id}/test/
{
  "country": "BD",
  "device_type": "mobile",
  "os": "android",
  "language": "bn",
  "isp": "Grameenphone"
}
```
Returns: `{"matched": true, "eligible_offers": 3}`
