# analytics_warehouse/admin.py
"""
Admin registration for analytics_warehouse models.
Uses the 'analytics' DB via AnalyticsRouter.
"""
from django.contrib import admin
from .models import (
    PublisherRecord, SiteRecord, AppRecord, AdUnitRecord,
    ImpressionRecord, ClickRecord, RevenueRecord,
    InvoiceRecord, PaymentRecord, FraudLogRecord,
    AuditLogRecord, AdPlacementRecord, ReportRecord,
    AlertRecord, WebhookLogRecord, NotificationRecord,
    SettingRecord, APIKeyLogRecord, OptimizationLogRecord,
    ABTestRecord,
)

# ── Shared base admin ─────────────────────────────────────────────────────────

class WarehouseModelAdmin(admin.ModelAdmin):
    """Base admin for all warehouse models — read-only in admin."""
    readonly_fields = ('id', 'created_at', 'updated_at', 'processed_at', 'checksum')
    list_per_page   = 50
    date_hierarchy  = 'record_date'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PublisherRecord)
class PublisherRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'record_hour', 'source', 'is_processed')
    list_filter   = ('is_processed', 'source')
    search_fields = ('publisher__publisher_id',)


@admin.register(SiteRecord)
class SiteRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'site', 'record_date', 'is_processed')
    list_filter   = ('is_processed',)
    search_fields = ('publisher__publisher_id', 'site__domain')


@admin.register(AppRecord)
class AppRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'app', 'record_date', 'is_processed')
    list_filter   = ('is_processed',)
    search_fields = ('publisher__publisher_id',)


@admin.register(AdUnitRecord)
class AdUnitRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'ad_unit', 'record_date', 'is_processed')
    list_filter   = ('is_processed',)
    search_fields = ('publisher__publisher_id',)


@admin.register(ImpressionRecord)
class ImpressionRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'impressions', 'fill_rate', 'viewability', 'is_processed')
    list_filter   = ('is_processed',)
    search_fields = ('publisher__publisher_id',)


@admin.register(ClickRecord)
class ClickRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'clicks', 'ctr', 'is_processed')
    list_filter   = ('is_processed',)
    search_fields = ('publisher__publisher_id',)


@admin.register(RevenueRecord)
class RevenueRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'gross_revenue', 'net_revenue', 'ecpm', 'currency', 'is_processed')
    list_filter   = ('is_processed', 'currency')
    search_fields = ('publisher__publisher_id',)


@admin.register(InvoiceRecord)
class InvoiceRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'amount', 'currency', 'status', 'is_processed')
    list_filter   = ('status', 'is_processed')
    search_fields = ('publisher__publisher_id',)


@admin.register(PaymentRecord)
class PaymentRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'amount', 'currency', 'method', 'status', 'is_processed')
    list_filter   = ('status', 'is_processed')
    search_fields = ('publisher__publisher_id',)


@admin.register(FraudLogRecord)
class FraudLogRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'fraud_type', 'fraud_score', 'action', 'resolved')
    list_filter   = ('fraud_type', 'resolved')
    search_fields = ('publisher__publisher_id', 'ip_address')


@admin.register(AuditLogRecord)
class AuditLogRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'action', 'actor_id', 'object_type')
    list_filter   = ('action',)
    search_fields = ('publisher__publisher_id', 'actor_id')


@admin.register(ReportRecord)
class ReportRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'report_type', 'report_name', 'status')
    list_filter   = ('report_type', 'status')
    search_fields = ('publisher__publisher_id', 'report_name')


@admin.register(AlertRecord)
class AlertRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'alert_type', 'severity', 'resolved')
    list_filter   = ('alert_type', 'severity', 'resolved')
    search_fields = ('publisher__publisher_id',)


@admin.register(ABTestRecord)
class ABTestRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'test_type', 'variant_name', 'is_control', 'ecpm')
    list_filter   = ('test_type', 'is_control')
    search_fields = ('publisher__publisher_id',)


@admin.register(OptimizationLogRecord)
class OptimizationLogRecordAdmin(WarehouseModelAdmin):
    list_display  = ('publisher', 'record_date', 'optimization_type', 'uplift_pct', 'applied')
    list_filter   = ('optimization_type', 'applied')
    search_fields = ('publisher__publisher_id',)
