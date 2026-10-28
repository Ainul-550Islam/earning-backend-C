# analytics_warehouse/serializers.py
"""
Analytics Warehouse Serializers — DRY refactored।

পুরনো pattern (40 বার repeated):
──────────────────────────────────
    class SiteRecordSerializer(WarehouseBaseSerializer):
        site_domain = serializers.CharField(source='site.domain', read_only=True, default='')

        class Meta(WarehouseBaseSerializer.Meta):         ← repeated 40×
            model  = SiteRecord
            fields = [...]
            read_only_fields = WarehouseBaseSerializer.Meta.read_only_fields  ← repeated 40×

নতুন pattern (factory function):
──────────────────────────────────
    SiteRecordSerializer = make_warehouse_serializer(
        SiteRecord,
        extra_fields={'site_domain': ...},
        fields=[...],
    )
"""
from rest_framework import serializers
from .models import (
    PublisherRecord, SiteRecord, AppRecord, AdUnitRecord,
    ImpressionRecord, ClickRecord, RevenueRecord,
    InvoiceRecord, PaymentRecord, FraudLogRecord,
    AuditLogRecord, AdPlacementRecord, ReportRecord,
    AlertRecord, WebhookLogRecord, NotificationRecord,
    SettingRecord, APIKeyLogRecord, OptimizationLogRecord,
    ABTestRecord,
)

# ── Shared read-only fields (defined ONCE) ────────────────────────────────────
_BASE_READONLY = ('id', 'created_at', 'updated_at', 'processed_at', 'checksum')

# ── Shared base fields (in every model) ──────────────────────────────────────
_BASE_FIELDS = [
    'id', 'publisher', 'publisher_id', 'tenant',
    'record_date', 'record_hour', 'source',
    'data', 'summary',
    'is_processed', 'processed_at', 'checksum',
    'created_at', 'updated_at',
]

_BASE_LIST_FIELDS = ['id', 'publisher_id', 'record_date', 'is_processed', 'created_at']


# ══════════════════════════════════════════════════════════════════════════════
# Base serializer (single definition)
# ══════════════════════════════════════════════════════════════════════════════

class WarehouseBaseSerializer(serializers.ModelSerializer):
    """
    All warehouse serializers extend this।
    Defines publisher_id once — not repeated 40 times।
    """
    publisher_id = serializers.CharField(
        source='publisher.publisher_id', read_only=True
    )

    class Meta:
        read_only_fields = _BASE_READONLY


# ══════════════════════════════════════════════════════════════════════════════
# Factory function — eliminates 40 repeated class Meta blocks
# ══════════════════════════════════════════════════════════════════════════════

def _make_serializer(
    model,
    fields: list,
    extra_fields: dict = None,
    list_fields: list = None,
    class_name: str = None,
):
    """
    Generates (DetailSerializer, ListSerializer) pair without repetition。

    Before (this block was written 40 times):
        class XSerializer(WarehouseBaseSerializer):
            class Meta(WarehouseBaseSerializer.Meta):
                model  = X
                fields = [...]
                read_only_fields = WarehouseBaseSerializer.Meta.read_only_fields

    After (one call per model):
        XSerializer, XListSerializer = _make_serializer(X, fields=[...])
    """
    extra_fields = extra_fields or {}
    list_fields  = list_fields  or _BASE_LIST_FIELDS

    # Build detail serializer attrs
    detail_attrs = {
        '__module__': __name__,
        **extra_fields,
        'Meta': type('Meta', (WarehouseBaseSerializer.Meta,), {
            'model':           model,
            'fields':          fields,
            'read_only_fields': _BASE_READONLY,
        }),
    }
    detail_cls = type(
        class_name or f'{model.__name__}Serializer',
        (WarehouseBaseSerializer,),
        detail_attrs,
    )

    # Build list serializer attrs
    list_attrs = {
        '__module__': __name__,
        **{k: v for k, v in extra_fields.items()},  # preserve extra fields in list too
        'Meta': type('Meta', (WarehouseBaseSerializer.Meta,), {
            'model':           model,
            'fields':          list_fields,
            'read_only_fields': _BASE_READONLY,
        }),
    }
    list_cls = type(
        f'{model.__name__}ListSerializer',
        (WarehouseBaseSerializer,),
        list_attrs,
    )
    return detail_cls, list_cls


# ══════════════════════════════════════════════════════════════════════════════
# 1. PublisherRecord
# ══════════════════════════════════════════════════════════════════════════════

PublisherRecordSerializer, PublisherRecordListSerializer = _make_serializer(
    PublisherRecord,
    fields=_BASE_FIELDS,
    list_fields=_BASE_LIST_FIELDS + ['record_hour', 'source'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SiteRecord (has extra field: site_domain)
# ══════════════════════════════════════════════════════════════════════════════

SiteRecordSerializer, SiteRecordListSerializer = _make_serializer(
    SiteRecord,
    extra_fields={
        'site_domain': serializers.CharField(
            source='site.domain', read_only=True, default=''
        ),
    },
    fields=_BASE_FIELDS + ['site', 'site_domain'],
    list_fields=_BASE_LIST_FIELDS + ['site', 'site_domain'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 3. AppRecord
# ══════════════════════════════════════════════════════════════════════════════

AppRecordSerializer, AppRecordListSerializer = _make_serializer(
    AppRecord,
    extra_fields={
        'app_name': serializers.CharField(
            source='app.app_name', read_only=True, default=''
        ),
    },
    fields=_BASE_FIELDS + ['app', 'app_name'],
    list_fields=_BASE_LIST_FIELDS + ['app', 'app_name'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 4. AdUnitRecord
# ══════════════════════════════════════════════════════════════════════════════

AdUnitRecordSerializer, AdUnitRecordListSerializer = _make_serializer(
    AdUnitRecord,
    extra_fields={
        'ad_unit_name': serializers.CharField(
            source='ad_unit.name', read_only=True, default=''
        ),
    },
    fields=_BASE_FIELDS + ['ad_unit', 'ad_unit_name'],
    list_fields=_BASE_LIST_FIELDS + ['ad_unit', 'ad_unit_name'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 5. ImpressionRecord
# ══════════════════════════════════════════════════════════════════════════════

_IMP_EXTRA = {
    'impressions': serializers.IntegerField(default=0),
    'fill_rate':   serializers.DecimalField(decimal_places=4, default=0, max_digits=6),
    'viewability': serializers.DecimalField(decimal_places=4, default=0, max_digits=6),
}

ImpressionRecordSerializer, ImpressionRecordListSerializer = _make_serializer(
    ImpressionRecord,
    extra_fields={'ad_unit': serializers.PrimaryKeyRelatedField(read_only=True), **_IMP_EXTRA},
    fields=_BASE_FIELDS + ['ad_unit', 'impressions', 'fill_rate', 'viewability'],
    list_fields=_BASE_LIST_FIELDS + ['ad_unit', 'impressions', 'fill_rate', 'viewability'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 6. ClickRecord
# ══════════════════════════════════════════════════════════════════════════════

ClickRecordSerializer, ClickRecordListSerializer = _make_serializer(
    ClickRecord,
    extra_fields={
        'ad_unit': serializers.PrimaryKeyRelatedField(read_only=True),
        'clicks':  serializers.IntegerField(default=0),
        'ctr':     serializers.DecimalField(decimal_places=4, default=0, max_digits=6),
    },
    fields=_BASE_FIELDS + ['ad_unit', 'clicks', 'ctr'],
    list_fields=_BASE_LIST_FIELDS + ['ad_unit', 'clicks', 'ctr'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 7. RevenueRecord
# ══════════════════════════════════════════════════════════════════════════════

_REV_EXTRA = {
    'gross_revenue': serializers.DecimalField(decimal_places=6, default=0, max_digits=14),
    'net_revenue':   serializers.DecimalField(decimal_places=6, default=0, max_digits=14),
    'ecpm':          serializers.DecimalField(decimal_places=4, default=0, max_digits=10),
    'currency':      serializers.CharField(default='USD', max_length=3),
}

RevenueRecordSerializer, RevenueRecordListSerializer = _make_serializer(
    RevenueRecord,
    extra_fields=_REV_EXTRA,
    fields=_BASE_FIELDS + ['gross_revenue', 'net_revenue', 'ecpm', 'currency'],
    list_fields=_BASE_LIST_FIELDS + ['gross_revenue', 'net_revenue', 'ecpm', 'currency'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 8. InvoiceRecord
# ══════════════════════════════════════════════════════════════════════════════

InvoiceRecordSerializer, InvoiceRecordListSerializer = _make_serializer(
    InvoiceRecord,
    extra_fields={
        'invoice': serializers.PrimaryKeyRelatedField(read_only=True),
        'amount':  serializers.DecimalField(decimal_places=2, default=0, max_digits=14),
        'currency':serializers.CharField(default='USD', max_length=3),
        'status':  serializers.CharField(default='pending', max_length=20),
    },
    fields=_BASE_FIELDS + ['invoice', 'amount', 'currency', 'status'],
    list_fields=_BASE_LIST_FIELDS + ['invoice', 'amount', 'currency', 'status'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 9. PaymentRecord
# ══════════════════════════════════════════════════════════════════════════════

PaymentRecordSerializer, PaymentRecordListSerializer = _make_serializer(
    PaymentRecord,
    extra_fields={
        'amount':  serializers.DecimalField(decimal_places=2, default=0, max_digits=14),
        'currency':serializers.CharField(default='USD', max_length=3),
        'method':  serializers.CharField(blank=True, max_length=50, required=False),
        'status':  serializers.CharField(default='pending', max_length=20),
    },
    fields=_BASE_FIELDS + ['amount', 'currency', 'method', 'status'],
    list_fields=_BASE_LIST_FIELDS + ['amount', 'currency', 'method', 'status'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 10. FraudLogRecord
# ══════════════════════════════════════════════════════════════════════════════

FraudLogRecordSerializer, FraudLogRecordListSerializer = _make_serializer(
    FraudLogRecord,
    extra_fields={
        'fraud_type':  serializers.CharField(max_length=50),
        'fraud_score': serializers.IntegerField(default=0),
        'ip_address':  serializers.IPAddressField(allow_null=True, required=False),
        'action':      serializers.CharField(allow_blank=True, max_length=50, required=False),
        'resolved':    serializers.BooleanField(default=False),
    },
    fields=_BASE_FIELDS + ['fraud_type', 'fraud_score', 'ip_address', 'action', 'resolved'],
    list_fields=_BASE_LIST_FIELDS + ['fraud_type', 'fraud_score', 'action', 'resolved'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 11. AuditLogRecord
# ══════════════════════════════════════════════════════════════════════════════

AuditLogRecordSerializer, AuditLogRecordListSerializer = _make_serializer(
    AuditLogRecord,
    extra_fields={
        'action':      serializers.CharField(max_length=100),
        'actor_id':    serializers.CharField(allow_blank=True, max_length=50, required=False),
        'object_type': serializers.CharField(allow_blank=True, max_length=100, required=False),
        'object_id':   serializers.CharField(allow_blank=True, max_length=50, required=False),
        'ip_address':  serializers.IPAddressField(allow_null=True, required=False),
    },
    fields=_BASE_FIELDS + ['action', 'actor_id', 'object_type', 'object_id', 'ip_address'],
    list_fields=_BASE_LIST_FIELDS + ['action', 'actor_id', 'object_type', 'object_id'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 12. AdPlacementRecord
# ══════════════════════════════════════════════════════════════════════════════

AdPlacementRecordSerializer, AdPlacementRecordListSerializer = _make_serializer(
    AdPlacementRecord,
    extra_fields={
        'placement':   serializers.PrimaryKeyRelatedField(read_only=True),
        'impressions': serializers.IntegerField(default=0),
        'revenue':     serializers.DecimalField(decimal_places=6, default=0, max_digits=14),
        'viewability': serializers.DecimalField(decimal_places=4, default=0, max_digits=6),
    },
    fields=_BASE_FIELDS + ['placement', 'impressions', 'revenue', 'viewability'],
    list_fields=_BASE_LIST_FIELDS + ['placement', 'impressions', 'revenue', 'viewability'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 13. ReportRecord
# ══════════════════════════════════════════════════════════════════════════════

ReportRecordSerializer, ReportRecordListSerializer = _make_serializer(
    ReportRecord,
    extra_fields={
        'report_type': serializers.CharField(max_length=50),
        'report_name': serializers.CharField(allow_blank=True, max_length=200, required=False),
        'period':      serializers.CharField(allow_blank=True, max_length=20, required=False),
        'file_url':    serializers.URLField(allow_blank=True, required=False),
        'status':      serializers.CharField(default='pending', max_length=20),
    },
    fields=_BASE_FIELDS + ['report_type', 'report_name', 'period', 'file_url', 'status'],
    list_fields=_BASE_LIST_FIELDS + ['report_type', 'report_name', 'period', 'status', 'file_url'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 14. AlertRecord
# ══════════════════════════════════════════════════════════════════════════════

AlertRecordSerializer, AlertRecordListSerializer = _make_serializer(
    AlertRecord,
    extra_fields={
        'alert_type':  serializers.CharField(max_length=50),
        'severity':    serializers.CharField(default='info', max_length=20),
        'message':     serializers.CharField(allow_blank=True, required=False),
        'resolved':    serializers.BooleanField(default=False),
        'resolved_at': serializers.DateTimeField(allow_null=True, required=False),
    },
    fields=_BASE_FIELDS + ['alert_type', 'severity', 'message', 'resolved', 'resolved_at'],
    list_fields=_BASE_LIST_FIELDS + ['alert_type', 'severity', 'message', 'resolved'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 15. WebhookLogRecord
# ══════════════════════════════════════════════════════════════════════════════

WebhookLogRecordSerializer, WebhookLogRecordListSerializer = _make_serializer(
    WebhookLogRecord,
    extra_fields={
        'event_type':    serializers.CharField(max_length=100),
        'endpoint_url':  serializers.URLField(allow_blank=True, required=False),
        'status':        serializers.CharField(default='pending', max_length=20),
        'response_code': serializers.IntegerField(allow_null=True, required=False),
        'attempt':       serializers.IntegerField(default=1),
    },
    fields=_BASE_FIELDS + ['event_type', 'endpoint_url', 'status', 'response_code', 'attempt'],
    list_fields=_BASE_LIST_FIELDS + ['event_type', 'status', 'response_code', 'attempt'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 16. NotificationRecord
# ══════════════════════════════════════════════════════════════════════════════

NotificationRecordSerializer, NotificationRecordListSerializer = _make_serializer(
    NotificationRecord,
    extra_fields={
        'notification_type': serializers.CharField(max_length=50),
        'title':   serializers.CharField(allow_blank=True, max_length=200, required=False),
        'is_read': serializers.BooleanField(default=False),
        'read_at': serializers.DateTimeField(allow_null=True, required=False),
    },
    fields=_BASE_FIELDS + ['notification_type', 'title', 'is_read', 'read_at'],
    list_fields=_BASE_LIST_FIELDS + ['notification_type', 'title', 'is_read'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 17. SettingRecord
# ══════════════════════════════════════════════════════════════════════════════

SettingRecordSerializer, SettingRecordListSerializer = _make_serializer(
    SettingRecord,
    extra_fields={
        'setting_key':   serializers.CharField(max_length=200),
        'setting_value': serializers.JSONField(default=dict),
        'changed_by':    serializers.CharField(allow_blank=True, max_length=50, required=False),
    },
    fields=_BASE_FIELDS + ['setting_key', 'setting_value', 'changed_by'],
    list_fields=_BASE_LIST_FIELDS + ['setting_key', 'changed_by'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 18. APIKeyLogRecord
# ══════════════════════════════════════════════════════════════════════════════

APIKeyLogRecordSerializer, APIKeyLogRecordListSerializer = _make_serializer(
    APIKeyLogRecord,
    extra_fields={
        'api_key_prefix': serializers.CharField(max_length=20),
        'endpoint':       serializers.CharField(allow_blank=True, max_length=200, required=False),
        'method':         serializers.CharField(default='GET', max_length=10),
        'response_code':  serializers.IntegerField(allow_null=True, required=False),
        'requests_count': serializers.IntegerField(default=0),
    },
    fields=_BASE_FIELDS + ['api_key_prefix', 'endpoint', 'method', 'response_code', 'requests_count'],
    list_fields=_BASE_LIST_FIELDS + ['api_key_prefix', 'endpoint', 'method', 'response_code', 'requests_count'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 19. OptimizationLogRecord
# ══════════════════════════════════════════════════════════════════════════════

OptimizationLogRecordSerializer, OptimizationLogRecordListSerializer = _make_serializer(
    OptimizationLogRecord,
    extra_fields={
        'optimization_type': serializers.CharField(max_length=50),
        'target_id':         serializers.CharField(allow_blank=True, max_length=50, required=False),
        'before_value':      serializers.JSONField(default=dict),
        'after_value':       serializers.JSONField(default=dict),
        'uplift_pct':        serializers.DecimalField(decimal_places=2, max_digits=6, allow_null=True, required=False),
        'applied':           serializers.BooleanField(default=False),
    },
    fields=_BASE_FIELDS + ['optimization_type', 'target_id', 'before_value', 'after_value', 'uplift_pct', 'applied'],
    list_fields=_BASE_LIST_FIELDS + ['optimization_type', 'target_id', 'uplift_pct', 'applied'],
)


# ══════════════════════════════════════════════════════════════════════════════
# 20. ABTestRecord
# ══════════════════════════════════════════════════════════════════════════════

ABTestRecordSerializer, ABTestRecordListSerializer = _make_serializer(
    ABTestRecord,
    extra_fields={
        'ab_test':          serializers.PrimaryKeyRelatedField(read_only=True),
        'test_type':        serializers.CharField(allow_blank=True, max_length=20, required=False),
        'variant_name':     serializers.CharField(allow_blank=True, max_length=100, required=False),
        'is_control':       serializers.BooleanField(default=False),
        'impressions':      serializers.IntegerField(default=0),
        'revenue':          serializers.DecimalField(decimal_places=6, default=0, max_digits=14),
        'ecpm':             serializers.DecimalField(decimal_places=4, default=0, max_digits=10),
        'confidence_level': serializers.DecimalField(decimal_places=2, max_digits=5, allow_null=True, required=False),
    },
    fields=_BASE_FIELDS + ['ab_test', 'test_type', 'variant_name', 'is_control', 'impressions', 'revenue', 'ecpm', 'confidence_level'],
    list_fields=_BASE_LIST_FIELDS + ['ab_test', 'test_type', 'variant_name', 'is_control', 'impressions', 'revenue', 'ecpm', 'confidence_level'],
)


# ══════════════════════════════════════════════════════════════════════════════
# ETL + Health serializers (no change needed — already DRY)
# ══════════════════════════════════════════════════════════════════════════════

class WarehouseIngestSerializer(serializers.Serializer):
    RECORD_TYPE_CHOICES = [
        'publisher', 'site', 'app', 'ad_unit',
        'impression', 'click', 'revenue', 'invoice', 'payment',
        'fraud_log', 'audit_log', 'ad_placement',
        'report', 'alert', 'webhook_log', 'notification',
        'setting', 'api_key_log', 'optimization_log', 'ab_test',
    ]
    record_type  = serializers.ChoiceField(choices=RECORD_TYPE_CHOICES)
    publisher_id = serializers.CharField(max_length=50)
    records      = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=1000,
    )
    dry_run = serializers.BooleanField(default=False)


class WarehouseMarkProcessedSerializer(serializers.Serializer):
    record_type = serializers.CharField(max_length=50)
    ids         = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=5000
    )


class WarehouseSummarySerializer(serializers.Serializer):
    total_records         = serializers.IntegerField()
    processed_records     = serializers.IntegerField()
    unprocessed_records   = serializers.IntegerField()
    processing_rate_pct   = serializers.FloatField()
    oldest_unprocessed    = serializers.DateField(allow_null=True)
    record_counts_by_type = serializers.DictField(child=serializers.IntegerField())
    last_updated          = serializers.DateTimeField()
