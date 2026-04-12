# Third-Party Integration Guide

This guide covers setting up all external API integrations for the proxy_intelligence module.
All API keys are stored in the `IntegrationCredential` model for per-tenant management,
with fallback to Django settings and environment variables.

---

## 1. MaxMind GeoIP2

**Purpose:** IP geolocation (country, city, lat/lng), ISP, ASN, and anonymizer detection (VPN/proxy flags on Insights plan).

### Setup

```bash
pip install geoip2
```

### Option A: Local Database (Free — GeoLite2)

```bash
# Download GeoLite2 databases (requires free MaxMind account)
wget "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=YOUR_KEY&suffix=tar.gz"
tar -xzf GeoLite2-City_*.tar.gz
mv GeoLite2-City.mmdb /var/lib/geoip/
```

```python
# settings.py
MAXMIND_CITY_DB    = '/var/lib/geoip/GeoLite2-City.mmdb'
MAXMIND_ASN_DB     = '/var/lib/geoip/GeoLite2-ASN.mmdb'
MAXMIND_COUNTRY_DB = '/var/lib/geoip/GeoLite2-Country.mmdb'
```

### Option B: Web Service (Paid — GeoIP2 Precision)

```python
# settings.py
MAXMIND_ACCOUNT_ID  = env('MAXMIND_ACCOUNT_ID')
MAXMIND_LICENSE_KEY = env('MAXMIND_LICENSE_KEY')
```

### Via IntegrationCredential (per-tenant)

```python
from api.proxy_intelligence.models import IntegrationCredential

IntegrationCredential.objects.create(
    tenant=tenant,
    service='maxmind',
    api_key='YOUR_LICENSE_KEY',           # stored as api_key
    config={'account_id': 'YOUR_ACCOUNT_ID', 'db_path': '/var/lib/geoip/GeoLite2-City.mmdb'},
    is_active=True,
)
```

---

## 2. IPQualityScore (IPQS)

**Purpose:** Proxy/VPN/Tor/bot detection, fraud scoring, abuse velocity.

### Plans
- Free: 5,000 requests/month
- Paid: Higher limits + residential proxy detection

### Setup

```python
# settings.py
IPQUALITYSCORE_API_KEY = env('IPQUALITYSCORE_API_KEY')
```

### Via IntegrationCredential

```python
IntegrationCredential.objects.create(
    tenant=tenant,
    service='ipqualityscore',
    api_key='YOUR_IPQS_API_KEY',
    daily_limit=5000,
    is_active=True,
)
```

### Test

```python
from api.proxy_intelligence.integrations.ipqualityscore_integration import IPQualityScoreIntegration
result = IPQualityScoreIntegration().check('1.2.3.4')
print(result)
```

---

## 3. AbuseIPDB

**Purpose:** Community-reported IP abuse database. Covers spam, brute force, bots, proxies.

### Plans
- Free: 1,000 checks/day
- Basic: 10,000/day | Premium: unlimited

### Setup

```python
# settings.py
ABUSEIPDB_API_KEY = env('ABUSEIPDB_API_KEY')
```

### Via IntegrationCredential

```python
IntegrationCredential.objects.create(
    tenant=tenant,
    service='abuseipdb',
    api_key='YOUR_ABUSEIPDB_KEY',
    daily_limit=1000,
    is_active=True,
)
```

### Test

```python
from api.proxy_intelligence.integrations.abuseipdb_integration import AbuseIPDBIntegration
result = AbuseIPDBIntegration().check('1.2.3.4')
print(f"Confidence: {result['abuse_confidence_score']}%")
```

---

## 4. VirusTotal

**Purpose:** IP reputation from 70+ antivirus engines. Detects malware, phishing, botnets.

### Plans
- Free: 4 requests/minute, 500/day
- Premium: Higher limits

### Setup

```python
# settings.py
VIRUSTOTAL_API_KEY = env('VIRUSTOTAL_API_KEY')
```

### Via IntegrationCredential

```python
IntegrationCredential.objects.create(
    tenant=tenant,
    service='virustotal',
    api_key='YOUR_VT_API_KEY',
    daily_limit=500,
    is_active=True,
)
```

---

## 5. Shodan

**Purpose:** Check device exposure, open ports, known vulnerabilities.

### Setup

```python
# settings.py
SHODAN_API_KEY = env('SHODAN_API_KEY')
```

### Via IntegrationCredential

```python
IntegrationCredential.objects.create(
    tenant=tenant,
    service='shodan',
    api_key='YOUR_SHODAN_KEY',
    is_active=True,
)
```

---

## 6. AlienVault OTX

**Purpose:** Open Threat Exchange — community threat intelligence with IP reputation.

### Setup

```python
# settings.py
ALIENVAULT_API_KEY = env('ALIENVAULT_API_KEY')
```

### Free registration at: https://otx.alienvault.com

---

## 7. CrowdSec

**Purpose:** Community-driven IP blocklist. Detects brute force, scanners, exploits.

### Setup

```python
# settings.py
CROWDSEC_API_KEY = env('CROWDSEC_API_KEY')
```

### Register at: https://app.crowdsec.net

---

## 8. FraudLabsPro

**Purpose:** Fraud scoring for IPs, emails, and transactions.

```python
# settings.py
FRAUDLABSPRO_API_KEY = env('FRAUDLABSPRO_API_KEY')
```

---

## 9. AbstractAPI

**Purpose:** IP geolocation with VPN/proxy/Tor detection.

```python
# settings.py
ABSTRACTAPI_API_KEY = env('ABSTRACTAPI_API_KEY')
```

---

## 10. ip-api / ipinfo.io

**Purpose:** Free-tier geolocation fallback (no API key required for basic use).

```python
# settings.py
IPAPI_API_KEY  = env('IPAPI_API_KEY', default='')   # Optional for pro features
IPINFO_API_KEY = env('IPINFO_API_KEY', default='')  # Optional for higher limits
```

---

## Managing Credentials via Admin

1. Go to Django Admin → **Proxy Intelligence** → **Integration Credentials**
2. Click **Add Integration Credential**
3. Select service, enter API key, set daily limit
4. Save and set `is_active = True`

The system automatically loads the credential for the correct tenant on each API call.

---

## Priority Order

For each integration, the system tries in this order:
1. `IntegrationCredential` model (tenant-specific, highest priority)
2. Django `settings.py` variable
3. OS environment variable

---

## Recommended Minimum Setup

For a production marketing/earning platform, we recommend:

| Integration | Tier | Purpose |
|-------------|------|---------|
| MaxMind GeoLite2 | Free | Geolocation (local DB, no quota) |
| AbuseIPDB | Free (1k/day) | IP abuse reports |
| IPQS | Free (5k/month) | VPN/proxy/bot detection |
| CrowdSec | Free | Community blocklist |

For higher accuracy add:
- MaxMind Insights (paid) — VPN/proxy flags built-in
- VirusTotal (paid) — malware/botnet engine votes
