# Proxy Intelligence Module

A comprehensive fraud detection and IP intelligence system for Django-based earning/marketing platforms.

## Overview

The `proxy_intelligence` module provides real-time detection of VPNs, proxies, Tor exit nodes, botnets, fraud rings, and suspicious user behavior. It is designed to protect marketing platforms, earning systems, and multi-tenant SaaS products from click fraud, incentive abuse, and identity fraud.

## Features

| Feature | Description |
|---------|-------------|
| **VPN Detection** | 7-signal VPN detection: ASN, ISP keywords, hostname, HTTP headers, port scan, threat DB, datacenter ASN |
| **Proxy Detection** | HTTP, SOCKS4/5, residential, mobile, SSH tunnel, datacenter proxy detection |
| **Tor Detection** | Real-time Tor exit node list synced from the Tor Project |
| **Fraud Detection** | Click fraud, conversion fraud, multi-account detection, velocity checks |
| **Threat Intelligence** | AbuseIPDB, VirusTotal, Shodan, AlienVault OTX, CrowdSec integration |
| **ML Risk Scoring** | Scikit-learn based fraud classifier with 21-feature vector |
| **Device Fingerprinting** | Canvas, WebGL, Audio fingerprint processing with spoofing detection |
| **Real-time Alerts** | Webhook, Slack, Discord, WebSocket alert dispatch |
| **Geographic Heatmaps** | Country-level risk aggregation and trend analysis |

## Quick Start

```bash
# 1. Add to INSTALLED_APPS
INSTALLED_APPS += ['api.proxy_intelligence']

# 2. Add URL patterns
path('api/proxy-intelligence/', include('api.proxy_intelligence.urls'))

# 3. Migrate
python manage.py migrate

# 4. Sync initial data
python manage.py sync_tor_nodes
python manage.py update_ip_database
python manage.py sync_threat_feeds

# 5. Health check
python manage.py pi_health_check
```

## Documentation

| Document | Description |
|----------|-------------|
| [API Documentation](api_documentation.md) | REST API endpoints and request/response formats |
| [Deployment Guide](deployment_guide.md) | Production setup, Celery tasks, environment variables |
| [Integration Guide](integration_guide.md) | Third-party API setup (MaxMind, AbuseIPDB, IPQS, etc.) |
| [Fraud Rules Guide](fraud_rules_guide.md) | Configuring and tuning fraud detection rules |
| [Architecture](architecture.md) | System design, data flow, and component overview |

## Module Structure

```
proxy_intelligence/
├── models.py                   # 24 Django models
├── services.py                 # 12 service classes (business logic)
├── views.py                    # REST API ViewSets
├── serializers.py              # DRF serializers
├── schemas.py                  # Typed dataclass DTOs
├── repository.py               # Data access layer (10 repositories)
├── middleware.py               # Request-level IP checking
├── tasks.py                    # Celery async tasks
├── signals.py                  # Django signal handlers
├── detection_engines/          # 12 detection engines
├── ip_intelligence/            # 10 IP data enrichment modules
├── ai_ml_engines/              # 8 ML/AI components
├── fraud_detection/            # 10 fraud detection modules
├── threat_intelligence/        # 12 threat feed integrations
├── analytics_reporting/        # 8 analytics and reporting modules
├── real_time_processing/       # 6 real-time event processing modules
├── database_models/            # 20 model manager/helper classes
├── integrations/               # 12 third-party API integrations
├── utilities/                  # 13 utility classes
├── testing/                    # 8 test and benchmark files
├── scripts/                    # 6 CLI management scripts
├── migrations/                 # Database migrations
└── docs/                       # This documentation
```

## Risk Score Reference

| Score | Level | Action |
|-------|-------|--------|
| 0–20  | Very Low | Allow |
| 21–40 | Low | Allow |
| 41–60 | Medium | Flag |
| 61–80 | High | Challenge (CAPTCHA/2FA) |
| 81–100| Critical | Block |

## License

Internal use only. Not for redistribution.
