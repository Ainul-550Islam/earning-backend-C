# analytics_warehouse/models.py
"""
Analytics Warehouse Models.

publisher_tools/database_models/ থেকে migrate করা হয়েছে।
এই সব models একটি আলাদা analytics read-replica DB-এ store হয়।

DB: settings.DATABASES['analytics']  (configured via AnalyticsRouter)

প্রতিটি Record model একটি নির্দিষ্ট event type track করে।
সব model-এর common pattern:
  - publisher FK (publisher_tools.Publisher)
  - record_date + record_hour (time partitioning)
  - data + summary JSONField (flexible schema)
  - is_processed flag (ETL pipeline status)
  - checksum (deduplication)
"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


# ── Shared mixin ──────────────────────────────────────────────────────────────

class WarehouseRecordMixin(TimeStampedModel):
    """
    Base mixin for all analytics warehouse records.
    Provides common fields and mark_processed() helper.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
    )
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        db_index=True,
    )
    record_date  = models.DateField(db_index=True)
    record_hour  = models.IntegerField(null=True, blank=True)
    data         = models.JSONField(default=dict, blank=True, verbose_name=_('Record Data'))
    summary      = models.JSONField(default=dict, blank=True, verbose_name=_('Summary Metrics'))
    source       = models.CharField(max_length=50, default='api', verbose_name=_('Data Source'))
    is_processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    checksum     = models.CharField(max_length=64, blank=True)

    class Meta:
        abstract = True

    def mark_processed(self) -> None:
        """ETL pipeline দ্বারা processed হলে call করা হয়।"""
        import hashlib
        import json
        from django.utils import timezone
        self.is_processed = True
        self.processed_at = timezone.now()
        self.checksum = hashlib.md5(
            json.dumps(self.data, sort_keys=True, default=str).encode()
        ).hexdigest()
        self.save(update_fields=['is_processed', 'processed_at', 'checksum', 'updated_at'])


# ==============================================================================
# WAREHOUSE RECORD MODELS (20 types)
# ==============================================================================

class PublisherRecord(WarehouseRecordMixin):
    """Publisher-level daily/hourly aggregate."""
    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_publisher_records'
        verbose_name        = _('Publisher Record')
        verbose_name_plural = _('Publisher Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_pub_date_01'),
            models.Index(fields=['is_processed'],             name='aw_idx_pub_proc_02'),
        ]

    def __str__(self):
        return f'Publisher: {self.publisher_id} — {self.record_date}'


class SiteRecord(WarehouseRecordMixin):
    """Site-level performance record."""
    site = models.ForeignKey(
        'publisher_tools.Site',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_site_records'
        verbose_name        = _('Site Record')
        verbose_name_plural = _('Site Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['site', 'record_date'], name='aw_idx_site_date_03'),
            models.Index(fields=['is_processed'],        name='aw_idx_site_proc_04'),
        ]

    def __str__(self):
        return f'Site: {self.site_id} — {self.record_date}'


class AppRecord(WarehouseRecordMixin):
    """App-level performance record."""
    app = models.ForeignKey(
        'publisher_tools.App',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_app_records'
        verbose_name        = _('App Record')
        verbose_name_plural = _('App Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['app', 'record_date'], name='aw_idx_app_date_05'),
            models.Index(fields=['is_processed'],       name='aw_idx_app_proc_06'),
        ]

    def __str__(self):
        return f'App: {self.app_id} — {self.record_date}'


class AdUnitRecord(WarehouseRecordMixin):
    """Ad unit performance record."""
    ad_unit = models.ForeignKey(
        'publisher_tools.AdUnit',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_ad_unit_records'
        verbose_name        = _('Ad Unit Record')
        verbose_name_plural = _('Ad Unit Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['ad_unit', 'record_date'], name='aw_idx_adunit_date_07'),
            models.Index(fields=['is_processed'],           name='aw_idx_adunit_proc_08'),
        ]

    def __str__(self):
        return f'AdUnit: {self.ad_unit_id} — {self.record_date}'


class ImpressionRecord(WarehouseRecordMixin):
    """Raw impression events."""
    ad_unit = models.ForeignKey(
        'publisher_tools.AdUnit',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='impression_records',
    )
    impressions   = models.BigIntegerField(default=0)
    fill_rate     = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))
    viewability   = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_impression_records'
        verbose_name        = _('Impression Record')
        verbose_name_plural = _('Impression Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_imp_date_09'),
            models.Index(fields=['is_processed'],             name='aw_idx_imp_proc_10'),
        ]

    def __str__(self):
        return f'Impression: {self.publisher_id} — {self.record_date}'


class ClickRecord(WarehouseRecordMixin):
    """Click events."""
    ad_unit = models.ForeignKey(
        'publisher_tools.AdUnit',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='click_records',
    )
    clicks = models.BigIntegerField(default=0)
    ctr    = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_click_records'
        verbose_name        = _('Click Record')
        verbose_name_plural = _('Click Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_click_date_11'),
            models.Index(fields=['is_processed'],             name='aw_idx_click_proc_12'),
        ]

    def __str__(self):
        return f'Click: {self.publisher_id} — {self.record_date}'


class RevenueRecord(WarehouseRecordMixin):
    """Revenue aggregate records."""
    gross_revenue = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    net_revenue   = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    ecpm          = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))
    currency      = models.CharField(max_length=3, default='USD')

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_revenue_records'
        verbose_name        = _('Revenue Record')
        verbose_name_plural = _('Revenue Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_rev_date_13'),
            models.Index(fields=['is_processed'],             name='aw_idx_rev_proc_14'),
        ]

    def __str__(self):
        return f'Revenue: {self.publisher_id} — {self.record_date}'


class InvoiceRecord(WarehouseRecordMixin):
    """Invoice events."""
    invoice = models.ForeignKey(
        'publisher_tools.PublisherInvoice',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )
    amount   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='USD')
    status   = models.CharField(max_length=20, default='pending', db_index=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_invoice_records'
        verbose_name        = _('Invoice Record')
        verbose_name_plural = _('Invoice Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_inv_date_15'),
            models.Index(fields=['status'],                   name='aw_idx_inv_status_16'),
        ]

    def __str__(self):
        return f'Invoice: {self.publisher_id} — {self.record_date}'


class PaymentRecord(WarehouseRecordMixin):
    """Payment payout records."""
    amount   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='USD')
    method   = models.CharField(max_length=50, blank=True)
    status   = models.CharField(max_length=20, default='pending', db_index=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_payment_records'
        verbose_name        = _('Payment Record')
        verbose_name_plural = _('Payment Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_pay_date_17'),
            models.Index(fields=['status'],                   name='aw_idx_pay_status_18'),
        ]

    def __str__(self):
        return f'Payment: {self.publisher_id} — {self.record_date}'


class FraudLogRecord(WarehouseRecordMixin):
    """Fraud detection events."""
    fraud_type  = models.CharField(max_length=50, db_index=True)
    fraud_score = models.IntegerField(default=0)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    action      = models.CharField(max_length=50, blank=True)
    resolved    = models.BooleanField(default=False, db_index=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_fraud_log_records'
        verbose_name        = _('Fraud Log Record')
        verbose_name_plural = _('Fraud Log Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_fraud_date_19'),
            models.Index(fields=['fraud_type'],               name='aw_idx_fraud_type_20'),
            models.Index(fields=['resolved'],                 name='aw_idx_fraud_res_21'),
        ]

    def __str__(self):
        return f'Fraud: {self.fraud_type} — {self.publisher_id} — {self.record_date}'


class AuditLogRecord(WarehouseRecordMixin):
    """Admin action audit trail."""
    action      = models.CharField(max_length=100, db_index=True)
    actor_id    = models.CharField(max_length=50, blank=True)
    object_type = models.CharField(max_length=100, blank=True)
    object_id   = models.CharField(max_length=50, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_audit_log_records'
        verbose_name        = _('Audit Log Record')
        verbose_name_plural = _('Audit Log Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['action'],                   name='aw_idx_audit_action_22'),
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_audit_date_23'),
        ]

    def __str__(self):
        return f'Audit: {self.action} by {self.actor_id} — {self.record_date}'


class AdPlacementRecord(WarehouseRecordMixin):
    """Ad placement performance."""
    placement = models.ForeignKey(
        'publisher_tools.AdPlacement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )
    impressions   = models.BigIntegerField(default=0)
    revenue       = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    viewability   = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_placement_records'
        verbose_name        = _('Placement Record')
        verbose_name_plural = _('Placement Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_place_date_24'),
            models.Index(fields=['placement'],                name='aw_idx_place_id_25'),
        ]

    def __str__(self):
        return f'Placement: {self.placement_id} — {self.record_date}'


class ReportRecord(WarehouseRecordMixin):
    """Generated report metadata."""
    report_type = models.CharField(max_length=50, db_index=True)
    report_name = models.CharField(max_length=200, blank=True)
    period      = models.CharField(max_length=20, blank=True)
    file_url    = models.URLField(blank=True)
    status      = models.CharField(max_length=20, default='pending', db_index=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_report_records'
        verbose_name        = _('Report Record')
        verbose_name_plural = _('Report Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'report_type'], name='aw_idx_rpt_type_26'),
            models.Index(fields=['status'],                   name='aw_idx_rpt_status_27'),
        ]

    def __str__(self):
        return f'Report: {self.report_type} — {self.publisher_id} — {self.record_date}'


class AlertRecord(WarehouseRecordMixin):
    """System alerts and notifications."""
    alert_type = models.CharField(max_length=50, db_index=True)
    severity   = models.CharField(max_length=20, default='info', db_index=True)
    message    = models.TextField(blank=True)
    resolved   = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_alert_records'
        verbose_name        = _('Alert Record')
        verbose_name_plural = _('Alert Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'alert_type'], name='aw_idx_alert_type_28'),
            models.Index(fields=['severity', 'resolved'],    name='aw_idx_alert_sev_29'),
        ]

    def __str__(self):
        return f'Alert: {self.alert_type} [{self.severity}] — {self.record_date}'


class WebhookLogRecord(WarehouseRecordMixin):
    """Webhook delivery history for analytics."""
    event_type    = models.CharField(max_length=100, db_index=True)
    endpoint_url  = models.URLField(blank=True)
    status        = models.CharField(max_length=20, default='pending', db_index=True)
    response_code = models.IntegerField(null=True, blank=True)
    attempt       = models.IntegerField(default=1)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_webhook_log_records'
        verbose_name        = _('Webhook Log Record')
        verbose_name_plural = _('Webhook Log Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'event_type'], name='aw_idx_wh_event_30'),
            models.Index(fields=['status'],                  name='aw_idx_wh_status_31'),
        ]

    def __str__(self):
        return f'Webhook: {self.event_type} [{self.status}] — {self.record_date}'


class NotificationRecord(WarehouseRecordMixin):
    """In-app notifications sent to publishers."""
    notification_type = models.CharField(max_length=50, db_index=True)
    title             = models.CharField(max_length=200, blank=True)
    is_read           = models.BooleanField(default=False, db_index=True)
    read_at           = models.DateTimeField(null=True, blank=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_notification_records'
        verbose_name        = _('Notification Record')
        verbose_name_plural = _('Notification Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'is_read'],        name='aw_idx_notif_read_32'),
            models.Index(fields=['notification_type'],           name='aw_idx_notif_type_33'),
        ]

    def __str__(self):
        return f'Notification: {self.notification_type} — {self.publisher_id}'


class SettingRecord(WarehouseRecordMixin):
    """Configuration change history."""
    setting_key   = models.CharField(max_length=200, db_index=True)
    setting_value = models.JSONField(default=dict, blank=True)
    changed_by    = models.CharField(max_length=50, blank=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_setting_records'
        verbose_name        = _('Setting Record')
        verbose_name_plural = _('Setting Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'setting_key'], name='aw_idx_setting_key_34'),
        ]

    def __str__(self):
        return f'Setting: {self.setting_key} — {self.publisher_id}'


class APIKeyLogRecord(WarehouseRecordMixin):
    """API key usage log."""
    api_key_prefix = models.CharField(max_length=20, db_index=True)
    endpoint       = models.CharField(max_length=200, blank=True)
    method         = models.CharField(max_length=10, default='GET')
    response_code  = models.IntegerField(null=True, blank=True)
    requests_count = models.BigIntegerField(default=0)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_api_key_log_records'
        verbose_name        = _('API Key Log Record')
        verbose_name_plural = _('API Key Log Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'],    name='aw_idx_apilog_date_35'),
            models.Index(fields=['api_key_prefix'],              name='aw_idx_apilog_key_36'),
        ]

    def __str__(self):
        return f'APIKey: {self.api_key_prefix} — {self.record_date}'


class OptimizationLogRecord(WarehouseRecordMixin):
    """Yield optimization event history."""
    optimization_type = models.CharField(max_length=50, db_index=True)
    target_id         = models.CharField(max_length=50, blank=True)
    before_value      = models.JSONField(default=dict, blank=True)
    after_value       = models.JSONField(default=dict, blank=True)
    uplift_pct        = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    applied           = models.BooleanField(default=False, db_index=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_optimization_log_records'
        verbose_name        = _('Optimization Log Record')
        verbose_name_plural = _('Optimization Log Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'optimization_type'], name='aw_idx_optlog_type_37'),
            models.Index(fields=['applied'],                        name='aw_idx_optlog_applied_38'),
        ]

    def __str__(self):
        return f'Optimization: {self.optimization_type} — {self.publisher_id} — {self.record_date}'


class ABTestRecord(WarehouseRecordMixin):
    """A/B test result snapshots."""
    ab_test = models.ForeignKey(
        'publisher_tools.ABTest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='warehouse_records',
    )
    test_type          = models.CharField(max_length=20, blank=True, db_index=True)
    variant_name       = models.CharField(max_length=100, blank=True)
    is_control         = models.BooleanField(default=False)
    impressions        = models.BigIntegerField(default=0)
    revenue            = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    ecpm               = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))
    confidence_level   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta(WarehouseRecordMixin.Meta):
        app_label           = 'analytics_warehouse'
        db_table            = 'aw_ab_test_records'
        verbose_name        = _('A/B Test Record')
        verbose_name_plural = _('A/B Test Records')
        ordering            = ['-record_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'record_date'], name='aw_idx_abtest_date_39'),
            models.Index(fields=['test_type'],                name='aw_idx_abtest_type_40'),
        ]

    def __str__(self):
        return f'ABTest: {self.test_type} — {self.variant_name} — {self.record_date}'
