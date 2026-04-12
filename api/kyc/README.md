# 🌍 World #1 KYC System — Complete Documentation

## 📦 Structure

```
kyc/
├── models.py              ← 23 model classes (3 original + 20 new)
├── views.py               ← 40+ API endpoints (all original + new)
├── serializers.py         ← 20+ serializers
├── urls.py                ← 35+ URL routes
├── services.py            ← 6 service classes
├── signals.py             ← Auto webhook + cache invalidation
├── apps.py                ← App config (original)
├── admin.py               ← Django admin (original)
├── forms.py               ← Forms (original)
├── constants.py           ← All constants
├── enums.py               ← Type-safe enums
├── exceptions.py          ← 30+ custom exceptions
├── managers.py            ← Custom QuerySets & Managers
├── validators.py          ← Field + model validators
├── permissions.py         ← DRF permission classes
├── filters.py             ← Django-filter integration
├── pagination.py          ← Pagination classes
├── throttling.py          ← Rate throttle classes
├── mixins.py              ← Reusable view mixins
├── selectors.py           ← Read-only query layer
├── querysets.py           ← Standalone queryset helpers
│
├── api/
│   ├── v1/urls.py         ← API v1 routes
│   └── v2/views.py + urls ← API v2 enhanced endpoints
│
├── utils/
│   ├── image_utils.py     ← Image processing (clarity, resize, face detect)
│   ├── ocr_utils.py       ← OCR extraction (Tesseract/Google/AWS)
│   ├── risk_utils.py      ← Risk scoring helpers
│   ├── cache_utils.py     ← Redis cache helpers
│   ├── audit_utils.py     ← Audit trail helpers
│   ├── phone_utils.py     ← BD phone normalization
│   └── encryption_utils.py← OTP hash, webhook signature, masking
│
├── security/
│   ├── fraud_detector.py  ← Multi-signal fraud detection engine
│   ├── rate_limiter.py    ← Redis-backed rate limiter
│   └── data_masker.py     ← PII masking (NID, phone, email, name)
│
├── tasks/
│   └── kyc_tasks.py       ← 12 Celery async tasks
│
├── reports/
│   └── generators.py      ← CSV / Excel / PDF report generators
│
├── management/commands/
│   ├── expire_kycs.py         ← python manage.py expire_kycs
│   ├── generate_kyc_analytics.py ← python manage.py generate_kyc_analytics
│   └── cleanup_kyc_data.py    ← python manage.py cleanup_kyc_data
│
├── migrations/
│   ├── 0001–0004          ← Original migrations (unchanged)
│   └── 0005_world1_new_models.py ← All 20 new models
│
└── tests/
    ├── factories.py        ← Test data creators
    ├── test_models.py      ← Model unit tests
    ├── test_views.py       ← API endpoint tests
    ├── test_services.py    ← Service + validator tests
    └── test_security.py    ← Fraud, masking, rate limit, encryption tests
```

---

## 🆕 23 Models

| # | Model | কাজ |
|---|-------|-----|
| 1 | `KYC` | Original ✅ |
| 2 | `KYCSubmission` | Original ✅ |
| 3 | `KYCVerificationLog` | Original ✅ |
| 4 | `KYCBlacklist` | Phone/doc/IP/email blacklisting |
| 5 | `KYCRiskProfile` | Detailed risk scoring profile |
| 6 | `KYCOCRResult` | OCR extraction data per document |
| 7 | `KYCFaceMatchResult` | Selfie vs ID face match result |
| 8 | `KYCWebhookEndpoint` | Tenant webhook configurations |
| 9 | `KYCWebhookDeliveryLog` | Every webhook delivery attempt |
| 10 | `KYCExportJob` | CSV/Excel/PDF export job tracking |
| 11 | `KYCBulkActionLog` | Bulk admin action audit |
| 12 | `KYCAdminNote` | Structured notes per KYC |
| 13 | `KYCRejectionTemplate` | Quick rejection reason templates |
| 14 | `KYCAnalyticsSnapshot` | Daily/hourly analytics snapshots |
| 15 | `KYCIPTracker` | IP fraud detection logs |
| 16 | `KYCDeviceFingerprint` | Device fingerprinting |
| 17 | `KYCVerificationStep` | Step-by-step progress tracking |
| 18 | `KYCOTPLog` | Phone OTP send/verify logs |
| 19 | `KYCTenantConfig` | Per-tenant KYC configuration |
| 20 | `KYCAuditTrail` | Immutable compliance audit trail |
| 21 | `KYCDuplicateGroup` | Duplicate record grouping |
| 22 | `KYCNotificationLog` | All notifications sent |
| 23 | `KYCFeatureFlag` | Runtime feature flags |

---

## 🌐 API Endpoints (35+)

### User Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/kyc/status/` | KYC submission status |
| GET/POST/DELETE | `/api/kyc/submit/` | Submit/update/delete KYC |
| POST | `/api/kyc/fraud-check/` | Trigger fraud check |
| GET | `/api/kyc/logs/` | User's own KYC logs |
| GET | `/api/kyc/notifications/my/` | User's notifications |
| POST | `/api/kyc/blacklist/check/` | Check if value is blacklisted |
| GET | `/api/kyc/health/` | Service health check |

### Admin Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/kyc/admin/list/` | All KYC records |
| GET | `/api/kyc/admin/stats/` | Dashboard stats |
| GET/POST/PATCH | `/api/kyc/admin/review/<id>/` | Review/approve/reject |
| DELETE | `/api/kyc/admin/delete/<id>/` | Delete KYC |
| POST | `/api/kyc/admin/reset/<id>/` | Reset to pending |
| GET | `/api/kyc/admin/logs/<id>/` | Audit logs |
| POST | `/api/kyc/admin/add-note/<id>/` | Add note |
| POST | `/api/kyc/admin/bulk-action/` | Bulk approve/reject |
| GET/POST | `/api/kyc/admin/notes/<id>/` | Structured notes |
| GET/POST | `/api/kyc/blacklist/` | Blacklist management |
| GET | `/api/kyc/admin/risk/<id>/` | Risk profile |
| POST | `/api/kyc/admin/risk/<id>/recompute/` | Recompute risk |
| GET | `/api/kyc/admin/analytics/` | Analytics snapshots |
| GET | `/api/kyc/admin/analytics/summary/` | Full summary |
| GET/PUT | `/api/kyc/admin/config/` | Tenant config |
| GET/POST | `/api/kyc/admin/webhooks/` | Webhook management |
| GET | `/api/kyc/admin/audit-trail/` | Full audit trail |
| GET/POST | `/api/kyc/admin/feature-flags/` | Feature flags |
| PATCH | `/api/kyc/admin/feature-flags/<key>/toggle/` | Toggle flag |
| GET | `/api/kyc/admin/duplicates/` | Duplicate groups |
| POST | `/api/kyc/admin/duplicates/<id>/resolve/` | Resolve duplicate |
| GET/POST | `/api/kyc/admin/exports/` | Export jobs |

---

## ⚡ Setup

### 1. Migration
```bash
python manage.py migrate kyc
```

### 2. Celery Beat Schedule (settings.py)
```python
CELERY_BEAT_SCHEDULE = {
    'expire-kycs-daily': {
        'task': 'api.kyc.tasks.kyc_tasks.expire_overdue_kycs',
        'schedule': crontab(hour=1, minute=0),
    },
    'notify-expiring-kycs': {
        'task': 'api.kyc.tasks.kyc_tasks.notify_expiring_soon_kycs',
        'schedule': crontab(hour=8, minute=0),
    },
    'daily-analytics': {
        'task': 'api.kyc.tasks.kyc_tasks.generate_daily_analytics',
        'schedule': crontab(hour=0, minute=30),
    },
    'cleanup-kyc-data': {
        'task': 'api.kyc.tasks.kyc_tasks.cleanup_old_export_jobs',
        'schedule': crontab(hour=2, minute=0),
    },
}
```

### 3. Management Commands
```bash
python manage.py expire_kycs                    # Expire overdue KYCs
python manage.py expire_kycs --dry-run          # Preview only
python manage.py generate_kyc_analytics --days 7  # Last 7 days analytics
python manage.py cleanup_kyc_data --days 30     # Clean old export/OTP data
```

### 4. Optional: Include versioned API URLs (settings/urls.py)
```python
urlpatterns += [
    path('api/kyc/v1/', include('api.kyc.api.v1.urls')),
    path('api/kyc/v2/', include('api.kyc.api.v2.urls')),
]
```

---

## ✅ Tests
```bash
python manage.py test api.kyc.tests
```
