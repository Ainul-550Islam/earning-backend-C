# Ainul Enterprise Engine — Webhook System API Reference

**Base URL:** `/api/webhooks/`  
**Authentication:** Bearer token or Session  
**Content-Type:** `application/json`

---

## 🔗 Core Endpoints

### Webhook Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/endpoints/` | List all endpoints |
| `POST` | `/endpoints/` | Create endpoint |
| `GET` | `/endpoints/{id}/` | Get endpoint |
| `PUT/PATCH` | `/endpoints/{id}/` | Update endpoint |
| `DELETE` | `/endpoints/{id}/` | Delete endpoint |
| `POST` | `/endpoints/{id}/test/` | Send test webhook |
| `POST` | `/endpoints/{id}/rotate-secret/` | Rotate HMAC secret |
| `POST` | `/endpoints/{id}/pause/` | Pause delivery |
| `POST` | `/endpoints/{id}/resume/` | Resume delivery |
| `GET` | `/endpoints/{id}/health-status/` | 24h health summary |
| `GET` | `/endpoints/{id}/delivery-logs/` | Delivery history |
| `GET` | `/endpoints/{id}/subscriptions/` | Active subscriptions |

### Subscriptions (nested under endpoints)
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/endpoints/{id}/subscriptions/` | List/create subscriptions |
| `GET/PUT/DELETE` | `/endpoints/{id}/subscriptions/{id}/` | Manage subscription |

### Delivery Logs
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/logs/` | List delivery logs |
| `GET` | `/logs/{id}/` | Get log detail |
| `POST` | `/logs/{id}/retry/` | Retry delivery |

### Emit
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/emit/` | Emit webhook event |
| `GET` | `/event-types/` | List event types |

---

## 📦 Advanced Endpoints

### Batches
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/batches/` | List/create batches |
| `POST` | `/batches/{id}/process/` | Start processing |
| `POST` | `/batches/{id}/cancel/` | Cancel batch |
| `POST` | `/batches/{id}/retry-failed/` | Retry failed items |
| `GET` | `/batches/{id}/progress/` | Get progress |
| `GET` | `/batches/{id}/status/` | Get status breakdown |
| `GET` | `/batches/stalled/` | Get stalled batches |
| `GET` | `/batches/status-overview/` | Status summary |

### Filters
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/filters/` | List/create filters |
| `GET/PUT/DELETE` | `/filters/{id}/` | Manage filter |

### Templates
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/templates/` | List/create templates |
| `POST` | `/templates/{id}/activate/` | Activate template |
| `POST` | `/templates/{id}/deactivate/` | Deactivate template |
| `POST` | `/templates/{id}/clone/` | Clone template |
| `POST` | `/templates/validate/` | Validate template syntax |
| `POST` | `/templates/bulk-activate/` | Bulk activate |

### Secrets
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/secrets/` | List secrets |
| `POST` | `/secrets/{id}/rotate/` | Rotate secret |

### Replay
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/replay/` | List/create replays |
| `POST` | `/replay/create-batch/` | Create replay batch |
| `GET` | `/replay/history/` | Replay history |
| `GET` | `/replay/statistics/` | Replay stats |
| `GET` | `/replay/{id}/items/` | Replay items |
| `GET` | `/replay/my-items/` | My replay items |

---

## 📊 Analytics & Observability

### Analytics
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/analytics/` | Analytics list |
| `GET` | `/analytics/health-summary/` | Health summary (all active endpoints) |
| `GET` | `/analytics/{id}/performance-report/` | Performance report |
| `GET` | `/analytics/{id}/event-stats/` | Event statistics |
| `POST` | `/analytics/{id}/export-csv/` | Export CSV |
| `GET` | `/analytics/routing-statistics/` | Routing stats |
| `GET` | `/analytics/orphaned-subscriptions/` | Orphaned subscriptions |
| `POST` | `/analytics/validate-routing/` | Validate routing |

### Health
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/health/` | Health log list |
| `POST` | `/health/check-health/` | Run health check |
| `GET` | `/health/batch-check/` | Batch health check |
| `GET` | `/health/{id}/trends/` | Health trends |
| `GET` | `/health/{id}/alerts/` | Health alerts |
| `POST` | `/health/{id}/ping/` | Live HTTP ping |
| `GET` | `/health/unhealthy-summary/` | Unhealthy endpoints |

### Rate Limits
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/rate-limits/` | Rate limit stats |
| `GET` | `/rate-limits/endpoint-summary/` | Per-endpoint summary |
| `GET` | `/rate-limits/top-consumers/` | Top by volume |
| `GET` | `/rate-limits/near-limit/` | Approaching quota |

### Retry Analysis
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/retry-analysis/` | Retry analysis list |
| `GET` | `/retry-analysis/worst-offenders/` | Highest failure rate |
| `GET` | `/retry-analysis/daily-trend/` | Daily trend |

---

## 📥 Inbound Webhooks

### Inbound Configuration
| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/inbound/` | List/create inbound configs |
| `POST` | `/inbound/{id}/activate/` | Activate |
| `POST` | `/inbound/{id}/deactivate/` | Deactivate |

### Inbound Logs
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/inbound-logs/` | Inbound log list |
| `GET` | `/inbound-logs/unprocessed/` | Unprocessed logs |
| `GET` | `/inbound-logs/invalid-signatures/` | Invalid sigs |
| `POST` | `/inbound-logs/bulk-process/` | Bulk process |

### Public Receiver (no auth — external providers)
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/receive/stripe/` | Receive from Stripe |
| `POST` | `/receive/bkash/` | Receive from bKash |
| `POST` | `/receive/nagad/` | Receive from Nagad |
| `POST` | `/receive/paypal/` | Receive from PayPal |
| `POST` | `/receive/{source}/` | Receive from any source |

---

## ♻️ Aging & Lifecycle

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/aging/endpoints/` | Endpoint aging records |
| `GET` | `/aging/logs/` | Log aging records |
| `GET` | `/aging/events/` | Aging events |
| `GET` | `/aging/summary/` | Aging summary |
| `GET/PUT` | `/aging/policy/` | Aging policy |
| `POST` | `/aging/archive/` | Manual archive (staff) |
| `POST` | `/aging/purge/` | Manual purge (staff) |

---

## 🔐 Admin (Superuser only)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/admin/webhooks/` | Admin endpoint list |
| `GET` | `/admin/webhooks/global-statistics/` | System-wide stats |
| `POST` | `/admin/webhooks/batch-operation/` | Bulk admin actions |
| `POST` | `/admin/webhooks/cleanup-data/` | Clean old data |
| `GET` | `/admin/webhooks/integration-status/` | Integration health |
| `POST` | `/admin/webhooks/integration-sync/` | Trigger sync |

---

## 📝 Request/Response Examples

### Create Endpoint
```json
POST /api/webhooks/endpoints/
{
  "label": "Payment Notifications",
  "target_url": "https://myapp.com/webhooks/payments",
  "http_method": "POST",
  "timeout_seconds": 30,
  "max_retries": 3
}
```
**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "label": "Payment Notifications",
  "target_url": "https://myapp.com/webhooks/payments",
  "status": "active",
  "secret_key": "whsec_...",
  "created_at": "2026-06-04T00:00:00Z"
}
```

### Emit Event
```json
POST /api/webhooks/emit/
{
  "event_type": "payment.succeeded",
  "payload": {
    "payment_id": "pay_abc123",
    "amount": 5000,
    "currency": "BDT"
  }
}
```

### Receive from bKash (public)
```json
POST /api/webhooks/receive/bkash/
Headers: X-bKash-Signature: sha256=abc123...
{
  "payment_ref_id": "MP2106161912341234",
  "amount": "500.00",
  "status": "Completed"
}
```
**Response 200:**
```json
{"received": true}
```

---

## ⚙️ Celery Beat Schedule

| Task | Frequency |
|------|-----------|
| retry_failed_dispatch | Every 5 min |
| auto_suspend_endpoints | Every 1 hour |
| health_check_all_endpoints | Every 1 hour |
| aging_full_sweep | Every 6 hours |
| aging_archive_due | Every 12 hours |
| analytics_daily | Daily 00:30 UTC |
| aging_purge_dry_run | Daily 01:00 UTC |
| sync_all_endpoints_with_integration | Every 6 hours |
| aging_purge_execute | Weekly Sunday 02:00 UTC |
| cleanup_all_old_data | Weekly Monday 04:30 UTC |

