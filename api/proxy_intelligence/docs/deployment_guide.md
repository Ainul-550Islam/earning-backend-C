# Proxy Intelligence — Production Deployment Guide

---

## 1. Requirements

```txt
Django>=4.2
djangorestframework>=3.14
celery>=5.3
redis>=4.6
requests>=2.31
geoip2>=4.7          # MaxMind integration
ipwhois>=1.2         # WHOIS lookups
scikit-learn>=1.3    # ML models (optional)
joblib>=1.3          # ML model serialization (optional)
kafka-python>=2.0    # Kafka streaming (optional)
channels>=4.0        # WebSocket notifications (optional)
```

```bash
pip install geoip2 ipwhois requests scikit-learn joblib
```

---

## 2. Django Settings

```python
# settings/base.py

INSTALLED_APPS += [
    'api.proxy_intelligence',
]

# ── Required: Cache (Redis) ──────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        }
    }
}

# ── Required: Celery ─────────────────────────────────────────────────────
CELERY_BROKER_URL    = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')

# ── Proxy Intelligence Config ────────────────────────────────────────────
PROXY_INTELLIGENCE = {
    'BLOCK_TOR':              True,
    'BLOCK_VPN':              False,
    'CHALLENGE_VPN':          True,
    'LOG_ALL_REQUESTS':       True,
    'RATE_LIMIT_PER_MINUTE':  120,
    'BLACKLIST_TTL_HOURS':    72,
    'CACHE_INTELLIGENCE_TTL': 3600,
    'ENABLE_ML_SCORING':      True,
    'MIN_RISK_SCORE_TO_LOG':  20,
}

# ── Third-Party API Keys ─────────────────────────────────────────────────
ABUSEIPDB_API_KEY         = env('ABUSEIPDB_API_KEY', default='')
IPQUALITYSCORE_API_KEY    = env('IPQUALITYSCORE_API_KEY', default='')
MAXMIND_ACCOUNT_ID        = env('MAXMIND_ACCOUNT_ID', default='')
MAXMIND_LICENSE_KEY       = env('MAXMIND_LICENSE_KEY', default='')
MAXMIND_CITY_DB           = env('MAXMIND_CITY_DB', default='/var/lib/geoip/GeoLite2-City.mmdb')
MAXMIND_ASN_DB            = env('MAXMIND_ASN_DB', default='/var/lib/geoip/GeoLite2-ASN.mmdb')
VIRUSTOTAL_API_KEY        = env('VIRUSTOTAL_API_KEY', default='')
SHODAN_API_KEY            = env('SHODAN_API_KEY', default='')
ALIENVAULT_API_KEY        = env('ALIENVAULT_API_KEY', default='')
CROWDSEC_API_KEY          = env('CROWDSEC_API_KEY', default='')

# ── Email alerts ─────────────────────────────────────────────────────────
PROXY_INTELLIGENCE_ADMIN_EMAILS = env.list('PI_ADMIN_EMAILS', default=[])
```

---

## 3. URL Configuration

```python
# config/urls.py
from django.urls import path, include

urlpatterns = [
    ...
    path('api/proxy-intelligence/', include('api.proxy_intelligence.urls')),
]
```

---

## 4. Middleware (Optional)

Add to automatically check every request:

```python
# settings.py
MIDDLEWARE = [
    ...
    'api.proxy_intelligence.middleware.ProxyIntelligenceMiddleware',
    ...
]
```

**Note:** Middleware uses `quick_check` (Redis cache only) — never blocks the request thread with external API calls.

---

## 5. Database Migration

```bash
python manage.py makemigrations proxy_intelligence
python manage.py migrate proxy_intelligence
python manage.py migrate
```

---

## 6. Initial Data Sync

Run these after first deployment:

```bash
# Sync Tor exit nodes (~1000-1500 nodes)
python manage.py sync_tor_nodes

# Update datacenter IP ranges (AWS, Cloudflare)
python manage.py update_ip_database

# Sync all active threat feeds
python manage.py sync_threat_feeds

# Verify everything is working
python manage.py pi_health_check
```

---

## 7. Celery Beat Schedule

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE.update({
    # Sync Tor exit nodes every 6 hours
    'pi-sync-tor-nodes': {
        'task': 'proxy_intelligence.sync_tor_exit_nodes',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    # Send daily risk summary at 8 AM
    'pi-daily-summary': {
        'task': 'proxy_intelligence.send_daily_risk_summary',
        'schedule': crontab(minute=0, hour=8),
    },
    # Clean up old logs daily at 2 AM
    'pi-cleanup-logs': {
        'task': 'proxy_intelligence.cleanup_old_logs',
        'schedule': crontab(minute=0, hour=2),
    },
    # Expire blacklist entries every 30 minutes
    'pi-expire-blacklist': {
        'task': 'proxy_intelligence.expire_blacklist_entries',
        'schedule': crontab(minute='*/30'),
    },
    # Sync threat feeds every 12 hours
    'pi-sync-threat-feeds': {
        'task': 'proxy_intelligence.sync_threat_feeds',
        'schedule': crontab(minute=0, hour='*/12'),
    },
})
```

---

## 8. Environment Variables

Create a `.env` file:

```env
# Redis
REDIS_URL=redis://localhost:6379/0

# AbuseIPDB
ABUSEIPDB_API_KEY=your_key_here

# IPQualityScore
IPQUALITYSCORE_API_KEY=your_key_here

# MaxMind
MAXMIND_ACCOUNT_ID=your_account_id
MAXMIND_LICENSE_KEY=your_license_key
MAXMIND_CITY_DB=/var/lib/geoip/GeoLite2-City.mmdb

# VirusTotal
VIRUSTOTAL_API_KEY=your_key_here

# Shodan
SHODAN_API_KEY=your_key_here

# AlienVault OTX
ALIENVAULT_API_KEY=your_key_here

# CrowdSec
CROWDSEC_API_KEY=your_key_here

# Admin alert emails (comma-separated)
PI_ADMIN_EMAILS=admin@example.com,security@example.com
```

---

## 9. Admin Setup

```python
# Add Proxy Intelligence admin to your INSTALLED_APPS
# Access at: https://yourdomain.com/admin/proxy_intelligence/
```

Key admin sections:
- **IP Intelligence** — search and audit detected IPs
- **IP Blacklist / Whitelist** — manage blocked/allowed IPs
- **Fraud Attempts** — review and resolve flagged events
- **Integration Credentials** — manage API keys per tenant
- **Fraud Rules** — configure detection rules
- **Alert Configurations** — set up webhook/email alerts
- **ML Model Metadata** — manage trained models
- **Tor Exit Nodes** — view synced nodes

---

## 10. Health Check

```bash
python manage.py pi_health_check
```

Expected output:
```
=== Proxy Intelligence Health Check ===

  ✓ [PASS] Database: IPIntelligence: 15420 records
  ✓ [PASS] Database: Blacklist: 127 active entries
  ✓ [PASS] Cache (Redis): Connected
  ✓ [PASS] Tor Exit Nodes: 1247 active
  ✓ [PASS] ML Models: 1 active models
  ✓ [PASS] Integration Credentials: 3 configured
  ✓ [PASS] Threat Feeds: 2 active feeds

7/7 checks passed.
```

---

## 11. Performance Tuning

### Redis Memory

```python
# Estimate: ~1KB per cached IP × concurrent unique IPs
# For 100k daily unique IPs: ~100MB Redis memory for PI cache
CACHES['default']['OPTIONS']['MAX_ENTRIES'] = 100000
```

### Database Indexes

The migration includes indexes on:
- `ip_address + tenant` (IPIntelligence lookup)
- `risk_score` (filtering high-risk IPs)
- `is_vpn + is_proxy + is_tor` (flag filtering)
- `ip_address + is_active` (blacklist lookup)

### Query Optimization

```python
# Use repository methods (they use select_related/only)
from api.proxy_intelligence.repository import IPIntelligenceRepository
high_risk = IPIntelligenceRepository.get_high_risk(threshold=61, limit=100)

# Never call full_check in a tight loop — use bulk check
from api.proxy_intelligence.services import IPIntelligenceService
result = svc.full_check('1.2.3.4', include_threat_feeds=False)
```
