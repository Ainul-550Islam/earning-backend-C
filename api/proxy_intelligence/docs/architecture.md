# Proxy Intelligence — Architecture Guide

## System Overview

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────────┐
│          ProxyIntelligenceMiddleware             │
│  1. Extract real client IP                      │
│  2. Blacklist check (Redis cache <1ms)          │
│  3. Whitelist check (Redis cache <1ms)          │
│  4. Velocity check (Redis atomic counter)       │
│  5. Attach request.client_ip                    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│          RealTimeScorer (cache-only ~5ms)        │
│  - Reads IPIntelligence from Redis               │
│  - Returns: risk_score, action, flags            │
└──────────────────────┬──────────────────────────┘
                       │ (if cache miss)
                       ▼
┌─────────────────────────────────────────────────┐
│       IPIntelligenceService.full_check()        │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │VPNDetect │ │ProxyDet. │ │TorDetect │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │DCDetect  │ │ASNLookup │ │ThreatDB  │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                 │
│  ▼ RiskScoringService.calculate()               │
│  ▼ IPIntelligence DB write                      │
│  ▼ UserRiskProfile update                       │
│  ▼ Cache set (TTL=1h)                           │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
            IPDetectionResult
     (risk_score, action, flags, geo)
```

---

## Data Flow

### Request Processing (< 5ms for cached IPs)

```
Request → Middleware → Redis Cache HIT → Score → Response
                    ↘ Cache MISS → Full Check → DB Write → Cache SET → Score → Response
```

### Full Check Flow (50-500ms for uncached IPs)

```
IP Address
    │
    ├── VPNDetector          (ASN + ISP + hostname + headers + ports + DB)
    ├── ProxyDetector        (headers + ports + type classification)
    ├── TorDetector          (exit node list lookup)
    ├── DatacenterDetector   (ASN + CIDR + ISP keyword)
    ├── ASNLookup            (MaxMind / ip-api)
    │
    ├── [optional] AbuseIPDB check
    ├── [optional] IPQS check
    │
    ▼
RiskScoringService.calculate({
    is_tor=45pts, is_vpn=30pts, is_proxy=20pts,
    is_datacenter=10pts, abuse_score×0.4, fraud_score×0.2
})
    │
    ├── IPIntelligence.update_or_create()
    ├── VPNDetectionLog.create()  (if VPN detected)
    ├── UserRiskProfile.update()  (if user authenticated)
    ├── AlertDispatcher.dispatch() (if score >= 61)
    └── Cache.set(TTL=3600)
```

---

## Component Map

### Core Layer
| Component | File | Responsibility |
|-----------|------|----------------|
| Services | `services.py` | Business logic orchestration |
| Models | `models.py` | 24 Django ORM models |
| Repository | `repository.py` | Data access layer |
| Schemas | `schemas.py` | Typed DTOs |
| Cache | `cache.py` | Redis key management |
| Middleware | `middleware.py` | Request interception |

### Detection Engines
| Engine | File | Signals Used |
|--------|------|-------------|
| VPN | `vpn_detector.py` | ASN, ISP, hostname, headers, ports, threat DB |
| Proxy | `proxy_detector.py` | Headers, ports, type classification |
| Tor | `tor_detector.py` | Exit node list, DNSBL |
| Datacenter | `datacenter_detector.py` | ASN prefix, CIDR ranges, ISP keywords |
| Residential Proxy | `residential_proxy_detector.py` | ISP keywords, threat DB |
| Mobile Proxy | `mobile_proxy_detector.py` | Carrier detection |
| SOCKS | `socks_detector.py` | Port scan (1080, 9050) |
| HTTP Proxy | `http_proxy_detector.py` | Headers, port scan |
| SSH Tunnel | `ssh_tunnel_detector.py` | Port scan, banner grab |
| DNS Leak | `dns_leak_detector.py` | IP vs DNS country mismatch |
| WebRTC Leak | `webrtc_leak_detector.py` | Public IP exposure via WebRTC |
| IP Rotation | `ip_rotation_detector.py` | Multiple IPs per session |

### Risk Score Weights

```
Signal                  Weight
──────────────────────────────
is_tor                  +45 pts
malicious_db_match      +35 pts
is_vpn × confidence     +30 pts
multi_account_detected  +20 pts
is_proxy × confidence   +20 pts
is_datacenter           +10 pts
abuse_score × 0.4       +0-40 pts
fraud_score × 0.2       +0-20 pts
velocity_exceeded       +15 pts
device_spoofing         +15 pts

Maximum                 100 pts
```

### Cache Keys (Redis)

```
pi:intel:{ip}           IPIntelligence data       TTL: 1h
pi:bl:{ip}              Blacklist status           TTL: 5m
pi:wl:{ip}              Whitelist status           TTL: 5m
pi:vpn_detect:{ip}      VPN detection result      TTL: 1h
pi:tor_check:{ip}       Tor check result          TTL: 1h
pi:vel:{ip}:{action}    Velocity counter           TTL: window_sec
pi:geo:{ip}             Geolocation data          TTL: 24h
pi:abuse:{ip}           AbuseIPDB result          TTL: 4h
pi:ipqs:{ip}            IPQS result               TTL: 4h
pi:dashboard_stats:*    Dashboard KPIs            TTL: 5m
```

---

## Database Schema

### 6 Model Categories

**IP Core (5 models)**
`IPIntelligence` → `VPNDetectionLog`, `ProxyDetectionLog`, `TorExitNode`, `DatacenterIPRange`

**Fraud Behavior (5 models)**
`FraudAttempt` → `ClickFraudRecord`, `DeviceFingerprint`, `MultiAccountLink`, `VelocityMetric`

**Threat Intelligence (4 models)**
`IPBlacklist`, `IPWhitelist`, `ThreatFeedProvider` → `MaliciousIPDatabase`

**AI Scoring (4 models)**
`UserRiskProfile` → `RiskScoreHistory`, `MLModelMetadata`, `AnomalyDetectionLog`

**Config Rules (3 models)**
`FraudRule`, `AlertConfiguration`, `IntegrationCredential`

**Audit Logs (3 models)**
`APIRequestLog`, `PerformanceMetric`, `SystemAuditTrail`

---

## Celery Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `sync_tor_exit_nodes` | Every 6h | Sync Tor exit node list |
| `send_daily_risk_summary` | Daily 8 AM | Email daily digest |
| `cleanup_old_logs` | Daily 2 AM | Delete old API logs |
| `sync_threat_feeds` | Every 12h | Refresh threat feed data |
| `expire_blacklist_entries` | Every 30min | Deactivate expired blacklists |

---

## Performance Targets

| Operation | Target Latency |
|-----------|---------------|
| Cached IP check (middleware) | < 5ms |
| Full IP check (no external APIs) | < 100ms |
| Full IP check (with AbuseIPDB) | < 500ms |
| Bulk IP check (100 IPs) | < 5s |
| Dashboard stats (cached) | < 10ms |
