# analytics_warehouse/urls.py
"""
Analytics Warehouse URL routing।

Project-level urls.py-তে include করো:
  from django.urls import path, include
  urlpatterns += [path('api/warehouse/', include('analytics_warehouse.urls'))]

সব endpoint:
  GET  /api/warehouse/publisher-records/           — list
  GET  /api/warehouse/publisher-records/{id}/      — detail
  GET  /api/warehouse/publisher-records/summary/   — aggregate summary

  GET  /api/warehouse/site-records/
  GET  /api/warehouse/app-records/
  GET  /api/warehouse/ad-unit-records/
  GET  /api/warehouse/impression-records/
  GET  /api/warehouse/impression-records/totals/
  GET  /api/warehouse/click-records/
  GET  /api/warehouse/revenue-records/
  GET  /api/warehouse/revenue-records/totals/
  GET  /api/warehouse/invoice-records/
  GET  /api/warehouse/payment-records/
  GET  /api/warehouse/fraud-log-records/
  GET  /api/warehouse/fraud-log-records/unresolved/
  GET  /api/warehouse/audit-log-records/
  GET  /api/warehouse/placement-records/
  GET  /api/warehouse/report-records/
  GET  /api/warehouse/alert-records/
  GET  /api/warehouse/alert-records/active/
  GET  /api/warehouse/webhook-log-records/
  GET  /api/warehouse/notification-records/
  GET  /api/warehouse/setting-records/
  GET  /api/warehouse/api-key-log-records/
  GET  /api/warehouse/api-key-log-records/top-endpoints/
  GET  /api/warehouse/optimization-log-records/
  GET  /api/warehouse/ab-test-records/
  GET  /api/warehouse/ab-test-records/by-test/{test_id}/

  GET  /api/warehouse/health/            — full health summary
  GET  /api/warehouse/health/counts/     — per-model record counts
  POST /api/warehouse/health/ingest/     — ETL bulk ingest
  POST /api/warehouse/health/mark-processed/ — mark processed

Common query params (সব list endpoints-এ):
  ?publisher_id=PUB123
  ?start_date=2025-01-01
  ?end_date=2025-01-31
  ?is_processed=true|false
"""
from rest_framework.routers import DefaultRouter

from .views import (
    PublisherRecordViewSet,
    SiteRecordViewSet,
    AppRecordViewSet,
    AdUnitRecordViewSet,
    ImpressionRecordViewSet,
    ClickRecordViewSet,
    RevenueRecordViewSet,
    InvoiceRecordViewSet,
    PaymentRecordViewSet,
    FraudLogRecordViewSet,
    AuditLogRecordViewSet,
    AdPlacementRecordViewSet,
    ReportRecordViewSet,
    AlertRecordViewSet,
    WebhookLogRecordViewSet,
    NotificationRecordViewSet,
    SettingRecordViewSet,
    APIKeyLogRecordViewSet,
    OptimizationLogRecordViewSet,
    ABTestRecordViewSet,
    WarehouseHealthViewSet,
)

router = DefaultRouter()

# ── 20 warehouse model ViewSets ───────────────────────────────────────────────
router.register(r'publisher-records',        PublisherRecordViewSet,        basename='aw-publisher-record')
router.register(r'site-records',             SiteRecordViewSet,             basename='aw-site-record')
router.register(r'app-records',              AppRecordViewSet,              basename='aw-app-record')
router.register(r'ad-unit-records',          AdUnitRecordViewSet,           basename='aw-adunit-record')
router.register(r'impression-records',       ImpressionRecordViewSet,       basename='aw-impression-record')
router.register(r'click-records',            ClickRecordViewSet,            basename='aw-click-record')
router.register(r'revenue-records',          RevenueRecordViewSet,          basename='aw-revenue-record')
router.register(r'invoice-records',          InvoiceRecordViewSet,          basename='aw-invoice-record')
router.register(r'payment-records',          PaymentRecordViewSet,          basename='aw-payment-record')
router.register(r'fraud-log-records',        FraudLogRecordViewSet,         basename='aw-fraud-log-record')
router.register(r'audit-log-records',        AuditLogRecordViewSet,         basename='aw-audit-log-record')
router.register(r'placement-records',        AdPlacementRecordViewSet,      basename='aw-placement-record')
router.register(r'report-records',           ReportRecordViewSet,           basename='aw-report-record')
router.register(r'alert-records',            AlertRecordViewSet,            basename='aw-alert-record')
router.register(r'webhook-log-records',      WebhookLogRecordViewSet,       basename='aw-webhook-log-record')
router.register(r'notification-records',     NotificationRecordViewSet,     basename='aw-notification-record')
router.register(r'setting-records',          SettingRecordViewSet,          basename='aw-setting-record')
router.register(r'api-key-log-records',      APIKeyLogRecordViewSet,        basename='aw-api-key-log-record')
router.register(r'optimization-log-records', OptimizationLogRecordViewSet,  basename='aw-opt-log-record')
router.register(r'ab-test-records',          ABTestRecordViewSet,           basename='aw-abtest-record')

# ── Health + ETL ──────────────────────────────────────────────────────────────
router.register(r'health',                   WarehouseHealthViewSet,        basename='aw-health')

urlpatterns = router.urls
